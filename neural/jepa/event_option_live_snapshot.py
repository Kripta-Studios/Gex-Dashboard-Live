from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.build_event_option_dataset import (
    DELTA_BUCKETS,
    build_levels,
    contract_features,
    level_features,
    minutes_of_day,
    normalize_right,
    select_contract,
)
from neural.jepa.enhance_event_option_dataset_physics import (
    add_cross_index_context,
    add_intraday_state,
    add_level_physics,
    add_option_physics,
)


OPTIONS_SYMBOLS = {"SPX": "SPXW", "SPXW": "SPXW", "SPY": "SPY", "QQQ": "QQQ"}
UNDERLYING_SYMBOLS = {"SPXW": "SPX", "SPX": "SPX", "SPY": "SPY", "QQQ": "QQQ"}
EXPIRY_MODES = {"0dte": "zero_dte", "weekly": "front_weekly"}
DELTA_INT_BUCKETS = tuple(int(round(delta * 100)) for delta in DELTA_BUCKETS)


@dataclass(frozen=True)
class LiveSnapshotBuildResult:
    rows: pd.DataFrame
    summary: dict[str, Any]


def _read_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_parquet(path)
    except Exception:
        return pd.DataFrame()


def _as_float(value: Any, default: float = float("nan")) -> float:
    try:
        out = float(value)
        return out if np.isfinite(out) else default
    except Exception:
        return default


def _parse_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, format="mixed", errors="coerce").dt.floor("min")


def _standardize_spot_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    out = frame.copy()
    if "timestamp" in out.columns:
        out["dt"] = _parse_datetime(out["timestamp"])
    elif "time" in out.columns and "date" in out.columns:
        out["dt"] = pd.to_datetime(out["date"].astype(str) + " " + out["time"].astype(str), errors="coerce").dt.floor("min")
    else:
        return pd.DataFrame()
    out = out.dropna(subset=["dt"]).copy()
    if "close" not in out.columns and "spot_price" in out.columns:
        out["close"] = out["spot_price"]
    for col in ("open", "high", "low"):
        if col not in out.columns:
            out[col] = out.get("close", np.nan)
    if "tick_count" not in out.columns:
        out["tick_count"] = 0.0
    for col in ("open", "high", "low", "close", "tick_count"):
        out[col] = pd.to_numeric(out[col], errors="coerce").astype(float)
    out = out.dropna(subset=["close"]).copy()
    out["minute"] = out["dt"].map(minutes_of_day).astype(int)
    out = out[(out["minute"] >= 570) & (out["minute"] <= 960)].copy()
    return out.sort_values("dt").reset_index(drop=True)


def load_spot_history(day_dir: Path, underlying_ticker: str) -> pd.DataFrame:
    spot = _standardize_spot_frame(_read_parquet(day_dir / f"spot_{underlying_ticker}_latest.parquet"))
    if not spot.empty:
        return spot
    ml = _read_parquet(day_dir / f"ml_features_1m_{underlying_ticker}_latest.parquet")
    if ml.empty:
        ml = _read_parquet(day_dir / f"ml_features_{underlying_ticker}_latest.parquet")
    return _standardize_spot_frame(ml)


def _latest_spot_at(spot: pd.DataFrame, dt: pd.Timestamp | None) -> tuple[float, int]:
    if spot.empty:
        return float("nan"), -1
    work = spot
    if dt is not None and pd.notna(dt):
        before = spot[spot["dt"] <= dt]
        if not before.empty:
            work = before
    row = work.iloc[-1]
    return _as_float(row.get("close")), int(row.get("minute", -1))


