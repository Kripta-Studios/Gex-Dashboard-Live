#!/usr/bin/env python3
"""Frozen executable replayer for one defined-risk symmetric short-premium family."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import pyarrow.parquet as pq


REPO_ROOT = Path(__file__).resolve().parents[2]
PREDECLARATION = REPO_ROOT / "research_papers/JEPA/SHORT_PREMIUM_DEFINED_RISK_V1_PREDECLARATION.md"
DEFAULT_GREEKS_ROOT = Path("D:/ThetaData/data_options")
DEFAULT_NATIVE_INDEX = Path(
    "D:/ThetaData/wall_native_quote_sidecar_202208_202512_v1r1/_seal/native_quote_index.csv"
)
DEFAULT_COMPLEMENT_INDEX = Path(
    "D:/ThetaData/wall_quote_size_native_complement_202208_202512_v1/_seal/quote_size_complement_index.csv"
)
DEFAULT_NATIVE_SEAL = (
    REPO_ROOT
    / "research_papers/JEPA/results/_diagnostics/"
    "wall_native_quote_sidecar_202208_202512_v1r1/manifest.json"
)
DEFAULT_COMPLEMENT_SEAL = Path(
    "D:/ThetaData/wall_quote_size_native_complement_202208_202512_v1/_seal/manifest.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "research_papers/JEPA/results/_diagnostics/"
    "short_premium_defined_risk_v1_202401_202512"
)

TICKERS = ("QQQ", "SPXW", "SPY")
FROZEN_START_DATE = "20240101"
FROZEN_END_DATE = "20251231"
FROZEN_SESSIONS_PER_TICKER = 502
ENTRY_TIME = "10:35:00"
MIN_HOLD_MINUTES = 30
MAX_HOLD_MINUTES = 180
ROUND_TRIP_FRICTION_POINTS = 0.08
CONDOR_DELTAS = (0.15, 0.20, 0.25)
WIDTHS = {"SPXW": (5.0, 10.0, 20.0), "QQQ": (1.0, 2.0, 5.0), "SPY": (1.0, 2.0, 5.0)}
FLY_WIDTHS = {"SPXW": (10.0, 20.0), "QQQ": (2.0, 5.0), "SPY": (2.0, 5.0)}
EXIT_RULES = {
    "PT25_SL100": (0.25, 1.00),
    "PT50_SL100": (0.50, 1.00),
    "PT50_SL200": (0.50, 2.00),
    "TIME180": (None, None),
}
KEY_COLUMNS = ["qdt", "right", "strike"]
PRICE_COLUMNS = ["bid", "ask"]


@dataclass(frozen=True)
class Structure:
    structure_id: str
    kind: str
    short_delta: float
    width: float
    short_call_strike: float
    short_put_strike: float
    long_call_strike: float
    long_put_strike: float
    entry_credit: float
    max_risk_points: float


def sha256_file(path: str | Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _strict_bool(value: object) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
        return value.strip().lower() == "true"
    raise ValueError(f"not a strict boolean: {value!r}")


def load_source_index(native_index: Path, complement_index: Path) -> pd.DataFrame:
    frames = []
    for origin, path in (("native_backfill", native_index), ("native_complement", complement_index)):
        frame = pd.read_csv(path, dtype={"trade_date": str})
        required = {
            "ticker",
            "trade_date",
            "greeks_path",
            "greeks_sha256",
            "quotes_path",
            "quotes_sha256",
            "stored_timestamp_key_coverage_exact",
            "missing_stored_key_rows",
        }
        missing = sorted(required.difference(frame.columns))
        if missing:
            raise KeyError(f"{path} missing source-index columns: {missing}")
        frame = frame.copy()
        frame["origin"] = origin
        frame["trade_date"] = frame["trade_date"].str.replace(r"\D", "", regex=True).str[:8]
        if not frame["stored_timestamp_key_coverage_exact"].map(_strict_bool).all():
            raise AssertionError(f"{path} contains a non-exact timestamp-key session")
        if not pd.to_numeric(frame["missing_stored_key_rows"], errors="raise").eq(0).all():
            raise AssertionError(f"{path} contains missing stored Greek keys")
        frames.append(frame)
    out = pd.concat(frames, ignore_index=True)
    if out.duplicated(["ticker", "trade_date"]).any():
        duplicate = out.loc[out.duplicated(["ticker", "trade_date"], keep=False), ["ticker", "trade_date"]]
        raise AssertionError(f"source indexes are not disjoint: {duplicate.head().to_dict('records')}")
    return out.sort_values(["ticker", "trade_date"], kind="stable").reset_index(drop=True)


def validate_seals(native_seal: Path, complement_seal: Path, native_index: Path, complement_index: Path) -> dict:
    native = json.loads(native_seal.read_text(encoding="utf-8"))
    complement = json.loads(complement_seal.read_text(encoding="utf-8"))
    expected = (
        (native, "wall_native_quote_sidecar_seal_v1", "PASS_NATIVE_TIMESTAMP_BACKFILL", 1441),
        (complement, "wall_quote_size_native_complement_seal_v1", "PASS_QSIZE_NATIVE_COMPLEMENT", 1078),
    )
    for payload, schema, status, sessions in expected:
        if payload.get("schema") != schema or payload.get("status") != status:
            raise AssertionError(f"invalid sealed quote source: expected {schema}/{status}")
        observed_sessions = int(payload.get("fallback_sessions", payload.get("sessions", -1)))
        if observed_sessions != sessions or bool(payload.get("holdout_2026_used", True)):
            raise AssertionError("sealed quote source violates frozen pre-2026 coverage")
        if not bool(payload.get("outcome_free", False)) or bool(payload.get("production_modified", True)):
            raise AssertionError("sealed quote source violates outcome-free/production provenance")
    if native.get("index_sha256") != sha256_file(native_index):
        raise AssertionError("native index hash differs from its seal")
    if complement.get("index_sha256") != sha256_file(complement_index):
        raise AssertionError("complement index hash differs from its seal")
    return {"native": native, "complement": complement}


def valid_quotes(frame: pd.DataFrame, *, short: bool = False) -> pd.Series:
    bid = pd.to_numeric(frame["bid"], errors="coerce")
    ask = pd.to_numeric(frame["ask"], errors="coerce")
    valid = np.isfinite(bid) & np.isfinite(ask) & (bid >= 0.0) & (ask > 0.0) & (bid <= ask)
    if short:
        valid &= bid > 0.0
    return pd.Series(valid, index=frame.index)


def normalize_greeks(frame: pd.DataFrame, ticker: str, day: str) -> pd.DataFrame:
    required = {"symbol", "expiration", "right", "strike", "delta", "bid", "ask", "underlying_timestamp"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise KeyError(f"Greek source missing columns: {missing}")
    time_col = "timestamp" if "timestamp" in frame.columns else "underlying_timestamp"
    out = frame.copy()
    out["symbol"] = out["symbol"].astype(str).str.upper()
    out["expiration"] = out["expiration"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    out["right"] = out["right"].astype(str).str.upper().replace({"CALL": "C", "PUT": "P"})
    out["qdt"] = pd.to_datetime(out[time_col], errors="coerce")
    underlying_dt = pd.to_datetime(out["underlying_timestamp"], errors="coerce")
    for column in ("strike", "delta", "bid", "ask"):
        out[column] = pd.to_numeric(out[column], errors="coerce")
    out = out.loc[out["symbol"].eq(ticker) & out["expiration"].eq(day)].copy()
    underlying_dt = underlying_dt.loc[out.index]
    if time_col == "timestamp" and not out["qdt"].eq(underlying_dt).all():
        raise AssertionError(f"{ticker} {day}: native Greek and underlying clocks differ")
    if out.empty or out["qdt"].isna().any():
        raise AssertionError(f"{ticker} {day}: empty or invalid Greek clock")
    if not (out["qdt"].dt.second.eq(0) & out["qdt"].dt.microsecond.eq(0)).all():
        raise AssertionError(f"{ticker} {day}: non-minute Greek timestamps")
    start = pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} {ENTRY_TIME}")
    end = start + pd.Timedelta(minutes=MAX_HOLD_MINUTES)
    out = out.loc[out["qdt"].between(start, end, inclusive="both")].copy()
    if out.empty or out.duplicated(KEY_COLUMNS).any():
        raise AssertionError(f"{ticker} {day}: empty or duplicate execution keys")
    return out.sort_values(KEY_COLUMNS, kind="stable").reset_index(drop=True)


def normalize_native_clock(frame: pd.DataFrame, ticker: str, day: str) -> pd.DataFrame:
    required = {"symbol", "expiration", "timestamp", "right", "strike"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise KeyError(f"native clock source missing columns: {missing}")
    out = frame.copy()
    out["symbol"] = out["symbol"].astype(str).str.upper()
    out["expiration"] = out["expiration"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    out["right"] = out["right"].astype(str).str.upper().replace({"CALL": "C", "PUT": "P"})
    out["qdt"] = pd.to_datetime(out["timestamp"], errors="coerce")
    out["strike"] = pd.to_numeric(out["strike"], errors="coerce")
    out = out.loc[out["symbol"].eq(ticker) & out["expiration"].eq(day), KEY_COLUMNS]
    if out.empty or out.isna().any().any() or out.duplicated(KEY_COLUMNS).any():
        raise AssertionError(f"{ticker} {day}: invalid native clock bridge")
    return out.sort_values(KEY_COLUMNS, kind="stable").reset_index(drop=True)


def assert_clock_coverage(greeks: pd.DataFrame, native_clock: pd.DataFrame, ticker: str, day: str) -> None:
    native_end = native_clock["qdt"].max()
    execution_window = greeks.loc[greeks["qdt"] <= native_end, KEY_COLUMNS]
    shared = execution_window.merge(native_clock, on=KEY_COLUMNS, how="left", indicator=True)
    missing = int(shared["_merge"].ne("both").sum())
    if missing:
        raise AssertionError(f"{ticker} {day}: native clock misses {missing} execution-window Greek keys")


def _relative_spread(frame: pd.DataFrame) -> pd.Series:
    mid = (frame["bid"] + frame["ask"]) / 2.0
    return (frame["ask"] - frame["bid"]) / mid.clip(lower=0.01)


def select_delta_leg(entry: pd.DataFrame, right: str, target: float) -> pd.Series | None:
    candidates = entry.loc[entry["right"].eq(right) & valid_quotes(entry, short=True)].copy()
    candidates = candidates.loc[np.isfinite(candidates["delta"])]
    if candidates.empty:
        return None
    candidates["delta_error"] = (candidates["delta"].abs() - target).abs()
    candidates["relative_spread"] = _relative_spread(candidates)
    candidates = candidates.sort_values(["delta_error", "relative_spread", "strike"], kind="stable")
    return candidates.iloc[0]


def select_common_fly_strike(entry: pd.DataFrame) -> tuple[pd.Series, pd.Series] | None:
    valid = entry.loc[valid_quotes(entry, short=True) & np.isfinite(entry["delta"])].copy()
    calls = valid.loc[valid["right"].eq("C")].set_index("strike", drop=False)
    puts = valid.loc[valid["right"].eq("P")].set_index("strike", drop=False)
    strikes = calls.index.intersection(puts.index)
    if strikes.empty:
        return None
    pairs = pd.DataFrame({"strike": strikes.astype(float)})
    pairs["delta_error"] = [
        abs(abs(float(calls.loc[strike, "delta"])) - 0.50)
        + abs(abs(float(puts.loc[strike, "delta"])) - 0.50)
        for strike in strikes
    ]
    pairs["relative_spread"] = [
        float(_relative_spread(calls.loc[[strike]]).iloc[0] + _relative_spread(puts.loc[[strike]]).iloc[0])
        for strike in strikes
    ]
    best = pairs.sort_values(["delta_error", "relative_spread", "strike"], kind="stable").iloc[0]
    strike = float(best["strike"])
    return calls.loc[strike], puts.loc[strike]


def _exact_long(entry: pd.DataFrame, right: str, strike: float) -> pd.Series | None:
    rows = entry.loc[entry["right"].eq(right) & np.isclose(entry["strike"], strike, rtol=0.0, atol=1e-9)]
    rows = rows.loc[valid_quotes(rows)]
    if len(rows) != 1:
        return None
    return rows.iloc[0]


def build_structure(
    entry: pd.DataFrame,
    ticker: str,
    *,
    kind: str,
    short_delta: float,
    width: float,
) -> Structure | None:
    if kind == "IC":
        short_call = select_delta_leg(entry, "C", short_delta)
        short_put = select_delta_leg(entry, "P", short_delta)
        if short_call is None or short_put is None:
            return None
    elif kind == "IF":
        pair = select_common_fly_strike(entry)
        if pair is None:
            return None
        short_call, short_put = pair
    else:
        raise ValueError(f"unknown structure kind: {kind}")
    sc = float(short_call["strike"])
    sp = float(short_put["strike"])
    if sp > sc + 1e-9:
        return None
    lc = sc + width
    lp = sp - width
    long_call = _exact_long(entry, "C", lc)
    long_put = _exact_long(entry, "P", lp)
    if long_call is None or long_put is None:
        return None
    credit = (
        float(short_call["bid"])
        + float(short_put["bid"])
        - float(long_call["ask"])
        - float(long_put["ask"])
    )
    max_risk = width - credit + ROUND_TRIP_FRICTION_POINTS
    if not (np.isfinite(credit) and 0.0 < credit < width and max_risk > 0.0):
        return None
    delta_tag = int(round(short_delta * 100))
    width_tag = f"{width:g}".replace(".", "p")
    return Structure(
        structure_id=f"{kind}_d{delta_tag:02d}_w{width_tag}",
        kind=kind,
        short_delta=short_delta,
        width=width,
        short_call_strike=sc,
        short_put_strike=sp,
        long_call_strike=lc,
        long_put_strike=lp,
        entry_credit=credit,
        max_risk_points=max_risk,
    )


def close_path(greeks: pd.DataFrame, structure: Structure, entry_dt: pd.Timestamp, scheduled_exit: pd.Timestamp) -> pd.DataFrame:
    specs = (
        ("short_call", "C", structure.short_call_strike),
        ("short_put", "P", structure.short_put_strike),
        ("long_call", "C", structure.long_call_strike),
        ("long_put", "P", structure.long_put_strike),
    )
    merged: pd.DataFrame | None = None
    for name, right, strike in specs:
        leg = greeks.loc[
            greeks["right"].eq(right) & np.isclose(greeks["strike"], strike, rtol=0.0, atol=1e-9),
            ["qdt", "bid", "ask"],
        ].copy()
        leg = leg.loc[valid_quotes(leg)].rename(columns={"bid": f"{name}_bid", "ask": f"{name}_ask"})
        merged = leg if merged is None else merged.merge(leg, on="qdt", how="inner", validate="one_to_one")
    if merged is None:
        return pd.DataFrame()
    start = entry_dt + pd.Timedelta(minutes=MIN_HOLD_MINUTES)
    merged = merged.loc[merged["qdt"].between(start, scheduled_exit, inclusive="both")].copy()
    merged["close_debit"] = (
        merged["short_call_ask"]
        + merged["short_put_ask"]
        - merged["long_call_bid"]
        - merged["long_put_bid"]
    )
    merged = merged.loc[np.isfinite(merged["close_debit"]) & (merged["close_debit"] >= 0.0)].copy()
    merged["gross_pnl_points"] = structure.entry_credit - merged["close_debit"]
    return merged.sort_values("qdt", kind="stable").reset_index(drop=True)


def apply_exit_rule(
    path: pd.DataFrame,
    structure: Structure,
    scheduled_exit: pd.Timestamp,
    exit_rule: str,
) -> dict | None:
    if path.empty or not path["qdt"].eq(scheduled_exit).any():
        return None
    profit_fraction, stop_multiple = EXIT_RULES[exit_rule]
    selected = None
    reason = "time"
    if profit_fraction is not None and stop_multiple is not None:
        take = structure.entry_credit * profit_fraction
        stop = -structure.entry_credit * stop_multiple
        triggered = path.loc[(path["gross_pnl_points"] >= take) | (path["gross_pnl_points"] <= stop)]
        if not triggered.empty:
            selected = triggered.iloc[0]
            reason = "profit_target" if float(selected["gross_pnl_points"]) >= take else "stop"
    if selected is None:
        selected = path.loc[path["qdt"].eq(scheduled_exit)].iloc[0]
    net_points = float(selected["gross_pnl_points"]) - ROUND_TRIP_FRICTION_POINTS
    return {
        "exit_dt": selected["qdt"],
        "exit_reason": reason,
        "close_debit": float(selected["close_debit"]),
        "gross_pnl_points": float(selected["gross_pnl_points"]),
        "net_pnl_points": net_points,
        "net_pnl_R": net_points / structure.max_risk_points,
    }


def build_session_candidates(greeks: pd.DataFrame, native_clock: pd.DataFrame, ticker: str, day: str) -> tuple[list[dict], list[dict]]:
    entry_dt = pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} {ENTRY_TIME}")
    native_end = native_clock["qdt"].max()
    scheduled_exit = min(entry_dt + pd.Timedelta(minutes=MAX_HOLD_MINUTES), native_end)
    if scheduled_exit < entry_dt + pd.Timedelta(minutes=MIN_HOLD_MINUTES):
        raise AssertionError(f"{ticker} {day}: native clock cannot support the minimum hold")
    entry = greeks.loc[greeks["qdt"].eq(entry_dt)].copy()
    structures: list[Structure] = []
    for delta in CONDOR_DELTAS:
        for width in WIDTHS[ticker]:
            structure = build_structure(entry, ticker, kind="IC", short_delta=delta, width=width)
            if structure is not None:
                structures.append(structure)
    for width in FLY_WIDTHS[ticker]:
        structure = build_structure(entry, ticker, kind="IF", short_delta=0.50, width=width)
        if structure is not None:
            structures.append(structure)
    trades: list[dict] = []
    unresolved: list[dict] = []
    for structure in structures:
        path = close_path(greeks, structure, entry_dt, scheduled_exit)
        for exit_rule in EXIT_RULES:
            result = apply_exit_rule(path, structure, scheduled_exit, exit_rule)
            profile_id = f"{structure.structure_id}__{exit_rule}"
            if result is None:
                unresolved.append({"ticker": ticker, "trade_date": day, "profile_id": profile_id})
                continue
            result["hold_minutes"] = int((pd.Timestamp(result["exit_dt"]) - entry_dt).total_seconds() // 60)
            trades.append(
                {
                    "ticker": ticker,
                    "trade_date": day,
                    "month": day[:6],
                    "entry_dt": entry_dt,
                    "scheduled_exit_dt": scheduled_exit,
                    "profile_id": profile_id,
                    "exit_rule": exit_rule,
                    **asdict(structure),
                    **result,
                }
            )
    return trades, unresolved


def profit_factor(values: Iterable[float]) -> float:
    array = np.asarray(list(values), dtype=float)
    gross_profit = float(array[array > 0.0].sum())
    gross_loss = float(-array[array < 0.0].sum())
    if gross_loss == 0.0:
        return math.inf if gross_profit > 0.0 else 0.0
    return gross_profit / gross_loss


def summarize_trades(frame: pd.DataFrame) -> dict:
    pnl = frame["net_pnl_R"].to_numpy(dtype=float) if not frame.empty else np.array([], dtype=float)
    gross_profit = float(pnl[pnl > 0.0].sum())
    top5 = float(np.sort(pnl[pnl > 0.0])[-5:].sum()) if np.any(pnl > 0.0) else 0.0
    curve = np.cumsum(pnl)
    peak = np.maximum.accumulate(np.r_[0.0, curve])
    drawdown = np.r_[0.0, curve] - peak
    return {
        "trades": int(len(frame)),
        "win_rate": float(np.mean(pnl > 0.0)) if len(pnl) else 0.0,
        "profit_factor": profit_factor(pnl),
        "net_pnl_R": float(pnl.sum()),
        "top5_gross_profit_fraction": float(top5 / gross_profit) if gross_profit > 0.0 else math.inf,
        "max_drawdown_R": float(drawdown.min()) if len(drawdown) else 0.0,
    }


def monthly_candidate_stats(candidates: pd.DataFrame, train_months: list[str]) -> pd.DataFrame:
    train = candidates.loc[candidates["month"].isin(train_months)].copy()
    rows = []
    for profile_id, group in train.groupby("profile_id", sort=True):
        month_rows = []
        for month, month_group in group.groupby("month", sort=True):
            metrics = summarize_trades(month_group)
            month_rows.append({"month": month, **metrics})
        monthly = pd.DataFrame(month_rows)
        if monthly.empty:
            continue
        aggregate = summarize_trades(group)
        complete_months = int(monthly["month"].isin(train_months).sum())
        min_trades = int(monthly["trades"].min()) if complete_months == len(train_months) else 0
        positive_months = int((monthly["net_pnl_R"] > 0.0).sum())
        coverage_eligible = complete_months == len(train_months) and min_trades >= 13
        robust_eligible = (
            coverage_eligible
            and aggregate["net_pnl_R"] > 0.0
            and aggregate["profit_factor"] > 1.0
            and positive_months >= 8
        )
        rows.append(
            {
                "profile_id": profile_id,
                "complete_months": complete_months,
                "min_month_trades": min_trades,
                "positive_months": positive_months,
                "monthly_pnl_q25": float(monthly["net_pnl_R"].quantile(0.25)),
                "monthly_pnl_median": float(monthly["net_pnl_R"].median()),
                "aggregate_profit_factor": aggregate["profit_factor"],
                "aggregate_win_rate": aggregate["win_rate"],
                "aggregate_pnl_R": aggregate["net_pnl_R"],
                "coverage_eligible": coverage_eligible,
                "robust_eligible": robust_eligible,
            }
        )
    return pd.DataFrame(rows)


def select_walkforward(candidates: pd.DataFrame, evaluation_months: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    selected_trades = []
    selections = []
    for ticker in TICKERS:
        ticker_frame = candidates.loc[candidates["ticker"].eq(ticker)].copy()
        for evaluation_month in evaluation_months:
            evaluation_period = pd.Period(evaluation_month, freq="M")
            train_months = [str(evaluation_period - lag).replace("-", "") for lag in range(12, 0, -1)]
            stats = monthly_candidate_stats(ticker_frame, train_months)
            eligible = stats.loc[stats["robust_eligible"]].copy()
            selection_mode = "robust_eligible"
            if eligible.empty:
                eligible = stats.loc[stats["coverage_eligible"]].copy()
                selection_mode = "coverage_fallback"
            if eligible.empty:
                raise AssertionError(f"{ticker} {evaluation_month}: no profile has frozen training coverage")
            eligible = eligible.sort_values(
                ["monthly_pnl_q25", "monthly_pnl_median", "aggregate_profit_factor", "profile_id"],
                ascending=[False, False, False, True],
                kind="stable",
            )
            chosen = eligible.iloc[0]
            profile_id = str(chosen["profile_id"])
            fold_trades = ticker_frame.loc[
                ticker_frame["month"].eq(evaluation_month) & ticker_frame["profile_id"].eq(profile_id)
            ].copy()
            selected_trades.append(fold_trades)
            selections.append(
                {
                    "ticker": ticker,
                    "evaluation_month": evaluation_month,
                    "train_start_month": train_months[0],
                    "train_end_month": train_months[-1],
                    "profile_id": profile_id,
                    "selection_mode": selection_mode,
                    **chosen.to_dict(),
                    "evaluation_trades": int(len(fold_trades)),
                }
            )
    return pd.concat(selected_trades, ignore_index=True), pd.DataFrame(selections)


def evaluate_gate(selected: pd.DataFrame, evaluation_months: list[str]) -> tuple[pd.DataFrame, dict]:
    monthly_rows = []
    ticker_metrics = {}
    for ticker in TICKERS:
        ticker_frame = selected.loc[selected["ticker"].eq(ticker)].sort_values(["entry_dt", "exit_dt"])
        aggregate = summarize_trades(ticker_frame)
        month_metrics = []
        for month in evaluation_months:
            metrics = summarize_trades(ticker_frame.loc[ticker_frame["month"].eq(month)])
            row = {"ticker": ticker, "month": month, **metrics}
            monthly_rows.append(row)
            month_metrics.append(row)
        min_month_trades = min(row["trades"] for row in month_metrics)
        positive_months = sum(row["net_pnl_R"] > 0.0 for row in month_metrics)
        passed = (
            aggregate["win_rate"] > 0.45
            and aggregate["profit_factor"] > 1.20
            and min_month_trades >= 13
            and positive_months == len(evaluation_months)
        )
        ticker_metrics[ticker] = {
            **aggregate,
            "min_month_trades": min_month_trades,
            "positive_months": positive_months,
            "evaluated_months": len(evaluation_months),
            "gate_pass": passed,
        }
    return pd.DataFrame(monthly_rows), {
        "ticker_metrics": ticker_metrics,
        "joint_gate_pass": all(metrics["gate_pass"] for metrics in ticker_metrics.values()),
    }


def _read_session(row: pd.Series, verify_hashes: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    ticker = str(row["ticker"])
    day = str(row["trade_date"])
    greeks_path = Path(str(row["greeks_path"]))
    quotes_path = Path(str(row["quotes_path"]))
    if verify_hashes:
        if sha256_file(greeks_path) != str(row["greeks_sha256"]):
            raise AssertionError(f"{ticker} {day}: Greek hash mismatch")
        if sha256_file(quotes_path) != str(row["quotes_sha256"]):
            raise AssertionError(f"{ticker} {day}: native quote hash mismatch")
    available = set(pq.ParquetFile(greeks_path).schema_arrow.names)
    columns = [
        column
        for column in (
            "symbol",
            "expiration",
            "timestamp",
            "underlying_timestamp",
            "right",
            "strike",
            "delta",
            "bid",
            "ask",
        )
        if column in available
    ]
    greeks = normalize_greeks(pd.read_parquet(greeks_path, columns=columns), ticker, day)
    clock = normalize_native_clock(
        pd.read_parquet(quotes_path, columns=["symbol", "expiration", "timestamp", "right", "strike"]),
        ticker,
        day,
    )
    assert_clock_coverage(greeks, clock, ticker, day)
    return greeks, clock


def run(args: argparse.Namespace) -> dict:
    if args.start_date != FROZEN_START_DATE or args.end_date != FROZEN_END_DATE:
        raise ValueError("V1 accepts only its frozen 2024-01-01..2025-12-31 scope")
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"immutable output already exists: {output}")
    seals = validate_seals(
        Path(args.native_seal), Path(args.complement_seal), Path(args.native_index), Path(args.complement_index)
    )
    source_index = load_source_index(Path(args.native_index), Path(args.complement_index))
    source_index = source_index.loc[
        source_index["ticker"].isin(TICKERS)
        & source_index["trade_date"].between(args.start_date, args.end_date, inclusive="both")
    ].copy()
    if source_index.empty:
        raise AssertionError("no sealed sessions in requested scope")
    session_counts = source_index.groupby("ticker", sort=True).size().to_dict()
    if session_counts != {ticker: FROZEN_SESSIONS_PER_TICKER for ticker in TICKERS}:
        raise AssertionError(f"frozen source-session census mismatch: {session_counts}")
    all_trades: list[dict] = []
    unresolved: list[dict] = []
    for position, (_, row) in enumerate(source_index.iterrows(), start=1):
        greeks, clock = _read_session(row, verify_hashes=True)
        trades, session_unresolved = build_session_candidates(
            greeks, clock, str(row["ticker"]), str(row["trade_date"])
        )
        all_trades.extend(trades)
        unresolved.extend(session_unresolved)
        if position % 50 == 0 or position == len(source_index):
            print(f"sessions={position}/{len(source_index)} candidates={len(all_trades)} unresolved={len(unresolved)}", flush=True)
    if unresolved:
        sample = unresolved[:10]
        raise AssertionError(f"entry-resolved profiles contain unresolved scheduled exits: {sample}")
    candidates = pd.DataFrame(all_trades)
    if candidates.empty:
        raise AssertionError("candidate trade ledger is empty")
    evaluation_months = [f"2025{month:02d}" for month in range(1, 13)]
    selected, selections = select_walkforward(candidates, evaluation_months)
    monthly, gate = evaluate_gate(selected, evaluation_months)
    output.mkdir(parents=True, exist_ok=False)
    candidates.to_parquet(output / "candidate_trade_ledger.parquet", index=False)
    selected.to_parquet(output / "selected_trade_ledger.parquet", index=False)
    selections.to_csv(output / "selected_folds.csv", index=False)
    monthly.to_csv(output / "monthly_metrics.csv", index=False)
    source_index.to_csv(output / "source_sessions.csv", index=False)
    metrics = {
        "schema": "short_premium_defined_risk_v1_metrics",
        "status": "PASS_PRE2026_GATE" if gate["joint_gate_pass"] else "CLOSED_PRE2026_GATE",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": {"start_date": args.start_date, "end_date": args.end_date, "evaluation_months": evaluation_months},
        "execution": {
            "entry_time": ENTRY_TIME,
            "min_hold_minutes": MIN_HOLD_MINUTES,
            "max_hold_minutes": MAX_HOLD_MINUTES,
            "round_trip_friction_points": ROUND_TRIP_FRICTION_POINTS,
            "entry_fill": "short_bid_minus_long_ask",
            "exit_fill": "short_ask_minus_long_bid",
        },
        "candidate_rows": int(len(candidates)),
        "selected_rows": int(len(selected)),
        "source_sessions": int(len(source_index)),
        "source_sessions_by_ticker": session_counts,
        **gate,
    }
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")
    provenance = {
        "schema": "short_premium_defined_risk_v1_provenance",
        "predeclaration_path": str(PREDECLARATION.relative_to(REPO_ROOT)),
        "predeclaration_sha256": sha256_file(PREDECLARATION),
        "runner_path": str(Path(__file__).resolve().relative_to(REPO_ROOT)),
        "runner_sha256": sha256_file(__file__),
        "native_index_sha256": sha256_file(args.native_index),
        "complement_index_sha256": sha256_file(args.complement_index),
        "native_seal_status": seals["native"]["status"],
        "complement_seal_status": seals["complement"]["status"],
        "historical_provenance": "CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION",
        "sidecar_prices_used": False,
        "original_greek_bid_ask_used": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "file_hash_validation": True,
    }
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )
    print(json.dumps(metrics, indent=2, sort_keys=True, allow_nan=False))
    return metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", default=FROZEN_START_DATE)
    parser.add_argument("--end-date", default=FROZEN_END_DATE)
    parser.add_argument("--native-index", default=str(DEFAULT_NATIVE_INDEX))
    parser.add_argument("--complement-index", default=str(DEFAULT_COMPLEMENT_INDEX))
    parser.add_argument("--native-seal", default=str(DEFAULT_NATIVE_SEAL))
    parser.add_argument("--complement-seal", default=str(DEFAULT_COMPLEMENT_SEAL))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
