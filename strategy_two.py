import pandas as pd
from utils import rsi

def strategy_two(df):
    df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df = rsi(df, window=14)
    df['volume_avg'] = df['volume'].rolling(window=20).mean()

    signals = []
    position = None

    for i in range(1, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i-1]

        # Лонг (золотой крест)
        buy_cond = (
            (prev['ema_20'] < prev['ema_50']) and (row['ema_20'] > row['ema_50']) and
            row['rsi'] > 50 and row['rsi'] <= 70 and
            row['volume'] > row['volume_avg']
        )

        # Шорт (крест смерти)
        sell_cond = (
            (prev['ema_20'] > prev['ema_50']) and (row['ema_20'] < row['ema_50']) and
            row['rsi'] < 50 and row['rsi'] >= 30 and
            row['volume'] > row['volume_avg']
        )

        # Выходы
        exit_long = (
            (prev['ema_20'] > prev['ema_50']) and (row['ema_20'] < row['ema_50'])
            or row['rsi'] > 70
        )
        exit_short = (
            (prev['ema_20'] < prev['ema_50']) and (row['ema_20'] > row['ema_50'])
            or row['rsi'] < 30
        )

        if buy_cond and position != 'long':
            signals.append('buy')
            position = 'long'
        elif sell_cond and position != 'short':
            signals.append('sell')
            position = 'short'
        elif position == 'long' and exit_long:
            signals.append('exit')
            position = None
        elif position == 'short' and exit_short:
            signals.append('exit')
            position = None
        else:
            signals.append('hold')

    signals.insert(0, 'hold')
    df['signal'] = signals
    return df
