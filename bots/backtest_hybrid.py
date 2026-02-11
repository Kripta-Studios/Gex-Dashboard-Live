"""
Backtesting Script for Hybrid Trading Model

Simulates trading based on model predictions and calculates:
- Win rate by direction
- Profit factor
- Max drawdown
- Sharpe ratio
- P&L by ticker

Usage:
    python bots/backtest_hybrid.py --data training_data/training_data.csv --threshold 0.6
"""

import os
import sys
import time
import argparse
import numpy as np
import pandas as pd
import torch
from pathlib import Path
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from hybrid_model import load_hybrid_model, get_device, FEATURE_COLUMNS
from datetime import datetime, timedelta

try:
    from tradingbot_wrapper import send_discord_trade_open, send_discord_trade_close
    _has_discord = True
    discord_error_msg = ""
except ImportError as e:
    print(f"⚠️ Discord module import failed: {e}")
    send_discord_trade_open = None
    send_discord_trade_close = None
    _has_discord = False
    discord_error_msg = str(e)


# --- TRADE SIMULATION ---
class TradeSimulator:
    """Simulates trades based on model predictions with cooldown to prevent overtrading."""
    
    def __init__(self, threshold: float = 0.6, position_size: float = 1.0, cooldown_minutes: int = 30, 
                 target_pct: float = 0.003, stop_pct: float = 0.003, max_time: int = 30, min_iv_pct: float = 0.0,
                 discord_enabled: bool = False, trade_limit: int = 0):
        self.threshold = threshold
        self.position_size = position_size
        self.cooldown_minutes = cooldown_minutes
        self.target_pct = target_pct
        self.stop_pct = stop_pct
        self.max_time = max_time
        self.min_iv_pct = min_iv_pct
        self.discord_enabled = discord_enabled
        self.trade_limit = trade_limit
        self.trades = []
        
    def simulate(self, df: pd.DataFrame, predictions: np.ndarray, probabilities: np.ndarray, time_predictions: np.ndarray = None) -> pd.DataFrame:
        """
        Simulate trades based on predictions with cooldown between trades.
        """
        trades = []
        
        # Create a copy with predictions and sort properly
        df_work = df.copy()
        df_work['pred'] = predictions
        df_work['max_prob'] = probabilities.max(axis=1)
        if time_predictions is not None:
            df_work['time_pred'] = time_predictions
        
        # Convert time to minutes for easier comparison
        def time_to_minutes(t):
            try:
                h, m = map(int, str(t).split(':'))
                return h * 60 + m
            except:
                return 0
        
        df_work['minutes'] = df_work['time'].apply(time_to_minutes)
        df_work['date'] = df_work['date'].astype(str)
        
        # Sort by ticker, date, time
        df_work = df_work.sort_values(['ticker', 'date', 'minutes']).reset_index(drop=True)
        
        # Build lookup: for each (ticker, date), list of (minute, price, idx)
        price_lookup = {}
        for idx, row in df_work.iterrows():
            key = (row['ticker'], row['date'])
            if key not in price_lookup:
                price_lookup[key] = []
            price_lookup[key].append((row['minutes'], row['spot_price'], idx))
        
        # Track last trade time per ticker per day to enforce cooldown
        last_trade_time = {}
        
        # Point values per ticker
        point_values = {
            "SPX": 50.0,
            "/ES": 50.0,
            "/NQ": 20.0,
            "SPY": 100.0,
            "QQQ": 100.0,
        }
        
        for idx, row in df_work.iterrows():
            pred = row['pred']
            max_prob = row['max_prob']
            
            # Only trade if confidence exceeds threshold
            if max_prob < self.threshold:
                continue
            
            # Skip HOLD predictions
            if pred == 1:
                continue
            
            ticker = row['ticker']
            date = row['date']
            time_str = row['time']
            current_minute = row['minutes']
            
            # Cooldown check
            last_time = last_trade_time.get((ticker, date), -999)
            if current_minute - last_time < self.cooldown_minutes:
                continue
                
            # Execute trade
            entry_price = row['spot_price']
            direction = "LONG" if pred == 2 else "SHORT"
            
            # Determine hold time using prediction if available
            pred_minutes_value = 30 # default
            if time_predictions is not None:
                # time_prediction is normalized 0-1 (fraction of 30 min)
                # We add 2 min minimum to avoid immediate exits
                raw_pred = row['time_pred'] * 30.0
                pred_minutes_value = int(round(raw_pred))
                
                # FILTER: Skip if predicted time is too long (slow move)
                if pred_minutes_value > self.max_time:
                    continue
                
                # FILTER: Skip if Volatility (IV Percentile) is too low
                # iv_percentile is in dataframe
                if 'iv_percentile' in row and row['iv_percentile'] < self.min_iv_pct:
                    continue
                    
                pred_minutes = max(2, pred_minutes_value)
                # Cap at 30 mins
                hold_minutes = min(30, pred_minutes)
            else:
                hold_minutes = 30  # Default fallback
                
            # --- DISCORD ALERT SIMULATION ---
            if self.discord_enabled and send_discord_trade_open:
                print(f"  [Discord Request] Sending alert for {ticker} {direction}...")
                # Create a mock signal object as expected by the wrapper
                tp_price = entry_price * (1 + self.target_pct) if direction == "LONG" else entry_price * (1 - self.target_pct)
                sl_price = entry_price * (1 - self.stop_pct) if direction == "LONG" else entry_price * (1 + self.stop_pct)
                
                class MockSignal:
                    def __init__(self, t, d, p, tp, sl):
                        self.ticker = t
                        self.direction = d
                        self.entry_price = p
                        self.stop_loss = sl
                        self.take_profit_1 = tp
                        self.take_profit_2 = tp
                        self.raw_confidence = 0.99
                        self.calibrated_confidence = 0.99
                        self.position_size = 1.0
                        self.max_hold_time = 30
                        self.regime = "trending_up" # Mock regime

                mock_signal = MockSignal(ticker, direction, entry_price, tp_price, sl_price)
                
                # Parse entry date/time for the alert
                try:
                    # date is YYYYMMDD (int or str), time_str is HH:MM
                    date_str = str(date)
                    dt_str = f"{date_str} {time_str}"
                    entry_dt = datetime.strptime(dt_str, "%Y%m%d %H:%M")
                except:
                    entry_dt = datetime.now()
                
                try:
                    send_discord_trade_open(mock_signal, timestamp=entry_dt)
                    # Small delay to avoid rate limits
                    time.sleep(0.1)
                except Exception as e:
                    print(f"  [Discord Error] {e}")

            
            exit_minute = current_minute + hold_minutes
            
            # Find exit price
            day_prices = price_lookup.get((ticker, date), [])
            
            exit_price = entry_price  # Default if no data found
            # effective_hold = 0
            
            # Find exit point logic...
            stop_hit = False
            target_hit = False
            found_exit = False
            actual_hold_minutes = hold_minutes
            
            # Find current index in day_prices
            start_search_idx = -1
            for search_i, (m, p, original_idx) in enumerate(day_prices):
                if m == current_minute:
                    start_search_idx = search_i
                    break
            
            if start_search_idx != -1:
                # Scan future prices up to hold_minutes
                for i in range(start_search_idx + 1, len(day_prices)):
                    minute, price, _ = day_prices[i]
                    actual_hold_minutes = minute - current_minute
                    
                    if minute > exit_minute:
                        # Reached time limit - exit here if not stopped out yet
                        exit_price = price
                        found_exit = True
                        break
                    
                    # Check stop/target
                    move_pct = (price - entry_price) / entry_price
                    if direction == "SHORT":
                        move_pct = -move_pct
                    
                    if move_pct <= -self.stop_pct:
                        exit_price = price
                        stop_hit = True
                        found_exit = True
                        break
                    
                    if move_pct >= self.target_pct:
                        exit_price = price
                        target_hit = True
                        found_exit = True
                        break
                
                # If loop finished without finding exit (end of day), take last price
                if not found_exit and start_search_idx < len(day_prices) - 1:
                     _, exit_price, _ = day_prices[-1]
                     # Approximate hold time if we ran out of data
                     actual_hold_minutes = day_prices[-1][0] - current_minute
            
            # Calculate P&L
            multiplier = point_values.get(ticker, 100.0)
            
            pnl_dollars = 0.0
            if direction == "LONG":
                pnl = (exit_price - entry_price)
                pnl_dollars = pnl * multiplier * self.position_size # 1.0 size
                pnl_pct = (exit_price - entry_price) / entry_price
            else:
                pnl = (entry_price - exit_price)
                pnl_dollars = pnl * multiplier * self.position_size
                pnl_pct = (entry_price - exit_price) / entry_price
            
            # --- DISCORD CLOSE ALERT ---
            if self.discord_enabled and send_discord_trade_close:
                print(f"  [Discord Request] Sending CLOSE alert for {ticker}...")
                 # Determine exit reason string
                reason = "Time Exit"
                if target_hit: reason = "Target Hit"
                elif stop_hit: reason = "Stop Loss"
                elif not found_exit: reason = "End of Day"

                # Parse/Calculated entry and exit times
                try:
                    date_str = str(date)
                    dt_str = f"{date_str} {time_str}"
                    entry_dt = datetime.strptime(dt_str, "%Y%m%d %H:%M")
                    # Calculate exit time based on actual hold minutes
                    exit_dt = entry_dt + timedelta(minutes=int(actual_hold_minutes))
                except:
                    entry_dt = datetime.now()
                    exit_dt = datetime.now()
                
                class MockPosition:
                    def __init__(self, t, d, p, et):
                        self.ticker = t
                        self.direction = d
                        self.entry_price = p
                        self.entry_time = et
                
                mock_position = MockPosition(ticker, direction, entry_price, entry_dt)
                
                try:
                    send_discord_trade_close(mock_position, exit_price, reason, pnl_pct, pnl_dollars, close_time=exit_dt)
                    time.sleep(0.1) # Rate limit
                except Exception as e:
                    print(f"  [Discord Close Error] {e}")

            # Record trade
            trades.append({
                "date": str(date),
                "entry_time": time_str,
                "ticker": ticker,
                "direction": direction,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "pnl": pnl,
                "confidence": max_prob,
                "hold_minutes": hold_minutes,
                "target_hit": target_hit,
                "stop_hit": stop_hit
            })
            
            # Check limit
            if self.trade_limit > 0 and len(trades) >= self.trade_limit:
                print(f"\n[INFO] Trade limit of {self.trade_limit} reached. Stopping simulation.")
                break
            
            # Update cooldown
            last_trade_time[(ticker, date)] = current_minute
            
        return pd.DataFrame(trades)


