# modules/guild_characters.py
import json
import os
import asyncio
import aiohttp
from telegram import Update
from telegram.ext import ContextTypes

from .utils import (
    logger, JSON_FILE_PATH, DATA_FOLDER
)


# ========== Маппинг имен персонажей ==========
CHARACTER_NAME_MAPPING = {
    "lord vader": "Lord Vader",
    "lv": "Lord Vader",
    "jedi master kenobi": "Jedi Master Kenobi",
    "jmk": "Jedi Master Kenobi",
    "supreme leader kylo ren": "Supreme Leader Kylo Ren",
    "slkr": "Supreme Leader Kylo Ren",
    "rey": "Rey",
    "rey jedi training": "Rey (Jedi Training)",
    "rjt": "Rey (Jedi Training)",
    "jedi master luke skywalker": "Jedi Master Luke Skywalker",
    "jml": "Jedi Master Luke Skywalker",
    "general hux": "General Hux",
    "hux": "General Hux",
    "darth vader": "Darth Vader",
    "vader": "Darth Vader",
    "commander luke skywalker": "Commander Luke Skywalker",
    "cls": "Commander Luke Skywalker",
    "general skywalker": "General Skywalker",
    "gas": "General Skywalker",
    "jedi knight revan": "Jedi Knight Revan",
    "jkr": "Jedi Knight Revan",
    "darth revan": "Darth Revan",
    "darth malak": "Darth Malak",
    "starkiller": "Starkiller",
    "cal kestis": "Cal Kestis",
    "cal": "Cal Kestis",
    "the mandalorian": "The Mandalorian",
    "mando": "The Mandalorian",
    "jango fett": "Jango Fett",
    "jango": "Jango Fett",
    "boba fett": "Boba Fett",
    "boba": "Boba Fett",
    "bossk": "Bossk",
    "general grievous": "General Grievous",
    "grievous": "General Grievous",
    "mother talzin": "Mother Talzin",
    "talzin": "Mother Talzin",
    "asajj ventress": "Asajj Ventress",
    "ventress": "Asajj Ventress",
    "padme amidala": "Padmé Amidala",
    "padme": "Padmé Amidala",
    "ahsoka tano": "Ahsoka Tano",
    "ahsoka": "Ahsoka Tano",
    "commander ahsoka tano": "Commander Ahsoka Tano",
    "cat": "Commander Ahsoka Tano",
    "grand master yoda": "Grand Master Yoda",
    "gmy": "Grand Master Yoda",
    "hermit yoda": "Hermit Yoda",
    "hoda": "Hermit Yoda",
    "general kenobi": "General Kenobi",
    "gk": "General Kenobi",
    "admiral piett": "Admiral Piett",
    "piett": "Admiral Piett",
    "moff gideon": "Moff Gideon",
    "gideon": "Moff Gideon",
    "grand admiral thrawn": "Grand Admiral Thrawn",
    "thrawn": "Grand Admiral Thrawn",
    "dark trooper": "Dark Trooper",
    "darktrooper": "Dark Trooper",
    "krrsantan": "Krrsantan",
    "bossk": "Bossk",
    "greef karga": "Greef Karga",
    "greef": "Greef Karga",
    "wat tambor": "Wat Tambor",
    "wat": "Wat Tambor",
    "c-3po": "C-3PO",
    "c3po": "C-3PO",
    "r2-d2": "R2-D2",
    "r2d2": "R2-D2",
    "chewbacca": "Chewbacca",
    "chewie": "Chewbacca",
    "bb-8": "BB-8",
    "bb8": "BB-8",
    "hera syndulla": "Hera Syndulla",
    "ezra bridger": "Ezra Bridger",
    "sabine wren": "Sabine Wren",
    "kanan jarrus": "Kanan Jarrus",
    "chopper": "Chopper",
    "zeb": "Garazeb \"Zeb\" Orrelios",
    "cara dune": "Cara Dune",
    "merrin": "Merrin",
    "great mothers": "Great Mothers",
    "tusken raider": "Tusken Raider",
    "tusken warrior": "Tusken Warrior",
    "tusken chieftain": "Tusken Chieftain",
    "tusken shaman": "Tusken Shaman",
    "jawa": "Jawa",
    "geonosian brood alpha": "Geonosian Brood Alpha",
    "geonosian soldier": "Geonosian Soldier",
    "geonosian spy": "Geonosian Spy",
    "nightsister zombie": "Nightsister Zombie",
    "old daka": "Old Daka",
    "imperial super commando": "Imperial Super Commando",
    "gar saxon": "Gar Saxon",
    "b2 super battle droid": "B2 Super Battle Droid",
    "b1 battle droid": "B1 Battle Droid",
    "droideka": "Droideka",
    "magnaguard": "IG-100 MagnaGuard",
    "nute gunray": "Nute Gunray",
    "poggle the lesser": "Poggle the Lesser",
    "sun fac": "Sun Fac",
    "count dooku": "Count Dooku",
    "darth sidious": "Darth Sidious",
    "darth maul": "Darth Maul",
    "savage opress": "Savage Opress",
    "darth talon": "Darth Talon",
    "sith trooper": "Sith Trooper",
    "sith marauder": "Sith Marauder",
    "sith assassin": "Sith Assassin",
    "darth nihilus": "Darth Nihilus",
    "darth sion": "Darth Sion",
    "darth traya": "Darth Traya",
    "jedi knight anakin": "Jedi Knight Anakin",
    "anakin skywalker": "Anakin Skywalker",
    "qui gon jinn": "Qui-Gon Jinn",
    "mace windu": "Mace Windu",
    "obi wan kenobi": "Obi-Wan Kenobi",
    "old ben kenobi": "Old Ben Kenobi",
    "plo koon": "Plo Koon",
    "kit fisto": "Kit Fisto",
    "eeth koth": "Eeth Koth",
    "ima gun di": "Ima-Gun Di",
    "jedi consular": "Jedi Consular",
    "jedi knight guardian": "Jedi Knight Guardian",
    "luminara unduli": "Luminara Unduli",
    "barris offee": "Barriss Offee",
    "ahsoka tano snips": "Ahsoka Tano",
    "commander luke skywalker": "Commander Luke Skywalker",
    "rebel officer leia": "Rebel Officer Leia Organa",
    "princess leia": "Princess Leia",
    "admiral ackbar": "Admiral Ackbar",
    "wedge antilles": "Wedge Antilles",
    "bigg darklighter": "Biggs Darklighter",
    "han solo": "Han Solo",
    "stormtrooper han": "Stormtrooper Han",
    "veteran smuggler han": "Veteran Smuggler Han Solo",
    "chewbacca": "Chewbacca",
    "veteran smuggler chewbacca": "Veteran Smuggler Chewbacca",
    "c-3po": "C-3PO",
    "r2-d2": "R2-D2",
    "cassian andor": "Cassian Andor",
    "k-2so": "K-2SO",
    "jyn erso": "Jyn Erso",
    "chirrut imwe": "Chirrut Îmwe",
    "baze malbus": "Baze Malbus",
    "bodhi rook": "Bodhi Rook",
    "saw gerrera": "Saw Gerrera",
    "scarif rebel pathfinder": "Scarif Rebel Pathfinder",
    "pao": "Pao",
    "bistan": "Bistan",
    "moroff": "Moroff",
    "l337": "L3-37",
    "qira": "Qi'ra",
    "young han solo": "Young Han Solo",
    "young lando calrissian": "Young Lando Calrissian",
    "vandor chewbacca": "Vandor Chewbacca",
    "l337": "L3-37",
    "enfy nest": "Enfys Nest",
    "wicket": "Wicket",
    "chief chirpa": "Chief Chirpa",
    "paploo": "Paploo",
    "teebo": "Teebo",
    "logray": "Logray",
    "ewok scout": "Ewok Scout",
    "ewok elder": "Ewok Elder",
    "princess kneesa": "Princess Kneesaa",
    "captain rex": "Captain Rex",
    "ct-7567 rex": "CT-7567 \"Rex\"",
    "ct-5555 fives": "CT-5555 \"Fives\"",
    "ct-210408 echo": "CT-21-0408 \"Echo\"",
    "arc trooper": "ARC Trooper",
    "clone sergeant": "Clone Sergeant - Phase I",
    "cody": "CC-2224 \"Cody\"",
    "general kenobi": "General Kenobi",
    "general skywalker": "General Skywalker",
    "bad batch hunter": "Hunter",
    "bad batch wrecker": "Wrecker",
    "bad batch tech": "Tech",
    "bad batch echo": "Echo",
    "bad batch omega": "Omega",
    "crosshair": "Crosshair (Scarred)",
    "commander ahsoka tano": "Commander Ahsoka Tano",
    "cat": "Commander Ahsoka Tano",
}


