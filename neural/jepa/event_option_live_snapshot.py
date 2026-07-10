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
LIVE_INTRADAY_STATE_COLUMNS = {
    "phys_event_seq_in_day",
    "phys_event_frac_in_day",
    "phys_minutes_since_first_event",
    "phys_spot_ret_from_first_event_bps",
    "phys_same_day_event_count",
}
LIVE_CONTEXT_COLUMNS = {
    "spot",
    "ret_1m_bps",
    "ret_5m_bps",
    "ret_15m_bps",
    "ret_30m_bps",
    "ib_range_bps",
    "nearest_level_abs_bps",
    "phys_d35_iv_skew_put_minus_call",
    "phys_total_volume_skew_call_minus_put",
    "phys_total_oi_skew_call_minus_put",
}


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
    """Parse exchange timestamps without destroying sub-minute ordering.

    Live ThetaData files contain one-second quotes.  Flooring them before
    selecting a chain snapshot turns every quote in the minute into the same
    key and can create many-to-many OHLC merges.  Minute bucketing belongs at
    the feature layer, after the latest complete quote snapshot is selected.
    """

    return pd.to_datetime(series, format="mixed", errors="coerce")


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
        # realtime_feed stores the number of observed one-second points under
        # ``volume``; the historical derived-underlying files call the same
        # causal quantity ``tick_count``.
        out["tick_count"] = out["volume"] if "volume" in out.columns else 0.0
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
        if before.empty:
            return float("nan"), -1
        work = before
    row = work.iloc[-1]
    return _as_float(row.get("close")), int(row.get("minute", -1))


def _prepare_chain(
    greeks: pd.DataFrame,
    oi: pd.DataFrame,
    ohlc: pd.DataFrame,
    *,
    require_open_interest: bool = False,
) -> pd.DataFrame:
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

    if require_open_interest and (
        oi.empty
        or "open_interest" not in oi.columns
        or "strike" not in oi.columns
        or "right" not in oi.columns
    ):
        return pd.DataFrame()

    if not oi.empty:
        oi_part = oi.copy()
        if "right" in oi_part.columns:
            oi_part["right"] = oi_part["right"].map(normalize_right)
        if "strike" in oi_part.columns:
            oi_part["strike"] = pd.to_numeric(oi_part["strike"], errors="coerce").astype(float)
        if "open_interest" in oi_part.columns:
            oi_part["open_interest"] = pd.to_numeric(oi_part["open_interest"], errors="coerce").astype(float)
            if require_open_interest:
                oi_part = oi_part.dropna(subset=["strike", "right", "open_interest"])
                if oi_part.empty:
                    return pd.DataFrame()
            oi_part = oi_part.groupby(["strike", "right"], observed=True)["open_interest"].max().reset_index()
            out = out.merge(oi_part, on=["strike", "right"], how="left")
    if "open_interest" not in out.columns:
        if require_open_interest:
            return pd.DataFrame()
        out["open_interest"] = 0.0
    out["open_interest"] = pd.to_numeric(out["open_interest"], errors="coerce").astype(float)
    if require_open_interest:
        out = out.dropna(subset=["open_interest"]).copy()
        if out.empty:
            return pd.DataFrame()
    else:
        out["open_interest"] = out["open_interest"].fillna(0.0)

    # Historical training quotes are sampled exactly at HH:MM:00.  Anchor live
    # to the same observable cross-section; choosing the latest second inside
    # the minute changes spot, Greeks and contract selection by up to 59s.
    key_cols = [col for col in ("strike", "right") if col in out.columns]
    if len(key_cols) == 2:
        snapshot_sizes = out.drop_duplicates(["dt", *key_cols]).groupby("dt", sort=True).size()
        if snapshot_sizes.empty:
            return pd.DataFrame()
        max_contracts = int(snapshot_sizes.max())
        min_complete = max(12, int(np.ceil(max_contracts * 0.80)))
        complete_times = snapshot_sizes[
            (snapshot_sizes >= min_complete)
            & (snapshot_sizes.index.second == 0)
            & (snapshot_sizes.index.microsecond == 0)
        ]
        if complete_times.empty:
            return pd.DataFrame()
        snapshot_dt = pd.Timestamp(complete_times.index.max())
        out = out[out["dt"] == snapshot_dt].copy()
        out = out.sort_values(["dt", *key_cols], kind="stable").drop_duplicates(key_cols, keep="last")

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
            latest_quote_dt = pd.Timestamp(out["dt"].max())
            previous_start = latest_quote_dt.floor("min") - pd.Timedelta(minutes=1)
            previous_end = latest_quote_dt.floor("min")
            opt = opt[(opt["dt"] >= previous_start) & (opt["dt"] < previous_end)]
            if not opt.empty:
                opt = opt.sort_values("dt", kind="stable")
                grouped = opt.groupby(["strike", "right"], as_index=False, observed=True).agg(
                    opt_close=("close", "last"),
                    opt_volume=("volume", "sum"),
                    opt_count=("count", "sum"),
                )
                out = out.merge(grouped, on=["strike", "right"], how="left", validate="one_to_one")
    for col in ("opt_close", "opt_volume", "opt_count"):
        if col not in out.columns:
            out[col] = 0.0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0).astype(float)
    return out


