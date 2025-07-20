from datetime import datetime

def now_iso():
    return datetime.utcnow().isoformat()

def log_trade_entry(strategy, symbol, price, volume):
    print(f"[{now_iso()}] Старт сделки: стратегия={strategy}, символ={symbol}, цена={price}, объём={volume}")

def log_trade_exit(trade_id, price, profit):
    print(f"[{now_iso()}] Закрыта сделка {trade_id}: цена выхода={price}, прибыль={profit}")
