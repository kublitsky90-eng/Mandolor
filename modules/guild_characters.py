import json
import os
import time
import asyncio
import aiohttp
from typing import Optional, Dict, Any
from telegram import Update
from telegram.ext import ContextTypes

from .utils import (
    logger, JSON_FILE_PATH, DATA_FOLDER, REQUEST_HEADERS
)
from .character_mapping import normalize_character_name


# ========== Настройки ==========
MAX_CONCURRENT_REQUESTS = 3  # Максимум параллельных запросов
REQUEST_DELAY = 1.5  # Задержка между запросами (секунды)
MAX_RETRIES = 3  # Максимум повторных попыток


async def fetch_player_data_async(session: aiohttp.ClientSession, ally_code: int, retry: int = 0) -> Optional[Dict]:
    """Асинхронная загрузка данных игрока с swgoh.gg"""
    url = f"https://swgoh.gg/api/player/{ally_code}/"
    
    headers = {
        **REQUEST_HEADERS,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ru,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
    }
    
    try:
        # Добавляем случайную задержку между запросами
        await asyncio.sleep(REQUEST_DELAY * (retry + 0.5))
        
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as response:
            status = response.status
            
            if status == 403:
                logger.warning(f"403 Forbidden для {ally_code}, попытка {retry + 1}/{MAX_RETRIES}")
                if retry < MAX_RETRIES - 1:
                    await asyncio.sleep(3 * (retry + 1))  # Экспоненциальная задержка
                    return await fetch_player_data_async(session, ally_code, retry + 1)
                return None
            
            if status == 404:
                logger.warning(f"404 Not Found для {ally_code}")
                return None
            
            if status != 200:
                logger.warning(f"Статус {status} для {ally_code}")
                if retry < MAX_RETRIES - 1:
                    await asyncio.sleep(2)
                    return await fetch_player_data_async(session, ally_code, retry + 1)
                return None
            
            # Проверяем Content-Type
            content_type = response.headers.get('Content-Type', '')
            if 'application/json' not in content_type:
                # Может быть HTML от Cloudflare
                text = await response.text()
                if 'cloudflare' in text.lower() or 'ddos' in text.lower():
                    logger.warning(f"Cloudflare защита для {ally_code}")
                    if retry < MAX_RETRIES - 1:
                        await asyncio.sleep(5)
                        return await fetch_player_data_async(session, ally_code, retry + 1)
                return None
            
            data = await response.json()
            
            # Проверяем валидность данных
            if not data or 'data' not in data:
                logger.warning(f"Невалидные данные для {ally_code}")
                return None
            
            return data
            
    except asyncio.TimeoutError:
        logger.warning(f"Таймаут для {ally_code}")
        if retry < MAX_RETRIES - 1:
            await asyncio.sleep(2)
            return await fetch_player_data_async(session, ally_code, retry + 1)
        return None
    except aiohttp.ClientError as e:
        logger.error(f"Клиентская ошибка для {ally_code}: {e}")
        return None
    except Exception as e:
        logger.error(f"Ошибка для {ally_code}: {e}")
        return None


async def get_players_data_batch(players: list, progress_callback=None) -> list:
    """Пакетная загрузка данных игроков с ограничением по параллельным запросам"""
    results = []
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    
    # Создаём сессию с куками
    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT_REQUESTS, ttl_dns_cache=300)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        # Сначала получаем главную страницу для установки кук
        try:
            async with session.get('https://swgoh.gg/', headers=REQUEST_HEADERS) as resp:
                logger.info(f"Главная страница: {resp.status}")
        except Exception as e:
            logger.warning(f"Не удалось загрузить главную страницу: {e}")
        
        tasks = []
        for idx, player in enumerate(players):
            async def fetch_with_semaphore(p, i):
                async with semaphore:
                    logger.info(f"[{i+1}/{len(players)}] Загружаю {p['player_name']}...")
                    data = await fetch_player_data_async(session, p['ally_code'])
                    
                    if progress_callback:
                        await progress_callback(i, len(players), p['player_name'], data is not None)
                    
                    return {
                        'player_name': p['player_name'],
                        'ally_code': p['ally_code'],
                        'data': data
                    }
            
            tasks.append(fetch_with_semaphore(player, idx))
        
        results = await asyncio.gather(*tasks)
    
    return results