def _prepare_chain(greeks: pd.DataFrame, oi: pd.DataFrame, ohlc: pd.DataFrame) -> pd.DataFrame:
    if greeks.empty:
        return pd.DataFrame()
    out = greeks.copy()
    time_col = "underlying_timestamp" if "underlying_timestamp" in out.columns else "timestamp" if "timestamp" in out.columns else ""
    if not time_col:
        return pd.DataFrame()
    out["dt"] = _parse_datetime(out[time_col])
    out = out.dropna(subset=["dt"]).copy()
    out["right"] = out["right"].map(normalize_right) if "right" in out.columns else ""
    if "implied_vol" not in out.columns and "implied_volatility" in out.columns:
        out["implied_vol"] = out["implied_volatility"]
    for col in ("strike", "underlying_price", "delta", "implied_vol", "theta", "vega", "bid", "ask"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").astype(float)
    if "expiration" in out.columns:
        out["expiration"] = out["expiration"].astype(str).str.replace(r"\D", "", regex=True).str[:8]

    if not oi.empty:
        oi_part = oi.copy()
        if "right" in oi_part.columns:
            oi_part["right"] = oi_part["right"].map(normalize_right)
        if "strike" in oi_part.columns:
            oi_part["strike"] = pd.to_numeric(oi_part["strike"], errors="coerce").astype(float)
        if "open_interest" in oi_part.columns:
            oi_part["open_interest"] = pd.to_numeric(oi_part["open_interest"], errors="coerce").fillna(0.0).astype(float)
            oi_part = oi_part.groupby(["strike", "right"], observed=True)["open_interest"].max().reset_index()
            out = out.merge(oi_part, on=["strike", "right"], how="left")
    if "open_interest" not in out.columns:
        out["open_interest"] = 0.0
    out["open_interest"] = pd.to_numeric(out["open_interest"], errors="coerce").fillna(0.0).astype(float)

    if not ohlc.empty:
        opt = ohlc.copy()
        if "timestamp" in opt.columns:
            opt["dt"] = _parse_datetime(opt["timestamp"])
        elif "underlying_timestamp" in opt.columns:
            opt["dt"] = _parse_datetime(opt["underlying_timestamp"])
        else:
            opt["dt"] = pd.NaT
        opt = opt.dropna(subset=["dt"]).copy()
        if "right" in opt.columns:
            opt["right"] = opt["right"].map(normalize_right)
        for col in ("strike", "close", "volume", "count"):
            if col in opt.columns:
                opt[col] = pd.to_numeric(opt[col], errors="coerce").fillna(0.0).astype(float)
        keep = [col for col in ("dt", "strike", "right", "close", "volume", "count") if col in opt.columns]
        if {"dt", "strike", "right"}.issubset(keep):
            opt = opt[keep].rename(columns={"close": "opt_close", "volume": "opt_volume", "count": "opt_count"})
            out = out.merge(opt, on=["dt", "strike", "right"], how="left")
    for col in ("opt_close", "opt_volume", "opt_count"):
        if col not in out.columns:
            out[col] = 0.0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0).astype(float)
    return out


def latest_chain_snapshot(day_dir: Path, options_symbol: str, suffix: str) -> pd.DataFrame:
    greeks = _read_parquet(day_dir / f"{options_symbol}_greeks_{suffix}_latest.parquet")
    oi = _read_parquet(day_dir / f"{options_symbol}_oi_{suffix}_latest.parquet")
    ohlc = _read_parquet(day_dir / f"{options_symbol}_ohlc_{suffix}_latest.parquet")
    chain = _prepare_chain(greeks, oi, ohlc)
    if chain.empty:
        return chain
    latest = chain["dt"].max()
    if pd.notna(latest):
        chain = chain[chain["dt"] == latest].copy()
    return chain.reset_index(drop=True)


def _expiration_from_snapshot(snapshot: pd.DataFrame, trade_date: str) -> tuple[str, int]:
    expiration = ""
    if "expiration" in snapshot.columns:
        values = snapshot["expiration"].dropna().astype(str).str.replace(r"\D", "", regex=True).str[:8]
        values = values[values.str.len() == 8]
        if not values.empty:
            expiration = str(values.iloc[0])
    if not expiration:
        expiration = trade_date
    try:
        dte = max((pd.Timestamp(expiration).date() - pd.Timestamp(trade_date).date()).days, 0)
    except Exception:
        dte = 0
    return expiration, int(dte)


def _ret_bps(spot: pd.DataFrame, current_pos: int, current_spot: float, lookback: int) -> float:
    current_minute = int(spot.iloc[current_pos]["minute"]) if current_pos >= 0 and not spot.empty else -1
    prior = spot[spot["minute"] <= current_minute - int(lookback)] if current_minute >= 0 else pd.DataFrame()
    if prior.empty:
        return float("nan")
    prev = _as_float(prior.iloc[-1].get("close"))
    if not np.isfinite(prev) or prev <= 0.0 or current_spot <= 0.0:
        return float("nan")
    return float((current_spot / prev - 1.0) * 10_000.0)


