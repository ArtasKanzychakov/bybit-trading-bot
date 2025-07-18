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