# --- METRICS CALCULATION ---
def calculate_metrics(trades_df: pd.DataFrame) -> dict:
    """Calculate trading metrics from trade results."""
    
    if trades_df.empty:
        return {"error": "No trades executed"}
    
    total_trades = len(trades_df)
    wins = trades_df[trades_df["pnl"] > 0]
    losses = trades_df[trades_df["pnl"] < 0]
    flat = trades_df[trades_df["pnl"] == 0]
    
    # Win rate
    win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0
    
    # Profit factor
    gross_profit = wins["pnl"].sum() if len(wins) > 0 else 0
    gross_loss = abs(losses["pnl"].sum()) if len(losses) > 0 else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    # Total P&L
    total_pnl = trades_df["pnl"].sum()
    
    # Cumulative P&L for drawdown
    cumulative = trades_df["pnl"].cumsum()
    running_max = cumulative.cummax()
    drawdown = cumulative - running_max
    max_drawdown = drawdown.min()
    
    # Sharpe ratio (simplified - daily returns)
    if len(trades_df) > 1:
        daily_returns = trades_df.groupby("date")["pnl"].sum()
        sharpe = daily_returns.mean() / daily_returns.std() * np.sqrt(252) if daily_returns.std() > 0 else 0
    else:
        sharpe = 0
    
    # By direction
    long_trades = trades_df[trades_df["direction"] == "LONG"]
    short_trades = trades_df[trades_df["direction"] == "SHORT"]
    
    long_win_rate = len(long_trades[long_trades["pnl"] > 0]) / len(long_trades) * 100 if len(long_trades) > 0 else 0
    short_win_rate = len(short_trades[short_trades["pnl"] > 0]) / len(short_trades) * 100 if len(short_trades) > 0 else 0
    
    return {
        "total_trades": total_trades,
        "wins": len(wins),
        "losses": len(losses),
        "flat": len(flat),
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "total_pnl": total_pnl,
        "max_drawdown": max_drawdown,
        "sharpe_ratio": sharpe,
        "long_trades": len(long_trades),
        "long_win_rate": long_win_rate,
        "long_pnl": long_trades["pnl"].sum() if len(long_trades) > 0 else 0,
        "short_trades": len(short_trades),
        "short_win_rate": short_win_rate,
        "short_pnl": short_trades["pnl"].sum() if len(short_trades) > 0 else 0,
    }


