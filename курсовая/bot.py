import telebot
from telebot import types
import os
import subprocess
from datetime import datetime, timedelta
import threading
import sys

try:
    from database import (
        init_db, 
        add_user, 
        save_session, 
        get_total_time, 
        get_sessions_count, 
        add_achievement, 
        get_achievements, 
        check_monthly_table, 
        add_monthly_focus, 
        get_streak, 
        update_streak
    )
except ImportError as e:
    print(f"Ошибка импорта database.py: {e}")
    sys.exit(1)

TOKEN = "8263245399:AAHKdcG4Q105UJauLmfECSNR20Xycq_oRF4"
bot = telebot.TeleBot(TOKEN)

#ну работает база или нет
try:
    init_db()
    check_monthly_table()
    print("База данных успешно подключена")
except Exception as e:
    print(f"Ошибка при инициализации БД: {e}")

active_sessions = {}
paused_sessions = {}

# Заблокированные софты (хаха чувствую себя РКН)
BLOCKED_APPS = [
    'steam.exe',
    'epicgameslauncher.exe',
    'uplay.exe',
    'battlenet.exe',
    'gog.exe',
    'discord.exe',
]

# Ачивки по времени
TIME_ACHIEVEMENTS = [
    (5, "🎯 Первый шаг: 5 минут фокуса"),
    (15, "⏱️ Растущий фокус: 15 минут"),
    (30, "💪 Мастер концентрации: 30 минут"),
    (60, "👑 Король фокуса: 1 час"),
    (180, "🔥 Супер фокус: 3 часа"),
    (360, "⚡ Легендарный ученик: 6 часов"),
]

# Ачивки за использование
BOT_ACHIEVEMENTS = [
    (1, "🤖 Первая неделя с ботом"),
    (2, "📈 Две недели мастерства"),
    (4, "🏆 Месяц совершенства"),
    (8, "👏 Двухмесячный чемпион"),
    (12, "⭐ Трёхмесячный герой"),
    (26, "🌟 Полугодовой легендарий"),
]

#═══════════════════════════════════════════════════════════════════════════════
# Кнопочки возврата
#═══════════════════════════════════════════════════════════════════════════════

def get_main_menu_markup():
    markup = types.InlineKeyboardMarkup()
    btn_start = types.InlineKeyboardButton(text="🚀 Начать сессию", callback_data="start_session")
    btn_stats = types.InlineKeyboardButton(text="📊 Статистика", callback_data="show_stats")
    btn_achievements = types.InlineKeyboardButton(text="🏅 Достижения", callback_data="show_achievements")
    markup.add(btn_start)
    markup.add(btn_stats)
    markup.add(btn_achievements)
    return markup

def get_back_button():
    markup = types.InlineKeyboardMarkup()
    btn_back = types.InlineKeyboardButton(text="◀️ Вернуться в меню", callback_data="back_to_menu")
    markup.add(btn_back)
    return markup

def get_session_controls():
    markup = types.InlineKeyboardMarkup()
    btn_stop = types.InlineKeyboardButton(text="⏸️ STOP", callback_data="pause_session")
    btn_close = types.InlineKeyboardButton(text="❌ CLOSE", callback_data="confirm_close_session")
    markup.add(btn_stop, btn_close)
    return markup

#═══════════════════════════════════════════════════════════════════════════════
# БЛОК РКН
#═══════════════════════════════════════════════════════════════════════════════

def block_apps(user_id):
    while user_id in active_sessions:
        try:
            result = subprocess.check_output('tasklist', shell=True).decode('utf-8', errors='ignore')
            
            for app in BLOCKED_APPS:
                if app.lower() in result.lower():
                    os.system(f'taskkill /IM {app} /F')
                    bot.send_message(user_id, f"Приложение {app} было закрыто!\n Фокусируйтесь на учебе!")
            
            threading.Event().wait(2)
        except Exception as e:
            print(f"Ошибка при блокировке приложений: {e}")

#═══════════════════════════════════════════════════════════════════════════════
# Золото за ачивочки
#═══════════════════════════════════════════════════════════════════════════════

def check_achievements(user_id, total_time):
    """Проверяет и выдает достижения по времени"""
    for time_needed, achievement_text in TIME_ACHIEVEMENTS:
        if total_time >= time_needed:
            if not add_achievement(user_id, achievement_text, "time"):
                bot.send_message(user_id, f"🏅 НОВОЕ ДОСТИЖЕНИЕ!\n{achievement_text}")

