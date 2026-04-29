import os
import json
import logging
from datetime import datetime, timedelta
from collections import defaultdict

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
LAST_GUILD_MSG_FILE = os.path.join(DATA_FOLDER, 'last_guild_msg.json')
HISTORY_FILE = os.path.join(DATA_FOLDER, 'gp_history.json')

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

# Маппинг лиг для красивого отображения
LEAGUE_NAMES = {
    'Carbonite': '🪨 Карбонит',
    'Bronzium': '🥉 Бронзиум',
    'Chromium': '🔵 Хромиум',
    'Aurodium': '🟡 Ауродиум',
    'Kyber': '💎 Кайбер'
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

# ========== Функции для работы с последним сообщением ==========
def save_last_guild_message(chat_id, message_id):
    """Сохраняет информацию о последнем сообщении со списком гильдии"""
    data = {
        'chat_id': chat_id,
        'message_id': message_id,
        'timestamp': datetime.now().isoformat()
    }
    save_json_file(LAST_GUILD_MSG_FILE, data)

def get_last_guild_message():
    """Получает информацию о последнем сообщении со списком гильдии"""
    return load_json_file(LAST_GUILD_MSG_FILE, None)

def clear_last_guild_message():
    """Очищает информацию о последнем сообщении"""
    if os.path.exists(LAST_GUILD_MSG_FILE):
        os.remove(LAST_GUILD_MSG_FILE)

# ========== Функции для экранирования Markdown ==========
def escape_markdown(text):
    """Экранирует специальные символы Markdown"""
    if not text:
        return text
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text