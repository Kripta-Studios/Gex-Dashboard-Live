from __future__ import annotations

import argparse
import json
import math
import os
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NEURAL_ROOT = PROJECT_ROOT / "neural"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(NEURAL_ROOT) not in sys.path:
    sys.path.insert(0, str(NEURAL_ROOT))

from neural.jepa.evaluate_180m_direction import fmt_float, fmt_money, fmt_pct
from neural.jepa.jepa_180m_signal import Jepa180mSignalModel, normalize_ticker


THETADATA_DIR = Path(str(Path("D:/ThetaData")))
OPTIONS_DIR = Path(str(Path(str(THETADATA_DIR)))) / "data_options"
GREEKS_COLS = [
    "underlying_timestamp",
    "strike",
    "right",
    "delta",
    "bid",
    "ask",
    "implied_vol",
    "theta",
    "gamma",
    "underlying_price",
]
TICKER_TO_OPTIONS = {"SPX": "SPXW", "SPXW": "SPXW", "QQQ": "QQQ", "SPY": "SPY"}
LOG_PATH: Path | None = None
LOG_HEARTBEAT_SECONDS = int(os.environ.get("JEPA_LOG_HEARTBEAT_SECONDS", "60"))
_LOG_LOCK = threading.Lock()


def log(message: str) -> None:
    with _LOG_LOCK:
        print(message, flush=True)
        if LOG_PATH is not None:
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with LOG_PATH.open("a", encoding="utf-8") as handle:
                handle.write(message + os.linesep)


