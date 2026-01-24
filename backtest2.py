import os
import json
import glob
import re
import csv
import requests
import asyncio
from datetime import datetime, timedelta, time as dt_time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import numpy as np
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

GREEK_DATA_DIR = "/home/Option-Greeks-Plotting-Discord-Bot/json_data"
IB_DATA_DIR = "/home/Option-Greeks-Plotting-Discord-Bot/ib_backtest"
TRADES_OUTPUT_DIR = "./trades"
TICKERS = ["SPX", "SPY", "QQQ"]
BACKTEST_DAYS = ["20260120", "20260121", "20260122", "20260123"]

MARKET_OPEN = dt_time(9, 30)
MARKET_CLOSE = dt_time(16, 0)
FORCE_EXIT_TIME = dt_time(15, 55)
IB_FORMATION_END = dt_time(10, 30)
LAST_ENTRY_TIME = dt_time(15, 15)

FIB_LEVELS = [0.272, 0.5, 0.618, 1.0, 1.272, 1.618, 2.0, 2.272]
FIB_LEVELS_NEG = [-0.272, -0.5, -0.618, -1.0, -1.272]

# --- PARÁMETROS DE GESTIÓN DE RIESGO ---
MIN_GAMMA_THRESHOLD = 0.5 
MIN_DGEX_THRESHOLD = 0.5
PROXIMITY_PCT = 0.0015     
MAX_LEVEL_DIST_PCT = 0.02  

# Reglas de Trading
STOP_LOSS_FIXED = 0.003    
BREAKEVEN_TRIGGER = 0.0025 
TRAILING_STEP = 0.002      
MIN_TARGET_DIST = 0.0015   
MIN_RISK_REWARD = 1.2      
COOLDOWN_MINUTES = 30      

# ============================================================================
# DISCORD NOTIFICATIONS
# ============================================================================

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
DISCORD_CHANNEL_ID = 1464600897404276841
DISCORD_ROLE_PING = "<@&1464601287411634226>"
DISCORD_ENABLED = True

def send_discord_trade_open(trade: "Trade"):
    """Sends trade OPEN notification to Discord."""
    if not DISCORD_ENABLED or not DISCORD_WEBHOOK_URL:
        return
    
    ticker = trade.ticker
    direction = trade.direction
    entry_price = trade.entry.price
    entry_time = trade.entry.time
    reason = trade.entry.reason
    details = trade.entry.setup_details
    target = trade.target_level
    stop_pct = STOP_LOSS_FIXED
    
    point_value = POINT_VALUES.get(ticker, 10.0)
    stop_price = entry_price * (1 - stop_pct) if direction == "LONG" else entry_price * (1 + stop_pct)
    risk_dollars = abs(entry_price - stop_price) * point_value
    reward_dollars = abs(target - entry_price) * point_value if target else 0
    
    color = 0x2ECC71 if direction == "LONG" else 0xE74C3C
    emoji = "📈" if direction == "LONG" else "📉"
    
    embed = {
        "title": f"{emoji} {direction} OPENED - {ticker}",
        "description": f"**{DISCORD_ROLE_PING}**\n\n**Setup:** {reason}\n{details}",
        "color": color,
        "fields": [
            {"name": "💵 Entry", "value": f"${entry_price:.2f}", "inline": True},
            {"name": "🎯 Target", "value": f"${target:.2f}" if target else "N/A", "inline": True},
            {"name": "🛑 Stop Loss", "value": f"${stop_price:.2f} ({stop_pct*100:.1f}%)", "inline": True},
            {"name": "💰 Risk/Reward ($)", "value": f"Risk: ${risk_dollars:.2f} | Reward: ${reward_dollars:.2f}", "inline": False},
            {"name": "📊 Point Value", "value": f"${point_value:.0f}/pt", "inline": True},
            {"name": "⏰ Time (NYC)", "value": entry_time, "inline": True},
        ],
        "footer": {"text": "Greek Exposure Strategy v2"}
    }
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=5)
        if response.status_code >= 400:
            print(f"[DISCORD] Error: {response.status_code}")
    except Exception as e:
        print(f"[DISCORD] Failed: {e}")

