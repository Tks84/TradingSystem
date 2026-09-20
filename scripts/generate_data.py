"""Generate realistic EURUSD H1 sample data for backtesting."""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

np.random.seed(42)

# Generate 60 days of H1 data (1440 bars)
start_time = datetime(2024, 1, 1, 7, 0, 0)  # Start Monday 7 AM UTC
dates = []
opens = []
highs = []
lows = []
closes = []
volumes = []

price = 1.0850  # Starting price for EURUSD

for i in range(1440):
    # Skip weekends (Fridays 22:00 UTC to Sundays 22:00 UTC)
    day_of_week = start_time.weekday()
    hour = start_time.hour
    
    # Weekend check: Friday 22:00 to Sunday 22:00 UTC
    is_weekend = (day_of_week == 4 and hour >= 22) or (day_of_week == 5) or (day_of_week == 6 and hour < 22)
    
    if not is_weekend:
        dates.append(start_time)
        
        # Random price movement with drift
        drift = 0.00001  # Slight upward drift
        volatility = 0.00012  # ~12 pips standard deviation
        
        daily_trend = np.sin(i / 50) * 0.00005  # Oscillating trend
        random_move = np.random.normal(drift + daily_trend, volatility)
        
        # OHLC generation
        open_price = price
        close_price = price + random_move
        
        # High and low around the move
        high_price = max(open_price, close_price) + abs(np.random.normal(0, volatility))
        low_price = min(open_price, close_price) - abs(np.random.normal(0, volatility))
        
        opens.append(round(open_price, 5))
        closes.append(round(close_price, 5))
        highs.append(round(high_price, 5))
        lows.append(round(low_price, 5))
        volumes.append(int(np.random.uniform(1000, 10000)))
        
        price = close_price
    
    start_time += timedelta(hours=1)

# Create DataFrame
df = pd.DataFrame({
    'timestamp': dates,
    'open': opens,
    'high': highs,
    'low': lows,
    'close': closes,
    'volume': volumes
})

print(f"Generated {len(df)} H1 bars from {df['timestamp'].min()} to {df['timestamp'].max()}")

# Save to CSV
df.to_csv('data/EURUSD_H1.csv', index=False)
print(f"Saved to data/EURUSD_H1.csv")
