"""
Trading Bot with Wrapper Integration - OPTIMIZED CONFIGURATION

Based on backtest results (threshold=0.8):
- 287 trades over 14 days
- 71.1% win rate (204W / 83L)
- Profit Factor: 3.44
- Sharpe Ratio: 16.60
- Total P&L: +1842.66

KEY INSIGHTS FROM BACKTEST:
1. ASYMMETRIC TARGETS are crucial:
   - LONG: 1.0% target → 83.2% win rate
   - SHORT: 0.5% target → 60.9% win rate
2. Threshold 0.8 provides best risk-adjusted returns
3. Cooldown 60min prevents overtrading
4. Bayesian uncertainty filter (σ < 45min) critical

This replaces the simpler tradingbot_pytorch.py logic.

Usage:
    python tradingbot_wrapper_optimized.py
"""

import os
import sys
import json
import time
import requests
import logging
from datetime import datetime, timedelta, time as dt_time
from pathlib import Path
import pytz
import pandas_market_calendars as mcal

# Add project root to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
import numpy as np
import torch

# Neural Model imports
from neural.hybrid_model import get_hybrid_model, FEATURE_COLUMNS, get_device, load_hybrid_model
from trading_wrapper import TradingWrapper, TradeSignal, MarketRegime

# --- CONFIGURATION ---
load_dotenv()

# Paths
GREEK_DATA_DIR = os.getenv("GREEK_DATA_DIR", "/home/Option-Greeks-Plotting-Discord-Bot/json_data")
FOURIER_DIR = os.getenv("FOURIER_DIR", "/home/Option-Greeks-Plotting-Discord-Bot/fourier")
IB_CHARTS_DIR = os.getenv("IB_CHARTS_DIR", "/home/Option-Greeks-Plotting-Discord-Bot/ib_charts")
MODEL_PATH = os.path.join(PROJECT_ROOT, "models", "trading_hybrid.pt")
NORMALIZER_PATH = os.path.join(PROJECT_ROOT, "models", "hybrid_normalizer.npz")
CALIBRATION_PATH = os.path.join(PROJECT_ROOT, "models", "calibration.json")
TRADES_DIR = os.path.join(PROJECT_ROOT, "trades_wrapper")
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
POSITIONS_FILE = os.path.join(PROJECT_ROOT, "trades_wrapper", "open_positions.json")  # Persistent positions

# Create directories
os.makedirs(TRADES_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# =============================================================================
# OPTIMIZED TRADING PARAMETERS (From Backtest: 71.1% WR, PF 3.44, Sharpe 16.6)
# =============================================================================

MIN_CONFIDENCE = 0.80  # Threshold: 0.8 (287 trades over 14 days)
BASE_RISK_PCT = 0.01   # 1% base risk per trade
MAX_POSITION_PCT = 0.05  # 5% maximum position size
LOOP_INTERVAL = 30  # seconds

# ASYMMETRIC PROFIT TARGETS - This is the SECRET SAUCE
# LONG targets are 2x SHORT targets because:
# - LONG win rate: 83.2% (needs more room to run)
# - SHORT win rate: 60.9% (tighter targets work better)
TARGET_LONG_PCT = 0.010   # 1.0% target for LONG positions
TARGET_SHORT_PCT = 0.005  # 0.5% target for SHORT positions

# Risk Management
STOP_LOSS_PCT = 0.003  # 0.3% stop loss (same for both directions)
MAX_TIME_MINUTES = 120  # Max predicted time to target
MAX_UNCERTAINTY_MINUTES = 45.0  # Bayesian σ exit threshold
TRADE_COOLDOWN_MINUTES = 60  # Cooldown between trades (prevents overtrading)

# Market Filters
MIN_IV_PCT = 0.00  # Minimum IV percentile (0.0 = disabled)

# Discord Configuration
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
DISCORD_ROLE_PING = "<@&1464601287411634226>"
DISCORD_ENABLED = True

# Tickers - ONLY the 5 tickers used in training (from backtest)
# SPX: 91.5% win rate, +$1,123.14 P&L (59 trades) ⭐ BEST
# SPY: 90.4% win rate, +$101.94 P&L (52 trades) ⭐ BEST
# QQQ: 76.3% win rate, +$91.45 P&L (76 trades)
# /ES: 41.3% win rate, +$379.61 P&L (46 trades) - Lower WR but high absolute profit
# /NQ: 48.1% win rate, +$146.52 P&L (54 trades)
TICKERS = [
    "SPX",  # Index - Best performer
    "SPY",  # ETF tracking SPX
    "QQQ",  # Nasdaq ETF
]
FUTURES_TO_TRACK = []  # Futures
FUTURES_GREEKS_MAPPING = {"/ES": "SPX", "/NQ": "QQQ"}

# Point values for P&L calculation (only trained tickers)
POINT_VALUES = {
    "SPX": 50.0,   # SPX options: $50 per point
    "SPY": 100.0,  # SPY options: $100 per share (100 shares per contract)
    "QQQ": 100.0,  # QQQ options: $100 per share
    "/ES": 50.0,   # E-mini S&P 500: $50 per point
    "/NQ": 20.0,   # E-mini Nasdaq: $20 per point
}

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, "tradingbot_wrapper_optimized.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# DISCORD NOTIFICATIONS
# =============================================================================

def send_discord_trade_open(signal, timestamp=None):
    """Sends trade OPEN notification to Discord with optimized config info."""
    if not DISCORD_ENABLED or not DISCORD_WEBHOOK_URL:
        return
    
    current_time = timestamp if timestamp else datetime.now()
    time_str = current_time.strftime("%H:%M:%S")
    date_str = current_time.strftime("%Y-%m-%d")
    
    ticker = signal.ticker
    direction = signal.direction
    entry_price = signal.entry_price
    
    point_value = POINT_VALUES.get(ticker, 100.0)
    stop_distance = abs(entry_price - signal.stop_loss)
    target_distance = abs(signal.take_profit_1 - entry_price)
    risk_dollars = stop_distance * point_value * signal.position_size
    reward_dollars = target_distance * point_value * signal.position_size
    
    # Show target % based on direction (ASYMMETRIC)
    target_pct = TARGET_LONG_PCT if direction == "LONG" else TARGET_SHORT_PCT
    
    reason_parts = []
    regime = signal.regime.value if hasattr(signal.regime, 'value') else str(signal.regime)
    
    if "trending_up" in regime:
        reason_parts.append("📈 **Trending Up** → ML detects bullish momentum")
    elif "trending_down" in regime:
        reason_parts.append("📉 **Trending Down** → ML detects bearish momentum")
    elif "ranging" in regime:
        reason_parts.append("↔️ **Ranging** → ML detects range-bound market")
    elif "high_vol" in regime:
        reason_parts.append("🌪️ **High Volatility** → Elevated VIX environment")
    else:
        reason_parts.append(f"📊 **{regime.replace('_', ' ').title()}** regime detected")
    
    reason_parts.append(f"🎯 **Confidence**: {signal.raw_confidence:.1%} → {signal.calibrated_confidence:.1%} (calibrated)")
    reason_parts.append(f"📏 **Position Size**: {signal.position_size:.1%}")
    reason_parts.append(f"⚖️ **Asymmetric Target**: {target_pct:.1%} ({direction})")
    
    # Bayesian uncertainty info
    if hasattr(signal, 'time_sigma_minutes') and signal.time_sigma_minutes > 0:
        reason_parts.append(f"🔮 **Uncertainty**: σ = {signal.time_sigma_minutes:.1f}min (threshold: {MAX_UNCERTAINTY_MINUTES}min)")
    
    reason_text = "\n".join(reason_parts)
    
    color = 0x2ECC71 if direction == "LONG" else 0xE74C3C
    emoji = "📈" if direction == "LONG" else "📉"
    
    embed = {
        "title": f"{emoji} OPTIMIZED BOT {direction} - {ticker}",
        "description": f"**{DISCORD_ROLE_PING}**\n\n**🤖 ML Reasoning:**\n{reason_text}\n\n*Config: Threshold 0.8 | 71.1% WR | PF 3.44*",
        "color": color,
        "fields": [
            {"name": "🕒 Open Time", "value": f"{date_str} {time_str}", "inline": True},
            {"name": "💵 Entry Price", "value": f"${entry_price:.2f}", "inline": True},
            {"name": "📊 Point Value", "value": f"${point_value:.0f}/pt", "inline": True},
            {"name": f"🎯 Target ({target_pct:.1%})", "value": f"${signal.take_profit_1:.2f}", "inline": True},
            {"name": "🎯 TP2 (Extended)", "value": f"${signal.take_profit_2:.2f}", "inline": True},
            {"name": "🛑 Stop Loss (0.3%)", "value": f"${signal.stop_loss:.2f}", "inline": True},
            {"name": "⏱️ Max Hold", "value": f"{signal.max_hold_time} min", "inline": True},
            {"name": "💰 R:R Ratio", "value": f"{target_distance/stop_distance:.2f}:1" if stop_distance > 0 else "N/A", "inline": True},
            {"name": "💵 Risk/Reward", "value": f"Risk: ${risk_dollars:.2f} | Reward: ${reward_dollars:.2f}" if risk_dollars > 0 else "N/A", "inline": False},
        ],
        "footer": {"text": "TradingBotWrapper v2.0 | Optimized | LIVE"}
    }
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json={"content": f"{DISCORD_ROLE_PING} Optimized ML Trade", "embeds": [embed]}, timeout=5)
        if response.status_code >= 400:
            logger.error(f"[DISCORD] Webhook error: {response.status_code}")
        else:
            logger.info(f"[DISCORD] Trade open notification sent for {ticker}")
    except Exception as e:
        logger.error(f"[DISCORD] Failed to send open notification: {e}")


