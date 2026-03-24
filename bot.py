import requests
import json
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# URL для скачивания JSON
GUILD_URL = "https://swgoh.gg/api/guild-profile/j16DZ27ZQWe7UqWJP90zjg/"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение."""
    await update.message.reply_text("Привет! Используй команду /guild, чтобы получить данные гильдии.")

async def get_guild(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Скачивает JSON с данными гильдии и отправляет их в чат."""
    await update.message.reply_text("Загружаю данные гильдии...")
    
    try:
        # Выполняем GET-запрос
        response = requests.get(GUILD_URL)
        response.raise_for_status()  # Проверяем, не произошла ли ошибка HTTP
        
        # Парсим JSON
        guild_data = response.json()
        
        # Извлекаем основные данные для красивого сообщения
        data = guild_data.get('data', {})
        guild_name = data.get('name', 'Не указано')
        member_count = data.get('member_count', 0)
        galactic_power = data.get('galactic_power', 0)
        
        # Формируем текст ответа
        message_text = (
            f"🏰 *Гильдия:* {guild_name}\n"
            f"👥 *Участников:* {member_count}/50\n"
            f"⚔️ *Галактическая мощь:* {galactic_power:,}\n\n"
            f"📊 *Полный JSON-ответ:*\n"
            f"```json\n{json.dumps(guild_data, indent=2, ensure_ascii=False)[:3000]}\n```"
        )
        
        # Отправляем сообщение
        await update.message.reply_text(message_text, parse_mode='Markdown')
        
    except requests.exceptions.RequestException as e:
        await update.message.reply_text(f"Ошибка при запросе данных: {e}")
    except json.JSONDecodeError:
        await update.message.reply_text("Ошибка: получен невалидный JSON")
    except Exception as e:
        await update.message.reply_text(f"Произошла непредвиденная ошибка: {e}")

def main() -> None:
    """Запускает бота."""
    # ВАЖНО: замените 'YOUR_BOT_TOKEN' на ваш реальный токен
    application = Application.builder().token("YOUR_BOT_TOKEN").build()
    
    # Регистрируем команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("guild", get_guild))
    
    # Запускаем бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()