def check_bot_usage_achievements(user_id, weeks):
    """Проверяет достижения за пользование ботом"""
    for weeks_needed, achievement_text in BOT_ACHIEVEMENTS:
        if weeks >= weeks_needed:
            if not add_achievement(user_id, achievement_text, "bot_usage"):
                bot.send_message(user_id, f"🏅 НОВОЕ ДОСТИЖЕНИЕ!\n{achievement_text}")

#═══════════════════════════════════════════════════════════════════════════════
# Ну тут короче меню да старт все дела 
#═══════════════════════════════════════════════════════════════════════════════

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username
    add_user(user_id, username)
    
    welcome_text = f"""
🎓 FOCUS BOT - УЧЕБНЫЙ ПОМОЩНИК
Привет, {username}! 👋

Этот бот поможет тебе:
✅ Улучшить концентрацию
✅ Повысить продуктивность
✅ Получать достижения
✅ Блокировать отвлекающие игры

Нажми кнопку чтобы начать! 💪
    """
    
    bot.reply_to(message, welcome_text, reply_markup=get_main_menu_markup())

#═══════════════════════════════════════════════════════════════════════════════
# Сам блок с фокусировкой
#═══════════════════════════════════════════════════════════════════════════════

@bot.callback_query_handler(func=lambda call: call.data == "start_session")
def handle_start_session(call):
    user_id = call.from_user.id
    
    if user_id in active_sessions:
        bot.answer_callback_query(call.id, "⚠️ У вас уже идет активная сессия!")
        return
    
    markup = types.InlineKeyboardMarkup()
    btn_5 = types.InlineKeyboardButton(text="⏱️ 5 мин", callback_data="session_5")
    btn_15 = types.InlineKeyboardButton(text="⏲️ 15 мин", callback_data="session_15")
    btn_30 = types.InlineKeyboardButton(text="🕐 30 мин", callback_data="session_30")
    btn_60 = types.InlineKeyboardButton(text="🕰️ 1 час", callback_data="session_60")
    markup.add(btn_5, btn_15)
    markup.add(btn_30, btn_60)
    markup.add(types.InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu"))
    
    text = "⏰ ВЫБЕРИ ВРЕМЯ СЕССИИ"
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

#═══════════════════════════════════════════════════════════════════════════════
# Тут статистика сессии
#═══════════════════════════════════════════════════════════════════════════════
@bot.callback_query_handler(func=lambda call: call.data.startswith("session_"))
def handle_session_time(call):
   
    user_id = call.from_user.id
    minutes = int(call.data.split("_")[1])
    
    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=minutes)
    
    active_sessions[user_id] = {
        'start_time': start_time,
        'end_time': end_time,
        'minutes': minutes,
        'chat_id': call.message.chat.id,
        'message_id': call.message.message_id
    }
    
    bot.answer_callback_query(call.id)
    
    session_text = f"""
✅ СЕССИЯ НАЧАЛАСЬ!

⏱️ Длительность: {minutes} минут
🕐 Начало: {start_time.strftime('%H:%M:%S')}
🏁 Конец: {end_time.strftime('%H:%M:%S')}

🎮 Игровые лаунчеры заблокированы
📱 Не отвлекайтесь!
💪 Удачи в учебе!
    """
    
    bot.edit_message_text(session_text, call.message.chat.id, call.message.message_id, reply_markup=get_session_controls())
    
    threading.Thread(target=block_apps, args=(user_id,)).start()
    threading.Thread(target=session_timer, args=(user_id, minutes, start_time, end_time)).start()

#═══════════════════════════════════════════════════════════════════════════════
# Конец.
#═══════════════════════════════════════════════════════════════════════════════

def session_timer(user_id, minutes, start_time, end_time):
    import time
    time.sleep(minutes * 60)
    
    if user_id in active_sessions:
        session_data = active_sessions.pop(user_id)
        save_session(user_id, start_time, end_time, minutes)
        add_monthly_focus(user_id, minutes)
        
        total_time = get_total_time(user_id)
        check_achievements(user_id, total_time)
        
        update_streak(user_id)
        
        end_text = f"""
🎉 СЕССИЯ ЗАВЕРШЕНА!

⏱️ Время: {minutes} минут
📊 Всего часов: {total_time // 60}ч {total_time % 60}м

👏 ОТЛИЧНАЯ РАБОТА! 👏
 
Ты становишься сильнее! 💪
        """
        
        bot.send_message(user_id, end_text, reply_markup=get_main_menu_markup())

#═════════════════════════════════════════════════════════════════════════
# Пауза нужна ли? (нужна)
#═══════════════════════════════════════════════════════════════════════════════

