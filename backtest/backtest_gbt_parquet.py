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
# Asegúrate de que estas líneas estén así al principio del archivo:
import os
import sys
from pathlib import Path

# 1. Obtenemos la raíz del proyecto (un nivel arriba de 'neural/')
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent

# 2. Añadimos tanto la raíz como las carpetas 'bots' y 'neural' al PATH de Python
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "bots"))
sys.path.insert(0, str(PROJECT_ROOT / "neural"))

import time
import argparse
import numpy as np
import pandas as pd
import torch
from pathlib import Path
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from hybrid_model import get_hybrid_model, load_hybrid_model, load_ensemble_model, EnsembleTradingModel, FeatureNormalizer, get_device, FEATURE_COLUMNS
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


# --- POSITION SIZING ---
INITIAL_BALANCE = 10_000.0

def _calc_contracts_futures(risk_capital: float, entry_price: float,
                            stop_pct: float, multiplier: float) -> int:
    max_loss_per_contract = entry_price * stop_pct * multiplier
    if max_loss_per_contract <= 0:
        return 1
    
    # Cap maximum contracts to prevent exponential explosion in backtests
    MAX_CONTRACTS = 1000
    raw_contracts = int(risk_capital / max_loss_per_contract)
    return max(1, min(raw_contracts, MAX_CONTRACTS))

# --- GBM EXIT CONSTANTS ---
GBM_TRAILING_ACTIVATION_PCT = 0.0050  # 0.50% spot profit to activate
GBM_TRAILING_STOP_PCT = 0.0030        # 0.30% retrace from peak to exit

