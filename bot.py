import requests
import json
import logging
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение."""
    await update.message.reply_text(
        "Привет! Я бот для получения данных гильдии из SWGOH.gg\n"
        "Используй команду /guild, чтобы получить данные гильдии."
    )

async def get_guild(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Скачивает JSON с данными гильдии и отправляет их в чат."""
    await update.message.reply_text("🔄 Загружаю данные гильдии...")
    
    try:
        # Выполняем GET-запрос
        response = requests.get(GUILD_URL, timeout=10)
        response.raise_for_status()
        
        # Парсим JSON
        guild_data = response.json()
        
        # Извлекаем основные данные для красивого сообщения
        data = guild_data.get('data', {})
        guild_name = data.get('name', 'Не указано')
        member_count = data.get('member_count', 0)
        galactic_power = data.get('galactic_power', 0)
        avg_gp = data.get('avg_galactic_power', 0)
        
        # Формируем текст ответа
        message_text = (
            f"🏰 *Гильдия:* {guild_name}\n"
            f"👥 *Участников:* {member_count}/50\n"
            f"⚔️ *Галактическая мощь:* {galactic_power:,}\n"
            f"📊 *Средняя ГМ:* {avg_gp:,.0f}\n\n"
            f"📄 *Полные данные (JSON):*\n"
            f"```json\n{json.dumps(guild_data, indent=2, ensure_ascii=False)[:3500]}\n```"
        )
        
        # Если JSON слишком длинный, отправляем файлом
        if len(message_text) > 4096:
            # Сохраняем JSON в файл
            json_str = json.dumps(guild_data, indent=2, ensure_ascii=False)
            with open('guild_data.json', 'w', encoding='utf-8') as f:
                f.write(json_str)
            
            await update.message.reply_text(
                f"📊 Данные гильдии *{guild_name}*:\n"
                f"👥 Участников: {member_count}/50\n"
                f"⚔️ Галактическая мощь: {galactic_power:,}\n\n"
                f"📎 Полный JSON слишком большой для отправки текстом.\n"
                f"Отправляю файлом...",
                parse_mode='Markdown'
            )
            await update.message.reply_document(
                document=open('guild_data.json', 'rb'),
                filename='guild_data.json',
                caption=f'Данные гильдии {guild_name}'
            )
        else:
            await update.message.reply_text(message_text, parse_mode='Markdown')
        
        logger.info(f"Данные гильдии успешно отправлены пользователю {update.effective_user.id}")
        
    except requests.exceptions.Timeout:
        await update.message.reply_text("❌ Ошибка: таймаут при запросе к API")
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

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет список доступных команд."""
    await update.message.reply_text(
        "📋 *Доступные команды:*\n"
        "/start - Приветственное сообщение\n"
        "/guild - Получить данные гильдии\n"
        "/help - Показать это сообщение",
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
    application.add_handler(CommandHandler("help", help_command))
    
    # Запускаем бота
    logger.info("Бот запущен и готов к работе")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()