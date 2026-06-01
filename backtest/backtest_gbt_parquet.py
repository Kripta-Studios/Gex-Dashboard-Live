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
from neural.signal_policy import (
    confidence_for_predictions,
    deployment_context_allowed,
    direction_from_prediction,
    is_actionable_signal,
    get_independent_signals,
)

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


def _row_nearest_level_dist_bps(row) -> float:
    """
    Distance to nearest deployment S/R level in bps.

    `nearest_level_dist` is broad: IB, fibs and Greek exposure levels.
    `nearest_level_dist_bps` is narrower IB/fib identity distance and is kept
    as fallback for old parquet files.
    """
    for col in ("nearest_level_dist", "nearest_level_dist_bps"):
        try:
            value = float(row.get(col, np.nan))
        except (AttributeError, TypeError, ValueError):
            continue
        if np.isfinite(value):
            return value
    return 999.0


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
                 discord_enabled: bool = False, trade_limit: int = 0,
                 risk_capital: float = 500.0, min_entry_minute: int = 580,
                 min_short_entry_minute: int | None = None,
                 min_short_price_vs_ib_high: float | None = None,
                 spx_target: float = 0.010, etf_target: float = 0.006,
                 spx_stop: float = 0.0025, etf_stop: float = 0.0025,
                 qqq_target: float | None = None, spy_target: float | None = None,
                 qqq_stop: float | None = None, spy_stop: float | None = None):
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
        self.min_entry_minute = min_entry_minute
        self.min_short_entry_minute = min_short_entry_minute
        self.min_short_price_vs_ib_high = min_short_price_vs_ib_high
        self.spx_target = spx_target
        self.etf_target = etf_target
        self.spx_stop = spx_stop
        self.etf_stop = etf_stop
        self.qqq_target = etf_target if qqq_target is None else qqq_target
        self.spy_target = etf_target if spy_target is None else spy_target
        self.qqq_stop = etf_stop if qqq_stop is None else qqq_stop
        self.spy_stop = etf_stop if spy_stop is None else spy_stop
        self.trades = []
        
    def load_ohlc_data(self, ticker, date):
        """Lazy load ThetaData 1-minute OHLC data for a ticker/date."""
        if (ticker, date) in self._ohlc_data_cache:
            return self._ohlc_data_cache[(ticker, date)]
        
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
                
                self._ohlc_data_cache[(ticker, date)] = parsed_series
                return parsed_series
            except Exception as e:
                print(f"Error loading Parquet data {filepath}: {e}")
        
        # Cache empty result if not found
        self._ohlc_data_cache[(ticker, date)] = []
        return []

    def simulate(self, df: pd.DataFrame, predictions: np.ndarray, probabilities: np.ndarray) -> pd.DataFrame:
        """
        Simulate trades based on predictions with cooldown between trades.
        """
        self._ohlc_data_cache = {} # Clear cache at start of simulation
        trades = []
        
        # Create a copy with predictions and sort properly
        df_work = df.copy()
        df_work['pred'] = predictions
        df_work['signal_confidence'] = confidence_for_predictions(probabilities, predictions)
        df_work['p_short'] = probabilities[:, 0]
        df_work['p_hold'] = probabilities[:, 1]
        df_work['p_long'] = probabilities[:, 2]
        df_work['signal_margin'] = np.abs(df_work['p_long'] - df_work['p_short'])
        
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
        ticker_consecutive_losses = {}
        
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
            signal_confidence = row['signal_confidence']
            direction = direction_from_prediction(pred)
            
            ticker = row['ticker']
            date = row['date']
            time_str = row['time']
            current_minute = row['minutes']
            
            # Graduated dynamic confidence threshold and risk sizing based on consecutive losses
            loss_streak_key = (ticker, date)
            if loss_streak_key not in ticker_consecutive_losses:
                ticker_consecutive_losses[loss_streak_key] = 0
            
            consec = ticker_consecutive_losses[loss_streak_key]
            if consec >= 4:
                # 4+ consecutive losses: very aggressive filter (P(L|LLLL) ≈ 65%+)
                effective_threshold = self.threshold + 0.20
                effective_risk_capital = self.risk_capital * 0.25
            elif consec >= 2:
                # 2-3 consecutive losses: moderate filter
                effective_threshold = self.threshold + 0.10
                effective_risk_capital = self.risk_capital * 0.50
            else:
                effective_threshold = self.threshold
                effective_risk_capital = self.risk_capital
                
            # --- DYNAMIC THRESHOLD BY TICKER & DIRECTION ---
            # Removed hardcoded overrides to allow natural evaluation based on label targets
            
            if not is_actionable_signal(direction, signal_confidence, base_confidence=effective_threshold):
                continue
            if not deployment_context_allowed(row, direction=direction):
                continue
            if current_minute < self.min_entry_minute:
                continue
            if (
                direction == "SHORT"
                and self.min_short_entry_minute is not None
                and current_minute < int(self.min_short_entry_minute)
            ):
                continue
            if (
                direction == "SHORT"
                and self.min_short_price_vs_ib_high is not None
                and float(row.get("price_vs_ib_high", 0.0)) < float(self.min_short_price_vs_ib_high)
            ):
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
            
            
            hold_minutes = int(self.max_time)
            
            # FILTER: Skip if Volatility (IV Percentile) is too low
            # iv_percentile is in dataframe
            if 'iv_percentile' in row and row['iv_percentile'] < self.min_iv_pct:
                continue
                
            # FILTER: Strict Price Action Confluence (User Edge)
            # Only trade if we are within 15 bps of a key level. Use the broad
            # collector distance so deployment matches labels: IB, fibs and
            # Greek exposure levels are all valid S/R anchors.
            level_dist_used = _row_nearest_level_dist_bps(row)
            if level_dist_used > 15.0:
                continue
            
            # --- HIGH RESOLUTION EXIT LOGIC ---
            exit_price = entry_price
            pnl = 0.0
            actual_hold_minutes = hold_minutes
            target_hit = False
            stop_hit = False
            trailing_stop_hit = False
            mae = 0.0
            peak_price = entry_price
            # --- TICKER TARGET/STOP ---
            ticker_stop = self.stop_pct
            ticker_target = self.target_long if direction == "LONG" else self.target_short

            if row.ticker == "QQQ":
                ticker_target = self.qqq_target
                ticker_stop = self.qqq_stop
            elif row.ticker == "SPY":
                ticker_target = self.spy_target
                ticker_stop = self.spy_stop
            elif row.ticker == "SPX":
                ticker_target = self.spx_target
                ticker_stop = self.spx_stop
            
            base_target = ticker_target
            
            # Load 1-minute data for this day
            minute_data = self.load_ohlc_data(ticker, date)
            
            if not minute_data:
                pass 
            else:
                entry_idx = -1
                for i, (m, o, h, l, c) in enumerate(minute_data):
                    if m >= current_minute:
                        entry_idx = i
                        break
                
                if entry_idx != -1:
                    exit_minute_limit = current_minute + hold_minutes
                    found_exit_scan = False
                    
                    for i in range(entry_idx, len(minute_data)):
                        m, o, h, l, c = minute_data[i]
                        
                        if m > exit_minute_limit:
                            exit_price = o
                            actual_hold_minutes = m - current_minute
                            found_exit_scan = True
                            break
                        
                        if direction == "LONG":
                            # Peak tracking
                            peak_price = max(peak_price, h)
                            peak_pnl = (peak_price - entry_price) / entry_price
                            
                            # Breakeven Stop: If we hit +0.4% profit, move stop to entry_price + 0.1%
                            current_stop_price = entry_price * (1 - ticker_stop)
                            if peak_pnl >= 0.004:
                                current_stop_price = max(current_stop_price, entry_price * 1.001)

                            # Stop Loss (Low triggers it)
                            if l <= current_stop_price:
                                exit_price = current_stop_price
                                stop_hit = True
                                actual_hold_minutes = m - current_minute
                                found_exit_scan = True
                                break
                            
                            # Take Profit (High triggers it)
                            if h >= entry_price * (1 + base_target):
                                exit_price = entry_price * (1 + base_target)
                                target_hit = True
                                actual_hold_minutes = m - current_minute
                                found_exit_scan = True
                                break
                                
                        else: # SHORT
                            # Peak tracking
                            peak_price = min(peak_price, l)
                            peak_pnl = (entry_price - peak_price) / entry_price
                            
                            # Breakeven Stop: If we hit +0.4% profit, move stop to entry_price - 0.1%
                            current_stop_price = entry_price * (1 + ticker_stop)
                            if peak_pnl >= 0.004:
                                current_stop_price = min(current_stop_price, entry_price * 0.999)

                            # Stop Loss (High triggers it)
                            if h >= current_stop_price:
                                exit_price = current_stop_price
                                stop_hit = True
                                actual_hold_minutes = m - current_minute
                                found_exit_scan = True
                                break
                                
                            # Take Profit (Low triggers it)
                            if l <= entry_price * (1 - base_target):
                                exit_price = entry_price * (1 - base_target)
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
                    tp_price = entry_price * (1 + base_target) if direction == "LONG" else entry_price * (1 - base_target)
                    sl_price = entry_price * (1 - ticker_stop) if direction == "LONG" else entry_price * (1 + ticker_stop)
                    
                    # Creamos un objeto Mock que imite lo que el Wrapper espera
                    class MockSignal:
                        def __init__(self, t, d, p, tp, sl):
                            self.ticker = t
                            self.direction = d
                            self.entry_price = p
                            self.stop_loss = sl
                            self.take_profit_1 = tp
                            self.take_profit_2 = tp * 1.05
                            self.raw_confidence = signal_confidence
                            self.calibrated_confidence = signal_confidence
                            self.position_size = 1.0
                            self.max_hold_time = hold_minutes
                            self.regime = "Backtest_Discovery"
                            self.reasoning = f"Backtest Signal (Prob: {signal_confidence:.2f})"

                    mock_signal = MockSignal(ticker, direction, entry_price, tp_price, sl_price)
                    
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
            contracts = _calc_contracts_futures(effective_risk_capital, entry_price, ticker_stop, multiplier)
            
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
            
            # Drawdown tracker updates
            if pnl_dollars > 0:
                ticker_consecutive_losses[loss_streak_key] = 0
            elif pnl_dollars < 0:
                ticker_consecutive_losses[loss_streak_key] += 1
            
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
                "confidence": signal_confidence,
                "p_short": float(row.get("p_short", np.nan)),
                "p_hold": float(row.get("p_hold", np.nan)),
                "p_long": float(row.get("p_long", np.nan)),
                "signal_margin": float(row.get("signal_margin", np.nan)),
                "nearest_level_dist_used_bps": float(level_dist_used),
                "nearest_level_dist": float(row.get("nearest_level_dist", np.nan)),
                "nearest_level_dist_bps": float(row.get("nearest_level_dist_bps", np.nan)),
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
            
            expected_exit_minute = current_minute + actual_hold_minutes
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

    hold_col = "actual_hold_minutes" if "actual_hold_minutes" in trades_df.columns else "hold_minutes"
    hold_values = trades_df[hold_col] if hold_col in trades_df.columns else pd.Series(dtype=float)
    winner_hold_values = wins[hold_col] if hold_col in wins.columns else pd.Series(dtype=float)
    exit_counts = trades_df["exit_reason"].value_counts() if "exit_reason" in trades_df.columns else pd.Series(dtype=int)
    
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
        "avg_hold_minutes": float(hold_values.mean()) if len(hold_values) > 0 else 0.0,
        "median_hold_minutes": float(hold_values.median()) if len(hold_values) > 0 else 0.0,
        "p25_hold_minutes": float(hold_values.quantile(0.25)) if len(hold_values) > 0 else 0.0,
        "p75_hold_minutes": float(hold_values.quantile(0.75)) if len(hold_values) > 0 else 0.0,
        "pct_hold_lt30": float((hold_values < 30).mean() * 100) if len(hold_values) > 0 else 0.0,
        "pct_hold_ge60": float((hold_values >= 60).mean() * 100) if len(hold_values) > 0 else 0.0,
        "pct_hold_ge120": float((hold_values >= 120).mean() * 100) if len(hold_values) > 0 else 0.0,
        "winner_avg_hold_minutes": float(winner_hold_values.mean()) if len(winner_hold_values) > 0 else 0.0,
        "winner_median_hold_minutes": float(winner_hold_values.median()) if len(winner_hold_values) > 0 else 0.0,
        "winner_pct_hold_ge60": float((winner_hold_values >= 60).mean() * 100) if len(winner_hold_values) > 0 else 0.0,
        "exit_target_trades": int(exit_counts.get("target", 0)),
        "exit_stop_trades": int(exit_counts.get("stop", 0)),
        "exit_trailing_stop_trades": int(exit_counts.get("trailing_stop", 0)),
        "exit_max_time_trades": int(exit_counts.get("max_time", 0)),
    }


