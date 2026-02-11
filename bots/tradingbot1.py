"""
Real-Time Trading Bot 1 - Greek Exposure Strategy

This bot implements the same strategy as backtest.py but uses real-time data
from gex_daemon.py and ib_service.py.

Runs Monday-Friday from 9:20 AM to 4:20 PM New York time.

Usage: python tradingbot1.py
"""

import os
import json
import glob
import re
import requests
import asyncio
import time
from datetime import datetime, timedelta, time as dt_time, date
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import numpy as np
from dotenv import load_dotenv

try:
    from zoneinfo import ZoneInfo
    NY_TZ = ZoneInfo("America/New_York")
except:
    import pytz
    NY_TZ = pytz.timezone("America/New_York")

load_dotenv()

import logging

# Script directory for relative paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(SCRIPT_DIR, 'tradingbot1.log')),  # Archivo
        logging.StreamHandler()                   # Console
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

GREEK_DATA_DIR = "/home/Option-Greeks-Plotting-Discord-Bot/json_data"
IB_CHARTS_DIR = "/home/Option-Greeks-Plotting-Discord-Bot/ib_charts"  # Real-time from ib_service.py
IB_BACKTEST_DIR = "/home/Option-Greeks-Plotting-Discord-Bot/ib_backtest"  # Historical with volume_profile
TRADES_OUTPUT_DIR = os.path.join(SCRIPT_DIR, "trades_live")

STATE_FILE = os.path.join(SCRIPT_DIR, "state_bot1.json")
FORCE_EXIT_TIME = dt_time(15, 55)
LAST_ENTRY_TIME = dt_time(15, 50)

TICKERS = ["SPX", "SPY", "QQQ"]

# Trading hours (NYC)
MARKET_OPEN = dt_time(4, 20)
MARKET_CLOSE = dt_time(16, 20)
IB_FORMATION_END = dt_time(10, 30)

# Fibonacci extensions
FIB_EXTENSIONS = [0.272, 0.5, 0.618, 1.0, 1.272, 1.618, 2.0, 2.272]
FIB_EXTENSIONS_NEG = [-0.272, -0.5, -0.618, -1.0, -1.272]

# Strategy parameters
MIN_GAMMA_THRESHOLD = 0.1
MIN_DGEX_THRESHOLD = 0.05
PRICE_PROXIMITY_PCT = 0.0005
MIN_VANNA_TOUCH_THRESHOLD = 0.001

# Trade management
MIN_HOLDING_TIME_MINUTES = 25
COOLDOWN_AFTER_EXIT_MINUTES = 10
MIN_CONFIDENCE_THRESHOLD = 0.55
EMERGENCY_STOP_LOSS_PCT = 0.005
PROFIT_TARGET_PCT = 0.012
STOP_LOSS_PCT = 0.003
RESISTANCE_EXIT_PROXIMITY = 0.998
SUPPORT_EXIT_PROXIMITY = 1.002

# Dollar value per point
POINT_VALUES = {
    "SPX": 10.0,
    "SPY": 100.0,
    "QQQ": 400.0,
}

# Discord Configuration
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
DISCORD_CHANNEL_ID = 1464600897404276841
DISCORD_ROLE_PING = "<@&1464601287411634226>"
DISCORD_ENABLED = True

# Loop timing
DATA_CHECK_INTERVAL_SECONDS = 20
MAX_DATA_AGE_SECONDS = 300  # 5 minutes

# Create output directory
if not os.path.exists(TRADES_OUTPUT_DIR):
    os.makedirs(TRADES_OUTPUT_DIR, exist_ok=True)

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class MinVannaState:
    level: Optional[float] = None
    touched: bool = False
    touch_time: Optional[str] = None
    previous_level: Optional[float] = None
    shift_direction: Optional[str] = None

@dataclass
class TradeEntry:
    time: str
    price: float
    spot_at_entry: float

@dataclass
class TradeExit:
    time: str
    price: float
    reason: str

@dataclass
class TradePnL:
    points: float
    percent: float

@dataclass
class TradeSignals:
    gamma_exposure: float
    gamma_regime: str
    vanna_signal: str
    charm_signal: str
    dgex_magnet: Optional[float]
    dgex_accelerator: Optional[float]
    zomma_signal: str
    nearest_resistance: Optional[float]
    nearest_support: Optional[float]
    zero_gamma: float
    min_vanna_magnet: Optional[float]
    min_vanna_touched: bool
    min_vanna_direction: str

@dataclass
class TradeLevels:
    ib_high_today: Optional[float]
    ib_low_today: Optional[float]
    ib_high_prev_days: List[float]
    ib_low_prev_days: List[float]
    fib_targets_up: List[float]
    fib_targets_down: List[float]
    max_gamma_strike: Optional[float]
    min_gamma_strike: Optional[float]
    max_dgex_strike: Optional[float]
    min_dgex_strike: Optional[float]
    min_vanna_strike: Optional[float]
    vp_vpoc: Optional[float]
    vp_vah: Optional[float]
    vp_val: Optional[float]
    vp_lvn_zones: List[dict]

@dataclass
class Confluence:
    spx_signal: str
    spy_signal: str
    qqq_signal: str
    aligned: bool

@dataclass
class Trade:
    trade_id: int
    ticker: str
    direction: str
    entry: TradeEntry
    exit: Optional[TradeExit]
    pnl: Optional[TradePnL]
    signals: TradeSignals
    levels: TradeLevels
    confluence: Confluence

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_ny_now() -> datetime:
    """Get current time in New York timezone."""
    return datetime.now(NY_TZ)

