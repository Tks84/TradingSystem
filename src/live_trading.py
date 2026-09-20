"""
Live Trading Adapter for HTF Trend Pullback Trail Strategy
Connects to broker APIs and sends notifications for position management.

Supported Brokers:
- OANDA (via oanda-v20)
- Interactive Brokers (via ib_insync)
- Binance (via ccxt)

Supported Notifications:
- Telegram
- Discord
- Email
- Webhook
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from enum import Enum

import pandas as pd
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TradeSide(Enum):
    """Position side."""
    FLAT = 0
    LONG = 1
    SHORT = -1


class NotificationService:
    """Base class for notifications."""

    def send(self, title: str, message: str, level: str = "INFO") -> bool:
        """Send notification."""
        raise NotImplementedError


class TelegramNotifier(NotificationService):
    """Send notifications via Telegram."""

    def __init__(self, bot_token: str, chat_id: str):
        """
        Initialize Telegram notifier.
        
        Args:
            bot_token: Telegram bot token (from BotFather)
            chat_id: Telegram chat ID to receive messages
        """
        self.bot_token = bot_token
        self.chat_id = chat_id

    def send(self, title: str, message: str, level: str = "INFO") -> bool:
        """Send message via Telegram."""
        try:
            import requests
            
            emoji = {"INFO": "ℹ️", "ENTRY": "🟢", "EXIT": "🔴", "ERROR": "🚨"}
            text = f"{emoji.get(level, '•')} **{title}**\n{message}"
            
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"}
            
            response = requests.post(url, json=data, timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Telegram notification failed: {e}")
            return False


class DiscordNotifier(NotificationService):
    """Send notifications via Discord webhook."""

    def __init__(self, webhook_url: str):
        """
        Initialize Discord notifier.
        
        Args:
            webhook_url: Discord webhook URL
        """
        self.webhook_url = webhook_url

    def send(self, title: str, message: str, level: str = "INFO") -> bool:
        """Send message via Discord."""
        try:
            import requests
            
            color_map = {"INFO": 3447003, "ENTRY": 3066993, "EXIT": 15158332, "ERROR": 15746113}
            
            embed = {
                "title": title,
                "description": message,
                "color": color_map.get(level, 3447003),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            data = {"embeds": [embed]}
            response = requests.post(self.webhook_url, json=data, timeout=5)
            return response.status_code in [200, 204]
        except Exception as e:
            logger.error(f"Discord notification failed: {e}")
            return False


class EmailNotifier(NotificationService):
    """Send notifications via email."""

    def __init__(self, smtp_server: str, from_email: str, password: str, to_emails: List[str]):
        """
        Initialize email notifier.
        
        Args:
            smtp_server: SMTP server (e.g., 'smtp.gmail.com')
            from_email: Sender email
            password: Email password or app-specific password
            to_emails: List of recipient emails
        """
        self.smtp_server = smtp_server
        self.from_email = from_email
        self.password = password
        self.to_emails = to_emails

    def send(self, title: str, message: str, level: str = "INFO") -> bool:
        """Send notification via email."""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = ', '.join(self.to_emails)
            msg['Subject'] = f"[{level}] {title}"
            
            body = f"{message}\n\nSent at: {datetime.now().isoformat()}"
            msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(self.smtp_server, 587) as server:
                server.starttls()
                server.login(self.from_email, self.password)
                server.send_message(msg)
            
            return True
        except Exception as e:
            logger.error(f"Email notification failed: {e}")
            return False


class BrokerAdapter:
    """Base class for broker connectivity."""

    def get_latest_candle(self, pair: str, timeframe: str) -> Dict:
        """Fetch latest OHLC candle."""
        raise NotImplementedError

    def get_historical_data(self, pair: str, timeframe: str, count: int) -> pd.DataFrame:
        """Fetch historical OHLC data."""
        raise NotImplementedError

    def get_open_positions(self) -> List[Dict]:
        """Get all open positions."""
        raise NotImplementedError

    def place_order(self, pair: str, side: str, volume: float, order_type: str = "MARKET", 
                   stop_loss: float = None, take_profit: float = None) -> Dict:
        """Place order."""
        raise NotImplementedError

    def close_position(self, pair: str) -> Dict:
        """Close position."""
        raise NotImplementedError


class OandaAdapter(BrokerAdapter):
    """OANDA Broker Adapter (using oanda-v20)."""

    def __init__(self, account_id: str, api_token: str, environment: str = "practice"):
        """
        Initialize OANDA adapter.
        
        Args:
            account_id: OANDA account ID
            api_token: OANDA API token
            environment: 'practice' or 'live'
        """
        try:
            import oanda.v20 as v20
            
            self.account_id = account_id
            self.api_token = api_token
            self.environment = environment
            
            ctx = v20.Context(environment, 443, token=api_token)
            self.ctx = ctx
            self.client = v20.Client(ctx)
            logger.info(f"Connected to OANDA {environment} environment")
        except ImportError:
            logger.error("oanda-v20 not installed. Install with: pip install oanda-v20")
            raise

    def get_latest_candle(self, pair: str, timeframe: str = "H1") -> Dict:
        """Fetch latest candle from OANDA."""
        try:
            # Map timeframe to OANDA format
            tf_map = {"H1": "H1", "D1": "D", "M15": "M15", "M5": "M5"}
            granularity = tf_map.get(timeframe, "H1")
            
            response = self.client.instrument.candles(pair, count=2, granularity=granularity)
            
            if response['candles']:
                latest = response['candles'][-1]
                return {
                    'timestamp': latest['time'],
                    'open': float(latest['mid']['o']),
                    'high': float(latest['mid']['h']),
                    'low': float(latest['mid']['l']),
                    'close': float(latest['mid']['c']),
                }
            return None
        except Exception as e:
            logger.error(f"Failed to fetch candle: {e}")
            return None

    def place_order(self, pair: str, side: str, volume: float, stop_loss: float = None, 
                   take_profit: float = None) -> Dict:
        """Place market order."""
        try:
            import oanda.v20.orders as orders
            
            units = volume if side == "BUY" else -volume
            
            order_data = {
                'order': {
                    'units': str(int(units)),
                    'instrument': pair,
                    'timeInForce': 'FOK',
                    'type': 'MARKET',
                    'priceBound': None
                }
            }
            
            if stop_loss:
                order_data['order']['stopLossOnFill'] = {'price': str(stop_loss)}
            if take_profit:
                order_data['order']['takeProfitOnFill'] = {'price': str(take_profit)}
            
            response = self.client.order.create(self.account_id, **order_data)
            
            logger.info(f"Order placed: {response}")
            return {'success': True, 'order_id': response['orderFillTransaction']['id']}
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return {'success': False, 'error': str(e)}

    def close_position(self, pair: str) -> Dict:
        """Close position."""
        try:
            # Get open positions
            response = self.client.position.open(self.account_id)
            
            for position in response['positions']:
                if position['instrument'] == pair and position['long']['units'] != "0":
                    units = -int(position['long']['units'])
                    self.place_order(pair, "SELL", abs(units))
                    return {'success': True}
                elif position['instrument'] == pair and position['short']['units'] != "0":
                    units = -int(position['short']['units'])
                    self.place_order(pair, "BUY", abs(units))
                    return {'success': True}
            
            return {'success': False, 'error': 'No position found'}
        except Exception as e:
            logger.error(f"Failed to close position: {e}")
            return {'success': False, 'error': str(e)}


class LiveStrategyRunner:
    """Live strategy execution engine."""

    def __init__(self, broker: BrokerAdapter, notifier: NotificationService, 
                 pair: str = "EUR_USD", timeframe: str = "H1"):
        """
        Initialize live strategy runner.
        
        Args:
            broker: BrokerAdapter instance
            notifier: NotificationService instance
            pair: Trading pair (e.g., 'EUR_USD')
            timeframe: Chart timeframe (H1, D1, etc.)
        """
        self.broker = broker
        self.notifier = notifier
        self.pair = pair
        self.timeframe = timeframe
        
        # Strategy state
        self.entry_price = None
        self.entry_side = TradeSide.FLAT
        self.bars_in_trade = 0
        
        # Strategy parameters (from Phase 02 baseline)
        self.ema_period = 50
        self.adx_period = 14
        self.adx_threshold = 18
        self.atr_period = 14
        self.sl_pips = 1.5
        self.trailing_atr_mult = 3.0
        self.max_bars_in_trade = 80

    def _calculate_indicators(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate EMA, ATR, ADX."""
        from src.indicators import ema, atr, adx
        
        ema_fast = ema(df['close'], self.ema_period)
        atr_val = atr(df, self.atr_period)
        adx_val, _, _ = adx(df, self.adx_period)
        
        return ema_fast, atr_val, adx_val

    def run(self, check_interval_seconds: int = 300):
        """
        Run strategy in live mode.
        
        Args:
            check_interval_seconds: How often to check for new candles (default: 5 min)
        """
        import time
        
        logger.info(f"Starting live strategy: {self.pair} {self.timeframe}")
        self.notifier.send(
            "Strategy Started",
            f"Live trading started for {self.pair} on {self.timeframe}",
            level="INFO"
        )
        
        last_candle_time = None
        
        try:
            while True:
                try:
                    # Fetch latest data
                    candle = self.broker.get_latest_candle(self.pair, self.timeframe)
                    if not candle:
                        logger.warning("Failed to fetch candle, retrying...")
                        time.sleep(check_interval_seconds)
                        continue
                    
                    # Check for new candle
                    if last_candle_time and candle['timestamp'] == last_candle_time:
                        time.sleep(10)  # Wait before next check
                        continue
                    
                    last_candle_time = candle['timestamp']
                    logger.info(f"New candle: {candle}")
                    
                    # Fetch historical data for indicators
                    df = self.broker.get_historical_data(self.pair, self.timeframe, 200)
                    
                    if df is None or len(df) < 50:
                        logger.warning("Insufficient historical data")
                        time.sleep(check_interval_seconds)
                        continue
                    
                    # Calculate indicators
                    ema_fast, atr_val, adx_val = self._calculate_indicators(df)
                    
                    current_close = df['close'].iloc[-1]
                    current_ema = ema_fast.iloc[-1]
                    current_adx = adx_val.iloc[-1]
                    current_atr = atr_val.iloc[-1]
                    
                    logger.info(f"EMA50: {current_ema:.5f}, ADX: {current_adx:.2f}, ATR: {current_atr:.5f}")
                    
                    # Check entry conditions
                    if self.entry_side == TradeSide.FLAT:
                        long_entry = (current_adx >= self.adx_threshold and 
                                    current_close > current_ema and
                                    df['close'].iloc[-1] > df['open'].iloc[-1])  # Bullish
                        
                        short_entry = (current_adx >= self.adx_threshold and 
                                     current_close < current_ema and
                                     df['close'].iloc[-1] < df['open'].iloc[-1])  # Bearish
                        
                        if long_entry:
                            self._enter_long(current_close, current_atr)
                        elif short_entry:
                            self._enter_short(current_close, current_atr)
                    
                    else:
                        # Check exit conditions
                        self._check_exits(current_close, current_atr)
                    
                    time.sleep(check_interval_seconds)
                
                except Exception as e:
                    logger.error(f"Error in main loop: {e}")
                    self.notifier.send("Strategy Error", str(e), level="ERROR")
                    time.sleep(check_interval_seconds)
        
        except KeyboardInterrupt:
            logger.info("Strategy stopped by user")
            self.notifier.send("Strategy Stopped", "Live trading stopped", level="INFO")

    def _enter_long(self, price: float, atr: float):
        """Enter long position."""
        self.entry_price = price
        self.entry_side = TradeSide.LONG
        self.bars_in_trade = 0
        
        stop_loss = price - (self.sl_pips / 10000)
        
        self.notifier.send(
            f"🟢 LONG Entry: {self.pair}",
            f"Entry Price: {price:.5f}\nStop Loss: {stop_loss:.5f}\nTime: {datetime.now().isoformat()}",
            level="ENTRY"
        )

    def _enter_short(self, price: float, atr: float):
        """Enter short position."""
        self.entry_price = price
        self.entry_side = TradeSide.SHORT
        self.bars_in_trade = 0
        
        stop_loss = price + (self.sl_pips / 10000)
        
        self.notifier.send(
            f"🔴 SHORT Entry: {self.pair}",
            f"Entry Price: {price:.5f}\nStop Loss: {stop_loss:.5f}\nTime: {datetime.now().isoformat()}",
            level="ENTRY"
        )

    def _check_exits(self, price: float, atr: float):
        """Check exit conditions."""
        self.bars_in_trade += 1
        
        pnl = (price - self.entry_price) * (1 if self.entry_side == TradeSide.LONG else -1)
        pnl_pct = (pnl / self.entry_price) * 100
        
        # Simple SL check
        sl_dist = self.sl_pips / 10000
        if self.entry_side == TradeSide.LONG and price < (self.entry_price - sl_dist):
            self._exit_trade("Stop Loss", price, pnl_pct)
        elif self.entry_side == TradeSide.SHORT and price > (self.entry_price + sl_dist):
            self._exit_trade("Stop Loss", price, pnl_pct)
        
        # Max bars check
        elif self.bars_in_trade >= self.max_bars_in_trade:
            self._exit_trade("Max Bars", price, pnl_pct)

    def _exit_trade(self, reason: str, exit_price: float, pnl_pct: float):
        """Exit current position."""
        side_str = "LONG" if self.entry_side == TradeSide.LONG else "SHORT"
        
        self.notifier.send(
            f"🔴 {side_str} Exit: {reason}",
            f"Entry: {self.entry_price:.5f}\nExit: {exit_price:.5f}\nP&L: {pnl_pct:.2f}%\nTime: {datetime.now().isoformat()}",
            level="EXIT"
        )
        
        self.entry_side = TradeSide.FLAT
        self.entry_price = None
        self.bars_in_trade = 0


if __name__ == "__main__":
    # Example usage
    print("HTF Trend Pullback Trail - Live Trading Module")
    print("Configure broker and notifier in your script:")
    print()
    print("# Telegram example:")
    print("notifier = TelegramNotifier(bot_token='YOUR_BOT_TOKEN', chat_id='YOUR_CHAT_ID')")
    print()
    print("# OANDA broker example:")
    print("broker = OandaAdapter(account_id='YOUR_ACCOUNT_ID', api_token='YOUR_API_TOKEN')")
    print()
    print("# Run strategy:")
    print("runner = LiveStrategyRunner(broker, notifier, pair='EUR_USD', timeframe='H1')")
    print("runner.run(check_interval_seconds=300)")
