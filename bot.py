"""
Telegram бот для парсинга данных гильдии с сайта swgoh.gg
"""

import requests
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
import telebot
from telebot import types
import time
import threading
import traceback

# Токен бота
TOKEN = '8295503667:AAEHfdeLyL158BE1qcRTLCpp0ya5BbzSFe4'
bot = telebot.TeleBot(TOKEN)

# ID гильдии из ссылки
GUILD_ID = 'j16DZ27ZQWe7UqWJP90zjg'

# Словарь для хранения данных о гильдии в кэше
guild_cache = {
    'data': None,
    'chars': None,
    'ships': None,
    'last_update': None,
    'error': None
}

# Глобальная переменная для ID админа
admin_chat_id = None


def get_player_json(ally_code):
    """Получение json по игроку"""
    try:
        link = f'https://swgoh.gg/api/player/{ally_code}/'
        print(f"Запрос к: {link}")
        response = requests.get(link, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        print(f"Таймаут при получении данных игрока {ally_code}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при получении данных игрока {ally_code}: {e}")
        return None
    except Exception as e:
        print(f"Неожиданная ошибка при получении игрока {ally_code}: {e}")
        return None


def get_data_player(json_data):
    """Получение информации по игроку из json"""
    try:
        if not json_data:
            return None
        
        data = json_data.get('data', {})
        if not data:
            return None
            
        # Проверяем наличие необходимых полей
        required_fields = ['ally_code', 'name', 'character_galactic_power', 
                          'ship_galactic_power', 'galactic_power', 'last_updated']
        
        for field in required_fields:
            if field not in data:
                print(f"Отсутствует поле {field} в данных игрока")
                return None
        
        data['last_updated'] = datetime.fromisoformat(data['last_updated'])
        data_df = pd.json_normalize(data)
        data_df = pd.DataFrame(
            data=data_df,
            index=None,
            columns=[
                'ally_code', 'name', 'character_galactic_power', 
                'ship_galactic_power', 'galactic_power', 'last_updated'
            ]
        )
        data_df.set_axis(
            ['ally_code', 'player_name', 'gp_chars', 'gp_ships', 'gp_total', 'last_updated'],
            axis='columns',
            inplace=True
        )
        data_df.loc[:, 'ally_code'] = data_df.loc[:, 'ally_code'].astype('int32')
        data_df.loc[:, 'gp_chars':'gp_total'] = data_df.loc[:, 'gp_chars':'gp_total'].astype('int32')
        return data_df
    except Exception as e:
        print(f"Ошибка в get_data_player: {e}")
        traceback.print_exc()
        return None


def get_units_player(json_data):
    """Получение списка персонажей по игроку из json"""
    try:
        if not json_data:
            return None
        
        if 'units' not in json_data:
            print("Отсутствуют данные о юнитах")
            return None
            
        units = pd.json_normalize(
            json_data, 'units', [['data', 'name'], ['data', 'ally_code']],
            record_prefix='unit.', max_level=2,
        )
        
        if len(units) == 0:
            return pd.DataFrame()
            
        # Проверяем наличие необходимых колонок
        required_cols = ['data.ally_code', 'unit.data.base_id']
        for col in required_cols:
            if col not in units.columns:
                print(f"Отсутствует колонка {col} в данных юнитов")
                return None
        
        # Создаем DataFrame с нужными колонками
        cols = [
            'data.ally_code', 'unit.data.base_id', 'unit.data.rarity', 
            'unit.data.gear_level', 'unit.data.relic_tier',
            'unit.data.power', 'unit.data.stats.1', 'unit.data.stats.28', 
            'unit.data.stats.5', 'unit.data.stats.6',
            'unit.data.stats.16', 'unit.data.stats.14', 'unit.data.stats.17', 
            'unit.data.stats.18',
            'unit.data.combat_type'
        ]
        
        # Проверяем существование каждой колонки
        existing_cols = [col for col in cols if col in units.columns]
        units = units[existing_cols]
        
        # Заполняем отсутствующие колонки нулями
        for col in cols:
            if col not in units.columns:
                units[col] = 0
        
        units = pd.DataFrame(data=units, index=None, columns=cols)
        
        # Преобразование типов
        try:
            units.loc[:, 'unit.data.rarity':'unit.data.relic_tier'] = \
                units.loc[:, 'unit.data.rarity':'unit.data.relic_tier'].astype('int8')
            units.loc[:, 'unit.data.power':'unit.data.stats.28'] = \
                units.loc[:, 'unit.data.power':'unit.data.stats.28'].astype('int32')
            units.loc[:, 'unit.data.stats.5':'unit.data.stats.6'] = \
                units.loc[:, 'unit.data.stats.5':'unit.data.stats.6'].astype('int16')
            units.loc[:, 'unit.data.stats.16':'unit.data.stats.18'] = \
                units.loc[:, 'unit.data.stats.16':'unit.data.stats.18'].astype('float16')
            units.loc[:, 'unit.data.combat_type'] = units.loc[:, 'unit.data.combat_type'].astype('int8')
        except Exception as e:
            print(f"Ошибка при преобразовании типов: {e}")
        
        units.set_axis(
            ['ally_code', 'unit_id', 'rarity', 'gear_level', 'relic_tier', 'power',
             'health', 'protection', 'speed', 'physical_damage', 'critical_damage', 
             'critical_chance', 'potency', 'tenacity', 'combat_type'],
            axis='columns',
            inplace=True
        )
        units = units.sort_values(by=['unit_id']).reset_index(drop=True)
        return units
    except Exception as e:
        print(f"Ошибка в get_units_player: {e}")
        traceback.print_exc()
        return None


def units_type_chars(units):
    """Отбор из юнитов только персонажей"""
    try:
        if units is None or len(units) == 0:
            return pd.DataFrame()
        characters = units[units['combat_type'] == 1].copy()
        if 'combat_type' in characters.columns:
            characters = characters.drop('combat_type', axis=1)
        return characters.reset_index(drop=True)
    except Exception as e:
        print(f"Ошибка в units_type_chars: {e}")
        return pd.DataFrame()


def units_type_ships(units):
    """Отбор из юнитов только флот"""
    try:
        if units is None or len(units) == 0:
            return pd.DataFrame()
        ships = units[units['combat_type'] == 2].copy()
        ships = ships.loc[:, ['ally_code', 'unit_id', 'rarity', 'power']]
        return ships.reset_index(drop=True)
    except Exception as e:
        print(f"Ошибка в units_type_ships: {e}")
        return pd.DataFrame()


def units_combat_type(units):
    """Разделение юнитов по классам (персонажи и флот)"""
    characters = units_type_chars(units)
    ships = units_type_ships(units)
    return characters, ships


def get_arena_average_rank(ally_code):
    """Получение средних значений арен игрока"""
    try:
        url = f'https://swgoh.gg/p/{ally_code}/'
        print(f"Парсинг арены: {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        value_average_rank = soup.find_all("div", {"class": "stat-item-value"})
        value_list = [i.get_text().strip() for i in value_average_rank]
        
        if len(value_list) > 5:
            chars_arena_rank = value_list[2] if len(value_list) > 2 else "N/A"
            ships_arena_rank = value_list[5] if len(value_list) > 5 else "N/A"
        else:
            value_current_rank = soup.find_all("div", {"class": "current-rank-value"})
            value_list = [i.get_text().strip() for i in value_current_rank]
            chars_arena_rank = value_list[0] if len(value_list) > 0 else "N/A"
            ships_arena_rank = value_list[1] if len(value_list) > 1 else "N/A"
        
        return chars_arena_rank, ships_arena_rank
    except Exception as e:
        print(f"Ошибка при получении арены для {ally_code}: {e}")
        return "N/A", "N/A"


def get_arena_average_rank_for_list(data):
    """Получение средних значений арен для всех игроков"""
    chars_arena = []
    ships_arena = []
    
    for idx, row in data.iterrows():
        ally = row['ally_code']
        print(f"Обработка арены для игрока {row['player_name']} ({ally})")
        chars_arena_player, ships_arena_player = get_arena_average_rank(ally)
        chars_arena.append(chars_arena_player)
        ships_arena.append(ships_arena_player)
        # Небольшая задержка, чтобы не перегружать сервер
        time.sleep(0.5)
    
    return chars_arena, ships_arena


def sync_for_guild_id(guild_id):
    """Получение всех данных по гильдии"""
    try:
        link = f'https://swgoh.gg/api/guild/{guild_id}/'
        print(f"Запрос к API гильдии: {link}")
        response = requests.get(link, timeout=15)
        response.raise_for_status()
        
        json_data = response.json()
        
        if 'players' not in json_data:
            print("В ответе нет поля 'players'")
            return None, None, None
        
        players = json_data['players']
        print(f"Найдено игроков: {len(players)}")
        
        data_list = []
        units_list = []
        
        for idx, player in enumerate(players):
            print(f"Обработка игрока {idx+1}/{len(players)}")
            
            data_player = get_data_player(player)
            if data_player is not None:
                data_list.append(data_player)
            
            units_player = get_units_player(player)
            if units_player is not None and len(units_player) > 0:
                units_list.append(units_player)
            
            # Небольшая задержка между запросами
            time.sleep(0.3)
        
        if not data_list:
            print("Нет данных об игроках")
            return None, None, None
        
        # Объединяем все данные
        data = pd.concat(data_list, ignore_index=True) if data_list else pd.DataFrame()
        units = pd.concat(units_list, ignore_index=True) if units_list else pd.DataFrame()
        
        if len(data) == 0:
            print("Пустой DataFrame данных")
            return None, None, None
        
        data = data.sort_values(by=['player_name']).reset_index(drop=True)
        
        # Получаем данные арены
        print("Получение данных арены...")
        chars_arena, ships_arena = get_arena_average_rank_for_list(data)
        data['chars_average_rank'] = chars_arena
        data['ships_average_rank'] = ships_arena
        
        if len(units) > 0:
            units = units.sort_values(by=['ally_code']).reset_index(drop=True)
            chars, ships = units_combat_type(units)
            return data, chars, ships
        else:
            return data, pd.DataFrame(), pd.DataFrame()
            
    except requests.exceptions.Timeout:
        print("Таймаут при запросе к API гильдии")
        return None, None, None
    except requests.exceptions.RequestException as e:
        print(f"Ошибка запроса к API гильдии: {e}")
        return None, None, None
    except Exception as e:
        print(f"Неожиданная ошибка в sync_for_guild_id: {e}")
        traceback.print_exc()
        return None, None, None


def update_guild_data():
    """Обновление данных гильдии в кэше"""
    global guild_cache, admin_chat_id
    
    try:
        print("Начинаю обновление данных гильдии...")
        
        if admin_chat_id:
            bot.send_message(admin_chat_id, "🔄 Начинаю обновление данных гильдии...")
        
        data, chars, ships = sync_for_guild_id(GUILD_ID)
        
        if data is not None and len(data) > 0:
            guild_cache['data'] = data
            guild_cache['chars'] = chars
            guild_cache['ships'] = ships
            guild_cache['last_update'] = datetime.now()
            guild_cache['error'] = None
            
            message = f"✅ Данные гильдии успешно обновлены!\n"
            message += f"👥 Игроков: {len(data)}\n"
            message += f"🕐 Время: {guild_cache['last_update'].strftime('%Y-%m-%d %H:%M:%S')}"
            print(message)
            
            if admin_chat_id:
                bot.send_message(admin_chat_id, message)
        else:
            error_msg = "❌ Ошибка при обновлении данных гильдии: получены пустые данные"
            print(error_msg)
            guild_cache['error'] = error_msg
            
            if admin_chat_id:
                bot.send_message(admin_chat_id, error_msg)
                
    except Exception as e:
        error_msg = f"❌ Ошибка при обновлении данных гильдии: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        guild_cache['error'] = error_msg
        
        if admin_chat_id:
            bot.send_message(admin_chat_id, error_msg)


@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Обработчик команды /start"""
    global admin_chat_id
    admin_chat_id = message.chat.id
    
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton("📊 Общая статистика")
    btn2 = types.KeyboardButton("👥 Список игроков")
    btn3 = types.KeyboardButton("🔄 Обновить данные")
    btn4 = types.KeyboardButton("📈 Топ по ГП")
    markup.add(btn1, btn2, btn3, btn4)
    
    welcome_text = (
        "🤖 *Привет! Я бот для парсинга данных гильдии SWGOH*\n\n"
        f"📌 *Гильдия:* [Ссылка](https://swgoh.gg/g/{GUILD_ID}/)\n\n"
        "Используй кнопки ниже для получения информации:\n"
        "• 📊 Общая статистика - общая информация о гильдии\n"
        "• 👥 Список игроков - список всех участников\n"
        "• 📈 Топ по ГП - топ-10 игроков по силе\n"
        "• 🔄 Обновить данные - принудительное обновление\n\n"
        "⏳ *Важно:* При первом запуске данные могут загружаться 1-2 минуты"
    )
    
    bot.send_message(
        message.chat.id,
        welcome_text,
        parse_mode='Markdown',
        reply_markup=markup
    )
    
    # Запускаем обновление данных при старте
    update_guild_data()


@bot.message_handler(func=lambda message: True)
def handle_buttons(message):
    """Обработчик кнопок"""
    if message.text == "📊 Общая статистика":
        show_general_stats(message)
    elif message.text == "👥 Список игроков":
        show_players_list(message)
    elif message.text == "🔄 Обновить данные":
        update_guild_data()
        bot.send_message(message.chat.id, "✅ Обновление данных запущено! Результат будет через несколько минут.")
    elif message.text == "📈 Топ по ГП":
        show_top_by_gp(message)
    else:
        bot.send_message(message.chat.id, "Используйте кнопки меню!")


def show_general_stats(message):
    """Показать общую статистику гильдии"""
    if guild_cache['data'] is None:
        if guild_cache['error']:
            bot.send_message(message.chat.id, f"⚠️ Ошибка загрузки данных:\n{guild_cache['error']}\n\nПопробуйте обновить данные позже.")
        else:
            bot.send_message(message.chat.id, "⏳ Данные еще не загружены. Попробуйте через минуту.")
        return
    
    data = guild_cache['data']
    total_gp = data['gp_total'].sum()
    avg_gp = data['gp_total'].mean()
    total_chars_gp = data['gp_chars'].sum()
    total_ships_gp = data['gp_ships'].sum()
    players_count = len(data)
    
    stats_text = (
        f"📊 *Общая статистика гильдии*\n\n"
        f"👥 *Количество игроков:* {players_count}\n"
        f"💪 *Общий ГП:* {total_gp:,}\n"
        f"📈 *Средний ГП:* {avg_gp:,.0f}\n"
        f"⚔️ *Общий ГП персонажей:* {total_chars_gp:,}\n"
        f"🚀 *Общий ГП флота:* {total_ships_gp:,}\n\n"
        f"🕐 *Последнее обновление:*\n{guild_cache['last_update'].strftime('%Y-%m-%d %H:%M:%S') if guild_cache['last_update'] else 'Не обновлялось'}"
    )
    bot.send_message(message.chat.id, stats_text, parse_mode='Markdown')


def show_players_list(message):
    """Показать список игроков"""
    if guild_cache['data'] is None:
        bot.send_message(message.chat.id, "⏳ Данные еще не загружены. Попробуйте через минуту.")
        return
    
    data = guild_cache['data']
    players_text = "*Список игроков гильдии:*\n\n"
    message_count = 1
    
    for idx, row in data.iterrows():
        players_text += f"{idx+1}. {row['player_name']}\n"
        players_text += f"   ГП: {row['gp_total']:,}\n"
        players_text += f"   Арена: {row['chars_average_rank']} | Флот: {row['ships_average_rank']}\n\n"
        
        # Разбиваем сообщение, если оно слишком длинное
        if len(players_text) > 3500:
            bot.send_message(message.chat.id, players_text, parse_mode='Markdown')
            players_text = f"*Список игроков (часть {message_count + 1}):*\n\n"
            message_count += 1
    
    if players_text and players_text != f"*Список игроков (часть {message_count + 1}):*\n\n":
        bot.send_message(message.chat.id, players_text, parse_mode='Markdown')


def show_top_by_gp(message):
    """Показать топ игроков по ГП"""
    if guild_cache['data'] is None:
        bot.send_message(message.chat.id, "⏳ Данные еще не загружены. Попробуйте через минуту.")
        return
    
    data = guild_cache['data'].sort_values('gp_total', ascending=False).head(10)
    top_text = "*🏆 Топ-10 игроков по ГП:*\n\n"
    
    for idx, row in data.iterrows():
        top_text += f"{idx+1}. *{row['player_name']}*\n"
        top_text += f"   💪 ГП: {row['gp_total']:,}\n"
        top_text += f"   ⚔️ Персонажи: {row['gp_chars']:,}\n"
        top_text += f"   🚀 Флот: {row['gp_ships']:,}\n"
        top_text += f"   🎯 Арена: {row['chars_average_rank']} | Флот: {row['ships_average_rank']}\n\n"
    
    bot.send_message(message.chat.id, top_text, parse_mode='Markdown')


def scheduled_update():
    """Функция для автоматического обновления данных"""
    while True:
        time.sleep(3600)  # Обновление раз в час
        update_guild_data()


if __name__ == "__main__":
    print("Бот запускается...")
    print(f"ID гильдии: {GUILD_ID}")
    
    # Запускаем поток для автоматического обновления данных
    update_thread = threading.Thread(target=scheduled_update, daemon=True)
    update_thread.start()
    
    try:
        print("Бот готов к работе!")
        bot.infinity_polling()
    except Exception as e:
        print(f"Ошибка при запуске бота: {e}")
        traceback.print_exc()