def latest_chain_snapshot(
    day_dir: Path,
    options_symbol: str,
    suffix: str,
    *,
    require_open_interest: bool = False,
) -> pd.DataFrame:
    greeks = _read_parquet(day_dir / f"{options_symbol}_greeks_{suffix}_latest.parquet")
    oi = _read_parquet(day_dir / f"{options_symbol}_oi_{suffix}_latest.parquet")
    ohlc = _read_parquet(day_dir / f"{options_symbol}_ohlc_{suffix}_latest.parquet")
    chain = _prepare_chain(greeks, oi, ohlc, require_open_interest=require_open_interest)
    if chain.empty:
        return chain
    latest = chain["dt"].max()
    if pd.notna(latest):
        chain = chain[chain["dt"] == latest].copy()
    return chain.reset_index(drop=True)


def _initial_balance_complete(spot: pd.DataFrame) -> bool:
    """Require every 09:30--10:29 ET minute used by the frozen IB contract."""

    if spot.empty or "minute" not in spot.columns:
        return False
    minutes = pd.to_numeric(spot["minute"], errors="coerce").dropna().astype(int)
    present = set(minutes[(minutes >= 570) & (minutes < 630)].tolist())
    return all(minute in present for minute in range(570, 630))


def _naive_wall_time(value: datetime | pd.Timestamp) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is not None:
        # ThetaData timestamps are naive US/Eastern wall-clock values.
        stamp = stamp.tz_localize(None)
    return stamp


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
    max_snapshot_age_seconds: int = 180,
    future_tolerance_seconds: int = 5,
) -> dict[str, Any] | None:
    options_symbol = OPTIONS_SYMBOLS.get(str(ticker).upper(), str(ticker).upper())
    underlying_ticker = UNDERLYING_SYMBOLS.get(options_symbol, str(ticker).upper())
    snapshot = latest_chain_snapshot(day_dir, options_symbol, suffix, require_open_interest=True)
    if snapshot.empty:
        return None
    dt = pd.Timestamp(snapshot["dt"].max())
    if now is not None and pd.notna(dt):
        age_seconds = float((_naive_wall_time(now) - _naive_wall_time(dt)).total_seconds())
        if age_seconds < -float(max(0, future_tolerance_seconds)):
            return None
        if age_seconds > float(max(0, max_snapshot_age_seconds)):
            return None
    trade_date = dt.strftime("%Y%m%d") if pd.notna(dt) else (now or datetime.now()).strftime("%Y%m%d")
    spot_history = load_spot_history(day_dir, underlying_ticker)
    if not spot_history.empty and pd.notna(dt):
        spot_history = spot_history[
            (spot_history["dt"].dt.normalize() == dt.normalize())
            & (spot_history["dt"] <= dt)
        ].copy().reset_index(drop=True)
    snapshot_spot = pd.to_numeric(snapshot.get("underlying_price"), errors="coerce") if "underlying_price" in snapshot else pd.Series(dtype=float)
    snapshot_spot = snapshot_spot[np.isfinite(snapshot_spot) & (snapshot_spot > 0.0)]
    spot_value = float(snapshot_spot.median()) if not snapshot_spot.empty else float("nan")
    if not np.isfinite(spot_value) or spot_value <= 0.0:
        spot_value, _minute_from_spot = _latest_spot_at(spot_history, dt)
    if not np.isfinite(spot_value) or spot_value <= 0.0:
        return None

    if not _initial_balance_complete(spot_history):
        return None
    levels = build_levels(spot_history)
    minute = minutes_of_day(dt) if pd.notna(dt) else int(spot_history.iloc[-1]["minute"])
    current_pos = int(spot_history[spot_history["dt"] <= dt].index.max()) if not spot_history[spot_history["dt"] <= dt].empty else len(spot_history) - 1
    completed_bars = spot_history[spot_history["dt"] < dt.floor("min")] if pd.notna(dt) else pd.DataFrame()
    prior_volume = (
        _as_float(completed_bars.iloc[-1].get("tick_count"), 0.0)
        if not completed_bars.empty
        else 0.0
    )
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
        "initial_balance_complete": 1,
        "underlying_volume": prior_volume,
        **level_features(float(spot_value), levels),
    }
    for lookback in (1, 5, 15, 30):
        row[f"ret_{lookback}m_bps"] = _ret_bps(spot_history, current_pos, float(spot_value), lookback)
    for delta in DELTA_BUCKETS:
        label = f"d{int(round(delta * 100)):02d}"
        call = select_contract(snapshot, "CALL", delta, option_price_mode="executable_quote")
        put = select_contract(snapshot, "PUT", delta, option_price_mode="executable_quote")
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
        frame = add_live_cross_index_context_asof(frame)
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