def print_metrics(metrics: dict, title: str = ""):
    """Pretty print metrics."""
    print(f"\n{'=' * 60}")
    print(f"  {title}" if title else "  BACKTEST RESULTS")
    print(f"{'=' * 60}")
    
    if "error" in metrics:
        print(f"  ⚠ {metrics['error']}")
        return
    
    print(f"\n  📊 TRADE SUMMARY")
    print(f"  {'─' * 40}")
    print(f"  Total trades:     {metrics['total_trades']:,}")
    print(f"  Wins:             {metrics['wins']:,}")
    print(f"  Losses:           {metrics['losses']:,}")
    print(f"  Flat:             {metrics['flat']:,}")
    
    print(f"\n  💰 PERFORMANCE")
    print(f"  {'─' * 40}")
    print(f"  Win Rate:         {metrics['win_rate']:.1f}%")
    print(f"  Profit Factor:    {metrics['profit_factor']:.2f}")
    print(f"  Total P&L:        {metrics['total_pnl']:+.2f}")
    print(f"  Max Drawdown:     {metrics['max_drawdown']:.2f}")
    print(f"  Sharpe Ratio:     {metrics['sharpe_ratio']:.2f}")
    
    print(f"\n  📈 BY DIRECTION")
    print(f"  {'─' * 40}")
    print(f"  LONG:  {metrics['long_trades']:,} trades | {metrics['long_win_rate']:.1f}% win | P&L: {metrics['long_pnl']:+.2f}")
    print(f"  SHORT: {metrics['short_trades']:,} trades | {metrics['short_win_rate']:.1f}% win | P&L: {metrics['short_pnl']:+.2f}")