def send_discord_trade_close(position, exit_price: float, reason: str, pnl_pct: float, pnl_dollars: float, close_time=None):
    """Sends trade CLOSE notification to Discord."""
    if not DISCORD_ENABLED or not DISCORD_WEBHOOK_URL:
        return
    
    exit_time = close_time if close_time else datetime.now()
    entry_time = position.entry_time
    
    ticker = position.ticker
    direction = position.direction
    entry_price = position.entry_price
    
    point_value = POINT_VALUES.get(ticker, 100.0)
    
    duration_mins = (exit_time - entry_time).total_seconds() / 60
    if duration_mins >= 60:
        hours = int(duration_mins // 60)
        mins = int(duration_mins % 60)
        duration_text = f"{hours}h {mins}m"
    else:
        duration_text = f"{int(duration_mins)}m"
    
    entry_str = entry_time.strftime("%Y-%m-%d %H:%M")
    exit_str = exit_time.strftime("%Y-%m-%d %H:%M")
    
    if "STOP" in reason.upper():
        exit_explanation = "🛑 **Stop Loss Hit** - Price moved against position"
    elif "PROFIT" in reason.upper() or "TP" in reason.upper():
        exit_explanation = "🎯 **Target Hit** - Price reached profit objective"
    elif "TIME" in reason.upper() or "HOLD" in reason.upper():
        exit_explanation = "⏰ **Max Hold Time** - Position held too long"
    elif "UNCERTAINTY" in reason.upper():
        exit_explanation = f"🌫️ **High Uncertainty** - Bayesian sigma > {MAX_UNCERTAINTY_MINUTES}min threshold"
    elif "CLOSE" in reason.upper() or "EOD" in reason.upper():
        exit_explanation = "🔔 **End of Day** - Forced exit before market close"
    else:
        exit_explanation = f"📋 **{reason}**"
    
    color = 0x2ECC71 if pnl_pct >= 0 else 0xE74C3C
    emoji = "✅" if pnl_pct >= 0 else "❌"
    result = "PROFIT" if pnl_pct >= 0 else "LOSS"
    
    price_move = exit_price - entry_price
    price_move_pct = (price_move / entry_price) * 100 if entry_price > 0 else 0
    
    # Show which target was used
    target_pct = TARGET_LONG_PCT if direction == "LONG" else TARGET_SHORT_PCT
    
    embed = {
        "title": f"{emoji} OPTIMIZED BOT {direction} CLOSED - {ticker} ({result})",
        "description": f"**{DISCORD_ROLE_PING}**\n\n{exit_explanation}\n\n*Target: {target_pct:.1%} | Stop: {STOP_LOSS_PCT:.1%}*",
        "color": color,
        "fields": [
            {"name": "🕒 Open", "value": entry_str, "inline": True},
            {"name": "🏁 Close", "value": exit_str, "inline": True},
            {"name": "⏱️ Duration", "value": duration_text, "inline": True},
            {"name": "💵 Entry", "value": f"${entry_price:.2f}", "inline": True},
            {"name": "💵 Exit", "value": f"${exit_price:.2f}", "inline": True},
            {"name": "📊 Move", "value": f"{price_move:+.2f} pts ({price_move_pct:+.2f}%)", "inline": True},
            {"name": "📊 P&L %", "value": f"{pnl_pct*100:+.2f}%", "inline": True},
            {"name": f"💰 P&L (${point_value:.0f}/pt)", "value": f"**${pnl_dollars:+.2f}**", "inline": True},
        ],
        "footer": {"text": "TradingBotWrapper v2.0 | Optimized | LIVE"}
    }
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json={"content": f"{DISCORD_ROLE_PING} Trade Closed", "embeds": [embed]}, timeout=5)
        if response.status_code >= 400:
            logger.error(f"[DISCORD] Webhook error: {response.status_code}")
        else:
            logger.info(f"[DISCORD] Trade close notification sent for {ticker}")
    except Exception as e:
        logger.error(f"[DISCORD] Failed to send close notification: {e}")


