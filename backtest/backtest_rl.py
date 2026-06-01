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
import pickle
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
from neural.rl.config import (
    RL_CONFIG, HARD_EXITS, STRIKE_BUCKETS,
    SNIPER_TOTAL_STATE_DIM, MLP_CONTEXT_DIM,
    POSITION_STATE_DIM, TICKER_CONTEXT_DIM, SNIPER_STATE_DIM,
    STRIKE_CONTEXT_DIM, STRIKE_CONTEXT_FEATURES_PER_BUCKET,
    get_half_spread,
)
from neural.rl.agent import PPOAgent
from rl.rewards import compute_step_reward, compute_terminal_reward
from rl.utils import get_delta_bucket, get_iv_bucket, get_pnl_bucket, CurriculumScheduler
from neural.signal_policy import (
    confidence_for_predictions,
    deployment_context_allowed,
    direction_from_prediction,
    get_independent_signals,
    is_actionable_signal,
    should_exit_on_reversal,
)
from backtest_gbt_parquet import TradeSimulator as GBTSpotTradeSimulator

# ─────────────────────────────────────────────────────────────────────────

def _parse_block_rule(rule: str) -> tuple[str, str, str]:
    """Parse ticker:direction:bucket policy rules, using * as wildcard."""
    parts = [p.strip() for p in str(rule).split(":")]
    if len(parts) != 3:
        raise ValueError(
            f"Invalid RL block rule '{rule}'. Expected ticker:direction:bucket, e.g. SPY:LONG:*"
        )
    ticker, direction, bucket = parts
    ticker = ticker.upper() if ticker and ticker != "*" else "*"
    direction = direction.upper() if direction and direction != "*" else "*"
    bucket = bucket.lower() if bucket and bucket != "*" else "*"
    return ticker, direction, bucket


def _matches_block_rule(
    ticker: str,
    direction: str,
    strike_bucket_label: str,
    rules: list[tuple[str, str, str]] | None,
) -> bool:
    if not rules:
        return False
    ticker = str(ticker).upper()
    direction = str(direction).upper()
    bucket = str(strike_bucket_label).lower()
    for rule_ticker, rule_direction, rule_bucket in rules:
        if rule_ticker not in ("*", ticker):
            continue
        if rule_direction not in ("*", direction):
            continue
        if rule_bucket not in ("*", bucket):
            continue
            return True
    return False


def _parse_strike_bucket_override(value: str | int | None) -> int | None:
    """Parse a strike bucket override from an int index or configured label."""
    if value is None or value == "":
        return None
    text = str(value).strip().lower()
    if text.isdigit():
        idx = int(text)
        if idx not in STRIKE_BUCKETS:
            raise ValueError(f"Invalid strike bucket index {idx}; expected 0-{len(STRIKE_BUCKETS)-1}")
        return idx
    for idx, spec in STRIKE_BUCKETS.items():
        if text == str(spec.get("label", "")).lower():
            return int(idx)
    labels = ", ".join(str(v["label"]) for v in STRIKE_BUCKETS.values())
    raise ValueError(f"Invalid strike bucket '{value}'. Expected one of: {labels}")


def _parse_ticker_strike_bucket_overrides(value: str | None) -> dict[str, int]:
    """Parse ticker:bucket overrides separated by comma or semicolon."""
    overrides: dict[str, int] = {}
    if not value:
        return overrides
    for raw_part in str(value).replace(";", ",").split(","):
        part = raw_part.strip()
        if not part:
            continue
        if ":" not in part:
            raise ValueError(
                f"Invalid ticker strike override '{part}'. Expected TICKER:bucket, e.g. SPX:deep_otm"
            )
        ticker, bucket = part.split(":", 1)
        ticker = ticker.strip().upper()
        overrides[ticker] = _parse_strike_bucket_override(bucket)
    return overrides


def _parse_feature_rule(rule: str) -> tuple[str, str, str, float]:
    """Parse direction:feature:op:value feature guards, with ALL/* as wildcard direction."""
    parts = [p.strip() for p in str(rule).split(":")]
    if len(parts) != 4:
        raise ValueError(
            f"Invalid RL feature rule '{rule}'. Expected direction:feature:op:value, "
            "e.g. SHORT:price_vs_ib_low:lte:5.4"
        )
    direction, feature, op, value = parts
    direction = direction.upper()
    if direction in ("ALL", ""):
        direction = "*"
    op = op.lower()
    if op not in ("lt", "lte", "gt", "gte"):
        raise ValueError(f"Invalid feature rule op '{op}'. Use lt/lte/gt/gte.")
    return direction, feature, op, float(value)


def _matches_feature_rule(
    row: pd.Series,
    direction: str,
    rules: list[tuple[str, str, str, float]] | None,
) -> bool:
    if not rules:
        return False
    direction = str(direction).upper()
    for rule_direction, feature, op, value in rules:
        if rule_direction not in ("*", direction):
            continue
        if feature not in row.index:
            continue
        try:
            observed = float(row.get(feature))
        except Exception:
            continue
        if not np.isfinite(observed):
            continue
        if op == "lt" and observed < value:
            return True
        if op == "lte" and observed <= value:
            return True
        if op == "gt" and observed > value:
            return True
        if op == "gte" and observed >= value:
            return True
    return False


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
    "SPY": 100.0, "QQQ": 100.0, "IWM": 100.0,
}

# --- GBM EXIT CONSTANTS (Aligned with backtest_gbt_parquet.py) ---
GBM_TRAILING_ACTIVATION_PCT = 0.0050
GBM_TRAILING_STOP_PCT = 0.0030

# ── Position Sizing ──
INITIAL_BALANCE = 10_000.0
GBT_MLP_TIME_TO_TARGET = 0.5
GBT_MLP_LOG_SIGMA = 0.0


def _pad_or_trim_state(state: np.ndarray, state_dim: int) -> np.ndarray:
    if len(state) < state_dim:
        pad = np.zeros(state_dim - len(state), dtype=np.float32)
        return np.concatenate([state, pad])
    return state[:state_dim]


def _build_position_state(pnl_pct: float = 0.0,
                          hold_norm: float = 0.0,
                          current_delta: float = 0.0,
                          recovery_prob: float = 0.0,
                          iv_ratio: float = 1.0,
                          mae: float = 0.0,
                          trailing_drawdown: float = 0.0) -> np.ndarray:
    pos = np.zeros(POSITION_STATE_DIM, dtype=np.float32)
    pos[0] = np.clip(pnl_pct, -1.0, 5.0)
    pos[1] = np.clip(hold_norm, 0.0, 1.0)
    pos[2] = abs(current_delta)
    pos[3] = np.clip(recovery_prob, 0.0, 1.0)
    pos[4] = np.clip(iv_ratio, 0.5, 3.0)
    pos[5] = np.clip(mae, -1.0, 0.0)
    if POSITION_STATE_DIM > 6:
        pos[6] = np.clip(trailing_drawdown, 0.0, 2.0)
    return pos


def _build_ticker_context(ticker: str) -> np.ndarray:
    ctx = np.zeros(TICKER_CONTEXT_DIM, dtype=np.float32)
    mapping = {"SPX": 0, "SPXW": 0, "SPY": 1, "QQQ": 2}
    idx = mapping.get(str(ticker).upper())
    if idx is not None and idx < TICKER_CONTEXT_DIM:
        ctx[idx] = 1.0
    return ctx