def normalize_character_name(name):
    """Нормализует имя персонажа для поиска"""
    name_lower = name.lower().strip()
    
    if name_lower in CHARACTER_NAME_MAPPING:
        return CHARACTER_NAME_MAPPING[name_lower]
    
    for key, value in CHARACTER_NAME_MAPPING.items():
        if key in name_lower or name_lower in key:
            return value
    
    return ' '.join(word.capitalize() for word in name_lower.split())


def get_player_ally_codes():
    """Извлекает ally_code всех игроков из guild_data.json"""
    if not os.path.exists(JSON_FILE_PATH):
        return []
    
    try:
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            guild_data = json.load(f)
        
        members = guild_data.get('data', {}).get('members', [])
        ally_codes = []
        
        for member in members:
            ally_code = member.get('ally_code')
            player_name = member.get('player_name', 'Unknown')
            if ally_code:
                ally_codes.append({
                    'ally_code': ally_code,
                    'player_name': player_name
                })
        
        logger.info(f"Найдено {len(ally_codes)} игроков с ally_code")
        return ally_codes
        
    except Exception as e:
        logger.error(f"Ошибка при получении ally_code: {e}")
        return []


async def download_player_data_async(session, ally_code):
    """Асинхронно скачивает данные игрока"""
    url = f"https://swgoh.gg/api/player/{ally_code}/"
    headers = {
		"Host": "swgoh.gg",
		"Connection": "keep-alive",
		"sec-ch-ua": "\"Not:A-Brand\";v=\"99\", \"Microsoft Edge\";v=\"145\", \"Chromium\";v=\"145\"",
		"sec-ch-ua-mobile": "?0",
		"sec-ch-ua-platform": "\"Windows\"",
		"Upgrade-Insecure-Requests": "1",
		"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0",
		"Accept": "application/json, text/plain, */*",
		"Sec-Fetch-Site": "same-origin",
		"Sec-Fetch-Mode": "cors",
		"Sec-Fetch-Dest": "empty",
		"Accept-Encoding": "gzip, deflate, br, zstd",
		"Accept-Language": "ru,en;q=0.9,en-GB;q=0.8,en-US;q=0.7",
		"Referer": "https://swgoh.gg/",
		"Origin": "https://swgoh.gg"
    }
    
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as response:
            if response.status == 200:
                return await response.json()
            else:
                logger.warning(f"Ошибка {response.status} для {ally_code}")
                return None
    except Exception as e:
        logger.error(f"Ошибка загрузки {ally_code}: {e}")
        return None


