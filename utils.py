from datetime import datetime
import os
import ccxt

def get_exchange(test_mode: bool):
    params = {
        'apiKey': os.getenv('BYBIT_API_KEY'),
        'secret': os.getenv('BYBIT_SECRET'),
    }
    if test_mode:
        return ccxt.bybit({'test': True, **params})
    return ccxt.bybit(params)

def now():
    return datetime.utcnow()
def get_balance(exchange):
    try:
        balance = exchange.fetch_balance()
        usdt_balance = balance['total'].get('USDT', 0)
        return f"💰 Баланс: {usdt_balance} USDT"
    except Exception as e:
        return f"Ошибка получения баланса: {e}"
