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

def download_and_save_json() -> bool:
    """Скачивает JSON с сайта и сохраняет в файл. Возвращает True при успехе."""
    try:
        # Выполняем GET-запрос с заголовками User-Agent для обхода блокировки
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(GUILD_URL, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Парсим JSON
        guild_data = response.json()
        
        # Сохраняем JSON в файл (перезаписываем старый)
        with open(JSON_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(guild_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"JSON успешно сохранен в {JSON_FILE_PATH}")
        return True
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при скачивании JSON: {e}")
        return False
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка при парсинге JSON: {e}")
        return False
    except Exception as e:
        logger.error(f"Непредвиденная ошибка: {e}")
        return False

def parse_guild_data() -> dict:
    """Парсит сохраненный JSON файл и возвращает данные для вывода."""
    try:
        # Проверяем, существует ли файл
        if not os.path.exists(JSON_FILE_PATH):
            return {'error': 'Файл с данными не найден. Используйте команду /update для загрузки данных.'}
        
        # Читаем JSON из файла
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            guild_data = json.load(f)
        
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
        return {'error': 'Ошибка при чтении файла данных. Попробуйте обновить данные командой /update'}
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при парсинге: {e}")
        return {'error': f'Ошибка при обработке данных: {e}'}

async def update_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Скачивает свежие данные с сайта и сохраняет их."""
    await update.message.reply_text("🔄 Скачиваю свежие данные с swgoh.gg...")
    
    if download_and_save_json():
        # Получаем название гильдии для подтверждения
        try:
            with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
                guild_data = json.load(f)
                guild_name = guild_data.get('data', {}).get('name', 'Гильдия')
            
            await update.message.reply_text(
                f"✅ Данные успешно обновлены!\n"
                f"🏰 Гильдия: {guild_name}\n"
                f"🕒 Данные актуальны на {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        except:
            await update.message.reply_text("✅ Данные успешно обновлены!")
    else:
        await update.message.reply_text(
            "❌ Не удалось обновить данные.\n"
            "Проверьте подключение к интернету или попробуйте позже."
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
    if result.get('last_sync'):
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