import aiohttp
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# --- Конфигурация ---
TOKEN = "8295503667:AAEHfdeLyL158BE1qcRTLCpp0ya5BbzSFe4"
GUILD_API_URL = "https://swgoh.gg/api/guild-profile/j16DZ27ZQWe7UqWJP90zjg/"

# --- Заголовки, имитирующие браузер ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': 'https://swgoh.gg/',
    'Origin': 'https://swgoh.gg',
}

# --- Функция получения и обработки данных гильдии ---
async def get_guild_roster():
    """
    Загружает данные о гильдии, возвращает:
    - formatted_message: текст для отправки в Telegram
    - member_count: текущее количество участников
    """
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout, headers=HEADERS) as session:
            async with session.get(GUILD_API_URL) as response:
                if response.status != 200:
                    print(f"Ошибка HTTP: {response.status}")
                    if response.status == 403:
                        return "⚠️ Доступ запрещен (403). Возможно, сайт временно блокирует запросы. Попробуйте позже.", 0
                    return f"⚠️ Ошибка загрузки: сервер вернул код {response.status}. Попробуйте позже.", 0
                
                data = await response.json()

        # Извлекаем данные
        guild_data = data.get("data", {})
        members = guild_data.get("members", [])
        
        if not members:
            return "⚠️ В гильдии нет участников или данные не найдены.", 0
            
        member_count = len(members)
        max_members = 50

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
        return f"⚠️ Внутренняя ошибка. Попробуйте позже.", 0

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
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("🔄 Загружаю список участников, пожалуйста, подождите...")
        message_to_edit = query.message
    else:
        chat_id = update.effective_chat.id
        message_to_edit = None
        temp_msg = await update.message.reply_text("🔄 Загружаю список участников, пожалуйста, подождите...")
        context.user_data['temp_msg_id'] = temp_msg.message_id
        context.user_data['chat_id'] = chat_id

    # Получаем данные
    roster_message, member_count = await get_guild_roster()

    # Отправляем результат
    if update.callback_query:
        await message_to_edit.edit_text(roster_message)
    else:
        chat_id = context.user_data.get('chat_id')
        try:
            if 'temp_msg_id' in context.user_data:
                await context.bot.delete_message(chat_id=chat_id, message_id=context.user_data['temp_msg_id'])
        except:
            pass
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
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("roster", show_roster))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(show_roster, pattern="^show_roster$"))

    print("🤖 Бот запущен и готов к работе...")
    print(f"📊 API URL: {GUILD_API_URL}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()