def send_discord_trade_close(trade: "Trade"):
    """Sends trade CLOSE notification to Discord with P&L in dollars."""
    if not DISCORD_ENABLED or not DISCORD_WEBHOOK_URL or not trade.exit or not trade.pnl:
        return
    
    ticker = trade.ticker
    direction = trade.direction
    entry_price = trade.entry.price
    exit_price = trade.exit.price
    exit_time = trade.exit.time
    exit_reason = trade.exit.reason
    pnl_points = trade.pnl.points
    pnl_pct = trade.pnl.percent
    pnl_dollars = trade.pnl.dollars
    
    point_value = POINT_VALUES.get(ticker, 10.0)
    color = 0x2ECC71 if pnl_dollars >= 0 else 0xE74C3C
    emoji = "✅" if pnl_dollars >= 0 else "❌"
    result = "PROFIT" if pnl_dollars >= 0 else "LOSS"
    
    embed = {
        "title": f"{emoji} {direction} CLOSED - {ticker} ({result})",
        "description": f"**{DISCORD_ROLE_PING}**\n\n**Exit Reason:** {exit_reason}",
        "color": color,
        "fields": [
            {"name": "💵 Entry", "value": f"${entry_price:.2f}", "inline": True},
            {"name": "💵 Exit", "value": f"${exit_price:.2f}", "inline": True},
            {"name": "⏰ Time (NYC)", "value": exit_time, "inline": True},
            {"name": "📊 P&L Points", "value": f"{pnl_points:+.2f} pts", "inline": True},
            {"name": "📊 P&L %", "value": f"{pnl_pct:+.2f}%", "inline": True},
            {"name": f"💰 P&L (${point_value:.0f}/pt)", "value": f"**${pnl_dollars:+.2f}**", "inline": True},
        ],
        "footer": {"text": "Greek Exposure Strategy v2"}
    }
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=5)
        if response.status_code >= 400:
            print(f"[DISCORD] Error: {response.status_code}")
    except Exception as e:
        print(f"[DISCORD] Failed: {e}")

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
    setup_details: str # Nueva info detallada

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

POINT_VALUES = {"SPX": 10.0, "SPY": 100.0, "QQQ": 400.0}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_dollar_value(ticker: str, points: float) -> float:
    return points * POINT_VALUES.get(ticker, 100.0)

def parse_greek_filename(filename: str) -> Tuple[str, str, datetime]:
    pattern = r"(\w+)_(0dte|weekly|all)_ExposureData_(\d{8})_(\d{6})\.json"
    match = re.match(pattern, os.path.basename(filename))
    if not match: return None, None, None
    ticker, expiry, date_str, time_str = match.groups()
    dt_cet = datetime.strptime(f"{date_str} {time_str}", "%Y%m%d %H%M%S")
    dt_nyc = dt_cet - timedelta(hours=6) 
    return ticker, expiry, dt_nyc

def load_greek_files_for_day(day: str, tickers: List[str]) -> Dict[str, List[dict]]:
    result = {t: [] for t in tickers}
    pattern = os.path.join(GREEK_DATA_DIR, f"*_0dte_ExposureData_{day}_*.json")
    files = glob.glob(pattern)
    print(f"  Found {len(files)} files for {day}")
    for filepath in files:
        ticker, expiry, dt_nyc = parse_greek_filename(filepath)
        if ticker in tickers and expiry == "0dte":
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    result[ticker].append({"datetime": dt_nyc, "data": data})
            except Exception: pass
    for t in result: result[t].sort(key=lambda x: x["datetime"])
    return result

# ============================================================================
# LEVEL CALCULATIONS
# ============================================================================

def get_historical_levels(ticker: str, current_day: str, num_days: int = 5) -> Dict[str, List[float]]:
    levels = {"highs": [], "lows": [], "ib_highs": [], "ib_lows": []}
    current_date = datetime.strptime(current_day, "%Y%m%d")
    found = 0
    days_back = 1
    while found < num_days and days_back < 30:
        prev_date = current_date - timedelta(days=days_back)
        d_str = prev_date.strftime("%Y%m%d")
        path = os.path.join(IB_DATA_DIR, f"ib_data_{ticker}_{d_str}.json")
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
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
            except: pass
        days_back += 1
    return levels

def calculate_fibs(high: float, low: float) -> List[float]:
    rng = high - low
    levels = []
    for fib in FIB_LEVELS: levels.append(high + (rng * fib))
    for fib in FIB_LEVELS_NEG: levels.append(low + (rng * fib))
    return levels

def find_nearest_resistance_support(price: float, levels: List[float]) -> Tuple[Optional[float], Optional[float]]:
    if not levels: return None, None
    above = sorted([l for l in levels if l > price])
    below = sorted([l for l in levels if l < price])
    res = above[0] if above else None
    sup = below[-1] if below else None
    return res, sup

