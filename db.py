import sqlite3
from contextlib import closing

DB_NAME = 'trading_bot.db'

def init_db():
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
                    profit REAL
                )
            ''')

def add_trade(strategy, symbol, entry_price, volume, entry_time):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute('''
                INSERT INTO trades (strategy, symbol, entry_price, volume, entry_time)
                VALUES (?, ?, ?, ?, ?)
            ''', (strategy, symbol, entry_price, volume, entry_time))

def close_trade(trade_id, exit_price, exit_time, profit):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute('''
                UPDATE trades
                SET exit_price = ?, exit_time = ?, profit = ?
                WHERE id = ?
            ''', (exit_price, exit_time, profit, trade_id))

def get_open_trades():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        cur = conn.cursor()
        cur.execute('SELECT * FROM trades WHERE exit_price IS NULL')
        return cur.fetchall()

def get_all_trades():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        cur = conn.cursor()
        cur.execute('SELECT * FROM trades')
        return cur.fetchall()

# Инициализация базы при первом запуске
init_db()
