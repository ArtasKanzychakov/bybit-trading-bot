import sqlite3
from contextlib import closing
from datetime import datetime
from typing import List, Tuple, Optional

DB_NAME = 'trading_bot.db'

def init_db():
    """Инициализирует базу данных с необходимыми таблицами"""
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    volume REAL NOT NULL,
                    entry_time TEXT NOT NULL,
                    exit_time TEXT,
                    profit REAL,
                    status TEXT NOT NULL DEFAULT 'open'
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    user_id INTEGER PRIMARY KEY,
                    default_strategy TEXT,
                    default_symbol TEXT,
                    risk_per_trade REAL DEFAULT 0.01
                )
            ''')

def add_trade(strategy: str, symbol: str, entry_price: float, volume: float) -> int:
    """Добавляет новую сделку в базу данных"""
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            cursor = conn.execute('''
                INSERT INTO trades (strategy, symbol, entry_price, volume, entry_time, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (strategy, symbol, entry_price, volume, datetime.utcnow().isoformat(), 'open'))
            return cursor.lastrowid

def close_trade(trade_id: int, exit_price: float, profit: float):
    """Закрывает сделку и записывает результат"""
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute('''
                UPDATE trades
                SET exit_price = ?, exit_time = ?, profit = ?, status = 'closed'
                WHERE id = ?
            ''', (exit_price, datetime.utcnow().isoformat(), profit, trade_id))

def get_open_trades() -> List[Tuple]:
    """Возвращает список открытых сделок"""
    with closing(sqlite3.connect(DB_NAME)) as conn:
        cur = conn.cursor()
        cur.execute('SELECT * FROM trades WHERE status = "open"')
        return cur.fetchall()

def get_trade_history(limit: int = 100) -> List[Tuple]:
    """Возвращает историю сделок"""
    with closing(sqlite3.connect(DB_NAME)) as conn:
        cur = conn.cursor()
        cur.execute('SELECT * FROM trades ORDER BY entry_time DESC LIMIT ?', (limit,))
        return cur.fetchall()

def get_user_settings(user_id: int) -> Optional[Tuple]:
    """Возвращает настройки пользователя"""
    with closing(sqlite3.connect(DB_NAME)) as conn:
        cur = conn.cursor()
        cur.execute('SELECT * FROM settings WHERE user_id = ?', (user_id,))
        return cur.fetchone()

def update_user_settings(user_id: int, strategy: str = None, symbol: str = None, risk: float = None):
    """Обновляет настройки пользователя"""
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            settings = get_user_settings(user_id)
            if not settings:
                conn.execute('''
                    INSERT INTO settings (user_id, default_strategy, default_symbol, risk_per_trade)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, strategy, symbol, risk))
            else:
                updates = []
                params = []
                if strategy:
                    updates.append("default_strategy = ?")
                    params.append(strategy)
                if symbol:
                    updates.append("default_symbol = ?")
                    params.append(symbol)
                if risk:
                    updates.append("risk_per_trade = ?")
                    params.append(risk)
                
                if updates:
                    params.append(user_id)
                    conn.execute(
                        f"UPDATE settings SET {', '.join(updates)} WHERE user_id = ?",
                        params
                    )

# Инициализация базы при первом запуске
init_db()
