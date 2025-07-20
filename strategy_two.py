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

class StrategyTwo:
    def __init__(self, api: BybitAPI, risk_per_trade: float = 0.01):
        self.position: Optional[str] = None
        self.api = api
        self.risk_per_trade = risk_per_trade
        self.ema_fast = 20
        self.ema_slow = 50
        self.rsi_period = 14
        self.volume_ma_period = 20
        self.current_trade_id: Optional[int] = None

    async def fetch_data(self, symbol: str, interval: str = '15m', limit: int = 100) -> pd.DataFrame:
        klines = await self.api.get_klines(symbol=symbol, interval=interval, limit=limit)
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume'
        ])
        return df.astype({
            'open': float, 'high': float, 'low': float, 
            'close': float, 'volume': float
        })

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        # EMA
        df['ema_fast'] = df['close'].ewm(span=self.ema_fast, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=self.ema_slow, adjust=False).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=self.rsi_period).mean()
        avg_loss = loss.rolling(window=self.rsi_period).mean()
        rs = avg_gain / avg_loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Volume MA
        df['volume_ma'] = df['volume'].rolling(window=self.volume_ma_period).mean()
        
        return df

    def calculate_position_size(self, price: float, balance: float) -> float:
        risk_amount = balance * self.risk_per_trade
        return risk_amount / price

    async def analyze(self, symbol: str, balance: float) -> TradeSignal:
        df = await self.fetch_data(symbol)
        if len(df) < 60:
            return TradeSignal('hold', 0, 0, 'Not enough data')
            
        df = self.calculate_indicators(df)
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        price = last['close']
        position_size = self.calculate_position_size(price, balance)
        
        # Crosses
        golden_cross = (prev['ema_fast'] <= prev['ema_slow']) and (last['ema_fast'] > last['ema_slow'])
        death_cross = (prev['ema_fast'] >= prev['ema_slow']) and (last['ema_fast'] < last['ema_slow'])
        
        # Long entry
        if self.position != 'long' and golden_cross:
            if last['rsi'] > 50 and last['rsi'] <= 70 and last['volume'] > last['volume_ma']:
                return TradeSignal(
                    'buy', price, position_size,
                    'Golden Cross + RSI >50 + Volume spike'
                )
        
        # Short entry
        if self.position != 'short' and death_cross:
            if last['rsi'] < 50 and last['rsi'] >= 30 and last['volume'] > last['volume_ma']:
                return TradeSignal(
                    'sell', price, position_size,
                    'Death Cross + RSI <50 + Volume spike'
                )
        
        # Exit conditions
        if self.position == 'long' and (death_cross or last['rsi'] > 70):
            return TradeSignal(
                'sell', price, position_size,
                'Death Cross or RSI >70'
            )
            
        if self.position == 'short' and (golden_cross or last['rsi'] < 30):
            return TradeSignal(
                'buy', price, position_size,
                'Golden Cross or RSI <30'
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
                strategy='Strategy 2 (EMA Cross)',
                symbol=symbol,
                entry_price=signal.price,
                volume=signal.volume
            )
            log_trade_entry('Strategy 2', symbol, signal.price, signal.volume)
            
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
                strategy='Strategy 2 (EMA Cross)',
                symbol=symbol,
                entry_price=signal.price,
                volume=signal.volume
            )
            log_trade_entry('Strategy 2', symbol, signal.price, signal.volume)
