import pandas as pd
from utils import bollinger_bands, supertrend, rsi

def strategy_one(df):
    # Добавляем индикаторы
    df = bollinger_bands(df, window=20, n_std=2)
    df = supertrend(df, period=10, multiplier=3)
    df = rsi(df, window=14)
    df['volume_avg'] = df['volume'].rolling(window=20).mean()

    signals = []

    for i in range(1, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i-1]

        # Вход в лонг
        buy_cond = (
            (row['close'] >= row['bb_lower'] and prev['close'] < prev['bb_lower']) and
            row['supertrend'] == True and
            30 < row['rsi'] <= 70 and
            row['volume'] > row['volume_avg']
        )

        # Вход в шорт
        sell_cond = (
            (row['close'] <= row['bb_upper'] and prev['close'] > prev['bb_upper']) and
            row['supertrend'] == False and
            30 <= row['rsi'] < 70 and
            row['volume'] > row['volume_avg']
        )

        # Выход
        exit_cond = False
        if prev['supertrend'] != row['supertrend']:
            exit_cond = True
        elif row['close'] >= row['bb_middle'] or row['close'] <= row['bb_middle']:
            exit_cond = True

        if buy_cond:
            signals.append('buy')
        elif sell_cond:
            signals.append('sell')
        elif exit_cond:
            signals.append('exit')
        else:
            signals.append('hold')

    signals.insert(0, 'hold')  # первый бар нет сигнала
    df['signal'] = signals
    return df
