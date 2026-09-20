"""Debug script to check indicator values."""
import pandas as pd
from src.indicators import ema, atr, adx
from src.strategy import get_daily_bias, check_pullback_entry
from src.backtest import load_h1_data, resample_to_daily

h1_frame = load_h1_data('data/EURUSD_H1.csv')
daily_frame = resample_to_daily(h1_frame)

# Compute indicators
h1_frame['ema_fast'] = ema(h1_frame['close'], 50)
h1_frame['atr'] = atr(h1_frame, 14)
h1_frame['adx'] = adx(h1_frame, 14)
daily_frame['ema_daily'] = ema(daily_frame['close'], 200)

print("H1 Data Sample (first 70 bars):")
print(h1_frame[['timestamp', 'close', 'ema_fast', 'atr', 'adx']].head(70).to_string())

print("\n\nDaily Data:")
print(daily_frame[['date', 'close', 'ema_daily']].to_string())

print("\n\nChecking for valid ADX:")
valid_adx = h1_frame[~h1_frame['adx'].isna()]
print(f"First bar with valid ADX: index {valid_adx.index[0] if len(valid_adx) > 0 else 'None'}")
print(f"Total bars with valid ADX: {len(valid_adx)}")

if len(valid_adx) > 0:
    print(f"ADX values range: {valid_adx['adx'].min():.2f} to {valid_adx['adx'].max():.2f}")
    print(f"Bars with ADX >= 18: {len(valid_adx[valid_adx['adx'] >= 18])}")

print("\n\nDaily bias:")
for idx, row in daily_frame.iterrows():
    if pd.notna(row['ema_daily']):
        bias = "LONG" if row['close'] > row['ema_daily'] else "SHORT"
        print(f"{row['date']}: Close={row['close']:.5f}, EMA200={row['ema_daily']:.5f} -> {bias}")

print("\n\nChecking pullback detection on bars 50-70:")
for i in range(50, min(70, len(h1_frame))):
    h1_subset = h1_frame.iloc[max(0, i - 5):i + 1]
    is_entry_long, low_long = check_pullback_entry(h1_subset, 1, 50)
    is_entry_short, high_short = check_pullback_entry(h1_subset, -1, 50)
    
    if is_entry_long or is_entry_short:
        print(f"Bar {i}: LONG={is_entry_long} SHORT={is_entry_short}")