def is_trading_hours() -> bool:
    """Check if within trading hours (9:20-16:20 NYC, Mon-Fri)."""
    ny_now = get_ny_now()
    if ny_now.weekday() >= 5:
        return False
    current_time = ny_now.time()
    return MARKET_OPEN <= current_time <= MARKET_CLOSE

def is_past_ib_formation() -> bool:
    """Check if past IB formation period (after 10:30 NYC)."""
    return get_ny_now().time() >= IB_FORMATION_END

def get_today_str() -> str:
    """Get today's date as YYYYMMDD string."""
    return get_ny_now().strftime("%Y%m%d")

def get_dollar_value(ticker: str, points: float) -> float:
    """Calculate dollar value of trade based on ticker."""
    return points * POINT_VALUES.get(ticker, 10.0)

def save_active_trade(trade: Optional[Trade]):
    """Guardar trade activo al disco inmediatamente después de abrir."""
    if trade is None:
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
    else:
        with open(STATE_FILE, 'w') as f:
            json.dump(asdict(trade), f, indent=2)
        logger.info(f"[PERSISTENCE] ✅ Saved: {trade.direction} {trade.ticker}")

def load_active_trade() -> Optional[Trade]:
    """Cargar trade activo al iniciar el bot."""
    if not os.path.exists(STATE_FILE):
        return None

    try:
        with open(STATE_FILE, 'r') as f:
            data = json.load(f)

        # --- RECONSTRUCCIÓN DE OBJETOS ---
        
        # 1. Entry (Obligatorio) - Nombre correcto: TradeEntry
        if 'entry' in data and isinstance(data['entry'], dict):
            data['entry'] = TradeEntry(**data['entry'])
            
        # 2. Signals (Obligatorio) - Nombre correcto: TradeSignals
        if 'signals' in data and isinstance(data['signals'], dict):
            data['signals'] = TradeSignals(**data['signals'])

        # 3. Levels (Obligatorio) - Nombre correcto: TradeLevels
        if 'levels' in data and isinstance(data['levels'], dict):
            data['levels'] = TradeLevels(**data['levels'])

        # 4. Confluence (Obligatorio) - Nombre correcto: Confluence
        if 'confluence' in data and isinstance(data['confluence'], dict):
            data['confluence'] = Confluence(**data['confluence'])

        # 5. Exit (Opcional) - Nombre correcto: TradeExit
        if data.get('exit') and isinstance(data['exit'], dict):
            data['exit'] = TradeExit(**data['exit'])
        else:
            data['exit'] = None # Asegurar que sea None si no existe

        # 6. PnL (Opcional) - Nombre correcto: TradePnL
        if data.get('pnl') and isinstance(data['pnl'], dict):
            data['pnl'] = TradePnL(**data['pnl'])
        else:
            data['pnl'] = None

        # --- CREAR EL OBJETO MAESTRO ---
        trade = Trade(**data)
        
        logger.info(f"[PERSISTENCE] ✅ RECOVERED: {trade.direction} {trade.ticker}")
        return trade

    except Exception as e:
        logger.error(f"[PERSISTENCE] ❌ Error reconstruyendo trade: {e}")
        # Si el archivo está corrupto o incompatible, es mejor ignorarlo 
        # para que el bot pueda arrancar (aunque olvide el trade anterior)
        return None
# ============================================================================
# DISCORD NOTIFICATIONS
# ============================================================================