def get_player_ally_codes():
    """Извлекает ally_code всех игроков из guild_data.json"""
    if not os.path.exists(JSON_FILE_PATH):
        return []
    
    try:
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            guild_data = json.load(f)
        
        members = guild_data.get('data', {}).get('members', [])
        ally_codes = []
        
        for member in members:
            ally_code = member.get('ally_code')
            player_name = member.get('player_name', 'Unknown')
            if ally_code:
                ally_codes.append({
                    'ally_code': ally_code,
                    'player_name': player_name
                })
        
        logger.info(f"Найдено {len(ally_codes)} игроков с ally_code")
        return ally_codes
        
    except Exception as e:
        logger.error(f"Ошибка при получении ally_code: {e}")
        return []


def find_character_in_player(player_data, character_name):
    """Ищет персонажа в данных игрока с поддержкой маппинга"""
    if not player_data or 'data' not in player_data:
        return None
    
    units = player_data.get('data', {}).get('units', [])
    search_name_lower = character_name.lower()
    
    for unit in units:
        unit_data = unit.get('data', {})
        unit_name = unit_data.get('name', '')
        unit_base_id = unit_data.get('base_id', '')
        
        # Точное совпадение по имени
        if unit_name.lower() == search_name_lower:
            logger.info(f"Найден точный match: {unit_name}")
            return _extract_character_data(unit_data, unit_name)
        
        # Частичное совпадение по имени
        if search_name_lower in unit_name.lower():
            logger.info(f"Найден частичный match: {unit_name}")
            return _extract_character_data(unit_data, unit_name)
        
        # Поиск по base_id
        if search_name_lower in unit_base_id.lower():
            logger.info(f"Найден match по base_id: {unit_base_id}")
            return _extract_character_data(unit_data, unit_name)
        
        # Поиск по имени без скобок и кавычек
        clean_name = unit_name.split('(')[0].split('"')[0].strip().lower()
        if search_name_lower == clean_name:
            logger.info(f"Найден clean name match: {clean_name}")
            return _extract_character_data(unit_data, unit_name)
    
    return None


def _extract_character_data(unit_data, unit_name):
    """Извлекает данные персонажа"""
    return {
        'name': unit_name,
        'gear_level': unit_data.get('gear_level', 0),
        'relic_tier': unit_data.get('relic_tier'),
        'level': unit_data.get('level', 0),
        'power': unit_data.get('power', 0),
        'rarity': unit_data.get('rarity', 0),
        'zeta_abilities': len(unit_data.get('zeta_abilities', [])),
        'has_ultimate': unit_data.get('has_ultimate', False),
        'is_galactic_legend': unit_data.get('is_galactic_legend', False)
    }


async def scan_all_players_for_character_async(character_name, status_message=None, update=None):
    """Асинхронно сканирует всех игроков гильдии в поисках указанного персонажа"""
    players = get_player_ally_codes()
    total = len(players)
    normalized_name = normalize_character_name(character_name)
    
    logger.info(f"Поиск персонажа: '{character_name}' -> нормализовано: '{normalized_name}'")
    
    results = []
    failed_players = []
    
    async def progress_callback(idx, total, player_name, success):
        if status_message and idx % 5 == 0:  # Обновляем статус каждые 5 игроков
            try:
                await status_message.edit_text(
                    f"🔍 Ищу персонажа *{normalized_name}*\n"
                    f"📊 Прогресс: {idx+1}/{total}\n"
                    f"✅ Найдено: {len(results)}\n"
                    f"❌ Ошибок: {len(failed_players)}\n\n"
                    f"⏳ Пожалуйста, подождите...",
                    parse_mode='Markdown'
                )
            except:
                pass
    
    # Загружаем данные всех игроков
    players_data = await get_players_data_batch(players, progress_callback)
    
    # Обрабатываем результаты
    for player_data in players_data:
        if player_data['data']:
            character_data = find_character_in_player(player_data['data'], normalized_name)
            
            if not character_data:
                character_data = find_character_in_player(player_data['data'], character_name)
            
            if character_data:
                results.append({
                    'player_name': player_data['player_name'],
                    'ally_code': player_data['ally_code'],
                    'character': character_data
                })
                logger.info(f"  ✅ Найден {character_data['name']} у {player_data['player_name']}")
        else:
            failed_players.append(player_data['player_name'])
            logger.info(f"  ❌ Не удалось загрузить данные для {player_data['player_name']}")
    
    return results, failed_players