def _build_strike_context_from_slice(
    entry_slice: pd.DataFrame | None,
    direction: str,
    spot: float,
    entry_atm_iv: float,
) -> np.ndarray:
    """Mirror RL training's per-bucket entry chain context."""
    context = np.zeros(STRIKE_CONTEXT_DIM, dtype=np.float32)
    if entry_slice is None or entry_slice.empty:
        return context

    spot = float(spot or 0.0)
    atm_iv = float(entry_atm_iv or 0.15)
    for action, bucket in STRIKE_BUCKETS.items():
        offset = int(action) * STRIKE_CONTEXT_FEATURES_PER_BUCKET
        chain = _find_strike_by_delta(
            entry_slice,
            direction,
            float(bucket.get("delta_target", 0.5)),
        )
        if chain is None:
            continue

        premium = float(chain.get("mid_price", 0.0))
        iv = float(chain.get("iv", atm_iv))
        theta = float(chain.get("theta", 0.0))
        context[offset + 0] = 1.0
        context[offset + 1] = np.clip(abs(float(chain.get("delta", 0.0))), 0.0, 1.0)
        context[offset + 2] = np.clip((premium / spot) * 100.0 if spot > 0 else 0.0, 0.0, 10.0)
        context[offset + 3] = np.clip(iv / atm_iv if atm_iv > 0 else 1.0, 0.25, 4.0)
        context[offset + 4] = np.clip(theta / premium if premium > 0 else 0.0, -5.0, 0.0)

    return context

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
                      probabilities: np.ndarray, threshold: float = RL_CONFIG["min_confidence"],
                      target_long: float = 0.010, target_short: float = 0.005,
                      stop_pct: float = 0.003, max_time: int = 180,
                      cooldown: int = 15, risk_capital: float = 500.0,
                      spx_target: float = 0.010, etf_target: float = 0.006,
                      spx_stop: float = 0.0025, etf_stop: float = 0.0025,
                      qqq_target: float | None = None, spy_target: float | None = None,
                      qqq_stop: float | None = None, spy_stop: float | None = None,
                      min_entry_minute: int = 580,
                      min_short_entry_minute: int | None = None,
                      min_short_price_vs_ib_high: float | None = None) -> pd.DataFrame:
    """
    Simulate GBT-only trades using spot price targets/stops.
    Aligned with backtest_hybrid_parquet.py: real dollar P&L, OHLC intrabar
    detection, open position tracking, first-10-min skip.
    """
    trades = []
    last_trade_minute = {}   # (ticker, date) -> last entry minute
    open_positions = {}      # (ticker, date) -> expected exit minute
    balance = INITIAL_BALANCE  # equity tracking

    # Drawdown mitigation sequence limit (per ticker)
    ticker_consecutive_losses = {}

    # Merge predictions into dataframe for proper sorting
    df_work = df.copy()
    df_work['pred'] = predictions
    df_work['signal_confidence'] = confidence_for_predictions(probabilities, predictions)
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
            signal_confidence = row['signal_confidence']
            current_minute = row['minutes']
            ticker = row.get('ticker', 'SPX')

            # Per-ticker dynamic confidence
            tck = str(ticker)
            loss_streak_key = (tck, str(d))
            if loss_streak_key not in ticker_consecutive_losses:
                ticker_consecutive_losses[loss_streak_key] = 0

            is_drawdown = ticker_consecutive_losses[loss_streak_key] >= 2
            effective_threshold = threshold + 0.10 if is_drawdown else threshold
            effective_risk_capital = risk_capital * 0.5 if is_drawdown else risk_capital

            direction = direction_from_prediction(pred)
            if not is_actionable_signal(direction, signal_confidence, base_confidence=effective_threshold):
                continue
            if not deployment_context_allowed(row, direction=direction):
                continue

            # Skip unstable opening window. 580 preserves the historical
            # first-10-minute guard; higher values are explicit pipeline policy.
            if current_minute < min_entry_minute:
                continue
            if (
                direction == "SHORT"
                and min_short_entry_minute is not None
                and current_minute < int(min_short_entry_minute)
            ):
                continue
            if (
                direction == "SHORT"
                and min_short_price_vs_ib_high is not None
                and float(row.get("price_vs_ib_high", 0.0)) < float(min_short_price_vs_ib_high)
            ):
                continue

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

            ticker_stop = stop_pct
            base_target = target_long if direction == "LONG" else target_short
            if ticker == "QQQ":
                base_target = etf_target if qqq_target is None else qqq_target
                ticker_stop = etf_stop if qqq_stop is None else qqq_stop
            elif ticker == "SPY":
                base_target = etf_target if spy_target is None else spy_target
                ticker_stop = etf_stop if spy_stop is None else spy_stop
            elif ticker in ("SPX", "SPXW"):
                base_target = spx_target
                ticker_stop = spx_stop

            # ── OHLC intrabar exit simulation ──
            ohlc = _load_ohlc_data(ticker, d)
            exit_price = entry_price
            actual_hold_minutes = max_time
            target_hit = False
            stop_hit = False
            trailing_stop_hit = False
            mae = 0.0
            peak_price = entry_price

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
                            # Peak tracking
                            peak_price = max(peak_price, h)
                            peak_pnl = (peak_price - entry_price) / entry_price

                            if peak_pnl >= GBM_TRAILING_ACTIVATION_PCT:
                                if (peak_price - l) / entry_price >= GBM_TRAILING_STOP_PCT:
                                    exit_price = peak_price - (entry_price * GBM_TRAILING_STOP_PCT)
                                    trailing_stop_hit = True
                                    actual_hold_minutes = elapsed
                                    found_exit = True
                                    break

                            # Stop loss (low triggers)
                            if l <= entry_price * (1 - ticker_stop):
                                exit_price = entry_price * (1 - ticker_stop)
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
                            # Peak tracking
                            peak_price = min(peak_price, l)
                            peak_pnl = (entry_price - peak_price) / entry_price

                            if peak_pnl >= GBM_TRAILING_ACTIVATION_PCT:
                                if (h - peak_price) / entry_price >= GBM_TRAILING_STOP_PCT:
                                    exit_price = peak_price + (entry_price * GBM_TRAILING_STOP_PCT)
                                    trailing_stop_hit = True
                                    actual_hold_minutes = elapsed
                                    found_exit = True
                                    break

                            # Stop loss (high triggers)
                            if h >= entry_price * (1 + ticker_stop):
                                exit_price = entry_price * (1 + ticker_stop)
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
                        peak_price = max(peak_price, price)
                        peak_pnl = (peak_price - entry_price) / entry_price

                        if peak_pnl >= GBM_TRAILING_ACTIVATION_PCT:
                            if (peak_price - price) / entry_price >= GBM_TRAILING_STOP_PCT:
                                exit_price = peak_price - (entry_price * GBM_TRAILING_STOP_PCT)
                                trailing_stop_hit = True
                                break

                        if price >= entry_price * (1 + base_target):
                            exit_price = entry_price * (1 + base_target)
                            target_hit = True
                            break
                        elif price <= entry_price * (1 - ticker_stop):
                            exit_price = entry_price * (1 - ticker_stop)
                            stop_hit = True
                            break
                    else:
                        peak_price = min(peak_price, price)
                        peak_pnl = (entry_price - peak_price) / entry_price

                        if peak_pnl >= GBM_TRAILING_ACTIVATION_PCT:
                            if (price - peak_price) / entry_price >= GBM_TRAILING_STOP_PCT:
                                exit_price = peak_price + (entry_price * GBM_TRAILING_STOP_PCT)
                                trailing_stop_hit = True
                                break

                        if price <= entry_price * (1 - base_target):
                            exit_price = entry_price * (1 - base_target)
                            target_hit = True
                            break
                        elif price >= entry_price * (1 + ticker_stop):
                            exit_price = entry_price * (1 + ticker_stop)
                            stop_hit = True
                            break
                    exit_price = price
                    actual_hold_minutes = elapsed

            if exit_price <= 0:
                continue

            # Real dollar P&L with dynamic sizing
            multiplier = GBT_POINT_VALUES.get(ticker, 100.0)
            contracts = _calc_contracts_futures(effective_risk_capital, entry_price, ticker_stop, multiplier)

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
                ticker_consecutive_losses[loss_streak_key] = 0
            elif pnl_dollars < 0:
                ticker_consecutive_losses[loss_streak_key] += 1

            exit_reason = "target" if target_hit else "stop" if stop_hit else "trailing_stop" if trailing_stop_hit else "max_time"

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
                "confidence": signal_confidence, "contracts": contracts,
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
_TICKER_TO_OPTIONS = {"SPX": "SPXW", "SPXW": "SPXW", "QQQ": "QQQ", "SPY": "SPY"}

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

                # Build O(1) greeks lookup: (time, strike, right) -> {delta, theta, iv, gamma, spot}
                greeks_lookup = {}
                for key, delta, theta, iv, gamma, spot in zip(
                    valid["_key"],
                    valid["delta"].fillna(0).astype(float),
                    valid.get("theta", pd.Series(0, index=valid.index)).fillna(0).astype(float),
                    valid.get("implied_vol", pd.Series(0.15, index=valid.index)).fillna(0.15).astype(float),
                    valid.get("gamma", pd.Series(0, index=valid.index)).fillna(0).astype(float),
                    valid.get("underlying_price", pd.Series(0, index=valid.index)).fillna(0).astype(float),
                ):
                    greeks_lookup[key] = {
                        "delta": float(delta), "theta": float(theta),
                        "iv": float(iv), "gamma": float(gamma), "spot": float(spot),
                    }

                # O(1) ATM greeks lookup for dynamic state. Training/live use
                # ATM IV/gamma, not the held strike's IV/gamma.
                atm = valid.copy()
                atm["_atm_dist"] = (atm["strike"].astype(float) - atm["underlying_price"].astype(float)).abs()
                atm = atm.sort_values("_atm_dist").groupby(["time_str", "right_upper"], observed=True).first().reset_index()
                for _, row in atm.iterrows():
                    greeks_lookup[(row["time_str"], "__ATM__", row["right_upper"])] = {
                        "delta": float(row.get("delta", 0.0)),
                        "theta": float(row.get("theta", 0.0)),
                        "iv": float(row.get("implied_vol", 0.15)),
                        "gamma": float(row.get("gamma", 0.0)),
                        "spot": float(row.get("underlying_price", 0.0)),
                    }

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


