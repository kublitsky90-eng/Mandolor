import os
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from dotenv import load_dotenv

from config import *
from modules.admin import (
    is_admin, add_nickname_command, remove_nickname_command, 
    role_command, admins_command, add_admin_command, 
    remove_admin_command, button_callback, get_guild_full,
    update_data, auto_update_status_command, toggle_auto_update_command,
    set_update_time_command
)
from modules.stats import (
    stats_command, stats_arena_command, stats_dynamic_command,
    player_dynamic_command
)
from modules.guild import start, help_command, get_guild, commands_list_command
from modules.scheduler import setup_scheduler, post_init, auto_update_data
from modules.utils import load_json_file, save_json_file, logger, DATA_FOLDER, ADMINS_FILE
from modules.guild_characters import unit_command, unit_info_command

load_dotenv()

# ========== Запуск бота ==========
def main() -> None:
    TOKEN = os.getenv('NEW_BOT_TOKEN')
    
    if not os.path.exists(ADMINS_FILE):
        save_json_file(ADMINS_FILE, ["KuBiK90"])
        logger.info("Создан файл админов с главным админом @KuBiK90")
    
    application = Application.builder().token(TOKEN).build()
    
    # Базовые команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("commands", commands_list_command))
    application.add_handler(CommandHandler("update", update_data))
    application.add_handler(CommandHandler("guild", get_guild))
    application.add_handler(CommandHandler("guild_full", get_guild_full))
    
    # Статистика
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("stats_arena", stats_arena_command))
    application.add_handler(CommandHandler("stats_dynamic", stats_dynamic_command))
    application.add_handler(CommandHandler("dynamic", player_dynamic_command))
    
    # Поиск персонажей
    application.add_handler(CommandHandler("unit", unit_command))
    application.add_handler(CommandHandler("unit_info", unit_info_command))
    
    # Управление игроками (админские)
    application.add_handler(CommandHandler("add", add_nickname_command))
    application.add_handler(CommandHandler("remove", remove_nickname_command))
    application.add_handler(CommandHandler("role", role_command))
    
    # Администрирование
    application.add_handler(CommandHandler("admins", admins_command))
    application.add_handler(CommandHandler("add_admin", add_admin_command))
    application.add_handler(CommandHandler("remove_admin", remove_admin_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Авто-обновление
    application.add_handler(CommandHandler("auto_update_status", auto_update_status_command))
    application.add_handler(CommandHandler("toggle_auto_update", toggle_auto_update_command))
    application.add_handler(CommandHandler("set_update_time", set_update_time_command))
    
    application.post_init = post_init
    
    logger.info("Бот запущен и готов к работе")
    logger.info("Главный админ: @KuBiK90")
    logger.info("Любой админ может добавлять других админов и назначать роли")
    logger.info(f"Авто-обновление: {'Включено' if AUTO_UPDATE_ENABLED else 'Выключено'}")
    logger.info(f"Время обновления: {AUTO_UPDATE_TIME} UTC")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()