def print_metrics(metrics: dict, title: str = ""):
    """Pretty print metrics."""
    print(f"\n{'=' * 60}")
    print(f"  {title}" if title else "  BACKTEST RESULTS")
    print(f"{'=' * 60}")
    
    if "error" in metrics:
        print(f"  [!] {metrics['error']}")
        return
    
    print(f"\n  TRADE SUMMARY")
    print(f"  {'-' * 40}")
    print(f"  Total trades:     {metrics['total_trades']:,}")
    print(f"  Wins:             {metrics['wins']:,}")
    print(f"  Losses:           {metrics['losses']:,}")
    print(f"  Flat:             {metrics['flat']:,}")
    
    print(f"\n  PERFORMANCE")
    print(f"  {'-' * 40}")
    print(f"  Win Rate:         {metrics['win_rate']:.1f}%")
    print(f"  Profit Factor:    {metrics['profit_factor']:.2f}")
    print(f"  Total P&L:        {metrics['total_pnl']:+.2f}")
    print(f"  Max Drawdown:     {metrics['max_drawdown']:.2f}")
    print(f"  Sharpe Ratio:     {metrics['sharpe_ratio']:.2f}")
    
    print(f"\n  BY DIRECTION")
    print(f"  {'-' * 40}")
    print(f"  LONG:  {metrics['long_trades']:,} trades | {metrics['long_win_rate']:.1f}% win | P&L: {metrics['long_pnl']:+.2f}")
    print(f"  SHORT: {metrics['short_trades']:,} trades | {metrics['short_win_rate']:.1f}% win | P&L: {metrics['short_pnl']:+.2f}")

    print(f"\n  HOLD / HOME-RUN PROFILE")
    print(f"  {'-' * 40}")
    print(f"  Avg hold:         {metrics['avg_hold_minutes']:.1f} min")
    print(f"  Median hold:      {metrics['median_hold_minutes']:.1f} min")
    print(f"  Hold p25 / p75:   {metrics['p25_hold_minutes']:.1f} / {metrics['p75_hold_minutes']:.1f} min")
    print(f"  Trades <30 min:   {metrics['pct_hold_lt30']:.1f}%")
    print(f"  Trades >=60 min:  {metrics['pct_hold_ge60']:.1f}%")
    print(f"  Trades >=120 min: {metrics['pct_hold_ge120']:.1f}%")
    print(f"  Winner avg hold:  {metrics['winner_avg_hold_minutes']:.1f} min")
    print(f"  Winner med hold:  {metrics['winner_median_hold_minutes']:.1f} min")
    print(f"  Winners >=60 min: {metrics['winner_pct_hold_ge60']:.1f}%")
    print(
        "  Exit reasons:     "
        f"target={metrics['exit_target_trades']:,}, "
        f"stop={metrics['exit_stop_trades']:,}, "
        f"trailing={metrics['exit_trailing_stop_trades']:,}, "
        f"max_time={metrics['exit_max_time_trades']:,}"
    )