def _build_dynamic_market_features(
    current_minute: int,
    entry_spot: float,
    entry_iv: float,
    spot_history: list,
    greeks_lookup: dict,
    actual_strike: float,
    option_right: str,
    future_time: str,
    entry_minute: int,
    direction: str,
    premium_history: list,
) -> np.ndarray:
    """
    Build the 8 dynamic market features the RL agent was trained on.
    Uses O(1) accumulated lists — no pandas scan per step.

    Index mapping (must match environment._get_dynamic_market_features):
      [0] spot_change_pct     — % spot change from signal time  (clipped ±2)
      [1] spot_velocity_5m    — % spot change over last 5 bars  (clipped ±1)
      [2] atm_iv_change       — relative IV change from signal  (clipped ±1)
      [3] atm_gamma_norm      — gamma * spot * 0.01             (clipped ±2)
      [4] spot_vs_entry       — signed % distance spot vs position open (clipped ±3)
      [5] minutes_remaining   — (390 - mins_since_open) / 390   (0-1)
      [6] option_momentum_3m  — option price change over last 3 bars  (clipped ±1)
      [7] underlying_trend    — directional ratio of last ≤20 bars  (-1 to 1)
    """
    dynamic = np.zeros(8, dtype=np.float32)

    if entry_spot <= 0:
        return dynamic

    # Pull current spot from greeks_lookup (any strike at this minute)
    current_spot = entry_spot  # fallback
    if greeks_lookup is not None and actual_strike is not None:
        right_upper = option_right.upper()
        alt_right = right_upper[0] if len(right_upper) > 1 else right_upper
        g = (greeks_lookup.get((future_time, actual_strike, right_upper)) or
             greeks_lookup.get((future_time, actual_strike, alt_right)))
        if g and g.get("spot", 0) > 0:
            current_spot = g["spot"]

    spot_history.append(current_spot)

    # [0] spot change from signal time
    dynamic[0] = float(np.clip((current_spot - entry_spot) / entry_spot * 100, -2.0, 2.0))

    # [1] spot velocity over last 5 bars
    if len(spot_history) >= 6:
        dynamic[1] = float(np.clip((current_spot - spot_history[-6]) / entry_spot * 100, -1.0, 1.0))
    elif len(spot_history) >= 2:
        dynamic[1] = float(np.clip((current_spot - spot_history[0]) / entry_spot * 100, -1.0, 1.0))

    # [2] ATM IV change  [3] ATM gamma
    if greeks_lookup is not None and actual_strike is not None:
        right_upper = option_right.upper()
        alt_right = right_upper[0] if len(right_upper) > 1 else right_upper
        g = (greeks_lookup.get((future_time, "__ATM__", right_upper)) or
             greeks_lookup.get((future_time, "__ATM__", alt_right)))
        if g:
            cur_iv = g.get("iv", entry_iv)
            if cur_iv > 0 and entry_iv > 0:
                dynamic[2] = float(np.clip((cur_iv - entry_iv) / entry_iv, -1.0, 1.0))
            dynamic[3] = float(np.clip(g.get("gamma", 0.0) * current_spot * 0.01, -2.0, 2.0))

    # [4] spot vs position entry spot (signed by direction)
    if entry_minute > 0 and current_spot > 0 and entry_spot > 0:
        spot_vs = (current_spot - entry_spot) / entry_spot
        if direction == "SHORT":
            spot_vs = -spot_vs
        dynamic[4] = float(np.clip(spot_vs * 100, -3.0, 3.0))

    # [5] minutes remaining to close
    SESSION_OPEN = 570  # 9:30
    mins_since_open = max(0, current_minute - SESSION_OPEN)
    dynamic[5] = float(max(0.0, (390 - mins_since_open) / 390.0))

    # [6] option momentum over last 3 bars
    if len(premium_history) >= 4 and premium_history[-4] > 0:
        dynamic[6] = float(np.clip((premium_history[-1] - premium_history[-4]) / premium_history[-4], -1.0, 1.0))

    # [7] underlying directional trend (last ≤20 bars)
    if len(spot_history) >= 3:
        window = spot_history[-min(20, len(spot_history)):]
        diffs = np.diff(window)
        up = float(np.sum(diffs > 0))
        dn = float(np.sum(diffs < 0))
        if up + dn > 0:
            dynamic[7] = float((up - dn) / (up + dn))

    return dynamic


# ─────────────────────────────────────────────────────────────────────────
# GBT+RL SIMULATOR (REAL OPTIONS PRICING)
# ─────────────────────────────────────────────────────────────────────────

