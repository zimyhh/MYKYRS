import sqlite3
from datetime import datetime, timedelta

DB_NAME = 'focus_bot.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, username TEXT, total_time INTEGER DEFAULT 0, last_session DATE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS sessions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, start_time TEXT, end_time TEXT, duration INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS achievements
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, achievement TEXT, type TEXT, date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS streak
                 (user_id INTEGER PRIMARY KEY, streak INTEGER DEFAULT 0, last_session_date DATE)''')
    conn.commit()
    conn.close()

def check_monthly_table():
    """Создает таблицу для месячного фокуса если нужно"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    current_month = datetime.now().strftime('%Y_%m')
    table_name = f'monthly_focus_{current_month}'
    c.execute(f'''CREATE TABLE IF NOT EXISTS {table_name}
                 (user_id INTEGER PRIMARY KEY, total_minutes INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

def add_user(user_id, username):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
    conn.commit()
    conn.close()

def save_session(user_id, start_time, end_time, duration):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''INSERT INTO sessions (user_id, start_time, end_time, duration)
                 VALUES (?, ?, ?, ?)''',
              (user_id, start_time.isoformat(), end_time.isoformat(), duration))
    c.execute('UPDATE users SET total_time = total_time + ?, last_session = ? WHERE user_id = ?', 
              (duration, datetime.now().date(), user_id))
    conn.commit()
    conn.close()

def get_total_time(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT total_time FROM users WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def get_sessions_count(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM sessions WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def add_achievement(user_id, achievement_text, achievement_type):
    """Добавляет достижение и возвращает True если оно уже есть"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT id FROM achievements WHERE user_id = ? AND achievement = ?', (user_id, achievement_text))
    if c.fetchone():
        conn.close()
        return True
    
    c.execute('INSERT INTO achievements (user_id, achievement, type, date) VALUES (?, ?, ?, ?)',
              (user_id, achievement_text, achievement_type, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return False

def get_achievements(user_id):
    """Получает все достижения пользователя"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT achievement FROM achievements WHERE user_id = ? ORDER BY date DESC', (user_id,))
    result = c.fetchall()
    conn.close()
    return result

def add_monthly_focus(user_id, minutes):
    """Добавляет время фокуса в месячную таблицу"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    current_month = datetime.now().strftime('%Y_%m')
    table_name = f'monthly_focus_{current_month}'
    
    c.execute(f'INSERT OR IGNORE INTO {table_name} (user_id) VALUES (?)', (user_id,))
    c.execute(f'UPDATE {table_name} SET total_minutes = total_minutes + ? WHERE user_id = ?', 
              (minutes, user_id))
    conn.commit()
    conn.close()

def get_streak(user_id):
    """Получает текущую серию фокуса"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT streak FROM streak WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def update_streak(user_id):
    """Обновляет серию фокуса"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    today = datetime.now().date()
    
    c.execute('SELECT streak, last_session_date FROM streak WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    
    if result:
        streak, last_date = result
        last_date = datetime.strptime(last_date, '%Y-%m-%d').date() if last_date else None
        
        if last_date == today:
            pass
        elif last_date == today - timedelta(days=1):
            streak += 1
            c.execute('UPDATE streak SET streak = ?, last_session_date = ? WHERE user_id = ?',
                      (streak, today, user_id))
        else:
            c.execute('UPDATE streak SET streak = 1, last_session_date = ? WHERE user_id = ?',
                      (today, user_id))
    else:
        c.execute('INSERT INTO streak (user_id, streak, last_session_date) VALUES (?, 1, ?)',
                  (user_id, today))
    
    conn.commit()
    conn.close()