"""HTF Trend Pullback Trail strategy: daily bias + H1 pullback + trailing stop."""
import pandas as pd
from src.indicators import ema, atr, adx


STRATEGY_NAME = "HTF Trend Pullback Trail"


def get_daily_bias(daily_frame, ema_period=200):
    """Return daily bias: 1 = LONG, -1 = SHORT, 0 = NO BIAS.
    Compares daily close to daily EMA200.
    """
    daily_frame = daily_frame.copy()
    daily_frame['ema'] = ema(daily_frame['close'], ema_period)
    close = daily_frame['close'].iloc[-1]
    ema_val = daily_frame['ema'].iloc[-1]
    
    if pd.isna(ema_val):
        return 0
    if close > ema_val:
        return 1  # LONG bias
    elif close < ema_val:
        return -1  # SHORT bias
    else:
        return 0  # NO BIAS


def check_pullback_entry(h1_frame, side, ema_period=50, lookback=5):
    """Check if last bar is a pullback entry signal.
    side: 1 for LONG, -1 for SHORT.
    h1_frame should have pre-computed 'ema' column.
    Returns (is_entry, pullback_extreme) or (False, None).
    """
    if len(h1_frame) < lookback + 1:
        return False, None
    
    # Use pre-computed EMA if available, otherwise compute
    if 'ema' not in h1_frame.columns:
        h1_frame = h1_frame.copy()
        h1_frame['ema'] = ema(h1_frame['close'], ema_period)
    
    # Get last N bars (lookback window)
    last_bars = h1_frame.iloc[-lookback:]
    ema_val = h1_frame['ema'].iloc[-1]
    last_close = h1_frame['close'].iloc[-1]
    
    if pd.isna(ema_val):
        return False, None
    
    if side == 1:  # LONG entry
        # Low touches EMA, close back at or above EMA, candle is bullish
        min_low = last_bars['low'].min()
        if min_low <= ema_val:
            if last_close >= ema_val and last_bars['close'].iloc[-1] >= last_bars['open'].iloc[-1]:
                return True, min_low
    elif side == -1:  # SHORT entry
        # High touches EMA, close back at or below EMA, candle is bearish
        max_high = last_bars['high'].max()
        if max_high >= ema_val:
            if last_close <= ema_val and last_bars['close'].iloc[-1] <= last_bars['open'].iloc[-1]:
                return True, max_high
    
    return False, None


def get_session_filter_ok(timestamp, utc_start=7, utc_end=16):
    """Check if timestamp is within FX session filter window (UTC)."""
    hour = pd.Timestamp(timestamp).hour
    return utc_start <= hour < utc_end
