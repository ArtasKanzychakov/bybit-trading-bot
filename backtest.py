import ccxt
import pandas as pd
import ta
from config import *

# Загрузка исторических данных
def fetch_historical_data(symbol, timeframe, limit=1000):
    exchange = ccxt.bybit()
    candles = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    return df

# Логика бэктестинга
def backtest(df):
    df = get_data(df)  # Используем ту же функцию get_data()
    df['signal'] = df.apply(check_signal, axis=1)
    df['pnl'] = df['close'].pct_change() * df['signal'].shift(1) * LEVERAGE
    return df['pnl'].sum()

# Запуск
data = fetch_historical_data(SYMBOL, TIMEFRAME)
profit = backtest(data)
print(f"📊 Тест стратегии: {profit * 100:.2f}%")
