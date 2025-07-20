import numpy as np

class StrategyOne:
    def __init__(self):
        self.position = None  # 'long', 'short' или None

    def calculate_bollinger_bands(self, prices, period=20, std_dev=2):
        """
        Возвращает среднюю, верхнюю и нижнюю полосы Боллинджера.
        """
        if len(prices) < period:
            return None, None, None
        
        sma = np.convolve(prices, np.ones(period)/period, mode='valid')
        std = np.array([np.std(prices[i:i+period]) for i in range(len(prices)-period+1)])
        upper = sma + std_dev * std
        lower = sma - std_dev * std

        # Для удобства возвращаем значения, выровненные с ценами
        # Добавим None вначале, чтобы длина совпадала с prices
        padding = [None]*(period-1)
        return padding + list(sma), padding + list(upper), padding + list(lower)

    def calculate_supertrend(self, high, low, close, period=10, multiplier=3):
        """
        Рассчет Supertrend. Возвращает массив тренда: True — восходящий (зелёный), False — нисходящий (красный).
        """
        atr = self.calculate_atr(high, low, close, period)
        hl2 = (np.array(high) + np.array(low)) / 2

        upperband = hl2 + (multiplier * atr)
        lowerband = hl2 - (multiplier * atr)

        trend = [True] * len(close)  # True — восходящий, False — нисходящий

        for i in range(period, len(close)):
            if close[i] > upperband[i-1]:
                trend[i] = True
            elif close[i] < lowerband[i-1]:
                trend[i] = False
            else:
                trend[i] = trend[i-1]
                # Дополнительно корректируем верхние и нижние границы, чтобы избежать ложных сигналов
                if trend[i] and lowerband[i] < lowerband[i-1]:
                    lowerband[i] = lowerband[i-1]
                if not trend[i] and upperband[i] > upperband[i-1]:
                    upperband[i] = upperband[i-1]
        return trend

    def calculate_atr(self, high, low, close, period=10):
        """
        Рассчет Average True Range.
        """
        tr = []
        for i in range(1, len(close)):
            tr.append(max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1])))
        tr = np.array(tr)
        atr = []
        for i in range(len(tr)):
            if i < period:
                atr.append(np.mean(tr[:i+1]))
            else:
                atr.append((atr[-1] * (period - 1) + tr[i]) / period)
        return [None] + atr  # Для выравнивания длины с входными данными

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

    def decide(self, close, high, low, volume):
        """
        Принимает списки close, high, low, volume.
        Возвращает решение: "buy", "sell" или "hold".
        """
        if len(close) < 30:
            return "hold"

        # Индикаторы
        sma, upper_band, lower_band = self.calculate_bollinger_bands(close)
        supertrend = self.calculate_supertrend(high, low, close)
        rsi = self.calculate_rsi(close)
        avg_volume = np.mean(volume)

        idx = -1  # Последний индекс

        price = close[idx]
        volume_curr = volume[idx]

        # Проверки, если есть None в данных индикаторов - hold
        if None in (sma[idx], upper_band[idx], lower_band[idx], rsi[idx]) or idx >= len(supertrend) or supertrend[idx] is None:
            return "hold"

        # Проверяем условия входа
        # Лонг
        touch_lower = price <= lower_band[idx]
        trend_up = supertrend[idx]  # True — зелёный
        rsi_val = rsi[idx]
        vol_high = volume_curr > avg_volume

        if self.position != "long":
            if touch_lower and trend_up and (30 < rsi_val <= 70) and vol_high:
                self.position = "long"
                return "buy"

        # Шорт
        touch_upper = price >= upper_band[idx]
        trend_down = not supertrend[idx]
        if self.position != "short":
            if touch_upper and trend_down and (30 <= rsi_val < 70) and vol_high:
                self.position = "short"
                return "sell"

        # Условия выхода
        # Для лонга: смена тренда на нисходящий или достижение верхней полосы (exit), фиксация части прибыли при средней линии
        if self.position == "long":
            if not trend_up or price >= sma[idx]:
                self.position = None
                return "sell"

        # Для шорта: смена тренда на восходящий или достижение нижней полосы (exit), фиксация части прибыли при средней линии
        if self.position == "short":
            if trend_up or price <= sma[idx]:
                self.position = None
                return "buy"

        return "hold"