# --- TRADE SIMULATION ---
class TradeSimulator:
    """Simulates trades based on model predictions with cooldown to prevent overtrading."""
    
    def __init__(self, threshold: float = 0.6, position_size: float = 1.0, cooldown_minutes: int = 30, 
                 target_long: float = 0.010, target_short: float = 0.005, # <-- Targets separados
                 stop_pct: float = 0.003, max_time: int = 180, min_iv_pct: float = 0.0,
                 discord_enabled: bool = False, trade_limit: int = 0, uncertainty_threshold: float = 45.0,
                 risk_capital: float = 500.0):
        self.threshold = threshold
        self.position_size = position_size
        self.risk_capital = risk_capital
        self.cooldown_minutes = cooldown_minutes
        self.target_long = target_long    # Guardamos ambos
        self.target_short = target_short
        self.stop_pct = stop_pct
        self.max_time = max_time
        self.min_iv_pct = min_iv_pct
        self.discord_enabled = discord_enabled
        self.trade_limit = trade_limit
        self.uncertainty_threshold = uncertainty_threshold  # σ > this → exit (minutes)
        self.trades = []
        
    def load_ib_data(self, ticker, date):
        """Lazy load ThetaData 1-minute OHLC data for a ticker/date."""
        if (ticker, date) in self._ib_data_cache:
            return self._ib_data_cache[(ticker, date)]
        
        file_ticker = "SPXW" if ticker.replace("/", "") == "SPX" else ticker
        date_str = str(date).replace("-", "")
        year, month = date_str[:4], date_str[4:6]
        
        filepath = Path(f"D:/ThetaData/data_underlying_derived/{file_ticker}/{year}/{month}/{file_ticker}_{date_str}.parquet")
        
        if filepath.exists():
            try:
                import pandas as pd
                df = pd.read_parquet(filepath)
                df['dt'] = pd.to_datetime(df['timestamp'])
                # Filter RTH (08:00 to 17:00 as per training data parsing)
                df = df[(df['dt'].dt.time >= pd.Timestamp('08:00').time()) & (df['dt'].dt.time <= pd.Timestamp('17:00').time())]
                
                parsed_series = []
                for _, row in df.iterrows():
                    t = row['dt']
                    mins = t.hour * 60 + t.minute
                    o = float(row['open'])
                    h_p = float(row['high'])
                    l = float(row['low'])
                    c = float(row['close'])
                    parsed_series.append((mins, o, h_p, l, c))
                
                self._ib_data_cache[(ticker, date)] = parsed_series
                return parsed_series
            except Exception as e:
                print(f"Error loading Parquet data {filepath}: {e}")
        
        # Cache empty result if not found
        self._ib_data_cache[(ticker, date)] = []
        return []

    def simulate(self, df: pd.DataFrame, predictions: np.ndarray, probabilities: np.ndarray, time_predictions: np.ndarray = None) -> pd.DataFrame:
        """
        Simulate trades based on predictions with cooldown between trades.
        """
        self._ib_data_cache = {} # Clear cache at start of simulation
        trades = []
        
        # Create a copy with predictions and sort properly
        df_work = df.copy()
        df_work['pred'] = predictions
        df_work['max_prob'] = probabilities.max(axis=1)
        if time_predictions is not None:
            df_work['time_mu'] = time_predictions[:, 0]   # μ (normalized 0-1)
            df_work['time_sigma'] = time_predictions[:, 1] # σ in minutes
        
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
        
        # Track last trade time per ticker per day to enforce cooldown
        last_trade_time = {}
        open_positions = {}  # key: (ticker, date), value: exit_minute
        balance = INITIAL_BALANCE  # equity tracking
        
        # Fixed point values per ticker (no dynamic scaling)
        POINT_VALUES = {
            "SPX": 50.0,
            "/ES": 50.0,
            "/NQ": 20.0,
            "SPY": 100.0,
            "QQQ": 100.0,
            "IWM": 100.0,
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
            if 570 <= current_minute < 580:
                continue

            if (ticker, date) in open_positions:
                expected_exit = open_positions[(ticker, date)]
                if current_minute < expected_exit:
                    continue  # Skip - position still open
                else:
                    # Position closed, remove from tracking
                    del open_positions[(ticker, date)]

            # Cooldown check
            last_time = last_trade_time.get((ticker, date), -999)
            if current_minute - last_time < self.cooldown_minutes:
                continue
                
            # Execute trade
            entry_price = row['spot_price']
            direction = "LONG" if pred == 2 else "SHORT"
            
            # Determine hold time using Bayesian prediction if available
            pred_minutes_value = 180 # default
            sigma_minutes = 0.0
            if time_predictions is not None:
                # μ is normalized 0-1, fraction of LOOKAHEAD_MINUTES (180)
                raw_pred = row['time_mu'] * 180.0
                pred_minutes_value = int(round(raw_pred))
                sigma_minutes = row['time_sigma']  # Already in minutes
                
                # FILTER: Skip if predicted time is too long (slow move)
                if pred_minutes_value > self.max_time:
                    continue
                
                # FILTER: Skip if uncertainty is too high (Bayesian)
                if sigma_minutes > self.uncertainty_threshold:
                    continue
                
                # FILTER: Skip if Volatility (IV Percentile) is too low
                # iv_percentile is in dataframe
                if 'iv_percentile' in row and row['iv_percentile'] < self.min_iv_pct:
                    continue
                    
                pred_minutes = max(2, pred_minutes_value)
                # Cap at 180 mins (LOOKAHEAD_MINUTES)
                hold_minutes = min(180, pred_minutes)
            else:
                hold_minutes = 180  # Default fallback
            
            # --- HIGH RESOLUTION EXIT LOGIC ---
            exit_price = entry_price
            pnl = 0.0
            actual_hold_minutes = hold_minutes
            target_hit = False
            stop_hit = False
            trailing_stop_hit = False
            mae = 0.0
            peak_price = entry_price

            base_target = self.target_long if direction == "LONG" else self.target_short
            
            smart_target = base_target
            if sigma_minutes < 15.0: # Si la incertidumbre es muy baja, somos más ambiciosos
                smart_target = base_target * 1.5
            
            # Load 1-minute data for this day
            minute_data = self.load_ib_data(ticker, date)
            
            if not minute_data:
                # Fallback: simple time exit at entry price (conservative)
                # Or could use low-res data if available, but let's be strict for now
                pass 
            else:
                # Find entry index
                entry_idx = -1
                # Simple binary search or scan? Scan is fine for ~390 mins
                for i, (m, o, h, l, c) in enumerate(minute_data):
                    if m >= current_minute:
                        entry_idx = i
                        break
                
                if entry_idx != -1:
                    # Scan forward
                    exit_minute_limit = current_minute + hold_minutes
                    found_exit_scan = False
                    
                    for i in range(entry_idx, len(minute_data)):
                        m, o, h, l, c = minute_data[i]
                        
                        # Check Time Force Exit
                        if m > exit_minute_limit:
                            exit_price = o # Exit at open of next candle
                            actual_hold_minutes = m - current_minute
                            found_exit_scan = True
                            break
                        
                        # Check Targets/Stops (Intra-candle)
                        # Conservative: check Low for Long Stop, High for Short Stop first?
                        # Realistic: check overlapping ranges.
                        
                        if direction == "LONG":
                            # Peak tracking
                            peak_price = max(peak_price, h)
                            peak_pnl = (peak_price - entry_price) / entry_price
                            
                            # Trailing stop check
                            if peak_pnl >= GBM_TRAILING_ACTIVATION_PCT:
                                if (peak_price - l) / entry_price >= GBM_TRAILING_STOP_PCT:
                                    exit_price = peak_price - (entry_price * GBM_TRAILING_STOP_PCT)
                                    trailing_stop_hit = True
                                    actual_hold_minutes = m - current_minute
                                    found_exit_scan = True
                                    break

                            # Stop Loss (Low triggers it)
                            if l <= entry_price * (1 - self.stop_pct):
                                exit_price = entry_price * (1 - self.stop_pct)
                                stop_hit = True
                                actual_hold_minutes = m - current_minute
                                found_exit_scan = True
                                break
                            
                            # Take Profit (High triggers it)
                            if h >= entry_price * (1 + smart_target):
                                exit_price = entry_price * (1 + smart_target)
                                target_hit = True
                                actual_hold_minutes = m - current_minute
                                found_exit_scan = True
                                break
                                
                        else: # SHORT
                            # Peak tracking
                            peak_price = min(peak_price, l)
                            peak_pnl = (entry_price - peak_price) / entry_price
                            
                            # Trailing stop check
                            if peak_pnl >= GBM_TRAILING_ACTIVATION_PCT:
                                if (h - peak_price) / entry_price >= GBM_TRAILING_STOP_PCT:
                                    exit_price = peak_price + (entry_price * GBM_TRAILING_STOP_PCT)
                                    trailing_stop_hit = True
                                    actual_hold_minutes = m - current_minute
                                    found_exit_scan = True
                                    break

                            # Stop Loss (High triggers it)
                            if h >= entry_price * (1 + self.stop_pct):
                                exit_price = entry_price * (1 + self.stop_pct)
                                stop_hit = True
                                actual_hold_minutes = m - current_minute
                                found_exit_scan = True
                                break
                                
                            # Take Profit (Low triggers it)
                            if l <= entry_price * (1 - smart_target):
                                exit_price = entry_price * (1 - smart_target)
                                target_hit = True
                                actual_hold_minutes = m - current_minute
                                found_exit_scan = True
                                break
                    
                    if not found_exit_scan:
                        # End of day exit
                        exit_price = minute_data[-1][4] # Close of last candle
                        actual_hold_minutes = minute_data[-1][0] - current_minute
                
                else:
                    # No data found after entry time?
                    pass

            
            # --- DISCORD ALERT SIMULATION ---
            if self.discord_enabled and _has_discord:
                try:
                    # Calculamos precios teóricos para el mensaje
                    tp_price = entry_price * (1 + smart_target) if direction == "LONG" else entry_price * (1 - smart_target)
                    sl_price = entry_price * (1 - self.stop_pct) if direction == "LONG" else entry_price * (1 + self.stop_pct)
                    
                    # Creamos un objeto Mock que imite lo que el Wrapper espera
                    class MockSignal:
                        def __init__(self, t, d, p, tp, sl, mu, sigma):
                            self.ticker = t
                            self.direction = d
                            self.entry_price = p
                            self.stop_loss = sl
                            self.take_profit_1 = tp
                            self.take_profit_2 = tp * 1.05
                            self.raw_confidence = max_prob
                            self.calibrated_confidence = max_prob
                            self.position_size = 1.0
                            self.max_hold_time = hold_minutes
                            self.regime = "Backtest_Discovery"
                            self.time_mu_minutes = mu
                            self.time_sigma_minutes = sigma
                            self.reasoning = f"Backtest Signal (Prob: {max_prob:.2f})"

                    mock_signal = MockSignal(ticker, direction, entry_price, tp_price, sl_price, 
                                            pred_minutes_value, sigma_minutes)
                    
                    # Convertimos la fecha del CSV a objeto datetime para el mensaje
                    entry_dt = datetime.strptime(f"{date} {time_str}", "%Y%m%d %H:%M")
                    
                    # LLAMADA REAL AL WEBHOOK
                    send_discord_trade_open(mock_signal, timestamp=entry_dt)
                    
                    # Pequeño delay para no saturar la API de Discord
                    time.sleep(0.5) 
                except Exception as e:
                    print(f"  [Discord Error] No se pudo enviar: {e}")

            # Calculate P&L using fixed multiplier and dynamic sizing
            multiplier = POINT_VALUES.get(ticker, 100.0)
            contracts = _calc_contracts_futures(self.risk_capital, entry_price, self.stop_pct, multiplier)
            
            pnl_dollars = 0.0
            if direction == "LONG":
                pnl = (exit_price - entry_price)
                pnl_dollars = pnl * multiplier * contracts
                pnl_pct = (exit_price - entry_price) / entry_price
            else:
                pnl = (entry_price - exit_price)
                pnl_dollars = pnl * multiplier * contracts
                pnl_pct = (entry_price - exit_price) / entry_price
            
            balance += pnl_dollars
            
            # --- DISCORD CLOSE ALERT ---
            if self.discord_enabled and send_discord_trade_close:
                # ... (Keeping simplified version)
                 # Determine exit reason string
                reason = "Time Exit"
                if target_hit: reason = "Target Hit"
                elif stop_hit: reason = "Stop Loss"
                elif trailing_stop_hit: reason = "Trailing Stop"
          
                try:
                    date_str = str(date)
                    dt_str = f"{date_str} {time_str}"
                    entry_dt = datetime.strptime(dt_str, "%Y%m%d %H:%M")
                    exit_dt = entry_dt + timedelta(minutes=int(actual_hold_minutes))
                    
                    class MockPosition:
                        def __init__(self, t, d, p, et):
                            self.ticker = t
                            self.direction = d
                            self.entry_price = p
                            self.entry_time = et
                    
                    mock_position = MockPosition(ticker, direction, entry_price, entry_dt)
                    
                    send_discord_trade_close(mock_position, exit_price, reason, pnl_pct, pnl_dollars, close_time=exit_dt)
                    time.sleep(0.1) 
                except Exception as e:
                    print(f"  [Discord Close Error] {e}")

            if exit_price <= 0:
                #print(f"⚠️ Ignorando trade inválido en {ticker} {date} {time_str} (Precio 0)")
                continue
            # Calculate exit time
            try:
                eh, em = map(int, time_str.split(':'))
                exit_m = eh * 60 + em + actual_hold_minutes
                exit_time_str = f"{exit_m // 60:02d}:{exit_m % 60:02d}"
            except Exception:
                exit_time_str = time_str

            # Record trade
            trades.append({
                "date": str(date),
                "entry_time": time_str,
                "exit_time": exit_time_str,
                "ticker": ticker,
                "direction": direction,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "pnl": pnl,
                "pnl_dollars": pnl_dollars,
                "confidence": max_prob,
                "hold_minutes": hold_minutes,
                "target_hit": target_hit,
                "stop_hit": stop_hit,
                "trailing_stop_hit": trailing_stop_hit,
                "exit_reason": "target" if target_hit else "stop" if stop_hit else "trailing_stop" if trailing_stop_hit else "max_time",
                "actual_hold_minutes": actual_hold_minutes,
                "point_value_used": multiplier,
                "contracts": contracts,
                "mae": mae,
                "balance": round(balance, 2)
            })
            
            # Log "Gray X" trades (0-min duration)
            if actual_hold_minutes == 0:
                result_emoji = "✅" if pnl_pct > 0 else "❌"
                reason_str = "TARGET" if target_hit else "STOP" if stop_hit else "TIME"
                #print(f"  [⚡ INSTANT] {ticker} {direction} at {date} {time_str} | Entry: {entry_price:.2f} -> Exit: {exit_price:.2f} | ({result_emoji} ${pnl_dollars:+.2f}) -> {reason_str}")
            
            # Check limit
            if self.trade_limit > 0 and len(trades) >= self.trade_limit:
                print(f"\n[INFO] Trade limit of {self.trade_limit} reached. Stopping simulation.")
                break
            
            expected_exit_minute = current_minute + hold_minutes
            open_positions[(ticker, date)] = expected_exit_minute
            
            # Update cooldown
            last_trade_time[(ticker, date)] = current_minute
            
        return pd.DataFrame(trades)


# --- METRICS CALCULATION ---
def calculate_metrics(trades_df: pd.DataFrame) -> dict:
    """Calculate trading metrics from trade results."""
    
    if trades_df.empty:
        return {"error": "No trades executed"}
    
    total_trades = len(trades_df)
    wins = trades_df[trades_df["pnl_dollars"] > 0]
    losses = trades_df[trades_df["pnl_dollars"] < 0]
    flat = trades_df[trades_df["pnl_dollars"] == 0]
    
    # Win rate
    win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0
    
    # Profit factor
    gross_profit = wins["pnl_dollars"].sum() if len(wins) > 0 else 0
    gross_loss = abs(losses["pnl_dollars"].sum()) if len(losses) > 0 else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    # Total P&L
    total_pnl = trades_df["pnl_dollars"].sum()
    
    # Cumulative P&L for drawdown
    cumulative = trades_df["pnl_dollars"].cumsum()
    running_max = cumulative.cummax()
    drawdown = cumulative - running_max
    max_drawdown = drawdown.min()
    
    # Sharpe ratio (simplified - daily returns)
    if len(trades_df) > 1:
        daily_returns = trades_df.groupby("date")["pnl_dollars"].sum()
        sharpe = daily_returns.mean() / daily_returns.std() * np.sqrt(252) if daily_returns.std() > 0 else 0
    else:
        sharpe = 0
    
    # By direction
    long_trades = trades_df[trades_df["direction"] == "LONG"]
    short_trades = trades_df[trades_df["direction"] == "SHORT"]
    
    long_win_rate = len(long_trades[long_trades["pnl_dollars"] > 0]) / len(long_trades) * 100 if len(long_trades) > 0 else 0
    short_win_rate = len(short_trades[short_trades["pnl_dollars"] > 0]) / len(short_trades) * 100 if len(short_trades) > 0 else 0
    
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
        "long_pnl": long_trades["pnl_dollars"].sum() if len(long_trades) > 0 else 0,
        "short_trades": len(short_trades),
        "short_win_rate": short_win_rate,
        "short_pnl": short_trades["pnl_dollars"].sum() if len(short_trades) > 0 else 0,
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
    parser.add_argument("--data", default="training_data/training_data_derived.parquet", help="Path to CSV data")
    parser.add_argument("--model", default="models/trading_hybrid_wf.pt", help="Path to model file")
    parser.add_argument("--normalizer", default="models/hybrid_normalizer_wf.npz", help="Path to normalizer file")
    parser.add_argument("--model-size", choices=["micro", "small", "medium", "large"], default="small", help="Model size used during training")
    parser.add_argument("--threshold", type=float, default=0.7, help="Confidence threshold for trades (0.5-0.9)")
    parser.add_argument("--cooldown", type=int, default=30, help="Minutes between trades per ticker (default: 30)")
    parser.add_argument("--risk-capital", type=float, default=500.0, help="Risk capital in dollars per trade (fixed)")
    parser.add_argument("--position-size", type=float, default=1.0, help="Position size multiplier")
    parser.add_argument("--target_long", type=float, default=0.010, help="Target for LONG (default 1%%)")
    parser.add_argument("--target_short", type=float, default=0.005, help="Target for SHORT (default 0.5%%)")
    parser.add_argument("--stop", type=float, default=0.003, help="Stop loss %% (default: 0.3%%)")
    parser.add_argument("--max-time", type=int, default=180, help="Max predicted time to enter trade (default: 180 min)")
    parser.add_argument("--min-iv", type=float, default=0.0, help="Min IV Percentile (0-1) to trade (default: 0)")
    parser.add_argument("--discord", action="store_true", help="Send Discord alerts for trades (first 3 only)")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of trades to simulate (0 = all)")
    parser.add_argument("--uncertainty", type=float, default=45.0, help="Max uncertainty sigma (minutes) to enter trade (default: 45)")
    parser.add_argument("--ensemble", action="store_true", help="Load model as ensemble (use with ensemble-trained .pt files)")
    parser.add_argument("--strict-wf", action="store_true", help="Enable strict Walk-Forward (only use models trained before the trade date)")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("  HYBRID MODEL BACKTESTING")
    print("=" * 60)
    print(f"  Configuration:")
    print(f"  • Threshold:  {args.threshold}")
    print(f"  • Target LONG: {args.target_long:.1%}")
    print(f"  • Target SHORT:{args.target_short:.1%}")
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
    
    # Get absolute paths relative to execution dir
    base_dir = Path(__file__).parent.parent
    data_path = Path(args.data).resolve()
    
    if args.strict_wf and args.model.endswith('.joblib'):
        # In strict WF mode, we use the _history ensemble containing all past models
        args.model = args.model.replace('.joblib', '_history.joblib')
        
    model_path = str(Path(args.model).resolve())
    normalizer_path = str(Path(args.normalizer).resolve())
    
    # Load model
    print(f"\n[1/4] Loading model from {model_path}...")
    
    if not os.path.exists(normalizer_path):
        print(f"  [!] Normalizer not found at {normalizer_path}. Trying default location...")
        normalizer_path = "models/hybrid_normalizer_wf.npz"
        
    try:
        if args.ensemble:
            model, normalizer = load_ensemble_model(model_path, normalizer_path, args.model_size, device)
            print(f"  [OK] Ensemble model loaded")
        else:
            model, normalizer = load_hybrid_model(model_path, normalizer_path, args.model_size, device)
            print("  [OK] Model loaded")
    except Exception as e:
        print(f"  [ERROR] Error loading model: {e}")
        return
    
    # Check if GBT
    is_gbt = hasattr(model, 'predict_proba') and not isinstance(model, torch.nn.Module)

    # Load data
    print(f"\n[2/4] Loading data from {data_path}...")
    if str(data_path).endswith('.parquet'):
        df = pd.read_parquet(data_path)
    else:
        df = pd.read_csv(data_path)
        
    df['date'] = df['date'].astype(str)
    
    # Use specified date args if added, otherwise use min/max from dataset
    date_filter_1 = getattr(args, 'start_date', df['date'].min())
    date_filter_2 = getattr(args, 'end_date', df['date'].max())
    
    print(f"  [i] Filtering for {date_filter_1} to {date_filter_2}...")
    df = df[(df['date'] >= date_filter_1) & (df['date'] <= date_filter_2)].copy()
    if df.empty:
        print(f"  [!] Error: No data found in the {date_filter_1} to {date_filter_2} range.")
        sys.exit(1)
    print(f"  [OK] Loaded {len(df):,} samples")
    print(f"  [OK] Tickers: {df['ticker'].unique().tolist()}")
    print(f"  [OK] Dates: {df['date'].nunique()} unique days")
    
    # Prepare features
    print(f"\n[3/4] Running predictions...")
    expected_cols = normalizer.feature_names if getattr(normalizer, 'feature_names', None) is not None and len(normalizer.feature_names) > 0 else FEATURE_COLUMNS
    
    features = np.zeros((len(df), len(expected_cols)), dtype=np.float32)
    for i, col in enumerate(expected_cols):
        if col in df.columns:
            features[:, i] = df[col].values.astype(np.float32)
    features = np.nan_to_num(features, nan=0.0, posinf=5.0, neginf=-5.0)

    # Normalize
    features_norm = normalizer.transform(features)

    if is_gbt:
        # GBT inference
        if args.strict_wf:
            print(f"  [i] Using STRICT Walk-Forward inference (date-by-date filtering)...")
            probs = np.zeros((len(df), 3), dtype=np.float32)
            
            # Group by date to apply correct ensemble filter per day
            unique_dates = sorted(df['date'].unique())
            for d_str in unique_dates:
                # Find indices for this date
                mask = df['date'] == d_str
                idx = np.where(mask)[0]
                if len(idx) == 0: continue
                
                # Predict only for this day using the date as filter
                # date format in CSV is 'YYYYMMDD' (from line 658)
                probs[idx] = model.predict_proba(features_norm[idx], date=d_str)
        else:
            probs = model.predict_proba(features_norm)
            
        predictions = np.argmax(probs, axis=1)
        # Dummy Bayesian time parameters for GBT [mu_norm=0.5 (60m), sigma_minutes=0.0]
        mu_norm = np.full(len(features_norm), 0.5)
        sigma_minutes = np.zeros(len(features_norm))
        time_predictions = np.column_stack([mu_norm, sigma_minutes])
    else:
        # PyTorch inference
        features_tensor = torch.tensor(features_norm, dtype=torch.float32)
        batch_size = 1024  
        logits_list = []
        time_pred_list = []

        with torch.inference_mode():
            for i in range(0, len(features_tensor), batch_size):
                batch = features_tensor[i:i + batch_size].to(device)
                batch_logits, batch_time_pred = model(batch)
                logits_list.append(batch_logits.cpu())
                time_pred_list.append(batch_time_pred.cpu())

        logits = torch.cat(logits_list, dim=0)
        time_pred = torch.cat(time_pred_list, dim=0)
        probs = torch.softmax(logits, dim=-1).numpy()
        predictions = logits.argmax(dim=-1).numpy()
        
        time_params = time_pred.numpy()
        mu_norm = time_params[:, 0]
        log_sigma = time_params[:, 1]
        sigma_minutes = np.exp(log_sigma) * 180.0
        time_predictions = np.column_stack([mu_norm, sigma_minutes])
    
    print(f"  [OK] Predictions complete")
    print(f"    SHORT: {(predictions == 0).sum():,}")
    print(f"    HOLD:  {(predictions == 1).sum():,}")
    print(f"    LONG:  {(predictions == 2).sum():,}")
    
    # Simulate trades
    print(f"\n[4/4] Simulating trades (threshold={args.threshold}, cooldown={args.cooldown}min, target_L={args.target_long:.1%}, target_S={args.target_short:.1%}, stop={args.stop:.1%}, max_time={args.max_time}m, min_iv={args.min_iv}, σ_max={args.uncertainty}m)...")
    simulator = TradeSimulator(threshold=args.threshold, position_size=args.position_size, cooldown_minutes=args.cooldown,
                               target_long=args.target_long, target_short=args.target_short, stop_pct=args.stop, max_time=args.max_time, min_iv_pct=args.min_iv,
                               discord_enabled=args.discord, uncertainty_threshold=args.uncertainty, risk_capital=args.risk_capital)
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
                             target_long=args.target_long, target_short=args.target_short, stop_pct=args.stop, max_time=args.max_time, min_iv_pct=args.min_iv,
                             discord_enabled=False, uncertainty_threshold=args.uncertainty, risk_capital=args.risk_capital)
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
