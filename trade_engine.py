# trade_engine.py

active = False

def start_trading(exchange, symbol, timeframe):
    global active
    active = True

    print(f"[Стратегия 1] Запущена торговля: {symbol} / {timeframe}")
    # Здесь ты реализуешь свою стратегию с индикаторами
    # Например: Bollinger Bands + RSI + Volume

def stop_trading():
    global active
    active = False
    print("Торговля остановлена.")