@contextmanager
def logged_phase(name: str, heartbeat_seconds: int | None = None):
    start = time.time()
    interval = int(heartbeat_seconds or LOG_HEARTBEAT_SECONDS)
    stop_event = threading.Event()

    def heartbeat() -> None:
        while not stop_event.wait(max(1, interval)):
            log(f"[OPTION_POLICY] STILL {name} elapsed={time.time() - start:.1f}s")

    log(f"[OPTION_POLICY] START {name}")
    thread = threading.Thread(target=heartbeat, name=f"option-policy-{name[:24]}", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop_event.set()
        thread.join(timeout=1.0)
        log(f"[OPTION_POLICY] DONE {name} elapsed={time.time() - start:.1f}s")


def get_half_spread(abs_delta: float) -> float:
    abs_delta = abs(float(abs_delta))
    if abs_delta < 0.30:
        return 0.03
    if abs_delta > 0.60:
        return 0.01
    return 0.015


def _load_daily_greeks(date_str: str, ticker: str = "SPX") -> tuple[pd.DataFrame | None, dict | None, dict | None]:
    import pyarrow.parquet as pq

    options_ticker = TICKER_TO_OPTIONS.get(str(ticker).upper(), str(ticker).upper())
    date_str = normalize_date(date_str)
    year, month = date_str[:4], date_str[4:6]
    search_dir = OPTIONS_DIR / options_ticker / "greeks" / year / month
    if not search_dir.exists():
        return None, None, None
    for path in search_dir.glob(f"{options_ticker}_*_{date_str}_greeks.parquet"):
        parts = path.name.split("_")
        if len(parts) < 3 or parts[1] != date_str:
            continue
        try:
            available = list(pq.ParquetFile(path).schema.names)
            cols = [c for c in GREEKS_COLS if c in available]
            df = pd.read_parquet(path, columns=cols)
            df["dt"] = pd.to_datetime(df["underlying_timestamp"])
            df["time_str"] = df["dt"].dt.strftime("%H:%M")
            df["right_upper"] = df["right"].astype(str).str.upper()
            df["delta_abs"] = df["delta"].astype(float).abs()
            bid = df["bid"].fillna(0).astype(float)
            ask = df["ask"].fillna(0).astype(float)
            df["mid"] = ((bid + ask) / 2.0).where((bid > 0) | (ask > 0), 0.0)
            valid = df[df["mid"] > 0].copy()
            valid["_key"] = list(zip(valid["time_str"], valid["strike"].astype(float), valid["right_upper"]))
            premium_lookup = dict(zip(valid["_key"], valid["mid"].astype(float)))
            greeks_lookup = {}
            theta = valid["theta"] if "theta" in valid else pd.Series(0.0, index=valid.index)
            gamma = valid["gamma"] if "gamma" in valid else pd.Series(0.0, index=valid.index)
            iv = valid["implied_vol"] if "implied_vol" in valid else pd.Series(0.15, index=valid.index)
            spot = valid["underlying_price"] if "underlying_price" in valid else pd.Series(0.0, index=valid.index)
            for key, delta, theta_v, iv_v, gamma_v, spot_v in zip(
                valid["_key"],
                valid["delta"].fillna(0).astype(float),
                theta.fillna(0).astype(float),
                iv.fillna(0.15).astype(float),
                gamma.fillna(0).astype(float),
                spot.fillna(0).astype(float),
            ):
                greeks_lookup[key] = {
                    "delta": float(delta),
                    "theta": float(theta_v),
                    "iv": float(iv_v),
                    "gamma": float(gamma_v),
                    "spot": float(spot_v),
                }
            return df, premium_lookup, greeks_lookup
        except Exception as exc:
            log(f"[OPTION_POLICY] failed loading greeks {path}: {exc}")
            return None, None, None
    return None, None, None


def _find_strike_by_delta(df_slice: pd.DataFrame, direction: str, delta_target: float) -> dict | None:
    if direction == "LONG":
        opt = df_slice[df_slice["right_upper"].isin(["CALL", "C"])].copy()
    else:
        opt = df_slice[df_slice["right_upper"].isin(["PUT", "P"])].copy()
    if opt.empty:
        return None
    if "bid" in opt.columns:
        opt = opt[opt["bid"].astype(float) > 0]
    opt = opt[opt["delta_abs"].astype(float) > 0.01]
    if opt.empty:
        return None
    opt["delta_diff"] = (opt["delta_abs"].astype(float) - float(delta_target)).abs()
    best = opt.loc[opt["delta_diff"].idxmin()]
    bid = float(best.get("bid", 0.0) or 0.0)
    ask = float(best.get("ask", 0.0) or 0.0)
    mid = (bid + ask) / 2.0 if (bid > 0.0 or ask > 0.0) else 0.0
    if mid <= 0.0:
        return None
    return {
        "strike": float(best["strike"]),
        "mid_price": float(mid),
        "bid": bid,
        "ask": ask,
        "delta": float(best.get("delta", delta_target)),
        "iv": float(best.get("implied_vol", 0.15) or 0.15),
        "theta": float(best.get("theta", 0.0) or 0.0),
        "gamma": float(best.get("gamma", 0.0) or 0.0),
        "right": "CALL" if direction == "LONG" else "PUT",
    }


def _get_premium_at_time(premium_lookup: dict, strike: float, right: str, time_str: str) -> float | None:
    right_upper = str(right).upper()
    mid = premium_lookup.get((str(time_str), float(strike), right_upper))
    if mid is not None and mid > 0:
        return float(mid)
    alt = right_upper[0] if len(right_upper) > 1 else right_upper
    mid = premium_lookup.get((str(time_str), float(strike), alt))
    return float(mid) if mid is not None and mid > 0 else None


LEAKAGE_COLUMNS = {
    "target",
    "time_to_target",
    "time_to_stop",
    "max_move",
    "future_return_180m",
    "future_return_bps_180m",
    "future_up_180m",
    "future_abs_bps_180m",
    "future_spot_180m",
}

OPTION_FEATURES = [
    "ticker_SPX",
    "ticker_QQQ",
    "ticker_SPY",
    "side_LONG",
    "side_SHORT",
    "jepa180_prob_up",
    "jepa180_confidence",
    "jepa180_direction",
    "jepa180_edge",
    "entry_minute",
    "pos_in_day",
    "minutes_to_close",
    "delta_target",
    "actual_delta",
    "actual_delta_abs",
    "entry_premium",
    "raw_entry_premium",
    "entry_spread_pct",
    "premium_to_spot_bps",
    "strike_distance_pts",
    "strike_distance_bps",
    "actual_iv",
    "actual_theta",
    "actual_gamma",
    "theta_over_premium",
    "gamma_notional",
]

EXIT_DYNAMIC_FEATURES = [
    "hold_minutes",
    "hold_norm",
    "current_pnl_pct",
    "current_return_on_risk",
    "current_premium",
    "premium_ratio",
    "peak_pnl_pct",
    "drawdown_from_peak",
    "mae_pnl_pct",
    "current_delta",
    "current_delta_abs",
    "current_iv",
    "current_gamma",
    "spot_return_bps",
    "signed_spot_return_bps",
    "minutes_remaining",
]


def normalize_date(value) -> str:
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return digits[:8] if len(digits) >= 8 else str(value)


def month_key(value) -> str:
    return normalize_date(value)[:6]


def time_to_minutes(value) -> int:
    try:
        text = str(value)[:5]
        hour, minute = text.split(":")
        return int(hour) * 60 + int(minute)
    except Exception:
        return 0


def calc_contracts(risk_capital: float, entry_premium: float) -> int:
    cost = float(entry_premium) * 100.0
    if cost <= 0.0:
        return 1
    return max(1, int(float(risk_capital) / cost))


def make_matrix(
    frame: pd.DataFrame,
    features: list[str],
    medians: pd.Series | None = None,
) -> tuple[pd.DataFrame, pd.Series]:
    x = frame.reindex(columns=features)
    x = x.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    if medians is None:
        medians = x.median(axis=0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    x = x.fillna(medians).fillna(0.0)
    return x.astype(np.float32), medians


def train_regressor(
    frame: pd.DataFrame,
    features: list[str],
    target_col: str,
    seed: int,
    n_estimators: int,
    n_jobs: int,
    ) -> tuple[lgb.LGBMRegressor, pd.Series]:
    x, medians = make_matrix(frame, features)
    y = frame[target_col].astype(float).clip(-2.0, 5.0).to_numpy()
    model = lgb.LGBMRegressor(
        objective="huber",
        alpha=0.90,
        n_estimators=int(n_estimators),
        learning_rate=0.035,
        num_leaves=31,
        max_depth=-1,
        subsample=0.85,
        colsample_bytree=0.85,
        min_child_samples=25,
        reg_alpha=0.05,
        reg_lambda=0.50,
        random_state=int(seed),
        n_jobs=int(n_jobs),
        verbose=-1,
    )
    with logged_phase(
        f"fit LGBMRegressor target={target_col} rows={len(frame):,} features={len(features):,} "
        f"trees={int(n_estimators):,} n_jobs={int(n_jobs)}"
    ):
        model.fit(x, y)
    return model, medians


def train_ranker(
    frame: pd.DataFrame,
    features: list[str],
    target_col: str,
    seed: int,
    n_estimators: int,
    n_jobs: int,
) -> tuple[lgb.LGBMRanker, pd.Series]:
    work = frame.sort_values(["signal_id", "delta_target"]).copy()
    x_train, medians = make_matrix(work, features)
    labels = work.groupby("signal_id")[target_col].rank(method="dense").astype(int).to_numpy() - 1
    groups = work.groupby("signal_id", sort=False).size().astype(int).tolist()
    model = lgb.LGBMRanker(
        objective="lambdarank",
        n_estimators=int(n_estimators),
        learning_rate=0.035,
        num_leaves=31,
        max_depth=-1,
        subsample=0.90,
        colsample_bytree=0.90,
        min_child_samples=10,
        reg_alpha=0.05,
        reg_lambda=0.50,
        random_state=int(seed),
        n_jobs=int(n_jobs),
        verbose=-1,
    )
    with logged_phase(
        f"fit LGBMRanker target={target_col} rows={len(work):,} groups={len(groups):,} "
        f"features={len(features):,} trees={int(n_estimators):,} n_jobs={int(n_jobs)}"
    ):
        model.fit(x_train, labels, group=groups)
    return model, medians


def predict_regressor(model, frame: pd.DataFrame, features: list[str], medians: pd.Series) -> np.ndarray:
    x, _ = make_matrix(frame, features, medians)
    return model.predict(x).astype(np.float64)


def apply_signal_cooldown(signals: pd.DataFrame, cooldown_steps: int) -> pd.DataFrame:
    if signals.empty:
        return signals
    work = signals.sort_values(["ticker", "date", "pos_in_day"]).copy()
    kept_index = []
    next_allowed: dict[tuple[str, str], int] = {}
    for idx, row in work.iterrows():
        key = (str(row["ticker"]), str(row["date"]))
        pos = int(row["pos_in_day"])
        if pos < next_allowed.get(key, -1):
            continue
        kept_index.append(idx)
        next_allowed[key] = pos + int(cooldown_steps)
    return work.loc[kept_index].reset_index(drop=True)


def load_path_frame(data_path: str | Path, min_date: str | None = None) -> pd.DataFrame:
    cols = ["ticker", "date", "time", "spot_price"]
    frame = pd.read_parquet(data_path, columns=cols)
    frame["ticker"] = frame["ticker"].map(normalize_ticker)
    frame["date"] = frame["date"].map(normalize_date)
    if min_date:
        frame = frame[frame["date"] >= normalize_date(min_date)].copy()
    frame["minutes"] = frame["time"].map(time_to_minutes).astype(int)
    frame = frame.sort_values(["ticker", "date", "minutes"]).reset_index(drop=True)
    frame["pos_in_day"] = frame.groupby(["ticker", "date"], sort=False).cumcount()
    return frame


def build_signal_scoring_frame(
    data_path: str | Path,
    required_features: list[str],
    horizon_steps: int,
    tickers: list[str] | None,
    truncate_to_eod: bool,
) -> pd.DataFrame:
    import pyarrow.parquet as pq

    log("[OPTION_POLICY] reading parquet schema")
    parquet_cols = list(pq.ParquetFile(data_path).schema.names)
    wanted = ["ticker", "date", "time", "spot_price", *required_features, "xjepa_context_valid"]
    columns = []
    seen = set()
    for col in wanted:
        if col in parquet_cols and col not in seen:
            columns.append(col)
            seen.add(col)
    log(f"[OPTION_POLICY] reading scoring columns={len(columns)}")
    frame = pd.read_parquet(data_path, columns=columns)
    log(f"[OPTION_POLICY] scoring rows loaded={len(frame):,}")
    frame["ticker"] = frame["ticker"].map(normalize_ticker)
    frame["date"] = frame["date"].map(normalize_date)
    if tickers:
        allowed = {normalize_ticker(t) for t in tickers}
        frame = frame[frame["ticker"].isin(allowed)].copy()
    frame["minutes"] = frame["time"].map(time_to_minutes).astype(int)
    frame = frame.sort_values(["ticker", "date", "minutes"]).reset_index(drop=True)
    frame["pos_in_day"] = frame.groupby(["ticker", "date"], sort=False).cumcount()

    horizon_steps = int(horizon_steps)
    future_spot = np.full(len(frame), np.nan, dtype=np.float64)
    terminal_hold_steps = np.full(len(frame), np.nan, dtype=np.float64)
    terminal_exit_time = np.full(len(frame), "", dtype=object)
    for _, idx in frame.groupby(["ticker", "date"], sort=False).groups.items():
        positions = np.asarray(list(idx), dtype=np.int64)
        if len(positions) <= 1 or horizon_steps <= 0:
            continue
        spot = frame.loc[positions, "spot_price"].to_numpy(dtype=np.float64)
        if truncate_to_eod:
            for pos_i, abs_i in enumerate(positions):
                target_i = min(pos_i + horizon_steps, len(positions) - 1)
                if target_i <= pos_i:
                    continue
                future_spot[abs_i] = spot[target_i]
                terminal_hold_steps[abs_i] = float(target_i - pos_i)
                terminal_exit_time[abs_i] = str(frame.loc[positions[target_i], "time"])
        else:
            if len(positions) <= horizon_steps:
                continue
            future = np.full(len(positions), np.nan, dtype=np.float64)
            future[:-horizon_steps] = spot[horizon_steps:]
            future_spot[positions] = future
            terminal_hold_steps[positions[:-horizon_steps]] = float(horizon_steps)
            terminal_exit_time[positions[:-horizon_steps]] = frame.loc[positions[horizon_steps:], "time"].astype(str).to_numpy()

    spot_now = frame["spot_price"].to_numpy(dtype=np.float64)
    future_return = future_spot / spot_now - 1.0
    valid = np.isfinite(future_return) & np.isfinite(spot_now) & (spot_now > 0.0)
    if "xjepa_context_valid" in frame.columns:
        valid &= frame["xjepa_context_valid"].astype(float).to_numpy() > 0.0
    frame["future_spot_180m"] = future_spot
    frame["future_return_180m"] = future_return
    frame["future_return_bps_180m"] = future_return * 10000.0
    frame["future_up_180m"] = (future_return > 0.0).astype(np.int8)
    frame["future_abs_bps_180m"] = np.abs(frame["future_return_bps_180m"].astype(float))
    frame["terminal_hold_steps"] = terminal_hold_steps
    frame["terminal_hold_minutes"] = terminal_hold_steps * 5.0
    frame["terminal_exit_time"] = terminal_exit_time
    frame["terminal_horizon_truncated"] = terminal_hold_steps < float(horizon_steps)
    frame["month"] = frame["date"].str[:6]
    out = frame.loc[valid].reset_index(drop=True)
    log(f"[OPTION_POLICY] scoring rows valid={len(out):,}")
    return out


def build_signals(args, signal_model: Jepa180mSignalModel) -> tuple[pd.DataFrame, pd.DataFrame]:
    log("[OPTION_POLICY] building JEPA signal scoring frame")
    labeled = build_signal_scoring_frame(
        args.data,
        signal_model.required_features(),
        args.horizon_steps,
        args.tickers,
        bool(args.truncate_eod_horizon),
    )
    log("[OPTION_POLICY] running JEPA signal inference")
    predictions = signal_model.predict_frame(labeled)
    predictions["entry_minute"] = predictions["time"].map(time_to_minutes).astype(int)
    signals = predictions[predictions["jepa180_direction"].astype(int) != 0].copy()
    signals = apply_signal_cooldown(signals, int(round(args.cooldown_minutes / 5.0)))
    signals = signals.reset_index(drop=True)
    if args.train_start_date:
        signals = signals[signals["date"].astype(str) >= normalize_date(args.train_start_date)].reset_index(drop=True)
    if int(args.max_signals) > 0:
        signals = signals.head(int(args.max_signals)).reset_index(drop=True)
    signals["signal_id"] = np.arange(len(signals), dtype=np.int64)
    signals["side"] = np.where(signals["jepa180_direction"].astype(int) > 0, "LONG", "SHORT")

    log(f"[OPTION_POLICY] signals after cooldown/filter={len(signals):,}")
    log("[OPTION_POLICY] loading minimal path frame")
    path_frame = load_path_frame(args.data, min_date=args.train_start_date)
    log(f"[OPTION_POLICY] path rows loaded={len(path_frame):,}")
    return signals, path_frame


def entry_atm_iv(entry_slice: pd.DataFrame, spot: float) -> float:
    if entry_slice is None or entry_slice.empty:
        return 0.15
    idx = (entry_slice["strike"].astype(float) - float(spot)).abs().idxmin()
    return float(entry_slice.loc[idx].get("implied_vol", 0.15) or 0.15)


def option_path_for_candidate(
    future_rows: pd.DataFrame,
    premium_lookup: dict,
    greeks_lookup: dict,
    entry_spot: float,
    entry_minute: int,
    entry_premium: float,
    contracts: int,
    actual_strike: float,
    option_right: str,
    side: str,
    max_hold_minutes: int,
) -> list[dict]:
    path: list[dict] = []
    side_sign = 1.0 if side == "LONG" else -1.0
    peak = -np.inf
    mae = np.inf
    for row in future_rows.itertuples(index=False):
        future_time = str(row.time)
        hold_minutes = int(row.minutes) - int(entry_minute)
        if hold_minutes <= 0 or hold_minutes > int(max_hold_minutes):
            continue
        premium = _get_premium_at_time(premium_lookup, float(actual_strike), option_right, future_time)
        if premium is None or premium <= 0:
            continue
        pnl_pct = (float(premium) - float(entry_premium)) / float(entry_premium)
        pnl_pct = float(np.clip(pnl_pct, -1.0, 10.0))
        pnl_dollars = (float(premium) - float(entry_premium)) * 100.0 * int(contracts)
        right_upper = option_right.upper()
        alt_right = right_upper[0] if len(right_upper) > 1 else right_upper
        greeks = (
            greeks_lookup.get((future_time, float(actual_strike), right_upper))
            or greeks_lookup.get((future_time, float(actual_strike), alt_right))
            or {}
        )
        spot = float(greeks.get("spot", getattr(row, "spot_price", entry_spot)) or getattr(row, "spot_price", entry_spot))
        spot_return_bps = (spot / float(entry_spot) - 1.0) * 10000.0 if entry_spot > 0 else 0.0
        peak = max(peak, pnl_pct)
        mae = min(mae, pnl_pct)
        path.append(
            {
                "time": future_time,
                "hold_minutes": hold_minutes,
                "current_premium": float(premium),
                "current_pnl_pct": pnl_pct,
                "current_return_on_risk": float(pnl_dollars) / float(max(1e-9, contracts * entry_premium * 100.0)),
                "pnl_dollars": float(pnl_dollars),
                "current_delta": float(greeks.get("delta", 0.0)),
                "current_iv": float(greeks.get("iv", 0.15)),
                "current_gamma": float(greeks.get("gamma", 0.0)),
                "spot_price": spot,
                "spot_return_bps": float(spot_return_bps),
                "signed_spot_return_bps": float(side_sign * spot_return_bps),
                "peak_pnl_pct": float(peak),
                "mae_pnl_pct": float(mae),
            }
        )
    return path


def select_rule_exit(path: list[dict], hard_stop_pct: float, take_profit_pct: float) -> tuple[dict, str]:
    for point in path:
        pnl_pct = float(point["current_pnl_pct"])
        if pnl_pct <= float(hard_stop_pct):
            return point, "hard_stop"
        if pnl_pct >= float(take_profit_pct):
            return point, "hard_take_profit"
    return path[-1], "max_time"


def select_oracle_exit(path: list[dict]) -> tuple[dict, str]:
    best = max(path, key=lambda x: float(x["pnl_dollars"]))
    return best, "oracle_best_exit"


def add_static_candidate_features(record: dict, row: pd.Series, ticker: str, side: str, chain: dict, entry_premium: float) -> None:
    spot = float(row.get("spot_price", 0.0) or 0.0)
    strike = float(chain["strike"])
    actual_delta = float(chain.get("delta", 0.0))
    actual_iv = float(chain.get("iv", 0.15))
    actual_theta = float(chain.get("theta", 0.0))
    actual_gamma = float(chain.get("gamma", 0.0))
    raw_entry_premium = float(chain["mid_price"])
    record.update(
        {
            "ticker_SPX": 1.0 if ticker == "SPX" else 0.0,
            "ticker_QQQ": 1.0 if ticker == "QQQ" else 0.0,
            "ticker_SPY": 1.0 if ticker == "SPY" else 0.0,
            "side_LONG": 1.0 if side == "LONG" else 0.0,
            "side_SHORT": 1.0 if side == "SHORT" else 0.0,
            "jepa180_prob_up": float(row.get("jepa180_prob_up", np.nan)),
            "jepa180_confidence": float(row.get("jepa180_confidence", np.nan)),
            "jepa180_direction": float(row.get("jepa180_direction", 0.0)),
            "jepa180_edge": abs(float(row.get("jepa180_prob_up", 0.5)) - 0.5),
            "entry_minute": float(row.get("entry_minute", time_to_minutes(row.get("time", "09:30")))),
            "pos_in_day": float(row.get("pos_in_day", 0.0)),
            "minutes_to_close": float(max(0, 960 - int(row.get("entry_minute", 570)))),
            "actual_delta": actual_delta,
            "actual_delta_abs": abs(actual_delta),
            "entry_premium": float(entry_premium),
            "raw_entry_premium": raw_entry_premium,
            "premium_to_spot_bps": (float(entry_premium) / spot * 10000.0) if spot > 0 else 0.0,
            "strike_distance_pts": strike - spot,
            "strike_distance_bps": ((strike - spot) / spot * 10000.0) if spot > 0 else 0.0,
            "actual_iv": actual_iv,
            "actual_theta": actual_theta,
            "actual_gamma": actual_gamma,
            "theta_over_premium": actual_theta / float(entry_premium) if entry_premium > 0 else 0.0,
            "gamma_notional": actual_gamma * spot * 0.01 if spot > 0 else 0.0,
        }
    )


def build_option_labels(
    signals: pd.DataFrame,
    path_frame: pd.DataFrame,
    base_features: list[str],
    args,
) -> tuple[pd.DataFrame, dict[int, list[dict]]]:
    path_groups = {
        key: group.sort_values("minutes").reset_index(drop=True)
        for key, group in path_frame.groupby(["ticker", "date"], sort=False)
    }
    greeks_cache: dict[tuple[str, str], tuple] = {}
    records: list[dict] = []
    paths: dict[int, list[dict]] = {}
    candidate_id = 0
    start = time.time()
    log(
        f"[OPTION_LABELS] START signals={len(signals):,} delta_targets={len(args.delta_targets):,} "
        f"max_hold_minutes={int(args.max_hold_minutes)} progress_every={int(args.progress_every)}"
    )

    for n, row in enumerate(signals.itertuples(index=False), start=1):
        row_s = pd.Series(row._asdict())
        ticker = normalize_ticker(row_s["ticker"])
        date = normalize_date(row_s["date"])
        side = str(row_s["side"])
        entry_time = str(row_s["time"])
        entry_minute = int(row_s.get("entry_minute", time_to_minutes(entry_time)))
        entry_spot = float(row_s.get("spot_price", 0.0) or 0.0)
        day_rows = path_groups.get((ticker, date))
        if day_rows is None or day_rows.empty:
            continue
        future_rows = day_rows[
            (day_rows["minutes"].astype(int) > entry_minute)
            & (day_rows["minutes"].astype(int) <= entry_minute + int(args.max_hold_minutes))
        ].copy()
        if future_rows.empty:
            continue

        cache_key = (ticker, date)
        if cache_key not in greeks_cache:
            greeks_cache[cache_key] = _load_daily_greeks(date, ticker)
            if len(greeks_cache) > int(args.greeks_cache_size):
                oldest = next(iter(greeks_cache))
                del greeks_cache[oldest]
        df_greeks, premium_lookup, greeks_lookup = greeks_cache[cache_key]
        if df_greeks is None or premium_lookup is None or greeks_lookup is None:
            continue
        entry_slice = df_greeks[df_greeks["time_str"] == entry_time]
        if entry_slice.empty:
            continue
        _ = entry_atm_iv(entry_slice, entry_spot)

        for delta_target in args.delta_targets:
            chain = _find_strike_by_delta(entry_slice, side, float(delta_target))
            if chain is None:
                continue
            raw_entry_premium = float(chain["mid_price"])
            if raw_entry_premium <= 0.0:
                continue
            spread = get_half_spread(abs(float(chain.get("delta", delta_target))))
            gamma_speed = float(row_s.get("gamma_speed", 0.0) or 0.0)
            effective_spread = spread * (1.0 + 0.5 * abs(gamma_speed))
            entry_premium = raw_entry_premium * (1.0 + effective_spread)
            contracts = calc_contracts(args.risk_capital, entry_premium)
            path = option_path_for_candidate(
                future_rows,
                premium_lookup,
                greeks_lookup,
                entry_spot,
                entry_minute,
                entry_premium,
                contracts,
                float(chain["strike"]),
                str(chain["right"]),
                side,
                int(args.max_hold_minutes),
            )
            if not path:
                continue

            rule_exit, rule_reason = select_rule_exit(path, args.hard_stop_pct, args.take_profit_pct)
            oracle_exit, oracle_reason = select_oracle_exit(path)
            hold_exit = path[-1]
            record = {
                "candidate_id": int(candidate_id),
                "signal_id": int(row_s["signal_id"]),
                "ticker": ticker,
                "date": date,
                "month": month_key(date),
                "time": entry_time,
                "side": side,
                "spot_price": entry_spot,
                "delta_target": float(delta_target),
                "actual_strike": float(chain["strike"]),
                "contracts": int(contracts),
                "entry_cost_dollars": float(entry_premium) * 100.0 * int(contracts),
                "rule_exit_reason": rule_reason,
                "rule_exit_time": rule_exit["time"],
                "rule_hold_minutes": int(rule_exit["hold_minutes"]),
                "rule_pnl_pct": float(rule_exit["current_pnl_pct"]),
                "rule_pnl_dollars": float(rule_exit["pnl_dollars"]),
                "rule_return_on_risk": float(rule_exit["pnl_dollars"]) / float(max(args.risk_capital, 1e-9)),
                "hold180_exit_time": hold_exit["time"],
                "hold180_hold_minutes": int(hold_exit["hold_minutes"]),
                "hold180_pnl_pct": float(hold_exit["current_pnl_pct"]),
                "hold180_pnl_dollars": float(hold_exit["pnl_dollars"]),
                "hold180_return_on_risk": float(hold_exit["pnl_dollars"]) / float(max(args.risk_capital, 1e-9)),
                "oracle_exit_reason": oracle_reason,
                "oracle_exit_time": oracle_exit["time"],
                "oracle_hold_minutes": int(oracle_exit["hold_minutes"]),
                "oracle_pnl_pct": float(oracle_exit["current_pnl_pct"]),
                "oracle_pnl_dollars": float(oracle_exit["pnl_dollars"]),
                "oracle_return_on_risk": float(oracle_exit["pnl_dollars"]) / float(max(args.risk_capital, 1e-9)),
                "path_points": int(len(path)),
            }
            add_static_candidate_features(record, row_s, ticker, side, chain, entry_premium)
            record["entry_spread_pct"] = float(effective_spread)
            for feature in base_features:
                if feature in row_s.index:
                    record[feature] = row_s.get(feature, np.nan)
            records.append(record)
            paths[candidate_id] = path
            candidate_id += 1

        if n % int(args.progress_every) == 0:
            elapsed = time.time() - start
            log(
                f"[OPTION_LABELS] signals={n}/{len(signals)} candidates={len(records)} "
                f"cache={len(greeks_cache)} elapsed={elapsed:.1f}s"
            )

    candidates = pd.DataFrame(records)
    log(
        f"[OPTION_LABELS] DONE signals={len(signals):,} candidates={len(candidates):,} "
        f"paths={len(paths):,} elapsed={time.time() - start:.1f}s"
    )
    return candidates, paths


def trade_metrics(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {
            "trades": 0,
            "win_rate": float("nan"),
            "profit_factor": float("nan"),
            "pnl_dollars": 0.0,
            "max_drawdown": 0.0,
            "avg_pnl": float("nan"),
            "avg_hold_minutes": float("nan"),
            "long_rate": float("nan"),
            "avg_delta_abs": float("nan"),
        }
    pnl = trades["pnl_dollars"].astype(float).to_numpy()
    wins = pnl[pnl > 0.0]
    losses = pnl[pnl < 0.0]
    equity = np.cumsum(pnl)
    peak = np.maximum.accumulate(np.insert(equity, 0, 0.0))[1:]
    drawdown = equity - peak
    gross_profit = float(wins.sum()) if len(wins) else 0.0
    gross_loss = float(-losses.sum()) if len(losses) else 0.0
    return {
        "trades": int(len(trades)),
        "win_rate": float((pnl > 0.0).mean()),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss > 0.0 else float("inf"),
        "pnl_dollars": float(pnl.sum()),
        "max_drawdown": float(drawdown.min()) if len(drawdown) else 0.0,
        "avg_pnl": float(pnl.mean()),
        "avg_hold_minutes": float(trades["hold_minutes"].astype(float).mean()) if "hold_minutes" in trades else float("nan"),
        "long_rate": float((trades["side"].astype(str) == "LONG").mean()) if "side" in trades else float("nan"),
        "avg_delta_abs": float(trades["actual_delta_abs"].astype(float).mean()) if "actual_delta_abs" in trades else float("nan"),
    }


def score_metrics(metrics: dict, min_trades: int) -> float:
    trades = int(metrics.get("trades", 0))
    pnl = float(metrics.get("pnl_dollars", 0.0))
    pf = float(metrics.get("profit_factor", 0.0))
    dd = abs(float(metrics.get("max_drawdown", 0.0)))
    if trades < int(min_trades) or pnl <= 0.0 or not np.isfinite(pf):
        return -1e9 + pnl
    return pf * math.log1p(trades) + pnl / 10000.0 - dd / 20000.0


def candidate_trades_from_selection(selected: pd.DataFrame, prefix: str, policy_name: str) -> pd.DataFrame:
    if selected.empty:
        return pd.DataFrame()
    return pd.DataFrame(
        {
            "policy": policy_name,
            "candidate_id": selected["candidate_id"].astype(int),
            "signal_id": selected["signal_id"].astype(int),
            "ticker": selected["ticker"].astype(str),
            "date": selected["date"].astype(str),
            "time": selected["time"].astype(str),
            "side": selected["side"].astype(str),
            "delta_target": selected["delta_target"].astype(float),
            "actual_delta_abs": selected["actual_delta_abs"].astype(float),
            "actual_strike": selected["actual_strike"].astype(float),
            "entry_premium": selected["entry_premium"].astype(float),
            "contracts": selected["contracts"].astype(int),
            "exit_reason": selected[f"{prefix}_exit_reason"].astype(str) if f"{prefix}_exit_reason" in selected else prefix,
            "exit_time": selected[f"{prefix}_exit_time"].astype(str),
            "hold_minutes": selected[f"{prefix}_hold_minutes"].astype(int),
            "pnl_pct": selected[f"{prefix}_pnl_pct"].astype(float),
            "pnl_dollars": selected[f"{prefix}_pnl_dollars"].astype(float),
        }
    )


def select_best_by_prediction(candidates: pd.DataFrame, pred: np.ndarray, threshold: float) -> pd.DataFrame:
    work = candidates.copy()
    work["_pred_utility"] = pred
    best = work.sort_values(["signal_id", "_pred_utility"]).groupby("signal_id", sort=False).tail(1)
    best = best[best["_pred_utility"].astype(float) >= float(threshold)].copy()
    return best.sort_values(["ticker", "date", "time"]).reset_index(drop=True)


def choose_entry_threshold(
    candidates: pd.DataFrame,
    pred: np.ndarray,
    min_trades: int,
) -> tuple[float, pd.DataFrame, dict]:
    finite_pred = np.asarray(pred, dtype=np.float64)
    finite_pred = finite_pred[np.isfinite(finite_pred)]
    if len(finite_pred) == 0:
        return -1e9, pd.DataFrame(), {}
    quantiles = np.quantile(finite_pred, [0.0, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90])
    grid = sorted(set([-1e9, -0.50, -0.25, -0.10, 0.0, 0.05, 0.10, 0.20, 0.30, *[float(x) for x in quantiles]]))
    rows = []
    best_score = -1e18
    best_threshold = -1e9
    best_trades = pd.DataFrame()
    for threshold in grid:
        selected = select_best_by_prediction(candidates, pred, threshold)
        trades = candidate_trades_from_selection(selected, "rule", "validation_entry_hard")
        metrics = trade_metrics(trades)
        score = score_metrics(metrics, min_trades)
        rows.append({"threshold": threshold, "score": score, **metrics})
        if score > best_score:
            best_score = score
            best_threshold = threshold
            best_trades = trades
    return float(best_threshold), best_trades, {"grid": rows}


def build_exit_state_record(
    candidate: pd.Series,
    point: dict,
    path_so_far: list[dict],
    max_hold_minutes: int,
    entry_features: list[str],
) -> dict:
    hold = float(point["hold_minutes"])
    current_pnl = float(point["current_pnl_pct"])
    peak = max(float(p["current_pnl_pct"]) for p in path_so_far)
    mae = min(float(p["current_pnl_pct"]) for p in path_so_far)
    record = {feature: candidate.get(feature, np.nan) for feature in entry_features}
    record.update(
        {
            "hold_minutes": hold,
            "hold_norm": hold / float(max_hold_minutes),
            "current_pnl_pct": current_pnl,
            "current_return_on_risk": float(point["pnl_dollars"]) / float(max(float(candidate.get("entry_cost_dollars", 1.0)), 1e-9)),
            "current_premium": float(point["current_premium"]),
            "premium_ratio": float(point["current_premium"]) / float(max(candidate.get("entry_premium", 1.0), 1e-9)),
            "peak_pnl_pct": peak,
            "drawdown_from_peak": max(0.0, peak - current_pnl),
            "mae_pnl_pct": mae,
            "current_delta": float(point.get("current_delta", 0.0)),
            "current_delta_abs": abs(float(point.get("current_delta", 0.0))),
            "current_iv": float(point.get("current_iv", 0.15)),
            "current_gamma": float(point.get("current_gamma", 0.0)),
            "spot_return_bps": float(point.get("spot_return_bps", 0.0)),
            "signed_spot_return_bps": float(point.get("signed_spot_return_bps", 0.0)),
            "minutes_remaining": float(max(0.0, max_hold_minutes - hold)),
        }
    )
    return record


def build_exit_training_rows(
    candidates: pd.DataFrame,
    paths: dict[int, list[dict]],
    entry_features: list[str],
    max_hold_minutes: int,
    risk_capital: float,
) -> pd.DataFrame:
    rows: list[dict] = []
    indexed = candidates.set_index("candidate_id", drop=False)
    total_paths = len(paths)
    start = time.time()
    last_log = start
    matched_paths = 0
    log(
        f"[OPTION_POLICY] START build exit training rows candidates={len(candidates):,} "
        f"paths={total_paths:,} entry_features={len(entry_features):,}"
    )
    for n, (candidate_id, path) in enumerate(paths.items(), start=1):
        if candidate_id not in indexed.index or not path:
            now = time.time()
            if total_paths and (n % 5000 == 0 or now - last_log >= LOG_HEARTBEAT_SECONDS):
                log(
                    f"[OPTION_POLICY] STILL build exit training rows paths={n:,}/{total_paths:,} "
                    f"matched={matched_paths:,} rows={len(rows):,} elapsed={now - start:.1f}s"
                )
                last_log = now
            continue
        candidate = indexed.loc[candidate_id]
        matched_paths += 1
        future_best = np.maximum.accumulate([float(p["pnl_dollars"]) for p in reversed(path)])[::-1]
        path_so_far: list[dict] = []
        for idx, point in enumerate(path):
            path_so_far.append(point)
            record = build_exit_state_record(candidate, point, path_so_far, max_hold_minutes, entry_features)
            record["future_best_return_on_risk"] = float(future_best[idx]) / float(max(risk_capital, 1e-9))
            rows.append(record)
        now = time.time()
        if total_paths and (n % 5000 == 0 or now - last_log >= LOG_HEARTBEAT_SECONDS):
            log(
                f"[OPTION_POLICY] STILL build exit training rows paths={n:,}/{total_paths:,} "
                f"matched={matched_paths:,} rows={len(rows):,} elapsed={now - start:.1f}s"
            )
            last_log = now
    log(
        f"[OPTION_POLICY] DONE build exit training rows paths={total_paths:,} matched={matched_paths:,} "
        f"rows={len(rows):,} elapsed={time.time() - start:.1f}s"
    )
    return pd.DataFrame(rows)


def simulate_learned_exit_for_selected(
    selected: pd.DataFrame,
    paths: dict[int, list[dict]],
    exit_model,
    exit_features: list[str],
    exit_medians: pd.Series,
    entry_features: list[str],
    args,
    policy_name: str,
    exit_margin: float,
) -> pd.DataFrame:
    trades: list[dict] = []
    indexed = selected.set_index("candidate_id", drop=False)
    total = len(indexed)
    start = time.time()
    last_log = start
    log(f"[OPTION_POLICY] START simulate learned exits policy={policy_name} selected={total:,} margin={float(exit_margin):.4f}")
    for n, (candidate_id, candidate) in enumerate(indexed.iterrows(), start=1):
        path = paths.get(int(candidate_id), [])
        if not path:
            now = time.time()
            if total and (n % 250 == 0 or now - last_log >= LOG_HEARTBEAT_SECONDS):
                log(
                    f"[OPTION_POLICY] STILL simulate learned exits policy={policy_name} "
                    f"selected={n:,}/{total:,} trades={len(trades):,} elapsed={now - start:.1f}s"
                )
                last_log = now
            continue
        path_so_far: list[dict] = []
        exit_point = path[-1]
        exit_reason = "max_time"
        for point in path:
            path_so_far.append(point)
            pnl_pct = float(point["current_pnl_pct"])
            if pnl_pct <= float(args.hard_stop_pct):
                exit_point = point
                exit_reason = "hard_stop"
                break
            if pnl_pct >= float(args.take_profit_pct):
                exit_point = point
                exit_reason = "hard_take_profit"
                break
            if int(point["hold_minutes"]) < int(args.min_exit_hold_minutes):
                continue
            state = build_exit_state_record(candidate, point, path_so_far, int(args.max_hold_minutes), entry_features)
            state_frame = pd.DataFrame([state])
            predicted_future = float(predict_regressor(exit_model, state_frame, exit_features, exit_medians)[0])
            current_return = float(point["pnl_dollars"]) / float(max(args.risk_capital, 1e-9))
            if predicted_future <= current_return + float(exit_margin):
                exit_point = point
                exit_reason = "learned_exit"
                break
        trades.append(
            {
                "policy": policy_name,
                "candidate_id": int(candidate["candidate_id"]),
                "signal_id": int(candidate["signal_id"]),
                "ticker": str(candidate["ticker"]),
                "date": str(candidate["date"]),
                "time": str(candidate["time"]),
                "side": str(candidate["side"]),
                "delta_target": float(candidate["delta_target"]),
                "actual_delta_abs": float(candidate["actual_delta_abs"]),
                "actual_strike": float(candidate["actual_strike"]),
                "entry_premium": float(candidate["entry_premium"]),
                "contracts": int(candidate["contracts"]),
                "exit_reason": exit_reason,
                "exit_time": str(exit_point["time"]),
                "hold_minutes": int(exit_point["hold_minutes"]),
                "pnl_pct": float(exit_point["current_pnl_pct"]),
                "pnl_dollars": float(exit_point["pnl_dollars"]),
                "pred_utility": float(candidate.get("_pred_utility", np.nan)),
            }
        )
        now = time.time()
        if total and (n % 250 == 0 or now - last_log >= LOG_HEARTBEAT_SECONDS):
            log(
                f"[OPTION_POLICY] STILL simulate learned exits policy={policy_name} "
                f"selected={n:,}/{total:,} trades={len(trades):,} elapsed={now - start:.1f}s"
            )
            last_log = now
    log(
        f"[OPTION_POLICY] DONE simulate learned exits policy={policy_name} selected={total:,} "
        f"trades={len(trades):,} elapsed={time.time() - start:.1f}s"
    )
    return pd.DataFrame(trades)


def choose_exit_margin(
    selected_val: pd.DataFrame,
    paths: dict[int, list[dict]],
    exit_model,
    exit_features: list[str],
    exit_medians: pd.Series,
    entry_features: list[str],
    args,
    min_trades: int,
) -> tuple[float, dict]:
    grid = [-0.20, -0.10, -0.05, 0.0, 0.05, 0.10, 0.20]
    best_score = -1e18
    best_margin = 0.0
    rows = []
    log(f"[OPTION_POLICY] START choose exit margin selected_val={len(selected_val):,} grid={grid}")
    for margin in grid:
        trades = simulate_learned_exit_for_selected(
            selected_val,
            paths,
            exit_model,
            exit_features,
            exit_medians,
            entry_features,
            args,
            "validation_learned_exit",
            margin,
        )
        metrics = trade_metrics(trades)
        score = score_metrics(metrics, min_trades)
        rows.append({"exit_margin": margin, "score": score, **metrics})
        log(
            f"[OPTION_POLICY] exit_margin={margin:.4f} trades={metrics.get('trades', 0)} "
            f"wr={metrics.get('win_rate', float('nan')):.4f} pf={metrics.get('profit_factor', float('nan')):.4f} "
            f"pnl={metrics.get('pnl_dollars', 0.0):.2f} score={score:.4f}"
        )
        if score > best_score:
            best_score = score
            best_margin = margin
    log(f"[OPTION_POLICY] DONE choose exit margin best_margin={best_margin:.4f} best_score={best_score:.4f}")
    return float(best_margin), {"grid": rows}


def fixed_delta_policy(candidates: pd.DataFrame, delta_target: float, prefix: str, policy_name: str) -> pd.DataFrame:
    if candidates.empty:
        return pd.DataFrame()
    work = candidates.copy()
    work["_delta_diff"] = (work["delta_target"].astype(float) - float(delta_target)).abs()
    selected = work.sort_values(["signal_id", "_delta_diff"]).groupby("signal_id", sort=False).head(1)
    return candidate_trades_from_selection(selected, prefix, policy_name)


def choose_validation_best_delta(
    val_candidates: pd.DataFrame,
    delta_targets: list[float],
    min_trades: int,
) -> tuple[float, list[dict]]:
    rows = []
    best_delta = float(delta_targets[0])
    best_score = -1e18
    for delta in delta_targets:
        trades = fixed_delta_policy(val_candidates, float(delta), "rule", f"validation_fixed_delta_{delta:.2f}")
        metrics = trade_metrics(trades)
        score = score_metrics(metrics, min_trades=min_trades)
        rows.append({"delta_target": float(delta), "score": score, **metrics})
        if score > best_score:
            best_score = score
            best_delta = float(delta)
    return best_delta, rows


def oracle_policy(candidates: pd.DataFrame, value_col: str, prefix: str, policy_name: str) -> pd.DataFrame:
    if candidates.empty:
        return pd.DataFrame()
    selected = candidates.sort_values(["signal_id", value_col]).groupby("signal_id", sort=False).tail(1)
    return candidate_trades_from_selection(selected, prefix, policy_name)


def summarize_by_ticker(trades: pd.DataFrame) -> dict[str, dict]:
    if trades.empty:
        return {}
    return {str(ticker): trade_metrics(frame) for ticker, frame in trades.groupby("ticker", sort=True)}


def metrics_row(label: str, metrics: dict) -> str:
    return (
        f"| {label} | {metrics.get('trades', 0)} | {fmt_pct(metrics.get('win_rate', float('nan')))} | "
        f"{fmt_float(metrics.get('profit_factor', float('nan')))} | "
        f"{fmt_money(metrics.get('pnl_dollars', 0.0))} | "
        f"{fmt_money(metrics.get('max_drawdown', 0.0))} | "
        f"{fmt_money(metrics.get('avg_pnl', 0.0))} | "
        f"{fmt_float(metrics.get('avg_hold_minutes', float('nan')), 1)} | "
        f"{fmt_float(metrics.get('avg_delta_abs', float('nan')), 3)} |"
    )


def write_summary(
    output_dir: Path,
    args,
    config: dict,
    signals: pd.DataFrame,
    candidates: pd.DataFrame,
    policy_results: dict[str, dict],
    validation: dict,
) -> None:
    train_signals = signals[signals["date"].astype(str) <= normalize_date(args.train_end_date)]
    test_signals = signals[signals["date"].astype(str) >= normalize_date(args.test_start_date)]
    lines = [
        "# JEPA Supervised 0DTE Option Policy",
        "",
        f"Data: `{args.data}`",
        f"Signal model: `{args.signal_model_dir}` / mode `{args.signal_mode}`",
        f"Train cutoff: `{normalize_date(args.train_end_date)}`",
        f"Test start: `{normalize_date(args.test_start_date)}`",
        f"Signals after `{args.cooldown_minutes}`m cooldown: {len(signals):,} total, {len(train_signals):,} train, {len(test_signals):,} test.",
        f"Option candidates with valid real premium paths: {len(candidates):,}.",
        f"Candidate deltas: `{', '.join(str(x) for x in args.delta_targets)}`.",
        f"Execution: buy 0DTE option, risk capital `${args.risk_capital:,.0f}`, max hold `{args.max_hold_minutes}`m, hard stop `{args.hard_stop_pct:.0%}`, take profit `{args.take_profit_pct:.0%}`.",
        "",
        "## Policies Tested",
        "",
        "- `fixed_delta_0.60_hard` / `fixed_delta_0.70_hard`: use every JEPA signal, buy the closest fixed-delta contract, exit with hard stop/take-profit/max-time.",
        "- `validation_best_delta_hard`: choose the fixed delta from the pre-OOS validation months, then use every OOS JEPA signal.",
        "- `learned_delta_regression_all_hard`: LightGBM predicts candidate option utility, chooses the best delta per signal, never skips a JEPA entry.",
        "- `learned_delta_ranker_all_hard`: LightGBM ranker chooses the best delta per signal, never skips a JEPA entry.",
        "- `supervised_entry_strike_skip_hard`: older LightGBM entry/strike policy with a validation threshold that can skip weak entries.",
        "- `supervised_entry_strike_learned_exit`: same skip-gated entry/strike model plus a supervised continuation-value exit model, only available when option paths are rebuilt in the same run.",
        "- `oracle_best_delta_hard`: non-deployable upper bound that chooses the best delta after seeing the future under hard exits.",
        "- `oracle_best_delta_oracle_exit`: non-deployable upper bound that chooses best delta and best future exit.",
        "",
        "## OOS Results",
        "",
        "| Policy | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for policy, payload in policy_results.items():
        lines.append(metrics_row(policy, payload["overall"]))

    lines += [
        "",
        "## Per-Ticker OOS Results",
        "",
    ]
    for policy, payload in policy_results.items():
        lines += [
            f"### {policy}",
            "",
            "| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for ticker, metrics in payload["per_ticker"].items():
            lines.append(metrics_row(ticker, metrics))
        lines.append("")

    lines += [
        "## Validation Choices",
        "",
        f"- Fixed delta selected on pre-OOS validation: `{fmt_float(validation.get('best_fixed_delta', float('nan')), 2)}`.",
        f"- Entry utility threshold selected on pre-OOS validation: `{fmt_float(validation.get('entry_threshold', float('nan')), 4)}`.",
        f"- Learned-exit margin selected on pre-OOS validation: `{fmt_float(validation.get('exit_margin', float('nan')), 4)}`.",
        "",
        "## Interpretation",
        "",
        "- This is a frozen OOS test: option-policy models are trained through the configured cutoff and scored from the configured test start onward.",
        "- Future option paths are used only to create supervised labels and to score the backtest, not as model inputs.",
        "- The test is stricter than the previous spot proxy because it uses real 0DTE option premium paths and spread-adjusted entries.",
        f"- The current deployable validated policy is `validation_best_delta_{validation.get('best_fixed_delta', float('nan')):.2f}_hard` unless a learned selector beats it on rolling walk-forward validation.",
        "- The oracle rows are ceilings, not deployable strategies. They diagnose the remaining strike/delta and exit-selection gap.",
        "",
    ]
    monthly_cv_path = output_dir / "monthly_cv_policy_grid.csv"
    if monthly_cv_path.exists():
        try:
            cv_frame = pd.read_csv(monthly_cv_path).head(12)
            lines += [
                "## Monthly Walk-Forward Validation",
                "",
                "File: `monthly_cv_policy_grid.csv`",
                "",
                "This validation uses only months before the configured OOS start. For each validation month, models are trained on prior months and scored on the next month.",
                "",
                "| Policy | Trades | WR | PF | PnL | Max DD | Avg Delta |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
            for _, row in cv_frame.iterrows():
                lines.append(
                    f"| {row.get('policy', '')} | {int(row.get('trades', 0))} | "
                    f"{fmt_pct(float(row.get('win_rate', float('nan'))))} | "
                    f"{fmt_float(float(row.get('profit_factor', float('nan'))))} | "
                    f"{fmt_money(float(row.get('pnl_dollars', 0.0)))} | "
                    f"{fmt_money(float(row.get('max_drawdown', 0.0)))} | "
                    f"{fmt_float(float(row.get('avg_delta_abs', float('nan'))), 3)} |"
                )
            lines += [
                "",
                "Decision: fixed 0.70 is the current robust deployable delta policy. Learned delta selectors remain research candidates.",
                "",
            ]
        except Exception as exc:
            lines += [f"Monthly CV summary unavailable: `{exc}`.", ""]
    lines += [
        "## Config",
        "",
        "```json",
        json.dumps(config, indent=2, allow_nan=True),
        "```",
        "",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def save_policy_outputs(output_dir: Path, policy_results: dict[str, dict]) -> None:
    for policy, payload in policy_results.items():
        trades = payload["trades"]
        trades.to_csv(output_dir / f"{policy}_trades.csv", index=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Train and backtest a supervised JEPA 0DTE option policy.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--signal-model-dir", required=True)
    parser.add_argument("--signal-mode", default="base_jepa")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPX", "QQQ", "SPY"])
    parser.add_argument("--train-start-date", default="20250101")
    parser.add_argument("--train-end-date", default="20260331")
    parser.add_argument("--test-start-date", default="20260401")
    parser.add_argument("--horizon-steps", type=int, default=36)
    parser.add_argument("--cooldown-minutes", type=int, default=180)
    parser.add_argument("--max-hold-minutes", type=int, default=180)
    parser.add_argument("--risk-capital", type=float, default=1000.0)
    parser.add_argument("--hard-stop-pct", type=float, default=-0.60)
    parser.add_argument("--take-profit-pct", type=float, default=2.50)
    parser.add_argument("--min-exit-hold-minutes", type=int, default=15)
    parser.add_argument(
        "--truncate-eod-horizon",
        action="store_true",
        help="Keep late JEPA signals by scoring terminal direction at min(entry + horizon, last same-day row).",
    )
    parser.add_argument("--delta-targets", nargs="+", type=float, default=[0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70])
    parser.add_argument("--val-months", type=int, default=3)
    parser.add_argument("--min-val-trades", type=int, default=12)
    parser.add_argument("--n-estimators", type=int, default=260)
    parser.add_argument("--exit-n-estimators", type=int, default=220)
    parser.add_argument("--seed", type=int, default=991)
    parser.add_argument("--n-jobs", type=int, default=20)
    parser.add_argument("--greeks-cache-size", type=int, default=50)
    parser.add_argument("--progress-every", type=int, default=100)
    parser.add_argument("--max-signals", type=int, default=0)
    parser.add_argument("--reuse-candidates", action="store_true", help="Reuse output_dir/candidate_labels.parquet instead of rebuilding option labels.")
    parser.add_argument("--labels-only", action="store_true", help="Build candidate_labels.parquet and exit without OOS model training.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    model_dir = Path(args.model_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)
    global LOG_PATH
    LOG_PATH = output_dir / "run.log"
    if LOG_PATH.exists():
        LOG_PATH.unlink()

    log(
        f"[OPTION_POLICY] config data={args.data} output_dir={output_dir} model_dir={model_dir} "
        f"train={normalize_date(args.train_start_date)}..{normalize_date(args.train_end_date)} "
        f"test_start={normalize_date(args.test_start_date)} n_jobs={int(args.n_jobs)} "
        f"heartbeat={LOG_HEARTBEAT_SECONDS}s reuse_candidates={bool(args.reuse_candidates)}"
    )
    log("[OPTION_POLICY] loading signal model")
    signal_model = Jepa180mSignalModel(args.signal_model_dir, args.signal_mode, tickers=args.tickers)
    base_features = [
        f
        for f in signal_model.required_features()
        if f not in LEAKAGE_COLUMNS
    ]
    log(f"[OPTION_POLICY] signal base_features={len(base_features):,}")
    candidate_path = output_dir / "candidate_labels.parquet"
    signal_path = output_dir / "signals.csv"
    if args.reuse_candidates and candidate_path.exists():
        log(f"[OPTION_POLICY] reusing candidate labels from {candidate_path}")
        candidates = pd.read_parquet(candidate_path)
        if signal_path.exists():
            signals = pd.read_csv(signal_path)
        else:
            signal_cols = [c for c in ["signal_id", "ticker", "date", "time", "pos_in_day", "side"] if c in candidates.columns]
            signals = candidates[signal_cols].drop_duplicates("signal_id").copy() if "signal_id" in signal_cols else pd.DataFrame()
        paths = {}
        log(f"[OPTION_POLICY] reused candidates={len(candidates):,} signals={len(signals):,}; learned-exit paths unavailable")
    else:
        if args.reuse_candidates:
            log(f"[OPTION_POLICY] candidate labels not found at {candidate_path}; rebuilding labels")
        signals, path_frame = build_signals(args, signal_model)
        log(
            f"[OPTION_POLICY] signals_total={len(signals)} train={(signals['date'].astype(str) <= normalize_date(args.train_end_date)).sum()} "
            f"test={(signals['date'].astype(str) >= normalize_date(args.test_start_date)).sum()}"
        )
        candidates, paths = build_option_labels(signals, path_frame, base_features, args)
    if candidates.empty:
        raise RuntimeError("No valid option candidates were built.")

    if "date" in candidates.columns:
        candidates["date"] = candidates["date"].astype(str).map(normalize_date)
    if "date" in signals.columns:
        signals["date"] = signals["date"].astype(str).map(normalize_date)
    if "month" not in candidates.columns:
        candidates["month"] = candidates["date"].astype(str).str.slice(0, 6)

    if not (args.reuse_candidates and candidate_path.exists()):
        with logged_phase(f"write candidate artifacts candidates={len(candidates):,} signals={len(signals):,}"):
            candidates.to_parquet(candidate_path, index=False)
            signals.to_csv(signal_path, index=False)
    if args.labels_only:
        metadata = {
            "config": vars(args),
            "base_feature_count": len(base_features),
            "signals": int(len(signals)),
            "candidates": int(len(candidates)),
            "candidate_labels": str(candidate_path),
            "signal_path": str(signal_path),
        }
        (output_dir / "metrics.json").write_text(json.dumps(metadata, indent=2, allow_nan=True), encoding="utf-8")
        log(
            f"[OPTION_POLICY] labels_only complete signals={len(signals):,} "
            f"candidates={len(candidates):,} output={candidate_path}"
        )
        return 0

    train_end = normalize_date(args.train_end_date)
    test_start = normalize_date(args.test_start_date)
    train_candidates = candidates[candidates["date"].astype(str) <= train_end].copy()
    test_candidates = candidates[candidates["date"].astype(str) >= test_start].copy()
    if train_candidates.empty or test_candidates.empty:
        raise RuntimeError("Train/test split produced no candidate rows.")

    train_months = sorted(train_candidates["month"].astype(str).unique().tolist())
    val_months = set(train_months[-int(args.val_months):]) if train_months else set()
    fit_candidates = train_candidates[~train_candidates["month"].isin(val_months)].copy()
    val_candidates = train_candidates[train_candidates["month"].isin(val_months)].copy()
    if fit_candidates.empty or val_candidates.empty:
        fit_candidates = train_candidates.copy()
        val_candidates = train_candidates.copy()
    log(
        f"[OPTION_POLICY] split train_candidates={len(train_candidates):,} fit={len(fit_candidates):,} "
        f"val={len(val_candidates):,} test_candidates={len(test_candidates):,} "
        f"val_months={','.join(sorted(val_months))}"
    )

    entry_features = [f for f in base_features if f in candidates.columns and f not in LEAKAGE_COLUMNS]
    entry_features += [f for f in OPTION_FEATURES if f in candidates.columns and f not in entry_features]
    entry_features = [f for f in entry_features if pd.api.types.is_numeric_dtype(candidates[f])]
    log(f"[OPTION_POLICY] entry_features={len(entry_features):,} option_features={len([f for f in OPTION_FEATURES if f in entry_features]):,}")

    entry_model_fit, entry_medians_fit = train_regressor(
        fit_candidates,
        entry_features,
        "rule_return_on_risk",
        args.seed,
        args.n_estimators,
        args.n_jobs,
    )
    with logged_phase(f"predict validation entry utilities rows={len(val_candidates):,}"):
        val_pred = predict_regressor(entry_model_fit, val_candidates, entry_features, entry_medians_fit)
    with logged_phase(f"choose validation entry threshold rows={len(val_candidates):,} min_trades={int(args.min_val_trades)}"):
        entry_threshold, validation_trades, entry_threshold_payload = choose_entry_threshold(
            val_candidates,
            val_pred,
            args.min_val_trades,
        )
    log(
        f"[OPTION_POLICY] validation entry_threshold={entry_threshold:.6f} "
        f"trades={len(validation_trades):,} pf={trade_metrics(validation_trades).get('profit_factor', float('nan')):.4f}"
    )
    with logged_phase(f"choose validation fixed delta rows={len(val_candidates):,}"):
        best_fixed_delta, fixed_delta_grid = choose_validation_best_delta(
            val_candidates,
            args.delta_targets,
            args.min_val_trades,
        )
    log(f"[OPTION_POLICY] validation best_fixed_delta={best_fixed_delta:.2f}")

    exit_features: list[str] = []
    exit_model_fit = None
    exit_medians_fit = pd.Series(dtype=float)
    exit_margin = float("nan")
    exit_margin_payload: dict = {"grid": []}
    if paths:
        exit_features = entry_features + EXIT_DYNAMIC_FEATURES
        exit_fit_rows = build_exit_training_rows(
            fit_candidates,
            paths,
            entry_features,
            args.max_hold_minutes,
            args.risk_capital,
        )
        if exit_fit_rows.empty:
            raise RuntimeError("No exit training rows were built.")
        exit_features = [f for f in exit_features if f in exit_fit_rows.columns and pd.api.types.is_numeric_dtype(exit_fit_rows[f])]
        log(f"[OPTION_POLICY] exit_fit_rows={len(exit_fit_rows):,} exit_features={len(exit_features):,}")
        exit_model_fit, exit_medians_fit = train_regressor(
            exit_fit_rows,
            exit_features,
            "future_best_return_on_risk",
            args.seed + 17,
            args.exit_n_estimators,
            args.n_jobs,
        )
        with logged_phase(f"select validation candidates rows={len(val_candidates):,}"):
            selected_val = select_best_by_prediction(val_candidates, val_pred, entry_threshold)
        log(f"[OPTION_POLICY] selected_val={len(selected_val):,}")
        exit_margin, exit_margin_payload = choose_exit_margin(
            selected_val,
            paths,
            exit_model_fit,
            exit_features,
            exit_medians_fit,
            entry_features,
            args,
            args.min_val_trades,
        )
    else:
        log("[OPTION_POLICY] option paths unavailable; skipping learned-exit model and reusing hard-exit labels only")

    entry_model, entry_medians = train_regressor(
        train_candidates,
        entry_features,
        "rule_return_on_risk",
        args.seed,
        args.n_estimators,
        args.n_jobs,
    )
    ranker_model, ranker_medians = train_ranker(
        train_candidates,
        entry_features,
        "rule_return_on_risk",
        args.seed + 31,
        args.n_estimators,
        args.n_jobs,
    )

    exit_model = None
    exit_medians = pd.Series(dtype=float)
    if paths:
        exit_train_rows = build_exit_training_rows(
            train_candidates,
            paths,
            entry_features,
            args.max_hold_minutes,
            args.risk_capital,
        )
        log(f"[OPTION_POLICY] exit_train_rows={len(exit_train_rows):,} exit_features={len(exit_features):,}")
        exit_model, exit_medians = train_regressor(
            exit_train_rows,
            exit_features,
            "future_best_return_on_risk",
            args.seed + 17,
            args.exit_n_estimators,
            args.n_jobs,
        )

    with logged_phase(f"predict OOS entry utilities rows={len(test_candidates):,}"):
        test_pred = predict_regressor(entry_model, test_candidates, entry_features, entry_medians)
    with logged_phase(f"build learned regression all-hard trades rows={len(test_candidates):,}"):
        selected_test_all = select_best_by_prediction(test_candidates, test_pred, -1e9)
        learned_regression_all = candidate_trades_from_selection(
            selected_test_all,
            "rule",
            "learned_delta_regression_all_hard",
        )
    with logged_phase(f"predict OOS ranker utilities rows={len(test_candidates):,}"):
        ranker_pred = predict_regressor(ranker_model, test_candidates, entry_features, ranker_medians)
    with logged_phase(f"build learned ranker all-hard trades rows={len(test_candidates):,}"):
        selected_ranker_all = select_best_by_prediction(test_candidates, ranker_pred, -1e9)
        learned_ranker_all = candidate_trades_from_selection(
            selected_ranker_all,
            "rule",
            "learned_delta_ranker_all_hard",
        )
    with logged_phase(f"build supervised skip trades rows={len(test_candidates):,} threshold={entry_threshold:.6f}"):
        selected_test_skip = select_best_by_prediction(test_candidates, test_pred, entry_threshold)
        supervised_hard = candidate_trades_from_selection(selected_test_skip, "rule", "supervised_entry_strike_skip_hard")
    if paths and exit_model is not None:
        supervised_learned = simulate_learned_exit_for_selected(
            selected_test_skip,
            paths,
            exit_model,
            exit_features,
            exit_medians,
            entry_features,
            args,
            "supervised_entry_strike_learned_exit",
            exit_margin,
        )
    else:
        supervised_learned = pd.DataFrame()
    with logged_phase(f"build fixed/oracle policies rows={len(test_candidates):,}"):
        fixed_delta_060 = fixed_delta_policy(test_candidates, 0.60, "rule", "fixed_delta_0.60_hard")
        fixed_delta_070 = fixed_delta_policy(test_candidates, 0.70, "rule", "fixed_delta_0.70_hard")
        validation_best_delta = fixed_delta_policy(
            test_candidates,
            best_fixed_delta,
            "rule",
            f"validation_best_delta_{best_fixed_delta:.2f}_hard",
        )
        oracle_rule = oracle_policy(test_candidates, "rule_pnl_dollars", "rule", "oracle_best_delta_hard")
        oracle_exit = oracle_policy(test_candidates, "oracle_pnl_dollars", "oracle", "oracle_best_delta_oracle_exit")

    policy_trades = {
        "fixed_delta_0.60_hard": fixed_delta_060,
        "fixed_delta_0.70_hard": fixed_delta_070,
        f"validation_best_delta_{best_fixed_delta:.2f}_hard": validation_best_delta,
        "learned_delta_regression_all_hard": learned_regression_all,
        "learned_delta_ranker_all_hard": learned_ranker_all,
        "supervised_entry_strike_skip_hard": supervised_hard,
        "supervised_entry_strike_learned_exit": supervised_learned,
        "oracle_best_delta_hard": oracle_rule,
        "oracle_best_delta_oracle_exit": oracle_exit,
    }
    policy_results = {
        policy: {
            "overall": trade_metrics(trades),
            "per_ticker": summarize_by_ticker(trades),
            "trades": trades,
        }
        for policy, trades in policy_trades.items()
    }
    for policy, payload in policy_results.items():
        metrics = payload["overall"]
        log(
            f"[OPTION_POLICY] OOS {policy} trades={metrics.get('trades', 0)} "
            f"wr={metrics.get('win_rate', float('nan')):.4f} pf={metrics.get('profit_factor', float('nan')):.4f} "
            f"pnl={metrics.get('pnl_dollars', 0.0):.2f} dd={metrics.get('max_drawdown', 0.0):.2f}"
        )

    with logged_phase("write policy CSV outputs"):
        selected_test_skip.to_csv(output_dir / "selected_test_candidates.csv", index=False)
        selected_test_all.to_csv(output_dir / "learned_delta_regression_selected_candidates.csv", index=False)
        selected_ranker_all.to_csv(output_dir / "learned_delta_ranker_selected_candidates.csv", index=False)
        save_policy_outputs(output_dir, policy_results)

    metadata = {
        "config": vars(args),
        "base_feature_count": len(base_features),
        "entry_features": entry_features,
        "exit_features": exit_features,
        "train_candidates": int(len(train_candidates)),
        "test_candidates": int(len(test_candidates)),
        "train_signals": int((signals["date"].astype(str) <= train_end).sum()),
        "test_signals": int((signals["date"].astype(str) >= test_start).sum()),
        "validation": {
            "val_months": sorted(val_months),
            "best_fixed_delta": best_fixed_delta,
            "fixed_delta_grid": fixed_delta_grid,
            "entry_threshold": entry_threshold,
            "exit_margin": exit_margin,
            "entry_threshold_grid": entry_threshold_payload,
            "exit_margin_grid": exit_margin_payload,
            "entry_validation_metrics": trade_metrics(validation_trades),
        },
        "policy_metrics": {
            policy: {
                "overall": payload["overall"],
                "per_ticker": payload["per_ticker"],
            }
            for policy, payload in policy_results.items()
        },
    }
    with logged_phase("write metrics/model/summary artifacts"):
        (output_dir / "metrics.json").write_text(json.dumps(metadata, indent=2, allow_nan=True), encoding="utf-8")

        joblib.dump(
            {
                "entry_model": entry_model,
                "entry_medians": entry_medians.to_dict(),
                "entry_features": entry_features,
                "entry_threshold": entry_threshold,
                "ranker_model": ranker_model,
                "ranker_medians": ranker_medians.to_dict(),
                "exit_model": exit_model,
                "exit_medians": exit_medians.to_dict(),
                "exit_features": exit_features,
                "exit_margin": exit_margin,
                "metadata": metadata,
            },
            model_dir / "jepa_option_policy.joblib",
        )
        write_summary(output_dir, args, metadata, signals, candidates, policy_results, metadata["validation"])
    log("[OPTION_POLICY] COMPLETE")
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
