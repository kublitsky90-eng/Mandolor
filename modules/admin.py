import json
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import NOTIFY_CHAT_ID
from .utils import (
    logger, escape_markdown, load_json_file, save_json_file,
    ADMINS_FILE, NICKNAMES_FILE, ROLES_FILE, JSON_FILE_PATH
)
from .data_handlers import parse_guild_data, download_and_save_json
from .guild import get_guild

# ========== Функции для работы с админами ==========
def normalize_username(username):
    """Убирает @ в начале, если есть, но сохраняет регистр"""
    if not username:
        return None
    if username.startswith('@'):
        username = username[1:]
    return username

def is_admin(username):
    """Проверяет, является ли пользователь админом по username (точное сравнение)"""
    if not username:
        return False
    
    normalized_username = normalize_username(username)
    if not normalized_username:
        return False
    
    admins = load_json_file(ADMINS_FILE, [])
    return normalized_username in admins

def add_admin(username):
    """Добавляет админа по username (сохраняет исходный регистр)"""
    normalized_username = normalize_username(username)
    if not normalized_username:
        return False
    
    admins = load_json_file(ADMINS_FILE, [])
    if normalized_username not in admins:
        admins.append(normalized_username)
        save_json_file(ADMINS_FILE, admins)
        return True
    return False

def remove_admin(username):
    """Удаляет админа по username (точное сравнение)"""
    normalized_username = normalize_username(username)
    if not normalized_username:
        return False
    
    admins = load_json_file(ADMINS_FILE, [])
    if normalized_username in admins:
        admins.remove(normalized_username)
        save_json_file(ADMINS_FILE, admins)
        return True
    return False

# ========== Функции для работы с ролями ==========
def set_role(player_name, role):
    """Устанавливает роль для игрока"""
    roles = load_json_file(ROLES_FILE, {})
    roles[player_name] = role
    save_json_file(ROLES_FILE, roles)

def get_role(player_name):
    """Получает роль игрока"""
    roles = load_json_file(ROLES_FILE, {})
    return roles.get(player_name, "Воины Мандалора")

def remove_role(player_name):
    """Удаляет роль (возвращает к стандартной)"""
    roles = load_json_file(ROLES_FILE, {})
    if player_name in roles:
        del roles[player_name]
        save_json_file(ROLES_FILE, roles)
        return True
    return False

# ========== Функции для работы с привязками ников ==========
def add_nickname(player_name, telegram_username):
    """Добавляет привязку ника игрока к Telegram username"""
    if telegram_username.startswith('@'):
        telegram_username = telegram_username[1:]
    
    nicknames = load_json_file(NICKNAMES_FILE, {})
    nicknames[player_name] = telegram_username
    save_json_file(NICKNAMES_FILE, nicknames)

def remove_nickname(player_name):
    """Удаляет привязку ника игрока"""
    nicknames = load_json_file(NICKNAMES_FILE, {})
    if player_name in nicknames:
        del nicknames[player_name]
        save_json_file(NICKNAMES_FILE, nicknames)
        return True
    return False

def get_nickname(player_name):
    """Получает Telegram username для игрока"""
    nicknames = load_json_file(NICKNAMES_FILE, {})
    return nicknames.get(player_name)

# ========== Команды ==========
async def update_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Скачивает свежие данные с сайта и сохраняет их."""
    username = update.effective_user.username
    if not username or not is_admin(username):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    message = await update.message.reply_text("🔄 Скачиваю свежие данные с swgoh.gg...\nЭто может занять несколько секунд...")
    
    success, info = download_and_save_json()
    
    if success:
        result = parse_guild_data()
        if 'success' in result:
            # Импортируем save_gp_history здесь, чтобы избежать циклического импорта
            from .stats import save_gp_history
            save_gp_history(result)
        
        await message.edit_text(
            f"✅ Данные успешно обновлены!\n"
            f"📊 {info}\n"
            f"🕒 Время обновления: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"Теперь используйте команду /guild для просмотра списка игроков\n"
            f"Или /stats для просмотра статистики"
        )
    else:
        await message.edit_text(
            f"❌ Не удалось обновить данные.\n"
            f"Причина: {info}\n\n"
            f"💡 Альтернатива:\n"
            f"Если у вас есть JSON файл, поместите его в папку data/guild_data.json"
        )

async def get_guild_full(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет сохраненный JSON файл."""
    username = update.effective_user.username
    if not username or not is_admin(username):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    if not os.path.exists(JSON_FILE_PATH):
        await update.message.reply_text(
            "❌ Файл с данными не найден.\n"
            "Используйте команду /update для загрузки данных."
        )
        return
    
    try:
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            guild_data = json.load(f)
            guild_name = guild_data.get('data', {}).get('name', 'Гильдия')
        
        await update.message.reply_document(
            document=open(JSON_FILE_PATH, 'rb'),
            filename='guild_data.json',
            caption=f"📄 Полные данные гильдии {guild_name}\n🕒 Отправлено: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при отправке файла: {e}")

