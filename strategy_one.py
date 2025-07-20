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
        self.position: Optional[str] = None
        self.api = api
        self.risk_per_trade = risk_per_trade
        self.bb_period = 20
        self.bb_std = 2
        self.rsi_period = 14
        self.atr_period = 10
        self.supertrend_multiplier = 3
        self.volume_ma_period = 20
        self.current_trade_id: Optional[int] = None

    async def fetch_data(self, symbol: str, interval: str = '5m', limit: int = 100) -> pd.DataFrame:
        klines = await self.api.get_klines(symbol=symbol, interval=interval, limit=limit)
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume'
        ])
        return df.astype({
            'open': float, 'high': float, 'low': float, 
            'close': float, 'volume': float
        })

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
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
        
        # Supertrend direction
        df['supertrend_direction'] = 1
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
        risk_amount = balance * self.risk_per_trade
        return risk_amount / price

    async def analyze(self, symbol: str, balance: float) -> TradeSignal:
        df = await self.fetch_data(symbol)
        if len(df) < 50:
            return TradeSignal('hold', 0, 0, 'Not enough data')
            
        df = self.calculate_indicators(df)
        last = df.iloc[-1]
        
        price = last['close']
        position_size = self.calculate_position_size(price, balance)
        
        # Long entry
        if self.position != 'long':
            if (last['close'] <= last['bb_lower'] and 
                last['supertrend_direction'] == 1 and
                30 < last['rsi'] <= 70 and
                last['volume'] > last['volume_ma']):
                
                return TradeSignal(
                    'buy', price, position_size,
                    'Bollinger touch lower + Supertrend UP + RSI >30 + Volume spike'
                )
        
        # Short entry
        if self.position != 'short':
            if (last['close'] >= last['bb_upper'] and 
                last['supertrend_direction'] == -1 and
                30 <= last['rsi'] < 70 and
                last['volume'] > last['volume_ma']):
                
                return TradeSignal(
                    'sell', price, position_size,
                    'Bollinger touch upper + Supertrend DOWN + RSI <70 + Volume spike'
                )
        
        # Exit conditions
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
        signal = await self.analyze(symbol, balance)
        
        if signal.action == 'hold':
            return
            
        if signal.action == 'buy':
            tp_price = signal.price * 1.02  # TP +2%
            sl_price = signal.price * 0.99  # SL -1%
            
            if self.position == 'short' and self.current_trade_id:
                await self.api.close_position(symbol, 'Buy', signal.volume)
                close_trade(self.current_trade_id, signal.price, None)
                log_trade_exit(self.current_trade_id, signal.price, None)
                self.position = None
                self.current_trade_id = None
                
            await self.api.place_order(
                symbol=symbol,
                side='buy',
                quantity=signal.volume,
                price=signal.price,
                take_profit=tp_price,
                stop_loss=sl_price
            )
            self.position = 'long'
            self.current_trade_id = add_trade(
                strategy='Strategy 1 (Bollinger)',
                symbol=symbol,
                entry_price=signal.price,
                volume=signal.volume
            )
            log_trade_entry('Strategy 1', symbol, signal.price, signal.volume)
            
        elif signal.action == 'sell':
            tp_price = signal.price * 0.98  # TP -2% (для шорта)
            sl_price = signal.price * 1.01  # SL +1% (для шорта)
            
            if self.position == 'long' and self.current_trade_id:
                await self.api.close_position(symbol, 'Sell', signal.volume)
                close_trade(self.current_trade_id, signal.price, None)
                log_trade_exit(self.current_trade_id, signal.price, None)
                self.position = None
                self.current_trade_id = None
                
            await self.api.place_order(
                symbol=symbol,
                side='sell',
                quantity=signal.volume,
                price=signal.price,
                take_profit=tp_price,
                stop_loss=sl_price
            )
            self.position = 'short'
            self.current_trade_id = add_trade(
                strategy='Strategy 1 (Bollinger)',
                symbol=symbol,
                entry_price=signal.price,
                volume=signal.volume
            )
            log_trade_entry('Strategy 1', symbol, signal.price, signal.volume)
