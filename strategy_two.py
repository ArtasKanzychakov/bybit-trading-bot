import numpy as np
import pandas as pd

class StrategyTwo:
    def __init__(self):
        self.position = None  # 'long', 'short' или None

    def calculate_ema(self, series, period):
        return series.ewm(span=period, adjust=False).mean()

    def calculate_rsi(self, close, period=14):
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def decide(self, df):
        """
        df — DataFrame с колонками: 'close', 'volume'
        Возвращает "buy", "sell" или "hold"
        """
        if len(df) < 60:
            return "hold"

        ema20 = self.calculate_ema(df['close'], 20)
        ema50 = self.calculate_ema(df['close'], 50)
        rsi = self.calculate_rsi(df['close'], 14)
        avg_volume = df['volume'].rolling(window=20).mean()

        ema20_curr = ema20.iloc[-1]
        ema20_prev = ema20.iloc[-2]

        ema50_curr = ema50.iloc[-1]
        ema50_prev = ema50.iloc[-2]

        rsi_curr = rsi.iloc[-1]
        volume_curr = df['volume'].iloc[-1]

        golden_cross = (ema20_prev <= ema50_prev) and (ema20_curr > ema50_curr)
        death_cross = (ema20_prev >= ema50_prev) and (ema20_curr < ema50_curr)

        # Вход в лонг
        if self.position != "long":
            if golden_cross and (rsi_curr > 50) and (rsi_curr <= 70) and (volume_curr > avg_volume.iloc[-1]):
                self.position = "long"
                return "buy"

        # Вход в шорт
        if self.position != "short":
            if death_cross and (rsi_curr < 50) and (rsi_curr >= 30) and (volume_curr > avg_volume.iloc[-1]):
                self.position = "short"
                return "sell"

        # Выход из лонга
        if self.position == "long":
            if death_cross or (rsi_curr > 70):
                self.position = None
                return "sell"

        # Выход из шорта
        if self.position == "short":
            if golden_cross or (rsi_curr < 30):
                self.position = None
                return "buy"

        return "hold"