async def add_nickname_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Добавляет привязку Telegram к игроку (поддерживает имена с пробелами без кавычек)"""
    username = update.effective_user.username
    if not username or not is_admin(username):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    full_text = update.message.text
    
    if full_text.startswith('/add '):
        full_text = full_text[5:]
    
    separator = ' - '
    if separator not in full_text:
        await update.message.reply_text(
            "❌ Неправильный формат команды.\n"
            "Используйте: /add ник игрока - @username\n"
            "Пример: /add Just Alex - @Alexey_B_B"
        )
        return
    
    parts = full_text.split(separator, 1)
    if len(parts) != 2:
        await update.message.reply_text(
            "❌ Неправильный формат команды.\n"
            "Используйте: /add ник игрока - @username\n"
            "Пример: /add Just Alex - @Alexey_B_B"
        )
        return
    
    player_name = parts[0].strip()
    telegram_username = parts[1].strip()
    
    if telegram_username.startswith('@'):
        telegram_username = telegram_username[1:]
    
    if not player_name:
        await update.message.reply_text("❌ Укажите имя игрока.")
        return
    
    if not telegram_username:
        await update.message.reply_text("❌ Укажите Telegram username.")
        return
    
    result = parse_guild_data()
    if 'error' in result:
        await update.message.reply_text(f"❌ {result['error']}")
        return
    
    players = result['players_raw']
    player_exists = any(p['player_name'] == player_name for p in players)
    
    if not player_exists:
        similar_names = [p['player_name'] for p in players if player_name.lower() in p['player_name'].lower()][:5]
        if similar_names:
            hint = "\n\n💡 Возможно, вы имели в виду:\n" + "\n".join([f"• {name}" for name in similar_names])
        else:
            hint = ""
        
        await update.message.reply_text(
            f"❌ Такого воина нет в гильдии: {player_name}{hint}\n\n"
            f"Используйте команду /guild для просмотра списка всех игроков."
        )
        return
    
    add_nickname(player_name, telegram_username)
    
    player_gp = next(p['galactic_power'] for p in players if p['player_name'] == player_name)
    formatted_gp = f"{player_gp:,}".replace(',', ' ')
    
    await update.message.reply_text(
        f"✅ Игрок \"{player_name}\" (GP: {formatted_gp}) привязан к @{telegram_username}\n\n"
        f"Теперь в списке гильдии он будет отображаться в категории 'Воины Мандалора'"
    )
    
    await get_guild(update, context)
    
    logger.info(f"Админ @{username} добавил привязку \"{player_name}\" -> @{telegram_username}")

async def remove_nickname_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаляет привязку Telegram к игроку (поддерживает имена с пробелами)"""
    username = update.effective_user.username
    if not username or not is_admin(username):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    full_text = update.message.text
    
    if full_text.startswith('/remove '):
        player_name = full_text[8:].strip()
    else:
        player_name = ' '.join(context.args) if context.args else ''
    
    if not player_name:
        await update.message.reply_text(
            "❌ Укажите имя игрока.\n"
            "Пример: /remove Just Alex"
        )
        return
    
    current_nickname = get_nickname(player_name)
    if not current_nickname:
        all_nicknames = load_json_file(NICKNAMES_FILE, {})
        similar_names = [name for name in all_nicknames.keys() if player_name.lower() in name.lower()][:5]
        
        if similar_names:
            hint = "\n\n💡 Возможно, вы имели в виду:\n" + "\n".join([f"• {name}" for name in similar_names])
        else:
            hint = ""
        
        await update.message.reply_text(
            f"❌ У игрока \"{player_name}\" нет привязки к Telegram.{hint}\n\n"
            f"Используйте команду /guild для просмотра списка всех игроков и их привязок."
        )
        return
    
    remove_nickname(player_name)
    
    await update.message.reply_text(
        f"✅ Привязка игрока \"{player_name}\" к @{current_nickname} удалена.\n"
        f"Теперь он будет отображаться в списке 'Неизвестные воины'"
    )
    
    await get_guild(update, context)
    
    logger.info(f"Админ @{username} удалил привязку \"{player_name}\"")

