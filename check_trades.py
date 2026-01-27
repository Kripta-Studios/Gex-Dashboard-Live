#!/usr/bin/env python3
"""
check_trades.py - Quick status check for active trades

Usage: python check_trades.py
"""

import os
import json
import glob
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
    NY_TZ = ZoneInfo("America/New_York")
except:
    import pytz
    NY_TZ = pytz.timezone("America/New_York")

# Paths to state files
STATE_BOT1 = "./state_bot1.json"
STATE_BOT2 = "./state_bot2.json"
GREEK_DATA_DIR = "/home/Option-Greeks-Plotting-Discord-Bot/json_data"

# Point values for P&L calculation
POINT_VALUES = {"SPX": 10.0, "SPY": 100.0, "QQQ": 400.0}

def get_current_spot(ticker: str) -> float:
    """Get latest spot price from Greek data files."""
    today = datetime.now(NY_TZ).strftime("%Y%m%d")
    pattern = os.path.join(GREEK_DATA_DIR, f"{ticker}_0dte_ExposureData_{today}_*.json")
    files = sorted(glob.glob(pattern))
    
    if not files:
        return None
    
    try:
        with open(files[-1], 'r') as f:
            data = json.load(f)
        return data.get("spot_price", None)
    except:
        return None

def load_trade(filepath: str) -> dict:
    """Load trade from state file."""
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except:
        return None