def send_discord_trade_open(trade_data: dict, analysis: dict):
    """Sends trade OPEN notification to Discord with detailed reasoning."""
    if not DISCORD_ENABLED or not DISCORD_WEBHOOK_URL:
        return
    
    ticker = trade_data.get("ticker", "???")
    direction = trade_data.get("direction", "???")
    entry_price = trade_data.get("entry", {}).get("price", 0)
    entry_time = trade_data.get("entry", {}).get("time", "")
    signals = trade_data.get("signals", {})
    levels = trade_data.get("levels", {})
    confluence = trade_data.get("confluence", {})
    
    stop_loss_price = entry_price * (1 - STOP_LOSS_PCT) if direction == "LONG" else entry_price * (1 + STOP_LOSS_PCT)
    emergency_stop = entry_price * (1 - EMERGENCY_STOP_LOSS_PCT) if direction == "LONG" else entry_price * (1 + EMERGENCY_STOP_LOSS_PCT)
    target_price = entry_price * (1 + PROFIT_TARGET_PCT) if direction == "LONG" else entry_price * (1 - PROFIT_TARGET_PCT)
    
    point_value = POINT_VALUES.get(ticker, 10.0)
    risk_dollars = abs(entry_price - stop_loss_price) * point_value
    reward_dollars = abs(target_price - entry_price) * point_value
    
    # Build detailed reasoning
    gamma_regime = signals.get("gamma_regime", "neutral")
    vanna_signal = signals.get("vanna_signal", "neutral")
    charm_signal = signals.get("charm_signal", "neutral")
    min_vanna = signals.get("min_vanna_magnet")
    dgex_magnet = signals.get("dgex_magnet")
    resistance = signals.get("nearest_resistance")
    support = signals.get("nearest_support")
    
    reason_parts = []
    
    # Gamma regime explanation
    if gamma_regime == "long":
        reason_parts.append("🟢 **Positive Gamma** → Mean-reversion environment")
    elif gamma_regime == "short":
        reason_parts.append("🔴 **Negative Gamma** → Momentum/trend environment")
    else:
        reason_parts.append("⚪ **Neutral Gamma** → Mixed environment")
    
    # Vanna signal
    if vanna_signal == "bullish":
        reason_parts.append("📈 **Vanna Bullish** → Dealer buying pressure expected")
    elif vanna_signal == "bearish":
        reason_parts.append("📉 **Vanna Bearish** → Dealer selling pressure expected")
    
    # Charm signal
    if charm_signal == "bullish":
        reason_parts.append("⏰ **Charm Bullish** → Time decay favors longs")
    elif charm_signal == "bearish":
        reason_parts.append("⏰ **Charm Bearish** → Time decay favors shorts")
    
    # Min Vanna magnet
    if min_vanna and not signals.get("min_vanna_touched", False):
        reason_parts.append(f"🧲 **Min Vanna Magnet** at ${min_vanna:.2f} (untouched)")
    
    # Entry reasoning based on levels
    if direction == "LONG" and support:
        reason_parts.append(f"💚 Near support at ${support:.2f}")
    elif direction == "SHORT" and resistance:
        reason_parts.append(f"💔 Near resistance at ${resistance:.2f}")
    
    reason_text = "\n".join(reason_parts) if reason_parts else "Multiple Greek signals aligned"
    
    # Build level info
    level_info = []
    if levels.get("ib_high_today"):
        level_info.append(f"IB High: ${levels['ib_high_today']:.2f}")
    if levels.get("ib_low_today"):
        level_info.append(f"IB Low: ${levels['ib_low_today']:.2f}")
    if resistance:
        level_info.append(f"Resistance: ${resistance:.2f}")
    if support:
        level_info.append(f"Support: ${support:.2f}")
    
    # Confluence info
    confluence_text = ""
    if confluence:
        spx = confluence.get("spx_signal", "HOLD")
        spy = confluence.get("spy_signal", "HOLD")
        qqq = confluence.get("qqq_signal", "HOLD")
        aligned = confluence.get("aligned", False)
        confluence_text = f"SPX: {spx} | SPY: {spy} | QQQ: {qqq} | {'✅ Aligned' if aligned else '⚠️ Mixed'}"
    
    color = 0x2ECC71 if direction == "LONG" else 0xE74C3C
    emoji = "📈" if direction == "LONG" else "📉"
    
    embed = {
        "title": f"{emoji} LIVE {direction} OPENED - {ticker}",
        "description": f"**{DISCORD_ROLE_PING}**\n\n**📊 Entry Reasoning:**\n{reason_text}",
        "color": color,
        "fields": [
            {"name": "💵 Entry Price", "value": f"${entry_price:.2f}", "inline": True},
            {"name": "⏰ Time (NYC)", "value": entry_time, "inline": True},
            {"name": "📊 Point Value", "value": f"${point_value:.0f}/pt", "inline": True},
            {"name": "🎯 Target", "value": f"${target_price:.2f} (+{PROFIT_TARGET_PCT*100:.1f}%)", "inline": True},
            {"name": "🛑 Stop Loss", "value": f"${stop_loss_price:.2f} (-{STOP_LOSS_PCT*100:.1f}%)", "inline": True},
            {"name": "⚠️ Emergency", "value": f"${emergency_stop:.2f}", "inline": True},
            {"name": "💰 Risk/Reward", "value": f"Risk: ${risk_dollars:.2f} | Reward: ${reward_dollars:.2f} | R:R = 1:{reward_dollars/risk_dollars:.1f}" if risk_dollars > 0 else "N/A", "inline": False},
        ],
        "footer": {"text": f"TradingBot1 | LIVE | Min Hold: {MIN_HOLDING_TIME_MINUTES}min"}
    }
    
    # Add levels if available
    if level_info:
        embed["fields"].append({
            "name": "📍 Key Levels",
            "value": " | ".join(level_info),
            "inline": False
        })
    
    # Add confluence if available
    if confluence_text:
        embed["fields"].append({
            "name": "🔗 Multi-Ticker Confluence",
            "value": confluence_text,
            "inline": False
        })
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json={"content": "<@&1464601287411634226> New Trade","embeds": [embed]}, timeout=5)
        if response.status_code >= 400:
            logger.error(f"[DISCORD] Webhook error: {response.status_code}")
        else:
            logger.info(f"[DISCORD] Trade open notification sent for {ticker}")
    except Exception as e:
        logger.error(f"[DISCORD] Failed to send open notification: {e}")

