"""Update dashboard with backtest verdict and metrics from reports."""
import json
from pathlib import Path


def load_metrics(metrics_path='reports/metrics.json'):
    """Load backtest metrics from JSON."""
    with open(metrics_path, 'r') as f:
        return json.load(f)


def check_verdict(metrics):
    """Determine backtest verdict based on OOS gates."""
    oos = metrics.get('out_of_sample', {})
    
    # OOS acceptance gates
    gates = {
        'profit_factor': oos.get('profit_factor', 0) >= 1.20,
        'max_drawdown': oos.get('max_drawdown_pct', 100) <= 25.0,
        'trades': oos.get('total_trades', 0) >= 40,
        'avg_trade': oos.get('avg_trade', 0) >= 0,
    }
    
    if not any(oos.values()):  # No trades
        return 'NOT_RUN', 'gray'
    
    if all(gates.values()):
        return 'PASSED', 'green'
    else:
        return 'FAILED', 'red'


def update_dashboard_html(verdict, verdict_color, metrics):
    """Update /docs/index.html with verdict badge and metrics."""
    html_path = Path('docs/index.html')
    
    if not html_path.exists():
        print(f"Dashboard HTML not found: {html_path}")
        return
    
    with open(html_path, 'r') as f:
        html_content = f.read()
    
    # Extract metrics
    oos_data = metrics.get('out_of_sample', {})
    date_range = metrics.get('data_range', 'N/A')
    trades = int(oos_data.get('total_trades', 0))
    win_rate = float(oos_data.get('win_rate', 0))
    pf = float(oos_data.get('profit_factor', 0))
    dd = float(oos_data.get('max_drawdown_pct', 0))
    ret = float(oos_data.get('total_return_pct', 0))
    
    verdict_class = 'passed' if verdict_color == 'green' else 'failed'
    
    # Use simple string replacement for verdict badge
    import re
    html_content = re.sub(
        r'<span class="verdict \w+">NOT RUN</span>|<span class="verdict \w+">PASSED</span>|<span class="verdict \w+">FAILED</span>',
        f'<span class="verdict {verdict_class}">{verdict}</span>',
        html_content
    )
    
    # Replace metrics using simple string matching
    html_content = html_content.replace(
        '<div class="metric"><span>Date range</span><strong>Pending</strong><small>Sample data loaded</small></div>',
        f'<div class="metric"><span>Date range</span><strong>{date_range}</strong><small>Full dataset</small></div>'
    )
    html_content = html_content.replace(
        '<div class="metric"><span>Trades</span><strong>--</strong><small>Research pipeline deferred</small></div>',
        f'<div class="metric"><span>Trades</span><strong>{trades}</strong><small>Out-of-sample</small></div>'
    )
    html_content = html_content.replace(
        '<div class="metric"><span>Win rate</span><strong>--</strong><small>Not a target</small></div>',
        f'<div class="metric"><span>Win rate</span><strong>{win_rate:.1f}%</strong><small>Out-of-sample</small></div>'
    )
    html_content = html_content.replace(
        '<div class="metric"><span>Profit factor</span><strong>--</strong><small>Not evaluated</small></div>',
        f'<div class="metric"><span>Profit factor</span><strong>{pf:.2f}</strong><small>Out-of-sample</small></div>'
    )
    html_content = html_content.replace(
        '<div class="metric"><span>Max drawdown</span><strong>--</strong><small>Not evaluated</small></div>',
        f'<div class="metric"><span>Max drawdown</span><strong>{dd:.1f}%</strong><small>Out-of-sample</small></div>'
    )
    html_content = html_content.replace(
        '<div class="metric"><span>Total return</span><strong>--</strong><small>Not evaluated</small></div>',
        f'<div class="metric"><span>Total return</span><strong>{ret:.2f}%</strong><small>Out-of-sample</small></div>'
    )
    
    # Write updated HTML
    with open(html_path, 'w') as f:
        f.write(html_content)
    
    print(f"Dashboard updated: {html_path}")


def main():
    """Read metrics and update dashboard."""
    metrics_path = Path('reports/metrics.json')
    
    if not metrics_path.exists():
        print(f"Metrics file not found: {metrics_path}")
        return
    
    print("Loading backtest metrics...")
    metrics = load_metrics(str(metrics_path))
    
    print(f"\nData range: {metrics.get('data_range', 'N/A')}")
    
    # Determine verdict
    verdict, verdict_color = check_verdict(metrics)
    print(f"\nVERDICT: {verdict}")
    
    # Show OOS results
    oos = metrics.get('out_of_sample', {})
    print(f"\nOut-of-Sample Results:")
    print(f"  Trades: {oos.get('total_trades', 0)}")
    print(f"  Win Rate: {oos.get('win_rate', 0):.1f}%")
    print(f"  Profit Factor: {oos.get('profit_factor', 0):.2f}")
    print(f"  Max Drawdown: {oos.get('max_drawdown_pct', 0):.1f}%")
    print(f"  Total Return: {oos.get('total_return_pct', 0):.2f}%")
    print(f"  Avg Trade: ${oos.get('avg_trade', 0):.2f}")
    
    # Update dashboard
    update_dashboard_html(verdict, verdict_color, metrics)
    
    print("\n✓ Dashboard build complete")


if __name__ == "__main__":
    main()

