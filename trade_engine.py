import asyncio
import threading
import logging
import time
from typing import Optional
from trading import BybitAPI
from strategy_one import StrategyOne
from strategy_two import StrategyTwo

logger = logging.getLogger("trade_engine")

STRATEGIES = {
    "Стратегия 1": StrategyOne,
    "Стратегия 2": StrategyTwo
}


class TradeEngine:
    def __init__(self, api_key: str, api_secret: str):
        self.api = BybitAPI(api_key, api_secret)
        self.current_strategy_instance = None
        self.active = False
        self.loop = None
        self.thread = None
        self._stop_event = threading.Event()
        self.symbol = ""
        self.strategy_name = ""
        self.risk = 0.0

    async def _run(self):
        """Основной цикл выполнения стратегии"""
        while not self._stop_event.is_set():
            try:
                if not self.loop or self.loop.is_closed():
                    self.loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(self.loop)

                balance = await self.get_balance()
                if balance > 0:
                    await self.current_strategy_instance.execute_trade(self.symbol, balance)
                else:
                    logger.warning("Нулевой баланс, торговля приостановлена")
            except Exception as e:
                logger.error(f"Ошибка: {e}")
                await asyncio.sleep(30)
            await asyncio.sleep(15)

    def _run_loop(self):
        """Цикл для запуска asyncio внутри отдельного потока"""
        while not self._stop_event.is_set():
            try:
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
                self.loop.run_until_complete(self._run())
            except Exception as e:
                logger.critical(f"Крах event loop: {e}")
                time.sleep(60)

    async def get_balance(self) -> float:
        try:
            balance_info = await self.api.get_balance()
            return float(balance_info.get("totalEquity", 0))
        except Exception as e:
            logger.error(f"Ошибка получения баланса: {e}")
            return 0.0

    def start_strategy(self, symbol: str, strategy_name: str, risk: float) -> bool:
        if self.active:
            logger.warning("Стратегия уже запущена")
            return False

        self.symbol = symbol
        self.strategy_name = strategy_name
        self.risk = risk

        StrategyClass = STRATEGIES.get(strategy_name)
        if not StrategyClass:
            logger.error(f"Неизвестная стратегия: {strategy_name}")
            return False

        self.current_strategy_instance = StrategyClass(self.api, risk)
        self._stop_event.clear()

        self.thread = threading.Thread(target=self._run_loop)
        self.thread.start()
        self.active = True

        logger.info(f"Стратегия '{strategy_name}' запущена для пары {symbol} с риском {risk}%")
        return True

    def stop_strategy(self) -> bool:
        try:
            self._stop_event.set()
            if self.loop and not self.loop.is_closed():
                self.loop.call_soon_threadsafe(self.loop.stop)
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=5)
            self.active = False
            self.current_strategy_instance = None
            logger.info("Торговля остановлена")
            return True
        except Exception as e:
            logger.error(f"Ошибка остановки: {e}")
            return False

    def get_status(self) -> str:
        if not self.active:
            return "Бот не активен"
        return f"Активная стратегия: {self.strategy_name}\nПара: {self.symbol}\nРиск: {self.risk}%"