def is_near(price: float, level: float, pct: float = PROXIMITY_PCT) -> bool:
    if level is None or level == 0: return False
    return abs(price - level) / level <= pct

# ============================================================================
# ANALYSIS & STRATEGY
# ============================================================================

def get_net_exposure(data: dict, greek: str) -> float:
    try: return sum(data.get(greek, {}).get("all", []))
    except: return 0.0

def get_max_min_strike(data: dict, greek: str) -> Tuple[Optional[float], Optional[float]]:
    try:
        levels = data.get("levels", [])
        vals = data.get(greek, {}).get("all", [])
        if not levels or not vals: return None, None
        return levels[np.argmax(vals)], levels[np.argmin(vals)]
    except: return None, None

def analyze_market_state(data: dict, prev_state: Optional[MarketState], spot: float) -> MarketState:
    net_gamma = get_net_exposure(data, "totalgamma")
    threshold = MIN_GAMMA_THRESHOLD if "levels" in data and data["levels"][0] > 1000 else MIN_GAMMA_THRESHOLD / 10
    gamma_regime = "positive" if net_gamma > threshold else "negative" if net_gamma < -threshold else "neutral"
    
    net_dgex = get_net_exposure(data, "totaldgex")
    dgex_regime = "sticky" if net_dgex > 0 else "volatile"
    max_dgex, min_dgex = get_max_min_strike(data, "totaldgex")
    
    _, min_vanna_level = get_max_min_strike(data, "totalvanna")
    v_vals = data.get("totalvanna", {}).get("all", [])
    levels = data.get("levels", [])
    if v_vals and levels: min_vanna_level = levels[np.argmin(v_vals)]
    
    touched = False
    shift = "stable"
    if prev_state:
        if prev_state.min_vanna_touched or (min_vanna_level and is_near(spot, min_vanna_level, 0.002)):
            touched = True
        if prev_state.min_vanna_level and min_vanna_level:
            if min_vanna_level > prev_state.min_vanna_level * 1.002: shift = "up"
            elif min_vanna_level < prev_state.min_vanna_level * 0.998: shift = "down"
    
    return MarketState(gamma_regime, dgex_regime, min_vanna_level, touched, shift, max_dgex, min_dgex)

def check_confluence_risk(current_ticker: str, tickers_data: dict, all_tickers_levels: dict) -> int:
    bias = 0 
    for t, spot_price in tickers_data.items():
        if t == current_ticker: continue
        levels = all_tickers_levels.get(t, [])
        res, sup = find_nearest_resistance_support(spot_price, levels)
        if res and is_near(spot_price, res): bias -= 1
        if sup and is_near(spot_price, sup): bias += 1
    return bias

def validate_target(spot: float, target: float) -> bool:
    if target is None or target == 0: return False
    dist_to_target = abs(target - spot)
    dist_pct = dist_to_target / spot
    if dist_pct > MAX_LEVEL_DIST_PCT: return False
    if dist_pct < MIN_TARGET_DIST: return False
    stop_dist = spot * STOP_LOSS_FIXED
    risk_reward = dist_to_target / stop_dist
    if risk_reward < MIN_RISK_REWARD: return False
    return True