@bot.callback_query_handler(func=lambda call: call.data == "pause_session")
def pause_session(call):
    user_id = call.from_user.id
    
    if user_id not in active_sessions:
        bot.answer_callback_query(call.id, "❌ Активная сессия не найдена!")
        return
    
    session_data = active_sessions.pop(user_id)
    paused_sessions[user_id] = session_data
    
    bot.answer_callback_query(call.id)
    
    pause_text = """
⏸️ СЕССИЯ ПРИОСТАНОВЛЕНА

Хотите возобновить таймер?
    """
    
    markup = types.InlineKeyboardMarkup()
    btn_restart = types.InlineKeyboardButton(text="🔄 RESTART", callback_data="restart_session")
    btn_discard = types.InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="back_to_menu")
    markup.add(btn_restart, btn_discard)
    
    bot.edit_message_text(pause_text, call.message.chat.id, call.message.message_id, reply_markup=markup)

#═══════════════════════════════════════════════════════════════════════════════
# Без этой кнопки никак не запустить снова
#═══════════════════════════════════════════════════════════════════════════════

@bot.callback_query_handler(func=lambda call: call.data == "restart_session")
def restart_session(call):
    user_id = call.from_user.id
    
    if user_id not in paused_sessions:
        bot.answer_callback_query(call.id, "❌ Нет приостановленной сессии!")
        return
    
    session_data = paused_sessions.pop(user_id)
    active_sessions[user_id] = session_data
    
    bot.answer_callback_query(call.id)
    
    remaining_time = (session_data['end_time'] - datetime.now()).total_seconds()
    minutes_left = int(remaining_time // 60)
    
    resume_text = f"""
✅ СЕССИЯ ВОЗОБНОВЛЕНА!

⏱️ Осталось: {minutes_left} минут
🏁 Конец: {session_data['end_time'].strftime('%H:%M:%S')}

💪 Продолжай фокусироваться!
    """
    
    bot.edit_message_text(resume_text, call.message.chat.id, call.message.message_id, reply_markup=get_session_controls())
    
    threading.Thread(target=session_timer_resume, args=(user_id, session_data['start_time'], session_data['end_time'], session_data['minutes'])).start()

#═══════════════════════════════════════════════════════════════════════════════
# нужно чтобы он мог возобновить таймер
#═══════════════════════════════════════════════════════════════════════════════
def session_timer_resume(user_id, start_time, end_time, original_minutes):
    import time
    
    remaining_time = (end_time - datetime.now()).total_seconds()
    time.sleep(remaining_time)
    
    if user_id in active_sessions:
        active_sessions.pop(user_id)
        save_session(user_id, start_time, end_time, original_minutes)
        add_monthly_focus(user_id, original_minutes)
        
        total_time = get_total_time(user_id)
        check_achievements(user_id, total_time)
        
        update_streak(user_id)
        
        end_text = f"""
🎉 СЕССИЯ ЗАВЕРШЕНА!

⏱️ Время: {original_minutes} минут
📊 Всего часов: {total_time // 60}ч {total_time % 60}м

👏 ОТЛИЧНАЯ РАБОТА! 👏
 
Ты становишься сильнее! 💪
        """
        
        bot.send_message(user_id, end_text, reply_markup=get_main_menu_markup())

#═══════════════════════════════════════════════════════════════════════════════
# это блок нету стержня
#═══════════════════════════════════════════════════════════════════════════════

@bot.callback_query_handler(func=lambda call: call.data == "confirm_close_session")
def confirm_close_session(call):
    user_id = call.from_user.id
    
    if user_id not in active_sessions:
        bot.answer_callback_query(call.id, "❌ Активная сессия не найдена!")
        return
    
    bot.answer_callback_query(call.id)
    
    confirm_text = """
❌ ЗАКРЫТЬ СЕССИЮ?

⚠️ Внимание: это время не будет засчитано!

Вы уверены?
    """
    
    markup = types.InlineKeyboardMarkup()
    btn_yes = types.InlineKeyboardButton(text="✅ ДА", callback_data="close_session_yes")
    btn_no = types.InlineKeyboardButton(text="❌ НЕТ", callback_data="close_session_no")
    markup.add(btn_yes, btn_no)
    
    bot.edit_message_text(confirm_text, call.message.chat.id, call.message.message_id, reply_markup=markup)

#═══════════════════════════════════════════════════════════════════════════════
# Ну точно нет стержня
#═══════════════════════════════════════════════════════════════════════════════

@bot.callback_query_handler(func=lambda call: call.data == "close_session_yes")
def close_session_yes(call):
    user_id = call.from_user.id
    
    if user_id in active_sessions:
        active_sessions.pop(user_id)
    
    if user_id in paused_sessions:
        paused_sessions.pop(user_id)
    
    bot.answer_callback_query(call.id)
    
    closed_text = """
✅ СЕССИЯ ЗАКРЫТА

Время не было засчитано.
Возвращаемся в меню...
    """
    
    bot.edit_message_text(closed_text, call.message.chat.id, call.message.message_id, reply_markup=get_main_menu_markup())

#═══════════════════════════════════════════════════════════════════════════════
# Появилась надежда на стержень
#═══════════════════════════════════════════════════════════════════════════════

@bot.callback_query_handler(func=lambda call: call.data == "close_session_no")
def close_session_no(call):
    user_id = call.from_user.id
    
    bot.answer_callback_query(call.id)
    
    resume_text = """
✅ СЕССИЯ ПРОДОЛЖАЕТСЯ

Продолжай фокусироваться!
    """
    
    bot.edit_message_text(resume_text, call.message.chat.id, call.message.message_id, reply_markup=get_session_controls())

#═══════════════════════════════════════════════════════════════════════════════
# Сколько часов у тебя был стержень
#═══════════════════════════════════════════════════════════════════════════════

@bot.callback_query_handler(func=lambda call: call.data == "show_stats")
def handle_show_stats(call):
    """Статистика сессии"""
    user_id = call.from_user.id
    
    total_time = get_total_time(user_id)
    sessions_count = get_sessions_count(user_id)
    streak = get_streak(user_id)
    
    hours = total_time // 60
    mins = total_time % 60
    
    bot.answer_callback_query(call.id)
    
    stats_text = f"""
📊 ТВОЯ СТАТИСТИКА

⏱️ Всего в фокусе: {hours}ч {mins}м
📌 Количество сессий: {sessions_count}
🔥 Текущая серия: {streak} дней

Хорошая работа, продолжай! 💪
    """
    
    bot.edit_message_text(stats_text, call.message.chat.id, call.message.message_id, reply_markup=get_back_button())

#═══════════════════════════════════════════════════════════════════════════════
# Блок ачивок (красивое)
#═══════════════════════════════════════════════════════════════════════════════

@bot.callback_query_handler(func=lambda call: call.data == "show_achievements")
def handle_show_achievements(call):
    user_id = call.from_user.id
    
    achievements = get_achievements(user_id)
    streak = get_streak(user_id)
    
    bot.answer_callback_query(call.id)
    
    if not achievements:
        achievement_text = "Пока нет достижений. Начни сессию чтобы получить первое! 🚀"
    else:
        achievement_text = "🏅 ТВОИ ДОСТИЖЕНИЯ\n"
        achievement_text += "═" * 32 + "\n\n"
        achievement_text += f"🔥 СЕРИЯ ФОКУСА: {streak} дней\n\n"
        achievement_text += "─" * 32 + "\n"
        
        for idx, achievement in enumerate(achievements, 1):
            achievement_text += f"{idx}. {achievement[0]}\n"
    
    bot.edit_message_text(achievement_text, call.message.chat.id, call.message.message_id, reply_markup=get_back_button())

#═══════════════════════════════════════════════════════════════════════════════
# Возврат в ПТУ
#═══════════════════════════════════════════════════════════════════════════════

@bot.callback_query_handler(func=lambda call: call.data == "back_to_menu")
def back_to_menu(call):
    bot.answer_callback_query(call.id)
    
    welcome_text = """
🎓 FOCUS BOT - ГЛАВНОЕ МЕНЮ

Выбери действие:
    """
    
    bot.edit_message_text(welcome_text, call.message.chat.id, call.message.message_id, reply_markup=get_main_menu_markup())

#═══════════════════════════════════════════════════════════════════════════════
#Тута будет секретная команда
#═══════════════════════════════════════════════════════════════════════════════
@bot.message_handler(commands=['secret'])
def secret_command(message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    secret_text = f"""
🔐 СЕКРЕТНАЯ КОМАНДА АКТИВИРОВАНА!
Коды GTA SAN ANDREAS разблокированы для пользователя {username} ({user_id}).
КОДЫ:
- Набор оружия 1: LXGIWYL
- Набор оружия 2: KJKSZPJ
- Набор оружия 3: UZUMYMW
- Полный боекомплект: WANRLTW
- Бессмертие на 5 минут: AEZAKMI
- Максимальное здоровье и броня: HESOYAM
- Уровень розыска +2: OSRBLHH
- Снижение уровня розыска: ASNAEB
- Полный боезапас: FULLCLIP
- Супер прыжок: KANGAROO
- Быстрый бег: CATCHME
- Быстрая езда: SPEEDFREAK
- Невидимость: WHEELSONLYPLEASE
    """
    
    bot.reply_to(message, secret_text)

bot.polling(none_stop=True)