def send_discord_trade_close(trade: dict):
    """Sends trade CLOSE notification to Discord with detailed P&L and context."""
    if not DISCORD_ENABLED or not DISCORD_WEBHOOK_URL:
        return
    
    ticker = trade.get("ticker", "???")
    direction = trade.get("direction", "???")
    entry_price = trade.get("entry", {}).get("price", 0)
    entry_time = trade.get("entry", {}).get("time", "")
    exit_price = trade.get("exit", {}).get("price", 0)
    exit_time = trade.get("exit", {}).get("time", "")
    exit_reason = trade.get("exit", {}).get("reason", "Unknown")
    pnl_points = trade.get("pnl", {}).get("points", 0)
    pnl_pct = trade.get("pnl", {}).get("percent", 0)
    
    point_value = POINT_VALUES.get(ticker, 10.0)
    pnl_dollars = pnl_points * point_value
    
    # Calculate trade duration
    duration_text = "Unknown"
    try:
        entry_dt = datetime.strptime(entry_time, "%Y-%m-%d %H:%M:%S")
        exit_dt = datetime.strptime(exit_time, "%Y-%m-%d %H:%M:%S")
        duration_mins = (exit_dt - entry_dt).total_seconds() / 60
        if duration_mins >= 60:
            hours = int(duration_mins // 60)
            mins = int(duration_mins % 60)
            duration_text = f"{hours}h {mins}m"
        else:
            duration_text = f"{int(duration_mins)}m"
    except:
        pass
    
    # Build exit reason explanation
    exit_explanation = ""
    if "Stop Loss" in exit_reason:
        exit_explanation = "🛑 **Stop Loss Hit** - Price moved against position beyond threshold"
    elif "Emergency" in exit_reason:
        exit_explanation = "⚠️ **Emergency Stop** - Catastrophic move triggered immediate exit"
    elif "Profit Target" in exit_reason:
        exit_explanation = "🎯 **Target Hit** - Price reached profit objective"
    elif "Market Close" in exit_reason:
        exit_explanation = "🔔 **Market Close** - End of day forced exit"
    elif "Min Vanna" in exit_reason:
        exit_explanation = "🧲 **Min Vanna Target** - Price reached vanna magnet level"
    elif "EOD" in exit_reason:
        exit_explanation = "⏰ **EOD Force Exit** - Approaching market close"
    else:
        exit_explanation = f"📋 {exit_reason}"
    
    color = 0x2ECC71 if pnl_dollars >= 0 else 0xE74C3C
    emoji = "✅" if pnl_dollars >= 0 else "❌"
    result = "PROFIT" if pnl_dollars >= 0 else "LOSS"
    
    # Price movement info
    price_move = exit_price - entry_price
    price_move_pct = (price_move / entry_price) * 100 if entry_price > 0 else 0
    
    embed = {
        "title": f"{emoji} LIVE {direction} CLOSED - {ticker} ({result})",
        "description": f"**{DISCORD_ROLE_PING}**\n\n{exit_explanation}",
        "color": color,
        "fields": [
            {"name": "💵 Entry", "value": f"${entry_price:.2f}", "inline": True},
            {"name": "💵 Exit", "value": f"${exit_price:.2f}", "inline": True},
            {"name": "📊 Move", "value": f"{price_move:+.2f} pts ({price_move_pct:+.2f}%)", "inline": True},
            {"name": "⏱️ Duration", "value": duration_text, "inline": True},
            {"name": "📈 P&L Points", "value": f"{pnl_points:+.2f} pts", "inline": True},
            {"name": "📊 P&L %", "value": f"{pnl_pct:+.2f}%", "inline": True},
            {"name": f"💰 P&L (${point_value:.0f}/pt)", "value": f"**${pnl_dollars:+.2f}**", "inline": False},
        ],
        "footer": {"text": "TradingBot1 | LIVE"}
    }
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json={"content": "<@&1464601287411634226> Trade Closed","embeds": [embed]}, timeout=5)
        if response.status_code >= 400:
            logger.error(f"[DISCORD] Webhook error: {response.status_code}")
        else:
            logger.info(f"[DISCORD] Trade close notification sent for {ticker}")
    except Exception as e:
        logger.error(f"[DISCORD] Failed to send close notification: {e}")

# ============================================================================
# REAL-TIME DATA LOADING
# ============================================================================

def get_latest_greek_file(ticker: str) -> Optional[dict]:
    """Get most recent Greek data file for ticker."""
    today = get_today_str()
    pattern = os.path.join(GREEK_DATA_DIR, f"{ticker}_0dte_ExposureData_{today}_*.json")
    files = sorted(glob.glob(pattern))
    
    if not files:
        return None
    
    latest = files[-1]
    mtime = os.path.getmtime(latest)
    
    if time.time() - mtime > MAX_DATA_AGE_SECONDS:
        return None
    
    try:
        with open(latest, 'r') as f:
            data = json.load(f)
        
        # Parse timestamp from filename
        match = re.search(r"_(\d{8})_(\d{6})\.json", latest)
        if match:
            dt_str = f"{match.group(1)} {match.group(2)}"
            file_dt = datetime.strptime(dt_str, "%Y%m%d %H%M%S")
            data['_file_datetime'] = file_dt
            data['_filepath'] = latest
        
        return data
    except Exception as e:
        print(f"[ERROR] Loading {latest}: {e}")
        return None

def get_current_ib_data(ticker: str) -> Optional[dict]:
    """Get current day's IB data for ticker from ib_charts (real-time)."""
    today = get_today_str()
    filepath = os.path.join(IB_CHARTS_DIR, f"ib_data_{ticker}_{today}.json")
    
    if not os.path.exists(filepath):
        return None
    
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except:
        return None

def get_previous_ib_levels(ticker: str, num_days: int = 5) -> Tuple[List[float], List[float]]:
    """Get IB high/low from previous N days. Checks ib_backtest first (historical), then ib_charts."""
    ib_highs = []
    ib_lows = []
    today = get_ny_now().date()
    
    days_found = 0
    days_back = 1
    
    while days_found < num_days and days_back < 30:
        prev_date = today - timedelta(days=days_back)
        if prev_date.weekday() >= 5:
            days_back += 1
            continue
        
        date_str = prev_date.strftime("%Y%m%d")
        
        # Try ib_backtest first (historical with volume_profile), then ib_charts
        filepath = os.path.join(IB_BACKTEST_DIR, f"ib_data_{ticker}_{date_str}.json")
        if not os.path.exists(filepath):
            filepath = os.path.join(IB_CHARTS_DIR, f"ib_data_{ticker}_{date_str}.json")
        
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                if "analysis" in data:
                    ib_highs.append(data["analysis"].get("ib_high", 0))
                    ib_lows.append(data["analysis"].get("ib_low", 0))
                    days_found += 1
            except:
                pass
        
        days_back += 1
    
    return ib_highs, ib_lows