def generate_signal(ticker: str, spot: float, state: MarketState, levels: List[float], confluence_bias: int, time_of_day: dt_time) -> Tuple[str, str, float, str, str]:
    """
    Returns: (Direction, Strategy, Target, ReasonShort, DetailsString)
    """
    res, sup = find_nearest_resistance_support(spot, levels)
    
    # 1. UNTOUCHED VANNA MAGNET
    if state.min_vanna_level and not state.min_vanna_touched:
        if validate_target(spot, state.min_vanna_level):
            # SHORT
            if state.min_vanna_level < spot and res and is_near(spot, res):
                if confluence_bias <= 0:
                    details = f"📉 REVERSAL SHORT\n   • Trigger: Resistance Rejection at {res:.2f}\n   • Target: Untouched Min Vanna at {state.min_vanna_level:.2f}"
                    return "SHORT", "REVERSAL", state.min_vanna_level, "Res Rejection -> Untouched Vanna", details
            # LONG
            if state.min_vanna_level > spot and sup and is_near(spot, sup):
                if confluence_bias >= 0:
                    details = f"📈 REVERSAL LONG\n   • Trigger: Support Bounce at {sup:.2f}\n   • Target: Untouched Min Vanna at {state.min_vanna_level:.2f}"
                    return "LONG", "REVERSAL", state.min_vanna_level, "Sup Bounce -> Untouched Vanna", details

    # 2. GAMMA/DGEX REVERSION
    if state.gamma_regime == "positive" or state.dgex_regime == "sticky":
        # SHORT
        if res and is_near(spot, res) and confluence_bias <= 0:
            potential_targets = []
            if state.max_dgex_magnet and state.max_dgex_magnet < spot: potential_targets.append(state.max_dgex_magnet)
            if sup: potential_targets.append(sup)
            
            for t in potential_targets:
                if validate_target(spot, t):
                    target_name = "Max DGEX Magnet" if t == state.max_dgex_magnet else "Nearest Support"
                    details = f"📉 POS GAMMA SHORT\n   • Trigger: Resistance Rejection at {res:.2f}\n   • Target: {target_name} at {t:.2f}"
                    return "SHORT", "REVERSAL", t, f"Pos Gamma Rejection at {res:.1f}", details
        
        # LONG
        if sup and is_near(spot, sup) and confluence_bias >= 0:
            potential_targets = []
            if state.max_dgex_magnet and state.max_dgex_magnet > spot: potential_targets.append(state.max_dgex_magnet)
            if res: potential_targets.append(res)
            
            for t in potential_targets:
                if validate_target(spot, t):
                    target_name = "Max DGEX Magnet" if t == state.max_dgex_magnet else "Nearest Resistance"
                    details = f"📈 POS GAMMA LONG\n   • Trigger: Support Bounce at {sup:.2f}\n   • Target: {target_name} at {t:.2f}"
                    return "LONG", "REVERSAL", t, f"Pos Gamma Bounce at {sup:.1f}", details

    # 3. MOMENTUM BREAKOUT
    if time_of_day >= IB_FORMATION_END and (state.gamma_regime == "negative" or state.dgex_regime == "volatile"):
        # SHORT
        if sup and spot < sup * 0.999 and spot > sup * 0.995: 
             target = state.min_dgex_accel if state.min_dgex_accel and state.min_dgex_accel < spot else spot * 0.985
             if validate_target(spot, target):
                target_name = "Min DGEX Accelerator" if target == state.min_dgex_accel else "Calc Breakdown Target"
                details = f"💥 NEG GAMMA BREAKDOWN\n   • Trigger: Broken Support at {sup:.2f}\n   • Target: {target_name} at {target:.2f}"
                return "SHORT", "MOMENTUM", target, f"Neg Gamma Breakdown of {sup:.1f}", details
        
        # LONG
        if res and spot > res * 1.001 and spot < res * 1.005:
             target = state.min_dgex_accel if state.min_dgex_accel and state.min_dgex_accel > spot else spot * 1.015
             if validate_target(spot, target):
                target_name = "Min DGEX Accelerator" if target == state.min_dgex_accel else "Calc Breakout Target"
                details = f"🚀 NEG GAMMA BREAKOUT\n   • Trigger: Broken Resistance at {res:.2f}\n   • Target: {target_name} at {target:.2f}"
                return "LONG", "MOMENTUM", target, f"Neg Gamma Breakout of {res:.1f}", details

    return None, None, None, None, None

# ============================================================================
# MAIN
# ============================================================================

