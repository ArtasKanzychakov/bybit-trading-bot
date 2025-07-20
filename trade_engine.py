import threading
import time
import logging
from strategy_one import StrategyOne
from strategy_two import StrategyTwo

logger = logging.getLogger(__name__)

class TradeEngine:
    def __init__(self):
        self.strategy = None
        self.symbol = None
        self.thread = None
        self.active = False
        self._stop_event = threading.Event()

    def start_strategy(self, symbol, strategy_name="Стратегия 2"):
        if self.active:
            logger.warning("Стратегия уже запущена")
            return False

        self.symbol = symbol
        self._stop_event.clear()

        if strategy_name == "Стратегия 1":
            self.strategy = StrategyOne()
        else:
            self.strategy = StrategyTwo()

        self.strategy.name = strategy_name
        self.active = True

        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.thread.start()
        logger.info(f"Стратегия '{strategy_name}' запущена для пары {symbol}")
        return True

    def _run(self):
        try:
            while not self._stop_event.is_set():
                if self.strategy:
                    logger.debug(f"Выполняется стратегия {self.strategy.name} на {self.symbol}")
                    self.strategy.execute(self.symbol)
                time.sleep(15)
        except Exception as e:
            logger.exception(f"Ошибка в стратегии: {e}")
        finally:
            self.active = False
            logger.info("Стратегия остановлена")

    def stop_strategy(self):
        if self.active:
            self._stop_event.set()
            self.thread.join()
            self.active = False
            logger.info("Торговля остановлена")
        else:
            logger.info("Нет активной стратегии для остановки")

    def get_status(self):
        if self.active and self.strategy and self.symbol:
            return f"Стратегия активна: {self.strategy.name}\nПара: {self.symbol}"
        else:
            return "Стратегия не запущена"
