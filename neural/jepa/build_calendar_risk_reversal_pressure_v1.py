#!/usr/bin/env python3
"""Build the outcome-free 2023 CALENDAR_RISK_REVERSAL_PRESSURE_V1 view."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from neural.jepa.surface_flow_features import normalize_right, validate_underlying_session  # noqa: E402


PROJECT_ROOT = SCRIPT_REPO_ROOT
TICKERS = ("QQQ", "SPXW", "SPY")
START_DATE = "20230101"
END_DATE = "20231231"
CLOCKS = ("10:30:00", "10:35:00")
TARGET_ABS_DELTA = 0.25
MAX_DELTA_GAP = 0.10
MIN_ANNUAL_COVERAGE = 0.90
MIN_DISTINCT_STATES = 50
MAX_ZERO_FRACTION = 0.995
MIN_MONTH_EVENTS_EXCLUSIVE = 12
HALF_DAYS = frozenset({"20230703", "20231124"})
PREDECLARATION = PROJECT_ROOT / (
    "research_papers/JEPA/CALENDAR_RISK_REVERSAL_PRESSURE_V1_PREDECLARATION.md"
)
DEFAULT_OPTIONS_ROOT = Path("D:/ThetaData/data_options")
DEFAULT_UNDERLYING_ROOT = Path("D:/ThetaData/data_underlying_derived")
DEFAULT_OUTPUT = PROJECT_ROOT / "tmp/calendar_risk_reversal_pressure_v1_data_gate_202301_202312_v1"

KEY_COLUMNS = ("symbol", "expiration", "trade_date", "timestamp", "strike", "right")
GREEK_COLUMNS = (*KEY_COLUMNS, "delta", "bid", "ask")
IV_COLUMNS = (*KEY_COLUMNS, "bid", "ask", "bid_implied_vol", "ask_implied_vol")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dataframe_digest(frame: pd.DataFrame) -> str:
    payload = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def current_git_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def tracked_clean(path: Path, label: str) -> None:
    relative = path.resolve().relative_to(PROJECT_ROOT).as_posix()
    subprocess.run(
        ["git", "ls-files", "--error-unmatch", relative],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", relative],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if dirty:
        raise AssertionError(f"{label} must be committed and clean: {dirty}")


def canonical_date(value: object) -> str:
    digits = "".join(character for character in str(value) if character.isdigit())
    if len(digits) < 8:
        raise ValueError(f"invalid date: {value!r}")
    return digits[:8]


def parse_option_filename(path: Path, expected_kind: str) -> tuple[str, str]:
    parts = path.stem.split("_")
    if len(parts) < 4 or parts[-1].lower() != expected_kind:
        raise ValueError(f"unexpected option filename: {path.name}")
    expiration = canonical_date(parts[-3])
    trade_date = canonical_date(parts[-2])
    return expiration, trade_date


def option_file_map(options_root: Path, ticker: str, kind: str) -> dict[tuple[str, str], Path]:
    mapping: dict[tuple[str, str], Path] = {}
    for path in sorted((options_root / ticker / kind / "2023").glob("*/*.parquet")):
        expiration, trade_date = parse_option_filename(path, kind)
        if START_DATE <= trade_date <= END_DATE:
            key = (trade_date, expiration)
            if key in mapping:
                raise AssertionError(f"duplicate {kind} source key: {ticker} {key}")
            mapping[key] = path
    return mapping


def discover_sessions(options_root: Path, underlying_root: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for ticker in TICKERS:
        greeks = option_file_map(options_root, ticker, "greeks")
        iv = option_file_map(options_root, ticker, "iv")
        if set(greeks) != set(iv):
            raise AssertionError(f"Greek/IV inventory mismatch for {ticker}")
        dates = sorted(trade_date for trade_date, expiration in greeks if trade_date == expiration)
        if not dates:
            raise AssertionError(f"no exact-0DTE sessions for {ticker}")
        for trade_date in dates:
            back_expiries = sorted(
                expiration
                for candidate_date, expiration in greeks
                if candidate_date == trade_date and expiration > trade_date
            )
            if not back_expiries:
                raise AssertionError(f"missing next expiration: {ticker} {trade_date}")
            back_expiration = back_expiries[0]
            underlying_path = (
                underlying_root
                / ticker
                / trade_date[:4]
                / trade_date[4:6]
                / f"{ticker}_{trade_date}.parquet"
            )
            if not underlying_path.is_file():
                raise FileNotFoundError(underlying_path)
            rows.append(
                {
                    "ticker": ticker,
                    "trade_date": trade_date,
                    "month": trade_date[:6],
                    "front_expiration": trade_date,
                    "back_expiration": back_expiration,
                    "front_dte_calendar": 0,
                    "back_dte_calendar": int(
                        (pd.Timestamp(back_expiration) - pd.Timestamp(trade_date)).days
                    ),
                    "calendar_half_day": trade_date in HALF_DAYS,
                    "economic_clock_eligible": trade_date not in HALF_DAYS,
                    "front_greeks_path": str(greeks[(trade_date, trade_date)].resolve()),
                    "front_iv_path": str(iv[(trade_date, trade_date)].resolve()),
                    "back_greeks_path": str(greeks[(trade_date, back_expiration)].resolve()),
                    "back_iv_path": str(iv[(trade_date, back_expiration)].resolve()),
                    "underlying_path": str(underlying_path.resolve()),
                }
            )
    sessions = pd.DataFrame(rows).sort_values(["ticker", "trade_date"], kind="stable").reset_index(drop=True)
    if (
        sessions.empty
        or sessions.duplicated(["ticker", "trade_date"]).any()
        or set(sessions["ticker"]) != set(TICKERS)
        or not sessions["trade_date"].between(START_DATE, END_DATE).all()
        or sessions["trade_date"].str.startswith("2024").any()
    ):
        raise AssertionError("discovered session universe violates frozen 2023 scope")
    ticker_counts = sessions.groupby("ticker", observed=True).size()
    if ticker_counts.nunique() != 1:
        raise AssertionError(f"ticker session counts differ: {ticker_counts.to_dict()}")
    return sessions


def target_datetimes(trade_date: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    day = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}"
    return tuple(pd.Timestamp(f"{day} {clock}") for clock in CLOCKS)  # type: ignore[return-value]


def target_timestamp_strings(trade_date: str) -> list[str]:
    values: list[str] = []
    for timestamp in target_datetimes(trade_date):
        base = timestamp.strftime("%Y-%m-%dT%H:%M:%S")
        values.extend((base, f"{base}.000"))
    return values


def validate_native_schema(path: Path, required: tuple[str, ...], kind: str) -> None:
    names = set(pq.ParquetFile(path).schema_arrow.names)
    missing = sorted(set(required).difference(names))
    if missing:
        raise KeyError(f"{kind} source missing required native fields {missing}: {path}")


def read_target_source(
    path: Path,
    *,
    kind: str,
    ticker: str,
    trade_date: str,
    expiration: str,
) -> pd.DataFrame:
    columns = GREEK_COLUMNS if kind == "greeks" else IV_COLUMNS
    validate_native_schema(path, columns, kind)
    frame = pd.read_parquet(
        path,
        columns=list(columns),
        filters=[("timestamp", "in", target_timestamp_strings(trade_date))],
    )
    if frame.empty:
        raise AssertionError(f"{kind} source has no rows at exact target clocks: {path}")
    output = frame.copy()
    output["symbol"] = output["symbol"].astype(str).str.upper().str.strip()
    output["expiration"] = output["expiration"].map(canonical_date)
    output["trade_date"] = output["trade_date"].map(canonical_date)
    output["timestamp"] = pd.to_datetime(output["timestamp"], errors="coerce")
    output["right"] = normalize_right(output["right"])
    numeric = ["strike", "bid", "ask"]
    numeric.extend(["delta"] if kind == "greeks" else ["bid_implied_vol", "ask_implied_vol"])
    for column in numeric:
        output[column] = pd.to_numeric(output[column], errors="coerce")
    times = set(target_datetimes(trade_date))
    if (
        output["timestamp"].isna().any()
        or set(output["timestamp"].unique()) != times
        or not output["symbol"].eq(ticker).all()
        or not output["trade_date"].eq(trade_date).all()
        or not output["expiration"].eq(expiration).all()
        or output.duplicated(list(KEY_COLUMNS)).any()
        or output[list(KEY_COLUMNS)].isna().any().any()
    ):
        raise AssertionError(f"{kind} source identity/native-clock contract failed: {path}")
    return output.sort_values(list(KEY_COLUMNS), kind="stable").reset_index(drop=True)


def join_greeks_iv(greeks: pd.DataFrame, iv: pd.DataFrame) -> pd.DataFrame:
    iv_renamed = iv.rename(
        columns={
            "bid": "iv_source_bid",
            "ask": "iv_source_ask",
        }
    )
    joined = greeks.merge(
        iv_renamed,
        on=list(KEY_COLUMNS),
        how="outer",
        indicator=True,
        validate="one_to_one",
    )
    if not joined["_merge"].eq("both").all() or len(joined) != len(greeks) or len(joined) != len(iv):
        raise AssertionError("Greek/IV exact key sets differ")
    for left, right in (("bid", "iv_source_bid"), ("ask", "iv_source_ask")):
        if not np.allclose(
            joined[left].to_numpy(dtype=np.float64),
            joined[right].to_numpy(dtype=np.float64),
            rtol=0.0,
            atol=1e-12,
            equal_nan=True,
        ):
            raise AssertionError(f"Greek/IV vintage {left} values differ")
    return joined.drop(columns=["_merge", "iv_source_bid", "iv_source_ask"])


def select_fixed_contract(
    chain: pd.DataFrame,
    *,
    right: str,
    spot_t0: float,
) -> dict[str, float]:
    t0, t1 = target_datetimes(str(chain["trade_date"].iloc[0]))
    first = chain.loc[chain["timestamp"].eq(t0) & chain["right"].eq(right)].copy()
    second = chain.loc[chain["timestamp"].eq(t1) & chain["right"].eq(right)].copy()
    persistent = first.merge(
        second,
        on=["symbol", "expiration", "trade_date", "strike", "right"],
        how="inner",
        suffixes=("_t0", "_t1"),
        validate="one_to_one",
    )
    target_delta = TARGET_ABS_DELTA if right == "CALL" else -TARGET_ABS_DELTA
    persistent["delta_gap"] = (persistent["delta_t0"] - target_delta).abs()
    persistent["abs_log_moneyness"] = np.abs(np.log(persistent["strike"] / float(spot_t0)))
    valid = (
        persistent["delta_gap"].le(MAX_DELTA_GAP)
        & persistent["bid_t0"].gt(0.0)
        & persistent["ask_t0"].ge(persistent["bid_t0"])
        & persistent["bid_t1"].gt(0.0)
        & persistent["ask_t1"].ge(persistent["bid_t1"])
    )
    for suffix in ("t0", "t1"):
        valid &= (
            persistent[f"bid_implied_vol_{suffix}"].gt(0.0)
            & persistent[f"ask_implied_vol_{suffix}"].ge(
                persistent[f"bid_implied_vol_{suffix}"]
            )
            & persistent[f"ask_implied_vol_{suffix}"].lt(5.0)
        )
    candidates = persistent.loc[valid].sort_values(
        ["delta_gap", "abs_log_moneyness", "strike"],
        kind="stable",
    )
    if candidates.empty:
        raise AssertionError(f"no persistent signable {right} 25-delta contract")
    chosen = candidates.iloc[0]
    return {
        "strike": float(chosen["strike"]),
        "delta_t0": float(chosen["delta_t0"]),
        "delta_t1": float(chosen["delta_t1"]),
        "mid_iv_t0": float(
            0.5 * (chosen["bid_implied_vol_t0"] + chosen["ask_implied_vol_t0"])
        ),
        "mid_iv_t1": float(
            0.5 * (chosen["bid_implied_vol_t1"] + chosen["ask_implied_vol_t1"])
        ),
        "delta_gap_t0": float(chosen["delta_gap"]),
        "candidate_count": int(len(candidates)),
    }


def calculate_session_feature(
    *,
    ticker: str,
    trade_date: str,
    front_expiration: str,
    back_expiration: str,
    spot_t0: float,
    spot_t1: float,
    front_chain: pd.DataFrame,
    back_chain: pd.DataFrame,
) -> dict[str, Any]:
    selected: dict[str, dict[str, float]] = {}
    for expiry_role, chain in (("front", front_chain), ("back", back_chain)):
        for right in ("CALL", "PUT"):
            selected[f"{expiry_role}_{right.lower()}"] = select_fixed_contract(
                chain,
                right=right,
                spot_t0=spot_t0,
            )
    front_rr_t0 = selected["front_call"]["mid_iv_t0"] - selected["front_put"]["mid_iv_t0"]
    front_rr_t1 = selected["front_call"]["mid_iv_t1"] - selected["front_put"]["mid_iv_t1"]
    back_rr_t0 = selected["back_call"]["mid_iv_t0"] - selected["back_put"]["mid_iv_t0"]
    back_rr_t1 = selected["back_call"]["mid_iv_t1"] - selected["back_put"]["mid_iv_t1"]
    calendar_rr_t0 = front_rr_t0 - back_rr_t0
    calendar_rr_t1 = front_rr_t1 - back_rr_t1
    pressure = calendar_rr_t1 - calendar_rr_t0
    if not np.isfinite(pressure):
        raise AssertionError("calendar risk-reversal pressure is non-finite")
    output: dict[str, Any] = {
        "ticker": ticker,
        "trade_date": trade_date,
        "year": trade_date[:4],
        "month": trade_date[:6],
        "front_expiration": front_expiration,
        "back_expiration": back_expiration,
        "back_dte_calendar": int(
            (pd.Timestamp(back_expiration) - pd.Timestamp(trade_date)).days
        ),
        "spot_t0": float(spot_t0),
        "spot_t1": float(spot_t1),
        "front_rr_t0": float(front_rr_t0),
        "front_rr_t1": float(front_rr_t1),
        "back_rr_t0": float(back_rr_t0),
        "back_rr_t1": float(back_rr_t1),
        "calendar_rr_t0": float(calendar_rr_t0),
        "calendar_rr_t1": float(calendar_rr_t1),
        "calendar_rr_pressure": float(pressure),
    }
    for name, values in selected.items():
        for field, value in values.items():
            output[f"{name}_{field}"] = value
    return output


def process_session(record: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    ticker = str(record["ticker"])
    trade_date = str(record["trade_date"])
    underlying_raw = pd.read_parquet(str(record["underlying_path"]))
    underlying, underlying_audit = validate_underlying_session(
        underlying_raw,
        expected_ticker=ticker,
        expected_trade_date=trade_date,
    )
    indexed = underlying.set_index("bar_start")
    t0, t1 = target_datetimes(trade_date)
    spot_t0 = float(indexed.loc[t0, "open"])
    spot_t1 = float(indexed.loc[t1, "open"])
    chains: dict[str, pd.DataFrame] = {}
    source_rows: dict[str, int] = {}
    for role in ("front", "back"):
        expiration = str(record[f"{role}_expiration"])
        greeks = read_target_source(
            Path(str(record[f"{role}_greeks_path"])),
            kind="greeks",
            ticker=ticker,
            trade_date=trade_date,
            expiration=expiration,
        )
        iv = read_target_source(
            Path(str(record[f"{role}_iv_path"])),
            kind="iv",
            ticker=ticker,
            trade_date=trade_date,
            expiration=expiration,
        )
        source_rows[f"{role}_greek_target_rows"] = int(len(greeks))
        source_rows[f"{role}_iv_target_rows"] = int(len(iv))
        chains[role] = join_greeks_iv(greeks, iv)
    feature = calculate_session_feature(
        ticker=ticker,
        trade_date=trade_date,
        front_expiration=str(record["front_expiration"]),
        back_expiration=str(record["back_expiration"]),
        spot_t0=spot_t0,
        spot_t1=spot_t1,
        front_chain=chains["front"],
        back_chain=chains["back"],
    )
    feature.update(
        {
            "calendar_half_day": bool(record["calendar_half_day"]),
            "economic_clock_eligible": bool(record["economic_clock_eligible"]),
            "feature_valid": True,
            "invalid_reason": "",
        }
    )
    audit = {
        "ticker": ticker,
        "trade_date": trade_date,
        "feature_valid": True,
        "invalid_reason": "",
        **source_rows,
        "underlying_rows": int(underlying_audit["underlying_rows"]),
        "underlying_out_of_scope_invalid_rows": int(
            underlying_audit["underlying_out_of_scope_invalid_rows"]
        ),
    }
    return feature, audit


def invalid_result(record: dict[str, Any], error: Exception) -> tuple[dict[str, Any], dict[str, Any]]:
    reason = f"{type(error).__name__}: {error}"
    base = {
        "ticker": str(record["ticker"]),
        "trade_date": str(record["trade_date"]),
        "year": str(record["trade_date"])[:4],
        "month": str(record["trade_date"])[:6],
        "front_expiration": str(record["front_expiration"]),
        "back_expiration": str(record["back_expiration"]),
        "back_dte_calendar": int(record["back_dte_calendar"]),
        "calendar_half_day": bool(record["calendar_half_day"]),
        "economic_clock_eligible": bool(record["economic_clock_eligible"]),
        "feature_valid": False,
        "invalid_reason": reason,
    }
    return base, {
        "ticker": base["ticker"],
        "trade_date": base["trade_date"],
        "feature_valid": False,
        "invalid_reason": reason,
    }


def build_features(sessions: pd.DataFrame, workers: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    records = sessions.to_dict(orient="records")
    features: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        future_map = {executor.submit(process_session, record): record for record in records}
        for future in as_completed(future_map):
            record = future_map[future]
            try:
                feature, audit = future.result()
            except Exception as error:  # noqa: BLE001 - data gate preserves exact failure
                feature, audit = invalid_result(record, error)
            features.append(feature)
            audits.append(audit)
    feature_frame = pd.DataFrame(features).sort_values(["ticker", "trade_date"], kind="stable").reset_index(drop=True)
    audit_frame = pd.DataFrame(audits).sort_values(["ticker", "trade_date"], kind="stable").reset_index(drop=True)
    if len(feature_frame) != len(sessions) or feature_frame.duplicated(["ticker", "trade_date"]).any():
        raise AssertionError("feature output is not one-to-one with session universe")
    return feature_frame, audit_frame


def build_source_inventory(sessions: pd.DataFrame, workers: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for record in sessions.to_dict(orient="records"):
        for role in ("front", "back"):
            for kind in ("greeks", "iv"):
                path = Path(str(record[f"{role}_{kind}_path"]))
                rows.append(
                    {
                        "ticker": record["ticker"],
                        "trade_date": record["trade_date"],
                        "expiration": record[f"{role}_expiration"],
                        "role": role,
                        "kind": kind,
                        "path": str(path),
                        "size_bytes": int(path.stat().st_size),
                    }
                )
        underlying_path = Path(str(record["underlying_path"]))
        rows.append(
            {
                "ticker": record["ticker"],
                "trade_date": record["trade_date"],
                "expiration": "",
                "role": "spot",
                "kind": "underlying",
                "path": str(underlying_path),
                "size_bytes": int(underlying_path.stat().st_size),
            }
        )
    inventory = pd.DataFrame(rows).sort_values(
        ["ticker", "trade_date", "role", "kind"], kind="stable"
    ).reset_index(drop=True)
    unique_paths = sorted(set(inventory["path"]))
    hashes: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        future_map = {executor.submit(sha256_file, path): path for path in unique_paths}
        for future in as_completed(future_map):
            hashes[future_map[future]] = future.result()
    inventory["sha256"] = inventory["path"].map(hashes)
    if inventory["sha256"].isna().any() or len(inventory) != len(sessions) * 5:
        raise AssertionError("source inventory hash coverage mismatch")
    return inventory


def evaluate_data_gate(features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    valid = features.loc[features["feature_valid"]].copy()
    coverage_rows: list[dict[str, Any]] = []
    distinct_rows: list[dict[str, Any]] = []
    for ticker in TICKERS:
        total = features.loc[features["ticker"].eq(ticker)]
        ticker_valid = valid.loc[valid["ticker"].eq(ticker)]
        coverage_rows.append(
            {
                "ticker": ticker,
                "total_sessions": int(len(total)),
                "valid_sessions": int(len(ticker_valid)),
                "coverage": float(len(ticker_valid) / len(total)) if len(total) else 0.0,
            }
        )
        eligible = ticker_valid.loc[ticker_valid["economic_clock_eligible"]]
        pressure = pd.to_numeric(eligible["calendar_rr_pressure"], errors="coerce")
        distinct_rows.append(
            {
                "ticker": ticker,
                "eligible_sessions": int(len(eligible)),
                "distinct_states": int(pressure.nunique(dropna=True)),
                "zero_fraction": float(pressure.eq(0.0).mean()) if len(pressure) else 1.0,
                "missing": int(pressure.isna().sum()),
            }
        )
    coverage = pd.DataFrame(coverage_rows)
    distinctness = pd.DataFrame(distinct_rows)
    months = pd.period_range("2023-01", "2023-12", freq="M").astype(str).str.replace("-", "")
    monthly_rows: list[dict[str, Any]] = []
    for ticker in TICKERS:
        ticker_valid = valid.loc[
            valid["ticker"].eq(ticker) & valid["economic_clock_eligible"]
        ]
        for month in months:
            monthly_rows.append(
                {
                    "ticker": ticker,
                    "month": month,
                    "valid_events": int(ticker_valid["month"].eq(month).sum()),
                }
            )
    monthly = pd.DataFrame(monthly_rows)
    gate = {
        "coverage_pass": bool(coverage["coverage"].ge(MIN_ANNUAL_COVERAGE).all()),
        "distinctness_pass": bool(
            distinctness["distinct_states"].ge(MIN_DISTINCT_STATES).all()
            and distinctness["zero_fraction"].lt(MAX_ZERO_FRACTION).all()
            and distinctness["missing"].eq(0).all()
        ),
        "frequency_pass": bool(monthly["valid_events"].gt(MIN_MONTH_EVENTS_EXCLUSIVE).all()),
        "minimum_coverage": float(coverage["coverage"].min()),
        "minimum_distinct_states": int(distinctness["distinct_states"].min()),
        "maximum_zero_fraction": float(distinctness["zero_fraction"].max()),
        "minimum_monthly_valid_events": int(monthly["valid_events"].min()),
        "source_session_errors": int((~features["feature_valid"]).sum()),
    }
    gate["passed"] = bool(
        gate["coverage_pass"] and gate["distinctness_pass"] and gate["frequency_pass"]
    )
    return coverage, distinctness.merge(monthly.groupby("ticker")["valid_events"].min().rename("min_month_events"), on="ticker"), gate


def runtime_environment() -> dict[str, Any]:
    import pyarrow

    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "packages": {
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "pyarrow": pyarrow.__version__,
        },
    }


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    frame.to_csv(path, index=False, lineterminator="\n")


def run(options_root: Path, underlying_root: Path, output_dir: Path, workers: int) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"immutable output already exists: {output_dir}")
    tracked_clean(PREDECLARATION, "predeclaration")
    tracked_clean(Path(__file__).resolve(), "builder")
    sessions = discover_sessions(options_root, underlying_root)
    source_inventory = build_source_inventory(sessions, workers)
    features, session_audit = build_features(sessions, workers)
    coverage, distinctness, gate = evaluate_data_gate(features)
    valid = features.loc[features["feature_valid"]]
    monthly = (
        valid.loc[valid["economic_clock_eligible"]]
        .groupby(["ticker", "month"], observed=True)
        .size()
        .rename("valid_events")
        .reset_index()
    )
    errors = session_audit.loc[~session_audit["feature_valid"], ["ticker", "trade_date", "invalid_reason"]]

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = output_dir.with_name(f".{output_dir.name}.staging-{os.getpid()}")
    if staging.exists():
        raise FileExistsError(staging)
    staging.mkdir()
    try:
        features.to_parquet(staging / "calendar_rr_features.parquet", index=False)
        _write_csv(staging / "session_audit.csv", session_audit)
        _write_csv(staging / "source_inventory.csv", source_inventory)
        _write_csv(staging / "coverage.csv", coverage)
        _write_csv(staging / "distinctness.csv", distinctness)
        _write_csv(staging / "monthly_capacity.csv", monthly)
        _write_csv(staging / "errors.csv", errors)
        output_names = (
            "calendar_rr_features.parquet",
            "session_audit.csv",
            "source_inventory.csv",
            "coverage.csv",
            "distinctness.csv",
            "monthly_capacity.csv",
            "errors.csv",
        )
        environment = runtime_environment()
        manifest = {
            "schema": "calendar_risk_reversal_pressure_v1_outcome_free_data_gate",
            "status": "PASS_DATA_GATE" if gate["passed"] else "REJECTED_DATA_GATE",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit": current_git_commit(),
            "scope": {"start_date": START_DATE, "end_date": END_DATE, "sessions": int(len(sessions))},
            "tickers": list(TICKERS),
            "rows": int(len(features)),
            "valid_rows": int(len(valid)),
            "source_inventory_rows": int(len(source_inventory)),
            "feature_contract": {
                "clocks": list(CLOCKS),
                "target_abs_delta": TARGET_ABS_DELTA,
                "maximum_delta_gap": MAX_DELTA_GAP,
                "front": "expiration=trade_date",
                "back": "minimum expiration>trade_date",
                "same_contract_t0_t1": True,
                "feature": "delta5m[(call25-put25)_front-(call25-put25)_back]",
            },
            "data_gate": gate,
            "predeclaration_sha256": sha256_file(PREDECLARATION),
            "builder_sha256": sha256_file(Path(__file__).resolve()),
            "runtime_environment": environment,
            "runtime_environment_sha256": hashlib.sha256(
                json.dumps(environment, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
            "output_sha256": {name: sha256_file(staging / name) for name in output_names},
            "labels_built": False,
            "outcome_accessed": False,
            "outer_2024_2025_opened": False,
            "holdout_2026_opened": False,
            "production_modified": False,
            "errors": errors.to_dict(orient="records"),
        }
        (staging / "manifest.json").write_text(
            json.dumps(manifest, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(staging, output_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--options-root", type=Path, default=DEFAULT_OPTIONS_ROOT)
    parser.add_argument("--underlying-root", type=Path, default=DEFAULT_UNDERLYING_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=8)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = run(
        args.options_root.resolve(),
        args.underlying_root.resolve(),
        args.output_dir.resolve(),
        args.workers,
    )
    print(json.dumps(manifest, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
