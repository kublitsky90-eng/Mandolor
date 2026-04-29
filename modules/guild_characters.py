# modules/guild_characters.py
import json
import os
from telegram import Update
from telegram.ext import ContextTypes

from .utils import (
    logger, load_json_file, JSON_FILE_PATH, DATA_FOLDER
)
from .admin import is_admin


# ========== Функции для работы с данными игроков ==========
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


def download_player_data(ally_code):
    """Скачивает данные игрока по ally_code"""
    import requests
    
    url = f"https://swgoh.gg/api/player/{ally_code}/"
    headers = {
		"Host": "swgoh.gg",
		"Connection": "keep-alive",
		"sec-ch-ua": "\"Not:A-Brand\";v=\"99\", \"Microsoft Edge\";v=\"145\", \"Chromium\";v=\"145\"",
		"sec-ch-ua-mobile": "?0",
		"sec-ch-ua-platform": "\"Windows\"",
		"Upgrade-Insecure-Requests": "1",
		"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0",
		"Accept": "application/json, text/plain, */*",
		"Sec-Fetch-Site": "same-origin",
		"Sec-Fetch-Mode": "cors",
		"Sec-Fetch-Dest": "empty",
		"Accept-Encoding": "gzip, deflate, br, zstd",
		"Accept-Language": "ru,en;q=0.9,en-GB;q=0.8,en-US;q=0.7",
		"Referer": "https://swgoh.gg/",
		"Origin": "https://swgoh.gg"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"Ошибка загрузки {ally_code}: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Ошибка при загрузке {ally_code}: {e}")
        return None


def find_character_in_player(player_data, character_name):
    """Ищет персонажа в данных игрока"""
    if not player_data or 'data' not in player_data:
        return None
    
    units = player_data.get('data', {}).get('units', [])
    
    for unit in units:
        unit_data = unit.get('data', {})
        if unit_data.get('name', '').lower() == character_name.lower():
            return {
                'name': unit_data.get('name'),
                'gear_level': unit_data.get('gear_level', 0),
                'relic_tier': unit_data.get('relic_tier'),
                'level': unit_data.get('level', 0),
                'power': unit_data.get('power', 0),
                'rarity': unit_data.get('rarity', 0),
                'zeta_abilities': len(unit_data.get('zeta_abilities', [])),
                'has_ultimate': unit_data.get('has_ultimate', False),
                'is_galactic_legend': unit_data.get('is_galactic_legend', False)
            }
    return None


def scan_all_players_for_character(character_name):
    """Сканирует всех игроков гильдии в поисках указанного персонажа"""
    players = get_player_ally_codes()
    results = []
    
    for player in players:
        ally_code = player['ally_code']
        player_name = player['player_name']
        
        logger.info(f"Проверяю игрока {player_name} ({ally_code})...")
        player_data = download_player_data(ally_code)
        
        if player_data:
            character_data = find_character_in_player(player_data, character_name)
            if character_data:
                results.append({
                    'player_name': player_name,
                    'ally_code': ally_code,
                    'character': character_data
                })
    
    return results


