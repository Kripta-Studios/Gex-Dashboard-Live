"""
Trading Bot with Wrapper Integration

Uses the TradingWrapper to make smarter decisions:
- Checks market regime before trading
- Calibrates model confidence
- Sizes positions based on Kelly criterion
- Manages trailing stops dynamically

This replaces the simpler tradingbot_pytorch.py logic.

Usage:
    python tradingbot_wrapper.py
"""

import os
import sys
import json
import time
import requests
import logging
from datetime import datetime, timedelta
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

from hybrid_model import load_hybrid_model, get_device, FEATURE_COLUMNS
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

# Create directories
os.makedirs(TRADES_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# Trading parameters
MIN_CONFIDENCE = 0.80  # Golden Config: 0.8 (from backtest)
BASE_RISK_PCT = 0.01   # 1% base risk per trade
MAX_POSITION_PCT = 0.05  # 5% maximum position size
LOOP_INTERVAL = 30  # seconds

# Filters
MIN_IV_PCT = 0.00  # Avoid chop (Golden Config: 0.0)
MAX_TIME_MINUTES = 120 # Avoid slow moves (Golden Config: 120)
STOP_LOSS_PCT = 0.003 # 0.3% stop loss (from backtest)
TRADE_COOLDOWN_MINUTES = 60 # Cooldown between trades (from backtest)

# Discord Configuration (same as tradingbot1.py)
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
DISCORD_ROLE_PING = "<@&1464601287411634226>"
DISCORD_ENABLED = True

# Tickers
TICKERS = [
    "SPX", "SPY", "QQQ", "IWM", "VIX",
    "AAPL", "NVDA", "TSLA", "AMD", "MSFT", "AMZN", "META", "GOOGL",
]
FUTURES_TO_TRACK = ["/ES", "/NQ"]
FUTURES_GREEKS_MAPPING = {"/ES": "SPX", "/NQ": "QQQ"}

# Point values for P&L calculation
POINT_VALUES = {
    "SPX": 10.0, "SPY": 100.0, "QQQ": 100.0, "IWM": 100.0, "VIX": 100.0,
    "AAPL": 100.0, "NVDA": 100.0, "TSLA": 100.0, "AMD": 100.0,
    "MSFT": 100.0, "AMZN": 100.0, "META": 100.0, "GOOGL": 100.0,
    "/ES": 50.0, "/NQ": 20.0,
}

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, "tradingbot_wrapper.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# DISCORD NOTIFICATIONS
# =============================================================================

def send_discord_trade_open(signal, timestamp=None):
    """Sends trade OPEN notification to Discord."""
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
    
    reason_text = "\n".join(reason_parts)
    
    color = 0x2ECC71 if direction == "LONG" else 0xE74C3C
    emoji = "📈" if direction == "LONG" else "📉"
    
    embed = {
        "title": f"{emoji} ML BOT {direction} OPENED - {ticker}",
        "description": f"**{DISCORD_ROLE_PING}**\n\n**🤖 ML Reasoning:**\n{reason_text}",
        "color": color,
        "fields": [
            {"name": "🕒 Open Time", "value": f"{date_str} {time_str}", "inline": True},
            {"name": "💵 Entry Price", "value": f"${entry_price:.2f}", "inline": True},
            {"name": "📊 Point Value", "value": f"${point_value:.0f}/pt", "inline": True},
            {"name": "🎯 TP1", "value": f"${signal.take_profit_1:.2f}", "inline": True},
            {"name": "🎯 TP2", "value": f"${signal.take_profit_2:.2f}", "inline": True},
            {"name": "🛑 Stop Loss", "value": f"${signal.stop_loss:.2f}", "inline": True},
            {"name": "⏱️ Max Hold", "value": f"{signal.max_hold_time} min", "inline": True},
            {"name": "💰 Risk/Reward", "value": f"Risk: ${risk_dollars:.2f} | Reward: ${reward_dollars:.2f}" if risk_dollars > 0 else "N/A", "inline": False},
        ],
        "footer": {"text": "TradingBotWrapper | ML Bot | LIVE"}
    }
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json={"content": f"{DISCORD_ROLE_PING} ML Trade", "embeds": [embed]}, timeout=5)
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
        exit_explanation = "🌫️ **High Uncertainty** - Bayesian σ exceeded threshold"
    elif "CLOSE" in reason.upper() or "EOD" in reason.upper():
        exit_explanation = "🔔 **End of Day** - Forced exit before market close"
    else:
        exit_explanation = f"📋 **{reason}**"
    
    color = 0x2ECC71 if pnl_pct >= 0 else 0xE74C3C
    emoji = "✅" if pnl_pct >= 0 else "❌"
    result = "PROFIT" if pnl_pct >= 0 else "LOSS"
    
    price_move = exit_price - entry_price
    price_move_pct = (price_move / entry_price) * 100 if entry_price > 0 else 0
    
    embed = {
        "title": f"{emoji} ML BOT {direction} CLOSED - {ticker} ({result})",
        "description": f"**{DISCORD_ROLE_PING}**\n\n{exit_explanation}",
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
        "footer": {"text": "TradingBotWrapper | ML Bot | LIVE"}
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
    """Tracks an open position."""
    
    def __init__(self, signal: TradeSignal):
        self.ticker = signal.ticker
        self.direction = signal.direction
        self.entry_price = signal.entry_price
        self.entry_time = datetime.now()
        self.position_size = signal.position_size
        self.calibrated_confidence = signal.calibrated_confidence
        self.current_stop = signal.stop_loss
        self.take_profit_1 = signal.take_profit_1
        self.take_profit_2 = signal.take_profit_2
        self.max_hold_time = signal.max_hold_time
        self.regime = signal.regime
        self.partial_exit_done = False
        # Bayesian uncertainty from initial signal
        self.time_mu_minutes = signal.time_mu_minutes
        self.time_sigma_minutes = signal.time_sigma_minutes
    
    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time.isoformat(),
            "position_size": self.position_size,
            "calibrated_confidence": self.calibrated_confidence,
            "current_stop": self.current_stop,
            "take_profit_1": self.take_profit_1,
            "take_profit_2": self.take_profit_2,
            "regime": self.regime.value,
        }


