"""Backtest engine: HTF Trend Pullback Trail on H1 data with daily bias."""
import pandas as pd
import numpy as np
import json
from pathlib import Path
from src.indicators import ema, atr, adx
from src.strategy import get_daily_bias, check_pullback_entry, get_session_filter_ok


class BacktestConfig:
    """Backtest configuration and defaults."""
    
    def __init__(self):
        self.commission_pips = 0.2      # Bid-ask spread
        self.slippage_pips = 0.3        # Entry/exit slippage
        self.risk_pct = 0.01            # 1% per trade
        self.ema_fast = 50              # H1 EMA50 for pullback
        self.ema_daily = 200            # Daily EMA200 for bias
        self.adx_min = 18               # ADX threshold
        self.sl_atr_mult = 1.5          # Stop loss = 1.5 * ATR
        self.trail_atr_mult = 3.0       # Trailing stop = 3.0 * ATR
        self.max_bars_in_trade = 80     # Exit after 80 bars
        self.session_filter = False     # No session filter by default


class Trade:
    """Single trade record."""
    
    def __init__(self, entry_idx, entry_time, entry_price, side, stop_loss, risk_amount):
        self.entry_idx = entry_idx
        self.entry_time = entry_time
        self.entry_price = entry_price
        self.side = side  # 1 for LONG, -1 for SHORT
        self.stop_loss = stop_loss
        self.risk_amount = risk_amount
        self.position_size = risk_amount / abs(entry_price - stop_loss) if entry_price != stop_loss else 0
        self.exit_idx = None
        self.exit_time = None
        self.exit_price = None
        self.exit_reason = None
        self.pnl = 0
        self.pnl_pct = 0


