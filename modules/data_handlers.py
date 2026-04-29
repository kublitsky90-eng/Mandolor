import json
import os
import requests
from datetime import datetime

from .utils import (
    logger, GUILD_URL, REQUEST_HEADERS, JSON_FILE_PATH,
    load_json_file, save_json_file, escape_markdown
)

# Импортируем из admin.py после определения, чтобы избежать циклического импорта
# Функции get_nickname и get_role будут импортированы позже

# ========== Основные функции обработки данных ==========
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
        
        sorted_members = sorted(members, key=lambda x: x.get('galactic_power', 0), reverse=True)
        
        return {
            'success': True,
            'guild_name': guild_name,
            'guild_data': guild_data,
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
    # Импортируем здесь, чтобы избежать циклического импорта
    from .admin import get_nickname, get_role
    
    result = parse_guild_data()
    
    if 'error' in result:
        return result['error']
    
    guild_name = result['guild_name']
    member_count = result['member_count']
    players = result['players_raw']
    
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
        
        if role == "Воины Мандалора" and not telegram_username:
            role = "Неизвестные воины"
        
        role_groups[role].append((player_name, telegram_username, gp))
    
    message_lines = [f"🏰 *{escape_markdown(guild_name)}*", f"👥 Игроков {member_count}/50:\n"]
    
    current_number = 1
    
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

def save_gp_history(current_data):
    """Сохраняет историю GP игроков"""
    from .stats import save_gp_history as stats_save_gp_history
    return stats_save_gp_history(current_data)