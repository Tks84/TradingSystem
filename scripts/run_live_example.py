"""
Quick Start Example: Run Live Strategy with Telegram Notifications

This example shows how to:
1. Connect to OANDA practice account
2. Send notifications to Telegram
3. Run strategy live with notifications

IMPORTANT: Test on PRACTICE account first!
"""

from src.live_trading import LiveStrategyRunner, OandaAdapter, TelegramNotifier
import json
from pathlib import Path


def main():
    # ====================================================================
    # STEP 1: Configure your credentials
    # ====================================================================
    
    # Get these from OANDA (oanda.com → Account Settings → API)
    OANDA_ACCOUNT_ID = "YOUR_ACCOUNT_ID"  # e.g., "123456789-001"
    OANDA_API_TOKEN = "YOUR_API_TOKEN"     # Long string starting with letters
    
    # Get these from Telegram
    TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN"  # From @BotFather
    TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"      # Your chat ID (numeric)
    
    # ====================================================================
    # STEP 2: Initialize broker connection
    # ====================================================================
    
    print("Connecting to OANDA...")
    broker = OandaAdapter(
        account_id=OANDA_ACCOUNT_ID,
        api_token=OANDA_API_TOKEN,
        environment="practice"  # Use "practice" for testing, "live" for real trading
    )
    
    # ====================================================================
    # STEP 3: Initialize notifications
    # ====================================================================
    
    print("Setting up Telegram notifications...")
    notifier = TelegramNotifier(
        bot_token=TELEGRAM_BOT_TOKEN,
        chat_id=TELEGRAM_CHAT_ID
    )
    
    # Test notification
    notifier.send(
        "Test Message",
        "If you see this, notifications are working!",
        level="INFO"
    )
    
    # ====================================================================
    # STEP 4: Create strategy runner
    # ====================================================================
    
    runner = LiveStrategyRunner(
        broker=broker,
        notifier=notifier,
        pair="EUR_USD",      # Trading pair
        timeframe="H1"       # 1-hour timeframe (match your analysis)
    )
    
    # ====================================================================
    # STEP 5: Run strategy
    # ====================================================================
    
    print("Starting live strategy...")
    print("You will receive notifications for:")
    print("  🟢 LONG entries")
    print("  🔴 SHORT entries")
    print("  🔴 Exits (SL, Trail stop, Max bars)")
    print("  🚨 Errors")
    print()
    print("Press Ctrl+C to stop")
    
    runner.run(check_interval_seconds=300)  # Check every 5 minutes


if __name__ == "__main__":
    main()
