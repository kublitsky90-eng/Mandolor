import os
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram.ext import ContextTypes

from config import AUTO_UPDATE_ENABLED, AUTO_UPDATE_TIME, NOTIFY_ON_AUTO_UPDATE, NOTIFY_ON_ERROR, NOTIFY_CHAT_ID
from .utils import logger, download_and_save_json, parse_guild_data, save_gp_history
from .guild import format_guild_list, get_last_guild_message

scheduler = None
bot_application = None

def get_scheduler():
    """Возвращает глобальный планировщик"""
    global scheduler
    return scheduler

def set_bot_application(application):
    """Устанавливает глобальный экземпляр приложения"""
    global bot_application
    bot_application = application

async def notify_admins(message: str, parse_mode: str = 'Markdown'):
    """Отправляет уведомление всем админам в указанный чат"""
    global bot_application
    
    if not bot_application:
        logger.error("Application не инициализирован")
        return
    
    if NOTIFY_CHAT_ID:
        try:
            await bot_application.bot.send_message(
                chat_id=NOTIFY_CHAT_ID,
                text=message,
                parse_mode=parse_mode
            )
            logger.info(f"Уведомление отправлено в чат {NOTIFY_CHAT_ID}")
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление: {e}")
    else:
        logger.info(f"Уведомление: {message[:100]}")

async def update_guild_message_auto(context: ContextTypes.DEFAULT_TYPE):
    """Автоматически обновляет сообщение с гильдией"""
    last_msg = get_last_guild_message()
    if not last_msg:
        return
    
    message_text = format_guild_list()
    if message_text.startswith("❌"):
        return
    
    try:
        await context.bot.edit_message_text(
            chat_id=last_msg['chat_id'],
            message_id=last_msg['message_id'],
            text=message_text,
            parse_mode='Markdown'
        )
        logger.info("Сообщение гильдии автоматически обновлено")
    except Exception as e:
        logger.warning(f"Не удалось автоматически обновить сообщение: {e}")

async def auto_update_data(context: Optional[ContextTypes.DEFAULT_TYPE] = None):
    """Автоматическое обновление данных"""
    logger.info("🔄 Запущено автоматическое обновление данных")
    
    if NOTIFY_ON_AUTO_UPDATE:
        await notify_admins("🔄 Начинаю автоматическое обновление данных гильдии...")
    
    try:
        success, info = download_and_save_json()
        
        if success:
            result = parse_guild_data()
            if 'success' in result:
                save_gp_history(result)
            
            message = (
                f"✅ **Автоматическое обновление выполнено!**\n"
                f"📊 {info}\n"
                f"🕒 Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            if NOTIFY_ON_AUTO_UPDATE:
                await notify_admins(message)
            
            if context and context.bot:
                await update_guild_message_auto(context)
            
            logger.info("✅ Автоматическое обновление успешно завершено")
        else:
            error_msg = f"❌ **Ошибка авто-обновления**\nПричина: {info}"
            logger.error(error_msg)
            if NOTIFY_ON_ERROR:
                await notify_admins(error_msg)
                
    except Exception as e:
        error_msg = f"❌ **Критическая ошибка авто-обновления**\n{str(e)}"
        logger.error(error_msg)
        if NOTIFY_ON_ERROR:
            await notify_admins(error_msg)

def setup_scheduler(application):
    """Настраивает планировщик задач"""
    global scheduler, bot_application
    
    bot_application = application
    
    if not AUTO_UPDATE_ENABLED:
        logger.info("Автоматическое обновление отключено в конфигурации")
        return
    
    scheduler = AsyncIOScheduler(timezone='UTC')
    
    hour, minute = map(int, AUTO_UPDATE_TIME.split(':'))
    scheduler.add_job(
        auto_update_data,
        CronTrigger(hour=hour, minute=minute),
        args=[],  
        id='daily_update',
        name='Ежедневное обновление данных гильдии',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info(f"Планировщик запущен. Авто-обновление в {AUTO_UPDATE_TIME} UTC")

def reschedule_daily_update(hour, minute):
    """Перезапускает задачу ежедневного обновления с новым временем"""
    global scheduler
    
    if scheduler:
        scheduler.remove_job('daily_update')
        scheduler.add_job(
            auto_update_data,
            CronTrigger(hour=hour, minute=minute),
            args=[],
            id='daily_update',
            name='Ежедневное обновление данных гильдии',
            replace_existing=True
        )
        logger.info(f"Задача ежедневного обновления перенастроена на {hour:02d}:{minute:02d} UTC")

async def post_init(application):
    """Запускается после инициализации приложения, когда event loop уже работает"""
    global bot_application, scheduler
    bot_application = application
    
    if AUTO_UPDATE_ENABLED:
        scheduler = AsyncIOScheduler(timezone='UTC')
        
        hour, minute = map(int, AUTO_UPDATE_TIME.split(':'))
        scheduler.add_job(
            auto_update_data,
            CronTrigger(hour=hour, minute=minute),
            args=[],  # Не передаем context
            id='daily_update',
            name='Ежедневное обновление данных гильдии',
            replace_existing=True
        )
        
        scheduler.start()
        logger.info(f"Планировщик запущен. Авто-обновление в {AUTO_UPDATE_TIME} UTC")
    else:
        logger.info("Автоматическое обновление отключено в конфигурации")