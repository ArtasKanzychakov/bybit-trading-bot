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

class StrategyOne:
    def __init__(self, api: BybitAPI, risk_per_trade: float = 0.01):
        self.position: Optional[str] = None  # 'long', 'short' или None
        self.api = api
        self.risk_per_trade = risk_per_trade
        self.bb_period = 20
        self.bb_std = 2
        self.rsi_period = 14
        self.atr_period = 10
        self.supertrend_multiplier = 3

    async def fetch_data(self, symbol: str, interval: str = '5m', limit: int = 100) -> pd.DataFrame:
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
        # Bollinger Bands
        df['bb_mid'], df['bb_upper'], df['bb_lower'] = ta.bbands(
            df['close'], length=self.bb_period, std=self.bb_std
        )
        
        # RSI
        df['rsi'] = ta.rsi(df['close'], length=self.rsi_period)
        
        # Supertrend
        st = ta.supertrend(
            df['high'], df['low'], df['close'], 
            length=self.atr_period, 
            multiplier=self.supertrend_multiplier
        )
        df['supertrend'] = st[f'SUPERT_{self.atr_period}_{self.supertrend_multiplier}']
        df['supertrend_direction'] = st[f'SUPERTd_{self.atr_period}_{self.supertrend_multiplier}']
        
        # Volume MA
        df['volume_ma'] = df['volume'].rolling(window=20).mean()
        
        return df

    def calculate_position_size(self, price: float, balance: float) -> float:
        """Рассчитывает объем позиции на основе риска"""
        risk_amount = balance * self.risk_per_trade
        # В реальной стратегии здесь должна быть логика расчета объема
        # на основе стоп-лосса и риска
        return risk_amount / price

    async def analyze(self, symbol: str, balance: float) -> TradeSignal:
        """Анализирует рынок и возвращает торговый сигнал"""
        df = await self.fetch_data(symbol)
        if len(df) < 50:
            return TradeSignal('hold', 0, 0, 'Not enough data')
            
        df = self.calculate_indicators(df)
        last = df.iloc[-1]
        
        price = last['close']
        position_size = self.calculate_position_size(price, balance)
        
        # Условия для входа в лонг
        if self.position != 'long':
            if (last['close'] <= last['bb_lower'] and 
                last['supertrend_direction'] == 1 and
                30 < last['rsi'] <= 70 and
                last['volume'] > last['volume_ma']):
                
                return TradeSignal(
                    'buy', price, position_size,
                    'Bollinger touch + Supertrend UP + RSI OK + Volume spike'
                )
        
        # Условия для входа в шорт
        if self.position != 'short':
            if (last['close'] >= last['bb_upper'] and 
                last['supertrend_direction'] == -1 and
                30 <= last['rsi'] < 70 and
                last['volume'] > last['volume_ma']):
                
                return TradeSignal(
                    'sell', price, position_size,
                    'Bollinger touch + Supertrend DOWN + RSI OK + Volume spike'
                )
        
        # Условия для выхода из позиции
        if self.position == 'long' and last['supertrend_direction'] == -1:
            return TradeSignal(
                'sell', price, position_size,
                'Supertrend reversed to DOWN'
            )
            
        if self.position == 'short' and last['supertrend_direction'] == 1:
            return TradeSignal(
                'buy', price, position_size,
                'Supertrend reversed to UP'
            )
        
        return TradeSignal('hold', 0, 0, 'No trading conditions met')

    async def execute_trade(self, symbol: str, balance: float):
        """Выполняет торговую операцию на основе анализа"""
        signal = await self.analyze(symbol, balance)
        
        if signal.action == 'hold':
            return
            
        if signal.action == 'buy':
            if self.position == 'short':
                # Закрываем шорт перед открытием лонга
                await self.api.close_position(symbol)
                self.position = None
                
            # Открываем лонг
            await self.api.place_order(
                symbol=symbol,
                side='buy',
                quantity=signal.volume,
                price=signal.price
            )
            self.position = 'long'
            trade_id = add_trade(
                strategy='Strategy 1',
                symbol=symbol,
                entry_price=signal.price,
                volume=signal.volume
            )
            log_trade_entry('Strategy 1', symbol, signal.price, signal.volume)
            
        elif signal.action == 'sell':
            if self.position == 'long':
                # Закрываем лонг перед открытием шорта
                await self.api.close_position(symbol)
                self.position = None
                
            # Открываем шорт
            await self.api.place_order(
                symbol=symbol,
                side='sell',
                quantity=signal.volume,
                price=signal.price
            )
            self.position = 'short'
            trade_id = add_trade(
                strategy='Strategy 1',
                symbol=symbol,
                entry_price=signal.price,
                volume=signal.volume
            )
            log_trade_entry('Strategy 1', symbol, signal.price, signal.volume)
