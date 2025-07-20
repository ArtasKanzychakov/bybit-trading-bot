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
        self.thread: Optional[threading.Thread] = None
        self.active: bool = False
        self._stop_event = threading.Event()
        self.api = None
        self.current_strategy_instance = None
        self.loop = None

    async def _init_api(self):
        """Инициализирует API при первом запуске"""
        if self.api is None:
            self.api = BybitAPI(
                api_key=os.getenv('BYBIT_API_KEY'),
                api_secret=os.getenv('BYBIT_API_SECRET')
            )

    async def get_balance(self) -> float:
        """Получает доступный баланс на бирже"""
        try:
            await self._init_api()
            balance_data = await self.api.get_balance()
            
            # Обрабатываем новый формат ответа Bybit API v5
            if balance_data and 'list' in balance_data:
                for account in balance_data['list']:
                    if account.get('accountType') == 'UNIFIED':
                        for coin in account.get('coin', []):
                            if coin.get('coin') == 'USDT':
                                return float(coin.get('availableToWithdraw', 0))
            
            logger.error(f"Неожиданный формат ответа баланса: {balance_data}")
            return 0.0
        except Exception as e:
            logger.error(f"Ошибка получения баланса: {e}")
            return 0.0

    def start_strategy(self, symbol: str, strategy_name: str = "Стратегия 2", risk: float = 0.01) -> bool:
        if self.active:
            logger.warning("Стратегия уже запущена")
            return False

        try:
            self.symbol = symbol
            self.strategy = strategy_name
            self.risk = risk
            self._stop_event.clear()

            if strategy_name == "Стратегия 1":
                self.current_strategy_instance = StrategyOne(self.api, risk)
            else:
                self.current_strategy_instance = StrategyTwo(self.api, risk)

            self.active = True
            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()
            logger.info(f"Стратегия '{strategy_name}' запущена для пары {symbol} с риском {risk*100}%")
            return True
        except Exception as e:
            logger.error(f"Ошибка запуска стратегии: {e}")
            return False

    def _run_loop(self):
        """Запускает асинхронный цикл в отдельном потоке"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._init_api())
            self.loop.run_until_complete(self._run())
        except Exception as e:
            logger.error(f"Ошибка в цикле стратегии: {e}")
        finally:
            if self.loop:
                self.loop.close()
            self.active = False

    async def _run(self):
        """Основной цикл выполнения стратегии"""
        try:
            while not self._stop_event.is_set():
                if self.current_strategy_instance and self.symbol:
                    try:
                        balance = await self.get_balance()
                        if balance > 0:
                            await self.current_strategy_instance.execute_trade(self.symbol, balance)
                        else:
                            logger.warning("Нулевой баланс, торговля приостановлена")
                    except Exception as e:
                        logger.error(f"Ошибка при выполнении сделки: {e}", exc_info=True)
                        await asyncio.sleep(60)  # Ждем минуту при ошибках API
                
                await asyncio.sleep(15)
        except Exception as e:
            logger.exception(f"Критическая ошибка в стратегии: {e}")
        finally:
            self.active = False
            logger.info("Стратегия остановлена")

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
                f"⚠ <b>Риск на сделку</b>: <code>{self.risk*100}%</code>"
            )
        return "ℹ <b>Стратегия не запущена</b>"