# ========== Команды ==========
async def unit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ищет указанного персонажа у всех игроков гильдии"""
    username = update.effective_user.username
    
    if not context.args:
        await update.message.reply_text(
            "❌ Укажите имя персонажа.\n"
            "Пример: /unit General Hux\n"
            "Пример: /unit Darth Vader\n\n"
            "Имя персонажа должно быть на английском языке, как в игре."
        )
        return
    
    character_name = ' '.join(context.args).strip()
    
    # Проверяем, что данные гильдии загружены
    if not os.path.exists(JSON_FILE_PATH):
        await update.message.reply_text(
            "❌ Файл с данными гильдии не найден.\n"
            "Сначала выполните команду /update для загрузки данных."
        )
        return
    
    status_message = await update.message.reply_text(
        f"🔍 Ищу персонажа *{character_name}* среди всех игроков гильдии...\n"
        f"Это может занять некоторое время (около 2-3 секунд на игрока).\n"
        f"Всего игроков: {len(get_player_ally_codes())}",
        parse_mode='Markdown'
    )
    
    try:
        results = scan_all_players_for_character(character_name)
        
        if not results:
            await status_message.edit_text(
                f"❌ Персонаж *{character_name}* не найден ни у одного из {len(get_player_ally_codes())} игроков гильдии.\n\n"
                f"💡 Проверьте правильность написания имени персонажа.\n"
                f"Имя должно быть на английском, как в игре (например: 'General Hux', 'Darth Vader', 'Rey').",
                parse_mode='Markdown'
            )
            return
        
        # Формируем ответ
        message = f"🔍 *Результаты поиска персонажа '{character_name}':*\n\n"
        message += f"Найден у {len(results)} игроков:\n\n"
        
        for i, result in enumerate(results, 1):
            player_name = result['player_name']
            char_data = result['character']
            gear_level = char_data.get('gear_level', 'N/A')
            relic_tier = char_data.get('relic_tier', 'N/A')
            power = char_data.get('power', 'N/A')
            level = char_data.get('level', 'N/A')
            zeta_count = char_data.get('zeta_abilities', 0)
            is_gl = char_data.get('is_galactic_legend', False)
            
            gl_marker = " 👑" if is_gl else ""
            
            message += f"{i}. *{player_name}*{gl_marker}\n"
            message += f"   ⚔️ Уровень: {level}\n"
            message += f"   🛡️ Снаряжение: {gear_level}\n"
            if relic_tier and relic_tier > 0:
                message += f"   💎 Реликвия: {relic_tier}\n"
            message += f"   📊 Сила: {power:,}\n".replace(',', ' ')
            if zeta_count > 0:
                message += f"   ✨ Зета-способности: {zeta_count}\n"
            message += "\n"
        
        # Если сообщение слишком длинное, разбиваем на части
        if len(message) > 4000:
            # Отправляем короткую версию с количеством
            short_message = f"🔍 *Результаты поиска персонажа '{character_name}':*\n\n"
            short_message += f"✅ Найден у {len(results)} игроков.\n\n"
            short_message += "Список игроков:\n"
            for i, result in enumerate(results, 1):
                short_message += f"{i}. {result['player_name']}\n"
            
            await status_message.edit_text(short_message, parse_mode='Markdown')
            
            # Отправляем детали отдельным файлом
            details = f"Детальный поиск персонажа '{character_name}'\n"
            details += "=" * 50 + "\n\n"
            for result in results:
                player_name = result['player_name']
                char_data = result['character']
                details += f"Игрок: {player_name}\n"
                details += f"Уровень: {char_data.get('level', 'N/A')}\n"
                details += f"Снаряжение: {char_data.get('gear_level', 'N/A')}\n"
                details += f"Реликвия: {char_data.get('relic_tier', 'N/A')}\n"
                details += f"Сила: {char_data.get('power', 'N/A'):,}\n".replace(',', ' ')
                details += "-" * 30 + "\n"
            
            with open(f"{DATA_FOLDER}/unit_search_{character_name.replace(' ', '_')}.txt", 'w', encoding='utf-8') as f:
                f.write(details)
            
            await update.message.reply_document(
                document=open(f"{DATA_FOLDER}/unit_search_{character_name.replace(' ', '_')}.txt", 'rb'),
                filename=f"unit_{character_name.replace(' ', '_')}.txt",
                caption=f"📄 Детальная информация по персонажу '{character_name}'"
            )
        else:
            await status_message.edit_text(message, parse_mode='Markdown')
        
        logger.info(f"Пользователь @{username} выполнил поиск персонажа '{character_name}', найдено {len(results)} результатов")
        
    except Exception as e:
        logger.error(f"Ошибка при поиске персонажа: {e}")
        await status_message.edit_text(
            f"❌ Произошла ошибка при поиске персонажа.\n"
            f"Причина: {str(e)[:200]}"
        )


async def unit_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает информацию о конкретном юните у конкретного игрока"""
    username = update.effective_user.username
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Укажите игрока и персонажа.\n"
            "Пример: /unit_info Qbik General Hux\n\n"
            "Имя игрока можно взять из команды /guild.\n"
            "Имя персонажа должно быть на английском языке."
        )
        return
    
    # Разделяем аргументы: первые N - имя игрока, последующие - имя персонажа
    # Ищем игрока среди всех аргументов - для простоты используем первый аргумент как имя игрока
    player_name = context.args[0]
    character_name = ' '.join(context.args[1:]).strip()
    
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
            # Поиск по частичному совпадению
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
            f"🔍 Загружаю данные игрока *{actual_player_name}*...",
            parse_mode='Markdown'
        )
        
        player_data = download_player_data(ally_code)
        
        if not player_data:
            await status_message.edit_text(
                f"❌ Не удалось загрузить данные игрока *{actual_player_name}*.",
                parse_mode='Markdown'
            )
            return
        
        character_data = find_character_in_player(player_data, character_name)
        
        if not character_data:
            await status_message.edit_text(
                f"❌ У игрока *{actual_player_name}* не найден персонаж *{character_name}*.\n\n"
                f"💡 Проверьте правильность написания имени персонажа.",
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
        message += f"⚔️ *Персонаж:* {character_name}{gl_marker}{ultimate_marker}\n"
        message += f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        message += f"📈 *Характеристики:*\n"
        message += f"• Уровень: {level}\n"
        message += f"• Снаряжение: {gear_level}\n"
        if relic_tier and relic_tier > 0:
            message += f"• Реликвия: {relic_tier}\n"
        message += f"• Сила: {power:,}\n".replace(',', ' ')
        message += f"• Звездность: {rarity}\n"
        message += f"• Зета-способности: {zeta_count}\n"
        
        await status_message.edit_text(message, parse_mode='Markdown')
        
        logger.info(f"Пользователь @{username} запросил информацию о персонаже {character_name} у игрока {actual_player_name}")
        
    except Exception as e:
        logger.error(f"Ошибка при получении информации о персонаже: {e}")
        await update.message.reply_text(
            f"❌ Произошла ошибка.\n"
            f"Причина: {str(e)[:200]}"
        )