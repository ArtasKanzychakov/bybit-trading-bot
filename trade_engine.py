import threading
import time
import logging
from strategy_one import StrategyOne
from strategy_two import StrategyTwo

logger = logging.getLogger(__name__)

class TradeEngine:
    def __init__(self):
        self.active = False
        self.strategy = None
        self.symbol = None
        self.thread = None

    def start_strategy(self, symbol):
        if self.active:
            logger.warning("Стратегия уже запущена")
            return False
        self.symbol = symbol
        # Для примера выбираем стратегию по символу
        if symbol.startswith("BTC"):
            self.strategy = StrategyOne()
        else:
            self.strategy = StrategyTwo()
        self.active = True
        self.thread = threading.Thread(target=self._run)
        self.thread.start()
        return True

    def _run(self):
        prices = []
        while self.active:
            # Здесь нужно получать актуальные цены с биржи (заглушка)
            new_price = self._get_price()
            prices.append(new_price)
            decision = self.strategy.decide(prices)
            logger.info(f"{self.strategy.name} decision: {decision} на {self.symbol} по цене {new_price}")
            # Вставь здесь логику открытия/закрытия сделок по решению
            time.sleep(15*60)  # пауза 15 минут

    def _get_price(self):
        # Заглушка: вернуть случайную цену или получить с API биржи
        import random
        return random.uniform(30000, 40000)

    def stop_strategy(self):
        self.active = False
        if self.thread:
            self.thread.join()

    def get_status(self):
        if self.active:
            return f"Торговля запущена по паре {self.symbol} с использованием стратегии {self.strategy.name}"
        return "Торговля не запущена"