def load_h1_data(csv_path):
    """Load H1 OHLC from CSV: timestamp, open, high, low, close, volume."""
    df = pd.read_csv(csv_path, parse_dates=['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)
    df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    return df


def resample_to_daily(h1_frame):
    """Resample H1 data to daily OHLC."""
    h1_frame = h1_frame.copy()
    h1_frame['date'] = h1_frame['timestamp'].dt.date
    daily = h1_frame.groupby('date').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).reset_index()
    daily.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
    return daily


def run_backtest(h1_frame, config=None, daily_frame=None):
    """Run backtest on H1 data.
    Returns (trades_list, metrics_dict).
    """
    if config is None:
        config = BacktestConfig()
    
    h1_frame = h1_frame.copy().reset_index(drop=True)
    if daily_frame is None:
        daily_frame = resample_to_daily(h1_frame)
    
    # Precompute indicators
    h1_frame['ema_fast'] = ema(h1_frame['close'], config.ema_fast)
    h1_frame['atr'] = atr(h1_frame, 14)
    h1_frame['adx'] = adx(h1_frame, 14)
    
    daily_frame['ema_daily'] = ema(daily_frame['close'], config.ema_daily)
    
    trades = []
    equity = 10000
    current_trade = None
    max_equity = equity
    max_drawdown = 0
    
    for bar_idx in range(1, len(h1_frame)):
        current_bar = h1_frame.iloc[bar_idx]
        current_time = current_bar['timestamp']
        current_price = current_bar['close']
        
        # Update daily bias
        current_date = pd.Timestamp(current_time).date()
        daily_rows = daily_frame[daily_frame['date'] == current_date]
        if len(daily_rows) > 0:
            daily_bias = 1 if daily_rows['close'].iloc[-1] > daily_rows['ema_daily'].iloc[-1] else -1
        else:
            daily_bias = 0
        
        # Exit current trade if any
        if current_trade is not None:
            bars_in_trade = bar_idx - current_trade.entry_idx
            trail_stop = current_trade.entry_price + current_trade.side * config.trail_atr_mult * current_bar['atr']
            
            exit_signal = False
            exit_reason = None
            exit_price = current_price
            
            if current_trade.side == 1 and current_price <= current_trade.stop_loss:
                exit_signal = True
                exit_reason = "SL"
                exit_price = current_trade.stop_loss - config.slippage_pips / 10000
            elif current_trade.side == -1 and current_price >= current_trade.stop_loss:
                exit_signal = True
                exit_reason = "SL"
                exit_price = current_trade.stop_loss + config.slippage_pips / 10000
            elif current_trade.side == 1 and current_price <= trail_stop:
                exit_signal = True
                exit_reason = "Trail"
                exit_price = trail_stop - config.slippage_pips / 10000
            elif current_trade.side == -1 and current_price >= trail_stop:
                exit_signal = True
                exit_reason = "Trail"
                exit_price = trail_stop + config.slippage_pips / 10000
            elif current_trade.side == 1 and current_price < current_bar['ema_fast']:
                exit_signal = True
                exit_reason = "EMA"
                exit_price = current_price - config.slippage_pips / 10000
            elif current_trade.side == -1 and current_price > current_bar['ema_fast']:
                exit_signal = True
                exit_reason = "EMA"
                exit_price = current_price + config.slippage_pips / 10000
            elif bars_in_trade >= config.max_bars_in_trade:
                exit_signal = True
                exit_reason = "MaxBars"
                exit_price = current_price
            
            if exit_signal:
                pnl_pips = (exit_price - current_trade.entry_price) * current_trade.side * 10000
                pnl_pips -= config.commission_pips
                pnl = pnl_pips * current_trade.position_size / 10000
                
                current_trade.exit_idx = bar_idx
                current_trade.exit_time = current_time
                current_trade.exit_price = exit_price
                current_trade.exit_reason = exit_reason
                current_trade.pnl = pnl
                current_trade.pnl_pct = (pnl / current_trade.risk_amount * 100) if current_trade.risk_amount > 0 else 0
                
                trades.append(current_trade)
                equity += pnl
                current_trade = None
        
        # Check for entry
        if current_trade is None:
            if pd.isna(current_bar['adx']) or current_bar['adx'] < config.adx_min:
                continue
            
            if config.session_filter and not get_session_filter_ok(current_time):
                continue
            
            if daily_bias == 1:
                # Check for LONG pullback entry on lookback window
                lookback_start = max(0, bar_idx - 5)
                h1_lookback = h1_frame.iloc[lookback_start:bar_idx + 1].copy()
                h1_lookback['ema'] = h1_frame['ema_fast'].iloc[lookback_start:bar_idx + 1].values
                is_entry, pullback_low = check_pullback_entry(h1_lookback, 1, config.ema_fast)
                if is_entry and pullback_low is not None:
                    stop_loss = pullback_low - config.sl_atr_mult * current_bar['atr']
                    risk_amount = equity * config.risk_pct
                    current_trade = Trade(bar_idx, current_time, current_price + config.slippage_pips / 10000, 1, stop_loss, risk_amount)
            
            elif daily_bias == -1:
                # Check for SHORT pullback entry on lookback window
                lookback_start = max(0, bar_idx - 5)
                h1_lookback = h1_frame.iloc[lookback_start:bar_idx + 1].copy()
                h1_lookback['ema'] = h1_frame['ema_fast'].iloc[lookback_start:bar_idx + 1].values
                is_entry, pullback_high = check_pullback_entry(h1_lookback, -1, config.ema_fast)
                if is_entry and pullback_high is not None:
                    stop_loss = pullback_high + config.sl_atr_mult * current_bar['atr']
                    risk_amount = equity * config.risk_pct
                    current_trade = Trade(bar_idx, current_time, current_price - config.slippage_pips / 10000, -1, stop_loss, risk_amount)
        
        # Update max drawdown
        if equity > max_equity:
            max_equity = equity
        drawdown = (max_equity - equity) / max_equity if max_equity > 0 else 0
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    
    # Calculate metrics
    total_return = equity - 10000
    total_return_pct = (total_return / 10000) * 100
    winning_trades = sum(1 for t in trades if t.pnl > 0)
    losing_trades = sum(1 for t in trades if t.pnl < 0)
    total_trades = len(trades)
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
    gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (1.0 if gross_profit > 0 else 0)
    
    avg_trade = (total_return / total_trades) if total_trades > 0 else 0
    
    metrics = {
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'total_return': total_return,
        'total_return_pct': total_return_pct,
        'max_drawdown_pct': max_drawdown * 100,
        'avg_trade': avg_trade,
        'final_equity': equity,
    }
    
    return trades, metrics


def trades_to_csv(trades, output_path):
    """Write trades to CSV."""
    records = []
    for t in trades:
        records.append({
            'pair': 'EURUSD',
            'side': 'LONG' if t.side == 1 else 'SHORT',
            'entry_time': t.entry_time,
            'exit_time': t.exit_time,
            'entry_price': f"{t.entry_price:.5f}",
            'exit_price': f"{t.exit_price:.5f}",
            'pnl': f"{t.pnl:.2f}",
            'pnl_pct': f"{t.pnl_pct:.2f}",
            'exit_reason': t.exit_reason,
        })
    df = pd.DataFrame(records)
    df.to_csv(output_path, index=False)


def main():
    """Run backtest on EURUSD H1 sample data."""
    # Try 2024 full year data first, fallback to sample
    data_path_new = Path('data/EURUSD_H1_2024.csv')
    data_path_old = Path('data/EURUSD_H1.csv')
    
    data_path = data_path_new if data_path_new.exists() else data_path_old
    
    if not data_path.exists():
        print(f"Data file not found")
        return
    
    print(f"Loading {data_path}...")
    h1_frame = load_h1_data(str(data_path))
    print(f"Loaded {len(h1_frame)} H1 bars from {h1_frame['timestamp'].min()} to {h1_frame['timestamp'].max()}")
    
    # Split 70/30
    split_idx = int(len(h1_frame) * 0.7)
    h1_train = h1_frame.iloc[:split_idx]
    h1_test = h1_frame.iloc[split_idx:]
    daily_train = resample_to_daily(h1_train)
    
    print(f"\nIn-sample: {len(h1_train)} bars, Out-of-sample: {len(h1_test)} bars")
    
    # Run in-sample backtest
    print("\nRunning in-sample backtest...")
    config = BacktestConfig()
    trades_is, metrics_is = run_backtest(h1_train, config, daily_train)
    
    # Run out-of-sample backtest
    print("Running out-of-sample backtest...")
    daily_test = resample_to_daily(h1_test)
    trades_oos, metrics_oos = run_backtest(h1_test, config, daily_test)
    
    # Print results
    print("\n" + "="*60)
    print("IN-SAMPLE RESULTS")
    print("="*60)
    print(f"Trades: {metrics_is['total_trades']} (W: {metrics_is['winning_trades']}, L: {metrics_is['losing_trades']})")
    print(f"Win Rate: {metrics_is['win_rate']:.1f}%")
    print(f"Profit Factor: {metrics_is['profit_factor']:.2f}")
    print(f"Total Return: {metrics_is['total_return_pct']:.2f}% ({metrics_is['total_return']:.2f})")
    print(f"Max Drawdown: {metrics_is['max_drawdown_pct']:.2f}%")
    print(f"Avg Trade: {metrics_is['avg_trade']:.2f}")
    
    print("\n" + "="*60)
    print("OUT-OF-SAMPLE RESULTS")
    print("="*60)
    print(f"Trades: {metrics_oos['total_trades']} (W: {metrics_oos['winning_trades']}, L: {metrics_oos['losing_trades']})")
    print(f"Win Rate: {metrics_oos['win_rate']:.1f}%")
    print(f"Profit Factor: {metrics_oos['profit_factor']:.2f}")
    print(f"Total Return: {metrics_oos['total_return_pct']:.2f}% ({metrics_oos['total_return']:.2f})")
    print(f"Max Drawdown: {metrics_oos['max_drawdown_pct']:.2f}%")
    print(f"Avg Trade: {metrics_oos['avg_trade']:.2f}")
    
    # Write reports
    print("\nWriting reports...")
    trades_to_csv(trades_is, 'reports/trades_is.csv')
    trades_to_csv(trades_oos, 'reports/trades_oos.csv')
    
    report = {
        'strategy': 'HTF Trend Pullback Trail',
        'data_range': f"{h1_frame['timestamp'].min()} to {h1_frame['timestamp'].max()}",
        'in_sample': metrics_is,
        'out_of_sample': metrics_oos,
    }
    with open('reports/metrics.json', 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print("Reports written to reports/")


if __name__ == "__main__":
    main()
