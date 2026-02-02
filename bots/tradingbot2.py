"""
Real-Time Trading Bot 2 - Simplified Greek Exposure Strategy

This bot implements the same strategy as backtest2.py but uses real-time data
from gex_daemon.py and ib_service.py.

Runs Monday-Friday from 9:20 AM to 4:20 PM New York time.

Usage: python tradingbot2.py
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
        logging.FileHandler(os.path.join(SCRIPT_DIR, 'tradingbot2.log')),  # Archivo
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
TRADES_OUTPUT_DIR = os.path.join(SCRIPT_DIR, "trades_live2")

STATE_FILE = os.path.join(SCRIPT_DIR, "state_bot2.json")

TICKERS = ["SPX", "SPY", "QQQ"]

# Trading hours (NYC)
MARKET_OPEN = dt_time(4, 20)
MARKET_CLOSE = dt_time(16, 20)
FORCE_EXIT_TIME = dt_time(15, 55)
IB_FORMATION_END = dt_time(10, 30)
LAST_ENTRY_TIME = dt_time(15, 15)

# Fibonacci
FIB_LEVELS = [0.272, 0.5, 0.618, 1.0, 1.272, 1.618, 2.0, 2.272]
FIB_LEVELS_NEG = [-0.272, -0.5, -0.618, -1.0, -1.272]

# Risk Management
MIN_GAMMA_THRESHOLD = 0.5
MIN_DGEX_THRESHOLD = 0.5
PROXIMITY_PCT = 0.0015
MAX_LEVEL_DIST_PCT = 0.02
STOP_LOSS_FIXED = 0.003
BREAKEVEN_TRIGGER = 0.0025
TRAILING_STEP = 0.002
MIN_TARGET_DIST = 0.0015
MIN_RISK_REWARD = 1.2
COOLDOWN_MINUTES = 30

# Dollar value per point
POINT_VALUES = {"SPX": 10.0, "SPY": 100.0, "QQQ": 400.0}

# Discord Configuration
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
DISCORD_ROLE_PING = "<@&1464601287411634226>"
DISCORD_ENABLED = True

# Loop timing
DATA_CHECK_INTERVAL_SECONDS = 20
MAX_DATA_AGE_SECONDS = 300

# Create output directory
if not os.path.exists(TRADES_OUTPUT_DIR):
    os.makedirs(TRADES_OUTPUT_DIR, exist_ok=True)

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class MarketState:
    gamma_regime: str
    dgex_regime: str
    min_vanna_level: Optional[float]
    min_vanna_touched: bool
    min_vanna_shift: str
    max_dgex_magnet: Optional[float]
    min_dgex_accel: Optional[float]

@dataclass
class TradeEntry:
    time: str
    price: float
    reason: str
    setup_details: str

@dataclass
class TradeExit:
    time: str
    price: float
    reason: str

@dataclass
class TradePnL:
    points: float
    percent: float
    dollars: float

@dataclass
class Trade:
    trade_id: int
    ticker: str
    direction: str
    strategy: str
    entry: TradeEntry
    exit: Optional[TradeExit]
    pnl: Optional[TradePnL]
    target_level: Optional[float]
    stop_level: float
    highest_pnl_pct: float = 0.0

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
    """Check if past IB formation period."""
    return get_ny_now().time() >= IB_FORMATION_END

def get_today_str() -> str:
    """Get today's date as YYYYMMDD string."""
    return get_ny_now().strftime("%Y%m%d")

def get_dollar_value(ticker: str, points: float) -> float:
    """Calculate dollar value of trade."""
    return points * POINT_VALUES.get(ticker, 10.0)

