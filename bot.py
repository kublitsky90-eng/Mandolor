import requests
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# --- Конфигурация ---
GUILD_API_URL = "https://swgoh.gg/api/guild-profile/j16DZ27ZQWe7UqWJP90zjg/"

# --- Функция получения и обработки данных гильдии ---
async def get_guild_roster():
    """
    Загружает данные о гильдии, возвращает:
    - formatted_message: текст для отправки в Telegram
    - member_count: текущее количество участников
    """
    try:
        response = requests.get(GUILD_API_URL, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Извлекаем данные
        guild_data = data.get("data", {})
        members = guild_data.get("members", [])
        member_count = len(members)
        max_members = 50  # Максимум в гильдии

        # Формируем список участников
        roster_lines = []
        for idx, member in enumerate(members, start=1):
            player_name = member.get("player_name", "Неизвестно")
            roster_lines.append(f"{idx}. {player_name}")

        # Собираем итоговое сообщение
        if roster_lines:
            members_list = "\n".join(roster_lines)
            formatted_message = (
                f"{members_list}\n\n"
                f"Участников в гильдии: {member_count}/{max_members}"
            )
        else:
            formatted_message = "Не удалось найти список участников."

        return formatted_message, member_count

    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к API: {e}")
        return "⚠️ Не удалось загрузить данные о гильдии. Попробуйте позже.", 0
    except Exception as e:
        print(f"Неожиданная ошибка: {e}")
        return "⚠️ Произошла внутренняя ошибка.", 0

# --- Обработчик команды /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет приветствие и кнопку для получения списка гильдии."""
    keyboard = [[InlineKeyboardButton("📋 Показать состав гильдии", callback_data="show_roster")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Привет! Я бот гильдии Mandalorians Kryze.\n"
        "Нажми на кнопку, чтобы увидеть актуальный список участников:",
        reply_markup=reply_markup
    )

# --- Обработчик нажатия на кнопку (или команды /roster) ---
async def show_roster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Формирует и отправляет сообщение со списком участников."""
    # Отправляем "печатает..." чтобы пользователь видел, что бот работает
    if update.callback_query:
        query = update.callback_query
        await query.answer()  # Обязательно отвечаем на callback, чтобы убрать "часики" у кнопки
        await query.edit_message_text("🔄 Загружаю список участников, подождите...")
        chat_id = query.message.chat_id
        message_to_edit = query.message
    else:  # Если вызвано как команду /roster
        chat_id = update.effective_chat.id
        message_to_edit = None
        await update.message.reply_text("🔄 Загружаю список участников, подождите...")

    # Получаем данные
    roster_message, member_count = await get_guild_roster()

    # Отправляем результат
    if message_to_edit:
        await message_to_edit.edit_text(roster_message)
    else:
        await context.bot.send_message(chat_id=chat_id, text=roster_message)

# --- Точка входа ---
def main():
    # Создаём приложение
    application = Application.builder().token(TOKEN).build()

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("roster", show_roster))
    application.add_handler(CallbackQueryHandler(show_roster, pattern="^show_roster$"))

    # Запускаем бота
    print("Бот запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()