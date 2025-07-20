import time
import logging

logger = logging.getLogger(__name__)

def get_balance(exchange):
    try:
        balance = exchange.fetch_balance()
        usdt_balance = balance['total'].get('USDT', 0)
        return f"Баланс USDT: {usdt_balance}"
    except Exception as e:
        logger.error(f"Ошибка при получении баланса: {e}")
        return "Не удалось получить баланс."

def start_trading(exchange, symbol, timeframe):
    logger.info(f"Начинаем торговлю на {symbol} с таймфреймом {timeframe}")
    try:
        for i in range(10):
            ticker = exchange.fetch_ticker(symbol)
            price = ticker['last']
            logger.info(f"[{i+1}/10] Цена {symbol}: {price}")
            time.sleep(5)
    except Exception as e:
        logger.error(f"Ошибка в торговле: {e}")

def stop_trading():
    logger.info("Остановка торговли по запросу.")
