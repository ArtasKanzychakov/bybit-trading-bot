import numpy as np
import pandas as pd
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
        self.volume_ma_period = 20

    async def fetch_data(self, symbol: str, interval: str = '5m', limit: int = 100) -> pd.DataFrame:
        """Получает данные с биржи"""
        klines = await self.api.get_klines(symbol=symbol, interval=interval, limit=limit)
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume'
        ])
        return df.astype({
            'open': float, 'high': float, 'low': float, 
            'close': float, 'volume': float
        })

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Вычисляет все индикаторы для стратегии"""
        # Bollinger Bands
        rolling_mean = df['close'].rolling(window=self.bb_period).mean()
        rolling_std = df['close'].rolling(window=self.bb_period).std()
        df['bb_mid'] = rolling_mean
        df['bb_upper'] = rolling_mean + (rolling_std * self.bb_std)
        df['bb_lower'] = rolling_mean - (rolling_std * self.bb_std)
        
        # RSI
        delta = df['close'].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=self.rsi_period).mean()
        avg_loss = loss.rolling(window=self.rsi_period).mean()
        rs = avg_gain / avg_loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Supertrend
        high_low = df['high'] - df['low']
        high_close_prev = (df['high'] - df['close'].shift(1)).abs()
        low_close_prev = (df['low'] - df['close'].shift(1)).abs()
        tr = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)
        atr = tr.rolling(window=self.atr_period).mean()
        hl2 = (df['high'] + df['low']) / 2
        df['supertrend_upper'] = hl2 + (self.supertrend_multiplier * atr)
        df['supertrend_lower'] = hl2 - (self.supertrend_multiplier * atr)
        
        # Определяем направление Supertrend
        df['supertrend_direction'] = 1  # 1 = восходящий, -1 = нисходящий
        for i in range(1, len(df)):
            if df['close'].iloc[i] > df['supertrend_upper'].iloc[i-1]:
                df['supertrend_direction'].iloc[i] = 1
            elif df['close'].iloc[i] < df['supertrend_lower'].iloc[i-1]:
                df['supertrend_direction'].iloc[i] = -1
            else:
                df['supertrend_direction'].iloc[i] = df['supertrend_direction'].iloc[i-1]
        
        # Volume MA
        df['volume_ma'] = df['volume'].rolling(window=self.volume_ma_period).mean()
        
        return df

    def calculate_position_size(self, price: float, balance: float) -> float:
        """Рассчитывает объем позиции на основе риска"""
        risk_amount = balance * self.risk_per_trade
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
                    'Bollinger touch lower + Supertrend UP + RSI >30 + Volume spike'
                )
        
        # Условия для входа в шорт
        if self.position != 'short':
            if (last['close'] >= last['bb_upper'] and 
                last['supertrend_direction'] == -1 and
                30 <= last['rsi'] < 70 and
                last['volume'] > last['volume_ma']):
                
                return TradeSignal(
                    'sell', price, position_size,
                    'Bollinger touch upper + Supertrend DOWN + RSI <70 + Volume spike'
                )
        
        # Условия для выхода из позиции
        if self.position == 'long' and (
            last['supertrend_direction'] == -1 or 
            last['close'] >= last['bb_mid']
        ):
            return TradeSignal(
                'sell', price, position_size,
                'Supertrend reversed or price reached middle BB'
            )
            
        if self.position == 'short' and (
            last['supertrend_direction'] == 1 or 
            last['close'] <= last['bb_mid']
        ):
            return TradeSignal(
                'buy', price, position_size,
                'Supertrend reversed or price reached middle BB'
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
                strategy='Strategy 1 (Bollinger)',
                symbol=symbol,
                entry_price=signal.price,
                volume=signal.volume
            )
            log_trade_entry('Strategy 1', symbol, signal.price, signal.volume)
            
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
                strategy='Strategy 1 (Bollinger)',
                symbol=symbol,
                entry_price=signal.price,
                volume=signal.volume
            )
            log_trade_entry('Strategy 1', symbol, signal.price, signal.volume)
