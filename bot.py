import aiohttp
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# --- Конфигурация ---
TOKEN = "8295503667:AAEHfdeLyL158BE1qcRTLCpp0ya5BbzSFe4"
GUILD_API_URL = "https://swgoh.gg/api/guild-profile/j16DZ27ZQWe7UqWJP90zjg/"

# --- Функция получения и обработки данных гильдии (асинхронная) ---
async def get_guild_roster():
    """
    Загружает данные о гильдии, возвращает:
    - formatted_message: текст для отправки в Telegram
    - member_count: текущее количество участников
    """
    try:
        # Используем aiohttp для асинхронного запроса
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(GUILD_API_URL) as response:
                if response.status != 200:
                    print(f"Ошибка HTTP: {response.status}")
                    return f"⚠️ Ошибка загрузки: сервер вернул код {response.status}. Попробуйте позже.", 0
                
                data = await response.json()

        # Извлекаем данные
        guild_data = data.get("data", {})
        members = guild_data.get("members", [])
        
        if not members:
            return "⚠️ В гильдии нет участников или данные не найдены.", 0
            
        member_count = len(members)
        max_members = 50  # Максимум в гильдии

        # Формируем список участников
        roster_lines = []
        for idx, member in enumerate(members, start=1):
            player_name = member.get("player_name", "Неизвестно")
            roster_lines.append(f"{idx}. {player_name}")

        # Собираем итоговое сообщение
        members_list = "\n".join(roster_lines)
        formatted_message = (
            f"{members_list}\n\n"
            f"Участников в гильдии: {member_count}/{max_members}"
        )

        return formatted_message, member_count

    except asyncio.TimeoutError:
        print("Таймаут при запросе к API")
        return "⚠️ Сервер не отвечает. Попробуйте позже.", 0
    except aiohttp.ClientError as e:
        print(f"Ошибка сети: {e}")
        return "⚠️ Ошибка соединения. Проверьте интернет и попробуйте снова.", 0
    except Exception as e:
        print(f"Неожиданная ошибка: {e}")
        return f"⚠️ Внутренняя ошибка: {str(e)[:100]}", 0

# --- Обработчик команды /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет приветствие и кнопку для получения списка гильдии."""
    keyboard = [[InlineKeyboardButton("📋 Показать состав гильдии", callback_data="show_roster")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Привет! Я бот гильдии *Mandalorians Kryze*\n\n"
        "Нажми на кнопку, чтобы увидеть актуальный список участников:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# --- Обработчик нажатия на кнопку (или команды /roster) ---
async def show_roster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Формирует и отправляет сообщение со списком участников."""
    # Определяем, откуда пришел запрос (кнопка или команда)
    if update.callback_query:
        query = update.callback_query
        await query.answer()  # Обязательно отвечаем на callback
        # Показываем сообщение о загрузке
        await query.edit_message_text("🔄 Загружаю список участников, пожалуйста, подождите...")
        chat_id = query.message.chat_id
        message_to_edit = query.message
    else:  # Если вызвано как команду /roster
        chat_id = update.effective_chat.id
        message_to_edit = None
        # Отправляем временное сообщение
        temp_msg = await update.message.reply_text("🔄 Загружаю список участников, пожалуйста, подождите...")
        context.user_data['temp_msg_id'] = temp_msg.message_id

    # Получаем данные
    roster_message, member_count = await get_guild_roster()

    # Отправляем результат
    if update.callback_query:
        # Редактируем исходное сообщение
        await message_to_edit.edit_text(roster_message)
    else:
        # Удаляем временное сообщение и отправляем результат
        try:
            if 'temp_msg_id' in context.user_data:
                await context.bot.delete_message(chat_id=chat_id, message_id=context.user_data['temp_msg_id'])
        except:
            pass  # Если не удалось удалить, игнорируем
        await context.bot.send_message(chat_id=chat_id, text=roster_message)

# --- Обработчик команды /help ---
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает справку по командам."""
    help_text = (
        "📖 *Доступные команды:*\n\n"
        "/start - Показать приветствие и главное меню\n"
        "/roster - Показать список участников гильдии\n"
        "/help - Показать эту справку\n\n"
        "Также вы можете использовать кнопки в интерфейсе."
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

# --- Точка входа ---
def main():
    # Создаём приложение
    application = Application.builder().token(TOKEN).build()

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("roster", show_roster))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(show_roster, pattern="^show_roster$"))

    # Запускаем бота
    print("🤖 Бот запущен и готов к работе...")
    print(f"📊 API URL: {GUILD_API_URL}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()