def add_live_cross_index_context_asof(
    frame: pd.DataFrame,
    *,
    max_context_age_minutes: int = 3,
) -> pd.DataFrame:
    """Add causal cross-index context for asynchronous live snapshots.

    The offline dataset samples all tickers on an aligned grid, so exact
    trade_date/minute joins work there. The live feed polls chains
    asynchronously; this uses the latest row available at or before each
    decision minute, bounded by a short staleness cap.
    """
    if frame.empty:
        return frame.copy()
    if not {"ticker", "trade_date", "minute"}.issubset(frame.columns):
        return add_cross_index_context(frame)

    out = frame.copy()
    out["minute"] = pd.to_numeric(out["minute"], errors="coerce").fillna(-1).astype(int)
    available = [col for col in LIVE_CONTEXT_COLUMNS if col in out.columns]
    if not available:
        return out

    base = out[["trade_date", "minute"]].copy()
    base["_row_index"] = np.arange(len(out))
    base = base.sort_values(["trade_date", "minute", "_row_index"], kind="stable")
    max_age = max(0, int(max_context_age_minutes))

    for ticker in ("SPXW", "SPY", "QQQ"):
        source = out[out["ticker"].astype(str).str.upper().eq(ticker)].copy()
        # Training context is built from the zero-DTE dataset.  With both live
        # expiry modes present, lexical sorting previously selected
        # ``front_weekly`` for almost every timestamp.
        if "expiry_mode" in source.columns:
            zero_dte = source[source["expiry_mode"].astype(str).eq("zero_dte")].copy()
            if not zero_dte.empty:
                source = zero_dte
        if source.empty:
            continue
        source = source.sort_values(
            [col for col in ("trade_date", "minute", "expiry_mode", "timestamp") if col in source.columns],
            kind="stable",
        )
        source = source.drop_duplicates(["trade_date", "minute"], keep="first")
        source_cols = ["trade_date", "minute", *available]
        source = source[source_cols].copy()
        source["_source_minute"] = source["minute"].astype(int)
        source = source.sort_values(["trade_date", "minute"], kind="stable")
        prefix = ticker.lower().replace("spxw", "spx")

        mapped_parts: list[pd.DataFrame] = []
        for trade_date, base_part in base.groupby("trade_date", sort=False):
            source_part = source[source["trade_date"].astype(str).eq(str(trade_date))].copy()
            if source_part.empty:
                mapped = base_part[["_row_index", "minute"]].copy()
                for col in available:
                    mapped[col] = np.nan
                mapped["_source_minute"] = np.nan
            else:
                mapped = pd.merge_asof(
                    base_part.sort_values("minute", kind="stable"),
                    source_part.sort_values("minute", kind="stable"),
                    on="minute",
                    direction="backward",
                )
            mapped_parts.append(mapped)
        if not mapped_parts:
            continue
        mapped_all = pd.concat(mapped_parts, ignore_index=True, sort=False).set_index("_row_index")
        age = out["minute"].astype(float) - pd.to_numeric(mapped_all["_source_minute"], errors="coerce")
        fresh = age.ge(0.0) & age.le(float(max_age))
        for col in available:
            values = pd.to_numeric(mapped_all[col], errors="coerce").where(fresh, np.nan)
            out[f"ctx_{prefix}_{col}"] = values.reindex(range(len(out))).to_numpy(dtype=float)
            if col.startswith("ret_") and col in out.columns:
                out[f"ctx_{prefix}_{col}_minus_self"] = out[f"ctx_{prefix}_{col}"] - pd.to_numeric(
                    out[col], errors="coerce"
                )

    if {"ctx_spy_ret_5m_bps", "ctx_qqq_ret_5m_bps"}.issubset(out.columns):
        out["ctx_spy_qqq_ret_5m_spread"] = (
            pd.to_numeric(out["ctx_spy_ret_5m_bps"], errors="coerce")
            - pd.to_numeric(out["ctx_qqq_ret_5m_bps"], errors="coerce")
        )
    if {"ctx_spx_ret_5m_bps", "ctx_spy_ret_5m_bps"}.issubset(out.columns):
        out["ctx_spx_spy_ret_5m_spread"] = (
            pd.to_numeric(out["ctx_spx_ret_5m_bps"], errors="coerce")
            - pd.to_numeric(out["ctx_spy_ret_5m_bps"], errors="coerce")
        )
    return out


def refresh_live_event_option_history_features(
    frame: pd.DataFrame,
    *,
    max_context_age_minutes: int = 3,
) -> pd.DataFrame:
    """Recompute history-dependent live features after appending snapshot history."""
    if frame.empty:
        return frame.copy()
    stale_cols = [
        col
        for col in frame.columns
        if col.startswith("ctx_") or col in LIVE_INTRADAY_STATE_COLUMNS
    ]
    out = frame.drop(columns=stale_cols, errors="ignore").copy()
    out = add_intraday_state(out)
    out = add_live_cross_index_context_asof(out, max_context_age_minutes=max_context_age_minutes)
    sort_cols = [col for col in ("ticker", "trade_date", "expiry_mode", "timestamp", "time") if col in out.columns]
    if sort_cols:
        out = out.sort_values(sort_cols, kind="stable").reset_index(drop=True)
    return out


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
