import ccxt
import time
import threading
import pandas as pd
from datetime import datetime
from strategy_one import strategy_one
from strategy_two import strategy_two
from db import save_session, update_overall

class Trader:
    def __init__(self, api_key, api_secret):
        self.exchange = ccxt.bybit({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
        })
        self.running = False
        self.strategy = None
        self.pair = None
        self.timeframe = '15m'
        self.successful_trades = 0
        self.failed_trades = 0
        self.profit = 0
        self.session_start = None
        self.thread = None

    def fetch_data(self, pair, timeframe='15m', limit=100):
        bars = self.exchange.fetch_ohlcv(pair, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df

    def run_strategy(self, strategy_func):
        df = self.fetch_data(self.pair, self.timeframe)
        df = strategy_func(df)
        last_signal = df['signal'].iloc[-1]
        # Для упрощения: лонг = открыть позицию, шорт = открыть шорт, exit = закрыть позицию
        return last_signal

    def trade_loop(self):
        self.session_start = datetime.utcnow()
        position = None
        self.successful_trades = 0
        self.failed_trades = 0
        self.profit = 0
        while self.running:
            try:
                if self.strategy == 'strategy_one':
                    signal = self.run_strategy(strategy_one)
                elif self.strategy == 'strategy_two':
                    signal = self.run_strategy(strategy_two)
                else:
                    signal = 'hold'

                if signal == 'buy' and position != 'long':
                    self.open_position('long')
                    position = 'long'
                elif signal == 'sell' and position != 'short':
                    self.open_position('short')
                    position = 'short'
                elif signal == 'exit' and position is not None:
                    self.close_position(position)
                    position = None

                time.sleep(15 * 60)  # ждать таймфрейм (15 мин)
            except Exception as e:
                print(f"Ошибка в торговом цикле: {e}")
                time.sleep(60)

        # Сессия окончена
        save_session(self.strategy, self.pair, self.timeframe, self.successful_trades, self.failed_trades, self.profit, self.session_start.isoformat(), datetime.utcnow().isoformat())
        update_overall(self.strategy, self.successful_trades, self.failed_trades, self.profit)

    def open_position(self, side):
        print(f"Открываем позицию {side} на {self.pair}")
        # TODO: реализовать реальные заявки через API Bybit
        # Для демо - просто считаем успех
        self.successful_trades += 1
        self.profit += 10  # фиктивная прибыль

    def close_position(self, side):
        print(f"Закрываем позицию {side} на {self.pair}")

    def start(self, strategy, pair, timeframe='15m'):
        if self.running:
            print("Уже запущен")
            return
        self.strategy = strategy
        self.pair = pair
        self.timeframe = timeframe
        self.running = True
        self.thread = threading.Thread(target=self.trade_loop)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