# ============================================================================
# GREEK ANALYSIS (from backtest.py)
# ============================================================================

def get_net_greek_exposure(data: dict, greek_name: str) -> float:
    """Calculate net Greek exposure."""
    greek_data = data.get(greek_name, {})
    if isinstance(greek_data, dict):
        all_data = greek_data.get("all", [])
        if isinstance(all_data, list) and len(all_data) > 0:
            return sum(all_data)
    return 0.0

def find_max_min_greek_level(data: dict, greek_name: str) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """Find strikes with max/min Greek exposure."""
    levels = data.get("levels", [])
    greek_data = data.get(greek_name, {})
    
    if isinstance(greek_data, dict):
        all_data = greek_data.get("all", [])
    else:
        all_data = []
    
    if not levels or not all_data or len(levels) != len(all_data):
        return None, None, None, None
    
    levels = np.array(levels)
    values = np.array(all_data)
    
    max_idx = np.argmax(values)
    min_idx = np.argmin(values)
    
    return levels[max_idx], values[max_idx], levels[min_idx], values[min_idx]

def analyze_gamma(data: dict) -> Tuple[str, float]:
    """Analyze gamma regime."""
    net_gamma = get_net_greek_exposure(data, "totalgamma")
    
    if net_gamma > MIN_GAMMA_THRESHOLD:
        return "long", net_gamma
    elif net_gamma < -MIN_GAMMA_THRESHOLD:
        return "short", net_gamma
    else:
        return "neutral", net_gamma

def analyze_vanna(data: dict, spot_price: float) -> str:
    """Analyze vanna signal."""
    net_vanna = get_net_greek_exposure(data, "totalvanna")
    
    if net_vanna > MIN_GAMMA_THRESHOLD:
        return "bullish"
    elif net_vanna < -MIN_GAMMA_THRESHOLD:
        return "bearish"
    else:
        return "neutral"

def analyze_charm(data: dict) -> str:
    """Analyze charm signal."""
    net_charm = get_net_greek_exposure(data, "totalcharm")
    
    if net_charm > MIN_GAMMA_THRESHOLD:
        return "bullish"
    elif net_charm < -MIN_GAMMA_THRESHOLD:
        return "bearish"
    else:
        return "neutral"

def analyze_dgex(data: dict) -> Tuple[str, Optional[float], Optional[float]]:
    """Analyze DGEX (delta-adjusted gamma)."""
    net_dgex = get_net_greek_exposure(data, "totaldgex")
    max_strike, _, min_strike, _ = find_max_min_greek_level(data, "totaldgex")
    
    if net_dgex > MIN_DGEX_THRESHOLD:
        return "sticky", max_strike, min_strike
    elif net_dgex < -MIN_DGEX_THRESHOLD:
        return "accelerator", max_strike, min_strike
    else:
        return "neutral", max_strike, min_strike

def analyze_zomma(data: dict) -> str:
    """Analyze zomma signal."""
    net_zomma = get_net_greek_exposure(data, "totalzomma")
    
    if net_zomma > MIN_GAMMA_THRESHOLD:
        return "stabilizing"
    elif net_zomma < -MIN_GAMMA_THRESHOLD:
        return "destabilizing"
    else:
        return "neutral"

# ============================================================================
# SIGNAL GENERATION
# ============================================================================

def generate_signal(analysis: dict, spot: float, gamma_regime: str) -> Tuple[str, float]:
    """Generate trading signal based on analysis."""
    signal = "HOLD"
    confidence = 0.0
    
    resistance = analysis.get("resistance")
    support = analysis.get("support")
    vanna = analysis.get("vanna_signal", "neutral")
    charm = analysis.get("charm_signal", "neutral")
    min_vanna = analysis.get("min_vanna_level")
    
    # Positive gamma = mean reversion
    if gamma_regime == "long":
        if resistance and abs(spot - resistance) / spot < PRICE_PROXIMITY_PCT:
            signal = "SHORT"
            confidence = 0.6
        elif support and abs(spot - support) / spot < PRICE_PROXIMITY_PCT:
            signal = "LONG"
            confidence = 0.6
    
    # Negative gamma = trend following
    elif gamma_regime == "short":
        if vanna == "bullish" or charm == "bullish":
            signal = "LONG"
            confidence = 0.55
        elif vanna == "bearish" or charm == "bearish":
            signal = "SHORT"
            confidence = 0.55
    
    # Min Vanna magnet
    if min_vanna and not analysis.get("min_vanna_touched", False):
        if min_vanna > spot * 1.002:
            if signal == "HOLD" or signal == "LONG":
                signal = "LONG"
                confidence = max(confidence, 0.6)
        elif min_vanna < spot * 0.998:
            if signal == "HOLD" or signal == "SHORT":
                signal = "SHORT"
                confidence = max(confidence, 0.6)
    
    return signal, confidence