async def role_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Назначает роль игроку (доступно админам)"""
    username = update.effective_user.username
    if not username or not is_admin(username):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    full_text = update.message.text
    if full_text.startswith('/role '):
        player_name = full_text[6:].strip()
    else:
        player_name = ' '.join(context.args) if context.args else ''
    
    if not player_name:
        await update.message.reply_text(
            "❌ Укажите имя игрока.\n"
            "Пример: /role Just Alex"
        )
        return
    
    result = parse_guild_data()
    if 'error' in result:
        await update.message.reply_text(f"❌ {result['error']}")
        return
    
    players = result['players_raw']
    player_exists = any(p['player_name'] == player_name for p in players)
    
    if not player_exists:
        similar_names = [p['player_name'] for p in players if player_name.lower() in p['player_name'].lower()][:5]
        if similar_names:
            hint = "\n\n💡 Возможно, вы имели в виду:\n" + "\n".join([f"• {name}" for name in similar_names])
        else:
            hint = ""
        
        await update.message.reply_text(
            f"❌ Такого воина нет в гильдии: {player_name}{hint}\n\n"
            f"Используйте команду /guild для просмотра списка всех игроков."
        )
        return
    
    keyboard = [
        [InlineKeyboardButton("👑 Манд'алор", callback_data=f"role_mandalor_{player_name}")],
        [InlineKeyboardButton("⚔️ Офицеры", callback_data=f"role_officer_{player_name}")],
        [InlineKeyboardButton("🛡️ Снять роль", callback_data=f"role_remove_{player_name}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    current_role = get_role(player_name)
    await update.message.reply_text(
        f"🎭 Выберите роль для игрока *{escape_markdown(player_name)}*\n\n"
        f"Текущая роль: *{current_role}*",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def admins_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает список админов (без Markdown, чтобы символы отображались корректно)"""
    username = update.effective_user.username
    if not username or not is_admin(username):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    admins = load_json_file(ADMINS_FILE, [])
    
    if not admins:
        await update.message.reply_text("📋 Список админов пуст.")
        return
    
    admin_list = []
    for admin in admins:
        admin_list.append(f"• @{admin}")
    
    message_text = "👥 Админы бота:\n\n" + "\n".join(admin_list)
    
    keyboard = []
    if is_admin(username):
        keyboard.append([InlineKeyboardButton("➕ Добавить админа", callback_data="add_admin")])
        keyboard.append([InlineKeyboardButton("➖ Удалить админа", callback_data="remove_admin")])
    
    if keyboard:
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(message_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message_text)

async def add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Добавляет админа по username (доступно всем админам)"""
    username = update.effective_user.username
    if not username or not is_admin(username):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Укажите username пользователя.\n"
            "Пример: /add_admin @username\n"
            "или /add_admin username\n\n"
            "Username может содержать буквы, цифры и символы подчеркивания."
        )
        return
    
    new_admin = context.args[0]
    if new_admin.startswith('@'):
        new_admin = new_admin[1:]
    
    if add_admin(new_admin):
        await update.message.reply_text(
            f"✅ Пользователь @{new_admin} добавлен в админы.\n\n"
            f"Теперь он может использовать команды:\n"
            f"• /update - обновлять данные\n"
            f"• /add - привязывать игроков\n"
            f"• /remove - удалять привязки\n"
            f"• /role - назначать роли\n"
            f"• /guild_full - получать JSON файл"
        )
        logger.info(f"Админ @{username} добавил админа @{new_admin}")
    else:
        await update.message.reply_text(f"❌ Пользователь @{new_admin} уже является админом.")

async def remove_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаляет админа по username (доступно всем админам)"""
    username = update.effective_user.username
    if not username or not is_admin(username):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Укажите username пользователя.\n"
            "Пример: /remove_admin @username\n"
            "или /remove_admin username"
        )
        return
    
    admin_to_remove = context.args[0]
    if admin_to_remove.startswith('@'):
        admin_to_remove = admin_to_remove[1:]
    
    if admin_to_remove == username:
        await update.message.reply_text("❌ Нельзя удалить самого себя.")
        return
    
    if remove_admin(admin_to_remove):
        await update.message.reply_text(f"✅ Пользователь @{admin_to_remove} удален из админов.")
        logger.info(f"Админ @{username} удалил админа @{admin_to_remove}")
    else:
        await update.message.reply_text(f"❌ Пользователь @{admin_to_remove} не является админом.")

