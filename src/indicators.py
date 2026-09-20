"""Technical indicators: EMA, ATR, ADX (Wilder). No lookahead."""
import pandas as pd
import numpy as np


def ema(series, period):
    """Exponential Moving Average. Alpha = 2 / (period + 1)."""
    alpha = 2.0 / (period + 1)
    result = [series.iloc[0]]
    for i in range(1, len(series)):
        result.append(series.iloc[i] * alpha + result[-1] * (1 - alpha))
    return pd.Series(result, index=series.index)


def tr(frame):
    """True Range: max(high - low, abs(high - close[prev]), abs(low - close[prev]))."""
    high = frame['high']
    low = frame['low']
    close = frame['close']
    prev_close = close.shift(1)
    
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    return pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)


def atr(frame, period=14):
    """Average True Range (Wilder smoothing).
    First ATR is SMA, then EMA with alpha = 1/period.
    """
    tr_vals = tr(frame)
    atr_result = pd.Series(np.nan, index=frame.index)
    
    # Check if we have enough bars
    if len(frame) < period:
        return atr_result
    
    # First ATR is SMA
    atr_result.iloc[period - 1] = tr_vals.iloc[:period].mean()
    
    # Subsequent: Wilder smoothing (1/period, not 2/(period+1))
    alpha = 1.0 / period
    for i in range(period, len(frame)):
        atr_result.iloc[i] = atr_result.iloc[i - 1] * (1 - alpha) + tr_vals.iloc[i] * alpha
    
    return atr_result


def adx(frame, period=14):
    """Average Directional Index (Wilder method).
    Returns ADX value (0-100).
    """
    if len(frame) < period * 2:
        return pd.Series(np.nan, index=frame.index)
    
    high = frame['high']
    low = frame['low']
    close = frame['close']
    
    # Directional movements
    up_move = high.diff()
    down_move = -low.diff()
    
    # Determine +DM and -DM
    plus_dm = pd.Series(0.0, index=frame.index)
    minus_dm = pd.Series(0.0, index=frame.index)
    
    for i in range(1, len(frame)):
        if up_move.iloc[i] > down_move.iloc[i] and up_move.iloc[i] > 0:
            plus_dm.iloc[i] = up_move.iloc[i]
        if down_move.iloc[i] > up_move.iloc[i] and down_move.iloc[i] > 0:
            minus_dm.iloc[i] = down_move.iloc[i]
    
    # True range
    tr_vals = tr(frame)
    
    # Smooth using Wilder method (over 'period' bars)
    plus_dm_smooth = pd.Series(np.nan, index=frame.index)
    minus_dm_smooth = pd.Series(np.nan, index=frame.index)
    tr_smooth = pd.Series(np.nan, index=frame.index)
    
    # Initial smoothed values at index period-1
    plus_dm_smooth.iloc[period - 1] = plus_dm.iloc[:period].sum()
    minus_dm_smooth.iloc[period - 1] = minus_dm.iloc[:period].sum()
    tr_smooth.iloc[period - 1] = tr_vals.iloc[:period].sum()
    
    # Subsequent smoothing
    for i in range(period, len(frame)):
        plus_dm_smooth.iloc[i] = plus_dm_smooth.iloc[i - 1] - plus_dm_smooth.iloc[i - 1] / period + plus_dm.iloc[i]
        minus_dm_smooth.iloc[i] = minus_dm_smooth.iloc[i - 1] - minus_dm_smooth.iloc[i - 1] / period + minus_dm.iloc[i]
        tr_smooth.iloc[i] = tr_smooth.iloc[i - 1] - tr_smooth.iloc[i - 1] / period + tr_vals.iloc[i]
    
    # Plus and Minus Directional Indicators
    plus_di = pd.Series(np.nan, index=frame.index)
    minus_di = pd.Series(np.nan, index=frame.index)
    
    for i in range(period - 1, len(frame)):
        if tr_smooth.iloc[i] != 0:
            plus_di.iloc[i] = 100 * plus_dm_smooth.iloc[i] / tr_smooth.iloc[i]
            minus_di.iloc[i] = 100 * minus_dm_smooth.iloc[i] / tr_smooth.iloc[i]
        else:
            plus_di.iloc[i] = 0
            minus_di.iloc[i] = 0
    
    # Directional Index (DX)
    di_sum = plus_di + minus_di
    dx = pd.Series(np.nan, index=frame.index)
    for i in range(period - 1, len(frame)):
        if di_sum.iloc[i] != 0:
            dx.iloc[i] = 100 * abs(plus_di.iloc[i] - minus_di.iloc[i]) / di_sum.iloc[i]
        else:
            dx.iloc[i] = 0
    
    # ADX: smooth DX over 'period'
    adx_result = pd.Series(np.nan, index=frame.index)
    if 2 * period - 2 < len(frame):
        adx_result.iloc[2 * period - 2] = dx.iloc[period - 1:2 * period - 1].mean()
        
        for i in range(2 * period - 1, len(frame)):
            adx_result.iloc[i] = (adx_result.iloc[i - 1] * (period - 1) + dx.iloc[i]) / period
    
    return adx_result