def simulate_mlp_rl(df: pd.DataFrame, predictions: np.ndarray,
                    probabilities: np.ndarray, rl_agent: PPOAgent,
                    market_features_matrix: np.ndarray = None,
                    threshold: float = RL_CONFIG["min_confidence"], max_time: int = 180,
                    cooldown: int = 15, device: torch.device = None,
                    risk_capital: float = 500.0,
                    target_long: float = 0.010, target_short: float = 0.010,
                    stop_pct: float = 0.0025,
                    spx_target: float = 0.010, etf_target: float = 0.006,
                    spx_stop: float = 0.0025, etf_stop: float = 0.0025,
                    qqq_target: float | None = None, spy_target: float | None = None,
                    qqq_stop: float | None = None, spy_stop: float | None = None,
                    single_step_eval: bool = False,
                    recovery_lookup: dict = None,
                    block_rules: list[tuple[str, str, str]] | None = None,
                    block_short_confidence_above: float | None = None,
                    feature_rules: list[tuple[str, str, str, float]] | None = None,
                    agent_exit_min_pnl: float | None = None,
                    force_strike_bucket: int | None = None,
                    force_ticker_strike_buckets: dict[str, int] | None = None,
                    force_delta_target: float | None = None,
                    underlying_exit_policy: str = "off",
                    disable_signal_reversal: bool = False,
                    exit_policy: str = "agent",
                    entry_skip_action: bool = False,
                    max_loss_pct: float | None = None,
                    max_profit_pct: float | None = None,
                    reentry_lock_minutes: int | None = None,
                    min_entry_minute: int = 580,
                    min_short_entry_minute: int | None = None,
                    min_short_price_vs_ib_high: float | None = None) -> pd.DataFrame:
    """Simulate GBT+RL trades using REAL options pricing from ThetaData."""
    trades = []
    skipped_diagnostics = []
    last_trade_time = {}
    open_positions = {}
    device = device or torch.device("cpu")
    rl_agent.eval()
    balance = INITIAL_BALANCE  # equity tracking

    # Drawdown mitigation sequence limit (per ticker)
    ticker_consecutive_losses = {}

    # Cache daily greeks by date to avoid re-loading
    # Each entry is (df, premium_lookup) or (None, None)
    _greeks_cache: dict[str, tuple] = {}
    options_loaded = 0
    options_missed = 0
    blocked_by_rule = 0
    blocked_by_confidence = 0
    blocked_by_feature = 0
    skipped_by_entry_policy = 0
    df_greeks = None
    premium_lookup = None
    greeks_lookup = None

    dates = sorted(df["date"].unique())
    total_dates = len(dates)
    t_start = _time.time()
    report_interval = max(1, total_dates // 10)  # report every ~10%
    agent_total_updates = getattr(rl_agent, "total_updates", RL_CONFIG.get("total_updates", 500))
    scheduler = CurriculumScheduler(total_updates=agent_total_updates)
    curr_params = scheduler.get_phase_info(getattr(rl_agent, "update_step", 0))
    rl_min_hold = curr_params.get("min_hold_minutes", 0)
    if agent_exit_min_pnl is None:
        agent_exit_min_pnl = float(RL_CONFIG.get("agent_exit_min_pnl_pct", 0.0))
    if reentry_lock_minutes is None:
        reentry_lock_minutes = 0
    reentry_lock_minutes = max(0, int(reentry_lock_minutes))
    force_ticker_strike_buckets = force_ticker_strike_buckets or {}
    hard_exits = dict(HARD_EXITS)
    if max_loss_pct is not None:
        hard_exits["max_loss_pct"] = -abs(float(max_loss_pct))
    if max_profit_pct is not None:
        hard_exits["max_profit_pct"] = float(max_profit_pct)
    underlying_exit_policy = str(underlying_exit_policy or "off").lower()
    if underlying_exit_policy not in {"off", "hybrid", "only"}:
        raise ValueError("underlying_exit_policy must be one of: off, hybrid, only")

    for d_idx, d in enumerate(dates):
        d_str = str(d)
        day_df = df[df["date"] == d].copy()
        day_df = day_df.sort_values("time")
        if "minutes" not in day_df.columns:
            day_df["minutes"] = day_df["time"].apply(_time_to_minutes)
        day_idx = day_df.index.tolist()

        # Greeks are now loaded per-ticker inside the trade loop below
        # (cache keyed by (ticker, date) instead of date only)

        # Pre-extract market features for the day. These stay raw to mirror the
        # RL training environment, which freezes the episode snapshot itself.
        day_features = market_features_matrix[day_idx] if market_features_matrix is not None else None
        if day_features is None:
            # Fallback (slow/raw)
            n_features = len(FEATURE_COLUMNS)
            day_features = np.zeros((len(day_idx), n_features), dtype=np.float32)
            for fi, col in enumerate(FEATURE_COLUMNS[:n_features]):
                if col in day_df.columns:
                    day_features[:, fi] = day_df[col].fillna(0).values.astype(np.float32)

        for i, global_idx in enumerate(day_idx):
            entry_idx = global_idx
            row = day_df.loc[global_idx]
            pred = predictions[global_idx]
            signal_confidence = float(probabilities[global_idx, pred])
            direction = direction_from_prediction(pred)

            ticker = row.get("ticker", "SPX")
            tck = str(ticker)
            loss_streak_key = (tck, str(d))
            if loss_streak_key not in ticker_consecutive_losses:
                ticker_consecutive_losses[loss_streak_key] = 0

            # CRITICAL: Define current_minute BEFORE using it in filters and chop guard
            entry_time = str(row.get("time", "09:30"))
            try:
                h, m = map(int, entry_time.split(':'))
                current_minute = h * 60 + m
            except Exception:
                current_minute = 570

            is_drawdown = ticker_consecutive_losses[loss_streak_key] >= 2
            effective_threshold = threshold + 0.10 if is_drawdown else threshold
            effective_risk_capital = risk_capital * 0.5 if is_drawdown else risk_capital

            if not is_actionable_signal(direction, signal_confidence, base_confidence=effective_threshold):
                continue
            if not deployment_context_allowed(row, direction=direction):
                continue

            if (
                block_short_confidence_above is not None
                and direction == "SHORT"
                and signal_confidence > block_short_confidence_above
            ):
                blocked_by_confidence += 1
                continue

            if _matches_feature_rule(row, direction, feature_rules):
                blocked_by_feature += 1
                continue

            # Skip unstable opening window. 580 preserves the historical
            # first-10-minute guard; higher values are explicit pipeline policy.
            if current_minute < min_entry_minute:
                continue
            if (
                direction == "SHORT"
                and min_short_entry_minute is not None
                and current_minute < int(min_short_entry_minute)
            ):
                continue
            if (
                direction == "SHORT"
                and min_short_price_vs_ib_high is not None
                and float(row.get("price_vs_ib_high", 0.0)) < float(min_short_price_vs_ib_high)
            ):
                continue

            # Ticker already extracted above

            key = f"{ticker}_{d}"

            # Open position check — don't overlap (in real minutes)
            if key in open_positions:
                if current_minute < open_positions[key]:
                    continue
                else:
                    del open_positions[key]

            if key in last_trade_time:
                elapsed = current_minute - last_trade_time[key]
                # Match the GBT-only simulator: cooldown is measured from the
                # entry timestamp, while open_positions prevents overlap until
                # the simulated position has actually closed.
                if elapsed < cooldown:
                    continue

            entry_price = row.get("spot_price", 0)
            if entry_price == 0:
                continue

            # Match the training environment: market features come from the
            # fixed signal-row snapshot, while only the dynamic/position blocks evolve.
            entry_market_features = day_features[i]

            # Current signal confidence and predicted class
            conf = probabilities[global_idx, pred]

            # RL state needs the context of the signal (same as training environment)
            # Group 3: MLP signal context (4 dims)
            mlp_context = np.array([
                conf,                        # confidence
                GBT_MLP_TIME_TO_TARGET,      # normalized time-to-target used by RL prep
                0.0,                         # mins_since_signal
                GBT_MLP_LOG_SIGMA,           # dummy log_sigma for GBT
            ], dtype=np.float32)

            # ── ENTRY: RL strike selection ──
            # Initialise per-trade O(1) histories
            _spot_history: list = [entry_price]
            _premium_history: list = []

            mins_left = 390.0 - (current_minute - 570)

            # Load greeks per-ticker (cached by (ticker, date)) for both entry and exit logic
            cache_key = f"{ticker}_{d_str}"
            if cache_key not in _greeks_cache:
                _greeks_cache[cache_key] = _load_daily_greeks(d_str, ticker)
                if len(_greeks_cache) > 30:
                    oldest_key = next(iter(_greeks_cache))
                    del _greeks_cache[oldest_key]
            df_greeks, premium_lookup, greeks_lookup = _greeks_cache[cache_key]

            # Find ATM IV at entry for dynamic features (snapshot, not per-minute)
            entry_atm_iv = 0.15
            entry_slice = None
            if df_greeks is not None:
                entry_slice = df_greeks[df_greeks["time_str"] == entry_time]
                if not entry_slice.empty:
                    closest_idx = (entry_slice["strike"] - entry_price).abs().idxmin()
                    entry_atm_iv = float(entry_slice.loc[closest_idx, "implied_vol"])

            # Entry dynamic: no held strike yet, so gamma/iv dims are 0; minutes_remaining is real
            dynamic_market_entry = np.zeros(8, dtype=np.float32)
            SESSION_OPEN_MIN = 570
            dynamic_market_entry[5] = float(max(0.0, (390 - max(0, current_minute - SESSION_OPEN_MIN)) / 390.0))

            # Entry position state (all zeros except iv_ratio=1.0)
            position_state_entry = _build_position_state(iv_ratio=1.0, trailing_drawdown=float(ticker_consecutive_losses[loss_streak_key]))

            ticker_context = _build_ticker_context(ticker)
            strike_context = _build_strike_context_from_slice(
                entry_slice,
                direction,
                entry_price,
                entry_atm_iv,
            )
            state_parts = [entry_market_features, dynamic_market_entry, position_state_entry, mlp_context, ticker_context, strike_context]
            if RL_CONFIG.get("use_sniper_mode", False):
                sniper_state = np.zeros(SNIPER_STATE_DIM, dtype=np.float32)
                state_parts.append(sniper_state)

            state = _pad_or_trim_state(np.concatenate(state_parts), rl_agent.state_dim)
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(device)
            use_entry_skip = (
                entry_skip_action
                and force_strike_bucket is None
                and not force_ticker_strike_buckets
            )
            entry_action_type = "sniper_entry" if use_entry_skip else "strike"

            with torch.no_grad():
                action, _, _ = rl_agent.get_action(
                    state_tensor, action_type=entry_action_type, deterministic=True)

            # Handle both dictionary (backwards compatibility) and integer (new architecture) actions
            raw_entry_action = action["strike"] if isinstance(action, dict) else int(action)
            if use_entry_skip:
                if raw_entry_action <= 0:
                    skipped_by_entry_policy += 1
                    last_trade_time[key] = current_minute
                    open_positions[key] = current_minute + cooldown
                    continue
                strike_bucket = raw_entry_action - 1
            else:
                strike_bucket = raw_entry_action
            ticker_override = force_ticker_strike_buckets.get(str(ticker).upper())
            if ticker_override is not None:
                strike_bucket = int(ticker_override)
            elif force_strike_bucket is not None:
                strike_bucket = int(force_strike_bucket)
            strike_bucket_label = STRIKE_BUCKETS[strike_bucket]["label"]
            if _matches_block_rule(ticker, direction, strike_bucket_label, block_rules):
                blocked_by_rule += 1
                continue
            delta_target = STRIKE_BUCKETS[strike_bucket]["delta_target"]
            if force_delta_target is not None:
                delta_target = abs(float(force_delta_target))
                strike_bucket_label = f"delta_{delta_target:.2f}"

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

            if df_greeks is not None:
                # Get options snapshot at strict entry time
                entry_slice = df_greeks[df_greeks["time_str"] == entry_time]
                if not entry_slice.empty:
                    entry_chain = _find_strike_by_delta(entry_slice, direction, delta_target)

            if entry_chain is not None:
                actual_strike = entry_chain["strike"]
                raw_entry_premium = entry_chain["mid_price"]
                actual_delta = entry_chain["delta"]
                actual_iv = entry_chain["iv"]
                actual_theta = entry_chain["theta"]
                actual_gamma = entry_chain["gamma"]
                option_right = entry_chain["right"]
                base_half_spread = get_half_spread(abs(actual_delta))
                gamma_speed = float(row.get("gamma_speed", 0.0) or 0.0)
                effective_spread = base_half_spread * (1.0 + 0.5 * abs(gamma_speed))
                entry_premium = raw_entry_premium * (1.0 + effective_spread)
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
            peak_premium = entry_premium
            peak_pnl = 0.0

            # Isolate future rows specific to this ticker
            ticker_mask = (day_df["ticker"] == ticker) & (day_df["minutes"] >= current_minute)
            ticker_df = day_df[ticker_mask]

            # Skip the first row (which is the entry minute itself)
            future_sub_df = ticker_df.iloc[1:max_time+1]

            ticker_stop = stop_pct
            base_target = target_long if direction == "LONG" else target_short
            if ticker == "QQQ":
                base_target = etf_target if qqq_target is None else qqq_target
                ticker_stop = etf_stop if qqq_stop is None else qqq_stop
            elif ticker == "SPY":
                base_target = etf_target if spy_target is None else spy_target
                ticker_stop = etf_stop if spy_stop is None else spy_stop
            elif ticker in ("SPX", "SPXW"):
                base_target = spx_target
                ticker_stop = spx_stop

            for t, (idx_global, future_row) in enumerate(future_sub_df.iterrows()):
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
                    # NOTE: For puts, delta is already negative (e.g. -0.4), so
                    # delta * spot_change naturally produces positive premium_change
                    # when spot drops (favorable for SHORT). No sign flip needed.
                    spot_change = price - entry_price
                    premium_change = actual_delta * spot_change + 0.5 * actual_gamma * spot_change**2
                    current_premium = max(0.01, entry_premium + premium_change)
                    premium_pnl_pct = (current_premium - entry_premium) / entry_premium

                premium_pnl_pct = float(np.clip(premium_pnl_pct, -1.0, 10.0))
                mae = min(mae, premium_pnl_pct)
                exit_premium = current_premium
                peak_premium = max(peak_premium, current_premium)
                peak_pnl = (peak_premium - entry_premium) / entry_premium
                _premium_history.append(current_premium)  # O(1) accumulation
                exit_price_spot = price

                if underlying_exit_policy in {"hybrid", "only"}:
                    if direction == "LONG":
                        underlying_pnl_pct = (price - entry_price) / entry_price
                    else:
                        underlying_pnl_pct = (entry_price - price) / entry_price
                    if underlying_pnl_pct <= -ticker_stop:
                        exit_reason = "underlying_stop"
                        break
                    if underlying_pnl_pct >= base_target:
                        exit_reason = "underlying_target"
                        break

                # Hard exit checks
                if underlying_exit_policy != "only":
                    if premium_pnl_pct <= hard_exits["max_loss_pct"]:
                        exit_reason = "hard_stop"
                        break
                    if premium_pnl_pct >= hard_exits["max_profit_pct"]:
                        exit_reason = "hard_take_profit"
                        break

                    # Trailing stop check (RL Premium based)
                    if peak_pnl >= hard_exits.get("trailing_stop_activation_pct", 0.40):
                        if (peak_premium - current_premium) / entry_premium >= hard_exits.get("trailing_stop_pct", 0.30):
                            exit_reason = "trailing_stop"
                            break

                # Match the training environment/live system: bail out when the
                # underlying directional signal flips with sufficient confidence.
                if not disable_signal_reversal:
                    future_pred = int(predictions[idx_global])
                    future_dir = direction_from_prediction(future_pred)
                    future_conf = float(probabilities[idx_global, future_pred])
                    bar_minute = current_minute + hold_minutes
                    if should_exit_on_reversal(
                        position_direction=direction,
                        signal_direction=future_dir,
                        signal_confidence=future_conf,
                        minutes_since_open=bar_minute,
                    ):
                        exit_reason = "signal_reversal"
                        break

                # ── Build RL state for exit decision ──
                hold_norm = hold_minutes / hard_exits["max_hold_minutes"]

                # Per-minute greeks
                right_upper = option_right.upper()
                alt_right = right_upper[0] if len(right_upper) > 1 else right_upper
                minute_greeks = None
                if greeks_lookup is not None and actual_strike is not None:
                    minute_greeks = (greeks_lookup.get((future_time, actual_strike, right_upper)) or
                                     greeks_lookup.get((future_time, actual_strike, alt_right)))

                if minute_greeks is not None:
                    cur_iv   = minute_greeks["iv"]
                    cur_delta = minute_greeks["delta"]
                else:
                    cur_iv   = actual_iv
                    cur_delta = actual_delta

                # Recovery lookup
                recovery_prob = 0.3
                if recovery_lookup is not None and actual_strike is not None:
                    d_bucket = get_delta_bucket(abs(cur_delta))
                    v_bucket = get_iv_bucket(cur_iv)
                    p_bucket = get_pnl_bucket(premium_pnl_pct)
                    recovery_prob = float(recovery_lookup.get((d_bucket, v_bucket, p_bucket), 0.3))

                iv_ratio = cur_iv / entry_atm_iv if entry_atm_iv > 0 else 1.0
                trailing_drawdown = max(0.0, peak_pnl - premium_pnl_pct)
                position_state = _build_position_state(
                    pnl_pct=premium_pnl_pct,
                    hold_norm=hold_norm,
                    current_delta=cur_delta,
                    recovery_prob=recovery_prob,
                    iv_ratio=iv_ratio,
                    mae=mae,
                    trailing_drawdown=trailing_drawdown,
                )
                market_features = (
                    entry_market_features
                    if single_step_eval
                    else (
                        market_features_matrix[idx_global]
                        if market_features_matrix is not None
                        else day_features[min(i + t + 1, len(day_features) - 1)]
                    )
                )

                dynamic_market = _build_dynamic_market_features(
                    current_minute=current_minute + hold_minutes,
                    entry_spot=entry_price,
                    entry_iv=entry_atm_iv,
                    spot_history=_spot_history,
                    greeks_lookup=greeks_lookup,
                    actual_strike=actual_strike,
                    option_right=option_right,
                    future_time=future_time,
                    entry_minute=current_minute,
                    direction=direction,
                    premium_history=_premium_history,
                )

                state_parts = [market_features, dynamic_market, position_state, mlp_context, ticker_context, strike_context]
                if RL_CONFIG.get("use_sniper_mode", False):
                    sniper_state = np.zeros(SNIPER_STATE_DIM, dtype=np.float32)
                    state_parts.append(sniper_state)

                state = _pad_or_trim_state(np.concatenate(state_parts), rl_agent.state_dim)
                state_tensor = torch.FloatTensor(state).unsqueeze(0).to(device)

                if exit_policy == "hold":
                    exit_action = 0
                else:
                    with torch.no_grad():
                        exit_action, _, _ = rl_agent.get_action(state_tensor, action_type="exit", deterministic=True)

                if int(exit_action) == 1:
                    is_emergency = premium_pnl_pct <= RL_CONFIG.get(
                        "emergency_stop_pct",
                        hard_exits["max_loss_pct"],
                    )
                    is_voluntary_exit_allowed = (
                        hold_minutes >= rl_min_hold
                        and premium_pnl_pct >= float(agent_exit_min_pnl)
                    )
                    if is_voluntary_exit_allowed or is_emergency:
                        exit_reason = "agent_exit"
                        break

            # Real strike distance from spot
            strike_distance_pts = actual_strike - entry_price if actual_strike else 0.0

            # Dynamic sizing for options (risk % of balance)
            contracts = _calc_contracts_options(effective_risk_capital, entry_premium) if entry_premium else 1

            # Apply contract limits
            contracts = min(contracts, 500) # Max 500 options contracts

            # P&L in dollars: premium_change * 100 * contracts
            premium_pnl_dollars = (exit_premium - entry_premium) * 100.0 * contracts
            balance += premium_pnl_dollars

            # Drawdown tracker updates
            if premium_pnl_dollars > 0:
                ticker_consecutive_losses[loss_streak_key] = 0
            elif premium_pnl_dollars < 0:
                ticker_consecutive_losses[loss_streak_key] += 1

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
                "raw_entry_premium": round(raw_entry_premium, 2) if using_real_data else 0,
                "entry_premium": round(entry_premium, 2) if entry_premium else 0,
                "entry_spread_pct": effective_spread if using_real_data else 0,
                "exit_premium": round(exit_premium, 2) if exit_premium else 0,
                "pnl_pct": premium_pnl_pct,
                "pnl_dollars": premium_pnl_dollars,
                "hold_minutes": hold_minutes, "exit_reason": exit_reason,
                "confidence": signal_confidence,
                "strike_bucket": strike_bucket_label,
                "delta_target": delta_target,
                "actual_delta": round(actual_delta, 3),
                "actual_iv": round(actual_iv, 3),
                "strike_distance_pts": strike_distance_pts,
                "using_real_data": using_real_data,
                "mae": mae,
                "contracts": contracts,
                "balance": round(balance, 2),
            })
            last_trade_time[key] = current_minute
            open_positions[key] = current_minute + max(hold_minutes, reentry_lock_minutes)

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
    if entry_skip_action:
        print(f"  RL entry policy skips: {skipped_by_entry_policy} candidate entries skipped")
    if block_rules:
        print(f"  RL policy rules: {blocked_by_rule} candidate entries blocked")
    if block_short_confidence_above is not None:
        print(
            f"  RL confidence guard: {blocked_by_confidence} SHORT candidates blocked "
            f"(confidence > {block_short_confidence_above:.3f})"
        )
    if feature_rules:
        print(f"  RL feature guards: {blocked_by_feature} candidate entries blocked")
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

    # Use pnl_dollars for W/L ratio — pnl_pct is in different units between
    # GBT-only (spot returns) and GBT+RL (premium returns), making them incomparable.
    mean_winner = wins["pnl_dollars"].mean() if len(wins) > 0 else 0
    mean_loser = abs(losses["pnl_dollars"].mean()) if len(losses) > 0 else 1e-6
    wl_ratio = mean_winner / mean_loser if mean_loser > 0 else 0

    hold_col = "actual_hold_minutes" if "actual_hold_minutes" in trades_df.columns else "hold_minutes"
    avg_hold_w = wins[hold_col].mean() if len(wins) > 0 and hold_col in wins.columns else 0
    avg_hold_l = losses[hold_col].mean() if len(losses) > 0 and hold_col in losses.columns else 0

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
    parser.add_argument(
        "--threshold",
        type=float,
        default=RL_CONFIG["min_confidence"],
        help="Base confidence threshold. LONG uses this value; SHORT uses the configured directional offset.",
    )
    parser.add_argument("--cooldown", type=int, default=15)
    parser.add_argument("--position-size", type=float, default=1.0,
                        help="Kept for parity with backtest_gbt_parquet.py; sizing is risk-capital based.")
    parser.add_argument("--target-long", type=float, default=0.010)
    parser.add_argument("--target-short", type=float, default=0.005)
    parser.add_argument("--stop", type=float, default=0.003)
    parser.add_argument("--min-iv", type=float, default=0.0,
                        help="Minimum iv_percentile for the GBT-only baseline, matching backtest_gbt_parquet.py.")
    parser.add_argument("--spx-target", type=float, default=0.010,
                        help="SPX target override used by the GBT-only simulator.")
    parser.add_argument("--etf-target", type=float, default=0.006,
                        help="Default SPY/QQQ target override used by the GBT-only simulator.")
    parser.add_argument("--spx-stop", type=float, default=0.0025,
                        help="SPX stop override used by the GBT-only simulator.")
    parser.add_argument("--etf-stop", type=float, default=0.0025,
                        help="Default SPY/QQQ stop override used by the GBT-only simulator.")
    parser.add_argument("--qqq-target", type=float, default=None,
                        help="QQQ target override; defaults to --etf-target.")
    parser.add_argument("--spy-target", type=float, default=None,
                        help="SPY target override; defaults to --etf-target.")
    parser.add_argument("--qqq-stop", type=float, default=None,
                        help="QQQ stop override; defaults to --etf-stop.")
    parser.add_argument("--spy-stop", type=float, default=None,
                        help="SPY stop override; defaults to --etf-stop.")
    parser.add_argument("--max-time", type=int, default=180)
    parser.add_argument("--min-entry-minute", type=int, default=580,
                        help="Earliest absolute minute of day for entries (10:30 = 630)")
    parser.add_argument("--min-short-entry-minute", type=int, default=None,
                        help="Earliest absolute minute of day for SHORT entries (10:15 = 615)")
    parser.add_argument("--min-short-price-vs-ib-high", type=float, default=None,
                        help="For SHORT entries, require price_vs_ib_high >= this value.")
    parser.add_argument("--tickers", nargs="+", default=None, help="Filter tickers (e.g. SPX SPY QQQ)")
    parser.add_argument("--start-date", default=None, help="Inclusive YYYYMMDD start date filter")
    parser.add_argument("--end-date", default=None, help="Inclusive YYYYMMDD end date filter")
    parser.add_argument("--ensemble", action="store_true", help="Load model as ensemble")
    parser.add_argument("--risk-capital", type=float, default=500.0,
                        help="Risk capital in dollars per trade (fixed)")
    parser.add_argument("--filter-by-greeks", action="store_true",
                        help="Drop training dates that have no 0DTE greeks parquet in ThetaData. "
                             "Use this to diagnose low trade counts — shows coverage before running.")
    parser.add_argument(
        "--single-step-eval",
        action="store_true",
        help="Freeze the entry market snapshot while dynamic and position features evolve, matching RL training/live.",
    )
    parser.add_argument("--strict-wf", action="store_true", help="Enable strict Walk-Forward date filtering for GBT inference")
    parser.add_argument(
        "--block-rl-rule",
        action="append",
        default=[],
        help="Block RL entries matching ticker:direction:bucket; use * as wildcard, e.g. SPY:LONG:* or *:*:itm_light.",
    )
    parser.add_argument(
        "--block-short-confidence-above",
        type=float,
        default=None,
        help="Block over-confident SHORT candidates above this probability; useful as a calibration guard.",
    )
    parser.add_argument(
        "--block-rl-feature-rule",
        action="append",
        default=[],
        help="Block RL entries by entry-row feature rule direction:feature:op:value; op is lt/lte/gt/gte.",
    )
    parser.add_argument(
        "--agent-exit-min-pnl",
        type=float,
        default=None,
        help="Minimum option PnL pct required for voluntary RL agent exits. "
             "Defaults to RL_CONFIG['agent_exit_min_pnl_pct']; emergency exits still apply.",
    )
    parser.add_argument(
        "--force-rl-strike-bucket",
        default=None,
        help="Diagnostic override: force RL strike bucket by index or label "
             "(deep_otm, otm_far, otm_near, otm_light, atm, itm_light, itm).",
    )
    parser.add_argument(
        "--force-rl-ticker-strike-buckets",
        default=None,
        help="Diagnostic per-ticker strike overrides, e.g. SPX:deep_otm,QQQ:atm,SPY:itm.",
    )
    parser.add_argument(
        "--force-rl-delta-target",
        type=float,
        default=None,
        help="Diagnostic override: select the option closest to this absolute delta target, e.g. 0.80.",
    )
    parser.add_argument(
        "--rl-underlying-exit-policy",
        choices=["off", "hybrid", "only"],
        default="off",
        help=(
            "Diagnostic exit alignment: off=current premium exits; "
            "hybrid=underlying target/stop plus premium exits; "
            "only=underlying target/stop without premium hard stop/take-profit."
        ),
    )
    parser.add_argument(
        "--disable-rl-signal-reversal",
        action="store_true",
        help="Diagnostic override: do not force RL exits on GBT signal reversal.",
    )
    parser.add_argument(
        "--rl-exit-policy",
        choices=["agent", "hold"],
        default="agent",
        help="Diagnostic exit policy. 'hold' disables voluntary agent exits; hard exits, reversals and max-time remain.",
    )
    parser.add_argument(
        "--rl-entry-skip-action",
        action="store_true",
        help="Use sniper_head as direct SKIP(0) / ENTER+strike(1-7) entry policy.",
    )
    parser.add_argument(
        "--rl-max-loss-pct",
        type=float,
        default=None,
        help=(
            "Diagnostic override for option premium hard stop magnitude. "
            "Positive values are normalized to losses, so 0.50 and -0.50 both mean -0.50."
        ),
    )
    parser.add_argument(
        "--rl-max-profit-pct",
        type=float,
        default=None,
        help="Diagnostic override for option premium hard take-profit, e.g. 3.0.",
    )
    parser.add_argument(
        "--rl-reentry-lock-minutes",
        type=int,
        default=None,
        help=(
            "Optional minimum minutes from entry before same ticker/day RL "
            "re-entry. Default 0 matches GBT-style open-position + cooldown "
            "behavior; use 180 only as a diagnostic long-horizon lock."
        ),
    )
    args = parser.parse_args()
    block_rules = [_parse_block_rule(rule) for rule in args.block_rl_rule]
    feature_rules = [_parse_feature_rule(rule) for rule in args.block_rl_feature_rule]
    force_strike_bucket = _parse_strike_bucket_override(args.force_rl_strike_bucket)
    force_ticker_strike_buckets = _parse_ticker_strike_bucket_overrides(args.force_rl_ticker_strike_buckets)
    if block_rules:
        print(f"  RL block rules: {args.block_rl_rule}")
    if feature_rules:
        print(f"  RL feature rules: {args.block_rl_feature_rule}")
    if force_strike_bucket is not None:
        print(
            "  RL force strike bucket: "
            f"{force_strike_bucket} ({STRIKE_BUCKETS[force_strike_bucket]['label']})"
        )
    if force_ticker_strike_buckets:
        pretty = ", ".join(
            f"{ticker}:{STRIKE_BUCKETS[idx]['label']}"
            for ticker, idx in sorted(force_ticker_strike_buckets.items())
        )
        print(f"  RL force ticker strike buckets: {pretty}")
    if args.force_rl_delta_target is not None:
        print(f"  RL force delta target: {abs(float(args.force_rl_delta_target)):.2f}")
    if args.rl_underlying_exit_policy != "off":
        print(f"  RL underlying exit policy: {args.rl_underlying_exit_policy}")
    if args.disable_rl_signal_reversal:
        print("  RL signal reversal exit: disabled")
    if args.rl_exit_policy != "agent":
        print(f"  RL exit policy override: {args.rl_exit_policy}")
    if args.rl_entry_skip_action:
        print("  RL entry skip action: enabled")
    if args.rl_max_loss_pct is not None:
        print(f"  RL max loss override: {-abs(args.rl_max_loss_pct):.2f}")
    if args.rl_max_profit_pct is not None:
        print(f"  RL max profit override: {args.rl_max_profit_pct:.2f}")

    device = get_device()

    # ── Load MLP ──
    print("=" * 72)
    print("  RL BACKTEST — GBT+RL vs GBT-ONLY")
    print("=" * 72)
    print(f"\n[1/5] Loading GBT model...")
    if args.strict_wf and args.model.endswith('.joblib') and not args.model.endswith('_history.joblib'):
        args.model = args.model.replace('.joblib', '_history.joblib')

    model_path = str(Path(args.model).resolve())
    normalizer_path = str(Path(args.normalizer).resolve())

    ticker_models = {}
    ticker_normalizers = {}
    is_ticker_specific = False
    model = None
    normalizer = None

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
        # Assign first one to 'model' and 'normalizer' to prevent undefined variable checks
        model = any_model
        normalizer = next(iter(ticker_normalizers.values()))
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
        is_gbt = hasattr(model, "predict_proba") and not isinstance(model, torch.nn.Module)

    # ── Load RL agent ──
    print(f"\n[2/5] Loading RL agent from {args.rl_model}...")
    if os.path.exists(args.rl_model):
        rl_agent = PPOAgent.load(args.rl_model, device)
        rl_agent.eval()
        has_rl = True
        # Compute curriculum min_hold from the agent's actual training step
        _agent_total_updates = getattr(rl_agent, "total_updates", RL_CONFIG.get("total_updates", 500))
        _curriculum = CurriculumScheduler(total_updates=_agent_total_updates)
        _agent_step = getattr(rl_agent, "update_step", 0)
        _phase_info = _curriculum.get_phase_info(_agent_step)
        if _agent_step == 0:
            # Legacy model without step metadata — fall back to final phase
            _final_phase = max(RL_CONFIG.get("curriculum_phases", {0: {}}).keys())
            _curriculum_min_hold = float(
                RL_CONFIG.get("curriculum_phases", {})
                .get(_final_phase, {})
                .get("min_hold_minutes", 0)
            )
        else:
            _curriculum_min_hold = float(_phase_info.get("min_hold_minutes", 0))
        rl_min_hold = max(_curriculum_min_hold, float(HARD_EXITS.get("min_hold_minutes", 0)))
        print(f"  OK ({sum(p.numel() for p in rl_agent.parameters()):,} params)")
        print(
            f"  Agent step: {_agent_step}/{_agent_total_updates} | "
            f"Phase: {_phase_info['phase']} | min_hold: {rl_min_hold:.0f} min"
        )
    else:
        print(f"  RL model not found — using random policy for comparison")
        rl_agent = PPOAgent()
        rl_agent.to(device)
        rl_agent.eval()
        has_rl = False
        # Default to final phase min_hold for random agent
        _final_phase = max(RL_CONFIG.get("curriculum_phases", {0: {}}).keys())
        rl_min_hold = max(
            float(RL_CONFIG["curriculum_phases"][_final_phase].get("min_hold_minutes", 0)),
            float(HARD_EXITS.get("min_hold_minutes", 0))
        )

    # ── Load recovery stats ──
    recovery_stats = None
    stats_path = os.path.join(PROJECT_ROOT, "rl_data", "recovery_stats.pkl")
    if os.path.exists(stats_path):
        try:
            with open(stats_path, "rb") as f:
                recovery_stats = pickle.load(f)
            print(f"  OK (Recovery stats loaded: {len(recovery_stats)} entries)")
        except Exception as e:
            print(f"  Warning: Failed to load recovery stats: {e}")
    else:
        print(f"  Warning: recovery_stats.pkl not found at {stats_path}")

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

    if args.start_date:
        df = df[df["date"] >= str(args.start_date)]
        print(f"  Filtered start date: {args.start_date}")
    if args.end_date:
        df = df[df["date"] <= str(args.end_date)]
        print(f"  Filtered end date:   {args.end_date}")

    # ── Optional: drop dates with no 0DTE greeks coverage ──
    if args.filter_by_greeks:
        ticker_to_options = {"SPX": "SPXW", "SPXW": "SPXW", "QQQ": "QQQ", "SPY": "SPY"}
        available_by_ticker: dict[str, set] = {}
        for tk in (args.tickers or df["ticker"].unique().tolist()):
            options_ticker = ticker_to_options.get(tk, tk)
            greeks_root = Path(OPTIONS_DIR) / options_ticker / "greeks"
            covered: set[str] = set()
            if greeks_root.exists():
                for f in greeks_root.rglob(f"{options_ticker}_*_greeks.parquet"):
                    parts = f.stem.split("_")   # e.g. SPXW_20240115_20240115_greeks
                    if len(parts) >= 3 and parts[1] == parts[2]:   # exp == trade date → 0DTE
                        covered.add(parts[1])
            available_by_ticker[tk] = covered
            print(f"  [{tk}] greeks coverage: {len(covered)} dates found under {greeks_root}")

        before = len(df)
        def _has_greeks(row):
            tk = row["ticker"]
            return str(row["date"]) in available_by_ticker.get(tk, set())
        df = df[df.apply(_has_greeks, axis=1)]
        after = len(df)
        print(f"  Greeks filter: {before:,} -> {after:,} rows "
              f"({before - after:,} dropped, {df['date'].nunique()} dates remain)")

    print(f"  {len(df):,} samples | {df['date'].nunique()} days | tickers: {df['ticker'].unique().tolist()}")

    # Reset index after all filtering so feature arrays align with df.index
    df = df.reset_index(drop=True)

    # ── GBT predictions ──
    print(f"\n[4/5] Running GBT predictions...")
    # Build feature matrix matching expected columns (fast, no fragmentation)
    features = np.zeros((len(df), len(FEATURE_COLUMNS)), dtype=np.float32)
    for i, col in enumerate(FEATURE_COLUMNS):
        if col in df.columns:
            features[:, i] = df[col].values.astype(np.float32)

    features = np.nan_to_num(features, nan=0.0, posinf=5.0, neginf=-5.0)

    if args.strict_wf:
        print(f"  [i] Using STRICT Walk-Forward inference (date-by-date filtering) for GBT predictions...")
        probs = np.zeros((len(df), 3), dtype=np.float32)
        unique_dates = sorted(df['date'].unique()) # Uses 'date' col typically strings
        for d_str in unique_dates:
            mask = df['date'] == d_str
            for ticker in df.loc[mask, 'ticker'].unique():
                t_mask = mask & (df['ticker'] == ticker)
                idx = np.where(t_mask)[0]
                if len(idx) == 0:
                    continue
                if is_ticker_specific and ticker in ticker_models:
                    t_model = ticker_models[ticker]
                    probs[idx] = t_model.predict_proba(features[idx], date=str(d_str))
                else:
                    if is_gbt:
                        probs[idx] = model.predict_proba(features[idx], date=str(d_str))
                    else:
                        batch = torch.FloatTensor(normalizer.transform(features[idx])).to(device)
                        with torch.no_grad():
                            logits, _ = model(batch)
                        probs[idx] = torch.softmax(logits, dim=-1).cpu().numpy()
    else:
        probs = np.zeros((len(df), 3), dtype=np.float32)
        if is_ticker_specific:
            for ticker in df['ticker'].unique():
                mask = df['ticker'] == ticker
                idx = np.where(mask)[0]
                if len(idx) == 0:
                    continue
                if ticker in ticker_models:
                    probs[idx] = ticker_models[ticker].predict_proba(features[idx])
                else:
                    probs[idx] = model.predict_proba(features[idx])
        else:
            if is_gbt:
                probs = model.predict_proba(features)
            else:
                batch = torch.FloatTensor(normalizer.transform(features)).to(device)
                with torch.no_grad():
                    logits, _ = model(batch)
                probs = torch.softmax(logits, dim=-1).cpu().numpy()
    predictions, _ = get_independent_signals(probs, base_confidence=args.threshold)

    print(f"  Predictions: {np.bincount(predictions, minlength=3)} [SHORT, HOLD, LONG]")

    # ── Simulate both ──
    print(f"\n[5/5] Running simulations...")
    print(
        "  GBT-only ticker exits: "
        f"SPX {args.spx_target:.2%}/{args.spx_stop:.2%}; "
        f"QQQ {(args.qqq_target if args.qqq_target is not None else args.etf_target):.2%}/"
        f"{(args.qqq_stop if args.qqq_stop is not None else args.etf_stop):.2%}; "
        f"SPY {(args.spy_target if args.spy_target is not None else args.etf_target):.2%}/"
        f"{(args.spy_stop if args.spy_stop is not None else args.etf_stop):.2%}"
    )

    # GBT-only
    print(f"  Running GBT-only simulation...")
    gbt_simulator = GBTSpotTradeSimulator(
        threshold=args.threshold,
        position_size=args.position_size,
        cooldown_minutes=args.cooldown,
        target_long=args.target_long,
        target_short=args.target_short,
        stop_pct=args.stop,
        max_time=args.max_time,
        min_iv_pct=args.min_iv,
        discord_enabled=False,
        risk_capital=args.risk_capital,
        min_entry_minute=args.min_entry_minute,
        min_short_entry_minute=args.min_short_entry_minute,
        min_short_price_vs_ib_high=args.min_short_price_vs_ib_high,
        spx_target=args.spx_target,
        etf_target=args.etf_target,
        spx_stop=args.spx_stop,
        etf_stop=args.etf_stop,
        qqq_target=args.qqq_target,
        spy_target=args.spy_target,
        qqq_stop=args.qqq_stop,
        spy_stop=args.spy_stop,
    )
    mlp_trades = gbt_simulator.simulate(df, predictions, probs)
    mlp_metrics = calculate_metrics(mlp_trades)
    print(f"  GBT-only: {len(mlp_trades)} trades")

    import sys
    print("\n--- GBT ONLY RESULTS ---")
    for k, v in mlp_metrics.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.3f}")
        else:
            print(f"  {k}: {v}")

    logs_dir = os.path.join(PROJECT_ROOT, "logs")           # → Gex-Dashboard-Live\logs
    os.makedirs(logs_dir, exist_ok=True)                    # no falla si ya existe
    mlp_trades.to_csv(os.path.join(logs_dir, "gbt_only_backtest_trades.csv"), index=False)
    print("Saved trades to logs/gbt_only_backtest_trades.csv")

    # GBT+RL
    print(f"  Running GBT+RL simulation...")
    rl_trades = simulate_mlp_rl(
        df, predictions, probs, rl_agent,
        market_features_matrix=features,
        threshold=args.threshold, max_time=args.max_time,
        cooldown=args.cooldown, device=device,
        risk_capital=args.risk_capital,
        target_long=args.target_long,
        target_short=args.target_short,
        stop_pct=args.stop,
        spx_target=args.spx_target,
        etf_target=args.etf_target,
        spx_stop=args.spx_stop,
        etf_stop=args.etf_stop,
        qqq_target=args.qqq_target,
        spy_target=args.spy_target,
        qqq_stop=args.qqq_stop,
        spy_stop=args.spy_stop,
        single_step_eval=args.single_step_eval,
        recovery_lookup=recovery_stats,
        block_rules=block_rules,
        block_short_confidence_above=args.block_short_confidence_above,
        feature_rules=feature_rules,
        agent_exit_min_pnl=args.agent_exit_min_pnl,
        force_strike_bucket=force_strike_bucket,
        force_ticker_strike_buckets=force_ticker_strike_buckets,
        force_delta_target=args.force_rl_delta_target,
        underlying_exit_policy=args.rl_underlying_exit_policy,
        disable_signal_reversal=args.disable_rl_signal_reversal,
        exit_policy=args.rl_exit_policy,
        entry_skip_action=args.rl_entry_skip_action,
        max_loss_pct=args.rl_max_loss_pct,
        max_profit_pct=args.rl_max_profit_pct,
        reentry_lock_minutes=args.rl_reentry_lock_minutes,
        min_entry_minute=args.min_entry_minute,
        min_short_entry_minute=args.min_short_entry_minute,
        min_short_price_vs_ib_high=args.min_short_price_vs_ib_high)
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
