"""
RL Backtest — GBT+RL vs GBT-only Comparison

Runs two parallel simulations on the same data:
1. GBT-only: directional entry at spot, exit at target/stop (same as backtest_hybrid_parquet.py)
2. GBT+RL: RL agent selects strike (delta bucket) + manages exit using options pricing

Usage:
    python backtest_rl.py --data ../training_data/training_data_derived.parquet
    python backtest_rl.py --rl-model ../rl_models/best_rl_agent.pt --model ../models/trading_hybrid_wf.pt
"""

import os
import sys
import argparse
import numpy as np
import pandas as pd
import torch
from pathlib import Path
from datetime import datetime
import time as _time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "neural"))

from hybrid_model import (
    get_hybrid_model, get_device, load_hybrid_model, load_ensemble_model,
    FeatureNormalizer, FEATURE_COLUMNS
)
from neural.rl.config import RL_CONFIG, HARD_EXITS, STRIKE_BUCKETS, SNIPER_TOTAL_STATE_DIM, MLP_CONTEXT_DIM, SNIPER_STATE_DIM
from neural.rl.agent import PPOAgent
from rl.rewards import compute_step_reward, compute_terminal_reward


# ─────────────────────────────────────────────────────────────────────────
# GBT-ONLY SIMULATOR (aligned with backtest_hybrid_parquet.py)
# ─────────────────────────────────────────────────────────────────────────

# OHLC data cache for intrabar exit detection
_ohlc_cache: dict = {}

def _load_ohlc_data(ticker: str, date_str: str) -> list:
    """Load 1-minute OHLC data from ThetaData underlying derived parquets."""
    cache_key = (ticker, date_str)
    if cache_key in _ohlc_cache:
        return _ohlc_cache[cache_key]

    file_ticker = "SPXW" if ticker.replace("/", "") == "SPX" else ticker
    year, month = date_str[:4], date_str[4:6]
    filepath = Path(f"D:/ThetaData/data_underlying_derived/{file_ticker}/{year}/{month}/{file_ticker}_{date_str}.parquet")

    if filepath.exists():
        try:
            df_ohlc = pd.read_parquet(filepath)
            df_ohlc['dt'] = pd.to_datetime(df_ohlc['timestamp'])
            df_ohlc = df_ohlc[
                (df_ohlc['dt'].dt.time >= pd.Timestamp('08:00').time()) &
                (df_ohlc['dt'].dt.time <= pd.Timestamp('17:00').time())
            ]
            parsed = []
            for _, row in df_ohlc.iterrows():
                t = row['dt']
                mins = t.hour * 60 + t.minute
                parsed.append((mins, float(row['open']), float(row['high']),
                               float(row['low']), float(row['close'])))
            _ohlc_cache[cache_key] = parsed
            return parsed
        except Exception:
            pass

    _ohlc_cache[cache_key] = []
    return []


def _time_to_minutes(t) -> int:
    try:
        h, m = map(int, str(t).split(':'))
        return h * 60 + m
    except Exception:
        return 0


# Fixed point values per ticker
GBT_POINT_VALUES = {
    "SPX": 50.0, "/ES": 50.0, "/NQ": 20.0,
    "SPY": 100.0, "QQQ": 100.0,
}

# ── Position Sizing ──
INITIAL_BALANCE = 10_000.0

def _calc_contracts_futures(risk_capital: float, entry_price: float, stop_pct: float, multiplier: float) -> int:
    """Contracts for futures (SPX spot): risk_capital / max_loss_per_contract."""
    max_loss_per_contract = entry_price * stop_pct * multiplier
    if max_loss_per_contract <= 0:
        return 1
    return max(1, int(risk_capital / max_loss_per_contract))

def _calc_contracts_options(risk_capital: float, entry_premium: float) -> int:
    """Contracts for options: risk_capital / cost_per_contract ($100 multiplier)."""
    cost_per_contract = entry_premium * 100.0
    if cost_per_contract <= 0:
        return 1
    return max(1, int(risk_capital / cost_per_contract))


