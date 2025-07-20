import sqlite3
from contextlib import closing

conn = sqlite3.connect('trade_stats.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy TEXT,
    pair TEXT,
    timeframe TEXT,
    successful_trades INTEGER,
    failed_trades INTEGER,
    profit REAL,
    start_time TEXT,
    end_time TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS overall_stats (
    strategy TEXT PRIMARY KEY,
    total_successful INTEGER,
    total_failed INTEGER,
    total_profit REAL
)
''')
conn.commit()

def save_session(strategy, pair, timeframe, successful, failed, profit, start, end):
    with closing(conn.cursor()) as cur:
        cur.execute('''
        INSERT INTO sessions (strategy, pair, timeframe, successful_trades, failed_trades, profit, start_time, end_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (strategy, pair, timeframe, successful, failed, profit, start, end))
        conn.commit()

def update_overall(strategy, successful, failed, profit):
    with closing(conn.cursor()) as cur:
        cur.execute('SELECT * FROM overall_stats WHERE strategy=?', (strategy,))
        row = cur.fetchone()
        if row:
            total_succ = row[1] + successful
            total_fail = row[2] + failed
            total_prof = row[3] + profit
            cur.execute('''
            UPDATE overall_stats SET total_successful=?, total_failed=?, total_profit=?
            WHERE strategy=?
            ''', (total_succ, total_fail, total_prof, strategy))
        else:
            cur.execute('''
            INSERT INTO overall_stats (strategy, total_successful, total_failed, total_profit)
            VALUES (?, ?, ?, ?)
            ''', (strategy, successful, failed, profit))
        conn.commit()

def get_overall_stats(strategy):
    with closing(conn.cursor()) as cur:
        cur.execute('SELECT * FROM overall_stats WHERE strategy=?', (strategy,))
        return cur.fetchone()

def get_last_sessions(strategy, limit=5):
    with closing(conn.cursor()) as cur:
        cur.execute('''
        SELECT * FROM sessions WHERE strategy=? ORDER BY id DESC LIMIT ?
        ''', (strategy, limit))
        return cur.fetchall()
