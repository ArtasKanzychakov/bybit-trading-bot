from datetime import datetime
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def now_iso() -> str:
    """Возвращает текущее время в ISO формате"""
    return datetime.utcnow().isoformat()

def log_trade_entry(strategy: str, symbol: str, price: float, volume: float):
    """Логирует вход в сделку"""
    message = (
        f"[{now_iso()}] 📈 Вход в сделку | "
        f"Стратегия: {strategy} | "
        f"Пара: {symbol} | "
        f"Цена: {price:.4f} | "
        f"Объем: {volume:.2f}"
    )
    logger.info(message)
    print(message)

def log_trade_exit(trade_id: int, price: float, profit: Optional[float]):
    """Логирует выход из сделки"""
    profit_str = f"{profit:.2f}%" if profit is not None else "N/A"
    message = (
        f"[{now_iso()}] 📉 Выход из сделки | "
        f"ID: {trade_id} | "
        f"Цена: {price:.4f} | "
        f"Прибыль: {profit_str}"
    )
    logger.info(message)
    print(message)

def calculate_percentage_change(entry: float, exit: float) -> float:
    """Вычисляет процент изменения цены"""
    return ((exit - entry) / entry) * 100
