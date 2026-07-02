from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


GREEK_COLS = [
    "strike",
    "right",
    "underlying_price",
    "underlying_timestamp",
    "delta",
    "implied_vol",
    "theta",
    "vega",
    "bid",
    "ask",
    "timestamp",
]
OI_COLS = ["strike", "right", "open_interest"]
OPT_OHLC_COLS = ["strike", "right", "timestamp", "open", "high", "low", "close", "volume", "count"]
UNDERLYING_COLS = ["timestamp", "open", "high", "low", "close", "tick_count"]
DELTA_BUCKETS = [0.15, 0.25, 0.35, 0.50, 0.65, 0.80]


def safe_read_parquet(path: str | Path, columns: list[str] | None = None) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        return pd.DataFrame()
    try:
        if columns is None:
            return pd.read_parquet(path)
        import pyarrow.parquet as pq

        available = set(pq.ParquetFile(path).schema.names)
        request = [c for c in columns if c in available]
        if not request:
            return pd.DataFrame()
        return pd.read_parquet(path, columns=request)
    except Exception:
        return pd.DataFrame()


def minutes_of_day(ts: pd.Timestamp) -> int:
    return int(ts.hour) * 60 + int(ts.minute)


def normalize_right(value: object) -> str:
    text = str(value).upper()
    if text.startswith("C"):
        return "CALL"
    if text.startswith("P"):
        return "PUT"
    return text


def add_dt(df: pd.DataFrame, source: str = "timestamp") -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    if source not in out.columns:
        source = "timestamp" if "timestamp" in out.columns else out.columns[0]
    out["dt"] = pd.to_datetime(out[source], errors="coerce").dt.floor("min")
    out = out.dropna(subset=["dt"])
    return out