def is_near(price: float, level: float, pct: float = PROXIMITY_PCT) -> bool:
    """Check if price is near a level."""
    if level is None or level == 0:
        return False
    return abs(price - level) / level <= pct

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

        # --- RECONSTRUCCIÓN DE OBJETOS (Específico para Bot 2) ---

        # 1. Entry (Obligatorio) - Nombre correcto: TradeEntry
        if 'entry' in data and isinstance(data['entry'], dict):
            data['entry'] = TradeEntry(**data['entry'])

        # 2. Exit (Opcional) - Nombre correcto: TradeExit
        if data.get('exit') and isinstance(data['exit'], dict):
            data['exit'] = TradeExit(**data['exit'])
        else:
            data['exit'] = None

        # 3. PnL (Opcional) - Nombre correcto: TradePnL
        if data.get('pnl') and isinstance(data['pnl'], dict):
            data['pnl'] = TradePnL(**data['pnl'])
        else:
            data['pnl'] = None

        # --- CREAR EL OBJETO MAESTRO ---
        # Nota: highest_pnl_pct tiene valor por defecto en la clase, 
        # así que no fallará si no está en el JSON antiguo.
        trade = Trade(**data)

        logger.info(f"[PERSISTENCE] ✅ RECOVERED: {trade.direction} {trade.ticker}")
        return trade

    except Exception as e:
        logger.error(f"[PERSISTENCE] ❌ Error reconstruyendo trade: {e}")
        return None
# ============================================================================
# DISCORD NOTIFICATIONS
# ============================================================================

def send_discord_trade_open(trade: Trade):
    """Sends trade OPEN notification to Discord with detailed reasoning."""
    if not DISCORD_ENABLED or not DISCORD_WEBHOOK_URL:
        return
    
    ticker = trade.ticker
    direction = trade.direction
    entry_price = trade.entry.price
    entry_time = trade.entry.time
    target = trade.target_level
    reason = trade.entry.reason
    details = trade.entry.setup_details
    strategy = trade.strategy
    
    point_value = POINT_VALUES.get(ticker, 10.0)
    stop_price = entry_price * (1 - STOP_LOSS_FIXED) if direction == "LONG" else entry_price * (1 + STOP_LOSS_FIXED)
    risk_dollars = abs(entry_price - stop_price) * point_value
    reward_dollars = abs(target - entry_price) * point_value if target else 0
    rr_ratio = reward_dollars / risk_dollars if risk_dollars > 0 else 0
    
    color = 0x2ECC71 if direction == "LONG" else 0xE74C3C
    emoji = "📈" if direction == "LONG" else "📉"
    strategy_emoji = "🔄" if strategy == "REVERSAL" else "🚀"
    
    # Build description with strategy type
    description_lines = [
        f"**{DISCORD_ROLE_PING}**",
        "",
        f"{strategy_emoji} **Estrategia:** {strategy}",
        f"**Trigger:** {reason}",
        "",
        f"**📊 Análisis Detallado:**",
        details
    ]
    
    embed = {
        "title": f"{emoji} LIVE {direction} OPENED - {ticker}",
        "description": "\n".join(description_lines),
        "color": color,
        "fields": [
            {"name": "💵 Entry", "value": f"${entry_price:.2f}", "inline": True},
            {"name": "🎯 Target", "value": f"${target:.2f}" if target else "N/A", "inline": True},
            {"name": "🛑 Stop Loss", "value": f"${stop_price:.2f} ({STOP_LOSS_FIXED*100:.1f}%)", "inline": True},
            {"name": "⏰ Time (NYC)", "value": entry_time, "inline": True},
            {"name": "💰 Risk", "value": f"${risk_dollars:.2f}", "inline": True},
            {"name": "💎 Reward", "value": f"${reward_dollars:.2f}", "inline": True},
            {"name": "📊 Risk/Reward Ratio", "value": f"1:{rr_ratio:.1f}" if rr_ratio > 0 else "N/A", "inline": True},
            {"name": "📈 Point Value", "value": f"${point_value:.0f}/pt", "inline": True},
        ],
        "footer": {"text": f"TradingBot2 | LIVE | Breakeven @ +{BREAKEVEN_TRIGGER*100:.2f}%"}
    }
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json={"content": "<@&1464601287411634226> New Trade","embeds": [embed]}, timeout=5)
        if response.status_code >= 400:
            logger.error(f"[DISCORD] Webhook error: {response.status_code}")
        else:
            logger.info(f"[DISCORD] Trade open notification sent for {ticker}")
    except Exception as e:
        logger.error(f"[DISCORD] Failed to send open notification: {e}")