def print_by_ticker(trades_df: pd.DataFrame):
    """Print metrics by ticker."""
    print(f"\n  BY TICKER")
    print(f"  {'-' * 40}")
    
    for ticker in trades_df["ticker"].unique():
        ticker_trades = trades_df[trades_df["ticker"] == ticker]
        metrics = calculate_metrics(ticker_trades)
        if "error" not in metrics:
            print(
                f"  {ticker:6s}: {metrics['total_trades']:4d} trades | "
                f"{metrics['win_rate']:5.1f}% win | PF {metrics['profit_factor']:.2f} | "
                f"P&L: {metrics['total_pnl']:+6.2f} | "
                f"hold med {metrics['median_hold_minutes']:.0f}m | >=60m {metrics['pct_hold_ge60']:.1f}%"
            )


# --- MAIN ---
def main():
    parser = argparse.ArgumentParser(description="Backtest hybrid trading model")
    parser.add_argument("--data", default="training_data/training_data_derived.parquet", help="Path to CSV data")
    parser.add_argument("--model", default="models/trading_hybrid_wf.pt", help="Path to model file")
    parser.add_argument("--normalizer", default="models/hybrid_normalizer_wf.npz", help="Path to normalizer file")
    parser.add_argument("--model-size", choices=["micro", "legacy", "small", "medium", "large"], default="small", help="Model size used during training")
    parser.add_argument("--threshold", type=float, default=0.45, help="Base confidence threshold for trades")
    parser.add_argument("--cooldown", type=int, default=30, help="Minutes between trades per ticker (default: 30)")
    parser.add_argument("--risk-capital", type=float, default=500.0, help="Risk capital in dollars per trade (fixed)")
    parser.add_argument("--position-size", type=float, default=1.0, help="Position size multiplier")
    parser.add_argument("--target_long", type=float, default=0.010, help="Target for LONG (default 1%%)")
    parser.add_argument("--target_short", type=float, default=0.005, help="Target for SHORT (default 0.5%%)")
    parser.add_argument("--stop", type=float, default=0.003, help="Stop loss %% (default: 0.3%%)")
    parser.add_argument("--spx-target", type=float, default=0.010, help="SPX target override used by the simulator.")
    parser.add_argument("--etf-target", type=float, default=0.006, help="SPY/QQQ target override used by the simulator.")
    parser.add_argument("--spx-stop", type=float, default=0.0025, help="SPX stop override used by the simulator.")
    parser.add_argument("--etf-stop", type=float, default=0.0025, help="SPY/QQQ stop override used by the simulator.")
    parser.add_argument("--qqq-target", type=float, default=None, help="QQQ target override; defaults to --etf-target.")
    parser.add_argument("--spy-target", type=float, default=None, help="SPY target override; defaults to --etf-target.")
    parser.add_argument("--qqq-stop", type=float, default=None, help="QQQ stop override; defaults to --etf-stop.")
    parser.add_argument("--spy-stop", type=float, default=None, help="SPY stop override; defaults to --etf-stop.")
    parser.add_argument("--max-time", type=int, default=180, help="Max predicted time to enter trade (default: 180 min)")
    parser.add_argument("--min-entry-minute", type=int, default=580, help="Earliest absolute minute of day for entries (10:30 = 630)")
    parser.add_argument("--min-short-entry-minute", type=int, default=None, help="Earliest absolute minute of day for SHORT entries (10:15 = 615)")
    parser.add_argument("--min-short-price-vs-ib-high", type=float, default=None, help="For SHORT entries, require price_vs_ib_high >= this value")
    parser.add_argument("--min-iv", type=float, default=0.0, help="Min IV Percentile (0-1) to trade (default: 0)")
    parser.add_argument("--discord", action="store_true", help="Send Discord alerts for trades (first 3 only)")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of trades to simulate (0 = all)")
    parser.add_argument("--ensemble", action="store_true", help="Load model as ensemble (use with ensemble-trained .pt files)")
    parser.add_argument("--strict-wf", action="store_true", help="Enable strict Walk-Forward (only use models trained before the trade date)")
    parser.add_argument("--tickers", nargs="+", help="Filter by specific tickers (e.g., SPY QQQ)")
    parser.add_argument(
        "--sensitivity-thresholds",
        nargs="+",
        type=float,
        default=[0.38, 0.40, 0.42, 0.45, 0.50],
        help="Confidence thresholds to test after the main backtest.",
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("  HYBRID MODEL BACKTESTING")
    print("=" * 60)
    print(f"  Configuration:")
    print(f"  • Threshold:  {args.threshold}")
    print(f"  • Target LONG: {args.target_long:.1%}")
    print(f"  • Target SHORT:{args.target_short:.1%}")
    print(f"  • Stop Loss:  {args.stop:.1%}")
    print(f"  • Ticker risk: SPX target/stop {args.spx_target:.1%}/{args.spx_stop:.2%}; "
          f"QQQ target/stop {(args.qqq_target if args.qqq_target is not None else args.etf_target):.1%}/{(args.qqq_stop if args.qqq_stop is not None else args.etf_stop):.2%}; "
          f"SPY target/stop {(args.spy_target if args.spy_target is not None else args.etf_target):.1%}/{(args.spy_stop if args.spy_stop is not None else args.etf_stop):.2%}")
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
    
    if args.strict_wf and args.model.endswith('.joblib') and not args.model.endswith('_history.joblib'):
        # In strict WF mode, we use the _history ensemble containing all past models
        args.model = args.model.replace('.joblib', '_history.joblib')
    model_path = str(Path(args.model).resolve())
    normalizer_path = str(Path(args.normalizer).resolve())
    
    # Load model
    print(f"\n[1/4] Loading model from {model_path}...")
    
    # Normalizer path may not exist as a base file if only ticker-specific ones exist.
    # We will check ticker-specific paths next.
    ticker_models = {}
    ticker_normalizers = {}
    is_ticker_specific = False
    
    for ticker in ["SPX", "QQQ", "SPY"]:
        if "_history.joblib" in model_path:
            t_model_path = model_path.replace("_history.joblib", f"_{ticker}_history.joblib")
        else:
            t_model_path = model_path.replace(".joblib", f"_{ticker}.joblib")
        t_norm_path = normalizer_path.replace(".npz", f"_{ticker}.npz")
        
        if os.path.exists(t_model_path) and os.path.exists(t_norm_path):
            print(f"  [i] Ticker-specific model found for {ticker}")
            try:
                if args.ensemble:
                    t_model, t_normalizer = load_ensemble_model(t_model_path, t_norm_path, args.model_size, device)
                else:
                    t_model, t_normalizer = load_hybrid_model(t_model_path, t_norm_path, args.model_size, device)
                ticker_models[ticker] = t_model
                ticker_normalizers[ticker] = t_normalizer
                is_ticker_specific = True
            except Exception as e:
                print(f"  [WARNING] Failed to load ticker-specific model for {ticker}: {e}")
                
    if is_ticker_specific:
        print(f"  [OK] Loaded ticker-specific models for: {list(ticker_models.keys())}")
        any_model = next(iter(ticker_models.values()))
        is_gbt = hasattr(any_model, 'predict_proba') and not isinstance(any_model, torch.nn.Module)
    else:
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
    
    if getattr(args, 'tickers', None):
        if len(args.tickers) == 1 and ' ' in args.tickers[0]:
            args.tickers = args.tickers[0].split(' ')
        print(f"  [i] Filtering to tickers: {args.tickers}")
        df = df[df['ticker'].isin(args.tickers)].copy()

    if df.empty:
        print(f"  [!] Error: No data found in the {date_filter_1} to {date_filter_2} range.")
        sys.exit(1)
    print(f"  [OK] Loaded {len(df):,} samples")
    print(f"  [OK] Tickers: {df['ticker'].unique().tolist()}")
    print(f"  [OK] Dates: {df['date'].nunique()} unique days")
    
    # Prepare features
    print(f"\n[3/4] Running predictions...")
    if is_ticker_specific:
        any_norm = next(iter(ticker_normalizers.values()))
        expected_cols = any_norm.feature_names if getattr(any_norm, 'feature_names', None) is not None and len(any_norm.feature_names) > 0 else FEATURE_COLUMNS
    else:
        expected_cols = normalizer.feature_names if getattr(normalizer, 'feature_names', None) is not None and len(normalizer.feature_names) > 0 else FEATURE_COLUMNS
    
    features = np.zeros((len(df), len(expected_cols)), dtype=np.float32)
    for i, col in enumerate(expected_cols):
        if col in df.columns:
            features[:, i] = df[col].values.astype(np.float32)
    features = np.nan_to_num(features, nan=0.0, posinf=5.0, neginf=-5.0)

    if args.strict_wf:
        print(f"  [i] Using STRICT Walk-Forward inference (date-by-date filtering)...")
        probs = np.zeros((len(df), 3), dtype=np.float32)
        unique_dates = sorted(df['date'].unique())
        for d_str in unique_dates:
            mask = df['date'] == d_str
            if is_ticker_specific:
                for ticker in df.loc[mask, 'ticker'].unique():
                    t_mask = mask & (df['ticker'] == ticker)
                    idx = np.where(t_mask)[0]
                    if len(idx) == 0:
                        continue
                    t_model = ticker_models[ticker]
                    t_norm = ticker_normalizers[ticker]
                    if is_gbt:
                        probs[idx] = t_model.predict_proba(features[idx], date=d_str)
                    else:
                        batch = torch.FloatTensor(t_norm.transform(features[idx])).to(device)
                        with torch.no_grad():
                            logits, _ = t_model(batch)
                        probs[idx] = torch.softmax(logits, dim=-1).cpu().numpy()
            else:
                idx = np.where(mask)[0]
                if len(idx) == 0:
                    continue
                if is_gbt:
                    probs[idx] = model.predict_proba(features[idx], date=d_str)
                else:
                    batch = torch.FloatTensor(normalizer.transform(features[idx])).to(device)
                    with torch.no_grad():
                        logits, _ = model(batch)
                    probs[idx] = torch.softmax(logits, dim=-1).cpu().numpy()
    else:
        probs = np.zeros((len(df), 3), dtype=np.float32)
        if is_ticker_specific:
            for ticker in df['ticker'].unique():
                t_mask = df['ticker'] == ticker
                idx = np.where(t_mask)[0]
                if len(idx) == 0:
                    continue
                t_model = ticker_models[ticker]
                t_norm = ticker_normalizers[ticker]
                if is_gbt:
                    probs[idx] = t_model.predict_proba(features[idx])
                else:
                    batch = torch.FloatTensor(t_norm.transform(features[idx])).to(device)
                    with torch.no_grad():
                        logits, _ = t_model(batch)
                    probs[idx] = torch.softmax(logits, dim=-1).cpu().numpy()
        else:
            if is_gbt:
                probs = model.predict_proba(features)
            else:
                batch = torch.FloatTensor(normalizer.transform(features)).to(device)
                with torch.no_grad():
                    logits, _ = model(batch)
                probs = torch.softmax(logits, dim=-1).cpu().numpy()
        
    predictions, _ = get_independent_signals(probs, base_confidence=args.threshold)
    
    print(f"  [OK] Predictions complete")
    print(f"    SHORT: {(predictions == 0).sum():,}")
    print(f"    HOLD:  {(predictions == 1).sum():,}")
    print(f"    LONG:  {(predictions == 2).sum():,}")
    
    # Simulate trades
    print(f"\n[4/4] Simulating trades (threshold={args.threshold}, cooldown={args.cooldown}min, target_L={args.target_long:.1%}, target_S={args.target_short:.1%}, stop={args.stop:.1%}, max_time={args.max_time}m, min_iv={args.min_iv}, min_entry_minute={args.min_entry_minute}, min_short_entry_minute={args.min_short_entry_minute}, min_short_price_vs_ib_high={args.min_short_price_vs_ib_high})...")
    simulator = TradeSimulator(threshold=args.threshold, position_size=args.position_size, cooldown_minutes=args.cooldown,
                               target_long=args.target_long, target_short=args.target_short, stop_pct=args.stop, max_time=args.max_time, min_iv_pct=args.min_iv,
                               discord_enabled=args.discord, risk_capital=args.risk_capital, min_entry_minute=args.min_entry_minute,
                               min_short_entry_minute=args.min_short_entry_minute,
                               min_short_price_vs_ib_high=args.min_short_price_vs_ib_high,
                               spx_target=args.spx_target, etf_target=args.etf_target,
                               spx_stop=args.spx_stop, etf_stop=args.etf_stop,
                               qqq_target=args.qqq_target, spy_target=args.spy_target,
                               qqq_stop=args.qqq_stop, spy_stop=args.spy_stop)
    trades_df = simulator.simulate(df, predictions, probs)
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
    print(f"  {'-' * 54}")
    
    for thresh in args.sensitivity_thresholds:
        thresh_predictions, _ = get_independent_signals(probs, base_confidence=thresh)
        sim = TradeSimulator(threshold=thresh, cooldown_minutes=args.cooldown,
                             target_long=args.target_long, target_short=args.target_short, stop_pct=args.stop, max_time=args.max_time, min_iv_pct=args.min_iv,
                             discord_enabled=False, risk_capital=args.risk_capital, min_entry_minute=args.min_entry_minute,
                             min_short_entry_minute=args.min_short_entry_minute,
                             min_short_price_vs_ib_high=args.min_short_price_vs_ib_high,
                             spx_target=args.spx_target, etf_target=args.etf_target,
                             spx_stop=args.spx_stop, etf_stop=args.etf_stop,
                             qqq_target=args.qqq_target, spy_target=args.spy_target,
                             qqq_stop=args.qqq_stop, spy_stop=args.spy_stop)
        trades = sim.simulate(df, thresh_predictions, probs)
        m = calculate_metrics(trades)
        if "error" not in m:
            print(f"  {thresh:<12.2f} {m['total_trades']:<10,} {m['win_rate']:<12.1f}% {m['profit_factor']:<10.2f} {m['total_pnl']:<+10.2f}")
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