# ========== Команды ==========
async def unit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ищет указанного персонажа у всех игроков гильдии (асинхронная версия)"""
    username = update.effective_user.username
    
    if not context.args:
        await update.message.reply_text(
            "❌ Укажите имя персонажа.\n"
            "Пример: /unit General Hux\n"
            "Пример: /unit Lord Vader\n\n"
            "💡 Можно использовать сокращения:\n"
            "• /unit LV - Lord Vader\n"
            "• /unit JMK - Jedi Master Kenobi\n"
            "• /unit SLKR - Supreme Leader Kylo Ren"
        )
        return
    
    character_name = ' '.join(context.args).strip()
    normalized_name = normalize_character_name(character_name)
    
    # Проверяем, что данные гильдии загружены
    if not os.path.exists(JSON_FILE_PATH):
        await update.message.reply_text(
            "❌ Файл с данными гильдии не найден.\n"
            "Сначала выполните команду /update для загрузки данных."
        )
        return
    
    players = get_player_ally_codes()
    total_players = len(players)
    
    if total_players == 0:
        await update.message.reply_text(
            "❌ Не удалось найти ally_code игроков.\n"
            "Проверьте, что файл guild_data.json содержит корректные данные."
        )
        return
    
    status_message = await update.message.reply_text(
        f"🔍 Ищу персонажа *{normalized_name}*...\n"
        f"📊 Всего игроков: {total_players}\n"
        f"⚙️ Режим: асинхронный ({MAX_CONCURRENT_REQUESTS} запросов одновременно)\n\n"
        f"⏳ Начинаю поиск..."
    )
    
    try:
        results, failed_players = await scan_all_players_for_character_async(
            character_name, 
            status_message, 
            update
        )
        
        if not results:
            fail_note = ""
            if failed_players:
                fail_note = f"\n\n⚠️ Не удалось загрузить данные для {len(failed_players)} игроков.\n"
                fail_note += "Возможно, swgoh.gg временно недоступен."
            
            await status_message.edit_text(
                f"❌ Персонаж *{normalized_name}* не найден ни у одного из {total_players} игроков.{fail_note}\n\n"
                f"💡 Попробуйте:\n"
                f"• Другое написание или сокращение\n"
                f"• Подождать несколько минут (защита Cloudflare)\n"
                f"• /unit_info [игрок] [персонаж] для конкретного игрока"
            )
            return
        
        # Формируем ответ
        message = f"🔍 *Результаты поиска '{normalized_name}':*\n\n"
        message += f"✅ Найден у {len(results)} из {total_players} игроков:\n\n"
        
        for i, result in enumerate(results, 1):
            player_name = result['player_name']
            char_data = result['character']
            gear_level = char_data.get('gear_level', 'N/A')
            relic_tier = char_data.get('relic_tier', 'N/A')
            power = char_data.get('power', 'N/A')
            zeta_count = char_data.get('zeta_abilities', 0)
            is_gl = char_data.get('is_galactic_legend', False)
            
            gl_marker = " 👑" if is_gl else ""
            relic_str = f" 💎{relic_tier}" if relic_tier and relic_tier > 0 else ""
            
            message += f"{i}. *{player_name}*{gl_marker}\n"
            message += f"   🛡️{gear_level}{relic_str} | 📊 {power:,}\n".replace(',', ' ')
            if zeta_count > 0:
                message += f"   ✨ Зета: {zeta_count}\n"
            message += "\n"
            
            # Если сообщение становится слишком длинным
            if len(message) > 3500:
                message += f"\n... и ещё {len(results) - i} игроков"
                break
        
        if failed_players:
            message += f"\n⚠️ Не удалось проверить {len(failed_players)} игроков из-за ограничений сервера."
        
        await status_message.edit_text(message, parse_mode='Markdown')
        
        logger.info(f"Поиск '{character_name}': найдено {len(results)} результатов, ошибок {len(failed_players)}")
        
    except Exception as e:
        logger.error(f"Ошибка при поиске: {e}", exc_info=True)
        await status_message.edit_text(
            f"❌ Ошибка: {str(e)[:200]}\n\n"
            f"Попробуйте позже или используйте /unit_info для конкретного игрока."
        )


async def unit_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает информацию о конкретном юните у конкретного игрока (синхронная версия для одного игрока)"""
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Укажите игрока и персонажа.\n"
            "Пример: /unit_info Qbik General Hux\n"
            "Пример: /unit_info Qbik LV\n\n"
            "Имя игрока можно взять из команды /guild"
        )
        return
    
    player_name = context.args[0]
    character_name = ' '.join(context.args[1:]).strip()
    normalized_name = normalize_character_name(character_name)
    
    # Получаем ally_code игрока
    if not os.path.exists(JSON_FILE_PATH):
        await update.message.reply_text(
            "❌ Файл с данными гильдии не найден.\n"
            "Сначала выполните команду /update для загрузки данных."
        )
        return
    
    try:
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            guild_data = json.load(f)
        
        members = guild_data.get('data', {}).get('members', [])
        ally_code = None
        actual_player_name = player_name
        
        for member in members:
            if member.get('player_name', '').lower() == player_name.lower():
                ally_code = member.get('ally_code')
                actual_player_name = member.get('player_name')
                break
        
        if not ally_code:
            matches = [m.get('player_name') for m in members if player_name.lower() in m.get('player_name', '').lower()]
            if matches:
                await update.message.reply_text(
                    f"❌ Игрок \"{player_name}\" не найден.\n\n"
                    f"💡 Возможно, вы имели в виду:\n" + "\n".join([f"• {name}" for name in matches[:5]])
                )
            else:
                await update.message.reply_text(
                    f"❌ Игрок \"{player_name}\" не найден.\n"
                    f"Используйте /guild для просмотра списка всех игроков."
                )
            return
        
        status_message = await update.message.reply_text(
            f"🔍 Загружаю данные игрока *{actual_player_name}* (ally_code: {ally_code})...",
            parse_mode='Markdown'
        )
        
        player_data = download_player_data(ally_code)
        
        if not player_data:
            await status_message.edit_text(
                f"❌ Не удалось загрузить данные игрока *{actual_player_name}*.\n\n"
                f"Возможные причины:\n"
                f"• Нет соединения с swgoh.gg\n"
                f"• Сайт временно недоступен\n"
                f"• Неверный ally_code",
                parse_mode='Markdown'
            )
            return
        
        # Пробуем найти по нормализованному имени
        character_data = find_character_in_player(player_data, normalized_name)
        
        # Если не нашли, пробуем по оригинальному
        if not character_data:
            character_data = find_character_in_player(player_data, character_name)
        
        if not character_data:
            await status_message.edit_text(
                f"❌ У игрока *{actual_player_name}* не найден персонаж *{character_name}*.\n\n"
                f"💡 Проверьте правильность написания или используйте /unit для поиска.",
                parse_mode='Markdown'
            )
            return
        
        # Формируем детальную информацию
        gear_level = character_data.get('gear_level', 'N/A')
        relic_tier = character_data.get('relic_tier', 'N/A')
        power = character_data.get('power', 'N/A')
        level = character_data.get('level', 'N/A')
        rarity = character_data.get('rarity', 'N/A')
        zeta_count = character_data.get('zeta_abilities', 0)
        is_gl = character_data.get('is_galactic_legend', False)
        has_ultimate = character_data.get('has_ultimate', False)
        
        gl_marker = " 👑 Галактическая Легенда" if is_gl else ""
        ultimate_marker = " 🔥 Ультимейт разблокирован" if has_ultimate else ""
        
        message = f"📊 *Информация о персонаже*\n\n"
        message += f"👤 *Игрок:* {actual_player_name}\n"
        message += f"⚔️ *Персонаж:* {character_data['name']}{gl_marker}{ultimate_marker}\n"
        message += f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        message += f"📈 *Характеристики:*\n"
        message += f"• Уровень: {level}\n"
        message += f"• Снаряжение: {gear_level}\n"
        if relic_tier and relic_tier > 0:
            message += f"• Реликвия: {relic_tier}\n"
        message += f"• Сила: {power:,}\n".replace(',', ' ')
        message += f"• Звездность: {rarity}/7\n"
        message += f"• Зета-способности: {zeta_count}\n"
        
        await status_message.edit_text(message, parse_mode='Markdown')
        
        logger.info(f"Запрошена информация о {character_name} у игрока {actual_player_name}")
        
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ Ошибка: {str(e)[:200]}"
        )