def send_discord_trade_close(trade: Trade):
    """Sends trade CLOSE notification to Discord with detailed P&L and context."""
    if not DISCORD_ENABLED or not DISCORD_WEBHOOK_URL or not trade.exit or not trade.pnl:
        return
    
    ticker = trade.ticker
    direction = trade.direction
    entry_price = trade.entry.price
    entry_time = trade.entry.time
    exit_price = trade.exit.price
    exit_time = trade.exit.time
    exit_reason = trade.exit.reason
    pnl_dollars = trade.pnl.dollars
    pnl_points = trade.pnl.points
    pnl_pct = trade.pnl.percent
    max_pnl_pct = trade.highest_pnl_pct
    
    point_value = POINT_VALUES.get(ticker, 10.0)
    
    # Calculate trade duration
    duration_text = "Unknown"
    try:
        entry_dt = datetime.strptime(entry_time.split('.')[0], "%Y-%m-%d %H:%M:%S")
        exit_dt = datetime.strptime(exit_time.split('.')[0], "%Y-%m-%d %H:%M:%S")
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
        exit_explanation = "🛑 **Stop Loss Hit** - Precio se movió contra la posición"
    elif "Trailing Stop" in exit_reason:
        exit_explanation = f"📉 **Trailing Stop Hit** - Max P&L alcanzado: +{max_pnl_pct*100:.2f}%"
    elif "Breakeven" in exit_reason:
        exit_explanation = "⚖️ **Breakeven Hit** - Trade cerrado sin pérdida"
    elif "Target Hit" in exit_reason:
        exit_explanation = "🎯 **Target Hit** - Objetivo de precio alcanzado"
    elif "Market Close" in exit_reason:
        exit_explanation = "🔔 **Market Close** - Cierre forzado por fin de día"
    elif "EOD" in exit_reason:
        exit_explanation = "⏰ **EOD Force Exit** - Próximo cierre de mercado"
    elif "Vanna" in exit_reason:
        exit_explanation = "🧲 **Vanna Shift** - Cambio en nivel Min Vanna"
    else:
        exit_explanation = f"📋 {exit_reason}"
    
    color = 0x2ECC71 if pnl_dollars >= 0 else 0xE74C3C
    emoji = "✅" if pnl_dollars >= 0 else "❌"
    result = "PROFIT" if pnl_dollars >= 0 else "LOSS"
    
    # Price movement
    price_move = exit_price - entry_price
    price_move_pct = (price_move / entry_price) * 100 if entry_price > 0 else 0
    
    embed = {
        "title": f"{emoji} LIVE {direction} CLOSED - {ticker} ({result})",
        "description": f"**{DISCORD_ROLE_PING}**\n\n{exit_explanation}",
        "color": color,
        "fields": [
            {"name": "💵 Entry", "value": f"${entry_price:.2f}", "inline": True},
            {"name": "💵 Exit", "value": f"${exit_price:.2f}", "inline": True},
            {"name": "📊 Move", "value": f"{price_move:+.2f} pts", "inline": True},
            {"name": "⏱️ Duration", "value": duration_text, "inline": True},
            {"name": "📈 Max P&L", "value": f"+{max_pnl_pct*100:.2f}%", "inline": True},
            {"name": "📊 Final P&L", "value": f"{pnl_pct:+.2f}%", "inline": True},
            {"name": f"💰 P&L (${point_value:.0f}/pt)", "value": f"**${pnl_dollars:+.2f}**", "inline": False},
        ],
        "footer": {"text": "TradingBot2 | LIVE"}
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
            return json.load(f)
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

def get_historical_levels(ticker: str, num_days: int = 5) -> Dict[str, List[float]]:
    """Get historical IB levels. Checks ib_backtest first (historical), then ib_charts."""
    levels = {"highs": [], "lows": [], "ib_highs": [], "ib_lows": []}
    today = get_ny_now().date()
    
    found = 0
    days_back = 1
    
    while found < num_days and days_back < 30:
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
                    levels["ib_highs"].append(data["analysis"].get("ib_high", 0))
                    levels["ib_lows"].append(data["analysis"].get("ib_low", 0))
                series = data.get("series", [])
                if series:
                    day_high = max([c.get("high", 0) for c in series])
                    day_low = min([c.get("low", 99999) for c in series if c.get("low", 0) > 0])
                    levels["highs"].append(day_high)
                    levels["lows"].append(day_low)
                found += 1
            except:
                pass
        days_back += 1
    
    return levels

# ============================================================================
# ANALYSIS FUNCTIONS
# ============================================================================

def get_net_exposure(data: dict, greek: str) -> float:
    """Get net Greek exposure."""
    try:
        return sum(data.get(greek, {}).get("all", []))
    except:
        return 0.0

def get_max_min_strike(data: dict, greek: str) -> Tuple[Optional[float], Optional[float]]:
    """Get strikes with max/min exposure."""
    try:
        levels = data.get("levels", [])
        vals = data.get(greek, {}).get("all", [])
        if not levels or not vals:
            return None, None
        return levels[np.argmax(vals)], levels[np.argmin(vals)]
    except:
        return None, None

def analyze_market_state(data: dict, prev_state: Optional[MarketState], spot: float) -> MarketState:
    """Analyze current market state."""
    net_gamma = get_net_exposure(data, "totalgamma")
    threshold = MIN_GAMMA_THRESHOLD if data.get("levels") and data["levels"][0] > 1000 else MIN_GAMMA_THRESHOLD / 10
    gamma_regime = "positive" if net_gamma > threshold else "negative" if net_gamma < -threshold else "neutral"
    
    net_dgex = get_net_exposure(data, "totaldgex")
    dgex_regime = "sticky" if net_dgex > 0 else "volatile"
    max_dgex, min_dgex = get_max_min_strike(data, "totaldgex")
    
    _, min_vanna_level = get_max_min_strike(data, "totalvanna")
    
    touched = False
    shift = "stable"
    if prev_state:
        if prev_state.min_vanna_touched or (min_vanna_level and is_near(spot, min_vanna_level, 0.002)):
            touched = True
        if prev_state.min_vanna_level and min_vanna_level:
            if min_vanna_level > prev_state.min_vanna_level * 1.002:
                shift = "up"
            elif min_vanna_level < prev_state.min_vanna_level * 0.998:
                shift = "down"
    
    return MarketState(gamma_regime, dgex_regime, min_vanna_level, touched, shift, max_dgex, min_dgex)

def find_nearest_resistance_support(price: float, levels: List[float]) -> Tuple[Optional[float], Optional[float]]:
    """Find nearest resistance and support."""
    if not levels:
        return None, None
    above = sorted([l for l in levels if l > price])
    below = sorted([l for l in levels if l < price])
    res = above[0] if above else None
    sup = below[-1] if below else None
    return res, sup

def calculate_fibs(high: float, low: float) -> List[float]:
    """Calculate Fibonacci levels."""
    rng = high - low
    levels = []
    for fib in FIB_LEVELS:
        levels.append(high + (rng * fib))
    for fib in FIB_LEVELS_NEG:
        levels.append(low + (rng * fib))
    return levels

def validate_target(spot: float, target: float) -> bool:
    """Validate if target is reasonable."""
    if target is None or target == 0:
        return False
    dist_pct = abs(target - spot) / spot
    if dist_pct > MAX_LEVEL_DIST_PCT or dist_pct < MIN_TARGET_DIST:
        return False
    stop_dist = spot * STOP_LOSS_FIXED
    risk_reward = abs(target - spot) / stop_dist
    return risk_reward >= MIN_RISK_REWARD

def generate_signal(ticker: str, spot: float, state: MarketState, levels: List[float], 
                   time_of_day: dt_time) -> Tuple[str, str, float, str, str]:
    """Generate trading signal."""
    res, sup = find_nearest_resistance_support(spot, levels)
    
    # 1. UNTOUCHED VANNA MAGNET
    if state.min_vanna_level and not state.min_vanna_touched:
        if validate_target(spot, state.min_vanna_level):
            if state.min_vanna_level < spot and res and is_near(spot, res):
                details = f"📉 REVERSAL SHORT\n   • Trigger: Res at {res:.2f}\n   • Target: Min Vanna at {state.min_vanna_level:.2f}"
                return "SHORT", "REVERSAL", state.min_vanna_level, "Res Rejection -> Untouched Vanna", details
            if state.min_vanna_level > spot and sup and is_near(spot, sup):
                details = f"📈 REVERSAL LONG\n   • Trigger: Sup at {sup:.2f}\n   • Target: Min Vanna at {state.min_vanna_level:.2f}"
                return "LONG", "REVERSAL", state.min_vanna_level, "Sup Bounce -> Untouched Vanna", details

    # 2. GAMMA/DGEX REVERSION
    if state.gamma_regime == "positive" or state.dgex_regime == "sticky":
        if res and is_near(spot, res):
            targets = []
            if state.max_dgex_magnet and state.max_dgex_magnet < spot:
                targets.append(state.max_dgex_magnet)
            if sup:
                targets.append(sup)
            for t in targets:
                if validate_target(spot, t):
                    details = f"📉 POS GAMMA SHORT\n   • Trigger: Res at {res:.2f}\n   • Target: {t:.2f}"
                    return "SHORT", "REVERSAL", t, f"Pos Gamma Rejection at {res:.1f}", details
        
        if sup and is_near(spot, sup):
            targets = []
            if state.max_dgex_magnet and state.max_dgex_magnet > spot:
                targets.append(state.max_dgex_magnet)
            if res:
                targets.append(res)
            for t in targets:
                if validate_target(spot, t):
                    details = f"📈 POS GAMMA LONG\n   • Trigger: Sup at {sup:.2f}\n   • Target: {t:.2f}"
                    return "LONG", "REVERSAL", t, f"Pos Gamma Bounce at {sup:.1f}", details

    # 3. MOMENTUM BREAKOUT
    if time_of_day >= IB_FORMATION_END and (state.gamma_regime == "negative" or state.dgex_regime == "volatile"):
        if sup and spot < sup * 0.999 and spot > sup * 0.995:
            target = state.min_dgex_accel if state.min_dgex_accel and state.min_dgex_accel < spot else spot * 0.985
            if validate_target(spot, target):
                details = f"💥 NEG GAMMA BREAKDOWN\n   • Trigger: Broken Sup at {sup:.2f}\n   • Target: {target:.2f}"
                return "SHORT", "MOMENTUM", target, f"Neg Gamma Breakdown of {sup:.1f}", details
        
        if res and spot > res * 1.001 and spot < res * 1.005:
            target = state.min_dgex_accel if state.min_dgex_accel and state.min_dgex_accel > spot else spot * 1.015
            if validate_target(spot, target):
                details = f"🚀 NEG GAMMA BREAKOUT\n   • Trigger: Broken Res at {res:.2f}\n   • Target: {target:.2f}"
                return "LONG", "MOMENTUM", target, f"Neg Gamma Breakout of {res:.1f}", details

    return None, None, None, None, None

# ============================================================================
# MAIN TRADING LOOP
# ============================================================================

async def main_loop():
    """Main trading loop."""
    print("=" * 60)
    print("TRADINGBOT2 - LIVE SIMPLIFIED STRATEGY")
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
    market_states: Dict[str, MarketState] = {t: None for t in TICKERS}
    last_exit_times: Dict[str, Optional[datetime]] = {t: None for t in TICKERS}
    prev_levels: Dict[str, dict] = {}
    current_day_ib: Dict[str, dict] = {}
    
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
                if ny_now.time() > MARKET_CLOSE:
                    market_states = {t: None for t in TICKERS}
                    last_exit_times = {t: None for t in TICKERS}
                    prev_levels = {}
                    current_day_ib = {}
                    current_trade = None
                
                await asyncio.sleep(20)
                continue
            
            curr_time = get_ny_now()
            curr_time_time = curr_time.time()
            print(f"\n[{curr_time.strftime('%H:%M:%S')}] Checking data...")
            
            # Load historical levels if not loaded
            if not prev_levels:
                for t in TICKERS:
                    prev_levels[t] = get_historical_levels(t)
                print("  Loaded historical levels")
            
            # Load current day IB
            for t in TICKERS:
                ib = get_current_ib_data(t)
                if ib:
                    current_day_ib[t] = ib.get("analysis", {})
            
            # Force exit at market close
            if curr_time_time >= MARKET_CLOSE:
                if current_trade:
                    data = get_latest_greek_file(current_trade.ticker)
                    spot = data.get("spot_price", current_trade.entry.price) if data else current_trade.entry.price
                    pnl_pts = spot - current_trade.entry.price if current_trade.direction == "LONG" else current_trade.entry.price - spot
                    val = get_dollar_value(current_trade.ticker, pnl_pts)
                    current_trade.exit = TradeExit(str(curr_time), spot, "Market Close")
                    current_trade.pnl = TradePnL(pnl_pts, (pnl_pts/current_trade.entry.price)*100, val)
                    all_trades.append(current_trade)
                    print(f"  [CLOSED] {current_trade.ticker} (Market Close): ${val:.2f}")
                    send_discord_trade_close(current_trade)
                    current_trade = None
                await asyncio.sleep(20)
                continue
            
            # Process each ticker
            current_spots = {}
            active_levels = {}
            
            for t in TICKERS:
                data = get_latest_greek_file(t)
                if not data:
                    continue
                
                spot = data.get("spot_price", 0)
                if spot == 0:
                    continue
                
                current_spots[t] = spot
                market_states[t] = analyze_market_state(data, market_states[t], spot)
                
                # Build levels
                raw_levels = []
                raw_levels.extend(prev_levels.get(t, {}).get("highs", []))
                raw_levels.extend(prev_levels.get(t, {}).get("lows", []))
                raw_levels.extend(prev_levels.get(t, {}).get("ib_highs", []))
                raw_levels.extend(prev_levels.get(t, {}).get("ib_lows", []))
                
                if is_past_ib_formation():
                    ib = current_day_ib.get(t, {})
                    if ib.get("ib_high"):
                        raw_levels.append(ib["ib_high"])
                        raw_levels.extend(calculate_fibs(ib["ib_high"], ib.get("ib_low", ib["ib_high"])))
                    if ib.get("ib_low"):
                        raw_levels.append(ib["ib_low"])
                
                active_levels[t] = [l for l in raw_levels if l > 0 and abs(l - spot)/spot <= MAX_LEVEL_DIST_PCT]
                
                print(f"  [{t}] Spot: {spot:.2f} | Gamma: {market_states[t].gamma_regime if market_states[t] else 'N/A'}")
                logger.debug(f"[{t}] Market state: gamma={market_states[t].gamma_regime}, dgex={market_states[t].dgex_regime}, min_vanna={f'{market_states[t].min_vanna_level:.2f}' if market_states[t].min_vanna_level else 'None'}")
            
            # Manage open trade
            if current_trade:
                t = current_trade.ticker
                if t in current_spots:
                    spot = current_spots[t]
                    state = market_states[t]
                    
                    if current_trade.direction == "LONG":
                        curr_pnl_pct = (spot - current_trade.entry.price) / current_trade.entry.price
                    else:
                        curr_pnl_pct = (current_trade.entry.price - spot) / current_trade.entry.price
                    
                    if curr_pnl_pct > current_trade.highest_pnl_pct:
                        current_trade.highest_pnl_pct = curr_pnl_pct
                    
                    should_exit = False
                    exit_reason = ""
                    
                    if curr_time_time >= FORCE_EXIT_TIME:
                        should_exit = True
                        exit_reason = "EOD Force Exit"
                    elif current_trade.highest_pnl_pct >= BREAKEVEN_TRIGGER:
                        dynamic_stop = current_trade.highest_pnl_pct - TRAILING_STEP
                        if dynamic_stop < 0:
                            dynamic_stop = 0.0005
                        if curr_pnl_pct < dynamic_stop:
                            should_exit = True
                            exit_reason = "Trailing Stop" if dynamic_stop > 0.001 else "Breakeven Hit"
                    elif curr_pnl_pct < -STOP_LOSS_FIXED:
                        should_exit = True
                        exit_reason = "Stop Loss"
                    elif current_trade.target_level:
                        if current_trade.direction == "LONG" and spot >= current_trade.target_level * 0.9995:
                            should_exit = True
                            exit_reason = "Target Hit"
                        elif current_trade.direction == "SHORT" and spot <= current_trade.target_level * 1.0005:
                            should_exit = True
                            exit_reason = "Target Hit"
                    
                    if should_exit:
                        pnl_pts = spot - current_trade.entry.price if current_trade.direction == "LONG" else current_trade.entry.price - spot
                        val = get_dollar_value(t, pnl_pts)
                        current_trade.exit = TradeExit(str(curr_time), spot, exit_reason)
                        current_trade.pnl = TradePnL(pnl_pts, curr_pnl_pct*100, val)
                        all_trades.append(current_trade)
                        last_exit_times[t] = curr_time
                        
                        emoji = "✅" if val > 0 else "❌"
                        print(f"  {emoji} CLOSED {t} | {exit_reason} | ${val:+.2f}")
                        logger.info(f"[TRADE CLOSED] {current_trade.direction} {t} @ {spot:.2f}")
                        logger.info(f"  └─ Reason: {exit_reason}")
                        logger.info(f"  └─ P&L: {pnl_pts:+.2f} pts ({curr_pnl_pct*100:+.2f}%) = ${val:+.2f}")
                        logger.info(f"  └─ Max P&L during trade: +{current_trade.highest_pnl_pct*100:.2f}%")
                        send_discord_trade_close(current_trade)
                        current_trade = None

                        save_active_trade(None)
            
            # Look for new entry
            if current_trade is None and curr_time_time < LAST_ENTRY_TIME:
                best_signal = None
                
                for t in TICKERS:
                    if t not in current_spots:
                        logger.debug(f"[{t}] No spot price available - skipping")
                        continue
                    
                    if last_exit_times[t]:
                        mins_since = (curr_time - last_exit_times[t]).total_seconds() / 60
                        if mins_since < COOLDOWN_MINUTES:
                            remaining = COOLDOWN_MINUTES - mins_since
                            logger.debug(f"[{t}] Cooldown: {remaining:.0f} min remaining")
                            continue
                    
                    direction, strategy, target, reason, details = generate_signal(
                        t, current_spots[t], market_states[t], active_levels.get(t, []), curr_time_time
                    )
                    
                    # Log signal evaluation
                    if direction:
                        # --- FIX APPLIED HERE: Format the string safely first ---
                        target_str = f"{target:.2f}" if target else "None"
                        logger.info(f"[{t}] Signal found: {direction} {strategy} target={target_str}")
                        logger.info(f"  └─ Reason: {reason}")

                    else:
                        logger.debug(f"[{t}] No signal generated")
                    
                    if direction:
                        if best_signal is None or (target is not None and best_signal[3] is None):
                            best_signal = (t, direction, strategy, target, reason, details)
                
                if best_signal:
                    t, direct, strat, targ, reas, details = best_signal
                    trade_counter += 1
                    current_trade = Trade(
                        trade_counter, t, direct, strat,
                        TradeEntry(str(curr_time), current_spots[t], reas, details),
                        None, None, targ, STOP_LOSS_FIXED
                    )
                    
                    # Calculate R:R for logging
                    stop_dist = current_spots[t] * STOP_LOSS_FIXED
                    target_dist = abs(targ - current_spots[t]) if targ else 0
                    rr_ratio = target_dist / stop_dist if stop_dist > 0 else 0
                    
                    print(f"  🔔 OPEN {direct} {t} @ {current_spots[t]:.2f}")
                    print(f"  {details}")
                    logger.info(f"[TRADE OPENED] {direct} {t} @ {current_spots[t]:.2f}")
                    logger.info(f"  └─ Strategy: {strat}")
                    logger.info(f"  └─ Reason: {reas}")
                    targ_str = f"{targ:.2f}" if targ else "None"
                    logger.info(f"  └─ Target: {targ_str}")
                    
                    logger.info(f"  └─ Stop: {current_spots[t]*(1-STOP_LOSS_FIXED) if direct=='LONG' else current_spots[t]*(1+STOP_LOSS_FIXED):.2f}")
                    logger.info(f"  └─ R:R Ratio: 1:{rr_ratio:.1f}")
                    logger.info(f"  └─ R:R Ratio: 1:{rr_ratio:.1f}")
                    save_active_trade(current_trade)
                    send_discord_trade_open(current_trade)
            
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
    print("STARTING TRADINGBOT2 - LIVE TRADING")
    print("=" * 60 + "\n")
    
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("\n[STOP] Stopped by user.")
