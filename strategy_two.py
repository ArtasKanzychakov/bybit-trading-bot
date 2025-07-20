import numpy as np

class StrategyTwo:
    def __init__(self):
        self.position = None  # 'long', 'short' или None

    def calculate_ema(self, prices, period):
        ema = []
        k = 2 / (period + 1)
        for i, price in enumerate(prices):
            if i == 0:
                ema.append(price)
            else:
                ema.append(price * k + ema[-1] * (1 - k))
        return ema

    def calculate_rsi(self, prices, period=14):
        deltas = np.diff(prices)
        seed = deltas[:period]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        rs = up / down if down != 0 else 0
        rsi = [100 - 100 / (1 + rs)]

        for i in range(period, len(prices) - 1):
            delta = deltas[i]
            if delta > 0:
                upval = delta
                downval = 0
            else:
                upval = 0
                downval = -delta

            up = (up * (period - 1) + upval) / period
            down = (down * (period - 1) + downval) / period

            rs = up / down if down != 0 else 0
            rsi.append(100 - 100 / (1 + rs))

        return [None]*period + rsi

    def decide(self, prices, volumes):
        """
        prices — список цен закрытия (float)
        volumes — список объёмов (float)
        Возвращает решение: "buy", "sell", "hold"
        """
        if len(prices) < 60 or len(volumes) < 60:
            return "hold"

        ema20 = self.calculate_ema(prices, 20)
        ema50 = self.calculate_ema(prices, 50)
        rsi = self.calculate_rsi(prices, 14)
        avg_volume = np.mean(volumes)

        ema20_curr = ema20[-1]
        ema20_prev = ema20[-2]

        ema50_curr = ema50[-1]
        ema50_prev = ema50[-2]

        rsi_curr = rsi[-1]
        volume_curr = volumes[-1]

        golden_cross = (ema20_prev <= ema50_prev) and (ema20_curr > ema50_curr)
        death_cross = (ema20_prev >= ema50_prev) and (ema20_curr < ema50_curr)

        # Лонг
        if self.position != "long":
            if golden_cross and 50 < rsi_curr < 70 and volume_curr > avg_volume:
                self.position = "long"
                return "buy"

        # Шорт
        if self.position != "short":
            if death_cross and 30 < rsi_curr < 50 and volume_curr > avg_volume:
                self.position = "short"
                return "sell"

        # Выход из лонга
        if self.position == "long":
            if death_cross or rsi_curr > 70:
                self.position = None
                return "sell"

        # Выход из шорта
        if self.position == "short":
            if golden_cross or rsi_curr < 30:
                self.position = None
                return "buy"

        return "hold"
