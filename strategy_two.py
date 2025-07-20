import numpy as np
import pandas as pd
import pandas_ta as ta
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
from trading import BybitAPI
from db import add_trade, close_trade
from utils import log_trade_entry, log_trade_exit

@dataclass
class TradeSignal:
    action: str  # 'buy', 'sell', 'hold'
    price: float
    volume: float
    reason: str

class StrategyTwo:
    def __init__(self, api: BybitAPI, risk_per_trade: float = 0.01):
        self.position: Optional[str] = None  # 'long', 'short' или None
        self.api = api
        self.risk_per_trade = risk_per_trade
        self.ema_fast = 20
        self.ema_slow = 50
        self.rsi_period = 14

    async def fetch_data(self, symbol: str, interval: str = '15m', limit: int = 100) -> pd.DataFrame:
        """Получает данные с биржи"""
        klines = await self.api.get_klines(symbol=symbol, interval=interval, limit=limit)
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume'
        ])
        df = df.astype({
            'open': float, 'high': float, 'low': float, 
            'close': float, 'volume': float
        })
        return df

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Вычисляет все индикаторы для стратегии"""
        # EMA
        df['ema_fast'] = ta.ema(df['close'], length=self.ema_fast)
        df['ema_slow'] = ta.ema(df['close'], length=self.ema_slow)
        
        # RSI
        df['rsi'] = ta.rsi(df['close'], length=self.rsi_period)
        
        # Volume MA
        df['volume_ma'] = df['volume'].rolling(window=20).mean()
        
        return df

    def calculate_position_size(self, price: float, balance: float) -> float:
        """Рассчитывает объем позиции на основе риска"""
        risk_amount = balance * self.risk_per_trade
        return risk_amount / price

    async def analyze(self, symbol: str, balance: float) -> TradeSignal:
        """Анализирует рынок и возвращает торговый сигнал"""
        df = await self.fetch_data(symbol)
        if len(df) < 60:
            return TradeSignal('hold', 0, 0, 'Not enough data')
            
        df = self.calculate_indicators(df)
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        price = last['close']
        position_size = self.calculate_position_size(price, balance)
        
        # Определяем пересечения EMA
        golden_cross = (prev['ema_fast'] <= prev['ema_slow']) and (last['ema_fast'] > last['ema_slow'])
        death_cross = (prev['ema_fast'] >= prev['ema_slow']) and (last['ema_fast'] < last['ema_slow'])
        
        # Условия для входа в лонг
        if self.position != 'long' and golden_cross:
            if last['rsi'] > 50 and last['rsi'] <= 70 and last['volume'] > last['volume_ma']:
                return TradeSignal(
                    'buy', price, position_size,
                    'Golden Cross + RSI > 50 + Volume spike'
                )
        
        # Условия для входа в шорт
        if self.position != 'short' and death_cross:
            if last['rsi'] < 50 and last['rsi'] >= 30 and last['volume'] > last['volume_ma']:
                return TradeSignal(
                    'sell', price, position_size,
                    'Death Cross + RSI < 50 + Volume spike'
                )
        
        # Условия для выхода из позиции
        if self.position == 'long' and (death_cross or last['rsi'] > 70):
            return TradeSignal(
                'sell', price, position_size,
                'Death Cross or RSI > 70'
            )
            
        if self.position == 'short' and (golden_cross or last['rsi'] < 30):
            return TradeSignal(
                'buy', price, position_size,
                'Golden Cross or RSI < 30'
            )
        
        return TradeSignal('hold', 0, 0, 'No trading conditions met')

    async def execute_trade(self, symbol: str, balance: float):
        """Выполняет торговую операцию на основе анализа"""
        signal = await self.analyze(symbol, balance)
        
        if signal.action == 'hold':
            return
            
        if signal.action == 'buy':
            if self.position == 'short':
                await self.api.close_position(symbol)
                self.position = None
                
            await self.api.place_order(
                symbol=symbol,
                side='buy',
                quantity=signal.volume,
                price=signal.price
            )
            self.position = 'long'
            trade_id = add_trade(
                strategy='Strategy 2',
                symbol=symbol,
                entry_price=signal.price,
                volume=signal.volume
            )
            log_trade_entry('Strategy 2', symbol, signal.price, signal.volume)
            
        elif signal.action == 'sell':
            if self.position == 'long':
                await self.api.close_position(symbol)
                self.position = None
                
            await self.api.place_order(
                symbol=symbol,
                side='sell',
                quantity=signal.volume,
                price=signal.price
            )
            self.position = 'short'
            trade_id = add_trade(
                strategy='Strategy 2',
                symbol=symbol,
                entry_price=signal.price,
                volume=signal.volume
            )
            log_trade_entry('Strategy 2', symbol, signal.price, signal.volume)
