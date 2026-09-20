# Live Trading Setup Guide

## 🚨 CRITICAL: Strategy Validation Status

**Current Status: ❌ FAILED VALIDATION**
- Profit Factor: 1.00 (required: ≥1.20)
- Out-of-Sample Trades: 12 (required: ≥40)
- Verdict: **FAILED** - Do not use with real money yet

Before going live, you need:
1. More historical data (6-12 months minimum)
2. Larger out-of-sample validation set (40+ trades)
3. Pass all OOS validation gates with real market conditions

---

## Part 1: TradingView Pine Script Setup

### Step 1: Copy Pine Script to TradingView

1. Open TradingView and go to **Pine Script Editor** (Alt+E or menu → Tools → Pine Script Editor)
2. Create a new script: **New → Strategy**
3. Copy the contents of `tradingview/HTF_Trend_Pullback_Trail.pine`
4. **Save** and give it a name

### Step 2: Configure Strategy Parameters

In the strategy properties, adjust these parameters:

| Parameter | Current | Description |
|-----------|---------|-------------|
| EMA Fast Period | 50 | Entry signal smoothing |
| ADX Period | 14 | Trend strength indicator |
| ADX Threshold | 18 | Minimum trend strength required |
| Stop Loss | 1.5 | Pips from entry |
| Trailing Stop | 3.0 | ATR multiplier for exit |
| Max bars in trade | 80 | Maximum bars to hold position |

### Step 3: Run Strategy Backtest on TradingView

1. **Strategy Tester** → Select chart
2. Set timeframe to **H1** (1-hour)
3. Choose symbol (e.g., EURUSD, USDJPY)
4. **Start backtest** and review results

---

## Part 2: Live Trading with Notifications

### Prerequisites

```bash
# Install dependencies
pip install oanda-v20 requests
pip install python-telegram-bot  # For Telegram
pip install discord.py           # For Discord
```

### Step 1: Choose Your Broker & Get API Keys

#### OANDA (Forex, CFDs)
1. Create account at [oanda.com](https://www.oanda.com)
2. Go to **Account Settings** → **API**
3. Generate API token
4. Copy **Account ID** and **Token**

#### Interactive Brokers
1. Create account at [interactivebrokers.com](https://www.interactivebrokers.com)
2. Download TWS (Trader Workstation)
3. Enable API in **Configure** → **Settings** → **API** → **Enable ActiveX and Socket Clients**

#### Binance (Crypto)
1. Create account at [binance.com](https://www.binance.com)
2. Go to **Account** → **API Management**
3. Create API key (no trading permissions needed yet)
4. Copy **API Key** and **Secret Key**

### Step 2: Set Up Notifications

#### Telegram (Recommended)
1. Open Telegram and message **@BotFather**
2. Type `/newbot` and follow instructions
3. Copy the **Bot Token**
4. Find your **Chat ID**:
   - Message **@userinfobot** to get your ID
   - Or add bot to a group and get group ID

#### Discord
1. Go to your Discord server → **Settings** → **Webhooks**
2. **Create Webhook** → name it (e.g., "Trading Bot")
3. Copy the **Webhook URL**

#### Email (Gmail)
1. Enable 2-factor authentication on Gmail
2. Create **App Password**: [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Copy the 16-character password

### Step 3: Create Live Trading Script

Create `config/live_config.json`:

```json
{
  "broker": {
    "type": "oanda",
    "account_id": "YOUR_ACCOUNT_ID",
    "api_token": "YOUR_API_TOKEN",
    "environment": "practice"
  },
  "notifier": {
    "type": "telegram",
    "bot_token": "YOUR_BOT_TOKEN",
    "chat_id": "YOUR_CHAT_ID"
  },
  "strategy": {
    "pair": "EUR_USD",
    "timeframe": "H1",
    "check_interval_seconds": 300
  }
}
```

Create `scripts/run_live.py`:

```python
import json
from pathlib import Path
from src.live_trading import LiveStrategyRunner, OandaAdapter, TelegramNotifier

# Load config
config_path = Path('config/live_config.json')
with open(config_path) as f:
    config = json.load(f)

# Initialize broker
broker_cfg = config['broker']
broker = OandaAdapter(
    account_id=broker_cfg['account_id'],
    api_token=broker_cfg['api_token'],
    environment=broker_cfg['environment']
)

# Initialize notifier
notifier_cfg = config['notifier']
if notifier_cfg['type'] == 'telegram':
    notifier = TelegramNotifier(
        bot_token=notifier_cfg['bot_token'],
        chat_id=notifier_cfg['chat_id']
    )

# Run strategy
runner = LiveStrategyRunner(
    broker=broker,
    notifier=notifier,
    pair=config['strategy']['pair'],
    timeframe=config['strategy']['timeframe']
)

runner.run(check_interval_seconds=config['strategy']['check_interval_seconds'])
```

### Step 4: Run Live Strategy

```bash
# Start live trading (practice account first!)
python scripts/run_live.py
```

You'll receive notifications like:
```
ℹ️ Strategy Started
Live trading started for EUR_USD on H1

🟢 LONG Entry: EUR_USD
Entry Price: 1.09823
Stop Loss: 1.09753
Time: 2026-09-20T14:30:00

🔴 LONG Exit: Trail Stop
Entry: 1.09823
Exit: 1.09750
P&L: -0.07%
Time: 2026-09-20T15:45:00
```

---

## ⚠️ Risk Management Checklist

Before going LIVE with real money:

- [ ] Test on **practice account** for at least 1 week
- [ ] Confirm notifications work correctly
- [ ] Monitor at least 10 live trades
- [ ] Verify P&L calculations match broker statements
- [ ] Set max daily loss limit in script
- [ ] Have emergency stop-loss procedure ready
- [ ] Validate strategy on more historical data (40+ OOS trades)

---

## Part 3: Advanced - Docker for 24/5 Execution

To run strategy continuously on a server:

### Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src src/
COPY scripts scripts/
COPY config config/
COPY data data/

CMD ["python", "scripts/run_live.py"]
```

### Build & Run:

```bash
# Build image
docker build -t tradingsystem:latest .

# Run container (detached)
docker run -d --name trading-bot tradingsystem:latest

# View logs
docker logs -f trading-bot

# Stop container
docker stop trading-bot
```

---

## Troubleshooting

### "No connection to broker"
- Check API token/credentials
- Verify network connectivity
- Try practice environment first

### "No notifications"
- Test Telegram: send message to bot manually
- Check chat_id is correct (should be numeric)
- Verify webhook URL is reachable

### "Insufficient historical data"
- Strategy requires minimum 50 bars of data
- On first run, may take 50 H1 candles (~2 days) to warm up

### "Position didn't close"
- Check broker account has available margin
- Verify position exists in broker platform
- Check order rejection errors in logs

---

## Dashboard Integration

The dashboard in `/docs/index.html` updates when you run:

```bash
uv run python -m src.backtest
uv run python -m src.optimize
uv run python -m src.build_site
```

Live strategy metrics will appear on dashboard automatically.

---

## Next Steps

1. **Backtest on more data** - Fetch 6-12 months of real EURUSD/USDJPY data
2. **Expand parameter grid** (Phase 02b) - Test EMA variations
3. **Multi-pair validation** - Validate across GBPUSD, USDJPY, BTCUSDT
4. **Deploy to cloud** - AWS/GCP/Azure for 24/5 execution

**Remember: Never trade with real money until strategy passes full OOS validation gates.**
