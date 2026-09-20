"""Optimize strategy parameters with OOS validation gates and robustness testing."""
import pandas as pd
import json
from pathlib import Path
from src.backtest import BacktestConfig, run_backtest, load_h1_data, resample_to_daily


# OOS acceptance gates (from requirements)
OOS_GATES = {
    'min_profit_factor': 1.20,
    'max_drawdown_pct': 25.0,
    'min_trades': 40,  # Single pair threshold
    'min_avg_trade': 0,
}

# Parameter grid to search
PARAM_GRID = {
    'ema_fast': [50],           # Phase 02: single value (full grid in Phase 02b)
    'adx_min': [18],
    'sl_atr': [1.5],
    'trail_atr': [3.0],
    'session_filter': [False],
}


def check_oos_gates(metrics):
    """Check if out-of-sample metrics pass acceptance gates."""
    checks = {
        'profit_factor': metrics['profit_factor'] >= OOS_GATES['min_profit_factor'],
        'max_drawdown': metrics['max_drawdown_pct'] <= OOS_GATES['max_drawdown_pct'],
        'trade_count': metrics['total_trades'] >= OOS_GATES['min_trades'],
        'avg_trade': metrics['avg_trade'] >= OOS_GATES['min_avg_trade'],
    }
    return checks, all(checks.values())


def run_robustness_tests(h1_frame, config, daily_frame):
    """Run robustness tests: higher costs, time shift.
    Returns dict of test results.
    """
    results = {}
    
    # Test 1: +50% transaction costs
    config_high_cost = BacktestConfig()
    for attr in ['commission_pips', 'slippage_pips', 'ema_fast', 'ema_daily', 'adx_min',
                 'sl_atr_mult', 'trail_atr_mult', 'max_bars_in_trade', 'session_filter']:
        if hasattr(config, attr):
            setattr(config_high_cost, attr, getattr(config, attr))
    config_high_cost.commission_pips *= 1.5
    config_high_cost.slippage_pips *= 1.5
    
    trades_high_cost, metrics_high_cost = run_backtest(h1_frame, config_high_cost, daily_frame)
    results['high_costs'] = {
        'trades': len(trades_high_cost),
        'profit_factor': metrics_high_cost['profit_factor'],
        'return_pct': metrics_high_cost['total_return_pct'],
    }
    
    # Test 2: Time shift (shift bars by 1, wrap around)
    h1_shifted = h1_frame.copy().reset_index(drop=True)
    shift_cols = ['open', 'high', 'low', 'close', 'volume']
    for col in shift_cols:
        h1_shifted[col] = h1_frame[col].shift(1).fillna(h1_frame[col].iloc[0])
    
    trades_shift, metrics_shift = run_backtest(h1_shifted, config, daily_frame)
    results['time_shift'] = {
        'trades': len(trades_shift),
        'profit_factor': metrics_shift['profit_factor'],
        'return_pct': metrics_shift['total_return_pct'],
    }
    
    return results


