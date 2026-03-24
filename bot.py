import requests
from bs4 import BeautifulSoup
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = "8295503667:AAEHfdeLyL158BE1qcRTLCpp0ya5BbzSFe4"
# Используем обычную страницу гильдии, а не API
GUILD_URL = "https://swgoh.gg/g/j16DZ27ZQWe7UqWJP90zjg/"

async def get_guild_roster():
    """Парсит список участников с HTML страницы гильдии"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        
        response = requests.get(GUILD_URL, headers=headers, timeout=15)
        
        if response.status_code != 200:
            return f"⚠️ Ошибка загрузки: {response.status_code}", 0
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Ищем название гильдии
        guild_name_tag = soup.find('h1', class_='guild-name')
        guild_name = guild_name_tag.text.strip() if guild_name_tag else "Mandalorians Kryze"
        
        # Ищем таблицу с участниками
        # На swgoh.gg участники обычно в таблице с классом "table"
        table = soup.find('table', class_='table')
        
        if not table:
            # Пробуем найти другой селектор
            table = soup.find('table')
        
        if not table:
            return "⚠️ Не удалось найти таблицу с участниками", 0
        
        # Парсим строки таблицы
        rows = table.find_all('tr')
        members = []
        
        for row in rows[1:]:  # Пропускаем заголовок
            cells = row.find_all('td')
            if len(cells) >= 2:
                # Имя обычно в первой или второй колонке
                name_cell = cells[0] if cells else None
                if name_cell:
                    name_tag = name_cell.find('a')
                    if name_tag:
                        player_name = name_tag.text.strip()
                        if player_name:
                            members.append(player_name)
        
        if not members:
            return "⚠️ Не удалось найти участников", 0
        
        member_count = len(members)
        
        # Формируем список
        roster_lines = []
        for idx, name in enumerate(sorted(members), start=1):
            roster_lines.append(f"{idx}. {name}")
        
        members_list = "\n".join(roster_lines)
        formatted_message = (
            f"🏰 *{guild_name}*\n"
            f"{members_list}\n\n"
            f"📊 Участников: {member_count}/50"
        )
        
        return formatted_message, member_count
        
    except Exception as e:
        print(f"Ошибка: {e}")
        return f"⚠️ Ошибка загрузки: {str(e)[:100]}", 0

# --- Обработчики команд (без изменений) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("📋 Показать состав гильдии", callback_data="show_roster")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Привет! Я бот гильдии *Mandalorians Kryze*\n\n"
        "Нажми на кнопку, чтобы увидеть список участников:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_roster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("🔄 Загружаю список участников...")
        message_to_edit = query.message
    else:
        chat_id = update.effective_chat.id
        message_to_edit = None
        temp_msg = await update.message.reply_text("🔄 Загружаю список участников...")
        context.user_data['temp_msg_id'] = temp_msg.message_id
        context.user_data['chat_id'] = chat_id

    roster_message, _ = await get_guild_roster()

    if update.callback_query:
        await message_to_edit.edit_text(roster_message, parse_mode='Markdown')
    else:
        try:
            await context.bot.delete_message(
                chat_id=context.user_data['chat_id'], 
                message_id=context.user_data['temp_msg_id']
            )
        except:
            pass
        await context.bot.send_message(
            chat_id=context.user_data['chat_id'], 
            text=roster_message, 
            parse_mode='Markdown'
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 *Доступные команды:*\n\n"
        "/start — Показать приветствие\n"
        "/roster — Показать список участников\n"
        "/help — Показать эту справку"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

def main():
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("roster", show_roster))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(show_roster, pattern="^show_roster$"))
    
    print("🤖 Бот запущен!")
    application.run_polling()

if __name__ == "__main__":
    main()