def load_underlying(path: str | Path) -> pd.DataFrame:
    df = safe_read_parquet(path, UNDERLYING_COLS)
    if df.empty:
        return df
    df = add_dt(df, "timestamp")
    for col in ["open", "high", "low", "close", "tick_count"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype(np.float32)
    df["minute"] = df["dt"].map(minutes_of_day).astype(np.int16)
    df = df[(df["minute"] >= 570) & (df["minute"] <= 960)].copy()
    return df.sort_values("dt").reset_index(drop=True)


def load_chain(row: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame]:
    greeks = safe_read_parquet(row["greeks_path"], GREEK_COLS)
    if greeks.empty:
        return pd.DataFrame(), pd.DataFrame()
    greeks = add_dt(greeks, "underlying_timestamp" if "underlying_timestamp" in greeks.columns else "timestamp")
    greeks["right"] = greeks["right"].map(normalize_right)
    for col in ["strike", "underlying_price", "delta", "implied_vol", "theta", "vega", "bid", "ask"]:
        if col in greeks.columns:
            greeks[col] = pd.to_numeric(greeks[col], errors="coerce").astype(np.float32)

    oi = safe_read_parquet(row["oi_path"], OI_COLS)
    if not oi.empty:
        oi["right"] = oi["right"].map(normalize_right)
        oi["strike"] = pd.to_numeric(oi["strike"], errors="coerce").astype(np.float32)
        oi["open_interest"] = pd.to_numeric(oi["open_interest"], errors="coerce").fillna(0.0).astype(np.float32)
        oi = oi.groupby(["strike", "right"], observed=True)["open_interest"].max().reset_index()
        greeks = greeks.merge(oi, on=["strike", "right"], how="left")
    else:
        greeks["open_interest"] = 0.0
    greeks["open_interest"] = greeks["open_interest"].fillna(0.0).astype(np.float32)

    ohlc = safe_read_parquet(row["ohlc_path"], OPT_OHLC_COLS)
    if not ohlc.empty:
        ohlc = add_dt(ohlc, "timestamp")
        ohlc["right"] = ohlc["right"].map(normalize_right)
        for col in ["strike", "open", "high", "low", "close", "volume", "count"]:
            if col in ohlc.columns:
                ohlc[col] = pd.to_numeric(ohlc[col], errors="coerce").fillna(0.0).astype(np.float32)
        current = ohlc[["dt", "strike", "right", "close", "volume", "count"]].rename(
            columns={"close": "opt_close", "volume": "opt_volume", "count": "opt_count"}
        )
        greeks = greeks.merge(current, on=["dt", "strike", "right"], how="left")
    else:
        greeks["opt_close"] = 0.0
        greeks["opt_volume"] = 0.0
        greeks["opt_count"] = 0.0
    for col in ["opt_close", "opt_volume", "opt_count"]:
        if col in greeks.columns:
            greeks[col] = greeks[col].fillna(0.0).astype(np.float32)
    return greeks, ohlc


def build_levels(underlying: pd.DataFrame) -> dict:
    ib = underlying[(underlying["minute"] >= 570) & (underlying["minute"] < 630)]
    if ib.empty:
        ib = underlying.head(60)
    ib_high = float(ib["high"].max())
    ib_low = float(ib["low"].min())
    ib_range = max(ib_high - ib_low, 1e-6)
    return {
        "ib_high": ib_high,
        "ib_low": ib_low,
        "ib_mid": (ib_high + ib_low) / 2.0,
        "fib_127_up": ib_high + ib_range * 0.272,
        "fib_161_up": ib_high + ib_range * 0.618,
        "fib_200_up": ib_high + ib_range,
        "fib_127_dn": ib_low - ib_range * 0.272,
        "fib_161_dn": ib_low - ib_range * 0.618,
        "fib_200_dn": ib_low - ib_range,
    }


def level_features(spot: float, levels: dict) -> dict:
    out = {}
    nearest_name = ""
    nearest_abs = float("inf")
    for name, value in levels.items():
        if name == "ib_mid":
            continue
        dist = (spot - float(value)) / max(spot, 1e-6) * 10_000.0
        out[f"dist_{name}_bps"] = float(dist)
        if abs(dist) < nearest_abs:
            nearest_abs = abs(dist)
            nearest_name = name
    out["nearest_level_name"] = nearest_name
    out["nearest_level_abs_bps"] = float(nearest_abs)
    out["ib_range_bps"] = float((levels["ib_high"] - levels["ib_low"]) / max(spot, 1e-6) * 10_000.0)
    return out


def simulate_spot_path(
    underlying: pd.DataFrame,
    pos: int,
    horizon_minutes: int,
    target_bps: float,
    stop_bps: float,
) -> dict:
    entry = float(underlying.iloc[pos]["close"])
    if entry <= 0:
        return {}
    end_minute = int(underlying.iloc[pos]["minute"]) + int(horizon_minutes)
    future = underlying[(underlying.index > pos) & (underlying["minute"] <= end_minute)]
    if future.empty:
        return {}
    high_ret = (future["high"].astype(float).max() / entry - 1.0) * 10_000.0
    low_ret = (future["low"].astype(float).min() / entry - 1.0) * 10_000.0
    close_ret = (float(future.iloc[-1]["close"]) / entry - 1.0) * 10_000.0
    long_status = 0
    short_status = 0
    long_exit_minutes = horizon_minutes
    short_exit_minutes = horizon_minutes
    for item in future.itertuples():
        elapsed = int(item.minute) - int(underlying.iloc[pos]["minute"])
        up = (float(item.high) / entry - 1.0) * 10_000.0
        down = (float(item.low) / entry - 1.0) * 10_000.0
        if long_status == 0:
            if down <= -float(stop_bps):
                long_status = -1
                long_exit_minutes = elapsed
            elif up >= float(target_bps):
                long_status = 1
                long_exit_minutes = elapsed
        if short_status == 0:
            if up >= float(stop_bps):
                short_status = -1
                short_exit_minutes = elapsed
            elif down <= -float(target_bps):
                short_status = 1
                short_exit_minutes = elapsed
    if long_status == 1 and short_status == 1:
        best_side = 1 if long_exit_minutes <= short_exit_minutes else -1
    elif long_status == 1:
        best_side = 1
    elif short_status == 1:
        best_side = -1
    else:
        best_side = 0
    return {
        "future_close_ret_bps": float(close_ret),
        "future_max_up_bps": float(high_ret),
        "future_max_down_bps": float(low_ret),
        "spot_long_win": int(long_status == 1),
        "spot_short_win": int(short_status == 1),
        "spot_long_exit_minutes": int(long_exit_minutes),
        "spot_short_exit_minutes": int(short_exit_minutes),
        "spot_best_side": int(best_side),
    }


def select_contract(snapshot: pd.DataFrame, right: str, target_abs_delta: float) -> pd.Series | None:
    part = snapshot[snapshot["right"].astype(str) == right].copy()
    if part.empty or "delta" not in part.columns:
        return None
    part["_delta_err"] = (part["delta"].abs().astype(float) - float(target_abs_delta)).abs()
    part["_liq"] = part.get("open_interest", 0.0).astype(float) + part.get("opt_volume", 0.0).astype(float)
    part = part.sort_values(["_delta_err", "_liq"], ascending=[True, False])
    return part.iloc[0] if not part.empty else None


def contract_features(contract: pd.Series | None, spot: float, prefix: str) -> dict:
    if contract is None:
        return {
            f"{prefix}_available": 0,
            f"{prefix}_strike_bps": np.nan,
            f"{prefix}_abs_delta": np.nan,
            f"{prefix}_iv": np.nan,
            f"{prefix}_mid_bps": np.nan,
            f"{prefix}_spread_pct": np.nan,
            f"{prefix}_theta_over_mid": np.nan,
            f"{prefix}_vega": np.nan,
            f"{prefix}_oi": np.nan,
            f"{prefix}_volume": np.nan,
        }
    bid = float(contract.get("bid", 0.0) or 0.0)
    ask = float(contract.get("ask", 0.0) or 0.0)
    opt_close = float(contract.get("opt_close", 0.0) or 0.0)
    mid = (bid + ask) / 2.0 if bid > 0.0 and ask > 0.0 else opt_close
    spread = (ask - bid) / max(mid, 1e-6) if bid > 0.0 and ask > 0.0 and mid > 0.0 else np.nan
    return {
        f"{prefix}_available": 1,
        f"{prefix}_strike_bps": float((float(contract["strike"]) / max(spot, 1e-6) - 1.0) * 10_000.0),
        f"{prefix}_abs_delta": float(abs(float(contract.get("delta", np.nan)))),
        f"{prefix}_iv": float(contract.get("implied_vol", np.nan)),
        f"{prefix}_mid_bps": float(mid / max(spot, 1e-6) * 10_000.0) if mid > 0.0 else np.nan,
        f"{prefix}_spread_pct": float(spread) if np.isfinite(spread) else np.nan,
        f"{prefix}_theta_over_mid": float(float(contract.get("theta", 0.0) or 0.0) / max(mid, 1e-6)) if mid > 0.0 else np.nan,
        f"{prefix}_vega": float(contract.get("vega", np.nan)),
        f"{prefix}_oi": float(contract.get("open_interest", np.nan)),
        f"{prefix}_volume": float(contract.get("opt_volume", np.nan)),
    }


def option_path_label(
    ohlc: pd.DataFrame,
    contract: pd.Series | None,
    ts: pd.Timestamp,
    horizon_minutes: int,
    tp_pct: float,
    sl_pct: float,
    prefix: str,
    exit_mode: str = "fixed",
    min_hold_minutes: int = 0,
    trail_activation_pct: float = 0.50,
    trail_drawdown_pct: float = 0.25,
) -> dict:
    if contract is None or ohlc.empty:
        return {
            f"{prefix}_opt_win": 0,
            f"{prefix}_opt_status": 0,
            f"{prefix}_opt_exit_ret": np.nan,
            f"{prefix}_opt_exit_minutes": 0,
            f"{prefix}_opt_max_ret": np.nan,
            f"{prefix}_opt_min_ret": np.nan,
        }
    strike = float(contract["strike"])
    right = str(contract["right"])
    entry = float(contract.get("opt_close", 0.0) or 0.0)
    bid = float(contract.get("bid", 0.0) or 0.0)
    ask = float(contract.get("ask", 0.0) or 0.0)
    if entry <= 0.0 and bid > 0.0 and ask > 0.0:
        entry = (bid + ask) / 2.0
    if entry <= 0.0:
        return {
            f"{prefix}_opt_win": 0,
            f"{prefix}_opt_status": 0,
            f"{prefix}_opt_exit_ret": np.nan,
            f"{prefix}_opt_exit_minutes": 0,
            f"{prefix}_opt_max_ret": np.nan,
            f"{prefix}_opt_min_ret": np.nan,
        }
    end_ts = ts + pd.Timedelta(minutes=int(horizon_minutes))
    path = ohlc[
        (ohlc["right"].astype(str) == right)
        & (np.isclose(ohlc["strike"].astype(float), strike))
        & (ohlc["dt"] > ts)
        & (ohlc["dt"] <= end_ts)
    ].copy()
    path = path[(path["high"].astype(float) > 0.0) | (path["low"].astype(float) > 0.0)]
    if path.empty:
        return {
            f"{prefix}_opt_win": 0,
            f"{prefix}_opt_status": 0,
            f"{prefix}_opt_exit_ret": np.nan,
            f"{prefix}_opt_exit_minutes": 0,
            f"{prefix}_opt_max_ret": np.nan,
            f"{prefix}_opt_min_ret": np.nan,
        }
    max_ret = float(path["high"].astype(float).max() / entry - 1.0)
    positive_lows = path[path["low"].astype(float) > 0.0]["low"].astype(float)
    min_ret = float(positive_lows.min() / entry - 1.0) if not positive_lows.empty else np.nan
    status = 0
    exit_ret = np.nan
    exit_minutes = 0
    peak_ret = -float("inf")
    mode = str(exit_mode).lower()
    min_hold = max(0, int(min_hold_minutes))
    for item in path.itertuples():
        high = float(item.high)
        low = float(item.low)
        elapsed = int((pd.Timestamp(item.dt) - ts).total_seconds() // 60)
        high_ret = high / entry - 1.0 if high > 0.0 else -float("inf")
        low_ret = low / entry - 1.0 if low > 0.0 else float("inf")

        if elapsed < min_hold:
            if high_ret > peak_ret:
                peak_ret = float(high_ret)
            continue

        # Conservative intrabar order: adverse low is evaluated before favorable high.
        if low_ret <= -float(sl_pct):
            status = -1
            exit_ret = -float(sl_pct)
            exit_minutes = elapsed
            break
        if mode == "trailing":
            if peak_ret >= float(trail_activation_pct) and low_ret <= peak_ret - float(trail_drawdown_pct):
                trail_ret = peak_ret - float(trail_drawdown_pct)
                status = 1 if trail_ret > 0.0 else -1
                exit_ret = float(trail_ret)
                exit_minutes = elapsed
                break
            if high_ret > peak_ret:
                peak_ret = float(high_ret)
            if peak_ret >= float(tp_pct):
                status = 1
                exit_ret = float(tp_pct)
                exit_minutes = elapsed
                break
            if peak_ret >= float(trail_activation_pct) and low_ret <= peak_ret - float(trail_drawdown_pct):
                trail_ret = peak_ret - float(trail_drawdown_pct)
                status = 1 if trail_ret > 0.0 else -1
                exit_ret = float(trail_ret)
                exit_minutes = elapsed
                break
        elif high_ret >= float(tp_pct):
            status = 1
            exit_ret = float(tp_pct)
            exit_minutes = elapsed
            break
    if status == 0:
        final_close = float(path.iloc[-1].get("close", 0.0) or 0.0)
        exit_ret = final_close / entry - 1.0 if final_close > 0.0 else np.nan
        exit_minutes = int((pd.Timestamp(path.iloc[-1]["dt"]) - ts).total_seconds() // 60)
    return {
        f"{prefix}_opt_win": int(status == 1),
        f"{prefix}_opt_status": int(status),
        f"{prefix}_opt_exit_ret": float(exit_ret) if np.isfinite(exit_ret) else np.nan,
        f"{prefix}_opt_exit_minutes": int(exit_minutes),
        f"{prefix}_opt_max_ret": max_ret,
        f"{prefix}_opt_min_ret": min_ret,
    }


def build_rows_for_manifest_row(row: dict, args_dict: dict) -> pd.DataFrame:
    args = argparse.Namespace(**args_dict)
    underlying = load_underlying(row["underlying_path"])
    if underlying.empty or len(underlying) < 120:
        return pd.DataFrame()
    greeks, ohlc = load_chain(pd.Series(row))
    if greeks.empty:
        return pd.DataFrame()
    levels = build_levels(underlying)
    greeks_by_dt = {ts: frame for ts, frame in greeks.groupby("dt", sort=False)}
    rows: list[dict] = []
    sample_positions = underlying[
        (underlying["minute"] >= int(args.start_minute))
        & (underlying["minute"] <= int(args.end_minute))
        & ((underlying["minute"] - int(args.start_minute)) % int(args.bar_minutes) == 0)
    ].index.tolist()
    for pos in sample_positions:
        ts = pd.Timestamp(underlying.loc[pos, "dt"])
        spot = float(underlying.loc[pos, "close"])
        if spot <= 0.0:
            continue
        lf = level_features(spot, levels)
        if bool(args.near_level_only) and lf["nearest_level_abs_bps"] > float(args.near_level_bps):
            continue
        snapshot = greeks_by_dt.get(ts)
        if snapshot is None or snapshot.empty:
            continue
        base = {
            "ticker": str(row["ticker"]),
            "underlying_ticker": str(row["underlying_ticker"]),
            "trade_date": str(row["trade_date"]),
            "expiration": str(row["expiration"]),
            "dte_days": int(row["dte_days"]),
            "expiry_mode": str(row["expiry_mode"]),
            "timestamp": ts.isoformat(),
            "time": ts.strftime("%H:%M"),
            "minute": int(underlying.loc[pos, "minute"]),
            "spot": spot,
            "underlying_volume": float(underlying.loc[pos].get("tick_count", np.nan)),
            **lf,
        }
        for lookback in [1, 5, 15, 30]:
            prior = underlying[underlying["minute"] <= int(underlying.loc[pos, "minute"]) - lookback]
            if prior.empty:
                base[f"ret_{lookback}m_bps"] = np.nan
            else:
                prior_close = float(prior.iloc[-1]["close"])
                base[f"ret_{lookback}m_bps"] = (
                    float((spot / prior_close - 1.0) * 10_000.0) if prior_close > 0.0 else np.nan
                )
        base.update(
            simulate_spot_path(
                underlying,
                pos,
                int(args.horizon_minutes),
                float(args.spot_target_bps),
                float(args.spot_stop_bps),
            )
        )
        selected_contracts: dict[str, pd.Series | None] = {}
        for delta in DELTA_BUCKETS:
            label = f"d{int(round(delta * 100)):02d}"
            call = select_contract(snapshot, "CALL", delta)
            put = select_contract(snapshot, "PUT", delta)
            selected_contracts[f"call_{label}"] = call
            selected_contracts[f"put_{label}"] = put
            base.update(contract_features(call, spot, f"call_{label}"))
            base.update(contract_features(put, spot, f"put_{label}"))
        for delta in DELTA_BUCKETS:
            label = f"d{int(round(delta * 100)):02d}"
            for side in ["call", "put"]:
                prefix = f"{side}_{label}"
                base.update(
                    option_path_label(
                        ohlc,
                        selected_contracts.get(prefix),
                        ts,
                        int(args.horizon_minutes),
                        float(args.option_tp_pct),
                        float(args.option_sl_pct),
                        prefix,
                        str(args.option_exit_mode),
                        int(args.option_min_hold_minutes),
                        float(args.option_trail_activation_pct),
                        float(args.option_trail_drawdown_pct),
                    )
                )
        rows.append(base)
        if int(args.max_rows_per_day) > 0 and len(rows) >= int(args.max_rows_per_day):
            break
    return pd.DataFrame(rows)


def filter_manifest(manifest: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    out = manifest.copy()
    if args.tickers:
        tickers = {str(t).upper() for t in args.tickers}
        out = out[out["ticker"].astype(str).str.upper().isin(tickers)]
    if args.expiry_modes:
        modes = {str(m) for m in args.expiry_modes}
        out = out[out["expiry_mode"].astype(str).isin(modes)]
    if args.start_date:
        out = out[out["trade_date"].astype(str) >= str(args.start_date)]
    if args.end_date:
        out = out[out["trade_date"].astype(str) <= str(args.end_date)]
    complete_cols = ["has_greeks", "has_iv", "has_ohlc", "has_oi", "has_underlying"]
    for col in complete_cols:
        if col in out.columns:
            out = out[out[col].astype(bool)]
    if int(args.max_days_per_ticker) > 0:
        parts = []
        for _, frame in out.groupby("ticker", sort=True):
            sorted_frame = frame.sort_values(["trade_date", "expiration"]).reset_index(drop=True)
            limit = int(args.max_days_per_ticker)
            if str(args.sample_mode) == "last":
                parts.append(sorted_frame.tail(limit))
            elif str(args.sample_mode) == "even":
                if len(sorted_frame) <= limit:
                    parts.append(sorted_frame)
                else:
                    positions = np.linspace(0, len(sorted_frame) - 1, limit).round().astype(int)
                    parts.append(sorted_frame.iloc[sorted(set(positions.tolist()))])
            else:
                parts.append(sorted_frame.head(limit))
        out = pd.concat(parts, ignore_index=True) if parts else out.iloc[0:0]
    return out.sort_values(["ticker", "trade_date", "expiration"]).reset_index(drop=True)


def write_summary(output_dir: Path, frame: pd.DataFrame, args: argparse.Namespace) -> None:
    if frame.empty:
        summary = {"rows": 0, "args": vars(args)}
    else:
        summary = {
            "rows": int(len(frame)),
            "args": vars(args),
            "tickers": sorted(frame["ticker"].unique().tolist()),
            "date_min": str(frame["trade_date"].min()),
            "date_max": str(frame["trade_date"].max()),
            "expiry_modes": frame["expiry_mode"].value_counts().sort_index().astype(int).to_dict(),
            "spot_best_side": frame["spot_best_side"].value_counts(dropna=False).sort_index().astype(int).to_dict()
            if "spot_best_side" in frame.columns
            else {},
            "by_ticker": {
                str(ticker): {
                    "rows": int(len(part)),
                    "expiry_modes": part["expiry_mode"].value_counts().sort_index().astype(int).to_dict(),
                    "spot_best_side": part["spot_best_side"].value_counts(dropna=False).sort_index().astype(int).to_dict()
                    if "spot_best_side" in part.columns
                    else {},
                }
                for ticker, part in frame.groupby("ticker", sort=True)
            },
        }
    (output_dir / "SUMMARY.json").write_text(json.dumps(summary, indent=2, allow_nan=True), encoding="utf-8")


def sort_dataset(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    cols = [c for c in ["ticker", "trade_date", "expiration", "minute"] if c in frame.columns]
    if not cols:
        return frame.reset_index(drop=True)
    return frame.sort_values(cols).reset_index(drop=True)


def process_manifest_tasks(
    tasks: list[dict],
    args_dict: dict,
    workers: int,
    label: str = "",
) -> pd.DataFrame:
    prefix = f"[EVENT_DATASET:{label}]" if label else "[EVENT_DATASET]"
    frames: list[pd.DataFrame] = []
    if int(workers) <= 1:
        for i, row in enumerate(tasks, start=1):
            frame = build_rows_for_manifest_row(row, args_dict)
            if not frame.empty:
                frames.append(frame)
            if i % 25 == 0 or i == len(tasks):
                print(f"{prefix} processed {i}/{len(tasks)} rows={sum(len(f) for f in frames):,}", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=int(workers)) as executor:
            futures = [executor.submit(build_rows_for_manifest_row, row, args_dict) for row in tasks]
            for i, future in enumerate(as_completed(futures), start=1):
                frame = future.result()
                if not frame.empty:
                    frames.append(frame)
                if i % 25 == 0 or i == len(futures):
                    print(f"{prefix} processed {i}/{len(futures)} rows={sum(len(f) for f in frames):,}", flush=True)
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return sort_dataset(out)


def chunk_manifest(work: pd.DataFrame, chunk_by: str) -> list[tuple[str, pd.DataFrame]]:
    if work.empty:
        return []
    keyed = work.copy()
    if chunk_by == "month":
        keyed["__chunk_key"] = keyed["trade_date"].astype(str).str.slice(0, 6)
    elif chunk_by == "ticker_month":
        keyed["__chunk_key"] = (
            keyed["ticker"].astype(str).str.upper() + "_" + keyed["trade_date"].astype(str).str.slice(0, 6)
        )
    else:
        return [("all", keyed)]
    chunks = []
    for key, frame in keyed.groupby("__chunk_key", sort=True):
        chunks.append((str(key), frame.drop(columns=["__chunk_key"]).reset_index(drop=True)))
    return chunks


def write_chunk_summary(path: Path, frame: pd.DataFrame, manifest_rows: int, args: argparse.Namespace) -> None:
    if frame.empty:
        summary = {"rows": 0, "manifest_rows": int(manifest_rows), "args": vars(args)}
    else:
        summary = {
            "rows": int(len(frame)),
            "manifest_rows": int(manifest_rows),
            "tickers": sorted(frame["ticker"].astype(str).unique().tolist()) if "ticker" in frame.columns else [],
            "date_min": str(frame["trade_date"].min()) if "trade_date" in frame.columns else "",
            "date_max": str(frame["trade_date"].max()) if "trade_date" in frame.columns else "",
            "expiry_modes": frame["expiry_mode"].value_counts().sort_index().astype(int).to_dict()
            if "expiry_mode" in frame.columns
            else {},
            "args": vars(args),
        }
    path.write_text(json.dumps(summary, indent=2, allow_nan=True), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a multi-ticker event-level option-chain dataset from a ThetaData manifest.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA", "TSLA", "META", "AMZN", "GOOGL"])
    parser.add_argument("--expiry-modes", nargs="+", default=["zero_dte", "front_weekly"])
    parser.add_argument("--start-date", default="")
    parser.add_argument("--end-date", default="")
    parser.add_argument("--max-days-per-ticker", type=int, default=0)
    parser.add_argument("--sample-mode", choices=["first", "last", "even"], default="first")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--bar-minutes", type=int, default=5)
    parser.add_argument("--start-minute", type=int, default=630)
    parser.add_argument("--end-minute", type=int, default=930)
    parser.add_argument("--near-level-only", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--near-level-bps", type=float, default=20.0)
    parser.add_argument("--max-rows-per-day", type=int, default=40)
    parser.add_argument("--horizon-minutes", type=int, default=180)
    parser.add_argument("--spot-target-bps", type=float, default=25.0)
    parser.add_argument("--spot-stop-bps", type=float, default=20.0)
    parser.add_argument("--option-tp-pct", type=float, default=0.50)
    parser.add_argument("--option-sl-pct", type=float, default=0.30)
    parser.add_argument("--option-exit-mode", choices=["fixed", "trailing"], default="fixed")
    parser.add_argument("--option-min-hold-minutes", type=int, default=0)
    parser.add_argument("--option-trail-activation-pct", type=float, default=0.50)
    parser.add_argument("--option-trail-drawdown-pct", type=float, default=0.25)
    parser.add_argument("--chunk-by", choices=["none", "month", "ticker_month"], default="none")
    parser.add_argument("--skip-existing-chunks", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = pd.read_csv(args.manifest, dtype={"trade_date": str, "expiration": str})
    work = filter_manifest(manifest, args)
    (output_dir / "filtered_manifest.csv").write_text(work.to_csv(index=False), encoding="utf-8")
    print(f"[EVENT_DATASET] manifest rows={len(work):,}", flush=True)
    if str(args.chunk_by) != "none":
        chunks_dir = output_dir / "chunks"
        chunks_dir.mkdir(parents=True, exist_ok=True)
        chunk_paths: list[Path] = []
        chunks = chunk_manifest(work, str(args.chunk_by))
        for idx, (key, frame) in enumerate(chunks, start=1):
            chunk_path = chunks_dir / f"event_option_dataset_{key}.parquet"
            chunk_summary_path = chunks_dir / f"SUMMARY_{key}.json"
            if bool(args.skip_existing_chunks) and chunk_path.exists():
                print(f"[EVENT_DATASET:{key}] skip existing chunk {idx}/{len(chunks)} -> {chunk_path}", flush=True)
                chunk_paths.append(chunk_path)
                continue
            print(f"[EVENT_DATASET:{key}] chunk {idx}/{len(chunks)} manifest rows={len(frame):,}", flush=True)
            chunk_out = process_manifest_tasks(
                [row for row in frame.to_dict("records")],
                vars(args),
                int(args.workers),
                key,
            )
            if not chunk_out.empty:
                chunk_out.to_parquet(chunk_path, index=False)
                chunk_paths.append(chunk_path)
            write_chunk_summary(chunk_summary_path, chunk_out, len(frame), args)
            print(f"[EVENT_DATASET:{key}] wrote {len(chunk_out):,} rows to {chunk_path}", flush=True)
        frames = [pd.read_parquet(path) for path in chunk_paths if path.exists()]
        out = pd.concat([frame for frame in frames if not frame.empty], ignore_index=True) if frames else pd.DataFrame()
        out = sort_dataset(out)
    else:
        out = process_manifest_tasks(
            [row for row in work.to_dict("records")],
            vars(args),
            int(args.workers),
        )
    out_path = output_dir / "event_option_dataset.parquet"
    out.to_parquet(out_path, index=False)
    write_summary(output_dir, out, args)
    print(f"[EVENT_DATASET] wrote {len(out):,} rows to {out_path}")
    print((output_dir / "SUMMARY.json").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
