"""
STRATEGY OPTIMIZATION ENGINE
Automatically tests multiple strategies on real TradingView data
and generates optimal Pine Scripts
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime, timedelta

# ============================================================================
# STRATEGY DEFINITIONS
# ============================================================================

class StrategyOptimizer:
    def __init__(self, h1_data_path='data/EURUSD_H1_2024.csv'):
        """Initialize optimizer with H1 OHLC data"""
        self.data = pd.read_csv(h1_data_path, parse_dates=['timestamp'])
        self.data.set_index('timestamp', inplace=True)
        self.results = {}
        
    def add_indicators(self, df):
        """Add technical indicators to dataframe"""
        df['atr'] = self._calculate_atr(df, 14)
        df['rsi'] = self._calculate_rsi(df, 14)
        df['ema_50'] = self._calculate_ema(df['close'], 50)
        df['ema_200_daily'] = self._get_daily_ema(df, 200)
        
        # Daily S/R
        df['daily_high'] = self._get_daily_high(df)
        df['daily_low'] = self._get_daily_low(df)
        df['daily_swing_high'] = self._get_daily_swing(df, 'high', 20)
        df['daily_swing_low'] = self._get_daily_swing(df, 'low', 20)
        
        return df
    
    def _calculate_atr(self, df, period=14):
        """Calculate Average True Range"""
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift(1))
        low_close = abs(df['low'] - df['close'].shift(1))
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(period).mean()
    
    def _calculate_rsi(self, df, period=14):
        """Calculate RSI"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def _calculate_ema(self, series, period):
        """Calculate EMA"""
        return series.ewm(span=period, adjust=False).mean()
    
    def _get_daily_ema(self, df, period):
        """Get daily EMA on H1 data - simplified"""
        return df['close'].rolling(window=24).mean()  # 24 H1 bars = 1 day
    
    def _get_daily_high(self, df):
        """Get daily high for each H1 bar - simplified"""
        return df['high'].rolling(window=24).max()
    
    def _get_daily_low(self, df):
        """Get daily low for each H1 bar - simplified"""
        return df['low'].rolling(window=24).min()
    
    def _get_daily_swing(self, df, hl, lookback=20):
        """Get daily swing points (20-bar high/low)"""
        if hl == 'high':
            return df['high'].rolling(window=lookback).max()
        else:
            return df['low'].rolling(window=lookback).min()
    
    def test_breakout_pullback(self, sl_mult=1.0, tp_mult=3.0, entry_rsi_level=50):
        """Test Breakout+Pullback strategy with different parameters"""
        df = self.data.copy()
        df = self.add_indicators(df)
        
        trades = []
        entry_price = None
        entry_side = None
        stop_loss = None
        take_profit = None
        entry_idx = None
        
        # Breakout detection
        breakout_lookback = 20
        df['breakout_high'] = df['high'].rolling(breakout_lookback).max().shift(1)
        df['breakout_low'] = df['low'].rolling(breakout_lookback).min().shift(1)
        
        for i in range(breakout_lookback + 1, len(df)):
            row = df.iloc[i]
            
            # Exit conditions
            if entry_side == 1:  # LONG
                if row['close'] <= stop_loss or row['close'] >= take_profit or (i - entry_idx) > 100:
                    exit_reason = "SL" if row['close'] <= stop_loss else ("TP" if row['close'] >= take_profit else "Max")
                    pnl = (row['close'] - entry_price) * 10000
                    trades.append({
                        'entry_price': entry_price,
                        'exit_price': row['close'],
                        'pnl': pnl,
                        'pnl_pct': pnl / (entry_price * 10),
                        'side': 'LONG',
                        'exit_reason': exit_reason,
                        'bars': i - entry_idx
                    })
                    entry_side = None
            
            elif entry_side == -1:  # SHORT
                if row['close'] >= stop_loss or row['close'] <= take_profit or (i - entry_idx) > 100:
                    exit_reason = "SL" if row['close'] >= stop_loss else ("TP" if row['close'] <= take_profit else "Max")
                    pnl = (entry_price - row['close']) * 10000
                    trades.append({
                        'entry_price': entry_price,
                        'exit_price': row['close'],
                        'pnl': pnl,
                        'pnl_pct': pnl / (entry_price * 10),
                        'side': 'SHORT',
                        'exit_reason': exit_reason,
                        'bars': i - entry_idx
                    })
                    entry_side = None
            
            # Entry conditions
            if entry_side is None and i >= breakout_lookback + 10:
                prev_row = df.iloc[i-1]
                breakout_high = df.iloc[i - breakout_lookback]['breakout_high']
                breakout_low = df.iloc[i - breakout_lookback]['breakout_low']
                
                # LONG: Breakout pullback with RSI confirmation
                if (prev_row['high'] >= breakout_high and row['close'] < breakout_high and 
                    row['close'] > row['open'] and row['rsi'] > entry_rsi_level):
                    entry_price = row['close']
                    entry_side = 1
                    stop_loss = breakout_low - sl_mult * row['atr']
                    take_profit = row['close'] + tp_mult * row['atr']
                    entry_idx = i
                
                # SHORT: Breakout pullback with RSI confirmation
                elif (prev_row['low'] <= breakout_low and row['close'] > breakout_low and 
                      row['close'] < row['open'] and row['rsi'] < (100 - entry_rsi_level)):
                    entry_price = row['close']
                    entry_side = -1
                    stop_loss = breakout_high + sl_mult * row['atr']
                    take_profit = row['close'] - tp_mult * row['atr']
                    entry_idx = i
        
        return self._calculate_metrics(trades, 'Breakout+Pullback')
    
    def test_sr_bounce(self, sl_mult=1.5, tp_mult=1.5, rsi_oversold=30, rsi_overbought=70):
        """Test S/R Bounce strategy"""
        df = self.data.copy()
        df = self.add_indicators(df)
        
        trades = []
        entry_price = None
        entry_side = None
        stop_loss = None
        take_profit = None
        entry_idx = None
        
        for i in range(50, len(df)):
            row = df.iloc[i]
            
            # Exit conditions
            if entry_side == 1:
                if row['close'] <= stop_loss or row['close'] >= take_profit or (i - entry_idx) > 80:
                    exit_reason = "SL" if row['close'] <= stop_loss else ("TP" if row['close'] >= take_profit else "Max")
                    pnl = (row['close'] - entry_price) * 10000
                    trades.append({
                        'entry_price': entry_price,
                        'exit_price': row['close'],
                        'pnl': pnl,
                        'pnl_pct': pnl / (entry_price * 10),
                        'side': 'LONG',
                        'exit_reason': exit_reason,
                        'bars': i - entry_idx
                    })
                    entry_side = None
            
            elif entry_side == -1:
                if row['close'] >= stop_loss or row['close'] <= take_profit or (i - entry_idx) > 80:
                    exit_reason = "SL" if row['close'] >= stop_loss else ("TP" if row['close'] <= take_profit else "Max")
                    pnl = (entry_price - row['close']) * 10000
                    trades.append({
                        'entry_price': entry_price,
                        'exit_price': row['close'],
                        'pnl': pnl,
                        'pnl_pct': pnl / (entry_price * 10),
                        'side': 'SHORT',
                        'exit_reason': exit_reason,
                        'bars': i - entry_idx
                    })
                    entry_side = None
            
            # Entry conditions
            if entry_side is None:
                daily_low = row['daily_swing_low']
                daily_high = row['daily_swing_high']
                
                # LONG: Bounce from daily low + RSI oversold
                if (row['close'] >= daily_low - row['atr'] and row['close'] <= daily_low + row['atr'] * 0.5 and
                    row['rsi'] < rsi_oversold and row['close'] > row['open']):
                    entry_price = row['close']
                    entry_side = 1
                    stop_loss = daily_low - sl_mult * row['atr']
                    take_profit = row['close'] + tp_mult * row['atr']
                    entry_idx = i
                
                # SHORT: Bounce from daily high + RSI overbought
                elif (row['close'] <= daily_high + row['atr'] and row['close'] >= daily_high - row['atr'] * 0.5 and
                      row['rsi'] > rsi_overbought and row['close'] < row['open']):
                    entry_price = row['close']
                    entry_side = -1
                    stop_loss = daily_high + sl_mult * row['atr']
                    take_profit = row['close'] - tp_mult * row['atr']
                    entry_idx = i
        
        return self._calculate_metrics(trades, 'S/R Bounce')
    
    def _calculate_metrics(self, trades, strategy_name):
        """Calculate performance metrics"""
        if not trades:
            return {
                'strategy': strategy_name,
                'trades': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'total_pnl': 0,
                'avg_trade': 0
            }
        
        df_trades = pd.DataFrame(trades)
        winning_trades = df_trades[df_trades['pnl'] > 0]
        losing_trades = df_trades[df_trades['pnl'] <= 0]
        
        total_wins = winning_trades['pnl'].sum() if len(winning_trades) > 0 else 0
        total_losses = abs(losing_trades['pnl'].sum()) if len(losing_trades) > 0 else 0
        
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        win_rate = len(winning_trades) / len(df_trades) * 100 if len(df_trades) > 0 else 0
        
        return {
            'strategy': strategy_name,
            'trades': len(df_trades),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_pnl': df_trades['pnl'].sum(),
            'avg_trade': df_trades['pnl'].mean(),
            'trades_detail': df_trades.to_dict('records')
        }
    
    def run_optimization(self):
        """Run optimization across multiple parameter combinations"""
        print("=" * 70)
        print("STRATEGY OPTIMIZATION ENGINE - REAL DATA")
        print("=" * 70)
        
        # Test Breakout+Pullback with different parameters
        print("\nOptimizing Breakout+Pullback Strategy...")
        best_breakout = None
        best_pf = 0
        
        for sl_mult in [0.8, 1.0, 1.2]:
            for tp_mult in [2.5, 3.0, 3.5, 4.0]:
                for rsi_level in [45, 50, 55]:
                    result = self.test_breakout_pullback(sl_mult, tp_mult, rsi_level)
                    
                    if result['profit_factor'] > best_pf and result['trades'] >= 20:
                        best_pf = result['profit_factor']
                        best_breakout = {
                            'params': {'sl_mult': sl_mult, 'tp_mult': tp_mult, 'rsi_level': rsi_level},
                            'result': result
                        }
        
        # Test S/R Bounce with different parameters
        print("Optimizing S/R Bounce Strategy...")
        best_sr = None
        best_pf_sr = 0
        
        for sl_mult in [1.0, 1.5, 2.0]:
            for tp_mult in [1.0, 1.5, 2.0]:
                for rsi_os in [25, 30, 35]:
                    result = self.test_sr_bounce(sl_mult, tp_mult, rsi_os, 100 - rsi_os)
                    
                    if result['profit_factor'] > best_pf_sr and result['trades'] >= 20:
                        best_pf_sr = result['profit_factor']
                        best_sr = {
                            'params': {'sl_mult': sl_mult, 'tp_mult': tp_mult, 'rsi_oversold': rsi_os},
                            'result': result
                        }
        
        # Report best strategy
        print("\n" + "=" * 70)
        print("OPTIMIZATION RESULTS")
        print("=" * 70)
        
        if best_breakout:
            print(f"\n✅ BEST STRATEGY: Breakout+Pullback")
            print(f"   Parameters: {best_breakout['params']}")
            print(f"   Trades: {best_breakout['result']['trades']}")
            print(f"   Win Rate: {best_breakout['result']['win_rate']:.2f}%")
            print(f"   Profit Factor: {best_breakout['result']['profit_factor']:.2f}")
            print(f"   Total P&L: ${best_breakout['result']['total_pnl']:.2f}")
            print(f"   Avg Trade: ${best_breakout['result']['avg_trade']:.2f}")
        
        if best_sr:
            print(f"\n✅ ALTERNATIVE: S/R Bounce")
            print(f"   Parameters: {best_sr['params']}")
            print(f"   Trades: {best_sr['result']['trades']}")
            print(f"   Win Rate: {best_sr['result']['win_rate']:.2f}%")
            print(f"   Profit Factor: {best_sr['result']['profit_factor']:.2f}")
            print(f"   Total P&L: ${best_sr['result']['total_pnl']:.2f}")
            print(f"   Avg Trade: ${best_sr['result']['avg_trade']:.2f}")
        
        # Save results
        results = {
            'timestamp': datetime.now().isoformat(),
            'best_breakout': best_breakout,
            'best_sr': best_sr
        }
        
        Path('reports').mkdir(exist_ok=True)
        with open('reports/optimization_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        print("\n✅ Results saved to reports/optimization_results.json")
        
        return best_breakout, best_sr

if __name__ == "__main__":
    optimizer = StrategyOptimizer()
    best_breakout, best_sr = optimizer.run_optimization()