def simulate_mlp_only(df: pd.DataFrame, predictions: np.ndarray,
                      probabilities: np.ndarray, threshold: float = 0.50,
                      target_long: float = 0.010, target_short: float = 0.005,
                      stop_pct: float = 0.003, max_time: int = 180,
                      cooldown: int = 10, risk_capital: float = 500.0) -> pd.DataFrame:
    """
    Simulate GBT-only trades using spot price targets/stops.
    Aligned with backtest_hybrid_parquet.py: real dollar P&L, OHLC intrabar
    detection, open position tracking, first-10-min skip.
    """
    trades = []
    last_trade_minute = {}   # (ticker, date) -> last entry minute
    open_positions = {}      # (ticker, date) -> expected exit minute
    balance = INITIAL_BALANCE  # equity tracking

    # Drawdown mitigation sequence limit
    consecutive_losses = 0
    in_drawdown_mode = False
    drawdown_watermark = balance

    # Merge predictions into dataframe for proper sorting
    df_work = df.copy()
    df_work['pred'] = predictions
    df_work['max_prob'] = probabilities.max(axis=1)
    df_work['minutes'] = df_work['time'].apply(_time_to_minutes)
    df_work['date'] = df_work['date'].astype(str)
    df_work = df_work.sort_values(['ticker', 'date', 'minutes']).reset_index(drop=True)

    dates = sorted(df_work['date'].unique())
    total_dates = len(dates)
    t_start = _time.time()
    report_interval = max(1, total_dates // 10)

    for d_idx, d in enumerate(dates):
        day_df = df_work[df_work['date'] == d]

        for _, row in day_df.iterrows():
            pred = row['pred']
            max_prob = row['max_prob']
            current_minute = row['minutes']
            ticker = row.get('ticker', 'SPX')

            if pred == 1 or max_prob < threshold:
                continue

            # Skip first 10 minutes (9:30-9:40) — market opening noise
            if 570 <= current_minute < 580:
                continue

            direction = "LONG" if pred == 2 else "SHORT"

            # Open position check — don't overlap
            if (ticker, d) in open_positions:
                if current_minute < open_positions[(ticker, d)]:
                    continue
                else:
                    del open_positions[(ticker, d)]

            # Cooldown check (in real minutes, not row indices)
            last_min = last_trade_minute.get((ticker, d), -999)
            if current_minute - last_min < cooldown:
                continue

            entry_price = row.get('spot_price', 0)
            if entry_price <= 0:
                continue

            base_target = target_long if direction == "LONG" else target_short

            # ── OHLC intrabar exit simulation ──
            ohlc = _load_ohlc_data(ticker, d)
            exit_price = entry_price
            actual_hold_minutes = max_time
            target_hit = False
            stop_hit = False
            mae = 0.0

            if ohlc:
                # Find entry index in OHLC data
                entry_idx = -1
                for ohlc_i, (m, o, h, l, c) in enumerate(ohlc):
                    if m >= current_minute:
                        entry_idx = ohlc_i
                        break

                if entry_idx >= 0:
                    # Scan forward minute by minute using OHLC
                    found_exit = False
                    for ohlc_j in range(entry_idx + 1, len(ohlc)):
                        m, o, h, l, c = ohlc[ohlc_j]
                        elapsed = m - current_minute
                        if elapsed > max_time:
                            exit_price = c
                            actual_hold_minutes = max_time
                            found_exit = True
                            break

                        if direction == "LONG":
                            # Track MAE (lowest point)
                            if l < entry_price:
                                current_mae = (l - entry_price) / entry_price
                                mae = min(mae, current_mae)
                                
                            # Stop loss (low triggers)
                            if l <= entry_price * (1 - stop_pct):
                                exit_price = entry_price * (1 - stop_pct)
                                stop_hit = True
                                actual_hold_minutes = elapsed
                                found_exit = True
                                break
                            # Take profit (high triggers)
                            if h >= entry_price * (1 + base_target):
                                exit_price = entry_price * (1 + base_target)
                                target_hit = True
                                actual_hold_minutes = elapsed
                                found_exit = True
                                break
                        else:  # SHORT
                            # Track MAE (highest point)
                            if h > entry_price:
                                current_mae = (entry_price - h) / entry_price
                                mae = min(mae, current_mae)
                                
                            # Stop loss (high triggers)
                            if h >= entry_price * (1 + stop_pct):
                                exit_price = entry_price * (1 + stop_pct)
                                stop_hit = True
                                actual_hold_minutes = elapsed
                                found_exit = True
                                break
                            # Take profit (low triggers)
                            if l <= entry_price * (1 - base_target):
                                exit_price = entry_price * (1 - base_target)
                                target_hit = True
                                actual_hold_minutes = elapsed
                                found_exit = True
                                break

                    if not found_exit:
                        exit_price = ohlc[-1][4]  # Close of last candle
                        actual_hold_minutes = ohlc[-1][0] - current_minute
            else:
                # Fallback: scan training data rows (no OHLC available)
                day_after = day_df[day_df['minutes'] > current_minute]
                for _, future_row in day_after.head(max_time).iterrows():
                    price = future_row.get('spot_price', entry_price)
                    elapsed = future_row['minutes'] - current_minute
                    if elapsed > max_time:
                        break
                    if direction == "LONG":
                        if price < entry_price:
                            current_mae = (price - entry_price) / entry_price
                            mae = min(mae, current_mae)
                            
                        if price >= entry_price * (1 + base_target):
                            exit_price = entry_price * (1 + base_target)
                            target_hit = True
                            actual_hold_minutes = elapsed
                            break
                        elif price <= entry_price * (1 - stop_pct):
                            exit_price = entry_price * (1 - stop_pct)
                            stop_hit = True
                            actual_hold_minutes = elapsed
                            break
                    else:
                        if price > entry_price:
                            current_mae = (entry_price - price) / entry_price
                            mae = min(mae, current_mae)
                            
                        if price <= entry_price * (1 - base_target):
                            exit_price = entry_price * (1 - base_target)
                            target_hit = True
                            actual_hold_minutes = elapsed
                            break
                        elif price >= entry_price * (1 + stop_pct):
                            exit_price = entry_price * (1 + stop_pct)
                            stop_hit = True
                            actual_hold_minutes = elapsed
                            break
                    exit_price = price
                    actual_hold_minutes = elapsed

            if exit_price <= 0:
                continue

            # Real dollar P&L with dynamic sizing
            multiplier = GBT_POINT_VALUES.get(ticker, 100.0)
            contracts = _calc_contracts_futures(risk_capital, entry_price, stop_pct, multiplier)

            # Apply contract limits
            contracts = min(contracts, 1000) # Max 1000 spot contracts

            if direction == "LONG":
                pnl_pts = exit_price - entry_price
            else:
                pnl_pts = entry_price - exit_price
            pnl_dollars = pnl_pts * multiplier * contracts
            pnl_pct = pnl_pts / entry_price
            balance += pnl_dollars

            # Drawdown tracker updates
            if pnl_dollars > 0:
                consecutive_losses = 0
                if in_drawdown_mode and balance >= drawdown_watermark:
                    in_drawdown_mode = False
            elif pnl_dollars < 0:
                if consecutive_losses == 0 and not in_drawdown_mode:
                    drawdown_watermark = balance - pnl_dollars
                consecutive_losses += 1
                if consecutive_losses >= 3:
                    in_drawdown_mode = True

            exit_reason = "target" if target_hit else "stop" if stop_hit else "max_time"

            # Compute approximate exit time from entry minute + actual hold minutes
            exit_minute = current_minute + actual_hold_minutes
            exit_time_str = f"{exit_minute // 60:02d}:{exit_minute % 60:02d}"
            entry_time_str = f"{current_minute // 60:02d}:{current_minute % 60:02d}"

            trades.append({
                "date": d, "entry_time": entry_time_str, "exit_time": exit_time_str,
                "ticker": ticker, "direction": direction,
                "entry_price": entry_price, "exit_price": exit_price,
                "pnl_pct": pnl_pct, "pnl_dollars": pnl_dollars,
                "hold_minutes": actual_hold_minutes, "exit_reason": exit_reason,
                "confidence": max_prob, "contracts": contracts,
                "mae": mae,
                "balance": round(balance, 2),
            })

            last_trade_minute[(ticker, d)] = current_minute
            open_positions[(ticker, d)] = current_minute + actual_hold_minutes

        # Progress reporting
        if (d_idx + 1) % report_interval == 0 or d_idx == total_dates - 1:
            elapsed = _time.time() - t_start
            pct = (d_idx + 1) / total_dates * 100
            rate = (d_idx + 1) / elapsed if elapsed > 0 else 0
            eta = (total_dates - d_idx - 1) / rate if rate > 0 else 0
            current_wr = 0.0
            if trades:
                wins = sum(1 for t in trades if t["pnl_dollars"] > 0)
                current_wr = wins / len(trades) * 100
            print(f"    [{pct:5.1f}%] {d_idx+1}/{total_dates} days | "
                  f"{len(trades)} trades (WR {current_wr:.1f}%) | "
                  f"ETA {int(eta)}s")

    return pd.DataFrame(trades)


# ─────────────────────────────────────────────────────────────────────────
# OPTIONS DATA LOADING
# ─────────────────────────────────────────────────────────────────────────

THETADATA_DIR = os.environ.get("THETADATA_DIR", r"D:\ThetaData")
OPTIONS_DIR = os.path.join(THETADATA_DIR, "data_options")

# Columns needed from greeks parquet — skip everything else to save RAM
_GREEKS_COLS = ["underlying_timestamp", "strike", "right", "delta",
                "bid", "ask", "implied_vol", "theta", "gamma", "underlying_price"]

# Map training-data ticker names to ThetaData options directory names
_TICKER_TO_OPTIONS = {"SPX": "SPXW", "SPXW": "SPXW", "QQQ": "QQQ"}

def _load_daily_greeks(date_str: str, ticker: str = "SPXW") -> tuple:
    """
    Load 0DTE greeks parquet for a given date and ticker.
    Returns (df, premium_lookup, greeks_lookup) where:
        premium_lookup: {(time_str, strike, right_upper): mid_price}
        greeks_lookup:  {(time_str, strike, right_upper): {delta, theta, iv}}
    Returns (None, None, None) if not found.
    """
    options_ticker = _TICKER_TO_OPTIONS.get(ticker, ticker)
    year, month = date_str[:4], date_str[4:6]
    search_dir = Path(OPTIONS_DIR) / options_ticker / "greeks" / year / month
    if not search_dir.exists():
        return None, None, None
    files = list(search_dir.glob(f"{options_ticker}_*_{date_str}_greeks.parquet"))
    # Find 0DTE: expiration == trade date
    for f in files:
        exp = f.name.split('_')[1]
        if exp == date_str:
            try:
                # Column-filtered load: ~50-80% less RAM
                import pyarrow.parquet as pq
                schema_cols = [c.name for c in pq.ParquetFile(f).schema]
                cols_to_load = [c for c in _GREEKS_COLS if c in schema_cols]
                df = pd.read_parquet(f, columns=cols_to_load)
                df["dt"] = pd.to_datetime(df["underlying_timestamp"])
                df["time_str"] = df["dt"].dt.strftime("%H:%M")
                df["right_upper"] = df["right"].str.upper()
                df["delta_abs"] = df["delta"].abs()

                # Vectorized mid-price computation (no iterrows!)
                bid = df["bid"].fillna(0).astype(float)
                ask = df["ask"].fillna(0).astype(float)
                df["mid"] = ((bid + ask) / 2.0).where((bid > 0) | (ask > 0), 0.0)

                # Build O(1) lookup from valid mid-prices using vectorized ops
                valid = df[df["mid"] > 0].copy()
                valid["_key"] = list(zip(valid["time_str"], valid["strike"].astype(float), valid["right_upper"]))
                premium_lookup = dict(zip(valid["_key"], valid["mid"]))

                # Build O(1) greeks lookup: (time, strike, right) -> {delta, theta, iv}
                greeks_lookup = {}
                for key, delta, theta, iv in zip(
                    valid["_key"],
                    valid["delta"].fillna(0).astype(float),
                    valid.get("theta", pd.Series(0, index=valid.index)).fillna(0).astype(float),
                    valid.get("implied_vol", pd.Series(0.15, index=valid.index)).fillna(0.15).astype(float),
                ):
                    greeks_lookup[key] = {"delta": float(delta), "theta": float(theta), "iv": float(iv)}

                return df, premium_lookup, greeks_lookup
            except Exception as e:
                import traceback
                print(f"    [GREEKS ERROR] {options_ticker}/{date_str}: {e}")
                traceback.print_exc()
                return None, None, None
    return None, None, None


def _find_strike_by_delta(df_slice: pd.DataFrame, direction: str,
                          delta_target: float) -> dict | None:
    """
    Find the real strike closest to delta_target from options chain snapshot.
    For LONG: use CALLs (positive delta).  For SHORT: use PUTs (negative delta, compare abs).
    Returns dict with {strike, mid_price, delta, iv, theta, gamma} or None.
    """
    if direction == "LONG":
        opt = df_slice[df_slice["right_upper"].isin(["CALL", "C"])].copy()
    else:
        opt = df_slice[df_slice["right_upper"].isin(["PUT", "P"])].copy()
    if opt.empty:
        return None

    # Filter out zero-bid strikes (no real market)
    if "bid" in opt.columns:
        opt = opt[opt["bid"] > 0]
    opt = opt[opt["delta_abs"] > 0.01]  # Filter out near-zero delta
    if opt.empty:
        return None

    # Find closest to target delta
    opt["delta_diff"] = (opt["delta_abs"] - delta_target).abs()
    best = opt.loc[opt["delta_diff"].idxmin()]

    bid = float(best.get("bid", 0))
    ask = float(best.get("ask", 0))
    mid = (bid + ask) / 2.0 if (bid > 0 or ask > 0) else 0.0

    if mid <= 0:
        return None

    return {
        "strike": float(best["strike"]),
        "mid_price": mid,
        "bid": bid,
        "ask": ask,
        "delta": float(best.get("delta", delta_target)),
        "iv": float(best.get("implied_vol", 0.15)),
        "theta": float(best.get("theta", 0)),
        "gamma": float(best.get("gamma", 0)),
        "right": "CALL" if direction == "LONG" else "PUT",
    }


def _get_premium_at_time(premium_lookup: dict, strike: float,
                         right: str, time_str: str) -> float | None:
    """O(1) dict lookup for mid-price of a specific strike/right at a given time."""
    right_upper = right.upper()
    # Try exact match first
    mid = premium_lookup.get((time_str, strike, right_upper))
    if mid is not None and mid > 0:
        return mid
    # Try alternate right format (CALL vs C)
    alt_right = right_upper[0] if len(right_upper) > 1 else right_upper
    mid = premium_lookup.get((time_str, strike, alt_right))
    return mid if mid is not None and mid > 0 else None


# ─────────────────────────────────────────────────────────────────────────
# GBT+RL SIMULATOR (REAL OPTIONS PRICING)
# ─────────────────────────────────────────────────────────────────────────

def simulate_mlp_rl(df: pd.DataFrame, predictions: np.ndarray,
                    probabilities: np.ndarray, rl_agent: PPOAgent,
                    threshold: float = 0.50, max_time: int = 180,
                    cooldown: int = 10, device: torch.device = None,
                    risk_capital: float = 500.0) -> pd.DataFrame:
    """Simulate GBT+RL trades using REAL options pricing from ThetaData."""
    trades = []
    skipped_diagnostics = []
    last_trade_time = {}
    open_positions = {}
    device = device or torch.device("cpu")
    rl_agent.eval()
    balance = INITIAL_BALANCE  # equity tracking

    # Drawdown mitigation sequence limit
    consecutive_losses = 0
    in_drawdown_mode = False
    drawdown_watermark = balance

    # Cache daily greeks by date to avoid re-loading
    # Each entry is (df, premium_lookup) or (None, None)
    _greeks_cache: dict[str, tuple] = {}
    options_loaded = 0
    options_missed = 0

    dates = sorted(df["date"].unique())
    total_dates = len(dates)
    t_start = _time.time()
    report_interval = max(1, total_dates // 10)  # report every ~10%

    for d_idx, d in enumerate(dates):
        d_str = str(d)
        day_df = df[df["date"] == d].copy()
        day_df = day_df.sort_values("time")
        if "minutes" not in day_df.columns:
            day_df["minutes"] = day_df["time"].apply(_time_to_minutes)
        day_idx = day_df.index.tolist()

        # Greeks are now loaded per-ticker inside the trade loop below
        # (cache keyed by (ticker, date) instead of date only)

        # Pre-extract market features for the day to avoid pandas overhead
        n_features = len(FEATURE_COLUMNS)
        day_features = np.zeros((len(day_idx), n_features), dtype=np.float32)
        for fi, col in enumerate(FEATURE_COLUMNS[:n_features]):
            if col in day_df.columns:
                day_features[:, fi] = day_df[col].fillna(0).values.astype(np.float32)

        for i, global_idx in enumerate(day_idx):
            row = day_df.loc[global_idx]
            pred = predictions[global_idx]
            max_prob = probabilities[global_idx].max()

            if pred == 1 or max_prob < threshold:
                continue

            direction = "LONG" if pred == 2 else "SHORT"
            ticker = row.get("ticker", "SPX")

            key = f"{ticker}_{d}"
            
            # Open position check — don't overlap
            if key in open_positions:
                if i < open_positions[key]:
                    continue
                else:
                    del open_positions[key]
                    
            if key in last_trade_time:
                elapsed = i - last_trade_time[key]
                if elapsed < cooldown:
                    continue

            entry_price = row.get("spot_price", 0)
            if entry_price == 0:
                continue

            entry_time = str(row.get("time", "09:30"))
            try:
                h, m = map(int, entry_time.split(':'))
                current_minute = h * 60 + m
            except Exception:
                current_minute = 570
                
            # Skip trades in the first 10 minutes (09:30-09:39) due to unstable options pricing.
            if 570 <= current_minute < 580:
                continue

            # Retrieve pre-calculated market features
            market_features = day_features[i]

            # Model context: [confidence, time_to_target, mins_since_signal, log_sigma]
            mlp_context = np.array([max_prob, 0.5, 0.0, 0.0], dtype=np.float32)
            sniper_state = np.zeros(SNIPER_STATE_DIM, dtype=np.float32)

            # ── ENTRY: RL strike selection ──
            position_state = np.zeros(6, dtype=np.float32)
            state = np.concatenate([market_features, position_state, mlp_context, sniper_state])
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(device)

            with torch.no_grad():
                action, _, _ = rl_agent.get_action(
                    state_tensor, action_type="strike", deterministic=True)
            strike_bucket = action["strike"]
            delta_target = STRIKE_BUCKETS[strike_bucket]["delta_target"]

            # ── Find REAL option contract ──
            entry_chain = None
            actual_strike = None
            entry_premium = None
            actual_delta = delta_target
            actual_iv = 0.15
            actual_theta = 0.0
            actual_gamma = 0.0
            option_right = "CALL" if direction == "LONG" else "PUT"
            using_real_data = False

            # Load greeks per-ticker (cached by (ticker, date))
            cache_key = f"{ticker}_{d_str}"
            if cache_key not in _greeks_cache:
                _greeks_cache[cache_key] = _load_daily_greeks(d_str, ticker)
                # Evict oldest entries to limit memory
                if len(_greeks_cache) > 30:
                    oldest_key = next(iter(_greeks_cache))
                    del _greeks_cache[oldest_key]
            df_greeks, premium_lookup, greeks_lookup = _greeks_cache[cache_key]

            if df_greeks is not None:
                # Get options snapshot at strict entry time
                entry_slice = df_greeks[df_greeks["time_str"] == entry_time]
                if not entry_slice.empty:
                    entry_chain = _find_strike_by_delta(entry_slice, direction, delta_target)

            if entry_chain is not None:
                actual_strike = entry_chain["strike"]
                entry_premium = entry_chain["mid_price"]
                actual_delta = entry_chain["delta"]
                actual_iv = entry_chain["iv"]
                actual_theta = entry_chain["theta"]
                actual_gamma = entry_chain["gamma"]
                option_right = entry_chain["right"]
                using_real_data = True
                options_loaded += 1
            else:
                options_missed += 1
                skipped_diagnostics.append({"date": d_str, "time": entry_time, "ticker": ticker, "direction": direction})
                continue  # Skip trades without real options data

            # ── Forward simulation with REAL premiums ──
            mae = 0.0
            exit_price_spot = entry_price
            exit_premium = entry_premium
            exit_reason = "max_time"
            hold_minutes = 0
            premium_pnl_pct = 0.0

            # Isolate future rows specific to this ticker
            ticker_mask = (day_df["ticker"] == ticker) & (day_df["minutes"] >= current_minute)
            ticker_df = day_df[ticker_mask]
            
            # Skip the first row (which is the entry minute itself)
            future_sub_df = ticker_df.iloc[1:max_time+1]

            for idx_global, future_row in future_sub_df.iterrows():
                price = future_row.get("spot_price", entry_price)
                future_time = str(future_row.get("time", ""))
                hold_minutes = future_row["minutes"] - current_minute
                
                # Failsafe
                if hold_minutes > max_time:
                    break

                # Look up REAL premium at this timestamp
                current_premium = None
                if premium_lookup is not None and actual_strike is not None:
                    current_premium = _get_premium_at_time(
                        premium_lookup, actual_strike, option_right, future_time)

                if current_premium is not None and current_premium > 0:
                    # Real P&L: for LONG calls, profit = exit - entry
                    # For SHORT (puts bought), profit = exit - entry (puts gain when spot drops)
                    premium_pnl_pct = (current_premium - entry_premium) / entry_premium
                else:
                    # Fallback: extrapolate from last known premium using delta approximation
                    spot_change = price - entry_price
                    premium_change = actual_delta * spot_change + 0.5 * actual_gamma * spot_change**2
                    if direction == "SHORT":
                        premium_change = -premium_change  # puts move inversely
                    current_premium = max(0.01, entry_premium + premium_change)
                    premium_pnl_pct = (current_premium - entry_premium) / entry_premium

                premium_pnl_pct = float(np.clip(premium_pnl_pct, -1.0, 10.0))
                mae = min(mae, premium_pnl_pct)
                exit_premium = current_premium

                # Hard exit checks
                if premium_pnl_pct <= HARD_EXITS["max_loss_pct"]:
                    exit_reason = "hard_stop"
                    exit_price_spot = price
                    break
                if premium_pnl_pct >= HARD_EXITS["max_profit_pct"]:
                    exit_reason = "hard_take_profit"
                    exit_price_spot = price
                    break

                # Build RL state for exit decision — use PER-MINUTE greeks
                hold_norm = hold_minutes / HARD_EXITS["max_hold_minutes"]

                # Fetch current greeks from lookup at this minute
                right_upper = option_right.upper()
                alt_right = right_upper[0] if len(right_upper) > 1 else right_upper
                minute_greeks = None
                if greeks_lookup is not None and actual_strike is not None:
                    minute_greeks = greeks_lookup.get((future_time, actual_strike, right_upper))
                    if minute_greeks is None:
                        minute_greeks = greeks_lookup.get((future_time, actual_strike, alt_right))

                if minute_greeks is not None:
                    cur_delta = minute_greeks["delta"]
                    cur_theta = minute_greeks["theta"]
                    cur_iv = minute_greeks["iv"]
                else:
                    cur_delta = actual_delta  # fallback to entry
                    cur_theta = actual_theta
                    cur_iv = actual_iv

                # Normalize theta by entry premium
                theta_vs = float(np.clip(cur_theta / entry_premium, -0.5, 0.0)) if entry_premium > 0 else -0.05
                iv_ratio = cur_iv / 0.15 if cur_iv > 0 else 1.0

                position_state = np.array([
                    np.clip(premium_pnl_pct, -1.0, 5.0),
                    np.clip(hold_norm, 0.0, 1.0),
                    abs(cur_delta),
                    theta_vs,
                    np.clip(iv_ratio, 0.5, 3.0),
                    np.clip(mae, -1.0, 0.0),
                ], dtype=np.float32)

                # Update market features from pre-calculated array.
                # `idx_global` is the original dataframe index. To match `day_features`, 
                # we must find its positional index within `day_idx`.
                pos_idx = day_idx.index(idx_global)
                market_features = day_features[pos_idx]

                state = np.concatenate([market_features, position_state, mlp_context, sniper_state])
                state_tensor = torch.FloatTensor(state).unsqueeze(0).to(device)

                with torch.no_grad():
                    exit_action, _, _ = rl_agent.get_action(
                        state_tensor, action_type="exit", deterministic=True)

                if exit_action == 1:  # EXIT
                    # Ensure agent respects Phase 3 min_hold unless emergency_stop is hit
                    min_hold = RL_CONFIG["hold_min_minutes_curriculum"][3]["min_hold"]
                    emergency_stop = RL_CONFIG.get("emergency_stop_pct", -0.30)
                    is_emergency = premium_pnl_pct <= emergency_stop
                    
                    if hold_minutes >= min_hold or is_emergency:
                        exit_reason = "agent_exit"
                        exit_price_spot = price
                        break

                exit_price_spot = price

            # Real strike distance from spot
            strike_distance_pts = actual_strike - entry_price if actual_strike else 0.0

            # Dynamic sizing for options (risk % of balance)
            contracts = _calc_contracts_options(risk_capital, entry_premium) if entry_premium else 1

            # Apply contract limits
            contracts = min(contracts, 500) # Max 500 options contracts
            
            # P&L in dollars: premium_change * 100 * contracts
            premium_pnl_dollars = (exit_premium - entry_premium) * 100.0 * contracts
            balance += premium_pnl_dollars

            # Drawdown tracker updates
            if premium_pnl_dollars > 0:
                consecutive_losses = 0
                if in_drawdown_mode and balance >= drawdown_watermark:
                    in_drawdown_mode = False
            elif premium_pnl_dollars < 0:
                if consecutive_losses == 0 and not in_drawdown_mode:
                    drawdown_watermark = balance - premium_pnl_dollars
                consecutive_losses += 1
                if consecutive_losses >= 3:
                    in_drawdown_mode = True

            # Compute exit time from entry time and hold minutes
            try:
                eh, em = map(int, entry_time.split(':'))
                exit_m = eh * 60 + em + hold_minutes
                exit_time_str = f"{exit_m // 60:02d}:{exit_m % 60:02d}"
            except Exception:
                exit_time_str = entry_time

            trades.append({
                "date": d, "entry_time": entry_time, "exit_time": exit_time_str,
                "ticker": ticker, "direction": direction,
                "entry_price": entry_price, "exit_price": exit_price_spot,
                "actual_strike": actual_strike,
                "entry_premium": round(entry_premium, 2) if entry_premium else 0,
                "exit_premium": round(exit_premium, 2) if exit_premium else 0,
                "pnl_pct": premium_pnl_pct,
                "pnl_dollars": premium_pnl_dollars,
                "hold_minutes": hold_minutes, "exit_reason": exit_reason,
                "confidence": max_prob,
                "strike_bucket": STRIKE_BUCKETS[strike_bucket]["label"],
                "delta_target": delta_target,
                "actual_delta": round(actual_delta, 3),
                "actual_iv": round(actual_iv, 3),
                "strike_distance_pts": strike_distance_pts,
                "using_real_data": using_real_data,
                "mae": mae,
                "contracts": contracts,
                "balance": round(balance, 2),
            })
            last_trade_time[key] = i
            open_positions[key] = i + hold_minutes

        # Progress reporting
        if (d_idx + 1) % report_interval == 0 or d_idx == total_dates - 1:
            elapsed = _time.time() - t_start
            pct = (d_idx + 1) / total_dates * 100
            rate = (d_idx + 1) / elapsed if elapsed > 0 else 0
            eta = (total_dates - d_idx - 1) / rate if rate > 0 else 0
            current_wr = 0.0
            if trades:
                wins = sum(1 for t in trades if t["pnl_dollars"] > 0)
                current_wr = wins / len(trades) * 100
            greeks_ok = sum(1 for v in _greeks_cache.values() if v[0] is not None)
            greeks_miss = sum(1 for v in _greeks_cache.values() if v[0] is None)
            print(f"    [{pct:5.1f}%] {d_idx+1}/{total_dates} days | "
                  f"{len(trades)} trades (WR {current_wr:.1f}%) | "
                  f"greeks: {greeks_ok}/{greeks_ok+greeks_miss} loaded | "
                  f"ETA {int(eta)}s")

    print(f"  Options data: {options_loaded} trades with real pricing, {options_missed} skipped (no data)")
    if skipped_diagnostics:
        skipped_df = pd.DataFrame(skipped_diagnostics)
        top_dates = skipped_df["date"].value_counts()
        top_tickers = skipped_df["ticker"].value_counts()
        print(f"\n  >>> MISSING DATA DIAGNOSTICS <<<")
        print(f"  By Ticker:")
        for tick, count in top_tickers.items():
            print(f"    {tick}: {count} missed")
        print(f"  Top 10 Dates:")
        for date, count in top_dates.items():
            print(f"    {date}: {count} missed")
        
    return pd.DataFrame(trades)


# ─────────────────────────────────────────────────────────────────────────
# METRICS
# ─────────────────────────────────────────────────────────────────────────

def calculate_metrics(trades_df: pd.DataFrame) -> dict:
    """Calculate trading metrics from trade results."""
    if trades_df.empty:
        return {"error": "No trades"}

    n = len(trades_df)
    wins = trades_df[trades_df["pnl_dollars"] > 0]
    losses = trades_df[trades_df["pnl_dollars"] < 0]

    win_rate = len(wins) / n * 100
    gross_profit = wins["pnl_dollars"].sum() if len(wins) > 0 else 0
    gross_loss = abs(losses["pnl_dollars"].sum()) if len(losses) > 0 else 1e-6
    pf = gross_profit / gross_loss if gross_loss > 0 else 0
    total_pnl = trades_df["pnl_dollars"].sum()

    cumulative = trades_df["pnl_dollars"].cumsum()
    max_dd = (cumulative - cumulative.cummax()).min()

    if n > 1:
        daily_ret = trades_df.groupby("date")["pnl_dollars"].sum()
        sharpe = daily_ret.mean() / (daily_ret.std() + 1e-8) * np.sqrt(252)
    else:
        sharpe = 0

    mean_winner = wins["pnl_pct"].mean() if len(wins) > 0 else 0
    mean_loser = abs(losses["pnl_pct"].mean()) if len(losses) > 0 else 1e-6
    wl_ratio = mean_winner / mean_loser if mean_loser > 0 else 0

    avg_hold_w = wins["hold_minutes"].mean() if len(wins) > 0 else 0
    avg_hold_l = losses["hold_minutes"].mean() if len(losses) > 0 else 0

    return {
        "total": n, "wins": len(wins), "losses": len(losses),
        "win_rate": win_rate, "pf": pf, "total_pnl": total_pnl,
        "max_dd": max_dd, "sharpe": sharpe, "wl_ratio": wl_ratio,
        "avg_hold_win": avg_hold_w, "avg_hold_loss": avg_hold_l,
    }


def print_comparison(mlp_metrics: dict, rl_metrics: dict):
    """Side-by-side comparison table."""
    print("\n" + "=" * 72)
    print("  GBT-ONLY vs GBT+RL COMPARISON")
    print("=" * 72)
    print(f"  {'Metric':<25s} {'GBT-Only':>15s} {'GBT+RL':>15s} {'Delta':>12s}")
    print(f"  {'-'*25} {'-'*15} {'-'*15} {'-'*12}")

    def row(label, key, fmt=".2f", higher_better=True):
        v1 = mlp_metrics.get(key, 0)
        v2 = rl_metrics.get(key, 0)
        delta = v2 - v1
        sign = "+" if delta > 0 else ""
        better = (delta > 0) == higher_better
        marker = " <<" if better and abs(delta) > 0.01 else ""
        print(f"  {label:<25s} {v1:>15{fmt}} {v2:>15{fmt}} {sign}{delta:>11{fmt}}{marker}")

    row("Total Trades", "total", "d", False)
    row("Win Rate (%)", "win_rate", ".1f")
    row("Profit Factor", "pf", ".2f")
    row("Total P&L ($)", "total_pnl", ".1f")
    row("Max Drawdown ($)", "max_dd", ".1f", False)
    row("Sharpe Ratio", "sharpe", ".2f")
    row("W/L Size Ratio", "wl_ratio", ".2f")
    row("Avg Hold Win (min)", "avg_hold_win", ".0f", False)
    row("Avg Hold Loss (min)", "avg_hold_loss", ".0f", False)
    print("=" * 72)

    # RL-specific metrics
    if "error" not in rl_metrics:
        rl_pf = rl_metrics.get("pf", 0)
        mlp_pf = mlp_metrics.get("pf", 0)
        if mlp_pf > 0:
            improvement = (rl_pf / mlp_pf - 1) * 100
            print(f"\n  Profit Factor improvement: {improvement:+.1f}%")


# ─────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="RL Backtest: GBT+RL vs GBT-only")
    parser.add_argument("--data", default=os.path.join(PROJECT_ROOT, "training_data", "training_data_derived.parquet"))
    parser.add_argument("--model", default=os.path.join(PROJECT_ROOT, "models", "trading_hybrid_wf.pt"))
    parser.add_argument("--normalizer", default=os.path.join(PROJECT_ROOT, "models", "hybrid_normalizer_wf.npz"))
    parser.add_argument("--model-size", default="small", choices=["micro", "small", "medium", "medium_v2", "large"])
    parser.add_argument("--rl-model", default=os.path.join(PROJECT_ROOT, "rl_models", "best_rl_agent.pt"), help="RL agent checkpoint")
    parser.add_argument("--threshold", type=float, default=0.50)
    parser.add_argument("--cooldown", type=int, default=10)
    parser.add_argument("--target-long", type=float, default=0.010)
    parser.add_argument("--target-short", type=float, default=0.005)
    parser.add_argument("--stop", type=float, default=0.003)
    parser.add_argument("--max-time", type=int, default=180)
    parser.add_argument("--tickers", nargs="+", default=None, help="Filter tickers (e.g. SPX SPY QQQ)")
    parser.add_argument("--ensemble", action="store_true", help="Load model as ensemble")
    parser.add_argument("--risk-capital", type=float, default=500.0,
                        help="Risk capital in dollars per trade (fixed)")
    args = parser.parse_args()

    device = get_device()

    # ── Load MLP ──
    print("=" * 72)
    print("  RL BACKTEST — GBT+RL vs GBT-ONLY")
    print("=" * 72)
    print(f"\n[1/5] Loading GBT model...")
    if args.ensemble:
        model, normalizer = load_ensemble_model(args.model, args.normalizer, args.model_size, device)
        print(f"  OK (ensemble)")
    else:
        model, normalizer = load_hybrid_model(args.model, args.normalizer, args.model_size, device)
        model.eval()
        print(f"  OK")

    # ── Load RL agent ──
    print(f"\n[2/5] Loading RL agent from {args.rl_model}...")
    if os.path.exists(args.rl_model):
        rl_agent = PPOAgent.load(args.rl_model, device)
        rl_agent.eval()
        has_rl = True
        print(f"  OK ({sum(p.numel() for p in rl_agent.parameters()):,} params)")
    else:
        print(f"  RL model not found — using random policy for comparison")
        rl_agent = PPOAgent()
        rl_agent.to(device)
        rl_agent.eval()
        has_rl = False

    # ── Load data ──
    print(f"\n[3/5] Loading data from {args.data}...")
    if args.data.endswith(".parquet"):
        df = pd.read_parquet(args.data)
    else:
        df = pd.read_csv(args.data)
    df["date"] = df["date"].astype(str)

    if args.tickers:
        df = df[df["ticker"].isin(args.tickers)]
        print(f"  Filtered to tickers: {args.tickers}")

    print(f"  {len(df):,} samples | {df['date'].nunique()} days | tickers: {df['ticker'].unique().tolist()}")

    # ── GBT predictions ──
    print(f"\n[4/5] Running GBT predictions...")
    # Build feature matrix matching expected columns (fast, no fragmentation)
    features = np.zeros((len(df), len(FEATURE_COLUMNS)), dtype=np.float32)
    for i, col in enumerate(FEATURE_COLUMNS):
        if col in df.columns:
            features[:, i] = df[col].values.astype(np.float32)
    
    # Check if GBT
    is_gbt = hasattr(model, 'predict_proba') and not isinstance(model, torch.nn.Module)

    features = np.nan_to_num(features, nan=0.0, posinf=5.0, neginf=-5.0)
    features_norm = normalizer.transform(features)
    
    if is_gbt:
        probs = model.predict_proba(features_norm)
        predictions = np.argmax(probs, axis=1)
    else:
        features_tensor = torch.tensor(features_norm, dtype=torch.float32)

        logits_list, time_list = [], []
        with torch.inference_mode():
            for i in range(0, len(features_tensor), 1024):
                batch = features_tensor[i:i+1024].to(device)
                out = model(batch)
                if isinstance(out, tuple):
                    logits_list.append(out[0].cpu())
                    time_list.append(out[1].cpu() if out[1] is not None else torch.zeros(len(batch), 2))
                else:
                    logits_list.append(out.cpu())

        logits = torch.cat(logits_list, dim=0)
        probs = torch.softmax(logits, dim=-1).numpy()
        predictions = np.argmax(probs, axis=1)
        
    print(f"  Predictions: {np.bincount(predictions, minlength=3)} [SHORT, HOLD, LONG]")

    # ── Simulate both ──
    print(f"\n[5/5] Running simulations...")

    # GBT-only
    print(f"  Running GBT-only simulation...")
    mlp_trades = simulate_mlp_only(
        df, predictions, probs,
        threshold=args.threshold,
        target_long=args.target_long, target_short=args.target_short,
        stop_pct=args.stop, max_time=args.max_time, cooldown=args.cooldown,
        risk_capital=args.risk_capital)
    mlp_metrics = calculate_metrics(mlp_trades)
    print(f"  GBT-only: {len(mlp_trades)} trades")

    # GBT+RL
    print(f"  Running GBT+RL simulation...")
    rl_trades = simulate_mlp_rl(
        df, predictions, probs, rl_agent,
        threshold=args.threshold, max_time=args.max_time,
        cooldown=args.cooldown, device=device,
        risk_capital=args.risk_capital)
    rl_metrics = calculate_metrics(rl_trades)
    print(f"  GBT+RL: {len(rl_trades)} trades")

    # ── Print comparison ──
    print_comparison(mlp_metrics, rl_metrics)

    # Per-ticker breakdown
    for label, trades_df in [("GBT-Only", mlp_trades), ("GBT+RL", rl_trades)]:
        if trades_df.empty:
            continue
        print(f"\n  {label} — By Ticker:")
        for t in trades_df["ticker"].unique():
            t_df = trades_df[trades_df["ticker"] == t]
            m = calculate_metrics(t_df)
            if "error" not in m:
                print(f"    {t:6s}: {m['total']:4d} trades | {m['win_rate']:5.1f}% WR | PF {m['pf']:.2f} | P&L {m['total_pnl']:+.1f}")

    # RL exit reason distribution
    if not rl_trades.empty and "exit_reason" in rl_trades.columns:
        print(f"\n  RL Exit Reasons:")
        for reason, count in rl_trades["exit_reason"].value_counts().items():
            print(f"    {reason:20s}: {count:4d} ({count/len(rl_trades)*100:.1f}%)")

    # RL strike distribution with performance per bucket
    if not rl_trades.empty and "strike_bucket" in rl_trades.columns:
        print(f"\n  RL Strike Analysis:")
        print(f"    {'Bucket':<15s} {'Trades':>7s} {'%':>6s} {'WR':>7s} {'PF':>7s} {'Avg Dist':>10s} {'Avg P&L':>9s}")
        print(f"    {'-'*15} {'-'*7} {'-'*6} {'-'*7} {'-'*7} {'-'*10} {'-'*9}")
        for bucket in ['deep_otm', 'otm_far', 'otm_near', 'otm_light', 'atm', 'itm_light', 'itm']:
            b_df = rl_trades[rl_trades['strike_bucket'] == bucket]
            if b_df.empty:
                continue
            b_count = len(b_df)
            b_pct = b_count / len(rl_trades) * 100
            b_wins = len(b_df[b_df['pnl_dollars'] > 0])
            b_wr = b_wins / b_count * 100
            b_gross_w = b_df[b_df['pnl_dollars'] > 0]['pnl_dollars'].sum()
            b_gross_l = abs(b_df[b_df['pnl_dollars'] < 0]['pnl_dollars'].sum()) + 1e-9
            b_pf = b_gross_w / b_gross_l
            b_avg_dist = b_df['strike_distance_pts'].mean() if 'strike_distance_pts' in b_df.columns else 0
            b_avg_pnl = b_df['pnl_dollars'].mean()
            print(f"    {bucket:<15s} {b_count:>7d} {b_pct:>5.1f}% {b_wr:>6.1f}% {b_pf:>7.2f} {b_avg_dist:>+9.1f}p {b_avg_pnl:>+8.2f}")

    # ── Alpha vs Beta Analysis ──
    print(f"\n" + "=" * 72)
    print("  ALPHA vs BETA ANALYSIS")
    print("=" * 72)
    
    if not df.empty:
        # Compute daily return of the underlying assets from the raw 1-min data
        daily_grp = df.groupby(['ticker', 'date'])['spot_price'].agg(['first', 'last']).reset_index()
        daily_grp['date'] = daily_grp['date'].astype(str)
        daily_grp['mkt_ret_pct'] = (daily_grp['last'] / daily_grp['first'] - 1) * 100
        daily_grp['mkt_dir'] = np.where(daily_grp['mkt_ret_pct'] > 0, 'UP', 'DOWN')

        for label, trades_df in [("GBT-Only", mlp_trades), ("GBT+RL", rl_trades)]:
            if trades_df.empty:
                continue
                
            # Merge market direction into the trades
            t_df = trades_df.merge(daily_grp[['ticker', 'date', 'mkt_ret_pct', 'mkt_dir']], on=['ticker', 'date'], how='inner')
            
            def _get_pf_wr(df_sub):
                if df_sub.empty: return 0.0, 0.0
                wins = len(df_sub[df_sub['pnl_dollars'] > 0])
                wr = (wins / len(df_sub)) * 100
                gw = df_sub[df_sub['pnl_dollars'] > 0]['pnl_dollars'].sum()
                gl = abs(df_sub[df_sub['pnl_dollars'] < 0]['pnl_dollars'].sum()) + 1e-9
                return (gw / gl), wr
                
            up_days = t_df[t_df['mkt_dir'] == 'UP']
            dn_days = t_df[t_df['mkt_dir'] == 'DOWN']
            
            pf_up, wr_up = _get_pf_wr(up_days)
            pf_dn, wr_dn = _get_pf_wr(dn_days)
            
            # Correlation: Calculate TRUE daily portfolio % return to adjust for GBT contracts and RL Options leverage as well as compounding
            daily_dollars = t_df.groupby('date')['pnl_dollars'].sum().reset_index()
            daily_dollars['cum_pnl'] = daily_dollars['pnl_dollars'].cumsum()
            # Approximate start balance per day
            daily_dollars['start_bal'] = 100_000.0 + daily_dollars['cum_pnl'].shift(1).fillna(0)
            daily_dollars['port_ret_pct'] = (daily_dollars['pnl_dollars'] / daily_dollars['start_bal']) * 100.0
            
            daily_mkt_simp = daily_grp[['date', 'mkt_ret_pct']].drop_duplicates()
            daily_strat = daily_dollars.merge(daily_mkt_simp, on='date', how='inner')
            
            corr = 0.0
            if len(daily_strat) > 1:
                # Use Spearman rank correlation instead of Pearson to ignore the massive non-linear spikes of options payouts
                corr = daily_strat['port_ret_pct'].corr(daily_strat['mkt_ret_pct'], method='spearman')
                
            print(f"  {label} Performance by Market Trend:")
            print(f"    Rank Correlation w/ Market: {corr:+.2f} (0.0 = Pure Alpha, +1.0/-1.0 = Pure Beta)")
            print(f"    On MARKET UP Days:   {len(up_days):4d} trades | WR: {wr_up:5.1f}% | PF: {pf_up:.2f}")
            print(f"    On MARKET DOWN Days: {len(dn_days):4d} trades | WR: {wr_dn:5.1f}% | PF: {pf_dn:.2f}")
            print(f"")

    # Save results
    out_dir = Path(PROJECT_ROOT) / "backtest_results"
    out_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    mlp_trades.to_csv(out_dir / f"gbt_only_{ts}.csv", index=False)
    rl_trades.to_csv(out_dir / f"gbt_rl_{ts}.csv", index=False)
    print(f"\n  Results saved to {out_dir}")


if __name__ == "__main__":
    main()