def find_character_in_player(player_data, character_name):
    """Ищет персонажа в данных игрока"""
    if not player_data or 'data' not in player_data:
        return None
    
    units = player_data.get('data', {}).get('units', [])
    search_name_lower = character_name.lower()
    
    for unit in units:
        unit_data = unit.get('data', {})
        unit_name = unit_data.get('name', '')
        unit_base_id = unit_data.get('base_id', '')
        
        if unit_name.lower() == search_name_lower:
            return _extract_character_data(unit_data, unit_name)
        
        if search_name_lower in unit_name.lower():
            return _extract_character_data(unit_data, unit_name)
        
        if search_name_lower in unit_base_id.lower():
            return _extract_character_data(unit_data, unit_name)
    
    return None


def _extract_character_data(unit_data, unit_name):
    """Извлекает данные персонажа"""
    return {
        'name': unit_name,
        'gear_level': unit_data.get('gear_level', 0),
        'relic_tier': unit_data.get('relic_tier'),
        'level': unit_data.get('level', 0),
        'power': unit_data.get('power', 0),
        'rarity': unit_data.get('rarity', 0),
        'zeta_abilities': len(unit_data.get('zeta_abilities', [])),
        'has_ultimate': unit_data.get('has_ultimate', False),
        'is_galactic_legend': unit_data.get('is_galactic_legend', False)
    }


async def scan_all_players_for_character_async(character_name, progress_callback=None):
    """Асинхронно сканирует всех игроков гильдии"""
    players = get_player_ally_codes()
    results = []
    total = len(players)
    
    normalized_search_name = normalize_character_name(character_name)
    logger.info(f"Поиск персонажа: '{character_name}' -> '{normalized_search_name}'")
    logger.info(f"Всего игроков для проверки: {total}")
    
    async with aiohttp.ClientSession() as session:
        for idx, player in enumerate(players):
            ally_code = player['ally_code']
            player_name = player['player_name']
            
            if progress_callback:
                await progress_callback(idx + 1, total, player_name)
            
            logger.info(f"Проверяю {idx+1}/{total}: {player_name}")
            
            player_data = await download_player_data_async(session, ally_code)
            
            if player_data:
                character_data = find_character_in_player(player_data, normalized_search_name)
                if character_data:
                    results.append({
                        'player_name': player_name,
                        'ally_code': ally_code,
                        'character': character_data
                    })
                    logger.info(f"  ✅ Найден {character_data['name']} у {player_name}")
    
    return results


