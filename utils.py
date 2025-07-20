import pandas as pd
import numpy as np
import ta

def bollinger_bands(df, window=20, n_std=2):
    indicator_bb = ta.volatility.BollingerBands(close=df['close'], window=window, window_dev=n_std)
    df['bb_middle'] = indicator_bb.bollinger_mavg()
    df['bb_upper'] = indicator_bb.bollinger_hband()
    df['bb_lower'] = indicator_bb.bollinger_lband()
    return df

def rsi(df, window=14):
    indicator_rsi = ta.momentum.RSIIndicator(close=df['close'], window=window)
    df['rsi'] = indicator_rsi.rsi()
    return df

def atr(df, window=10):
    indicator_atr = ta.volatility.AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=window)
    df['atr'] = indicator_atr.average_true_range()
    return df

def ema(df, span):
    df[f'ema_{span}'] = df['close'].ewm(span=span, adjust=False).mean()
    return df

def supertrend(df, period=10, multiplier=3):
    # Supertrend calculation
    hl2 = (df['high'] + df['low']) / 2
    atr_ = ta.volatility.AverageTrueRange(df['high'], df['low'], df['close'], window=period).average_true_range()
    upperband = hl2 + (multiplier * atr_)
    lowerband = hl2 - (multiplier * atr_)
    supertrend = [True] * len(df)  # True = green/uptrend, False = red/downtrend

    for i in range(1, len(df)):
        if df['close'][i] > upperband[i-1]:
            supertrend[i] = True
        elif df['close'][i] < lowerband[i-1]:
            supertrend[i] = False
        else:
            supertrend[i] = supertrend[i-1]
            if supertrend[i] and lowerband[i] < lowerband[i-1]:
                lowerband[i] = lowerband[i-1]
            if not supertrend[i] and upperband[i] > upperband[i-1]:
                upperband[i] = upperband[i-1]

    df['supertrend'] = supertrend
    df['supertrend_upperband'] = upperband
    df['supertrend_lowerband'] = lowerband
    return df