def run_backtest():
    if not os.path.exists(TRADES_OUTPUT_DIR): os.makedirs(TRADES_OUTPUT_DIR)
    
    all_trades = []
    trade_id_counter = 0
    current_trade: Optional[Trade] = None
    last_known_spots = {}
    last_exit_times = {t: None for t in TICKERS} 
    
    for day in BACKTEST_DAYS:
        print(f"\n{'='*60}\n📅 PROCESSING DAY: {day}\n{'='*60}")
        greek_data = load_greek_files_for_day(day, TICKERS)
        if not any(greek_data.values()): continue
        
        prev_levels = {}
        for t in TICKERS: prev_levels[t] = get_historical_levels(t, day)
        
        current_day_ib = {}
        try:
            for t in TICKERS:
                with open(os.path.join(IB_DATA_DIR, f"ib_data_{t}_{day}.json")) as f:
                    current_day_ib[t] = json.load(f).get("analysis", {})
        except: pass

        timeline = defaultdict(dict)
        for t, entries in greek_data.items():
            for e in entries:
                t_stamp = e["datetime"].replace(second=0, microsecond=0)
                timeline[t_stamp][t] = e["data"]
        
        sorted_times = sorted(timeline.keys())
        market_states = {t: None for t in TICKERS}
        
        for curr_time in sorted_times:
            curr_time_time = curr_time.time()
            
            # --- FORCE EXIT AT MARKET CLOSE ---
            if curr_time_time >= MARKET_CLOSE:
                if current_trade:
                    spot = timeline[curr_time].get(current_trade.ticker, {}).get("spot_price", current_trade.entry.price)
                    pnl_pts = spot - current_trade.entry.price if current_trade.direction == "LONG" else current_trade.entry.price - spot
                    val = get_dollar_value(current_trade.ticker, pnl_pts)
                    current_trade.exit = TradeExit(str(curr_time), spot, "Market Close")
                    current_trade.pnl = TradePnL(pnl_pts, (pnl_pts/current_trade.entry.price)*100, val)
                    all_trades.append(current_trade)
                    print(f"[{curr_time.time()}] 🔴 CLOSED {current_trade.ticker} (Market Close): ${val:.2f}")
                    send_discord_trade_close(current_trade)
                    current_trade = None
                continue
                
            if curr_time_time < MARKET_OPEN: continue

            current_spots = {}
            active_levels = {} 
            
            for t in TICKERS:
                if t not in timeline[curr_time]: continue
                data = timeline[curr_time][t]
                spot = data.get("spot_price", 0)
                current_spots[t] = spot
                last_known_spots[t] = spot
                market_states[t] = analyze_market_state(data, market_states[t], spot)
                
                raw_levels = []
                raw_levels.extend(prev_levels[t]["highs"])
                raw_levels.extend(prev_levels[t]["lows"])
                raw_levels.extend(prev_levels[t]["ib_highs"])
                raw_levels.extend(prev_levels[t]["ib_lows"])
                
                if curr_time_time >= IB_FORMATION_END:
                    ib = current_day_ib.get(t, {})
                    if ib.get("ib_high"): 
                        raw_levels.append(ib["ib_high"])
                        raw_levels.extend(calculate_fibs(ib["ib_high"], ib["ib_low"]))
                    if ib.get("ib_low"):
                        raw_levels.append(ib["ib_low"])
                
                active_levels[t] = [l for l in raw_levels if l > 0 and abs(l - spot)/spot <= MAX_LEVEL_DIST_PCT]

            # --- MANAGE OPEN TRADE ---
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
                         should_exit = True; exit_reason = "EOD Force Exit"

                    elif current_trade.highest_pnl_pct >= BREAKEVEN_TRIGGER:
                        dynamic_stop_pct = current_trade.highest_pnl_pct - TRAILING_STEP
                        if dynamic_stop_pct < 0: dynamic_stop_pct = 0.0005 
                        
                        if curr_pnl_pct < dynamic_stop_pct:
                            should_exit = True
                            if dynamic_stop_pct <= 0.001: exit_reason = "Breakeven Hit"
                            else: exit_reason = "Trailing Stop Hit"
                    
                    elif curr_pnl_pct < -STOP_LOSS_FIXED:
                        should_exit = True; exit_reason = "Stop Loss"
                        
                    elif current_trade.target_level:
                        exit_buffer = 0.0005
                        if current_trade.direction == "LONG":
                            target_price = current_trade.target_level * (1 - exit_buffer)
                            if spot >= target_price:
                                should_exit = True; exit_reason = "Target Hit"
                        elif current_trade.direction == "SHORT":
                            target_price = current_trade.target_level * (1 + exit_buffer)
                            if spot <= target_price:
                                should_exit = True; exit_reason = "Target Hit"
                    
                    elif current_trade.strategy == "REVERSAL":
                        if state.min_vanna_shift == "up" and current_trade.direction == "SHORT":
                            should_exit = True; exit_reason = "Vanna Shifted Up"
                        if state.min_vanna_shift == "down" and current_trade.direction == "LONG":
                            should_exit = True; exit_reason = "Vanna Shifted Down"

                    if should_exit:
                        pnl_pts = spot - current_trade.entry.price if current_trade.direction == "LONG" else current_trade.entry.price - spot
                        val = get_dollar_value(t, pnl_pts)
                        current_trade.exit = TradeExit(str(curr_time), spot, exit_reason)
                        current_trade.pnl = TradePnL(pnl_pts, curr_pnl_pct*100, val)
                        all_trades.append(current_trade)
                        
                        last_exit_times[t] = curr_time
                        
                        # --- VERBOSE EXIT PRINT ---
                        emoji = "✅" if val > 0 else "❌"
                        print(f"[{curr_time.time()}] {emoji} CLOSED {t} {current_trade.direction}")
                        print(f"   • Reason: {exit_reason}")
                        print(f"   • Exit Price: {spot:.2f}")
                        print(f"   • P&L: {pnl_pts:.2f} pts ({curr_pnl_pct*100:.2f}%) -> ${val:+.2f}")
                        print("-" * 50)
                        
                        # Send Discord notification
                        send_discord_trade_close(current_trade)
                        
                        current_trade = None
                        continue

            # --- LOOK FOR NEW ENTRY ---
            if current_trade is None and curr_time_time < LAST_ENTRY_TIME:
                best_signal = None
                for t in TICKERS:
                    if t not in current_spots: continue
                    
                    if last_exit_times[t]:
                        mins_since = (curr_time - last_exit_times[t]).total_seconds() / 60
                        if mins_since < COOLDOWN_MINUTES: continue

                    conf_bias = check_confluence_risk(t, current_spots, active_levels)
                    direction, strategy, target, reason, details = generate_signal(
                        t, current_spots[t], market_states[t], active_levels[t], conf_bias, curr_time_time
                    )
                    
                    if direction:
                         if best_signal is None or (target is not None and best_signal[3] is None):
                            best_signal = (t, direction, strategy, target, reason, details)
                
                if best_signal:
                    t, direct, strat, targ, reas, details = best_signal
                    trade_id_counter += 1
                    current_trade = Trade(
                        trade_id_counter, t, direct, strat, 
                        TradeEntry(str(curr_time), current_spots[t], reas, details), 
                        None, None, targ, STOP_LOSS_FIXED
                    )
                    
                    # --- VERBOSE ENTRY PRINT ---
                    dist_target = abs(targ - current_spots[t])
                    dist_stop = current_spots[t] * STOP_LOSS_FIXED
                    rr_ratio = dist_target / dist_stop
                    
                    print(f"[{curr_time.time()}] 🔔 OPEN {direct} {t} @ {current_spots[t]:.2f}")
                    print(f"{details}")
                    print(f"   • Stop Loss: ~{current_spots[t]*(1-STOP_LOSS_FIXED) if direct=='LONG' else current_spots[t]*(1+STOP_LOSS_FIXED):.2f} (Fixed 0.3%)")
                    print(f"   • Est. Risk/Reward: {rr_ratio:.2f}")
                    print("-" * 50)
                    
                    # Send Discord notification
                    send_discord_trade_open(current_trade)

        # EOD CLEANUP
        if current_trade:
            t = current_trade.ticker
            exit_price = last_known_spots.get(t, current_trade.entry.price)
            pnl_pts = exit_price - current_trade.entry.price if current_trade.direction == "LONG" else current_trade.entry.price - exit_price
            val = get_dollar_value(t, pnl_pts)
            current_trade.exit = TradeExit(f"{day} 16:00:00", exit_price, "EOD Cleanup")
            current_trade.pnl = TradePnL(pnl_pts, (pnl_pts/current_trade.entry.price)*100, val)
            all_trades.append(current_trade)
            print(f"[EOD CLEANUP] CLOSED {t}: ${val:.2f}")
            send_discord_trade_close(current_trade)
            current_trade = None

    # Summary
    print("\n" + "="*50)
    print("BACKTEST SUMMARY")
    print("="*50)
    total_pl = sum([t.pnl.dollars for t in all_trades if t.pnl])
    wins = len([t for t in all_trades if t.pnl and t.pnl.dollars > 0])
    print(f"Total Trades: {len(all_trades)}")
    print(f"Wins: {wins} | Win Rate: {(wins/len(all_trades)*100 if all_trades else 0):.1f}%")
    print(f"Total P&L: ${total_pl:.2f}")
    
    # Save CSV
    with open("backtest_summary.csv", "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["ID", "Ticker", "Direction", "Entry Time", "Entry Price", "Exit Time", "Exit Price", "PnL $", "Reason"])
        for t in all_trades:
            writer.writerow([
                t.trade_id, t.ticker, t.direction, t.entry.time, t.entry.price, 
                t.exit.time, t.exit.price, t.pnl.dollars, t.exit.reason
            ])

    for t in all_trades:
        fname = f"trade_{t.trade_id}_{t.ticker}_{t.entry.time.replace(' ','_').replace(':','')}.json"
        with open(os.path.join(TRADES_OUTPUT_DIR, fname), 'w') as f:
            json.dump(asdict(t), f, indent=4, default=str)

if __name__ == "__main__":
    run_backtest()
