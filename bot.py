import requests
import json
import logging
import os
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# URL для скачивания JSON
GUILD_URL = "https://swgoh.gg/api/guild-profile/j16DZ27ZQWe7UqWJP90zjg/"

# Создаем папку для сохранения файлов, если её нет
DATA_FOLDER = "data"
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

JSON_FILE_PATH = os.path.join(DATA_FOLDER, 'guild_data.json')

def download_and_save_json() -> tuple[bool, str]:
    """Скачивает JSON с сайта и сохраняет в файл. Возвращает (успех, сообщение)."""
    try:
        # Полные заголовки браузера для обхода блокировки
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://swgoh.gg/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        }
        
        logger.info(f"Пытаюсь скачать данные с {GUILD_URL}")
        
        # Выполняем GET-запрос
        response = requests.get(GUILD_URL, headers=headers, timeout=15)
        
        logger.info(f"Статус ответа: {response.status_code}")
        
        # Проверяем статус ответа
        if response.status_code == 403:
            return False, "Сайт блокирует запрос. Возможно, потребуется добавить дополнительные заголовки или использовать прокси."
        
        response.raise_for_status()
        
        # Проверяем, что ответ не пустой
        if not response.text:
            return False, "Получен пустой ответ от сервера"
        
        # Парсим JSON
        try:
            guild_data = response.json()
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON: {e}")
            logger.debug(f"Первые 500 символов ответа: {response.text[:500]}")
            return False, f"Ошибка парсинга JSON: {str(e)[:100]}"
        
        # Сохраняем JSON в файл (перезаписываем старый)
        with open(JSON_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(guild_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"JSON успешно сохранен в {JSON_FILE_PATH}")
        
        # Получаем название гильдии для информации
        guild_name = guild_data.get('data', {}).get('name', 'Неизвестно')
        member_count = guild_data.get('data', {}).get('member_count', 0)
        
        return True, f"Гильдия: {guild_name}, участников: {member_count}"
        
    except requests.exceptions.Timeout:
        logger.error("Timeout при запросе к API")
        return False, "Таймаут при подключении к серверу. Попробуйте позже."
    except requests.exceptions.ConnectionError:
        logger.error("Ошибка подключения")
        return False, "Не удалось подключиться к серверу. Проверьте интернет-соединение."
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при скачивании JSON: {e}")
        return False, f"Ошибка запроса: {str(e)[:100]}"
    except Exception as e:
        logger.error(f"Непредвиденная ошибка: {e}")
        return False, f"Непредвиденная ошибка: {str(e)[:100]}"

def parse_guild_data() -> dict:
    """Парсит сохраненный JSON файл и возвращает данные для вывода."""
    try:
        # Проверяем, существует ли файл
        if not os.path.exists(JSON_FILE_PATH):
            return {'error': 'Файл с данными не найден. Используйте команду /update для загрузки данных.'}
        
        # Проверяем размер файла
        file_size = os.path.getsize(JSON_FILE_PATH)
        if file_size == 0:
            return {'error': 'Файл с данными пуст. Используйте команду /update для повторной загрузки.'}
        
        # Читаем JSON из файла
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            guild_data = json.load(f)
        
        # Проверяем структуру данных
        if 'data' not in guild_data:
            return {'error': 'Неверная структура JSON файла'}
        
        # Извлекаем данные
        data = guild_data.get('data', {})
        guild_name = data.get('name', 'Не указано')
        member_count = data.get('member_count', 0)
        members = data.get('members', [])
        
        if not members:
            return {'error': 'Не удалось найти список участников гильдии'}
        
        # Сортируем игроков по ГМ (мощности) по убыванию
        sorted_members = sorted(members, key=lambda x: x.get('galactic_power', 0), reverse=True)
        
        # Формируем список игроков
        players_list = []
        for i, member in enumerate(sorted_members, 1):
            player_name = member.get('player_name', 'Неизвестно')
            galactic_power = member.get('galactic_power', 0)
            # Форматируем число с разделителями тысяч
            formatted_gp = f"{galactic_power:,}".replace(',', ' ')
            players_list.append(f"{i}. {player_name} (GP: {formatted_gp})")
        
        return {
            'success': True,
            'guild_name': guild_name,
            'member_count': member_count,
            'players_list': players_list,
            'last_sync': data.get('last_sync', 'Неизвестно')
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка при чтении JSON файла: {e}")
        return {'error': f'Ошибка при чтении файла данных: {str(e)[:100]}. Попробуйте обновить данные командой /update'}
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при парсинге: {e}")
        return {'error': f'Ошибка при обработке данных: {str(e)[:100]}'}

async def update_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Скачивает свежие данные с сайта и сохраняет их."""
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
            f"💡 Возможные решения:\n"
            f"• Проверьте подключение к интернету\n"
            f"• Попробуйте позже\n"
            f"• Если проблема повторяется, возможно сайт изменил API"
        )

async def get_guild(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Парсит сохраненный JSON и выводит список игроков."""
    
    # Парсим данные из сохраненного файла
    result = parse_guild_data()
    
    if 'error' in result:
        await update.message.reply_text(f"❌ {result['error']}")
        return
    
    # Формируем итоговое сообщение
    message_text = (
        f"🏰 *{result['guild_name']}*\n"
        f"👥 Игроков {result['member_count']}/50:\n\n"
        f"{chr(10).join(result['players_list'])}"
    )
    
    # Добавляем информацию о времени последней синхронизации
    if result.get('last_sync') and result['last_sync'] != 'Неизвестно':
        message_text += f"\n\n🕒 Данные от: {result['last_sync']}"
    
    # Проверяем длину сообщения (ограничение Telegram - 4096 символов)
    if len(message_text) > 4096:
        # Если слишком длинное, отправляем файлом
        players_file = os.path.join(DATA_FOLDER, 'players_list.txt')
        with open(players_file, 'w', encoding='utf-8') as f:
            f.write(message_text)
        
        await update.message.reply_document(
            document=open(players_file, 'rb'),
            filename='guild_players.txt',
            caption=f"📊 Список игроков гильдии {result['guild_name']}"
        )
    else:
        await update.message.reply_text(message_text, parse_mode='Markdown')
    
    logger.info(f"Список игроков отправлен пользователю {update.effective_user.id}")

async def get_guild_full(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет сохраненный JSON файл."""
    
    # Проверяем, существует ли файл
    if not os.path.exists(JSON_FILE_PATH):
        await update.message.reply_text(
            "❌ Файл с данными не найден.\n"
            "Используйте команду /update для загрузки данных."
        )
        return
    
    try:
        # Читаем JSON для получения названия гильдии
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            guild_data = json.load(f)
            guild_name = guild_data.get('data', {}).get('name', 'Гильдия')
        
        # Отправляем файл
        await update.message.reply_document(
            document=open(JSON_FILE_PATH, 'rb'),
            filename='guild_data.json',
            caption=f"📄 Полные данные гильдии {guild_name}\n🕒 Отправлено: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        logger.info(f"Полный JSON отправлен пользователю {update.effective_user.id}")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при отправке файла: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение."""
    await update.message.reply_text(
        "👋 Привет! Я бот для получения данных гильдии из SWGOH.gg\n\n"
        "📋 *Доступные команды:*\n"
        "/update - Скачать свежие данные с swgoh.gg\n"
        "/guild - Показать список игроков гильдии\n"
        "/guild_full - Получить полные данные (JSON-файл)\n"
        "/help - Показать это сообщение\n\n"
        "💡 *Важно:* Сначала используйте /update для загрузки данных!",
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет список доступных команд."""
    await update.message.reply_text(
        "📋 *Доступные команды:*\n\n"
        "/start - Приветственное сообщение\n"
        "/update - Скачать свежие данные с swgoh.gg\n"
        "/guild - Показать список игроков гильдии (сортировка по ГМ)\n"
        "/guild_full - Получить полные данные гильдии (JSON-файл)\n"
        "/help - Показать это сообщение\n\n"
        "📊 *Информация:*\n"
        "GP - Galactic Power (Галактическая мощь игрока)\n"
        "Данные сохраняются локально и обновляются командой /update",
        parse_mode='Markdown'
    )

def main() -> None:
    """Запускает бота."""
    # ВАЖНО: замените на ваш реальный токен
    TOKEN = "8295503667:AAEHfdeLyL158BE1qcRTLCpp0ya5BbzSFe4"
    
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()
    
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("update", update_data))
    application.add_handler(CommandHandler("guild", get_guild))
    application.add_handler(CommandHandler("guild_full", get_guild_full))
    application.add_handler(CommandHandler("help", help_command))
    
    # Запускаем бота
    logger.info("Бот запущен и готов к работе")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()