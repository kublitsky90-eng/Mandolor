# guild_characters.py
import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

from telegram import Update
from telegram.ext import ContextTypes

from .utils import logger, escape_markdown, load_json_file, save_json_file
from .admin import is_admin

# ========== Настройки Comlink ==========
COMLINK_URL = "http://185.72.144.142:3200"

# Файл для кэширования данных персонажей
CHARACTERS_CACHE_FILE = os.path.join("data", "characters_cache.json")
GAME_DATA_CACHE_FILE = os.path.join("data", "game_data_cache.json")

# Глобальные переменные для кэша
_characters_cache = {}
_game_data_cache = {}

# ========== Загрузка кэша ==========
def load_caches():
    """Загружает кэши из файлов"""
    global _characters_cache, _game_data_cache
    
    # Загружаем кэш персонажей
    if os.path.exists(CHARACTERS_CACHE_FILE):
        try:
            with open(CHARACTERS_CACHE_FILE, 'r', encoding='utf-8') as f:
                _characters_cache = json.load(f)
            logger.info(f"Загружен кэш персонажей: {len(_characters_cache)} записей")
        except Exception as e:
            logger.error(f"Ошибка загрузки кэша персонажей: {e}")
            _characters_cache = {}
    
    # Загружаем кэш игровых данных
    if os.path.exists(GAME_DATA_CACHE_FILE):
        try:
            with open(GAME_DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                _game_data_cache = json.load(f)
            logger.info("Загружен кэш игровых данных")
        except Exception as e:
            logger.error(f"Ошибка загрузки кэша игровых данных: {e}")
            _game_data_cache = {}

def save_character_cache():
    """Сохраняет кэш персонажей в файл"""
    try:
        with open(CHARACTERS_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(_characters_cache, f, indent=2, ensure_ascii=False)
        logger.info("Кэш персонажей сохранен")
    except Exception as e:
        logger.error(f"Ошибка сохранения кэша персонажей: {e}")

def save_game_data_cache():
    """Сохраняет игровые данные в файл"""
    try:
        with open(GAME_DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(_game_data_cache, f, indent=2, ensure_ascii=False)
        logger.info("Кэш игровых данных сохранен")
    except Exception as e:
        logger.error(f"Ошибка сохранения кэша игровых данных: {e}")

# ========== Инициализация Comlink клиента ==========
def get_comlink_client():
    """Создает и возвращает клиент Comlink"""
    try:
        from swgoh_comlink import SwgohComlink
        return SwgohComlink(url=COMLINK_URL)
    except ImportError:
        logger.error("Библиотека swgoh_comlink не установлена")
        return None
    except Exception as e:
        logger.error(f"Ошибка подключения к Comlink: {e}")
        return None

def get_game_data(force_update: bool = False):
    """Получает игровые данные (с кэшированием)"""
    global _game_data_cache
    
    if not force_update and _game_data_cache:
        return _game_data_cache
    
    comlink = get_comlink_client()
    if not comlink:
        return None
    
    try:
        logger.info("Запрос игровых данных из Comlink...")
        game_data = comlink.get_game_data()
        
        _game_data_cache = game_data
        save_game_data_cache()
        
        logger.info("Игровые данные успешно получены")
        return game_data
    except Exception as e:
        logger.error(f"Ошибка получения игровых данных: {e}")
        return _game_data_cache if _game_data_cache else None

def get_character_list(force_update: bool = False) -> List[Dict[str, Any]]:
    """Получает список всех персонажей из игровых данных"""
    global _characters_cache
    
    if not force_update and _characters_cache.get('characters'):
        return _characters_cache['characters']
    
    game_data = get_game_data(force_update)
    if not game_data:
        return []
    
    characters = []
    
    try:
        # Персонажи находятся в game_data['character_list']
        if 'character_list' in game_data:
            for char_id, char_data in game_data['character_list'].items():
                character = {
                    'id': char_id,
                    'name': char_data.get('name', char_id),
                    'base_id': char_data.get('base_id', char_id),
                    'power': char_data.get('power', 0),
                    'alignment': char_data.get('alignment', 'unknown'),
                    'combat_type': char_data.get('combat_type', 1),  # 1 = character, 2 = ship
                }
                
                # Получаем дополнительную информацию
                if 'skill_data' in char_data:
                    character['skills'] = len(char_data.get('skill_data', {}))
                
                characters.append(character)
        
        # Сортируем по имени
        characters.sort(key=lambda x: x['name'].lower())
        
        _characters_cache['characters'] = characters
        _characters_cache['last_update'] = datetime.now().isoformat()
        save_character_cache()
        
        logger.info(f"Загружено {len(characters)} персонажей")
        return characters
        
    except Exception as e:
        logger.error(f"Ошибка парсинга списка персонажей: {e}")
        return []

def search_character(query: str) -> Optional[Dict[str, Any]]:
    """Ищет персонажа по имени или ID"""
    characters = get_character_list()
    if not characters:
        return None
    
    query_lower = query.lower().strip()
    
    # Точное совпадение по имени
    for char in characters:
        if char['name'].lower() == query_lower:
            return char
    
    # Частичное совпадение
    matches = [char for char in characters if query_lower in char['name'].lower()]
    
    if matches:
        return matches[0]
    
    return None

def get_player_info(allycode: int) -> Optional[Dict[str, Any]]:
    """Получает информацию об игроке по allycode"""
    comlink = get_comlink_client()
    if not comlink:
        return None
    
    try:
        logger.info(f"Запрос информации об игроке {allycode}...")
        player_data = comlink.get_player(allycode=allycode)
        return player_data
    except Exception as e:
        logger.error(f"Ошибка получения игрока {allycode}: {e}")
        return None

def format_character_info(character: Dict[str, Any]) -> str:
    """Форматирует информацию о персонаже для вывода"""
    message = f"🎭 *{escape_markdown(character['name'])}*\n"
    message += f"━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # Основная информация
    message += f"📋 **ID:** `{character['id']}`\n"
    
    # Альянс
    alignment = character.get('alignment', 'unknown')
    alignment_emoji = {
        'light': '⚪',
        'dark': '⚫',
        'neutral': '🟡',
        'unknown': '❓'
    }.get(alignment, '❓')
    message += f"{alignment_emoji} **Альянс:** {alignment.capitalize()}\n"
    
    # Тип
    combat_type = character.get('combat_type', 1)
    type_str = "👤 Персонаж" if combat_type == 1 else "🚀 Корабль"
    message += f"**Тип:** {type_str}\n"
    
    # Сила (GP)
    if character.get('power', 0) > 0:
        power = character['power']
        message += f"⚔️ **Базовая сила:** {power:,}\n".replace(',', ' ')
    
    # Количество способностей
    if character.get('skills', 0) > 0:
        message += f"✨ **Способностей:** {character['skills']}\n"
    
    return message

# ========== Команды Telegram ==========
async def unit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Поиск информации о персонаже по имени"""
    if not context.args:
        await update.message.reply_text(
            "❌ Укажите имя персонажа.\n"
            "Примеры:\n"
            "/unit Darth Vader\n"
            "/unit Rey\n"
            "/unit B1\n\n"
            "💡 Поддерживаются как полные имена, так и сокращения."
        )
        return
    
    query = ' '.join(context.args).strip()
    
    # Отправляем сообщение о начале поиска
    status_msg = await update.message.reply_text(f"🔍 Ищу персонажа *{escape_markdown(query)}*...", parse_mode='Markdown')
    
    character = search_character(query)
    
    if not character:
        await status_msg.edit_text(
            f"❌ Персонаж *{escape_markdown(query)}* не найден.\n\n"
            f"💡 Попробуйте использовать:\n"
            f"• Полное имя персонажа\n"
            f"• Часть имени\n"
            f"• /unit_info для поиска по дополнительным параметрам",
            parse_mode='Markdown'
        )
        return
    
    # Форматируем информацию
    message = format_character_info(character)
    
    await status_msg.edit_text(message, parse_mode='Markdown')
    logger.info(f"Пользователь @{update.effective_user.username} запросил персонажа: {query} -> {character['name']}")

async def unit_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Расширенная информация о персонаже (с поиском по игрокам)"""
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Неправильный формат команды.\n\n"
            "📝 **Способы использования:**\n\n"
            "1️⃣ **Поиск персонажа у игрока:**\n"
            "`/unit_info @username имя_персонажа`\n"
            "Пример: `/unit_info @KuBiK90 Darth Vader`\n\n"
            "2️⃣ **Поиск персонажа по allycode:**\n"
            "`/unit_info allycode имя_персонажа`\n"
            "Пример: `/unit_info 245866537 Rey`\n\n"
            "3️⃣ **Поиск информации о персонаже:**\n"
            "`/unit_info имя_персонажа`\n"
            "Пример: `/unit_info Jedi Master Kenobi`\n\n"
            "💡 Игрок должен быть привязан к Telegram через команду /add",
            parse_mode='Markdown'
        )
        return
    
    # Определяем тип запроса
    first_arg = context.args[0]
    character_name = ' '.join(context.args[1:]) if len(context.args) > 1 else ''
    
    # Запрос только персонажа (без привязки к игроку)
    if len(context.args) == 1:
        character_name = first_arg
        character = search_character(character_name)
        
        if not character:
            await update.message.reply_text(f"❌ Персонаж *{escape_markdown(character_name)}* не найден.", parse_mode='Markdown')
            return
        
        message = format_character_info(character)
        await update.message.reply_text(message, parse_mode='Markdown')
        return
    
    # Запрос персонажа у конкретного игрока
    character = search_character(character_name)
    if not character:
        await update.message.reply_text(f"❌ Персонаж *{escape_markdown(character_name)}* не найден.", parse_mode='Markdown')
        return
    
    # Определяем игрока
    player_identifier = first_arg
    allycode = None
    telegram_username = None
    
    if player_identifier.startswith('@'):
        telegram_username = player_identifier[1:]
    elif player_identifier.isdigit() and len(player_identifier) >= 8:
        allycode = int(player_identifier)
    else:
        await update.message.reply_text(
            "❌ Неверный формат идентификатора игрока.\n"
            "Используйте:\n"
            "• @username - для поиска по Telegram\n"
            "• allycode - для поиска по коду (9 цифр)",
            parse_mode='Markdown'
        )
        return
    
    status_msg = await update.message.reply_text(
        f"🔍 Ищу персонажа *{escape_markdown(character['name'])}* у игрока...",
        parse_mode='Markdown'
    )
    
    # Получаем данные игрока
    player_data = None
    
    if allycode:
        player_data = get_player_info(allycode)
    elif telegram_username:
        # Ищем игрока по привязке Telegram
        from .admin import get_nickname
        nicknames = load_json_file('data/nicknames.json', {})
        
        player_name = None
        for name, tg_username in nicknames.items():
            if tg_username == telegram_username:
                player_name = name
                break
        
        if player_name:
            # Получаем данные гильдии и ищем игрока
            from .data_handlers import parse_guild_data
            result = parse_guild_data()
            if 'success' in result:
                for player in result['players_raw']:
                    if player['player_name'] == player_name:
                        player_allycode = player.get('ally_code')
                        if player_allycode:
                            player_data = get_player_info(player_allycode)
                        break
    
    if not player_data:
        await status_msg.edit_text(
            f"❌ Не удалось найти игрока.\n\n"
            f"💡 Убедитесь, что:\n"
            f"• Игрок привязан к Telegram через команду /add\n"
            f"• Allycode указан верно\n"
            f"• Данные гильдии обновлены (/update)",
            parse_mode='Markdown'
        )
        return
    
    # Ищем персонажа в ростре игрока
    roster = player_data.get('rosterUnit', [])
    found_unit = None
    
    for unit in roster:
        unit_def_id = unit.get('definitionId', '')
        unit_name = unit.get('definitionId', '').lower()
        
        if character['id'].lower() in unit_def_id.lower() or character['name'].lower() in unit_name:
            found_unit = unit
            break
    
    if not found_unit:
        await status_msg.edit_text(
            f"❌ У игрока *{escape_markdown(player_data.get('name', 'Неизвестно'))}* не найден персонаж *{escape_markdown(character['name'])}*.\n\n"
            f"💡 Возможно, персонаж:\n"
            f"• Еще не разблокирован\n"
            f"• Имеет другое имя в игре",
            parse_mode='Markdown'
        )
        return
    
    # Формируем подробную информацию о персонаже у игрока
    message = f"🎭 *{escape_markdown(character['name'])}* у игрока *{escape_markdown(player_data.get('name', 'Неизвестно'))}*\n"
    message += f"━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # Характеристики персонажа
    gp = found_unit.get('gp', 0)
    if gp > 0:
        message += f"⚔️ **GP:** {gp:,}\n".replace(',', ' ')
    
    rarity = found_unit.get('rarity', 0)
    if rarity > 0:
        message += f"⭐ **Звездность:** {rarity}/7\n"
    
    level = found_unit.get('level', 0)
    if level > 0:
        message += f"📊 **Уровень:** {level}/85\n"
    
    gear = found_unit.get('gear', 0)
    if gear > 0:
        message += f"🔧 **Уровень снаряжения:** {gear}/13\n"
    
    # Релики
    relic_tier = found_unit.get('relic', {}).get('tier', 0) if 'relic' in found_unit else 0
    if relic_tier > 0:
        message += f"💎 **Реликвия:** {relic_tier}\n"
    
    # Моды
    mods = found_unit.get('mods', [])
    if mods:
        mods_count = len(mods)
        message += f"💿 **Модов:** {mods_count}/6\n"
    
    # Способности
    skills = found_unit.get('skills', [])
    if skills:
        skill_names = []
        for skill in skills[:4]:  # Показываем первые 4 способности
            skill_tier = skill.get('tier', 0)
            if skill_tier > 0:
                skill_names.append(f"Ур. {skill_tier}")
        
        if skill_names:
            message += f"✨ **Способности:** {', '.join(skill_names)}\n"
    
    # Звания (для отрядов)
    if 'reputation' in found_unit:
        rep = found_unit['reputation']
        message += f"🏅 **Репутация:** Уровень {rep}\n"
    
    await status_msg.edit_text(message, parse_mode='Markdown')
    logger.info(f"Пользователь @{update.effective_user.username} запросил инфо о {character['name']} у игрока {player_data.get('name')}")

async def load_characters_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Принудительная загрузка списка персонажей (только для админов)"""
    username = update.effective_user.username
    if not username or not is_admin(username):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    status_msg = await update.message.reply_text("🔄 Загружаю список персонажей из Comlink...\nЭто может занять несколько секунд...")
    
    characters = get_character_list(force_update=True)
    
    if characters:
        await status_msg.edit_text(
            f"✅ Загружено {len(characters)} персонажей.\n"
            f"🕒 Кэш обновлен: {datetime.now().strftime('%Y-%Y-%m-%d %H:%M:%S')}\n\n"
            f"Теперь можно использовать команды:\n"
            f"/unit - поиск персонажа\n"
            f"/unit_info - расширенная информация"
        )
    else:
        await status_msg.edit_text(
            "❌ Не удалось загрузить список персонажей.\n\n"
            "Проверьте:\n"
            "• Доступность Comlink сервера\n"
            "• Правильность URL в настройках"
        )

# ========== Инициализация при запуске ==========
load_caches()

# Если кэш пуст, загружаем данные в фоне (при первом вызове)
if not _characters_cache:
    logger.info("Кэш персонажей пуст, данные будут загружены при первом запросе")