def build_snapshot_row(
    *,
    day_dir: Path,
    ticker: str,
    suffix: str,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    options_symbol = OPTIONS_SYMBOLS.get(str(ticker).upper(), str(ticker).upper())
    underlying_ticker = UNDERLYING_SYMBOLS.get(options_symbol, str(ticker).upper())
    snapshot = latest_chain_snapshot(day_dir, options_symbol, suffix)
    if snapshot.empty:
        return None
    dt = pd.Timestamp(snapshot["dt"].max())
    trade_date = dt.strftime("%Y%m%d") if pd.notna(dt) else (now or datetime.now()).strftime("%Y%m%d")
    spot_history = load_spot_history(day_dir, underlying_ticker)
    spot_value, _minute_from_spot = _latest_spot_at(spot_history, dt)
    if not np.isfinite(spot_value) or spot_value <= 0.0:
        spot_value = _as_float(snapshot["underlying_price"].dropna().iloc[-1] if "underlying_price" in snapshot.columns and snapshot["underlying_price"].notna().any() else np.nan)
    if not np.isfinite(spot_value) or spot_value <= 0.0:
        return None

    if spot_history.empty:
        minute = minutes_of_day(dt) if pd.notna(dt) else -1
        spot_history = pd.DataFrame(
            [{
                "dt": dt,
                "open": spot_value,
                "high": spot_value,
                "low": spot_value,
                "close": spot_value,
                "tick_count": 0.0,
                "minute": minute,
            }]
        )
    levels = build_levels(spot_history)
    minute = minutes_of_day(dt) if pd.notna(dt) else int(spot_history.iloc[-1]["minute"])
    current_pos = int(spot_history[spot_history["dt"] <= dt].index.max()) if not spot_history[spot_history["dt"] <= dt].empty else len(spot_history) - 1
    expiration, dte_days = _expiration_from_snapshot(snapshot, trade_date)
    row: dict[str, Any] = {
        "ticker": options_symbol,
        "underlying_ticker": underlying_ticker,
        "trade_date": trade_date,
        "expiration": expiration,
        "dte_days": dte_days,
        "expiry_mode": EXPIRY_MODES.get(suffix, suffix),
        "timestamp": dt.isoformat() if pd.notna(dt) else "",
        "time": dt.strftime("%H:%M") if pd.notna(dt) else "",
        "minute": int(minute),
        "spot": float(spot_value),
        "underlying_volume": _as_float(spot_history.iloc[current_pos].get("tick_count"), 0.0) if current_pos >= 0 else 0.0,
        **level_features(float(spot_value), levels),
    }
    for lookback in (1, 5, 15, 30):
        row[f"ret_{lookback}m_bps"] = _ret_bps(spot_history, current_pos, float(spot_value), lookback)
    for delta in DELTA_BUCKETS:
        label = f"d{int(round(delta * 100)):02d}"
        call = select_contract(snapshot, "CALL", delta)
        put = select_contract(snapshot, "PUT", delta)
        row.update(contract_features(call, float(spot_value), f"call_{label}"))
        row.update(contract_features(put, float(spot_value), f"put_{label}"))
    return row


def build_live_event_option_snapshots(
    day_dir: str | Path,
    *,
    tickers: tuple[str, ...] = ("SPXW", "SPY", "QQQ"),
    suffixes: tuple[str, ...] = ("0dte", "weekly"),
    now: datetime | None = None,
) -> LiveSnapshotBuildResult:
    root = Path(day_dir)
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for ticker in tickers:
        for suffix in suffixes:
            row = build_snapshot_row(day_dir=root, ticker=ticker, suffix=suffix, now=now)
            if row is None:
                missing.append(f"{ticker}:{suffix}")
                continue
            rows.append(row)
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = add_option_physics(frame, DELTA_INT_BUCKETS)
        frame = add_level_physics(frame)
        frame = add_intraday_state(frame)
        frame = add_cross_index_context(frame)
        frame = frame.sort_values(["ticker", "expiry_mode", "minute"]).reset_index(drop=True)
    summary = {
        "rows": int(len(frame)),
        "day_dir": str(root),
        "tickers": sorted(frame["ticker"].astype(str).unique().tolist()) if not frame.empty and "ticker" in frame.columns else [],
        "expiry_modes": frame["expiry_mode"].value_counts().sort_index().astype(int).to_dict() if not frame.empty and "expiry_mode" in frame.columns else {},
        "missing": missing,
        "columns": int(len(frame.columns)) if not frame.empty else 0,
    }
    return LiveSnapshotBuildResult(rows=frame, summary=summary)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build live event-option snapshot rows from rt_data parquet files.")
    parser.add_argument("--rt-day-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary", default="")
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--suffixes", nargs="+", default=["0dte", "weekly"])
    args = parser.parse_args()

    result = build_live_event_option_snapshots(
        args.rt_day_dir,
        tickers=tuple(str(x).upper() for x in args.tickers),
        suffixes=tuple(str(x).lower() for x in args.suffixes),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.rows.to_parquet(output, index=False)
    summary_path = Path(args.summary) if args.summary else output.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(result.summary, indent=2, allow_nan=True), encoding="utf-8")
    print(json.dumps(result.summary, indent=2, allow_nan=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
