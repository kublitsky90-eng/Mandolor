import requests
import json
import logging
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# URL для скачивания JSON
GUILD_URL = "https://swgoh.gg/api/guild-profile/j16DZ27ZQWe7UqWJP90zjg/"

# Создаем папку для сохранения файлов
DATA_FOLDER = "data"
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

JSON_FILE_PATH = os.path.join(DATA_FOLDER, 'guild_data.json')
PLAYERS_LIST_FILE = os.path.join(DATA_FOLDER, 'players_list.txt')
ADMINS_FILE = os.path.join(DATA_FOLDER, 'admins.json')
NICKNAMES_FILE = os.path.join(DATA_FOLDER, 'nicknames.json')
ROLES_FILE = os.path.join(DATA_FOLDER, 'roles.json')

# Заголовки из вашего браузера (адаптированные для swgoh.gg)
REQUEST_HEADERS = {
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

# ========== Функции работы с файлами ==========
def load_json_file(file_path, default=None):
    """Загружает JSON из файла"""
    if not os.path.exists(file_path):
        return default if default is not None else {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return default if default is not None else {}

def save_json_file(file_path, data):
    """Сохраняет JSON в файл"""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ========== Функции для работы с админами ==========
def normalize_username(username):
    """Убирает @ в начале, если есть, но сохраняет регистр"""
    if not username:
        return None
    if username.startswith('@'):
        username = username[1:]
    return username

def is_admin(username):
    """Проверяет, является ли пользователь админом по username (точное сравнение)"""
    if not username:
        return False
    
    normalized_username = normalize_username(username)
    if not normalized_username:
        return False
    
    admins = load_json_file(ADMINS_FILE, [])
    return normalized_username in admins

def add_admin(username):
    """Добавляет админа по username (сохраняет исходный регистр)"""
    normalized_username = normalize_username(username)
    if not normalized_username:
        return False
    
    admins = load_json_file(ADMINS_FILE, [])
    if normalized_username not in admins:
        admins.append(normalized_username)
        save_json_file(ADMINS_FILE, admins)
        return True
    return False

def remove_admin(username):
    """Удаляет админа по username (точное сравнение)"""
    normalized_username = normalize_username(username)
    if not normalized_username:
        return False
    
    admins = load_json_file(ADMINS_FILE, [])
    if normalized_username in admins:
        admins.remove(normalized_username)
        save_json_file(ADMINS_FILE, admins)
        return True
    return False

# ========== Функции для работы с ролями ==========
def set_role(player_name, role):
    """Устанавливает роль для игрока"""
    roles = load_json_file(ROLES_FILE, {})
    roles[player_name] = role
    save_json_file(ROLES_FILE, roles)

def get_role(player_name):
    """Получает роль игрока"""
    roles = load_json_file(ROLES_FILE, {})
    return roles.get(player_name, "Воины Мандалора")  # По умолчанию "Воины Мандалора"

def remove_role(player_name):
    """Удаляет роль (возвращает к стандартной)"""
    roles = load_json_file(ROLES_FILE, {})
    if player_name in roles:
        del roles[player_name]
        save_json_file(ROLES_FILE, roles)
        return True
    return False

# ========== Функции для работы с привязками ников ==========
def add_nickname(player_name, telegram_username):
    """Добавляет привязку ника игрока к Telegram username"""
    if telegram_username.startswith('@'):
        telegram_username = telegram_username[1:]
    
    nicknames = load_json_file(NICKNAMES_FILE, {})
    nicknames[player_name] = telegram_username
    save_json_file(NICKNAMES_FILE, nicknames)

def remove_nickname(player_name):
    """Удаляет привязку ника игрока"""
    nicknames = load_json_file(NICKNAMES_FILE, {})
    if player_name in nicknames:
        del nicknames[player_name]
        save_json_file(NICKNAMES_FILE, nicknames)
        return True
    return False

def get_nickname(player_name):
    """Получает Telegram username для игрока"""
    nicknames = load_json_file(NICKNAMES_FILE, {})
    return nicknames.get(player_name)

# ========== Функции для экранирования Markdown ==========
def escape_markdown(text):
    """Экранирует специальные символы Markdown"""
    if not text:
        return text
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

# ========== Основные функции ==========
def download_and_save_json() -> tuple[bool, str]:
    """Скачивает JSON с сайта используя заголовки браузера."""
    try:
        logger.info(f"Пытаюсь скачать данные с {GUILD_URL}")
        
        session = requests.Session()
        
        logger.info("Заходим на главную страницу для получения куки...")
        main_response = session.get('https://swgoh.gg/', headers=REQUEST_HEADERS, timeout=10)
        logger.info(f"Главная страница: статус {main_response.status_code}")
        
        logger.info("Запрашиваем API...")
        response = session.get(GUILD_URL, headers=REQUEST_HEADERS, timeout=15)
        
        logger.info(f"Статус ответа API: {response.status_code}")
        
        if response.status_code == 403:
            return False, "Сайт вернул 403 Forbidden. Возможно, требуется авторизация."
        
        if response.status_code == 404:
            return False, "Страница не найдена (404). Проверьте URL гильдии."
        
        response.raise_for_status()
        
        if not response.text:
            return False, "Получен пустой ответ от сервера"
        
        try:
            guild_data = response.json()
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON: {e}")
            return False, f"Сервер вернул не JSON. Первые 100 символов: {response.text[:100]}"
        
        with open(JSON_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(guild_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"JSON успешно сохранен в {JSON_FILE_PATH}")
        
        guild_name = guild_data.get('data', {}).get('name', 'Неизвестно')
        member_count = guild_data.get('data', {}).get('member_count', 0)
        
        return True, f"Гильдия: {guild_name}, участников: {member_count}"
        
    except requests.exceptions.Timeout:
        return False, "Таймаут при подключении к серверу. Попробуйте позже."
    except requests.exceptions.ConnectionError:
        return False, "Не удалось подключиться к серверу. Проверьте интернет-соединение."
    except requests.exceptions.RequestException as e:
        return False, f"Ошибка запроса: {str(e)[:100]}"
    except Exception as e:
        return False, f"Непредвиденная ошибка: {str(e)[:100]}"

def parse_guild_data() -> dict:
    """Парсит сохраненный JSON файл и возвращает данные для вывода."""
    try:
        if not os.path.exists(JSON_FILE_PATH):
            return {'error': 'Файл с данными не найден. Используйте команду /update для загрузки данных.'}
        
        file_size = os.path.getsize(JSON_FILE_PATH)
        if file_size == 0:
            return {'error': 'Файл с данными пуст. Используйте команду /update для повторной загрузки.'}
        
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            guild_data = json.load(f)
        
        if 'data' not in guild_data:
            return {'error': 'Неверная структура JSON файла'}
        
        data = guild_data.get('data', {})
        guild_name = data.get('name', 'Не указано')
        member_count = data.get('member_count', 0)
        members = data.get('members', [])
        
        if not members:
            return {'error': 'Не удалось найти список участников гильдии'}
        
        # Сортируем игроков по ГМ (мощности) по убыванию
        sorted_members = sorted(members, key=lambda x: x.get('galactic_power', 0), reverse=True)
        
        return {
            'success': True,
            'guild_name': guild_name,
            'member_count': member_count,
            'players_raw': sorted_members,
            'last_sync': data.get('last_sync', 'Неизвестно')
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка при чтении JSON файла: {e}")
        return {'error': f'Ошибка при чтении файла данных: {str(e)[:100]}'}
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при парсинге: {e}")
        return {'error': f'Ошибка при обработке данных: {str(e)[:100]}'}

def format_guild_list():
    """Форматирует список игроков с ролями и привязками к Telegram"""
    result = parse_guild_data()
    
    if 'error' in result:
        return result['error']
    
    guild_name = result['guild_name']
    member_count = result['member_count']
    players = result['players_raw']
    
    # Группируем игроков по ролям
    role_groups = {
        "Манд'алор": [],
        "Офицеры": [],
        "Воины Мандалора": [],
        "Неизвестные воины": []
    }
    
    for player in players:
        player_name = player['player_name']
        telegram_username = get_nickname(player_name)
        role = get_role(player_name)
        gp = player['galactic_power']
        
        # Если игрок привязан к Telegram, он автоматически в "Воины Мандалора" если роль не указана
        if role == "Воины Мандалора" and not telegram_username:
            role = "Неизвестные воины"
        
        role_groups[role].append((player_name, telegram_username, gp))
    
    # Формируем сообщение
    message_lines = [f"🏰 *{escape_markdown(guild_name)}*", f"👥 Игроков {member_count}/50:\n"]
    
    current_number = 1
    
    # Порядок ролей: Манд'алор, Офицеры, Воины Мандалора, Неизвестные воины
    for role in ["Манд'алор", "Офицеры", "Воины Мандалора", "Неизвестные воины"]:
        players_in_role = role_groups[role]
        if players_in_role:
            message_lines.append(f"*{role}:*")
            for player_name, telegram_username, gp in players_in_role:
                formatted_gp = f"{gp:,}".replace(',', ' ')
                escaped_name = escape_markdown(player_name)
                
                if telegram_username:
                    escaped_tg_name = escape_markdown(telegram_username)
                    message_lines.append(f"{current_number}. {escaped_name} - @{escaped_tg_name} (GP: {formatted_gp})")
                else:
                    message_lines.append(f"{current_number}. {escaped_name} (GP: {formatted_gp})")
                current_number += 1
            message_lines.append("")
    
    if result.get('last_sync') and result['last_sync'] != 'Неизвестно':
        message_lines.append(f"\n🕒 Данные от: {result['last_sync']}")
    
    return "\n".join(message_lines)

# ========== Команды бота ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 Привет! Я бот для получения данных гильдии из SWGOH.gg\n\n"
        "📋 *Доступные команды:*\n"
        "/update - Скачать свежие данные с swgoh.gg\n"
        "/guild - Показать список игроков гильдии\n"
        "/guild_full - Получить полные данные (JSON-файл)\n"
        "/add ник игрока - @username - Привязать Telegram к игроку\n"
        "/remove ник игрока - Удалить привязку Telegram\n"
        "/role ник игрока - Назначить роль игроку\n"
        "/admins - Показать список админов\n"
        "/help - Показать это сообщение\n\n"
        "📝 *Примеры:*\n"
        "/add Qbik - @KuBiK90\n"
        "/add Just Alex - @Alexey_B_B\n"
        "/role Just Alex\n"
        "/remove Qbik\n\n"
        "💡 *Важно:* Имена с пробелами пишите без кавычек, просто через пробел.\n\n"
        "👑 *Роли:* Манд'алор, Офицеры, Воины Мандалора (по умолчанию), Неизвестные воины",
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📋 *Доступные команды:*\n\n"
        "/start - Приветственное сообщение\n"
        "/update - Скачать свежие данные с swgoh.gg\n"
        "/guild - Показать список игроков гильдии\n"
        "/guild_full - Получить полные данные (JSON-файл)\n"
        "/add ник игрока - @username - Привязать Telegram к игроку\n"
        "/remove ник игрока - Удалить привязку Telegram\n"
        "/role ник игрока - Назначить роль игроку\n"
        "/admins - Показать список админов\n"
        "/help - Показать это сообщение\n\n"
        "📝 *Примеры:*\n"
        "/add Qbik - @KuBiK90\n"
        "/add Just Alex - @Alexey_B_B\n"
        "/role Just Alex\n"
        "/remove Qbik\n\n"
        "👑 *Роли:*\n"
        "• Манд'алор - верховный лидер\n"
        "• Офицеры - помощники\n"
        "• Воины Мандалора - игроки с привязкой к Telegram\n"
        "• Неизвестные воины - игроки без привязки\n\n"
        "💡 *Важно:* Имена с пробелами пишите без кавычек, просто через пробел.\n\n"
        "👑 *Админы:* Любой админ может добавлять других админов.",
        parse_mode='Markdown'
    )

async def update_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Скачивает свежие данные с сайта и сохраняет их."""
    username = update.effective_user.username
    if not username or not is_admin(username):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    message = await update.message.reply_text("🔄 Скачиваю свежие данные с swgoh.gg...\nЭто может занять несколько секунд...")
    
    success, info = download_and_save_json()
    
    if success:
        await message.edit_text(
            f"✅ Данные успешно обновлены!\n"
            f"📊 {info}\n"
            f"🕒 Время обновления: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"Теперь используйте команду /guild для просмотра списка игроков"
        )
    else:
        await message.edit_text(
            f"❌ Не удалось обновить данные.\n"
            f"Причина: {info}\n\n"
            f"💡 Альтернатива:\n"
            f"Если у вас есть JSON файл, поместите его в папку data/guild_data.json"
        )

async def get_guild(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Парсит сохраненный JSON и выводит список игроков."""
    message_text = format_guild_list()
    
    if message_text.startswith("❌"):
        await update.message.reply_text(message_text)
        return
    
    # Сохраняем список в файл
    with open(PLAYERS_LIST_FILE, 'w', encoding='utf-8') as f:
        f.write(message_text)
    
    if len(message_text) > 4096:
        await update.message.reply_document(
            document=open(PLAYERS_LIST_FILE, 'rb'),
            filename='guild_players.txt',
            caption="📊 Список игроков гильдии"
        )
    else:
        await update.message.reply_text(message_text, parse_mode='Markdown')
    
    logger.info(f"Список игроков отправлен пользователю @{update.effective_user.username}")

async def get_guild_full(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет сохраненный JSON файл."""
    username = update.effective_user.username
    if not username or not is_admin(username):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    if not os.path.exists(JSON_FILE_PATH):
        await update.message.reply_text(
            "❌ Файл с данными не найден.\n"
            "Используйте команду /update для загрузки данных."
        )
        return
    
    try:
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            guild_data = json.load(f)
            guild_name = guild_data.get('data', {}).get('name', 'Гильдия')
        
        await update.message.reply_document(
            document=open(JSON_FILE_PATH, 'rb'),
            filename='guild_data.json',
            caption=f"📄 Полные данные гильдии {guild_name}\n🕒 Отправлено: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при отправке файла: {e}")

async def add_nickname_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Добавляет привязку Telegram к игроку (поддерживает имена с пробелами без кавычек)"""
    username = update.effective_user.username
    if not username or not is_admin(username):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    # Получаем полный текст команды
    full_text = update.message.text
    
    # Убираем команду "/add "
    if full_text.startswith('/add '):
        full_text = full_text[5:]
    
    # Ищем разделитель " - "
    separator = ' - '
    if separator not in full_text:
        await update.message.reply_text(
            "❌ Неправильный формат команды.\n"
            "Используйте: /add ник игрока - @username\n"
            "Пример: /add Just Alex - @Alexey_B_B"
        )
        return
    
    # Разделяем на имя и username
    parts = full_text.split(separator, 1)
    if len(parts) != 2:
        await update.message.reply_text(
            "❌ Неправильный формат команды.\n"
            "Используйте: /add ник игрока - @username\n"
            "Пример: /add Just Alex - @Alexey_B_B"
        )
        return
    
    player_name = parts[0].strip()
    telegram_username = parts[1].strip()
    
    # Очищаем username от @
    if telegram_username.startswith('@'):
        telegram_username = telegram_username[1:]
    
    # Проверяем, что имя игрока не пустое
    if not player_name:
        await update.message.reply_text("❌ Укажите имя игрока.")
        return
    
    # Проверяем, что username не пустой
    if not telegram_username:
        await update.message.reply_text("❌ Укажите Telegram username.")
        return
    
    # Проверяем, существует ли игрок в гильдии
    result = parse_guild_data()
    if 'error' in result:
        await update.message.reply_text(f"❌ {result['error']}")
        return
    
    players = result['players_raw']
    player_exists = any(p['player_name'] == player_name for p in players)
    
    if not player_exists:
        # Показываем похожие имена для подсказки
        similar_names = [p['player_name'] for p in players if player_name.lower() in p['player_name'].lower()][:5]
        if similar_names:
            hint = "\n\n💡 Возможно, вы имели в виду:\n" + "\n".join([f"• {name}" for name in similar_names])
        else:
            hint = ""
        
        await update.message.reply_text(
            f"❌ Такого воина нет в гильдии: {player_name}{hint}\n\n"
            f"Используйте команду /guild для просмотра списка всех игроков."
        )
        return
    
    # Добавляем привязку
    add_nickname(player_name, telegram_username)
    
    # Форматируем GP игрока
    player_gp = next(p['galactic_power'] for p in players if p['player_name'] == player_name)
    formatted_gp = f"{player_gp:,}".replace(',', ' ')
    
    await update.message.reply_text(
        f"✅ Игрок \"{player_name}\" (GP: {formatted_gp}) привязан к @{telegram_username}\n\n"
        f"Теперь в списке гильдии он будет отображаться в категории 'Воины Мандалора'"
    )
    
    logger.info(f"Админ @{username} добавил привязку \"{player_name}\" -> @{telegram_username}")

async def remove_nickname_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаляет привязку Telegram к игроку (поддерживает имена с пробелами)"""
    username = update.effective_user.username
    if not username or not is_admin(username):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    # Получаем полный текст команды
    full_text = update.message.text
    
    # Убираем команду "/remove "
    if full_text.startswith('/remove '):
        player_name = full_text[8:].strip()
    else:
        player_name = ' '.join(context.args) if context.args else ''
    
    if not player_name:
        await update.message.reply_text(
            "❌ Укажите имя игрока.\n"
            "Пример: /remove Just Alex"
        )
        return
    
    # Проверяем, есть ли привязка
    current_nickname = get_nickname(player_name)
    if not current_nickname:
        # Показываем похожие имена для подсказки
        all_nicknames = load_json_file(NICKNAMES_FILE, {})
        similar_names = [name for name in all_nicknames.keys() if player_name.lower() in name.lower()][:5]
        
        if similar_names:
            hint = "\n\n💡 Возможно, вы имели в виду:\n" + "\n".join([f"• {name}" for name in similar_names])
        else:
            hint = ""
        
        await update.message.reply_text(
            f"❌ У игрока \"{player_name}\" нет привязки к Telegram.{hint}\n\n"
            f"Используйте команду /guild для просмотра списка всех игроков и их привязок."
        )
        return
    
    # Удаляем привязку
    remove_nickname(player_name)
    
    await update.message.reply_text(
        f"✅ Привязка игрока \"{player_name}\" к @{current_nickname} удалена.\n"
        f"Теперь он будет отображаться в списке 'Неизвестные воины'"
    )
    
    logger.info(f"Админ @{username} удалил привязку \"{player_name}\"")

async def role_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Назначает роль игроку (доступно админам)"""
    username = update.effective_user.username
    if not username or not is_admin(username):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    # Получаем имя игрока
    full_text = update.message.text
    if full_text.startswith('/role '):
        player_name = full_text[6:].strip()
    else:
        player_name = ' '.join(context.args) if context.args else ''
    
    if not player_name:
        await update.message.reply_text(
            "❌ Укажите имя игрока.\n"
            "Пример: /role Just Alex"
        )
        return
    
    # Проверяем, существует ли игрок в гильдии
    result = parse_guild_data()
    if 'error' in result:
        await update.message.reply_text(f"❌ {result['error']}")
        return
    
    players = result['players_raw']
    player_exists = any(p['player_name'] == player_name for p in players)
    
    if not player_exists:
        similar_names = [p['player_name'] for p in players if player_name.lower() in p['player_name'].lower()][:5]
        if similar_names:
            hint = "\n\n💡 Возможно, вы имели в виду:\n" + "\n".join([f"• {name}" for name in similar_names])
        else:
            hint = ""
        
        await update.message.reply_text(
            f"❌ Такого воина нет в гильдии: {player_name}{hint}\n\n"
            f"Используйте команду /guild для просмотра списка всех игроков."
        )
        return
    
    # Создаем кнопки для выбора роли
    keyboard = [
        [InlineKeyboardButton("👑 Манд'алор", callback_data=f"role_mandalor_{player_name}")],
        [InlineKeyboardButton("⚔️ Офицеры", callback_data=f"role_officer_{player_name}")],
        [InlineKeyboardButton("🛡️ Снять роль", callback_data=f"role_remove_{player_name}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    current_role = get_role(player_name)
    await update.message.reply_text(
        f"🎭 Выберите роль для игрока *{escape_markdown(player_name)}*\n\n"
        f"Текущая роль: *{current_role}*",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def admins_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает список админов (без Markdown, чтобы символы отображались корректно)"""
    username = update.effective_user.username
    if not username or not is_admin(username):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    admins = load_json_file(ADMINS_FILE, [])
    
    if not admins:
        await update.message.reply_text("📋 Список админов пуст.")
        return
    
    # Формируем список админов
    admin_list = []
    for admin in admins:
        admin_list.append(f"• @{admin}")
    
    message_text = "👥 Админы бота:\n\n" + "\n".join(admin_list)
    
    # Кнопки для добавления/удаления админов (доступны всем админам)
    keyboard = []
    if is_admin(username):
        keyboard.append([InlineKeyboardButton("➕ Добавить админа", callback_data="add_admin")])
        keyboard.append([InlineKeyboardButton("➖ Удалить админа", callback_data="remove_admin")])
    
    if keyboard:
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(message_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message_text)

async def add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Добавляет админа по username (доступно всем админам)"""
    username = update.effective_user.username
    if not username or not is_admin(username):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Укажите username пользователя.\n"
            "Пример: /add_admin @username\n"
            "или /add_admin username\n\n"
            "Username может содержать буквы, цифры и символы подчеркивания."
        )
        return
    
    new_admin = context.args[0]
    if new_admin.startswith('@'):
        new_admin = new_admin[1:]
    
    if add_admin(new_admin):
        await update.message.reply_text(
            f"✅ Пользователь @{new_admin} добавлен в админы.\n\n"
            f"Теперь он может использовать команды:\n"
            f"• /update - обновлять данные\n"
            f"• /add - привязывать игроков\n"
            f"• /remove - удалять привязки\n"
            f"• /role - назначать роли\n"
            f"• /guild_full - получать JSON файл"
        )
        logger.info(f"Админ @{username} добавил админа @{new_admin}")
    else:
        await update.message.reply_text(f"❌ Пользователь @{new_admin} уже является админом.")

async def remove_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаляет админа по username (доступно всем админам)"""
    username = update.effective_user.username
    if not username or not is_admin(username):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Укажите username пользователя.\n"
            "Пример: /remove_admin @username\n"
            "или /remove_admin username"
        )
        return
    
    admin_to_remove = context.args[0]
    if admin_to_remove.startswith('@'):
        admin_to_remove = admin_to_remove[1:]
    
    if admin_to_remove == username:
        await update.message.reply_text("❌ Нельзя удалить самого себя.")
        return
    
    if remove_admin(admin_to_remove):
        await update.message.reply_text(f"✅ Пользователь @{admin_to_remove} удален из админов.")
        logger.info(f"Админ @{username} удалил админа @{admin_to_remove}")
    else:
        await update.message.reply_text(f"❌ Пользователь @{admin_to_remove} не является админом.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    username = update.effective_user.username
    
    # Обработка кнопок ролей
    if query.data.startswith("role_"):
        if not username or not is_admin(username):
            await query.edit_message_text("❌ У вас нет прав для назначения ролей.")
            return
        
        parts = query.data.split("_", 2)
        if len(parts) < 3:
            return
        
        action = parts[1]
        player_name = parts[2]
        
        if action == "mandalor":
            set_role(player_name, "Манд'алор")
            await query.edit_message_text(
                f"✅ Игроку *{escape_markdown(player_name)}* назначена роль *Манд'алор*",
                parse_mode='Markdown'
            )
            logger.info(f"Админ @{username} назначил роль Манд'алор игроку {player_name}")
        elif action == "officer":
            set_role(player_name, "Офицеры")
            await query.edit_message_text(
                f"✅ Игроку *{escape_markdown(player_name)}* назначена роль *Офицеры*",
                parse_mode='Markdown'
            )
            logger.info(f"Админ @{username} назначил роль Офицеры игроку {player_name}")
        elif action == "remove":
            remove_role(player_name)
            await query.edit_message_text(
                f"✅ Роль игрока *{escape_markdown(player_name)}* сброшена.\n"
                f"Теперь он в категории 'Воины Мандалора' (если есть привязка) или 'Неизвестные воины'",
                parse_mode='Markdown'
            )
            logger.info(f"Админ @{username} сбросил роль игрока {player_name}")
    
    # Обработка кнопок админов
    elif query.data == "add_admin":
        if not username or not is_admin(username):
            await query.edit_message_text("❌ У вас нет прав для добавления админов.")
            return
        
        await query.edit_message_text(
            "✏️ Введите username пользователя, которого хотите сделать админом.\n"
            "Формат: /add_admin @username\n"
            "Пример: /add_admin @Alexey_B_B\n\n"
            "Используйте команду прямо в чате."
        )
    elif query.data == "remove_admin":
        if not username or not is_admin(username):
            await query.edit_message_text("❌ У вас нет прав для удаления админов.")
            return
        
        await query.edit_message_text(
            "✏️ Введите username пользователя, которого хотите удалить из админов.\n"
            "Формат: /remove_admin @username\n"
            "Пример: /remove_admin @Alexey_B_B\n\n"
            "Используйте команду прямо в чате."
        )

# ========== Запуск бота ==========
def main() -> None:
    # ВАЖНО: замените на ваш новый токен после отзыва старого!
    TOKEN = "8295503667:AAEHfdeLyL158BE1qcRTLCpp0ya5BbzSFe4"
    
    # Инициализируем данные с главным админом
    if not os.path.exists(ADMINS_FILE):
        save_json_file(ADMINS_FILE, ["KuBiK90"])
        logger.info("Создан файл админов с главным админом @KuBiK90")
    
    application = Application.builder().token(TOKEN).build()
    
    # Регистрируем команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("update", update_data))
    application.add_handler(CommandHandler("guild", get_guild))
    application.add_handler(CommandHandler("guild_full", get_guild_full))
    application.add_handler(CommandHandler("add", add_nickname_command))
    application.add_handler(CommandHandler("remove", remove_nickname_command))
    application.add_handler(CommandHandler("role", role_command))
    application.add_handler(CommandHandler("admins", admins_command))
    application.add_handler(CommandHandler("add_admin", add_admin_command))
    application.add_handler(CommandHandler("remove_admin", remove_admin_command))
    
    # Обработчик кнопок
    application.add_handler(CallbackQueryHandler(button_callback))
    
    logger.info("Бот запущен и готов к работе")
    logger.info("Главный админ: @KuBiK90")
    logger.info("Любой админ может добавлять других админов и назначать роли")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()