# ========== Команды ==========
async def unit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ищет указанного персонажа у всех игроков гильдии"""
    username = update.effective_user.username
    
    if not context.args:
        await update.message.reply_text(
            "❌ Укажите имя персонажа.\n"
            "Пример: /unit Lord Vader\n"
            "Пример: /unit General Hux\n"
            "Пример: /unit SLKR\n\n"
            "💡 Можно использовать сокращения:\n"
            "• LV - Lord Vader\n"
            "• JMK - Jedi Master Kenobi\n"
            "• SLKR - Supreme Leader Kylo Ren\n"
            "• JML - Jedi Master Luke Skywalker\n"
            "• CAT - Commander Ahsoka Tano"
        )
        return
    
    character_name = ' '.join(context.args).strip()
    normalized_name = normalize_character_name(character_name)
    
    if not os.path.exists(JSON_FILE_PATH):
        await update.message.reply_text(
            "❌ Файл с данными гильдии не найден.\n"
            "Сначала выполните команду /update для загрузки данных."
        )
        return
    
    players = get_player_ally_codes()
    total_players = len(players)
    
    if total_players == 0:
        await update.message.reply_text("❌ Не удалось получить список игроков гильдии.")
        return
    
    status_message = await update.message.reply_text(
        f"🔍 Ищу персонажа *{normalized_name}*...\n"
        f"📊 Всего игроков: {total_players}\n"
        f"⏳ Начинаю проверку...",
        parse_mode='Markdown'
    )
    
    last_update_time = 0
    current_progress = 0
    
    async def update_progress(current, total, player_name):
        nonlocal last_update_time, current_progress, status_message
        
        current_progress = current
        
        # Обновляем сообщение не чаще чем раз в 2 секунды или на каждом 5м игроке
        import time
        now = time.time()
        if now - last_update_time >= 2 or current % 5 == 0 or current == total:
            last_update_time = now
            try:
                await status_message.edit_text(
                    f"🔍 Ищу персонажа *{normalized_name}*...\n"
                    f"📊 Всего игроков: {total}\n"
                    f"⏳ Проверено: {current}/{total}\n"
                    f"🔄 Текущий: {player_name[:25]}...\n\n"
                    f"⏱️ Пожалуйста, подождите...",
                    parse_mode='Markdown'
                )
            except Exception:
                pass
    
    try:
        await status_message.edit_text(
            f"🔍 Начинаю поиск *{normalized_name}*...\n"
            f"📊 Проверяю {total_players} игроков...\n"
            f"⏳ Это может занять 1-2 минуты.",
            parse_mode='Markdown'
        )
        
        results = await scan_all_players_for_character_async(normalized_name, update_progress)
        
        if not results:
            await status_message.edit_text(
                f"❌ Персонаж *{character_name}* не найден ни у одного из {total_players} игроков.\n\n"
                f"💡 Возможные причины:\n"
                f"• У игроков гильдии нет этого персонажа\n"
                f"• Попробуйте другое написание: /unit lv или /unit lord vader\n"
                f"• Используйте английское название персонажа",
                parse_mode='Markdown'
            )
            return
        
        # Формируем результат
        message = f"🔍 *Результаты поиска '{character_name}':*\n\n"
        message += f"✅ Найден у {len(results)} из {total_players} игроков:\n\n"
        
        for i, result in enumerate(results, 1):
            player_name = result['player_name']
            char_data = result['character']
            gear_level = char_data.get('gear_level', 'N/A')
            relic_tier = char_data.get('relic_tier', 'N/A')
            power = char_data.get('power', 'N/A')
            level = char_data.get('level', 'N/A')
            zeta_count = char_data.get('zeta_abilities', 0)
            is_gl = char_data.get('is_galactic_legend', False)
            
            gl_marker = " 👑" if is_gl else ""
            relic_str = f" 💎{relic_tier}" if relic_tier and relic_tier > 0 else ""
            
            message += f"{i}. *{player_name}*{gl_marker}\n"
            message += f"   🛡️{gear_level}{relic_str} | 📊 {power:,} | ⚔️{level}\n".replace(',', ' ')
            if zeta_count > 0:
                message += f"   ✨ Зета: {zeta_count}\n"
            message += "\n"
        
        if len(message) > 4000:
            short_message = f"🔍 *Найден {character_name} у {len(results)} игроков:*\n\n"
            for i, result in enumerate(results, 1):
                short_message += f"{i}. {result['player_name']}\n"
            
            await status_message.edit_text(short_message, parse_mode='Markdown')
            
            # Отправляем детали файлом
            details = f"🔍 Поиск '{character_name}'\n"
            details += "=" * 50 + "\n\n"
            for result in results:
                char_data = result['character']
                details += f"👤 {result['player_name']}\n"
                details += f"⚔️ {char_data['name']}\n"
                details += f"📈 Уровень: {char_data.get('level', 'N/A')}\n"
                details += f"🛡️ Снаряжение: {char_data.get('gear_level', 'N/A')}\n"
                if char_data.get('relic_tier'):
                    details += f"💎 Реликвия: {char_data.get('relic_tier')}\n"
                details += f"📊 Сила: {char_data.get('power', 'N/A'):,}\n".replace(',', ' ')
                details += "-" * 30 + "\n"
            
            safe_name = character_name.replace(' ', '_').replace('"', '').replace("'", '')
            filename = f"unit_{safe_name}.txt"
            filepath = os.path.join(DATA_FOLDER, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(details)
            
            await update.message.reply_document(
                document=open(filepath, 'rb'),
                filename=filename,
                caption=f"📄 Детали по '{character_name}'"
            )
        else:
            await status_message.edit_text(message, parse_mode='Markdown')
        
        logger.info(f"Поиск '{character_name}': найдено {len(results)} результатов")
        
    except Exception as e:
        logger.error(f"Ошибка при поиске: {e}", exc_info=True)
        await status_message.edit_text(
            f"❌ Ошибка: {str(e)[:200]}\n\n"
            f"Попробуйте позже или уточните имя персонажа."
        )


async def unit_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает информацию о конкретном юните у конкретного игрока"""
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Укажите игрока и персонажа.\n"
            "Пример: /unit_info Qbik Lord Vader"
        )
        return
    
    player_name = context.args[0]
    character_name = ' '.join(context.args[1:]).strip()
    normalized_name = normalize_character_name(character_name)
    
    if not os.path.exists(JSON_FILE_PATH):
        await update.message.reply_text("❌ Сначала выполните /update")
        return
    
    try:
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            guild_data = json.load(f)
        
        members = guild_data.get('data', {}).get('members', [])
        ally_code = None
        actual_player_name = player_name
        
        for member in members:
            if member.get('player_name', '').lower() == player_name.lower():
                ally_code = member.get('ally_code')
                actual_player_name = member.get('player_name')
                break
        
        if not ally_code:
            matches = [m.get('player_name') for m in members if player_name.lower() in m.get('player_name', '').lower()]
            if matches:
                await update.message.reply_text(
                    f"❌ Игрок не найден.\n💡 Возможно: " + ", ".join(matches[:3])
                )
            else:
                await update.message.reply_text(f"❌ Игрок \"{player_name}\" не найден.")
            return
        
        status_message = await update.message.reply_text(f"🔍 Загружаю данные...")
        
        async with aiohttp.ClientSession() as session:
            player_data = await download_player_data_async(session, ally_code)
        
        if not player_data:
            await status_message.edit_text(f"❌ Не удалось загрузить данные.")
            return
        
        character_data = find_character_in_player(player_data, normalized_name)
        
        if not character_data:
            character_data = find_character_in_player(player_data, character_name)
        
        if not character_data:
            await status_message.edit_text(
                f"❌ У игрока *{actual_player_name}* не найден персонаж *{character_name}*.\n\n"
                f"💡 Используйте /unit для поиска всех игроков с этим персонажем.",
                parse_mode='Markdown'
            )
            return
        
        gear_level = character_data.get('gear_level', 'N/A')
        relic_tier = character_data.get('relic_tier', 'N/A')
        power = character_data.get('power', 'N/A')
        level = character_data.get('level', 'N/A')
        rarity = character_data.get('rarity', 'N/A')
        zeta_count = character_data.get('zeta_abilities', 0)
        is_gl = character_data.get('is_galactic_legend', False)
        has_ultimate = character_data.get('has_ultimate', False)
        
        gl_marker = " 👑 ГЛ" if is_gl else ""
        ultimate_marker = " 🔥 Ультимейт" if has_ultimate else ""
        
        message = f"📊 *{character_data['name']}*{gl_marker}{ultimate_marker}\n"
        message += f"👤 Игрок: {actual_player_name}\n"
        message += f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        message += f"📈 Уровень: {level}\n"
        message += f"🛡️ Снаряжение: {gear_level}\n"
        if relic_tier and relic_tier > 0:
            message += f"💎 Реликвия: {relic_tier}\n"
        message += f"📊 Сила: {power:,}\n".replace(',', ' ')
        message += f"⭐ Звездность: {rarity}\n"
        message += f"✨ Зета: {zeta_count}\n"
        
        await status_message.edit_text(message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)[:200]}")