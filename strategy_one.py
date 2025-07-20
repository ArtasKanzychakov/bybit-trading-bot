import numpy as np
import pandas as pd

class StrategyOne:
    def __init__(self):
        self.position = None  # 'long', 'short' или None

    def calculate_bollinger_bands(self, close, period=20, std_dev=2):
        sma = close.rolling(window=period).mean()
        std = close.rolling(window=period).std()
        upper = sma + std_dev * std
        lower = sma - std_dev * std
        return sma, upper, lower

    def calculate_atr(self, high, low, close, period=10):
        high_low = high - low
        high_close_prev = (high - close.shift(1)).abs()
        low_close_prev = (low - close.shift(1)).abs()
        tr = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)
        atr = tr.rolling(window=period, min_periods=period).mean()
        return atr

    def calculate_supertrend(self, high, low, close, period=10, multiplier=3):
        atr = self.calculate_atr(high, low, close, period)
        hl2 = (high + low) / 2

        upperband = hl2 + multiplier * atr
        lowerband = hl2 - multiplier * atr

        trend = pd.Series(True, index=close.index)  # True — восходящий, False — нисходящий
        final_upperband = upperband.copy()
        final_lowerband = lowerband.copy()

        for i in range(period, len(close)):
            if close.iloc[i] > final_upperband.iloc[i - 1]:
                trend.iloc[i] = True
            elif close.iloc[i] < final_lowerband.iloc[i - 1]:
                trend.iloc[i] = False
            else:
                trend.iloc[i] = trend.iloc[i - 1]
                if trend.iloc[i] and final_lowerband.iloc[i] < final_lowerband.iloc[i - 1]:
                    final_lowerband.iloc[i] = final_lowerband.iloc[i - 1]
                if not trend.iloc[i] and final_upperband.iloc[i] > final_upperband.iloc[i - 1]:
                    final_upperband.iloc[i] = final_upperband.iloc[i - 1]
        return trend

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
        df — DataFrame с колонками: 'close', 'high', 'low', 'volume'
        Возвращает "buy", "sell" или "hold"
        """
        if len(df) < 30:
            return "hold"

        sma, upper_band, lower_band = self.calculate_bollinger_bands(df['close'])
        supertrend = self.calculate_supertrend(df['high'], df['low'], df['close'])
        rsi = self.calculate_rsi(df['close'])
        avg_volume = df['volume'].rolling(window=20).mean()

        idx = -1  # последний индекс

        price = df['close'].iloc[idx]
        vol_curr = df['volume'].iloc[idx]

        # Проверка None/NaN
        if pd.isna(sma.iloc[idx]) or pd.isna(upper_band.iloc[idx]) or pd.isna(lower_band.iloc[idx]) or pd.isna(rsi.iloc[idx]) or pd.isna(avg_volume.iloc[idx]):
            return "hold"

        touch_lower = price <= lower_band.iloc[idx]
        touch_upper = price >= upper_band.iloc[idx]
        trend_up = supertrend.iloc[idx]
        rsi_val = rsi.iloc[idx]
        vol_high = vol_curr > avg_volume.iloc[idx]

        # Вход в лонг
        if self.position != "long":
            if touch_lower and trend_up and (30 < rsi_val <= 70) and vol_high:
                self.position = "long"
                return "buy"

        # Вход в шорт
        if self.position != "short":
            if touch_upper and not trend_up and (30 <= rsi_val < 70) and vol_high:
                self.position = "short"
                return "sell"

        # Выход из лонга
        if self.position == "long":
            if (not trend_up) or (price >= sma.iloc[idx]):
                self.position = None
                return "sell"

        # Выход из шорта
        if self.position == "short":
            if trend_up or (price <= sma.iloc[idx]):
                self.position = None
                return "buy"

        return "hold"
