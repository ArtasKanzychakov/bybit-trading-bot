import os
import threading
import time
import logging
import asyncio
from typing import Optional, Dict, Any
from strategy_one import StrategyOne
from strategy_two import StrategyTwo
from trading import BybitAPI
from db import get_user_settings

logger = logging.getLogger(__name__)

class TradeEngine:
    def __init__(self):
        self.strategy: Optional[str] = None
        self.symbol: Optional[str] = None
        self.risk: float = 0.01
        self.leverage: int = 5
        self.thread: Optional[threading.Thread] = None
        self.active: bool = False
        self._stop_event = threading.Event()
        self.api = None
        self.current_strategy_instance = None
        self.loop = None
        self.last_balance_check = 0
        self.balance_cache = 0.0
        self.cache_timeout = 60  # Кеширование баланса на 60 секунд

    async def _init_api(self):
        if self.api is None:
            self.api = BybitAPI(
                api_key=os.getenv('BYBIT_API_KEY'),
                api_secret=os.getenv('BYBIT_API_SECRET')
            )
            await self.api.initialize()  # Явная инициализация

    async def get_balance(self, force_update: bool = False) -> float:
        """Получение баланса с кешированием и принудительным обновлением"""
        try:
            current_time = time.time()
            
            # Если баланс недавно проверяли и не требуется принудительное обновление
            if not force_update and current_time - self.last_balance_check < self.cache_timeout:
                return self.balance_cache
                
            await self._init_api()
            logger.debug("Запрашиваем актуальный баланс с биржи...")
            
            # Добавляем параметры для избежания кеширования
            balance_data = await self.api.get_balance(params={
                'timestamp': int(current_time * 1000),
                'recvWindow': 5000
            })
            
            if not balance_data:
                logger.error("Пустой ответ от API при запросе баланса")
                return self.balance_cache

            logger.debug(f"Raw balance response: {balance_data}")
            
            if 'list' in balance_data:
                for account in balance_data['list']:
                    if account.get('accountType') == 'UNIFIED':
                        for coin in account.get('coin', []):
                            if coin.get('coin') == 'USDT':
                                available = float(coin.get('availableToWithdraw', 0))
                                self.balance_cache = available
                                self.last_balance_check = current_time
                                logger.info(f"Текущий баланс: {available:.2f} USDT")
                                return available
            
            logger.error(f"Неожиданный формат ответа баланса: {balance_data}")
            return self.balance_cache
            
        except Exception as e:
            logger.error(f"Ошибка получения баланса: {str(e)}", exc_info=True)
            return self.balance_cache

    # ... остальные методы класса без изменений ...

    def start_strategy(self, symbol: str, strategy_name: str = "Стратегия 2", risk: float = 0.01, leverage: int = 5) -> bool:
        if self.active:
            logger.warning("Стратегия уже запущена")
            return False

        try:
            self.symbol = symbol
            self.strategy = strategy_name
            self.risk = risk
            self.leverage = leverage
            self._stop_event.clear()

            if strategy_name == "Стратегия 1":
                self.current_strategy_instance = StrategyOne(self.api, risk, leverage)
            else:
                self.current_strategy_instance = StrategyTwo(self.api, risk, leverage)

            self.active = True
            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()
            logger.info(f"Стратегия '{strategy_name}' запущена для пары {symbol} с риском {risk*100}% и плечом {leverage}x")
            return True
        except Exception as e:
            logger.error(f"Ошибка запуска стратегии: {e}")
            return False

    def _run_loop(self):
        while not self._stop_event.is_set():
            try:
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
                self.loop.run_until_complete(self._init_api())
                self.loop.run_until_complete(self._run())
            except Exception as e:
                logger.critical(f"Критическая ошибка в цикле стратегии: {e}")
                time.sleep(60)

    async def _run(self):
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
                logger.error(f"Ошибка при выполнении сделки: {e}")
                await asyncio.sleep(30)
            
            await asyncio.sleep(15)

    def stop_strategy(self) -> bool:
        if self.active:
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
                logger.error(f"Ошибка остановки стратегии: {e}")
                return False
        logger.info("Нет активной стратегии для остановки")
        return False

    def get_status(self) -> str:
        if self.active and self.strategy and self.symbol:
            return (
                f"📊 <b>Активная стратегия</b>:\n"
                f"🏷 <b>Стратегия</b>: <code>{self.strategy}</code>\n"
                f"📌 <b>Пара</b>: <code>{self.symbol}</code>\n"
                f"⚠ <b>Риск на сделку</b>: <code>{self.risk*100}%</code>\n"
                f"↔ <b>Плечо</b>: <code>{self.leverage}x</code>"
            )
        return "ℹ <b>Стратегия не запущена</b>"
