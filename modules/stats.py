from datetime import datetime, timedelta
from collections import defaultdict
from telegram import Update
from telegram.ext import ContextTypes

from .utils import (
    logger, escape_markdown, get_nickname, get_role,
    parse_guild_data, save_gp_history, get_gp_changes,
    HISTORY_FILE
)

# ========== Функции для работы с историей GP ==========
def save_gp_history(current_data):
    """Сохраняет историю GP игроков"""
    from .utils import load_json_file, save_json_file, HISTORY_FILE
    
    history = load_json_file(HISTORY_FILE, {})
    timestamp = datetime.now().isoformat()
    
    players_gp = {}
    for player in current_data.get('players_raw', []):
        player_name = player['player_name']
        players_gp[player_name] = {
            'gp': player['galactic_power'],
            'timestamp': timestamp
        }
    
    if not history:
        history['snapshots'] = []
    
    history['snapshots'].append({
        'timestamp': timestamp,
        'players': players_gp
    })
    
    # Оставляем только последние 30 снимков
    if len(history['snapshots']) > 30:
        history['snapshots'] = history['snapshots'][-30:]
    
    save_json_file(HISTORY_FILE, history)
    return history

def get_gp_changes(player_name, days=7):
    """Получает изменение GP игрока за указанное количество дней"""
    from .utils import load_json_file, HISTORY_FILE
    
    history = load_json_file(HISTORY_FILE, {})
    if not history or 'snapshots' not in history or len(history['snapshots']) < 2:
        return None
    
    target_date = datetime.now() - timedelta(days=days)
    
    old_snapshot = None
    new_snapshot = history['snapshots'][-1]
    
    for snapshot in history['snapshots'][::-1]:
        snapshot_date = datetime.fromisoformat(snapshot['timestamp'])
        if snapshot_date <= target_date:
            old_snapshot = snapshot
            break
    
    if not old_snapshot:
        old_snapshot = history['snapshots'][0]
    
    old_gp = old_snapshot['players'].get(player_name, {}).get('gp', 0)
    new_gp = new_snapshot['players'].get(player_name, {}).get('gp', 0)
    
    if old_gp == 0:
        return None
    
    return {
        'change': new_gp - old_gp,
        'old_gp': old_gp,
        'new_gp': new_gp,
        'days': (datetime.now() - datetime.fromisoformat(old_snapshot['timestamp'])).days
    }