def should_exit_trade(trade: Trade, current_price: float, current_time: datetime, 
                     gamma_regime: str, resistance: Optional[float], 
                     support: Optional[float], min_vanna: Optional[float]) -> Tuple[bool, str]:
    """Check if trade should be exited."""
    entry_price = trade.entry.price
    entry_time = datetime.strptime(trade.entry.time, "%Y-%m-%d %H:%M:%S")
    
    if trade.direction == "LONG":
        pnl_pct = (current_price - entry_price) / entry_price
    else:
        pnl_pct = (entry_price - current_price) / entry_price
    
    minutes_held = (current_time.replace(tzinfo=None) - entry_time).total_seconds() / 60
    
    # Emergency stop (always active)
    if pnl_pct < -EMERGENCY_STOP_LOSS_PCT:
        return True, "Emergency Stop Loss"
    
    # Market close
    if current_time.time() >= dt_time(16, 15):
        return True, "Market Close"
    
    # Before minimum holding time, only emergency exits
    if minutes_held < MIN_HOLDING_TIME_MINUTES:
        return False, ""
    
    # Profit target
    if pnl_pct >= PROFIT_TARGET_PCT:
        return True, "Profit Target Hit"
    
    # Stop loss
    if pnl_pct <= -STOP_LOSS_PCT:
        return True, "Stop Loss Hit"
    
    # Min Vanna target reached
    if min_vanna:
        if trade.direction == "LONG" and current_price >= min_vanna * 0.998:
            return True, "Min Vanna Target Reached"
        if trade.direction == "SHORT" and current_price <= min_vanna * 1.002:
            return True, "Min Vanna Target Reached"
    
    return False, ""

def check_multi_ticker_confluence(ticker_signals: dict) -> Confluence:
    """Check alignment across tickers."""
    spx_sig = ticker_signals.get("SPX", {}).get("signal", "HOLD")
    spy_sig = ticker_signals.get("SPY", {}).get("signal", "HOLD")
    qqq_sig = ticker_signals.get("QQQ", {}).get("signal", "HOLD")
    
    signals = [s for s in [spx_sig, spy_sig, qqq_sig] if s != "HOLD"]
    aligned = len(set(signals)) <= 1 if signals else False
    
    return Confluence(
        spx_signal=spx_sig,
        spy_signal=spy_sig,
        qqq_signal=qqq_sig,
        aligned=aligned
    )

# ============================================================================
# TRADE MANAGEMENT
# ============================================================================

def save_trade(trade: Trade):
    """Save trade to JSON file."""
    trade_dict = asdict(trade)
    fname = f"live_trade_{trade.trade_id}_{trade.ticker}_{trade.entry.time.replace(' ','_').replace(':','')}.json"
    filepath = os.path.join(TRADES_OUTPUT_DIR, fname)
    
    with open(filepath, 'w') as f:
        json.dump(trade_dict, f, indent=2, default=str)
    
    print(f"[SAVED] {fname}")

# ============================================================================
# MAIN TRADING LOOP
# ============================================================================