class TradingBotWrapper:
    """Trading bot using the intelligent wrapper."""
    
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
    
    def _load_model(self):
        """Load model and initialize wrapper."""
        if not os.path.exists(MODEL_PATH):
            logger.error(f"Model not found: {MODEL_PATH}")
            logger.info("Run train_hybrid.py or train_walkforward.py first")
            raise FileNotFoundError(MODEL_PATH)
        
        self.model, self.normalizer = load_hybrid_model(
            MODEL_PATH, NORMALIZER_PATH, 
            model_size="small", device=self.device
        )
        
        # Initialize wrapper
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
        
        logger.info("Model and wrapper loaded successfully")
    
    def get_latest_greek_data(self, ticker: str) -> dict:
        """Find and load the most recent Greek data JSON."""
        # /ES -> ES
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
        
        # 0DTE Greek exposures (6 greeks)
        for greek in ["totalgamma", "totalvanna", "totalcharm", "totaldgex", "totalzomma", "totaldelta"]:
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
        
        # ===== WEEKLY GREEKS =====
        if weekly_data:
            for greek in ["totalgamma", "totalvanna", "totalcharm", "totaldgex", "totalzomma", "totaldelta"]:
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
        
        # ===== CROSS-EXPIRY DIVERGENCE =====
        def _sign_div(a, b):
            if abs(a) < 0.01 or abs(b) < 0.01:
                return 0.5
            return 1.0 if (a > 0) != (b > 0) else 0.0
        
        features["gamma_0dte_vs_wk"] = _sign_div(features.get("net_gamma", 0), features.get("wk_net_gamma", 0))
        features["vanna_0dte_vs_wk"] = _sign_div(features.get("net_vanna", 0), features.get("wk_net_vanna", 0))
        features["dgex_0dte_vs_wk"] = _sign_div(features.get("net_dgex", 0), features.get("wk_net_dgex", 0))
        features["delta_0dte_vs_wk"] = _sign_div(features.get("net_delta", 0), features.get("wk_net_delta", 0))
        
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
        else:
            # First run: no change
            features["gamma_change"] = 0.0
            features["vanna_change"] = 0.0
            features["dgex_change"] = 0.0
            features["delta_change"] = 0.0
            features["spot_change"] = 0.0
            features["gamma_momentum"] = 0.0
            features["price_vs_dgex_magnet"] = 0.0

        # Update cache
        self.prev_features[ticker] = {
            "spot": current_price,
            "net_gamma": features["net_gamma"],
            "net_vanna": features["net_vanna"],
            "net_dgex": features["net_dgex"],
            "net_delta": features.get("net_delta", 0)
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
            # Load weekly data for feature extraction
            weekly_ticker = FUTURES_GREEKS_MAPPING.get(ticker, ticker)
            weekly_data = self.get_latest_weekly_data(weekly_ticker)
            
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

                self._open_position(signal)
    
    def _open_position(self, signal: TradeSignal):
        """Open a new position based on wrapper signal."""
        position = Position(signal)
        self.positions[signal.ticker] = position
        
        logger.info(f"[OPEN] {signal.ticker} {signal.direction}")
        logger.info(f"  Price: {signal.entry_price:.2f}")
        logger.info(f"  Confidence: {signal.raw_confidence:.1%} → {signal.calibrated_confidence:.1%}")
        logger.info(f"  Size: {signal.position_size:.1%}")
        logger.info(f"  Regime: {signal.regime.value}")
        logger.info(f"  Stop: {signal.stop_loss:.2f} | TP1: {signal.take_profit_1:.2f} | TP2: {signal.take_profit_2:.2f}")
        
        # Send Discord notification
        send_discord_trade_open(signal)
        
        self.daily_stats["trades"] += 1
    
    def _manage_position(self, ticker: str, current_price: float):
        """Manage an open position with real-time Bayesian uncertainty."""
        position = self.positions[ticker]
        
        # --- Real-time Bayesian inference ---
        # Re-run model on current features to get live σ (uncertainty)
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
                    
                    logger.debug(f"  {ticker} Live σ = {current_uncertainty_mins:.1f} min")
        except Exception as e:
            logger.debug(f"  {ticker} Live inference failed (using fallback): {e}")
        
        # Update trailing stop and check exit (with Bayesian uncertainty)
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
        
        # Update stop
        if new_stop != position.current_stop:
            logger.debug(f"  {ticker} Stop updated: {position.current_stop:.2f} → {new_stop:.2f}")
            position.current_stop = new_stop
        
        # Check take profit 1 (partial exit)
        if not position.partial_exit_done:
            if position.direction == "LONG" and current_price >= position.take_profit_1:
                logger.info(f"  {ticker} TP1 hit - partial exit")
                position.partial_exit_done = True
                position.position_size *= 0.5  # Exit half
            elif position.direction == "SHORT" and current_price <= position.take_profit_1:
                logger.info(f"  {ticker} TP1 hit - partial exit")
                position.partial_exit_done = True
                position.position_size *= 0.5
        
        # Check full exit
        if should_exit:
            self._close_position(ticker, current_price, exit_reason)
        elif position.direction == "LONG" and current_price >= position.take_profit_2:
            self._close_position(ticker, current_price, "TAKE_PROFIT_2")
        elif position.direction == "SHORT" and current_price <= position.take_profit_2:
            self._close_position(ticker, current_price, "TAKE_PROFIT_2")
    
    def _close_position(self, ticker: str, current_price: float, reason: str):
        """Close a position and record P&L."""
        position = self.positions[ticker]
        
        # Calculate P&L
        if position.direction == "LONG":
            pnl_pct = (current_price - position.entry_price) / position.entry_price
        else:
            pnl_pct = (position.entry_price - current_price) / position.entry_price
        
        point_value = POINT_VALUES.get(ticker, 100)
        pnl_dollars = pnl_pct * position.entry_price * point_value
        
        # Update stats
        if pnl_pct > 0:
            self.daily_stats["wins"] += 1
        else:
            self.daily_stats["losses"] += 1
        self.daily_stats["pnl"] += pnl_dollars
        
        logger.info(f"[CLOSE] {ticker} {position.direction} | {reason}")
        logger.info(f"  Entry: {position.entry_price:.2f} → Exit: {current_price:.2f}")
        logger.info(f"  P&L: {pnl_pct:+.2%} (${pnl_dollars:+.2f})")
        logger.info(f"  Hold time: {(datetime.now() - position.entry_time).total_seconds()/60:.1f} min")
        
        # Record trade
        trade_record = {
            **position.to_dict(),
            "exit_price": current_price,
            "exit_time": datetime.now().isoformat(),
            "exit_reason": reason,
            "pnl_pct": pnl_pct,
            "pnl_dollars": pnl_dollars,
        }
        self.trade_history.append(trade_record)
        
        # Send Discord notification
        send_discord_trade_close(position, current_price, reason, pnl_pct, pnl_dollars)
        
        del self.positions[ticker]
        self.last_trade_time[ticker] = datetime.now() # Start cooldown from CLOSE time
        self._save_trade_history()
    
    def _save_trade_history(self):
        """Save trade history to file."""
        today = datetime.now().strftime("%Y-%m-%d")
        filepath = os.path.join(TRADES_DIR, f"trades_{today}.json")
        
        with open(filepath, 'w') as f:
            json.dump(self.trade_history, f, indent=2)

    def is_market_day(self) -> bool:
        """Comprueba si hoy es fin de semana o festivo en el NYSE."""
        # Obtener la hora actual en Nueva York
        ny_tz = pytz.timezone('America/New_York')
        now_ny = datetime.now(ny_tz)

        # 1. Comprobar fines de semana (5 = Sábado, 6 = Domingo)
        if now_ny.weekday() >= 5:
            return False

        # 2. Comprobar calendario del NYSE (Festivos)
        nyse = mcal.get_calendar('NYSE')
        # Pedimos el calendario solo para el día de hoy
        schedule = nyse.schedule(start_date=now_ny.date(), end_date=now_ny.date())

        # Si el schedule está vacío, significa que el mercado está cerrado hoy (festivo)
        if schedule.empty:
            return False

        return True
    
    def run(self):
        """Main trading loop."""
        logger.info("=" * 60)
        logger.info("TRADING BOT WITH WRAPPER STARTED")
        logger.info("=" * 60)
        logger.info(f"Tickers: {', '.join(TICKERS + FUTURES_TO_TRACK)}")
        logger.info(f"Min confidence: {MIN_CONFIDENCE:.0%}")
        logger.info(f"Base risk: {BASE_RISK_PCT:.1%} | Max position: {MAX_POSITION_PCT:.1%}")
        logger.info(f"Loop interval: {LOOP_INTERVAL}s")
        
        while True:
            try:
                if not self.is_market_day():
                    logger.info("El mercado está cerrado (Fin de semana o Festivo NYSE). Pausando el bot por 1 hora...")
                    time.sleep(3600)  # Duerme 1 hora (3600 segundos) y vuelve a comprobar
                    continue
                # Process all tickers
                for ticker in TICKERS + FUTURES_TO_TRACK:
                    self.process_ticker(ticker)
                
                # Log daily stats periodically
                if self.daily_stats["trades"] > 0:
                    wins = self.daily_stats["wins"]
                    losses = self.daily_stats["losses"]
                    win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0
                    logger.debug(f"Daily: {self.daily_stats['trades']} trades, "
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