async def auto_update_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статус авто-обновления"""
    from config import AUTO_UPDATE_ENABLED, AUTO_UPDATE_TIME, NOTIFY_ON_AUTO_UPDATE, NOTIFY_ON_ERROR
    
    username = update.effective_user.username
    if not username or not is_admin(username):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    status_text = (
        f"🤖 **Статус автоматического обновления**\n\n"
        f"Состояние: {'✅ Включено' if AUTO_UPDATE_ENABLED else '❌ Выключено'}\n"
        f"Время обновления: {AUTO_UPDATE_TIME} UTC\n"
        f"Уведомления админам: {'✅ Да' if NOTIFY_ON_AUTO_UPDATE else '❌ Нет'}\n"
        f"Уведомления об ошибках: {'✅ Да' if NOTIFY_ON_ERROR else '❌ Нет'}\n\n"
        f"📝 Команды:\n"
        f"/toggle_auto_update - Вкл/Выкл авто-обновление\n"
        f"/set_update_time 08:00 - Установить время обновления\n"
        f"/update - Ручное обновление"
    )
    
    await update.message.reply_text(status_text, parse_mode='Markdown')

async def toggle_auto_update_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Включает/выключает авто-обновление"""
    import config
    from .scheduler import get_scheduler
    
    username = update.effective_user.username
    if not username or not is_admin(username):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    config.AUTO_UPDATE_ENABLED = not config.AUTO_UPDATE_ENABLED
    scheduler = get_scheduler()
    
    if config.AUTO_UPDATE_ENABLED:
        if scheduler:
            scheduler.resume()
        await update.message.reply_text(
            f"✅ Автоматическое обновление **включено**\n"
            f"Время обновления: {config.AUTO_UPDATE_TIME} UTC"
        )
    else:
        if scheduler:
            scheduler.pause()
        await update.message.reply_text("❌ Автоматическое обновление **выключено**")
    
    save_json_file('data/auto_update_config.json', {
        'enabled': config.AUTO_UPDATE_ENABLED,
        'update_time': config.AUTO_UPDATE_TIME
    })

async def set_update_time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Устанавливает время автоматического обновления"""
    import config
    from .scheduler import get_scheduler, reschedule_daily_update
    
    username = update.effective_user.username
    if not username or not is_admin(username):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Укажите время в формате HH:MM (UTC)\n"
            "Пример: /set_update_time 08:00"
        )
        return
    
    time_str = context.args[0]
    try:
        hour, minute = map(int, time_str.split(':'))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
        
        config.AUTO_UPDATE_TIME = time_str
        
        reschedule_daily_update(hour, minute)
        
        save_json_file('data/auto_update_config.json', {
            'enabled': config.AUTO_UPDATE_ENABLED,
            'update_time': config.AUTO_UPDATE_TIME
        })
        
        await update.message.reply_text(
            f"✅ Время автоматического обновления установлено на **{time_str} UTC**\n"
            f"Обновления будут происходить ежедневно в это время."
        )
        
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат времени.\n"
            "Используйте: /set_update_time 08:00\n"
            "Часы: 00-23, минуты: 00-59"
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    username = update.effective_user.username
    
    if query.data.startswith("role_"):
        if not username or not is_admin(username):
            await query.edit_message_text("❌ У вас нет прав для назначения ролей.")
            return
        
        parts = query.data.split("_", 2)
        if len(parts) < 3:
            return
        
        action = parts[1]
        player_name = parts[2]
        
        if action == "mandalor":
            set_role(player_name, "Манд'алор")
            await query.edit_message_text(
                f"✅ Игроку *{escape_markdown(player_name)}* назначена роль *Манд'алор*",
                parse_mode='Markdown'
            )
            logger.info(f"Админ @{username} назначил роль Манд'алор игроку {player_name}")
        elif action == "officer":
            set_role(player_name, "Офицеры")
            await query.edit_message_text(
                f"✅ Игроку *{escape_markdown(player_name)}* назначена роль *Офицеры*",
                parse_mode='Markdown'
            )
            logger.info(f"Админ @{username} назначил роль Офицеры игроку {player_name}")
        elif action == "remove":
            remove_role(player_name)
            await query.edit_message_text(
                f"✅ Роль игрока *{escape_markdown(player_name)}* сброшена.\n"
                f"Теперь он в категории 'Воины Мандалора' (если есть привязка) или 'Неизвестные воины'",
                parse_mode='Markdown'
            )
            logger.info(f"Админ @{username} сбросил роль игрока {player_name}")
        
        await get_guild(update, context)
    
    elif query.data == "add_admin":
        if not username or not is_admin(username):
            await query.edit_message_text("❌ У вас нет прав для добавления админов.")
            return
        
        await query.edit_message_text(
            "✏️ Введите username пользователя, которого хотите сделать админом.\n"
            "Формат: /add_admin @username\n"
            "Пример: /add_admin @Alexey_B_B\n\n"
            "Используйте команду прямо в чате."
        )
    elif query.data == "remove_admin":
        if not username or not is_admin(username):
            await query.edit_message_text("❌ У вас нет прав для удаления админов.")
            return
        
        await query.edit_message_text(
            "✏️ Введите username пользователя, которого хотите удалить из админов.\n"
            "Формат: /remove_admin @username\n"
            "Пример: /remove_admin @Alexey_B_B\n\n"
            "Используйте команду прямо в чате."
        )