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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение."""
    await update.message.reply_text(
        "👋 Привет! Я бот для получения данных гильдии из SWGOH.gg\n\n"
        "📋 *Доступные команды:*\n"
        "/guild - Получить список игроков гильдии\n"
        "/guild_full - Получить полные данные гильдии (JSON-файл)\n"
        "/help - Показать это сообщение",
        parse_mode='Markdown'
    )

async def get_guild(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Скачивает JSON, парсит и выводит список игроков."""
    await update.message.reply_text("🔄 Загружаю данные гильдии...")
    
    try:
        # Выполняем GET-запрос
        response = requests.get(GUILD_URL, timeout=10)
        response.raise_for_status()
        
        # Парсим JSON
        guild_data = response.json()
        
        # Сохраняем JSON в файл (перезаписываем старый)
        json_file_path = os.path.join(DATA_FOLDER, 'guild_data.json')
        with open(json_file_path, 'w', encoding='utf-8') as f:
            json.dump(guild_data, f, indent=2, ensure_ascii=False)
        logger.info(f"JSON сохранен в {json_file_path}")
        
        # Извлекаем данные
        data = guild_data.get('data', {})
        guild_name = data.get('name', 'Не указано')
        member_count = data.get('member_count', 0)
        members = data.get('members', [])
        
        if not members:
            await update.message.reply_text("❌ Не удалось найти список участников гильдии")
            return
        
        # Сортируем игроков по ГМ (мощности) по убыванию
        sorted_members = sorted(members, key=lambda x: x.get('galactic_power', 0), reverse=True)
        
        # Формируем список игроков
        players_list = []
        for i, member in enumerate(sorted_members, 1):
            player_name = member.get('player_name', 'Неизвестно')
            galactic_power = member.get('galactic_power', 0)
            players_list.append(f"{i}. {player_name} (GP: {galactic_power:,})")
        
        # Формируем итоговое сообщение
        message_text = (
            f"🏰 *{guild_name}*\n"
            f"👥 Игроков {member_count}/50:\n\n"
            f"{chr(10).join(players_list)}"
        )
        
        # Проверяем длину сообщения (ограничение Telegram - 4096 символов)
        if len(message_text) > 4096:
            # Если слишком длинное, отправляем файлом
            players_file = os.path.join(DATA_FOLDER, 'players_list.txt')
            with open(players_file, 'w', encoding='utf-8') as f:
                f.write(message_text)
            
            await update.message.reply_document(
                document=open(players_file, 'rb'),
                filename='guild_players.txt',
                caption=f"📊 Список игроков гильдии {guild_name}"
            )
        else:
            await update.message.reply_text(message_text, parse_mode='Markdown')
        
        logger.info(f"Список игроков отправлен пользователю {update.effective_user.id}")
        
    except requests.exceptions.Timeout:
        await update.message.reply_text("❌ Ошибка: таймаут при запросе к API. Попробуйте позже.")
        logger.error("Timeout при запросе к API")
    except requests.exceptions.RequestException as e:
        await update.message.reply_text(f"❌ Ошибка при запросе данных: {e}")
        logger.error(f"Request error: {e}")
    except json.JSONDecodeError:
        await update.message.reply_text("❌ Ошибка: получен невалидный JSON")
        logger.error("JSON decode error")
    except Exception as e:
        await update.message.reply_text(f"❌ Произошла непредвиденная ошибка: {e}")
        logger.error(f"Unexpected error: {e}")

async def get_guild_full(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Скачивает JSON и отправляет полный файл."""
    await update.message.reply_text("🔄 Загружаю полные данные гильдии...")
    
    try:
        # Выполняем GET-запрос
        response = requests.get(GUILD_URL, timeout=10)
        response.raise_for_status()
        
        # Парсим JSON
        guild_data = response.json()
        
        # Сохраняем JSON в файл
        json_file_path = os.path.join(DATA_FOLDER, 'guild_data.json')
        with open(json_file_path, 'w', encoding='utf-8') as f:
            json.dump(guild_data, f, indent=2, ensure_ascii=False)
        
        # Извлекаем название гильдии для подписи
        guild_name = guild_data.get('data', {}).get('name', 'Гильдия')
        
        # Отправляем файл
        await update.message.reply_document(
            document=open(json_file_path, 'rb'),
            filename='guild_data.json',
            caption=f"📄 Полные данные гильдии {guild_name}\n🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        logger.info(f"Полный JSON отправлен пользователю {update.effective_user.id}")
        
    except requests.exceptions.Timeout:
        await update.message.reply_text("❌ Ошибка: таймаут при запросе к API")
    except requests.exceptions.RequestException as e:
        await update.message.reply_text(f"❌ Ошибка при запросе данных: {e}")
    except Exception as e:
        await update.message.reply_text(f"❌ Произошла ошибка: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет список доступных команд."""
    await update.message.reply_text(
        "📋 *Доступные команды:*\n\n"
        "/start - Приветственное сообщение\n"
        "/guild - Получить список игроков гильдии (сортировка по ГМ)\n"
        "/guild_full - Получить полные данные гильдии (JSON-файл)\n"
        "/help - Показать это сообщение\n\n"
        "📊 *Информация:*\n"
        "GP - Galactic Power (Галактическая мощь игрока)\n"
        "Данные обновляются с swgoh.gg в реальном времени",
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
    application.add_handler(CommandHandler("guild", get_guild))
    application.add_handler(CommandHandler("guild_full", get_guild_full))
    application.add_handler(CommandHandler("help", help_command))
    
    # Запускаем бота
    logger.info("Бот запущен и готов к работе")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()