class Position:
    """Tracks an open position with asymmetric targets and comprehensive analytics."""
    
    def __init__(self, signal: TradeSignal):
        self.ticker = signal.ticker
        self.direction = signal.direction
        self.entry_price = signal.entry_price
        self.entry_time = datetime.now()
        self.position_size = signal.position_size
        self.calibrated_confidence = signal.calibrated_confidence
        self.raw_confidence = signal.raw_confidence
        self.current_stop = signal.stop_loss
        self.take_profit_1 = signal.take_profit_1
        self.take_profit_2 = signal.take_profit_2
        self.max_hold_time = signal.max_hold_time
        self.regime = signal.regime
        self.partial_exit_done = False
        
        # Bayesian uncertainty from initial signal
        self.time_mu_minutes = signal.time_mu_minutes
        self.time_sigma_minutes = signal.time_sigma_minutes
        
        # Store full reasoning for post-trade analysis
        self.entry_reasoning = signal.reasoning
        
        # Track price movement history (for post-analysis)
        self.price_history = []  # List of (timestamp, price) tuples
        self.stop_updates = []   # List of (timestamp, old_stop, new_stop) tuples
        
        # Greek snapshots at entry (will be populated by _open_position)
        self.entry_greeks = {}
        self.entry_ib_context = {}
        
        # Target used (for asymmetric tracking)
        self.target_pct_used = TARGET_LONG_PCT if direction == "LONG" else TARGET_SHORT_PCT
    
    def add_price_update(self, price: float):
        """Track price movement during trade lifetime."""
        self.price_history.append({
            "timestamp": datetime.now().isoformat(),
            "price": price
        })
    
    def add_stop_update(self, old_stop: float, new_stop: float):
        """Track trailing stop adjustments."""
        self.stop_updates.append({
            "timestamp": datetime.now().isoformat(),
            "old_stop": old_stop,
            "new_stop": new_stop,
            "distance_from_entry_pct": abs(new_stop - self.entry_price) / self.entry_price
        })
    
    def to_dict(self) -> dict:
        """Serialize position to comprehensive dictionary for JSON storage."""
        return {
            # === BASIC TRADE INFO ===
            "ticker": self.ticker,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time.isoformat(),
            
            # === POSITION SIZING & CONFIDENCE ===
            "position_size": self.position_size,
            "raw_confidence": self.raw_confidence,
            "calibrated_confidence": self.calibrated_confidence,
            
            # === TARGETS & STOPS (ASYMMETRIC) ===
            "target_pct_used": self.target_pct_used,
            "stop_loss_pct": STOP_LOSS_PCT,
            "current_stop": self.current_stop,
            "take_profit_1": self.take_profit_1,
            "take_profit_2": self.take_profit_2,
            
            # === BAYESIAN PREDICTIONS ===
            "time_mu_minutes": self.time_mu_minutes,
            "time_sigma_minutes": self.time_sigma_minutes,
            "max_hold_time": self.max_hold_time,
            
            # === MARKET CONTEXT AT ENTRY ===
            "regime": self.regime.value if hasattr(self.regime, 'value') else str(self.regime),
            "entry_reasoning": self.entry_reasoning,
            "entry_greeks": self.entry_greeks,
            "entry_ib_context": self.entry_ib_context,
            
            # === TRADE MANAGEMENT ===
            "partial_exit_done": self.partial_exit_done,
            "stop_updates": self.stop_updates,
            "price_history": self.price_history[-50:] if len(self.price_history) > 50 else self.price_history,  # Last 50 updates only
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Position':
        """Deserialize position from dictionary."""
        # Create a mock signal to initialize Position
        class MockSignal:
            def __init__(self, d):
                self.ticker = d["ticker"]
                self.direction = d["direction"]
                self.entry_price = d["entry_price"]
                self.position_size = d["position_size"]
                self.calibrated_confidence = d["calibrated_confidence"]
                self.stop_loss = d["current_stop"]
                self.take_profit_1 = d["take_profit_1"]
                self.take_profit_2 = d["take_profit_2"]
                self.max_hold_time = d["max_hold_time"]
                self.time_mu_minutes = d.get("time_mu_minutes", 0.0)
                self.time_sigma_minutes = d.get("time_sigma_minutes", 0.0)
                
                # Handle regime (could be string or enum)
                regime_str = d.get("regime", "ranging")
                try:
                    self.regime = MarketRegime(regime_str)
                except:
                    self.regime = MarketRegime.RANGING
        
        position = cls(MockSignal(data))
        position.entry_time = datetime.fromisoformat(data["entry_time"])
        position.partial_exit_done = data.get("partial_exit_done", False)
        
        return position


class TradingBotWrapper:
    """Trading bot using the intelligent wrapper with OPTIMIZED configuration."""
    
    def __init__(self):
        self.device = get_device()
        self.model = None
        self.normalizer = None
        self.wrapper = None
        self.positions = {}  # ticker -> Position
        self.trade_history = []
        self.prev_features = {}  # Cache for temporal deltas {ticker: features_dict}
        self.daily_stats = {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "pnl": 0.0,
        }
        self.last_trade_time = {} # ticker -> datetime
        
        self._load_model()
        self._load_open_positions()  # Load any positions that survived restart
    
    def _save_open_positions(self):
        """Save all open positions to disk (atomic write)."""
        try:
            positions_data = {
                ticker: position.to_dict() 
                for ticker, position in self.positions.items()
            }
            
            # Atomic write: write to temp file, then rename
            temp_file = POSITIONS_FILE + ".tmp"
            with open(temp_file, 'w') as f:
                json.dump(positions_data, f, indent=2)
            
            # Atomic rename (overwrites existing file)
            os.replace(temp_file, POSITIONS_FILE)
            
            logger.debug(f"Saved {len(positions_data)} open position(s) to disk")
        except Exception as e:
            logger.error(f"Failed to save open positions: {e}")
    
    def _load_open_positions(self):
        """Load open positions from disk after restart."""
        if not os.path.exists(POSITIONS_FILE):
            logger.info("No saved positions found (fresh start)")
            return
        
        try:
            with open(POSITIONS_FILE, 'r') as f:
                positions_data = json.load(f)
            
            if not positions_data:
                logger.info("No open positions to restore")
                return
            
            # Restore positions
            for ticker, pos_dict in positions_data.items():
                try:
                    position = Position.from_dict(pos_dict)
                    self.positions[ticker] = position
                    
                    # Calculate how long position has been open
                    duration_mins = (datetime.now() - position.entry_time).total_seconds() / 60
                    
                    logger.info(f"[RESTORED] {ticker} {position.direction}")
                    logger.info(f"  Entry: {position.entry_price:.2f} @ {position.entry_time.strftime('%Y-%m-%d %H:%M')}")
                    logger.info(f"  Duration: {duration_mins:.0f} min")
                    logger.info(f"  Stop: {position.current_stop:.2f} | TP1: {position.take_profit_1:.2f} | TP2: {position.take_profit_2:.2f}")
                except Exception as e:
                    logger.error(f"Failed to restore position for {ticker}: {e}")
            
            logger.info(f"Successfully restored {len(self.positions)} position(s) from disk")
            
        except Exception as e:
            logger.error(f"Failed to load open positions: {e}")
            # Don't crash - continue with empty positions
    
    def _load_model(self):
        """Load model and initialize wrapper."""
        if not os.path.exists(MODEL_PATH):
            logger.error(f"Model not found: {MODEL_PATH}")
            logger.info("Run train_hybrid.py or train_walkforward.py first")
            raise FileNotFoundError(MODEL_PATH)
        
        self.model, self.normalizer = load_hybrid_model(
            MODEL_PATH, NORMALIZER_PATH, 
            model_size="medium", device=self.device  # Changed from "small" to "medium"
        )
        
        # Initialize wrapper with OPTIMIZED parameters
        calibration = CALIBRATION_PATH if os.path.exists(CALIBRATION_PATH) else None
        
        self.wrapper = TradingWrapper(
            model=self.model,
            normalizer=self.normalizer,
            greek_dir=GREEK_DATA_DIR,
            fourier_dir=FOURIER_DIR,
            ib_dir=IB_CHARTS_DIR,
            calibration_path=calibration,
            min_confidence=MIN_CONFIDENCE,
            base_risk_pct=BASE_RISK_PCT,
            max_position_pct=MAX_POSITION_PCT,
            min_iv_pct=MIN_IV_PCT,
            max_time_minutes=MAX_TIME_MINUTES,
            stop_loss_pct=STOP_LOSS_PCT,
        )
        
        logger.info("=" * 70)
        logger.info("OPTIMIZED MODEL CONFIGURATION LOADED")
        logger.info("=" * 70)
        logger.info(f"Backtest Performance (14 days, threshold {MIN_CONFIDENCE}):")
        logger.info(f"  • Total Trades: 287")
        logger.info(f"  • Win Rate: 71.1% (204W / 83L)")
        logger.info(f"  • Profit Factor: 3.44")
        logger.info(f"  • Sharpe Ratio: 16.60")
        logger.info(f"  • Total P&L: +$1,842.66")
        logger.info(f"\nKey Features:")
        logger.info(f"  • ASYMMETRIC TARGETS:")
        logger.info(f"    - LONG: {TARGET_LONG_PCT:.1%} target (83.2% WR backtest)")
        logger.info(f"    - SHORT: {TARGET_SHORT_PCT:.1%} target (60.9% WR backtest)")
        logger.info(f"  • Stop Loss: {STOP_LOSS_PCT:.1%} (both directions)")
        logger.info(f"  • Bayesian Exit: sigma > {MAX_UNCERTAINTY_MINUTES}min")
        logger.info(f"  • Cooldown: {TRADE_COOLDOWN_MINUTES}min")
        logger.info("=" * 70)
    
    def get_latest_greek_data(self, ticker: str) -> dict:
        """Find and load the most recent Greek data JSON."""
        search_ticker = ticker.replace("/", "")
        pattern = f"{search_ticker}_0dte_ExposureData_"
        json_files = list(Path(GREEK_DATA_DIR).glob(f"{pattern}*.json"))
        
        if not json_files:
            return None
        
        latest_file = max(json_files, key=lambda p: p.stat().st_mtime)
        
        # Check freshness
        age = time.time() - latest_file.stat().st_mtime
        if age > 120:  # 2 minutes
            logger.debug(f"Greek data for {ticker} is {age/60:.1f} min old")
            return None
        
        with open(latest_file, 'r') as f:
            return json.load(f)
    
    def get_ib_data(self, ticker: str) -> dict:
        """Load IB data for ticker."""
        safe_ticker = ticker.replace("/", "")
        today = datetime.now().strftime("%Y-%m-%d")
        ib_file = Path(IB_CHARTS_DIR) / f"ib_data_{safe_ticker}_{today}.json"
        
        if not ib_file.exists():
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            ib_file = Path(IB_CHARTS_DIR) / f"ib_data_{safe_ticker}_{yesterday}.json"
        
        if not ib_file.exists():
            return None
        
        with open(ib_file, 'r') as f:
            return json.load(f)
    
    def get_latest_weekly_data(self, ticker: str) -> dict:
        """Find and load the most recent weekly Greek data JSON."""
        search_ticker = ticker.replace("/", "")
        pattern = f"{search_ticker}_weekly_ExposureData_"
        json_files = list(Path(GREEK_DATA_DIR).glob(f"{pattern}*.json"))
        
        if not json_files:
            return None
        
        latest_file = max(json_files, key=lambda p: p.stat().st_mtime)
        
        # Weekly data changes slowly, 30 min freshness is fine
        age = time.time() - latest_file.stat().st_mtime
        if age > 1800:  # 30 minutes
            logger.debug(f"Weekly data for {ticker} is {age/60:.1f} min old")
            return None
        
        with open(latest_file, 'r') as f:
            return json.load(f)
    
    def extract_features(self, greek_data: dict, ib_data: dict, ticker: str,
                         weekly_data: dict = None) -> np.ndarray:
        """Extract features from 0DTE Greek, weekly Greek, and IB data."""
        features = {}
        
        # Get current price
        current_price = greek_data.get("spot", greek_data.get("spot_price", 0))
        if current_price == 0:
            return None
        
        # 0DTE Greek exposures (8 greeks — includes Vega and Vomma)
        for greek in ["totalgamma", "totalvanna", "totalcharm", "totaldgex", "totalzomma", "totaldelta", "totalvega", "totalvomma"]:
            data = greek_data.get(greek, {}).get("all", [])
            net_value = sum(data) if data else 0
            name = greek.replace("total", "net_")
            features[name] = net_value
        
        # Greek signals
        features["gamma_regime"] = 1 if features.get("net_gamma", 0) > 0 else 0
        features["vanna_bullish"] = 1 if features.get("net_vanna", 0) > 0 else 0
        features["charm_bullish"] = 1 if features.get("net_charm", 0) > 0 else 0
        features["dgex_sticky"] = 1 if abs(features.get("net_dgex", 0)) > 1e6 else 0
        features["zomma_stabilizing"] = 1 if features.get("net_zomma", 0) > 0 else 0
        features["vega_elevated"] = 1 if abs(features.get("net_vega", 0)) > 0.1 else 0
        
        # Key levels (0DTE)
        strikes = greek_data.get("strikes", greek_data.get("levels", []))
        gamma_data = greek_data.get("totalgamma", {}).get("all", [])
        vanna_data = greek_data.get("totalvanna", {}).get("all", [])
        dgex_data = greek_data.get("totaldgex", {}).get("all", [])
        
        if strikes and gamma_data and len(strikes) == len(gamma_data):
            max_idx = np.argmax(gamma_data)
            min_idx = np.argmin(gamma_data)
            max_gamma_strike = strikes[max_idx]
            min_gamma_strike = strikes[min_idx]
            
            features["dist_to_max_gamma"] = (current_price - max_gamma_strike) / current_price
            features["dist_to_min_gamma"] = (current_price - min_gamma_strike) / current_price
            features["near_max_gamma"] = 1 if abs(features["dist_to_max_gamma"]) < 0.004 else 0
            features["near_min_gamma"] = 1 if abs(features["dist_to_min_gamma"]) < 0.004 else 0
        
        if strikes and vanna_data and len(strikes) == len(vanna_data):
            min_idx = np.argmin(vanna_data)
            min_vanna_strike = strikes[min_idx]
            features["dist_to_min_vanna"] = (current_price - min_vanna_strike) / current_price
        
        features["dist_to_zero_gamma"] = features.get("dist_to_max_gamma", 0)
        
        # DGEX key levels (Magnet & Accelerator)
        if strikes and dgex_data and len(strikes) == len(dgex_data):
            max_dgex_strike = strikes[np.argmax(dgex_data)]
            min_dgex_strike = strikes[np.argmin(dgex_data)]
            features["dist_to_max_dgex"] = (current_price - max_dgex_strike) / current_price
            features["dist_to_min_dgex"] = (current_price - min_dgex_strike) / current_price
        
        # Vega/Vomma key levels
        vega_data = greek_data.get("totalvega", {}).get("all", [])
        vomma_data = greek_data.get("totalvomma", {}).get("all", [])
        
        max_vega_strike = current_price
        min_vega_strike = current_price
        max_vomma_strike = current_price
        min_vomma_strike = current_price
        
        if strikes and vega_data and len(strikes) == len(vega_data):
            max_vega_strike = strikes[np.argmax(vega_data)]
            min_vega_strike = strikes[np.argmin(vega_data)]
            features["dist_to_max_vega"] = (current_price - max_vega_strike) / current_price
            features["dist_to_min_vega"] = (current_price - min_vega_strike) / current_price
        
        if strikes and vomma_data and len(strikes) == len(vomma_data):
            max_vomma_strike = strikes[np.argmax(vomma_data)]
            min_vomma_strike = strikes[np.argmin(vomma_data)]
            features["dist_to_max_vomma"] = (current_price - max_vomma_strike) / current_price
            features["dist_to_min_vomma"] = (current_price - min_vomma_strike) / current_price
        
        # ===== WEEKLY GREEKS =====
        if weekly_data:
            for greek in ["totalgamma", "totalvanna", "totalcharm", "totaldgex", "totalzomma", "totaldelta", "totalvega", "totalvomma"]:
                wk_arr = weekly_data.get(greek, {}).get("all", [])
                name = "wk_" + greek.replace("total", "net_")
                features[name] = sum(wk_arr) if wk_arr else 0
            
            wk_strikes = weekly_data.get("strikes", weekly_data.get("levels", []))
            wk_gamma = weekly_data.get("totalgamma", {}).get("all", [])
            wk_dgex = weekly_data.get("totaldgex", {}).get("all", [])
            
            if wk_strikes and wk_gamma and len(wk_strikes) == len(wk_gamma):
                features["wk_dist_to_max_gamma"] = (current_price - wk_strikes[np.argmax(wk_gamma)]) / current_price
                features["wk_dist_to_min_gamma"] = (current_price - wk_strikes[np.argmin(wk_gamma)]) / current_price
            
            if wk_strikes and wk_dgex and len(wk_strikes) == len(wk_dgex):
                features["wk_dist_to_max_dgex"] = (current_price - wk_strikes[np.argmax(wk_dgex)]) / current_price
                features["wk_dist_to_min_dgex"] = (current_price - wk_strikes[np.argmin(wk_dgex)]) / current_price
            
            # Weekly regime signals
            features["wk_gamma_regime"] = 0.5 if features.get("wk_net_gamma", 0) == 0 else (1.0 if features.get("wk_net_gamma", 0) > 0 else 0.0)
            features["wk_vanna_bullish"] = 1 if features.get("wk_net_vanna", 0) > 0 else 0
            features["wk_dgex_sticky"] = 1 if features.get("wk_net_dgex", 0) > 0 else 0
            features["wk_zomma_stabilizing"] = 1 if features.get("wk_net_zomma", 0) > 0 else 0
            features["wk_vega_elevated"] = 1 if abs(features.get("wk_net_vega", 0)) > 0.1 else 0
            
            # Weekly Vega/Vomma key levels
            wk_vega = weekly_data.get("totalvega", {}).get("all", [])
            if wk_strikes and wk_vega and len(wk_strikes) == len(wk_vega):
                features["wk_dist_to_max_vega"] = (current_price - wk_strikes[np.argmax(wk_vega)]) / current_price
                features["wk_dist_to_min_vega"] = (current_price - wk_strikes[np.argmin(wk_vega)]) / current_price
        
        # ===== CROSS-EXPIRY DIVERGENCE =====
        def _sign_div(a, b):
            if abs(a) < 0.01 or abs(b) < 0.01:
                return 0.5
            return 1.0 if (a > 0) != (b > 0) else 0.0
        
        features["gamma_0dte_vs_wk"] = _sign_div(features.get("net_gamma", 0), features.get("wk_net_gamma", 0))
        features["vanna_0dte_vs_wk"] = _sign_div(features.get("net_vanna", 0), features.get("wk_net_vanna", 0))
        features["dgex_0dte_vs_wk"] = _sign_div(features.get("net_dgex", 0), features.get("wk_net_dgex", 0))
        features["delta_0dte_vs_wk"] = _sign_div(features.get("net_delta", 0), features.get("wk_net_delta", 0))
        features["vega_0dte_vs_wk"] = _sign_div(features.get("net_vega", 0), features.get("wk_net_vega", 0))
        features["vomma_0dte_vs_wk"] = _sign_div(features.get("net_vomma", 0), features.get("wk_net_vomma", 0))
        
        # IB levels
        if ib_data and "analysis" in ib_data:
            analysis = ib_data["analysis"]
            ib_high = analysis.get("ib_high", current_price)
            ib_low = analysis.get("ib_low", current_price)
            ib_range = ib_high - ib_low if ib_high > ib_low else 1
            
            features["price_vs_ib_high"] = (current_price - ib_high) / current_price
            features["price_vs_ib_low"] = (current_price - ib_low) / current_price
            features["ib_range_pct"] = ib_range / current_price
            features["near_ib_high"] = 1 if abs(features["price_vs_ib_high"]) < 0.004 else 0
            features["near_ib_low"] = 1 if abs(features["price_vs_ib_low"]) < 0.004 else 0
            features["above_ib"] = 1 if current_price > ib_high else 0
            features["below_ib"] = 1 if current_price < ib_low else 0
            features["in_ib_range"] = 1 if ib_low <= current_price <= ib_high else 0
            
            # Fibonacci
            fib_127 = ib_high + (ib_range * 0.272)
            fib_161 = ib_high + (ib_range * 0.618)
            features["dist_fib_127_up"] = (current_price - fib_127) / current_price
            features["dist_fib_161_up"] = (current_price - fib_161) / current_price
            
            # Extended Fibonacci (bullish + bearish)
            fib_200_up = ib_high + (ib_range * 1.0)
            fib_127_dn = ib_low - (ib_range * 0.272)
            fib_161_dn = ib_low - (ib_range * 0.618)
            fib_200_dn = ib_low - (ib_range * 1.0)
            features["dist_fib_200_up"] = (current_price - fib_200_up) / current_price
            features["dist_fib_127_dn"] = (current_price - fib_127_dn) / current_price
            features["dist_fib_161_dn"] = (current_price - fib_161_dn) / current_price
            features["dist_fib_200_dn"] = (current_price - fib_200_dn) / current_price
            
            # RBF Confluences
            def _rbf(a, b, sigma=0.05):
                if current_price == 0 or a is None or b is None or a == 0 or b == 0:
                    return 0.0
                d = abs(a - b) / current_price
                v = np.exp(-d**2 / (2 * sigma**2))
                return float(np.clip(v, 0.0, 1.0)) if np.isfinite(v) else 0.0
            
            max_gamma_s = features.get("_max_gamma_strike", max_gamma_strike if 'max_gamma_strike' in dir() else current_price)
            min_gamma_s = features.get("_min_gamma_strike", min_gamma_strike if 'min_gamma_strike' in dir() else current_price)
            
            # IB × Greek confluences
            features["confluence_ib_high_max_gamma"] = _rbf(ib_high, max_gamma_s)
            features["confluence_ib_low_min_gamma"] = _rbf(ib_low, min_gamma_s)
            features["confluence_ib_high_max_vega"] = _rbf(ib_high, max_vega_strike)
            features["confluence_ib_low_max_dgex"] = _rbf(ib_low, max_dgex_strike if 'max_dgex_strike' in dir() else current_price)
            # Fib × Greek confluences
            features["confluence_fib127_bull_max_gamma"] = _rbf(fib_127, max_gamma_s)
            features["confluence_fib161_bull_max_vega"] = _rbf(fib_161, max_vega_strike)
            features["confluence_fib127_bear_min_gamma"] = _rbf(fib_127_dn, min_gamma_s)
        
        # IV/VIX features (defaults if not available from wrapper's regime filter)
        features["atm_iv"] = 0.2  # Default 20%
        features["iv_zscore"] = 0
        features["iv_percentile"] = 0.5
        features["vix_spot"] = 0.4  # 20/50 normalized
        features["vix_gamma"] = 0
        features["vix_regime"] = 0.5
        
        # Defaults
        features["rsi"] = 0.5
        features["vol_relative"] = 0.2

        # --- ENGINEERED FEATURES ---
        # 1. Ratios
        epsilon = 1e-6
        features["gamma_vanna_ratio"] = features["net_gamma"] / (abs(features["net_vanna"]) + epsilon)
        features["dgex_gamma_ratio"] = features["net_dgex"] / (abs(features["net_gamma"]) + epsilon)
        features["charm_vanna_ratio"] = features["net_charm"] / (abs(features["net_vanna"]) + epsilon)
        features["delta_gamma_ratio"] = features.get("net_delta", 0) / (abs(features["net_gamma"]) + epsilon)
        features["vega_gamma_ratio"] = features.get("net_vega", 0) / (abs(features["net_gamma"]) + epsilon)
        features["vomma_vega_ratio"] = features.get("net_vomma", 0) / (abs(features.get("net_vega", 0)) + epsilon)

        # 2. Temporal Deltas
        prev = self.prev_features.get(ticker)
        
        if prev:
            features["gamma_change"] = features["net_gamma"] - prev["net_gamma"]
            features["vanna_change"] = features["net_vanna"] - prev["net_vanna"]
            features["dgex_change"] = features["net_dgex"] - prev["net_dgex"]
            features["delta_change"] = features.get("net_delta", 0) - prev.get("net_delta", 0)
            features["spot_change"] = (current_price - prev["spot"]) / prev["spot"] if prev["spot"] > 0 else 0.0
            
            # Cross-Features
            features["gamma_momentum"] = features["gamma_change"] * np.sign(features["net_gamma"])
            features["price_vs_dgex_magnet"] = features["spot_change"] * np.sign((current_price - features.get("max_dgex_strike", current_price))/current_price) if current_price > 0 else 0.0
            # Vega/Vomma temporal deltas
            features["vega_change"] = features.get("net_vega", 0) - prev.get("net_vega", 0)
            features["vomma_change"] = features.get("net_vomma", 0) - prev.get("net_vomma", 0)
        else:
            # First run: no change
            features["gamma_change"] = 0.0
            features["vanna_change"] = 0.0
            features["dgex_change"] = 0.0
            features["delta_change"] = 0.0
            features["spot_change"] = 0.0
            features["gamma_momentum"] = 0.0
            features["price_vs_dgex_magnet"] = 0.0
            features["vega_change"] = 0.0
            features["vomma_change"] = 0.0

        # Update cache
        self.prev_features[ticker] = {
            "spot": current_price,
            "net_gamma": features["net_gamma"],
            "net_vanna": features["net_vanna"],
            "net_dgex": features["net_dgex"],
            "net_delta": features.get("net_delta", 0),
            "net_vega": features.get("net_vega", 0),
            "net_vomma": features.get("net_vomma", 0),
        }
        
        # Build feature vector
        feature_vector = []
        for col in FEATURE_COLUMNS:
            feature_vector.append(features.get(col, 0.0))
        
        return np.array(feature_vector, dtype=np.float32)
    
    def process_ticker(self, ticker: str):
        """Process a single ticker."""
        # Get data
        greek_ticker = FUTURES_GREEKS_MAPPING.get(ticker, ticker)
        greek_data = self.get_latest_greek_data(greek_ticker)
        ib_data = self.get_ib_data(ticker)
        
        if not greek_data:
            return
        
        # Extract features (0DTE + weekly)
        weekly_data = self.get_latest_weekly_data(greek_ticker)
        features = self.extract_features(greek_data, ib_data, ticker, weekly_data=weekly_data)
        if features is None:
            return
        
        current_price = greek_data.get("spot", greek_data.get("spot_price", 0))
        
        # Check if we have an open position
        if ticker in self.positions:
            self._manage_position(ticker, current_price)
        else:
            # Get signal from wrapper
            signal = self.wrapper.get_signal(ticker, features, current_price)
            
            if signal.direction != "HOLD" and signal.position_size > 0:
                # Check Cooldown
                last_time = self.last_trade_time.get(ticker)
                if last_time:
                    elapsed = (datetime.now() - last_time).total_seconds() / 60
                    if elapsed < TRADE_COOLDOWN_MINUTES:
                        logger.debug(f"Skipping {ticker} trade (Cooldown: {elapsed:.0f}/{TRADE_COOLDOWN_MINUTES}m)")
                        return

                # OVERRIDE WRAPPER STOPS WITH ASYMMETRIC TARGETS
                target_pct = TARGET_LONG_PCT if signal.direction == "LONG" else TARGET_SHORT_PCT
                
                if signal.direction == "LONG":
                    signal.take_profit_1 = signal.entry_price * (1 + target_pct)
                    signal.take_profit_2 = signal.entry_price * (1 + target_pct * 1.5)  # Extended target
                else:  # SHORT
                    signal.take_profit_1 = signal.entry_price * (1 - target_pct)
                    signal.take_profit_2 = signal.entry_price * (1 - target_pct * 1.5)

                self._open_position(signal)
    
    def _open_position(self, signal: TradeSignal):
        """Open a new position based on wrapper signal and capture entry market conditions."""
        position = Position(signal)
        
        # Capture Greek snapshots at entry for post-analysis
        greek_ticker = FUTURES_GREEKS_MAPPING.get(signal.ticker, signal.ticker)
        greek_data = self.get_latest_greek_data(greek_ticker)
        weekly_data = self.get_latest_weekly_data(greek_ticker)
        ib_data = self.get_ib_data(signal.ticker)
        
        # Store 0DTE Greek snapshot
        if greek_data:
            position.entry_greeks = {
                "net_gamma": sum(greek_data.get("totalgamma", {}).get("all", [])),
                "net_vanna": sum(greek_data.get("totalvanna", {}).get("all", [])),
                "net_charm": sum(greek_data.get("totalcharm", {}).get("all", [])),
                "net_dgex": sum(greek_data.get("totaldgex", {}).get("all", [])),
                "net_zomma": sum(greek_data.get("totalzomma", {}).get("all", [])),
                "net_delta": sum(greek_data.get("totaldelta", {}).get("all", [])),
                "zero_gamma": greek_data.get("zerogamma", 0),
                "zero_delta": greek_data.get("zerodelta", 0),
            }
            
            # Add weekly Greeks
            if weekly_data:
                position.entry_greeks["wk_net_gamma"] = sum(weekly_data.get("totalgamma", {}).get("all", []))
                position.entry_greeks["wk_net_vanna"] = sum(weekly_data.get("totalvanna", {}).get("all", []))
                position.entry_greeks["wk_net_dgex"] = sum(weekly_data.get("totaldgex", {}).get("all", []))
        
        # Store IB context
        if ib_data and "analysis" in ib_data:
            analysis = ib_data["analysis"]
            position.entry_ib_context = {
                "ib_high": analysis.get("ib_high", 0),
                "ib_low": analysis.get("ib_low", 0),
                "ib_range_pct": ((analysis.get("ib_high", 0) - analysis.get("ib_low", 0)) / signal.entry_price * 100) if signal.entry_price > 0 else 0,
                "above_ib": signal.entry_price > analysis.get("ib_high", 0),
                "below_ib": signal.entry_price < analysis.get("ib_low", 0),
                "in_ib_range": analysis.get("ib_low", 0) <= signal.entry_price <= analysis.get("ib_high", 0),
            }
        
        self.positions[signal.ticker] = position
        
        target_pct = TARGET_LONG_PCT if signal.direction == "LONG" else TARGET_SHORT_PCT
        
        logger.info(f"[OPEN] {signal.ticker} {signal.direction}")
        logger.info(f"  Price: {signal.entry_price:.2f}")
        logger.info(f"  Confidence: {signal.raw_confidence:.1%} → {signal.calibrated_confidence:.1%}")
        logger.info(f"  Size: {signal.position_size:.1%}")
        logger.info(f"  Regime: {signal.regime.value}")
        logger.info(f"  ASYMMETRIC Target: {target_pct:.1%}")
        logger.info(f"  Stop: {signal.stop_loss:.2f} | TP1: {signal.take_profit_1:.2f} | TP2: {signal.take_profit_2:.2f}")
        logger.info(f"  Bayesian: μ={signal.time_mu_minutes:.1f}m, σ={signal.time_sigma_minutes:.1f}m")
        
        # Send Discord notification
        send_discord_trade_open(signal)
        
        self.daily_stats["trades"] += 1
        
        # PERSIST TO DISK (critical for restart recovery)
        self._save_open_positions()
    
    def _manage_position(self, ticker: str, current_price: float):
        """Manage an open position with real-time Bayesian uncertainty and tracking."""
        position = self.positions[ticker]
        
        # Track price update
        position.add_price_update(current_price)
        
        # --- Real-time Bayesian inference ---
        current_uncertainty_mins = None
        try:
            greek_ticker = FUTURES_GREEKS_MAPPING.get(ticker, ticker)
            greek_data = self.get_latest_greek_data(greek_ticker)
            ib_data = self.get_ib_data(ticker)
            
            if greek_data is not None:
                weekly_data = self.get_latest_weekly_data(greek_ticker)
                features = self.extract_features(greek_data, ib_data, ticker, weekly_data=weekly_data)
                if features is not None:
                    features_norm = self.wrapper.normalizer.transform(features.reshape(1, -1))
                    x = torch.FloatTensor(features_norm).to(self.device)
                    
                    self.model.eval()
                    with torch.no_grad():
                        _, time_pred = self.model.predict(x)
                        log_sigma = time_pred.cpu().numpy()[0][1]
                        current_uncertainty_mins = float(np.exp(log_sigma) * 120.0)
                    
                    if current_uncertainty_mins > MAX_UNCERTAINTY_MINUTES:
                        logger.info(f"  {ticker} HIGH UNCERTAINTY: σ={current_uncertainty_mins:.1f}m > {MAX_UNCERTAINTY_MINUTES}m threshold")
        except Exception as e:
            logger.debug(f"  {ticker} Live inference failed (using fallback): {e}")
        
        # Update trailing stop and check exit (with Bayesian uncertainty)
        old_stop = position.current_stop
        new_stop, should_exit, exit_reason = self.wrapper.update_position(
            ticker=ticker,
            entry_price=position.entry_price,
            entry_time=position.entry_time,
            current_price=current_price,
            current_stop=position.current_stop,
            direction=position.direction,
            max_hold_minutes=position.max_hold_time,
            current_uncertainty_mins=current_uncertainty_mins,
        )
        
        # Track if position state changed (needs save)
        state_changed = False
        
        # Update stop and track change
        if new_stop != old_stop:
            logger.debug(f"  {ticker} Stop updated: {old_stop:.2f} → {new_stop:.2f}")
            position.current_stop = new_stop
            position.add_stop_update(old_stop, new_stop)
            state_changed = True
        
        # Check take profit 1 (partial exit)
        if not position.partial_exit_done:
            if position.direction == "LONG" and current_price >= position.take_profit_1:
                logger.info(f"  {ticker} TP1 ({TARGET_LONG_PCT:.1%}) hit - partial exit")
                position.partial_exit_done = True
                position.position_size *= 0.5  # Exit half
                state_changed = True
            elif position.direction == "SHORT" and current_price <= position.take_profit_1:
                logger.info(f"  {ticker} TP1 ({TARGET_SHORT_PCT:.1%}) hit - partial exit")
                position.partial_exit_done = True
                position.position_size *= 0.5
                state_changed = True
        
        # Save position state if changed
        if state_changed:
            self._save_open_positions()
        
        # Check full exit
        if should_exit:
            self._close_position(ticker, current_price, exit_reason)
        elif position.direction == "LONG" and current_price >= position.take_profit_2:
            self._close_position(ticker, current_price, "TAKE_PROFIT_2")
        elif position.direction == "SHORT" and current_price <= position.take_profit_2:
            self._close_position(ticker, current_price, "TAKE_PROFIT_2")
    
    def _close_position(self, ticker: str, current_price: float, reason: str):
        """Close a position and record comprehensive P&L and analytics."""
        position = self.positions[ticker]
        exit_time = datetime.now()
        
        # Calculate P&L
        if position.direction == "LONG":
            pnl_pct = (current_price - position.entry_price) / position.entry_price
        else:
            pnl_pct = (position.entry_price - current_price) / position.entry_price
        
        point_value = POINT_VALUES.get(ticker, 100)
        pnl_dollars = pnl_pct * position.entry_price * point_value
        
        # Calculate trade duration
        hold_time_minutes = (exit_time - position.entry_time).total_seconds() / 60
        
        # Capture EXIT Greek snapshots for comparison
        exit_greeks = {}
        greek_ticker = FUTURES_GREEKS_MAPPING.get(ticker, ticker)
        greek_data = self.get_latest_greek_data(greek_ticker)
        if greek_data:
            exit_greeks = {
                "net_gamma": sum(greek_data.get("totalgamma", {}).get("all", [])),
                "net_vanna": sum(greek_data.get("totalvanna", {}).get("all", [])),
                "net_dgex": sum(greek_data.get("totaldgex", {}).get("all", [])),
            }
        
        # Calculate max favorable excursion (MFE) and max adverse excursion (MAE)
        mfe = 0.0  # Max profit during trade
        mae = 0.0  # Max loss during trade
        if position.price_history:
            for update in position.price_history:
                price = update["price"]
                if position.direction == "LONG":
                    move_pct = (price - position.entry_price) / position.entry_price
                else:
                    move_pct = (position.entry_price - price) / position.entry_price
                mfe = max(mfe, move_pct)
                mae = min(mae, move_pct)
        
        # Update stats
        if pnl_pct > 0:
            self.daily_stats["wins"] += 1
        else:
            self.daily_stats["losses"] += 1
        self.daily_stats["pnl"] += pnl_dollars
        
        target_pct = TARGET_LONG_PCT if position.direction == "LONG" else TARGET_SHORT_PCT
        
        logger.info(f"[CLOSE] {ticker} {position.direction} | {reason}")
        logger.info(f"  Entry: {position.entry_price:.2f} → Exit: {current_price:.2f}")
        logger.info(f"  Target: {target_pct:.1%} | Stop: {STOP_LOSS_PCT:.1%}")
        logger.info(f"  P&L: {pnl_pct:+.2%} (${pnl_dollars:+.2f})")
        logger.info(f"  Hold time: {hold_time_minutes:.1f} min | MFE: {mfe:.2%} | MAE: {mae:.2%}")
        
        # === BUILD COMPREHENSIVE TRADE RECORD ===
        trade_record = {
            # All position data (entry context, Greeks, IB, etc.)
            **position.to_dict(),
            
            # === EXIT DATA ===
            "exit_price": current_price,
            "exit_time": exit_time.isoformat(),
            "exit_reason": reason,
            "exit_greeks": exit_greeks,
            
            # === P&L METRICS ===
            "pnl_pct": pnl_pct,
            "pnl_dollars": pnl_dollars,
            "point_value": point_value,
            
            # === TIMING METRICS ===
            "hold_time_minutes": hold_time_minutes,
            "predicted_time_minutes": position.time_mu_minutes,
            "time_prediction_error_minutes": hold_time_minutes - position.time_mu_minutes,
            
            # === RISK METRICS ===
            "max_favorable_excursion_pct": mfe,  # How far it went in our favor
            "max_adverse_excursion_pct": mae,    # How far it went against us
            "risk_reward_ratio": abs(target_pct / STOP_LOSS_PCT),
            
            # === TRADE QUALITY METRICS ===
            "hit_target": "TARGET" in reason or "PROFIT" in reason,
            "hit_stop": "STOP" in reason,
            "partial_exit_executed": position.partial_exit_done,
            "num_stop_updates": len(position.stop_updates),
            "num_price_updates": len(position.price_history),
            
            # === CONFIGURATION (for analysis) ===
            "config": {
                "threshold": MIN_CONFIDENCE,
                "target_long_pct": TARGET_LONG_PCT,
                "target_short_pct": TARGET_SHORT_PCT,
                "stop_loss_pct": STOP_LOSS_PCT,
                "max_uncertainty_minutes": MAX_UNCERTAINTY_MINUTES,
                "cooldown_minutes": TRADE_COOLDOWN_MINUTES,
            }
        }
        
        self.trade_history.append(trade_record)
        
        # Send Discord notification
        send_discord_trade_close(position, current_price, reason, pnl_pct, pnl_dollars)
        
        # Remove from active positions
        del self.positions[ticker]
        self.last_trade_time[ticker] = datetime.now()
        
        # PERSIST STATE: Save remaining positions and trade history
        self._save_open_positions()  # Update disk (position now removed)
        self._save_trade_history()
    
    def _save_trade_history(self):
        """Save comprehensive trade history to organized JSON files."""
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Create dated subfolder for organization
        dated_folder = os.path.join(TRADES_DIR, today.replace("-", ""))
        os.makedirs(dated_folder, exist_ok=True)
        
        # Save full trade history with all details
        trades_file = os.path.join(dated_folder, f"trades_full_{today}.json")
        
        # Calculate summary stats
        if self.trade_history:
            wins = [t for t in self.trade_history if t["pnl_pct"] > 0]
            losses = [t for t in self.trade_history if t["pnl_pct"] < 0]
            
            summary = {
                "date": today,
                "total_trades": len(self.trade_history),
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": len(wins) / len(self.trade_history) if self.trade_history else 0,
                "total_pnl_dollars": sum(t["pnl_dollars"] for t in self.trade_history),
                "avg_win_pct": sum(t["pnl_pct"] for t in wins) / len(wins) if wins else 0,
                "avg_loss_pct": sum(t["pnl_pct"] for t in losses) / len(losses) if losses else 0,
                "avg_hold_time_minutes": sum(t["hold_time_minutes"] for t in self.trade_history) / len(self.trade_history),
                "by_ticker": {},
                "by_direction": {"LONG": {"count": 0, "wins": 0, "pnl": 0}, "SHORT": {"count": 0, "wins": 0, "pnl": 0}},
            }
            
            # Aggregate by ticker
            for trade in self.trade_history:
                ticker = trade["ticker"]
                direction = trade["direction"]
                
                if ticker not in summary["by_ticker"]:
                    summary["by_ticker"][ticker] = {"count": 0, "wins": 0, "losses": 0, "pnl": 0}
                
                summary["by_ticker"][ticker]["count"] += 1
                summary["by_ticker"][ticker]["pnl"] += trade["pnl_dollars"]
                
                if trade["pnl_pct"] > 0:
                    summary["by_ticker"][ticker]["wins"] += 1
                else:
                    summary["by_ticker"][ticker]["losses"] += 1
                
                # By direction
                summary["by_direction"][direction]["count"] += 1
                summary["by_direction"][direction]["pnl"] += trade["pnl_dollars"]
                if trade["pnl_pct"] > 0:
                    summary["by_direction"][direction]["wins"] += 1
            
            # Calculate win rates
            for ticker_stats in summary["by_ticker"].values():
                if ticker_stats["count"] > 0:
                    ticker_stats["win_rate"] = ticker_stats["wins"] / ticker_stats["count"]
            
            for dir_stats in summary["by_direction"].values():
                if dir_stats["count"] > 0:
                    dir_stats["win_rate"] = dir_stats["wins"] / dir_stats["count"]
        else:
            summary = {"date": today, "total_trades": 0}
        
        # Save comprehensive data
        data_to_save = {
            "summary": summary,
            "trades": self.trade_history,
            "generated_at": datetime.now().isoformat(),
            "bot_version": "v2.0_optimized",
        }
        
        with open(trades_file, 'w') as f:
            json.dump(data_to_save, f, indent=2)
        
        # Also save summary separately for quick reference
        summary_file = os.path.join(dated_folder, f"summary_{today}.json")
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.debug(f"Trade history saved: {trades_file}")

    def is_market_day(self) -> bool:
        """Check if today is a trading day (NYSE calendar)."""
        ny_tz = pytz.timezone('America/New_York')
        now_ny = datetime.now(ny_tz)

        # Weekend check
        if now_ny.weekday() >= 5:
            return False

        # Holiday check
        nyse = mcal.get_calendar('NYSE')
        schedule = nyse.schedule(start_date=now_ny.date(), end_date=now_ny.date())

        if schedule.empty:
            return False

        return True
    
    def is_trading_hours(self) -> tuple[bool, str]:
        """
        Check if current time is within trading hours (8:00 AM - 4:30 PM EST).
        
        Returns:
            (bool, str): (is_tradeable, reason)
        """
        ny_tz = pytz.timezone('America/New_York')
        now_ny = datetime.now(ny_tz)
        
        current_time = now_ny.time()
        
        # Trading hours: 8:00 AM - 4:30 PM EST
        start_time = dt_time(8, 0)   # 8:00 AM
        end_time = dt_time(16, 30)   # 4:30 PM
        
        if current_time < start_time:
            minutes_until_open = ((datetime.combine(now_ny.date(), start_time) - 
                                   datetime.combine(now_ny.date(), current_time)).total_seconds() / 60)
            return False, f"Pre-market: {minutes_until_open:.0f} min until 8:00 AM EST"
        
        if current_time > end_time:
            return False, "After-hours: Market closed at 4:30 PM EST"
        
        return True, "Trading hours active"
    
    def run(self):
        """Main trading loop."""
        logger.info("=" * 70)
        logger.info("OPTIMIZED TRADING BOT STARTED (v2.0)")
        logger.info("=" * 70)
        logger.info(f"Configuration:")
        logger.info(f"  • Tickers: {', '.join(TICKERS + FUTURES_TO_TRACK)}")
        logger.info(f"  • Threshold: {MIN_CONFIDENCE:.0%}")
        logger.info(f"  • Trading Hours: 8:00 AM - 4:30 PM EST")
        logger.info(f"  • ASYMMETRIC Targets:")
        logger.info(f"    - LONG: {TARGET_LONG_PCT:.1%} (backtest: 83.2% WR)")
        logger.info(f"    - SHORT: {TARGET_SHORT_PCT:.1%} (backtest: 60.9% WR)")
        logger.info(f"  • Stop Loss: {STOP_LOSS_PCT:.1%}")
        logger.info(f"  • Bayesian Exit: sigma > {MAX_UNCERTAINTY_MINUTES}min")
        logger.info(f"  • Cooldown: {TRADE_COOLDOWN_MINUTES}min")
        logger.info(f"  • Loop Interval: {LOOP_INTERVAL}s")
        logger.info("=" * 70)
        
        last_hours_log = None
        
        while True:
            try:
                # Check if market day
                if not self.is_market_day():
                    logger.info("Market closed (Weekend/Holiday). Pausing for 1 hour...")
                    time.sleep(3600)
                    continue
                
                # Check trading hours
                in_hours, hours_reason = self.is_trading_hours()
                
                # Log hours status change (only once per status change)
                if hours_reason != last_hours_log:
                    logger.info(f"Trading Hours Status: {hours_reason}")
                    last_hours_log = hours_reason
                
                if not in_hours:
                    # Close all positions at end of day (4:30 PM)
                    if "After-hours" in hours_reason and self.positions:
                        logger.info("End of trading day - closing all positions")
                        for ticker in list(self.positions.keys()):
                            greek_ticker = FUTURES_GREEKS_MAPPING.get(ticker, ticker)
                            greek_data = self.get_latest_greek_data(greek_ticker)
                            if greek_data:
                                current_price = greek_data.get("spot", greek_data.get("spot_price", 0))
                                if current_price > 0:
                                    self._close_position(ticker, current_price, "EOD_CLOSE")
                    
                    # Sleep longer outside trading hours
                    time.sleep(60)
                    continue
                
                # Process all tickers (only during trading hours)
                for ticker in TICKERS + FUTURES_TO_TRACK:
                    self.process_ticker(ticker)
                
                # Log daily stats periodically
                if self.daily_stats["trades"] > 0:
                    wins = self.daily_stats["wins"]
                    losses = self.daily_stats["losses"]
                    win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0
                    logger.debug(f"Daily Stats: {self.daily_stats['trades']} trades, "
                                f"WR {win_rate:.1%}, P&L ${self.daily_stats['pnl']:.2f}")
                
                time.sleep(LOOP_INTERVAL)
                
            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(10)


if __name__ == "__main__":
    bot = TradingBotWrapper()
    bot.run()