async def main_loop():
    """Main trading loop."""
    print("=" * 60)
    print("TRADINGBOT1 - LIVE GREEK EXPOSURE STRATEGY")
    print("=" * 60)
    print(f"Greeks Dir: {GREEK_DATA_DIR}")
    print(f"IB Charts Dir: {IB_CHARTS_DIR}")
    print(f"IB Backtest Dir: {IB_BACKTEST_DIR}")
    print(f"Tickers: {TICKERS}")
    print(f"Trading Hours: {MARKET_OPEN} - {MARKET_CLOSE} NYC")
    print("=" * 60)
    logger.info("[STARTUP] Bot starting...")
    current_trade = load_active_trade()
    trade_counter = 0
    all_trades: List[Trade] = []
    min_vanna_states = {t: MinVannaState() for t in TICKERS}
    last_trade_exit_time = None
    last_processed_files = {}
    
    while True:
        try:
            # Check trading hours
            if not is_trading_hours():
                ny_now = get_ny_now()
                if ny_now.weekday() >= 5:
                    print(f"[{ny_now.strftime('%H:%M:%S')}] Weekend - sleeping...")
                else:
                    print(f"[{ny_now.strftime('%H:%M:%S')}] Outside trading hours - sleeping...")
                
                # Reset state at end of day
                if current_trade is None and ny_now.time() > MARKET_CLOSE:
                    min_vanna_states = {t: MinVannaState() for t in TICKERS}
                    last_trade_exit_time = None
                
                await asyncio.sleep(20)
                continue
            
            current_time = get_ny_now()
            print(f"\n[{current_time.strftime('%H:%M:%S')}] Checking data...")
            
            # Gather data for all tickers
            ticker_analysis = {}
            ticker_signals = {}
            
            for ticker in TICKERS:
                data = get_latest_greek_file(ticker)
                if not data:
                    print(f"  [{ticker}] No fresh data")
                    continue
                
                # Skip if we already processed this file
                filepath = data.get('_filepath', '')
                if filepath == last_processed_files.get(ticker):
                    continue
                last_processed_files[ticker] = filepath
                
                spot_price = data.get("spot_price", 0)
                if spot_price == 0:
                    continue
                
                # Analyze Greeks
                gamma_regime, gamma_exp = analyze_gamma(data)
                vanna_signal = analyze_vanna(data, spot_price)
                charm_signal = analyze_charm(data)
                dgex_signal, dgex_magnet, dgex_accel = analyze_dgex(data)
                zomma_signal = analyze_zomma(data)
                
                # Get levels
                max_gamma_strike, _, min_gamma_strike, _ = find_max_min_greek_level(data, "totalgamma")
                max_dgex_strike, _, min_dgex_strike, _ = find_max_min_greek_level(data, "totaldgex")
                _, _, min_vanna_level, _ = find_max_min_greek_level(data, "totalvanna")
                
                # Get IB data
                ib_data = get_current_ib_data(ticker)
                ib_high = ib_data.get("analysis", {}).get("ib_high") if ib_data and is_past_ib_formation() else None
                ib_low = ib_data.get("analysis", {}).get("ib_low") if ib_data and is_past_ib_formation() else None
                
                # Find resistance/support
                all_levels = []
                if ib_high: all_levels.append(ib_high)
                if ib_low: all_levels.append(ib_low)
                if max_gamma_strike: all_levels.append(max_gamma_strike)
                if min_gamma_strike: all_levels.append(min_gamma_strike)
                
                resistance = min([l for l in all_levels if l > spot_price], default=None)
                support = max([l for l in all_levels if l < spot_price], default=None)
                
                # Min Vanna tracking
                state = min_vanna_states[ticker]
                if min_vanna_level:
                    if state.level and abs(spot_price - min_vanna_level) / spot_price < MIN_VANNA_TOUCH_THRESHOLD:
                        state.touched = True
                        state.touch_time = current_time.strftime("%H:%M:%S")
                    state.level = min_vanna_level
                
                analysis = {
                    "spot_price": spot_price,
                    "gamma_regime": gamma_regime,
                    "gamma_exp": gamma_exp,
                    "vanna_signal": vanna_signal,
                    "charm_signal": charm_signal,
                    "dgex_signal": dgex_signal,
                    "dgex_magnet": dgex_magnet,
                    "dgex_accel": dgex_accel,
                    "zomma_signal": zomma_signal,
                    "resistance": resistance,
                    "support": support,
                    "ib_high_today": ib_high,
                    "ib_low_today": ib_low,
                    "min_vanna_level": min_vanna_level,
                    "min_vanna_touched": state.touched,
                    "max_gamma_strike": max_gamma_strike,
                    "min_gamma_strike": min_gamma_strike,
                }
                
                signal, confidence = generate_signal(analysis, spot_price, gamma_regime)
                analysis["signal"] = signal
                analysis["confidence"] = confidence
                
                ticker_analysis[ticker] = analysis
                ticker_signals[ticker] = {"signal": signal, "confidence": confidence}
                
                print(f"  [{ticker}] Spot: {spot_price:.2f} | Gamma: {gamma_regime} | Signal: {signal} ({confidence:.0%})")
            
            # Check confluence
            confluence = check_multi_ticker_confluence(ticker_signals)
            
            # Check for EOD force exit on active trade
            if current_time.time() >= FORCE_EXIT_TIME and current_trade:
                ticker = current_trade.ticker
                if ticker in ticker_analysis:
                    analysis = ticker_analysis[ticker]
                    current_trade.exit = TradeExit(
                        time=current_time.strftime("%Y-%m-%d %H:%M:%S"),
                        price=analysis["spot_price"],
                        reason="EOD Force Exit"
                    )
                    
                    if current_trade.direction == "LONG":
                        pnl_points = analysis["spot_price"] - current_trade.entry.price
                    else:
                        pnl_points = current_trade.entry.price - analysis["spot_price"]
                    
                    pnl_pct = pnl_points / current_trade.entry.price * 100
                    current_trade.pnl = TradePnL(points=pnl_points, percent=pnl_pct)
                    
                    all_trades.append(current_trade)
                    save_trade(current_trade)
                    
                    dollar_pnl = get_dollar_value(ticker, pnl_points)
                    logger.info(f"[EOD EXIT] Closed {current_trade.direction} {ticker} @ {analysis['spot_price']:.2f} | P&L: ${dollar_pnl:+.2f}")
                    send_discord_trade_close(asdict(current_trade))
                    
                    current_trade = None
                    save_active_trade(None)
                
                await asyncio.sleep(DATA_CHECK_INTERVAL_SECONDS)
                continue
            
            # Manage existing trade
            if current_trade:
                ticker = current_trade.ticker
                if ticker in ticker_analysis:
                    analysis = ticker_analysis[ticker]
                    should_exit, exit_reason = should_exit_trade(
                        current_trade,
                        analysis["spot_price"],
                        current_time,
                        analysis["gamma_regime"],
                        analysis["resistance"],
                        analysis["support"],
                        analysis.get("min_vanna_level")
                    )
                    
                    if should_exit:
                        current_trade.exit = TradeExit(
                            time=current_time.strftime("%Y-%m-%d %H:%M:%S"),
                            price=analysis["spot_price"],
                            reason=exit_reason
                        )
                        
                        if current_trade.direction == "LONG":
                            pnl_points = analysis["spot_price"] - current_trade.entry.price
                        else:
                            pnl_points = current_trade.entry.price - analysis["spot_price"]
                        
                        pnl_pct = pnl_points / current_trade.entry.price * 100
                        current_trade.pnl = TradePnL(points=pnl_points, percent=pnl_pct)
                        
                        all_trades.append(current_trade)
                        save_trade(current_trade)
                        
                        dollar_pnl = get_dollar_value(ticker, pnl_points)
                        logger.info(f"[TRADE CLOSED] {current_trade.direction} {ticker} @ {analysis['spot_price']:.2f}")
                        logger.info(f"  └─ Reason: {exit_reason}")
                        logger.info(f"  └─ P&L: {pnl_points:+.2f} pts ({pnl_pct:+.2f}%) = ${dollar_pnl:+.2f}")
                        print(f"  [CLOSED] {current_trade.direction} {ticker} @ {analysis['spot_price']:.2f} | P&L: ${dollar_pnl:+.2f} | {exit_reason}")
                        send_discord_trade_close(asdict(current_trade))
                        
                        last_trade_exit_time = current_time
                        current_trade = None
                        save_active_trade(None)
            
            # Look for new entry
            if current_trade is None:
                # Check cooldown
                if last_trade_exit_time:
                    mins_since = (current_time - last_trade_exit_time).total_seconds() / 60
                    if mins_since < COOLDOWN_AFTER_EXIT_MINUTES:
                        remaining = COOLDOWN_AFTER_EXIT_MINUTES - mins_since
                        logger.debug(f"[COOLDOWN] {remaining:.0f} min remaining before next trade allowed")
                        print(f"  [COOLDOWN] {remaining:.0f} min remaining")
                        await asyncio.sleep(DATA_CHECK_INTERVAL_SECONDS)
                        continue
                
                # Check if past last entry time
                if current_time.time() >= LAST_ENTRY_TIME:
                    logger.debug(f"[NO ENTRY] Past last entry time ({LAST_ENTRY_TIME})")
                    await asyncio.sleep(DATA_CHECK_INTERVAL_SECONDS)
                    continue
                
                # Find best entry
                best_ticker = None
                best_signal = "HOLD"
                best_confidence = 0
                
                for ticker in TICKERS:
                    if ticker not in ticker_analysis:
                        logger.debug(f"[{ticker}] No analysis available - skipping")
                        continue
                    
                    analysis = ticker_analysis[ticker]
                    signal = analysis["signal"]
                    confidence = analysis["confidence"]
                    
                    # Log why signal was rejected/accepted
                    if signal == "HOLD":
                        logger.debug(f"[{ticker}] Signal=HOLD - no entry")
                    elif confidence <= MIN_CONFIDENCE_THRESHOLD:
                        logger.debug(f"[{ticker}] Signal={signal} but confidence {confidence:.0%} <= {MIN_CONFIDENCE_THRESHOLD:.0%} threshold")
                    elif not confluence.aligned:
                        logger.debug(f"[{ticker}] Signal={signal} ({confidence:.0%}) but confluence not aligned")
                    else:
                        logger.info(f"[{ticker}] Candidate: {signal} @ {analysis['spot_price']:.2f} (conf: {confidence:.0%})")
                    
                    if signal in ["LONG", "SHORT"] and confidence > MIN_CONFIDENCE_THRESHOLD:
                        if confluence.aligned and confidence > best_confidence:
                            best_ticker = ticker
                            best_signal = signal
                            best_confidence = confidence
                
                # Open trade
                if best_ticker and best_signal != "HOLD":
                    analysis = ticker_analysis[best_ticker]
                    trade_counter += 1
                    
                    prev_ib_highs, prev_ib_lows = get_previous_ib_levels(best_ticker)
                    
                    current_trade = Trade(
                        trade_id=trade_counter,
                        ticker=best_ticker,
                        direction=best_signal,
                        entry=TradeEntry(
                            time=current_time.strftime("%Y-%m-%d %H:%M:%S"),
                            price=analysis["spot_price"],
                            spot_at_entry=analysis["spot_price"]
                        ),
                        exit=None,
                        pnl=None,
                        signals=TradeSignals(
                            gamma_exposure=analysis["gamma_exp"],
                            gamma_regime=analysis["gamma_regime"],
                            vanna_signal=analysis["vanna_signal"],
                            charm_signal=analysis["charm_signal"],
                            dgex_magnet=analysis["dgex_magnet"],
                            dgex_accelerator=analysis["dgex_accel"],
                            zomma_signal=analysis["zomma_signal"],
                            nearest_resistance=analysis["resistance"],
                            nearest_support=analysis["support"],
                            zero_gamma=0,
                            min_vanna_magnet=analysis["min_vanna_level"],
                            min_vanna_touched=analysis["min_vanna_touched"],
                            min_vanna_direction=""
                        ),
                        levels=TradeLevels(
                            ib_high_today=analysis["ib_high_today"],
                            ib_low_today=analysis["ib_low_today"],
                            ib_high_prev_days=prev_ib_highs,
                            ib_low_prev_days=prev_ib_lows,
                            fib_targets_up=[],
                            fib_targets_down=[],
                            max_gamma_strike=analysis["max_gamma_strike"],
                            min_gamma_strike=analysis["min_gamma_strike"],
                            max_dgex_strike=None,
                            min_dgex_strike=None,
                            min_vanna_strike=analysis["min_vanna_level"],
                            vp_vpoc=None,
                            vp_vah=None,
                            vp_val=None,
                            vp_lvn_zones=[]
                        ),
                        confluence=confluence
                    )
                    
                    # Detailed logging for trade open
                    logger.info(f"[TRADE OPENED] {best_signal} {best_ticker} @ {analysis['spot_price']:.2f}")
                    logger.info(f"  └─ Confidence: {best_confidence:.0%}")
                    logger.info(f"  └─ Gamma Regime: {analysis['gamma_regime']}")
                    logger.info(f"  └─ Vanna Signal: {analysis['vanna_signal']}")
                    logger.info(f"  └─ Resistance: {analysis.get('resistance', 'N/A')}")
                    logger.info(f"  └─ Support: {analysis.get('support', 'N/A')}")
                    if analysis.get('min_vanna_level'):
                        logger.info(f"  └─ Min Vanna: {analysis['min_vanna_level']:.2f} (touched: {analysis.get('min_vanna_touched', False)})")
                    print(f"  [OPENED] {best_signal} {best_ticker} @ {analysis['spot_price']:.2f} (conf: {best_confidence:.0%})")
                    save_active_trade(current_trade)
                    send_discord_trade_open(asdict(current_trade), analysis)
            
            await asyncio.sleep(DATA_CHECK_INTERVAL_SECONDS)
            
        except Exception as e:
            print(f"[ERROR] {e}")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(20)

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("STARTING TRADINGBOT1 - LIVE TRADING")
    print("=" * 60 + "\n")
    
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("\n[STOP] Stopped by user.")