# ========== Функции статистики ==========
def calculate_guild_stats():
    """Рассчитывает общую статистику гильдии"""
    result = parse_guild_data()
    if 'error' in result:
        return None
    
    players = result['players_raw']
    gps = [p['galactic_power'] for p in players]
    total_gp = sum(gps)
    avg_gp = total_gp // len(players) if players else 0
    
    sorted_gps = sorted(gps)
    median_gp = sorted_gps[len(sorted_gps)//2] if sorted_gps else 0
    
    linked_count = 0
    for player in players:
        if get_nickname(player['player_name']):
            linked_count += 1
    
    # Новые диапазоны GP
    ranges = [
        (0, 4_000_000, '🔵 0-4M'),
        (4_000_000, 6_000_000, '🟢 4-6M'),
        (6_000_000, 8_000_000, '🟡 6-8M'),
        (8_000_000, 10_000_000, '🟠 8-10M'),
        (10_000_000, float('inf'), '🔴 10M+')
    ]
    
    distribution = []
    for low, high, label in ranges:
        count = sum(1 for gp in gps if low <= gp < high)
        if count > 0:
            percentage = (count / len(players)) * 100
            bar_length = int(percentage / 2)
            bar = '█' * bar_length
            distribution.append(f"{label}: {count:2d} ({percentage:3.0f}%) {bar}")
    
    role_counts = defaultdict(int)
    for player in players:
        role = get_role(player['player_name'])
        role_counts[role] += 1
    
    return {
        'guild_name': result['guild_name'],
        'member_count': result['member_count'],
        'total_gp': total_gp,
        'avg_gp': avg_gp,
        'median_gp': median_gp,
        'linked_count': linked_count,
        'unlinked_count': len(players) - linked_count,
        'distribution': distribution,
        'role_counts': dict(role_counts),
        'last_sync': result.get('last_sync', 'Неизвестно')
    }

def calculate_arena_stats():
    """Рассчитывает статистику по арене"""
    result = parse_guild_data()
    if 'error' in result:
        return None
    
    players = result['players_raw']
    
    league_stats = defaultdict(int)
    
    for player in players:
        league_name = player.get('league_name', 'Unknown')
        
        if league_name == 'AURODIUM':
            league_stats["🟡 Ауродиум"] += 1
        elif league_name == 'CHROMIUM':
            league_stats["🔵 Хромиум"] += 1
        elif league_name == 'BRONZIUM':
            league_stats["🥉 Бронзиум"] += 1
        elif league_name == 'CARBONITE':
            league_stats["🪨 Карбонит"] += 1
        elif league_name == 'KYBER':
            league_stats["💎 Кайбер"] += 1
        elif league_name != 'Unknown':
            league_stats[league_name] += 1
    
    return {
        'guild_name': result['guild_name'],
        'member_count': result['member_count'],
        'league_stats': dict(league_stats),
        'last_sync': result.get('last_sync', 'Неизвестно')
    }

def calculate_dynamic_stats():
    """Рассчитывает динамику роста"""
    result = parse_guild_data()
    if 'error' in result:
        return None
    
    players = result['players_raw']
    
    save_gp_history(result)
    
    weekly_changes = []
    monthly_changes = []
    
    for player in players:
        player_name = player['player_name']
        current_gp = player['galactic_power']
        
        weekly = get_gp_changes(player_name, 7)
        if weekly and weekly['change'] != 0:
            weekly_changes.append({
                'name': player_name,
                'change': weekly['change'],
                'current_gp': current_gp
            })
        
        monthly = get_gp_changes(player_name, 30)
        if monthly and monthly['change'] != 0:
            monthly_changes.append({
                'name': player_name,
                'change': monthly['change'],
                'current_gp': current_gp
            })
    
    weekly_top = sorted(weekly_changes, key=lambda x: x['change'], reverse=True)
    weekly_bottom = sorted(weekly_changes, key=lambda x: x['change'])
    
    monthly_top = sorted(monthly_changes, key=lambda x: x['change'], reverse=True)
    monthly_bottom = sorted(monthly_changes, key=lambda x: x['change'])
    
    predictions = []
    for player in weekly_top[:10]:
        if player['change'] > 0:
            current_gp = player['current_gp']
            next_million = ((current_gp // 1_000_000) + 1) * 1_000_000
            gp_needed = next_million - current_gp
            
            if gp_needed > 0 and player['change'] > 0:
                weeks_needed = gp_needed / player['change']
                if weeks_needed <= 52:
                    predictions.append({
                        'name': player['name'],
                        'current_gp': current_gp,
                        'next_million': next_million,
                        'weeks_needed': weeks_needed
                    })
    
    return {
        'guild_name': result['guild_name'],
        'member_count': result['member_count'],
        'weekly_top': weekly_top[:5],
        'weekly_bottom': weekly_bottom[:5],
        'weekly_changes': weekly_changes,
        'monthly_top': monthly_top[:5],
        'monthly_bottom': monthly_bottom[:5],
        'monthly_changes': monthly_changes,
        'predictions': predictions[:5],
        'last_sync': result.get('last_sync', 'Неизвестно')
    }

# ========== Команды ==========
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает общую статистику гильдии"""
    stats = calculate_guild_stats()
    
    if not stats:
        await update.message.reply_text("❌ Не удалось получить статистику. Убедитесь, что данные загружены (/update).")
        return
    
    message = f"📊 *Статистика гильдии*\n\n"
    message += f"🏰 *{escape_markdown(stats['guild_name'])}*\n"
    message += f"━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    message += f"📋 *Общая информация:*\n"
    message += f"• Всего игроков: {stats['member_count']}/50\n"
    message += f"• Общий GP: {stats['total_gp']:,}\n".replace(',', ' ')
    message += f"• Средний GP: {stats['avg_gp']:,}\n".replace(',', ' ')
    message += f"• Медианный GP: {stats['median_gp']:,}\n".replace(',', ' ')
    message += f"• Последняя синхронизация: {stats['last_sync']}\n\n"
    
    message += f"👥 *Активность:*\n"
    message += f"• Привязано к Telegram: {stats['linked_count']} ({stats['linked_count']*100//stats['member_count']}%)\n"
    message += f"• Не привязано: {stats['unlinked_count']} ({stats['unlinked_count']*100//stats['member_count']}%)\n\n"
    
    message += f"🎭 *Роли:*\n"
    for role, count in stats['role_counts'].items():
        message += f"• {role}: {count}\n"
    message += "\n"
    
    message += f"📈 *Распределение GP:*\n"
    for line in stats['distribution']:
        message += f"{line}\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def stats_arena_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает статистику по Великой Арене"""
    stats = calculate_arena_stats()
    
    if not stats:
        await update.message.reply_text("❌ Не удалось получить статистику арены. Убедитесь, что данные загружены (/update).")
        return
    
    message = f"⚔️ *Статистика Великой Арены*\n\n"
    message += f"🏰 *{escape_markdown(stats['guild_name'])}*\n"
    message += f"━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    if stats.get('league_stats'):
        message += f"🏆 *Распределение по лигам:*\n"
        for league, count in sorted(stats['league_stats'].items(), key=lambda x: x[1], reverse=True):
            percentage = count * 100 // stats['member_count']
            bar_length = percentage // 5
            bar = '█' * bar_length if bar_length > 0 else '▏'
            message += f"{league}: {count} ({percentage}%) {bar}\n"
        
        message += f"\n📊 *Всего игроков с данными о лигах:* {sum(stats['league_stats'].values())}/{stats['member_count']}"
    else:
        message += f"❌ Данные о лигах не найдены.\n"
        message += f"Возможные причины:\n"
        message += f"• Нет данных об участниках\n"
        message += f"• У игроков отсутствует поле league_name\n"
    
    message += f"\n\n🕒 Данные от: {stats.get('last_sync', 'Неизвестно')}"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def stats_dynamic_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает динамику роста игроков"""
    stats = calculate_dynamic_stats()
    
    if not stats:
        await update.message.reply_text("❌ Не удалось получить динамику. Убедитесь, что данные загружены (/update).")
        return
    
    message = f"📈 *Динамика роста гильдии*\n\n"
    message += f"🏰 *{escape_markdown(stats['guild_name'])}*\n"
    message += f"━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    if stats['weekly_top']:
        message += f"🚀 *Топ-5 по росту GP (неделя):*\n"
        for i, player in enumerate(stats['weekly_top'], 1):
            change_millions = player['change'] / 1_000_000
            message += f"{i}. *{escape_markdown(player['name'])}* +{change_millions:.2f}M GP\n"
        message += "\n"
    
    if len(stats.get('weekly_changes', [])) >= 3:
        weekly_bottom = sorted(stats['weekly_changes'], key=lambda x: x['change'])[:5]
        if weekly_bottom:
            message += f"🐌 *Самый медленный рост за неделю:*\n"
            for i, player in enumerate(weekly_bottom[:5], 1):
                change_millions = player['change'] / 1_000_000
                if player['change'] < 0:
                    message += f"{i}. *{escape_markdown(player['name'])}* {change_millions:.2f}M GP ⚠️\n"
                elif player['change'] < 100000:
                    message += f"{i}. *{escape_markdown(player['name'])}* +{change_millions:.2f}M GP 🐢\n"
                else:
                    message += f"{i}. *{escape_markdown(player['name'])}* +{change_millions:.2f}M GP\n"
            message += "\n"
    
    if stats['monthly_top']:
        message += f"🌟 *Топ-5 по росту GP (месяц):*\n"
        for i, player in enumerate(stats['monthly_top'], 1):
            change_millions = player['change'] / 1_000_000
            message += f"{i}. *{escape_markdown(player['name'])}* +{change_millions:.2f}M GP\n"
        message += "\n"
        
        if len(stats.get('monthly_changes', [])) >= 3:
            monthly_bottom = sorted(stats['monthly_changes'], key=lambda x: x['change'])[:5]
            if monthly_bottom:
                message += f"🐌 *Самый медленный рост за месяц:*\n"
                for i, player in enumerate(monthly_bottom[:5], 1):
                    change_millions = player['change'] / 1_000_000
                    if player['change'] < 0:
                        message += f"{i}. *{escape_markdown(player['name'])}* {change_millions:.2f}M GP ⚠️\n"
                    elif player['change'] < 500000:
                        message += f"{i}. *{escape_markdown(player['name'])}* +{change_millions:.2f}M GP 🐢\n"
                    else:
                        message += f"{i}. *{escape_markdown(player['name'])}* +{change_millions:.2f}M GP\n"
                message += "\n"
    
    if stats['predictions']:
        message += f"🔮 *Прогноз достижения следующего миллиона:*\n"
        for player in stats['predictions']:
            current_millions = player['current_gp'] / 1_000_000
            next_millions = player['next_million'] / 1_000_000
            weeks = player['weeks_needed']
            
            if weeks < 1:
                time_str = f"{weeks*7:.0f} дней"
            elif weeks < 4:
                time_str = f"{weeks:.1f} недель"
            else:
                time_str = f"{weeks/4:.1f} месяцев"
            
            message += f"• *{escape_markdown(player['name'])}*: {current_millions:.1f}M → {next_millions:.0f}M (~{time_str})\n"
        message += "\n"
    
    if not stats['weekly_top'] and not stats['monthly_top']:
        message += f"📊 *Статус:*\n"
        message += f"Недостаточно исторических данных для анализа динамики.\n"
        message += f"Данные будут собираться автоматически при каждом обновлении (/update).\n"
    
    message += f"\n🕒 Данные от: {stats['last_sync']}"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def player_dynamic_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает динамику роста и статистику конкретного игрока"""
    username = update.effective_user.username
    
    if not context.args:
        await update.message.reply_text(
            "❌ Укажите имя игрока.\n"
            "Пример: /dynamic Just Alex\n"
            "Имя можно взять из команды /guild"
        )
        return
    
    player_name = ' '.join(context.args).strip()
    
    result = parse_guild_data()
    if 'error' in result:
        await update.message.reply_text(f"❌ {result['error']}")
        return
    
    players = result['players_raw']
    player_data = None
    for p in players:
        if p['player_name'].lower() == player_name.lower():
            player_data = p
            player_name = p['player_name']
            break
    
    if not player_data:
        matches = [p['player_name'] for p in players if player_name.lower() in p['player_name'].lower()]
        if matches:
            matches_text = "\n".join([f"• {name}" for name in matches[:5]])
            await update.message.reply_text(
                f"❌ Игрок \"{player_name}\" не найден.\n\n"
                f"💡 Возможно, вы имели в виду:\n{matches_text}\n\n"
                f"Используйте точное имя из команды /guild"
            )
        else:
            await update.message.reply_text(
                f"❌ Игрок \"{player_name}\" не найден в гильдии.\n"
                f"Используйте /guild для просмотра списка всех игроков."
            )
        return
    
    current_gp = player_data['galactic_power']
    league_name = player_data.get('league_name', 'Неизвестно')
    guild_join_time = player_data.get('guild_join_time', 'Неизвестно')
    
    if guild_join_time != 'Неизвестно':
        try:
            join_date = datetime.fromisoformat(guild_join_time.replace('Z', '+00:00'))
            join_date_str = join_date.strftime('%d.%m.%Y')
            days_in_guild = (datetime.now() - join_date).days
            join_info = f"{join_date_str} ({days_in_guild} дней)"
        except:
            join_info = guild_join_time
    else:
        join_info = "Неизвестно"
    
    weekly = get_gp_changes(player_name, 7)
    monthly = get_gp_changes(player_name, 30)
    
    league_display = {
        'Aurodium': '🟡 Ауродиум',
        'Chromium': '🔵 Хромиум',
        'Bronzium': '🥉 Бронзиум',
        'Carbonite': '🪨 Карбонит',
        'Kyber': '💎 Кайбер'
    }.get(league_name, league_name)
    
    message = f"📊 *Статистика игрока*\n\n"
    message += f"👤 *{escape_markdown(player_name)}*\n"
    message += f"━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    formatted_gp = f"{current_gp:,}".replace(',', ' ')
    message += f"⚔️ *GP:* {formatted_gp}\n"
    
    if weekly and weekly['change'] != 0:
        change_millions = weekly['change'] / 1_000_000
        arrow = "📈" if weekly['change'] > 0 else "📉"
        message += f"📆 *Рост за неделю:* {arrow} {change_millions:+.2f}M GP\n"
    elif weekly and weekly['change'] == 0:
        message += f"📆 *Рост за неделю:* ⚪ 0 GP\n"
    else:
        message += f"📆 *Рост за неделю:* ❌ Недостаточно данных\n"
    
    if monthly and monthly['change'] != 0:
        change_millions = monthly['change'] / 1_000_000
        arrow = "📈" if monthly['change'] > 0 else "📉"
        message += f"📆 *Рост за месяц:* {arrow} {change_millions:+.2f}M GP\n"
    elif monthly and monthly['change'] == 0:
        message += f"📆 *Рост за месяц:* ⚪ 0 GP\n"
    else:
        message += f"📆 *Рост за месяц:* ❌ Недостаточно данных\n"
    
    message += f"\n🏆 *Лига ВА:* {league_display}\n"
    message += f"📅 *В гильдии с:* {join_info}\n"
    
    tg_nick = get_nickname(player_name)
    if tg_nick:
        message += f"🔗 *Telegram:* @{escape_markdown(tg_nick)}\n"
    
    role = get_role(player_name)
    if role and role != "Воины Мандалора":
        message += f"🎭 *Роль:* {role}\n"
    
    message += f"\n🕒 Данные от: {result.get('last_sync', 'Неизвестно')}"
    
    await update.message.reply_text(message, parse_mode='Markdown')