def format_duration(entry_time_str: str) -> str:
    """Calculate duration from entry to now."""
    try:
        # Handle different time formats
        if "." in entry_time_str:
            entry_time_str = entry_time_str.split(".")[0]
        if "-05:00" in entry_time_str or "-04:00" in entry_time_str:
            entry_time_str = entry_time_str.split("-0")[0]
        
        entry_dt = datetime.strptime(entry_time_str.strip(), "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        
        # Approximate duration (ignoring timezone for simplicity)
        duration = now - entry_dt
        hours = int(duration.total_seconds() // 3600)
        mins = int((duration.total_seconds() % 3600) // 60)
        
        if hours > 0:
            return f"{hours}h {mins}m"
        return f"{mins}m"
    except Exception as e:
        return f"Unknown ({e})"

def display_trade(trade: dict, bot_name: str):
    """Display trade info in a formatted way."""
    if not trade:
        print(f"\n{'='*60}")
        print(f"  {bot_name}: NO ACTIVE TRADE")
        print(f"{'='*60}")
        return None
    
    ticker = trade.get("ticker", "???")
    direction = trade.get("direction", "???")
    
    # Handle different entry formats between bots
    entry = trade.get("entry", {})
    if isinstance(entry, dict):
        entry_price = entry.get("price", 0)
        entry_time = entry.get("time", "Unknown")
        entry_reason = entry.get("reason", "")
        setup_details = entry.get("setup_details", "")
    else:
        entry_price = 0
        entry_time = "Unknown"
        entry_reason = ""
        setup_details = ""
    
    # Get current spot for P&L
    current_spot = get_current_spot(ticker)
    
    # Calculate unrealized P&L
    pnl_points = 0
    pnl_pct = 0
    pnl_dollars = 0
    if current_spot and entry_price:
        if direction == "LONG":
            pnl_points = current_spot - entry_price
        else:
            pnl_points = entry_price - current_spot
        pnl_pct = (pnl_points / entry_price) * 100
        pnl_dollars = pnl_points * POINT_VALUES.get(ticker, 10.0)
    
    duration = format_duration(entry_time)
    
    # Get strategy info
    strategy = trade.get("strategy", "")
    target = trade.get("target_level")
    
    # Get signals (Bot1 style)
    signals = trade.get("signals", {})
    gamma_regime = signals.get("gamma_regime", "")
    vanna_signal = signals.get("vanna_signal", "")
    min_vanna = signals.get("min_vanna_magnet")
    
    # Confluence
    confluence = trade.get("confluence", {})
    
    # Display
    emoji = "📈" if direction == "LONG" else "📉"
    pnl_emoji = "✅" if pnl_dollars >= 0 else "❌"
    
    print(f"\n{'='*60}")
    print(f"  {bot_name}: {emoji} {direction} {ticker}")
    print(f"{'='*60}")
    print(f"  Entry Price:  ${entry_price:.2f}")
    print(f"  Entry Time:   {entry_time}")
    print(f"  Duration:     {duration}")
    
    if current_spot:
        print(f"\n  Current Spot: ${current_spot:.2f}")
        print(f"  {pnl_emoji} Unrealized:  {pnl_points:+.2f} pts ({pnl_pct:+.2f}%) = ${pnl_dollars:+.2f}")
    else:
        print(f"\n  Current Spot: Unable to fetch")
    
    # Show entry reasoning
    print(f"\n  {'─'*56}")
    print(f"  WHY THIS TRADE?")
    print(f"  {'─'*56}")
    
    if entry_reason:
        print(f"  Reason: {entry_reason}")
    if setup_details:
        for line in setup_details.split("\n"):
            print(f"    {line}")
    if strategy:
        print(f"  Strategy: {strategy}")
    if target:
        dist_to_target = abs(target - current_spot) if current_spot else 0
        print(f"  Target: ${target:.2f} ({dist_to_target:.2f} pts away)")
    
    # Bot1-specific signals
    if gamma_regime:
        print(f"\n  Gamma Regime: {gamma_regime.upper()}")
    if vanna_signal and vanna_signal != "neutral":
        print(f"  Vanna: {vanna_signal}")
    if min_vanna:
        touched = signals.get("min_vanna_touched", False)
        status = "TOUCHED" if touched else "UNTOUCHED (magnet)"
        print(f"  Min Vanna: ${min_vanna:.2f} - {status}")
    
    # Confluence
    if confluence:
        spx = confluence.get("spx_signal", "HOLD")
        spy = confluence.get("spy_signal", "HOLD")
        qqq = confluence.get("qqq_signal", "HOLD")
        aligned = confluence.get("aligned", False)
        print(f"\n  Confluence: SPX={spx} | SPY={spy} | QQQ={qqq}")
        print(f"  Aligned: {'✅ YES' if aligned else '⚠️ NO'}")
    
    return {"ticker": ticker, "direction": direction, "pnl_dollars": pnl_dollars}

def check_contradiction(bot1_info: dict, bot2_info: dict):
    """Check if bots have contradictory positions and explain why."""
    if not bot1_info or not bot2_info:
        return
    
    print(f"\n{'='*60}")
    print("  ⚠️  POSITION ANALYSIS")
    print(f"{'='*60}")
    
    # Check if same ticker
    if bot1_info["ticker"] == bot2_info["ticker"]:
        if bot1_info["direction"] != bot2_info["direction"]:
            print(f"  🚨 CONTRADICTION on {bot1_info['ticker']}!")
            print(f"     Bot1: {bot1_info['direction']}")
            print(f"     Bot2: {bot2_info['direction']}")
            print(f"\n  This should NOT happen. Check strategies.")
        else:
            print(f"  ✅ ALIGNED on {bot1_info['ticker']} ({bot1_info['direction']})")
    else:
        # Different tickers
        print(f"  Different tickers: Bot1={bot1_info['ticker']}, Bot2={bot2_info['ticker']}")
        
        if bot1_info["direction"] != bot2_info["direction"]:
            print(f"\n  ⚠️ OPPOSING DIRECTIONS:")
            print(f"     Bot1: {bot1_info['direction']} {bot1_info['ticker']}")
            print(f"     Bot2: {bot2_info['direction']} {bot2_info['ticker']}")
            print(f"\n  WHY THIS CAN HAPPEN:")
            print(f"  ─────────────────────")
            print(f"  • Bot1 (tradingbot1.py) uses confluence-based entries")
            print(f"    requiring signal alignment across SPX/SPY/QQQ")
            print(f"  • Bot2 (tradingbot2.py) uses level-based reversals")
            print(f"    and momentum breakouts on individual tickers")
            print(f"\n  • They entered at different times with different")
            print(f"    market conditions and different signal logic")
            print(f"\n  COMBINED P&L: ${bot1_info['pnl_dollars'] + bot2_info['pnl_dollars']:+.2f}")
        else:
            print(f"  ✅ Same direction ({bot1_info['direction']}) on different tickers")

def main():
    print("\n" + "="*60)
    print("        ACTIVE TRADES STATUS - " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("="*60)
    
    # Load both trades
    trade1 = load_trade(STATE_BOT1)
    trade2 = load_trade(STATE_BOT2)
    
    # Display each
    info1 = display_trade(trade1, "TRADINGBOT1")
    info2 = display_trade(trade2, "TRADINGBOT2")
    
    # Check for contradictions
    if info1 and info2:
        check_contradiction(info1, info2)
    
    print(f"\n{'='*60}")
    print("  State files:")
    print(f"    Bot1: {STATE_BOT1} {'✅' if trade1 else '(empty)'}")
    print(f"    Bot2: {STATE_BOT2} {'✅' if trade2 else '(empty)'}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
