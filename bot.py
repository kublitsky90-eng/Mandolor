import aiohttp
import asyncio
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# --- Конфигурация ---
TOKEN = "8295503667:AAEHfdeLyL158BE1qcRTLCpp0ya5BbzSFe4"
GUILD_API_URL = "https://swgoh.gg/api/guild-profile/j16DZ27ZQWe7UqWJP90zjg/"

# --- Полный набор заголовков как у реального браузера ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Referer': 'https://swgoh.gg/g/j16DZ27ZQWe7UqWJP90zjg/',
    'Origin': 'https://swgoh.gg',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'Cache-Control': 'max-age=0',
    'Upgrade-Insecure-Requests': '1',
}

# --- Функция получения данных с повторными попытками ---
async def fetch_with_retry(url, max_retries=3):
    """Пытается загрузить данные с несколькими попытками и случайными задержками"""
    for attempt in range(max_retries):
        try:
            # Случайная задержка между попытками (1-3 секунды)
            if attempt > 0:
                wait_time = random.uniform(2, 5)
                print(f"Повторная попытка {attempt + 1} через {wait_time:.1f} секунд...")
                await asyncio.sleep(wait_time)
            
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout, headers=HEADERS) as session:
                async with session.get(url) as response:
                    print(f"Попытка {attempt + 1}: статус {response.status}")
                    
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 403:
                        # Если 403, пробуем другой User-Agent
                        HEADERS['User-Agent'] = random.choice([
                            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                        ])
                        continue
                    else:
                        return None
                        
        except asyncio.TimeoutError:
            print(f"Попытка {attempt + 1}: таймаут")
            continue
        except Exception as e:
            print(f"Попытка {attempt + 1}: ошибка - {e}")
            continue
    
    return None

# --- Функция получения и обработки данных гильдии ---
async def get_guild_roster():
    """Загружает данные о гильдии с повторными попытками"""
    try:
        # Пробуем загрузить данные
        data = await fetch_with_retry(GUILD_API_URL)
        
        if not data:
            return "⚠️ Не удалось загрузить данные после нескольких попыток. Сайт временно недоступен.", 0

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
        
        # Добавляем название гильдии
        guild_name = guild_data.get("name", "Mandalorians Kryze")
        
        formatted_message = (
            f"🏰 *{guild_name}*\n"
            f"{members_list}\n\n"
            f"📊 Участников: {member_count}/{max_members}"
        )

        return formatted_message, member_count

    except Exception as e:
        print(f"Неожиданная ошибка: {e}")
        return "⚠️ Произошла внутренняя ошибка. Попробуйте позже.", 0

# --- Обработчик команды /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет приветствие и кнопку для получения списка гильдии."""
    keyboard = [
        [InlineKeyboardButton("📋 Показать состав гильдии", callback_data="show_roster")],
        [InlineKeyboardButton("🔄 Обновить данные", callback_data="show_roster")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Привет! Я бот гильдии *Mandalorians Kryze*\n\n"
        "📌 Нажми на кнопку ниже, чтобы увидеть актуальный список участников:\n"
        "• Данные обновляются каждый день\n"
        "• Список показывает всех участников гильдии\n"
        "• Максимум в гильдии — 50 человек",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# --- Обработчик нажатия на кнопку или команды /roster ---
async def show_roster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Формирует и отправляет сообщение со списком участников."""
    # Определяем тип запроса
    if update.callback_query:
        query = update.callback_query
        await query.answer("Загружаю данные...")
        await query.edit_message_text("🔄 Загружаю список участников, пожалуйста, подождите...\n\n_Это может занять до 10 секунд_", parse_mode='Markdown')
        chat_id = query.message.chat_id
        message_to_edit = query.message
    else:
        chat_id = update.effective_chat.id
        message_to_edit = None
        temp_msg = await update.message.reply_text("🔄 Загружаю список участников, пожалуйста, подождите...\n\n_Это может занять до 10 секунд_", parse_mode='Markdown')
        context.user_data['temp_msg_id'] = temp_msg.message_id
        context.user_data['chat_id'] = chat_id

    # Получаем данные
    roster_message, member_count = await get_guild_roster()

    # Отправляем результат
    if update.callback_query:
        await message_to_edit.edit_text(roster_message, parse_mode='Markdown')
    else:
        try:
            if 'temp_msg_id' in context.user_data:
                await context.bot.delete_message(chat_id=chat_id, message_id=context.user_data['temp_msg_id'])
        except:
            pass
        await context.bot.send_message(chat_id=chat_id, text=roster_message, parse_mode='Markdown')

# --- Обработчик команды /help ---
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает справку по командам."""
    help_text = (
        "📖 *Доступные команды:*\n\n"
        "• `/start` — Показать приветствие и главное меню\n"
        "• `/roster` — Показать список участников гильдии\n"
        "• `/help` — Показать эту справку\n\n"
        "📌 *Как это работает:*\n"
        "Бот получает данные с сайта swgoh.gg каждые 24 часа.\n"
        "При нажатии на кнопку показывается актуальный список.\n\n"
        "⚠️ *Примечание:*\n"
        "Если сайт временно недоступен, попробуйте позже."
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

# --- Основная функция ---
def main():
    application = Application.builder().token(TOKEN).build()

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("roster", show_roster))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(show_roster, pattern="^show_roster$"))

    print("🤖 Бот запущен!")
    print("📊 Проверка API...")
    print("💡 Если бот не работает, попробуйте через 5-10 минут")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()