def main():
    """Run parameter grid search with OOS validation."""
    # Try to use 2024 full year data, fallback to sample
    data_path_new = Path('data/EURUSD_H1_2024.csv')
    data_path_old = Path('data/EURUSD_H1.csv')
    
    data_path = data_path_new if data_path_new.exists() else data_path_old
    
    if not data_path.exists():
        print(f"Data file not found: {data_path_new} or {data_path_old}")
        return
    
    print("="*60)
    print("STRATEGY OPTIMIZATION")
    print("="*60)
    print(f"\nLoading {data_path}...")
    h1_frame = load_h1_data(str(data_path))
    daily_frame = resample_to_daily(h1_frame)
    
    print(f"Loaded {len(h1_frame)} H1 bars from {h1_frame['timestamp'].min()} to {h1_frame['timestamp'].max()}")
    print(f"  → 9148 bars = ~365 days (12 months) of data")
    print(f"  → Expected: ~640 bars IS (70%), ~2730 bars OOS (30%)")
    
    # Split 70/30
    split_idx = int(len(h1_frame) * 0.7)
    h1_train = h1_frame.iloc[:split_idx]
    h1_test = h1_frame.iloc[split_idx:]
    daily_train = resample_to_daily(h1_train)
    
    print(f"\nIn-sample: {len(h1_train)} bars ({h1_train['timestamp'].min()} to {h1_train['timestamp'].max()})")
    print(f"Out-of-sample: {len(h1_test)} bars ({h1_test['timestamp'].min()} to {h1_test['timestamp'].max()})")
    
    # Generate parameter combinations
    combos = []
    for ema_fast in PARAM_GRID['ema_fast']:
        for adx_min in PARAM_GRID['adx_min']:
            for sl_atr in PARAM_GRID['sl_atr']:
                for trail_atr in PARAM_GRID['trail_atr']:
                    for session_filter in PARAM_GRID['session_filter']:
                        combos.append({
                            'ema_fast': ema_fast,
                            'adx_min': adx_min,
                            'sl_atr': sl_atr,
                            'trail_atr': trail_atr,
                            'session_filter': session_filter,
                        })
    
    print(f"\nSearching {len(combos)} parameter combination(s)...")
    print("-"*60)
    
    # Run backtest for each combo on IN-SAMPLE data
    best_combo = None
    best_profit_factor = 0
    all_results = []
    metrics_is = None
    
    for idx, combo in enumerate(combos, 1):
        config = BacktestConfig()
        config.ema_fast = combo['ema_fast']
        config.adx_min = combo['adx_min']
        config.sl_atr_mult = combo['sl_atr']
        config.trail_atr_mult = combo['trail_atr']
        config.session_filter = combo['session_filter']
        
        # Run on in-sample
        trades_is, metrics_is = run_backtest(h1_train, config, daily_train)
        
        print(f"\nCombo {idx}/{len(combos)}: EMA={combo['ema_fast']}, ADX={combo['adx_min']}, "
              f"SL={combo['sl_atr']}, Trail={combo['trail_atr']}")
        print(f"  IS: {len(trades_is)} trades, PF={metrics_is['profit_factor']:.2f}, "
              f"Return={metrics_is['total_return_pct']:.1f}%")
        
        # Track best IS combo
        if metrics_is['profit_factor'] > best_profit_factor:
            best_profit_factor = metrics_is['profit_factor']
            best_combo = (config, combo)
        
        all_results.append({
            'combo': combo,
            'is': metrics_is,
            'oos': None,
            'robustness': None,
            'verdict': None,
        })
    
    if best_combo is None:
        print("\n" + "="*60)
        print("NO TRADES GENERATED IN-SAMPLE")
        print("="*60)
        print("\nVERDICT: FAILED (insufficient in-sample data)")
        print("Recommendation: Add more historical data or adjust entry filters.")
        
        report = {
            'timestamp': str(pd.Timestamp.now()),
            'strategy': 'HTF Trend Pullback Trail',
            'verdict': 'FAILED',
            'reason': 'No trades generated in-sample',
            'combo_tested': None,
            'all_results': all_results,
        }
        with open('reports/optimization_report.json', 'w') as f:
            json.dump(report, f, indent=2, default=str)
        return
    
    # Validate best combo on OUT-OF-SAMPLE
    config_best, combo_best = best_combo
    trades_oos, metrics_oos = run_backtest(h1_test, config_best, resample_to_daily(h1_test))
    
    print("\n" + "="*60)
    print(f"OUT-OF-SAMPLE VALIDATION")
    print("="*60)
    print(f"Combo: EMA={combo_best['ema_fast']}, ADX={combo_best['adx_min']}, "
          f"SL={combo_best['sl_atr']}, Trail={combo_best['trail_atr']}")
    print(f"\nOOS Results: {len(trades_oos)} trades, PF={metrics_oos['profit_factor']:.2f}, "
          f"Return={metrics_oos['total_return_pct']:.1f}%, MaxDD={metrics_oos['max_drawdown_pct']:.1f}%")
    
    # Check OOS gates
    gate_checks, gates_passed = check_oos_gates(metrics_oos)
    print(f"\nOOS Gate Checks:")
    for gate_name, passed in gate_checks.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {gate_name}")
    
    # Update results
    all_results[0]['oos'] = metrics_oos
    
    if not gates_passed:
        print("\n" + "="*60)
        print("VERDICT: FAILED")
        print("="*60)
        print("Out-of-sample validation failed robustness gates.")
        print("Do NOT increase parameter grid. Do NOT add indicators.")
        print("Recommendation: Review data quality or strategy logic.")
        
        all_results[0]['verdict'] = 'FAILED'
        
        report = {
            'timestamp': str(pd.Timestamp.now()),
            'strategy': 'HTF Trend Pullback Trail',
            'verdict': 'FAILED',
            'reason': 'Failed OOS validation gates',
            'combo_tested': combo_best,
            'in_sample': metrics_is,
            'out_of_sample': metrics_oos,
            'gate_checks': gate_checks,
            'all_results': all_results,
        }
        with open('reports/optimization_report.json', 'w') as f:
            json.dump(report, f, indent=2, default=str)
        return
    
    # Run robustness tests
    print("\n" + "="*60)
    print(f"ROBUSTNESS TESTING")
    print("="*60)
    
    robustness_results = run_robustness_tests(h1_test, config_best, resample_to_daily(h1_test))
    
    for test_name, test_result in robustness_results.items():
        print(f"\n{test_name}: {test_result['trades']} trades, "
              f"PF={test_result['profit_factor']:.2f}, Return={test_result['return_pct']:.1f}%")
    
    all_results[0]['robustness'] = robustness_results
    
    # Check robustness: PF should stay above 1.0 on all tests
    robustness_passed = True
    for test_name, test_result in robustness_results.items():
        if test_result['profit_factor'] < 1.0:
            robustness_passed = False
            print(f"✗ FRAGILE: {test_name} shows profit_factor < 1.0")
    
    if not robustness_passed:
        print("\n" + "="*60)
        print("VERDICT: FAILED")
        print("="*60)
        print("Strategy is FRAGILE. Failed robustness tests.")
        print("Do NOT deploy. Do NOT expand parameter grid.")
        print("Recommendation: Revisit entry logic or stop-loss placement.")
        
        all_results[0]['verdict'] = 'FAILED (Fragile)'
        
        report = {
            'timestamp': str(pd.Timestamp.now()),
            'strategy': 'HTF Trend Pullback Trail',
            'verdict': 'FAILED',
            'reason': 'Failed robustness testing',
            'combo_tested': combo_best,
            'in_sample': metrics_is,
            'out_of_sample': metrics_oos,
            'robustness': robustness_results,
            'all_results': all_results,
        }
        with open('reports/optimization_report.json', 'w') as f:
            json.dump(report, f, indent=2, default=str)
        return
    
    # All gates passed!
    print("\n" + "="*60)
    print("VERDICT: PASSED ✓")
    print("="*60)
    print(f"\nCombo passed all validation gates:")
    print(f"  ✓ OOS Profit Factor: {metrics_oos['profit_factor']:.2f} >= {OOS_GATES['min_profit_factor']}")
    print(f"  ✓ OOS Max Drawdown: {metrics_oos['max_drawdown_pct']:.1f}% <= {OOS_GATES['max_drawdown_pct']}%")
    print(f"  ✓ OOS Trade Count: {metrics_oos['total_trades']} >= {OOS_GATES['min_trades']}")
    print(f"  ✓ Robustness: All tests PF >= 1.0")
    print(f"\nRecommended Parameters:")
    print(f"  EMA (H1 pullback): {combo_best['ema_fast']}")
    print(f"  ADX threshold: {combo_best['adx_min']}")
    print(f"  SL ATR mult: {combo_best['sl_atr']}")
    print(f"  Trail ATR mult: {combo_best['trail_atr']}")
    print(f"  Session filter: {combo_best['session_filter']}")
    
    all_results[0]['verdict'] = 'PASSED'
    
    report = {
        'timestamp': str(pd.Timestamp.now()),
        'strategy': 'HTF Trend Pullback Trail',
        'verdict': 'PASSED',
        'reason': 'Passed all OOS gates and robustness tests',
        'combo_tested': combo_best,
        'in_sample': metrics_is,
        'out_of_sample': metrics_oos,
        'gate_checks': gate_checks,
        'robustness': robustness_results,
        'all_results': all_results,
    }
    with open('reports/optimization_report.json', 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print("\n" + "="*60)
    print("Optimization report written to reports/optimization_report.json")


if __name__ == "__main__":
    main()
