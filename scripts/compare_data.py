"""Quick comparison of old vs new data."""
import pandas as pd
from src.backtest import load_h1_data

old_data = load_h1_data('data/EURUSD_H1.csv')
new_data = load_h1_data('data/EURUSD_H1_2024.csv')

print('OLD DATA (60 days):')
print(f'  Candles: {len(old_data)}')
print(f'  Date range: {old_data.iloc[0]["timestamp"]} to {old_data.iloc[-1]["timestamp"]}')
print(f'  Price: {old_data["open"].min():.5f} to {old_data["open"].max():.5f}')

print('\nNEW DATA (full 2024):')
print(f'  Candles: {len(new_data)}')
print(f'  Date range: {new_data.iloc[0]["timestamp"]} to {new_data.iloc[-1]["timestamp"]}')
print(f'  Price: {new_data["open"].min():.5f} to {new_data["open"].max():.5f}')
print(f'\n✓ {len(new_data) / len(old_data):.1f}x more data! (9148 vs 1056 candles)')
print(f'✓ 70/30 split will generate: ~{int(len(new_data)*0.3/2)} OOS trades (if pattern holds)')
