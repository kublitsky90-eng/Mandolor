import os
import requests
import asyncio
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = "8295503667:AAEHfdeLyL158BE1qcRTLCpp0ya5BbzSFe4"
COMLINK_URL = "http://localhost:3000"
GUILD_ID = "j16DZ27ZQWe7UqWJP90zjg"

def wait_for_comlink(max_retries=30, delay=2):
    """Ожидает запуска Comlink, делает до 30 попыток с интервалом 2 секунды"""
    print("⏳ Ожидание запуска Comlink...")
    for i in range(max_retries):
        try:
            response = requests.get(f"{COMLINK_URL}/", timeout=2)
            if response.status_code == 200:
                print("✅ Comlink готов к работе!")
                return True
        except:
            pass
        print(f"   Попытка {i+1}/{max_retries}...")
        time.sleep(delay)
    print("❌ Comlink не запустился вовремя")
    return False

async def get_guild_roster():
    """Получает список участников через Comlink"""
    try:
        payload = {
            "payload": {
                "guildId": GUILD_ID,
                "includeRecentGuildActivityInfo": False
            }
        }
        
        response = requests.post(
            f"{COMLINK_URL}/guild",
            json=payload,
            timeout=15
        )
        
        if response.status_code != 200:
            return f"⚠️ Ошибка Comlink: {response.status_code}", 0
        
        data = response.json()
        members = data.get("member", [])
        profile = data.get("profile", {})
        
        if not members:
            return "⚠️ В гильдии нет участников", 0
            
        member_count = len(members)
        guild_name = profile.get("name", "Mandalorians Kryze")
        
        sorted_members = sorted(members, key=lambda x: x.get("playerName", ""))
        
        roster_lines = []
        for idx, member in enumerate(sorted_members, start=1):
            player_name = member.get("playerName", "Неизвестно")
            roster_lines.append(f"{idx}. {player_name}")
        
        members_list = "\n".join(roster_lines)
        formatted_message = (
            f"🏰 *{guild_name}*\n"
            f"{members_list}\n\n"
            f"📊 Участников: {member_count}/50"
        )
        
        return formatted_message, member_count
        
    except Exception as e:
        print(f"Ошибка: {e}")
        return f"⚠️ Ошибка подключения к Comlink. Подробности: {e}", 0

# --- Обработчики команд ---
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
    # Ждем запуска Comlink перед стартом бота
    if not wait_for_comlink():
        print("⚠️ Внимание: Comlink не отвечает, бот может работать некорректно")
    
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("roster", show_roster))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(show_roster, pattern="^show_roster$"))
    
    print("🤖 Бот запущен!")
    application.run_polling()

if __name__ == "__main__":
    main()