def print_by_ticker(trades_df: pd.DataFrame):
    """Print metrics by ticker."""
    print(f"\n  📊 BY TICKER")
    print(f"  {'─' * 40}")
    
    for ticker in trades_df["ticker"].unique():
        ticker_trades = trades_df[trades_df["ticker"] == ticker]
        metrics = calculate_metrics(ticker_trades)
        if "error" not in metrics:
            print(f"  {ticker:6s}: {metrics['total_trades']:4d} trades | {metrics['win_rate']:5.1f}% win | P&L: {metrics['total_pnl']:+6.2f}")


# --- MAIN ---
def main():
    parser = argparse.ArgumentParser(description="Backtest hybrid trading model")
    parser.add_argument("--data", default="training_data/training_data.csv", help="Path to CSV data")
    parser.add_argument("--model", default="models/trading_hybrid.pt", help="Path to model file")
    parser.add_argument("--threshold", type=float, default=0.7, help="Confidence threshold for trades (0.5-0.9)")
    parser.add_argument("--cooldown", type=int, default=30, help="Minutes between trades per ticker (default: 30)")
    parser.add_argument("--position-size", type=float, default=1.0, help="Position size multiplier")
    parser.add_argument("--target", type=float, default=0.003, help="Target profit %% (default: 0.3%%)")
    parser.add_argument("--stop", type=float, default=0.003, help="Stop loss %% (default: 0.3%%)")
    parser.add_argument("--max-time", type=int, default=30, help="Max predicted time to enter trade (default: 30, i.e. no filter)")
    parser.add_argument("--min-iv", type=float, default=0.0, help="Min IV Percentile (0-1) to trade (default: 0)")
    parser.add_argument("--discord", action="store_true", help="Send Discord alerts for trades (first 3 only)")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of trades to simulate (0 = all)")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("  HYBRID MODEL BACKTESTING")
    print("=" * 60)
    print(f"  Configuration:")
    print(f"  • Threshold:  {args.threshold}")
    print(f"  • Target:     {args.target:.1%}")
    print(f"  • Stop Loss:  {args.stop:.1%}")
    print(f"  • Max Time:   {args.max_time} min")
    print(f"  • Min IV Pct: {args.min_iv:.2f}")
    if args.discord:
        if _has_discord:
            print(f"  • Discord:    HEADLESS MODE (Simulated Alerts)")
        else:
            print(f"  • Discord:    ⚠️ FAILED (Error: {discord_error_msg})")
    else:
        print(f"  • Discord:    DISABLED")
    
    # Check device
    device = get_device()
    
    # Get absolute paths
    base_dir = Path(__file__).parent.parent
    data_path = base_dir / args.data
    
    # Load model
    print(f"\n[1/4] Loading model from {args.model}...")
    
    # Construct normalizer path assuming it's in the same directory as the model
    # or in a 'models' directory relative to project root.
    # The default args.model is "models/trading_hybrid.pt"
    model_dir = os.path.dirname(args.model)
    normalizer_path = os.path.join(model_dir, "hybrid_normalizer.npz")
    
    if not os.path.exists(normalizer_path):
        print(f"  [!] Normalizer not found at {normalizer_path}. Trying default location...")
        normalizer_path = "models/hybrid_normalizer.npz"
        
    try:
        # load_hybrid_model returns (model, normalizer)
        model, normalizer = load_hybrid_model(args.model, normalizer_path)
        model.to(device)
        model.eval()
        print("  [OK] Model loaded")
    except Exception as e:
        print(f"  [ERROR] Error loading model: {e}")
        return
    
    # Load data
    print(f"\n[2/4] Loading data from {data_path}...")
    df = pd.read_csv(data_path)
    print(f"  [OK] Loaded {len(df):,} samples")
    print(f"  [OK] Tickers: {df['ticker'].unique().tolist()}")
    print(f"  [OK] Dates: {df['date'].nunique()} unique days")
    
    # Prepare features
    print(f"\n[3/4] Running predictions...")
    available_cols = [c for c in FEATURE_COLUMNS if c in df.columns]
    if len(available_cols) != len(FEATURE_COLUMNS):
        missing = set(FEATURE_COLUMNS) - set(available_cols)
        print(f"  [!] Missing columns: {missing}")
    
    features = df[available_cols].values.astype(np.float32)
    
    # Normalize
    with open("normalization_debug.txt", "w") as f:
        f.write(f"Normalizer means (first 5): {normalizer.means[:5] if normalizer.means is not None else 'None'}\n")
        f.write(f"Feature sample (raw): {features[0][:5]}\n")
        
        features_norm = normalizer.transform(features)
        
        f.write(f"Feature sample (norm): {features_norm[0][:5]}\n")
        f.write(f"Feature sample (norm) max: {features_norm.max()}\n")
        f.write(f"Feature sample (norm) min: {features_norm.min()}\n")
    
    features_tensor = torch.tensor(features_norm, dtype=torch.float32).to(device)
    
    # Predict
    with torch.no_grad():
        logits, time_pred = model(features_tensor)
        probs = torch.softmax(logits, dim=-1).cpu().numpy()
        predictions = logits.argmax(dim=-1).cpu().numpy()
        time_predictions = time_pred.cpu().numpy().flatten()
    
    print(f"  [OK] Predictions complete")
    print(f"    SHORT: {(predictions == 0).sum():,}")
    print(f"    HOLD:  {(predictions == 1).sum():,}")
    print(f"    LONG:  {(predictions == 2).sum():,}")
    
    # Simulate trades
    print(f"\n[4/4] Simulating trades (threshold={args.threshold}, cooldown={args.cooldown}min, target={args.target:.1%}, stop={args.stop:.1%}, max_time={args.max_time}m, min_iv={args.min_iv})...")
    simulator = TradeSimulator(threshold=args.threshold, position_size=args.position_size, cooldown_minutes=args.cooldown,
                               target_pct=args.target, stop_pct=args.stop, max_time=args.max_time, min_iv_pct=args.min_iv,
                               discord_enabled=args.discord)
    trades_df = simulator.simulate(df, predictions, probs, time_predictions)
    print(f"  [OK] Executed {len(trades_df):,} trades")
    
    # Calculate and print metrics
    metrics = calculate_metrics(trades_df)
    print_metrics(metrics, f"BACKTEST RESULTS (threshold={args.threshold})")
    
    if not trades_df.empty:
        print_by_ticker(trades_df)
    
    # Test different thresholds
    print(f"\n{'=' * 60}")
    print("  THRESHOLD SENSITIVITY ANALYSIS")
    print(f"{'=' * 60}")
    print(f"\n  {'Threshold':<12} {'Trades':<10} {'Win Rate':<12} {'PF':<10} {'P&L':<10}")
    print(f"  {'─' * 54}")
    
    for thresh in [0.5, 0.6, 0.7, 0.8, 0.9]:
        sim = TradeSimulator(threshold=thresh, cooldown_minutes=args.cooldown,
                             target_pct=args.target, stop_pct=args.stop, max_time=args.max_time, min_iv_pct=args.min_iv,
                             discord_enabled=False) # Disable discord for sensitivity analysis
        trades = sim.simulate(df, predictions, probs, time_predictions)
        m = calculate_metrics(trades)
        if "error" not in m:
            print(f"  {thresh:<12.1f} {m['total_trades']:<10,} {m['win_rate']:<12.1f}% {m['profit_factor']:<10.2f} {m['total_pnl']:<+10.2f}")
        else:
            print(f"  {thresh:<12.1f} {'No trades':<10}")
    
    # Save trades to CSV
    if not trades_df.empty:
        output_path = base_dir / "training_data" / "backtest_trades.csv"
        trades_df.to_csv(output_path, index=False)
        print(f"\n  [OK] Trades saved to {output_path}")
    
    print(f"\n{'=' * 60}")


if __name__ == "__main__":
    main()
