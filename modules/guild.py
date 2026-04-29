import json
import os
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from .utils import (
    logger, escape_markdown, get_last_guild_message, save_last_guild_message,
    parse_guild_data, format_guild_list, PLAYERS_LIST_FILE
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 Привет! Я бот для получения данных гильдии из SWGOH.gg\n\n"
        "📋 *Доступные команды:*\n"
        "/update - Скачать свежие данные с swgoh.gg\n"
        "/guild - Показать список игроков гильдии\n"
        "/guild_full - Получить полные данные (JSON-файл)\n"
        "/stats - Общая статистика гильдии\n"
        "/stats_arena - Статистика по Великой Арене\n"
        "/stats_dynamic - Динамика роста игроков\n"
        "/add ник игрока - @username - Привязать Telegram к игроку\n"
        "/remove ник игрока - Удалить привязку Telegram\n"
        "/role ник игрока - Назначить роль игроку\n"
        "/admins - Показать список админов\n"
        "/help - Показать это сообщение\n\n"
        "📝 *Примеры:*\n"
        "/add Qbik - @KuBiK90\n"
        "/add Just Alex - @Alexey_B_B\n"
        "/role Just Alex\n"
        "/remove Qbik\n\n"
        "💡 *Важно:* Имена с пробелами пишите без кавычек, просто через пробел.",
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📋 *Доступные команды:*\n\n"
        "/start - Приветственное сообщение\n"
        "/update - Скачать свежие данные с swgoh.gg\n"
        "/guild - Показать список игроков гильдии\n"
        "/guild_full - Получить полные данные (JSON-файл)\n"
        "/stats - Общая статистика гильдии\n"
        "/stats_arena - Статистика по Великой Арене\n"
        "/stats_dynamic - Динамика роста игроков\n"
        "/add ник игрока - @username - Привязать Telegram к игроку\n"
        "/remove ник игрока - Удалить привязку Telegram\n"
        "/role ник игрока - Назначить роль игроку\n"
        "/admins - Показать список админов\n"
        "/help - Показать это сообщение\n\n"
        "📝 *Примеры:*\n"
        "/add Qbik - @KuBiK90\n"
        "/add Just Alex - @Alexey_B_B\n"
        "/role Just Alex\n"
        "/remove Qbik\n\n"
        "👑 *Роли:*\n"
        "• Манд'алор - верховный лидер\n"
        "• Офицеры - помощники\n"
        "• Воины Мандалора - игроки с привязкой к Telegram\n"
        "• Неизвестные воины - игроки без привязки\n\n"
        "👑 *Админы:* Любой админ может добавлять других админов.",
        parse_mode='Markdown'
    )

async def get_guild(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Парсит сохраненный JSON и выводит список игроков (редактирует предыдущее сообщение)"""
    message_text = format_guild_list()
    
    if message_text.startswith("❌"):
        await update.message.reply_text(message_text)
        return
    
    with open(PLAYERS_LIST_FILE, 'w', encoding='utf-8') as f:
        f.write(message_text)
    
    last_msg = get_last_guild_message()
    current_chat_id = update.effective_chat.id
    
    try:
        if last_msg and last_msg.get('chat_id') == current_chat_id:
            await context.bot.edit_message_text(
                chat_id=last_msg['chat_id'],
                message_id=last_msg['message_id'],
                text=message_text,
                parse_mode='Markdown'
            )
            logger.info(f"Сообщение отредактировано (ID: {last_msg['message_id']}")
            
            notification = await update.message.reply_text("✅ Список гильдии обновлен!")
            await notification.delete()
            
        else:
            if len(message_text) > 4096:
                sent_message = await update.message.reply_document(
                    document=open(PLAYERS_LIST_FILE, 'rb'),
                    filename='guild_players.txt',
                    caption="📊 Список игроков гильдии"
                )
            else:
                sent_message = await update.message.reply_text(message_text, parse_mode='Markdown')
                save_last_guild_message(current_chat_id, sent_message.message_id)
                
    except Exception as e:
        logger.warning(f"Не удалось отредактировать сообщение: {e}")
        
        if len(message_text) > 4096:
            sent_message = await update.message.reply_document(
                document=open(PLAYERS_LIST_FILE, 'rb'),
                filename='guild_players.txt',
                caption="📊 Список игроков гильдии"
            )
        else:
            sent_message = await update.message.reply_text(message_text, parse_mode='Markdown')
            save_last_guild_message(current_chat_id, sent_message.message_id)
    
    logger.info(f"Список игроков отправлен пользователю @{update.effective_user.username}")