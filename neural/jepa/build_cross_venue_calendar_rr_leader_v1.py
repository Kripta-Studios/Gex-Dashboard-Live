#!/usr/bin/env python3
"""Build the outcome-free 2024-2025 CROSS_VENUE_CALENDAR_RR_LEADER_V1 view."""

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

from neural.jepa.build_calendar_risk_reversal_pressure_v1 import (  # noqa: E402
    calculate_session_feature,
    canonical_date,
    join_greeks_iv,
    target_datetimes,
    tracked_clean,
)
from neural.jepa.capture_cross_venue_calendar_rr_native_clock_full import (  # noqa: E402
    EXPECTED_CAPTURE_ID_SHA256,
    EXPECTED_CAPTURES,
    EXPECTED_LOGICAL_INVENTORY_SHA256,
    EXPECTED_SESSIONS,
    EXPECTED_SESSIONS_PER_TICKER,
    discover_full_specs,
    prepare_spec,
)
from neural.jepa.capture_cross_venue_calendar_rr_native_clock_preflight import (  # noqa: E402
    sha256_file,
    target_timestamp_values,
    validate_existing_capture,
)
from neural.jepa.surface_flow_features import normalize_right  # noqa: E402


PROJECT_ROOT = SCRIPT_REPO_ROOT
TICKERS = ("QQQ", "SPXW", "SPY")
YEARS = ("2024", "2025")
START_DATE = "20240101"
END_DATE = "20251231"
CLOCKS = ("10:30:00", "10:35:00")
SENSOR_MAP = {"QQQ": "QQQ", "SPXW": "SPY", "SPY": "SPY"}
HALF_DAYS = frozenset(
    {
        "20240703",
        "20241129",
        "20241224",
        "20250703",
        "20251128",
        "20251224",
    }
)
MIN_ANNUAL_COVERAGE = 0.90
MIN_DISTINCT_STATES = 50
MAX_ZERO_FRACTION = 0.995
MIN_MONTH_EVENTS_EXCLUSIVE = 12

PREDECLARATION = PROJECT_ROOT / (
    "research_papers/JEPA/CROSS_VENUE_CALENDAR_RR_LEADER_V1_PREDECLARATION.md"
)
DATA_GATE_CONTRACT = PROJECT_ROOT / (
    "research_papers/JEPA/CROSS_VENUE_CALENDAR_RR_LEADER_V1_DATA_GATE_CONTRACT.md"
)
DEFAULT_OPTIONS_ROOT = Path("D:/ThetaData/data_options")
DEFAULT_UNDERLYING_ROOT = Path("D:/ThetaData/data_underlying_derived")
DEFAULT_SIDECAR_ROOT = Path(
    "D:/ThetaData/cross_venue_calendar_rr_native_clock_2024_2025_v1"
)
DEFAULT_OUTPUT = PROJECT_ROOT / (
    "tmp/cross_venue_calendar_rr_leader_v1_data_gate_202401_202512_v1"
)

KEY_COLUMNS = ("symbol", "expiration", "trade_date", "timestamp", "strike", "right")
GREEK_VALUE_COLUMNS = ("delta", "bid", "ask")
IV_VALUE_COLUMNS = ("bid", "ask", "bid_implied_vol", "ask_implied_vol")
CAPTURE_INDEX_COLUMNS = (
    "capture_id",
    "ticker",
    "trade_date",
    "role",
    "expiration",
    "rows",
    "raw_bytes",
    "parquet_bytes",
    "greek_rows",
    "native_extra_target_key_rows",
    "revised_bid_ask_rows",
    "crossed_native_rows",
    "raw_sha256",
    "parquet_sha256",
    "manifest_sha256",
)


def current_git_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def dataframe_digest(frame: pd.DataFrame) -> str:
    payload = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"JSON object required: {path}")
    return value


def _canonical_capture_index(frame: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(set(CAPTURE_INDEX_COLUMNS).difference(frame.columns))
    if missing:
        raise KeyError(f"capture index lacks columns: {missing}")
    output = frame.loc[:, CAPTURE_INDEX_COLUMNS].copy()
    for column in ("capture_id", "ticker", "trade_date", "role", "expiration"):
        output[column] = output[column].astype(str)
    for column in CAPTURE_INDEX_COLUMNS[5:12]:
        output[column] = pd.to_numeric(output[column], errors="raise").astype(np.int64)
    for column in CAPTURE_INDEX_COLUMNS[12:]:
        output[column] = output[column].astype(str)
    return output.sort_values(["ticker", "trade_date", "role"], kind="stable").reset_index(
        drop=True
    )


def validate_full_capture_seal(
    sidecar_root: str | Path,
) -> tuple[dict[str, Any], dict[str, Any], pd.DataFrame]:
    root = Path(sidecar_root)
    contract_path = root / "_state/capture_contract.json"
    universe_path = root / "_state/universe.csv"
    seal_path = root / "_seal/seal.json"
    index_path = root / "_seal/capture_index.csv"
    for path in (contract_path, universe_path, seal_path, index_path):
        if not path.is_file():
            raise FileNotFoundError(f"full native-clock PASS artifact missing: {path}")
    contract = _read_json(contract_path)
    seal = _read_json(seal_path)
    required_contract = {
        "schema": "cross_venue_calendar_rr_native_clock_full_contract_v1",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
    }
    if any(contract.get(key) != value for key, value in required_contract.items()):
        raise AssertionError("full capture root contract is not outcome-free")
    code_hashes = contract.get("code_hashes")
    if not isinstance(code_hashes, dict) or not code_hashes:
        raise AssertionError("full capture code-hash closure is missing")
    for relative, expected_sha256 in code_hashes.items():
        source_path = PROJECT_ROOT / str(relative)
        if not source_path.is_file() or sha256_file(source_path) != expected_sha256:
            raise AssertionError(f"full capture code blob changed: {relative}")
    universe = contract.get("universe_audit", {})
    if (
        universe.get("sessions") != EXPECTED_SESSIONS
        or universe.get("captures") != EXPECTED_CAPTURES
        or universe.get("capture_id_sha256") != EXPECTED_CAPTURE_ID_SHA256
        or universe.get("logical_inventory_sha256")
        != EXPECTED_LOGICAL_INVENTORY_SHA256
        or universe.get("sessions_per_ticker")
        != {ticker: EXPECTED_SESSIONS_PER_TICKER for ticker in TICKERS}
        or contract.get("universe_file_sha256") != sha256_file(universe_path)
    ):
        raise AssertionError("full capture universe contract changed")
    required_seal = {
        "schema": "cross_venue_calendar_rr_native_clock_full_seal_v1",
        "status": "PASS_CROSS_VENUE_CALENDAR_RR_NATIVE_CLOCK_FULL_CAPTURE",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "sessions": EXPECTED_SESSIONS,
        "captures": EXPECTED_CAPTURES,
        "missing_vintage_key_rows": 0,
    }
    if any(seal.get(key) != value for key, value in required_seal.items()):
        raise AssertionError("full native-clock seal is not a valid PASS")
    if (
        seal.get("git_commit") != contract.get("git_commit")
        or seal.get("code_hashes") != contract.get("code_hashes")
        or seal.get("source_provenance") != contract.get("source_provenance")
        or seal.get("runtime_lock_sha256") != contract.get("runtime_lock_sha256")
        or seal.get("runtime_environment_sha256")
        != contract.get("runtime_environment_sha256")
        or seal.get("capture_index_sha256") != sha256_file(index_path)
    ):
        raise AssertionError("full seal provenance/hash contract changed")
    index = _canonical_capture_index(pd.read_csv(index_path, dtype=str))
    counts = index.groupby("ticker", observed=True)["trade_date"].nunique().to_dict()
    if (
        len(index) != EXPECTED_CAPTURES
        or index["capture_id"].duplicated().any()
        or index.duplicated(["ticker", "trade_date", "role"]).any()
        or set(index["ticker"]) != set(TICKERS)
        or set(index["role"]) != {"front", "back"}
        or counts != {ticker: EXPECTED_SESSIONS_PER_TICKER for ticker in TICKERS}
        or not index["trade_date"].str[:4].isin(YEARS).all()
    ):
        raise AssertionError("full capture index identity changed")
    return contract, seal, index


def revalidate_all_captures(
    specs: pd.DataFrame,
    *,
    sidecar_root: Path,
    contract: dict[str, Any],
    expected_index: pd.DataFrame,
    workers: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    runtime = {
        "lock_sha256": str(contract["runtime_lock_sha256"]),
        "environment_sha256": str(contract["runtime_environment_sha256"]),
    }
    prepared: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(prepare_spec, record): record
            for record in specs.to_dict(orient="records")
        }
        for future in as_completed(futures):
            prepared.append(future.result())
    prepared_frame = (
        pd.DataFrame(prepared)
        .sort_values(["ticker", "trade_date", "role"], kind="stable")
        .reset_index(drop=True)
    )
    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(
                validate_existing_capture,
                record,
                staging=sidecar_root,
                capture_code_hashes=dict(contract["code_hashes"]),
                runtime=runtime,
            ): record
            for record in prepared_frame.to_dict(orient="records")
        }
        for future in as_completed(futures):
            rows.append(future.result())
    actual = _canonical_capture_index(pd.DataFrame(rows))
    try:
        pd.testing.assert_frame_equal(expected_index, actual, check_dtype=True)
    except AssertionError as exc:
        raise AssertionError("full capture revalidation differs from sealed index") from exc
    return prepared_frame, actual


def build_session_table(
    specs: pd.DataFrame, underlying_root: str | Path, sidecar_root: str | Path
) -> pd.DataFrame:
    role_frames: dict[str, pd.DataFrame] = {}
    for role in ("front", "back"):
        role_frame = specs.loc[specs["role"].eq(role)].copy()
        rename = {
            column: f"{role}_{column}"
            for column in (
                "capture_id",
                "expiration",
                "greeks_path",
                "iv_path",
                "greeks_sha256",
                "iv_sha256",
            )
        }
        role_frames[role] = role_frame.rename(columns=rename).drop(columns=["role"])
    sessions = role_frames["front"].merge(
        role_frames["back"],
        on=["ticker", "trade_date"],
        how="outer",
        validate="one_to_one",
        indicator=True,
    )
    if not sessions["_merge"].eq("both").all():
        raise AssertionError("front/back session inventory differs")
    sessions = sessions.drop(columns="_merge")
    sessions["trade_date"] = sessions["trade_date"].astype(str)
    sessions["year"] = sessions["trade_date"].str[:4]
    sessions["month"] = sessions["trade_date"].str[:6]
    sessions["calendar_half_day"] = sessions["trade_date"].isin(HALF_DAYS)
    sessions["economic_clock_eligible"] = ~sessions["calendar_half_day"]
    underlying_root = Path(underlying_root)
    sidecar_root = Path(sidecar_root)
    sessions["underlying_path"] = sessions.apply(
        lambda row: str(
            (
                underlying_root
                / str(row["ticker"])
                / str(row["year"])
                / str(row["month"])[4:6]
                / f"{row['ticker']}_{row['trade_date']}.parquet"
            ).resolve()
        ),
        axis=1,
    )
    for role in ("front", "back"):
        sessions[f"{role}_sidecar_path"] = sessions.apply(
            lambda row, capture_role=role: str(
                (
                    sidecar_root
                    / str(row["ticker"])
                    / str(row["trade_date"])
                    / capture_role
                    / "quotes.parquet"
                ).resolve()
            ),
            axis=1,
        )
    if (
        len(sessions) != EXPECTED_SESSIONS
        or sessions.duplicated(["ticker", "trade_date"]).any()
        or not sessions["year"].isin(YEARS).all()
        or set(sessions["ticker"]) != set(TICKERS)
    ):
        raise AssertionError("session table violates frozen scope")
    missing_paths = [
        path
        for column in (
            "front_greeks_path",
            "front_iv_path",
            "front_sidecar_path",
            "back_greeks_path",
            "back_iv_path",
            "back_sidecar_path",
            "underlying_path",
        )
        for path in sessions[column].map(Path)
        if not path.is_file()
    ]
    if missing_paths:
        raise FileNotFoundError(missing_paths[0])
    return sessions.sort_values(["ticker", "trade_date"], kind="stable").reset_index(
        drop=True
    )


def _read_vintage_values(
    path: Path,
    *,
    kind: str,
    ticker: str,
    trade_date: str,
    expiration: str,
) -> pd.DataFrame:
    value_columns = GREEK_VALUE_COLUMNS if kind == "greeks" else IV_VALUE_COLUMNS
    source_columns = (
        "symbol",
        "expiration",
        "trade_date",
        "underlying_timestamp",
        "strike",
        "right",
        *value_columns,
    )
    schema = set(pq.read_schema(path).names)
    missing = sorted(set(source_columns).difference(schema))
    if missing:
        raise KeyError(f"{kind} vintage source lacks fields {missing}: {path}")
    frame = pd.read_parquet(
        path,
        columns=list(source_columns),
        filters=[("underlying_timestamp", "in", target_timestamp_values(trade_date))],
    ).rename(columns={"underlying_timestamp": "timestamp"})
    output = frame.copy()
    output["symbol"] = output["symbol"].astype(str).str.upper().str.strip()
    output["expiration"] = output["expiration"].map(canonical_date)
    output["trade_date"] = output["trade_date"].map(canonical_date)
    output["timestamp"] = pd.to_datetime(output["timestamp"], errors="coerce")
    output["right"] = normalize_right(output["right"])
    for column in ("strike", *value_columns):
        output[column] = pd.to_numeric(output[column], errors="coerce")
    expected_times = set(target_datetimes(trade_date))
    if (
        output.empty
        or output[list(KEY_COLUMNS)].isna().any().any()
        or not output["symbol"].eq(ticker).all()
        or not output["trade_date"].eq(trade_date).all()
        or not output["expiration"].eq(expiration).all()
        or set(output["timestamp"].unique()) != expected_times
        or not output["right"].isin(["CALL", "PUT"]).all()
        or output.duplicated(list(KEY_COLUMNS)).any()
    ):
        raise AssertionError(f"invalid {kind} vintage target rows: {path}")
    return output.sort_values(list(KEY_COLUMNS), kind="stable").reset_index(drop=True)


def _read_native_keys(
    path: Path, *, ticker: str, trade_date: str, expiration: str
) -> pd.DataFrame:
    frame = pd.read_parquet(path, columns=list(KEY_COLUMNS))
    output = frame.copy()
    output["symbol"] = output["symbol"].astype(str).str.upper().str.strip()
    output["expiration"] = output["expiration"].map(canonical_date)
    output["trade_date"] = output["trade_date"].map(canonical_date)
    output["timestamp"] = pd.to_datetime(output["timestamp"], errors="coerce")
    output["strike"] = pd.to_numeric(output["strike"], errors="coerce")
    output["right"] = normalize_right(output["right"])
    expected_times = set(target_datetimes(trade_date))
    output = output.loc[output["timestamp"].isin(expected_times)].copy()
    if (
        output.empty
        or output.isna().any().any()
        or not output["symbol"].eq(ticker).all()
        or not output["trade_date"].eq(trade_date).all()
        or not output["expiration"].eq(expiration).all()
        or set(output["timestamp"].unique()) != expected_times
        or not output["right"].isin(["CALL", "PUT"]).all()
        or output.duplicated(list(KEY_COLUMNS)).any()
    ):
        raise AssertionError(f"invalid native key sidecar: {path}")
    return output.sort_values(list(KEY_COLUMNS), kind="stable").reset_index(drop=True)


def certify_vintage_clock(
    vintage: pd.DataFrame, native_keys: pd.DataFrame
) -> dict[str, Any]:
    vintage_keys = vintage.loc[:, KEY_COLUMNS]
    matched = vintage_keys.merge(
        native_keys,
        on=list(KEY_COLUMNS),
        how="left",
        indicator=True,
        validate="one_to_one",
    )
    if not matched["_merge"].eq("both").all() or len(matched) != len(vintage):
        raise AssertionError("native sidecar does not certify every vintage target key")
    extra = native_keys.merge(
        vintage_keys,
        on=list(KEY_COLUMNS),
        how="left",
        indicator=True,
        validate="one_to_one",
    )["_merge"].ne("both")
    return {
        "vintage_target_rows": int(len(vintage)),
        "native_target_rows": int(len(native_keys)),
        "native_extra_target_rows": int(extra.sum()),
        "clock_key_coverage_exact": True,
    }


def read_certified_chain(
    *,
    greeks_path: Path,
    iv_path: Path,
    sidecar_path: Path,
    ticker: str,
    trade_date: str,
    expiration: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    greeks = _read_vintage_values(
        greeks_path,
        kind="greeks",
        ticker=ticker,
        trade_date=trade_date,
        expiration=expiration,
    )
    iv = _read_vintage_values(
        iv_path,
        kind="iv",
        ticker=ticker,
        trade_date=trade_date,
        expiration=expiration,
    )
    native = _read_native_keys(
        sidecar_path,
        ticker=ticker,
        trade_date=trade_date,
        expiration=expiration,
    )
    greek_clock = certify_vintage_clock(greeks, native)
    iv_clock = certify_vintage_clock(iv, native)
    chain = join_greeks_iv(greeks, iv)
    return chain, {
        "greek_vintage_target_rows": int(len(greeks)),
        "iv_vintage_target_rows": int(len(iv)),
        "native_target_rows": int(len(native)),
        "native_extra_vs_greek_rows": int(greek_clock["native_extra_target_rows"]),
        "native_extra_vs_iv_rows": int(iv_clock["native_extra_target_rows"]),
        "clock_key_coverage_exact": True,
    }


def read_target_spots(path: Path, ticker: str, trade_date: str) -> tuple[float, float]:
    required = ("symbol", "date", "timestamp", "open")
    schema = set(pq.read_schema(path).names)
    missing = sorted(set(required).difference(schema))
    if missing:
        raise KeyError(f"underlying source lacks fields {missing}: {path}")
    values = target_timestamp_values(trade_date)
    frame = pd.read_parquet(
        path,
        columns=list(required),
        filters=[("timestamp", "in", values)],
    )
    output = frame.copy()
    output["symbol"] = output["symbol"].astype(str).str.upper().str.strip()
    output["date"] = output["date"].map(canonical_date)
    output["timestamp"] = pd.to_datetime(output["timestamp"], errors="coerce")
    output["open"] = pd.to_numeric(output["open"], errors="coerce")
    expected_times = target_datetimes(trade_date)
    if (
        len(output) != 2
        or output.isna().any().any()
        or not output["symbol"].eq(ticker).all()
        or not output["date"].eq(trade_date).all()
        or set(output["timestamp"]) != set(expected_times)
        or output["timestamp"].duplicated().any()
        or not np.isfinite(output["open"].to_numpy(dtype=float)).all()
        or not output["open"].gt(0.0).all()
    ):
        raise AssertionError(f"invalid exact target spots: {path}")
    indexed = output.set_index("timestamp")
    return float(indexed.loc[expected_times[0], "open"]), float(
        indexed.loc[expected_times[1], "open"]
    )


def process_local_session(record: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    ticker = str(record["ticker"])
    trade_date = str(record["trade_date"])
    spot_t0, spot_t1 = read_target_spots(
        Path(str(record["underlying_path"])), ticker, trade_date
    )
    chains: dict[str, pd.DataFrame] = {}
    role_audits: dict[str, Any] = {}
    for role in ("front", "back"):
        chains[role], role_audit = read_certified_chain(
            greeks_path=Path(str(record[f"{role}_greeks_path"])),
            iv_path=Path(str(record[f"{role}_iv_path"])),
            sidecar_path=Path(str(record[f"{role}_sidecar_path"])),
            ticker=ticker,
            trade_date=trade_date,
            expiration=str(record[f"{role}_expiration"]),
        )
        role_audits.update({f"{role}_{key}": value for key, value in role_audit.items()})
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
            "local_feature_valid": True,
            "local_invalid_reason": "",
        }
    )
    audit = {
        "ticker": ticker,
        "trade_date": trade_date,
        "local_feature_valid": True,
        "local_invalid_reason": "",
        **role_audits,
    }
    return feature, audit


def _invalid_local_result(
    record: dict[str, Any], error: Exception
) -> tuple[dict[str, Any], dict[str, Any]]:
    reason = f"{type(error).__name__}: {error}"
    feature = {
        "ticker": str(record["ticker"]),
        "trade_date": str(record["trade_date"]),
        "year": str(record["trade_date"])[:4],
        "month": str(record["trade_date"])[:6],
        "front_expiration": str(record["front_expiration"]),
        "back_expiration": str(record["back_expiration"]),
        "calendar_half_day": bool(record["calendar_half_day"]),
        "economic_clock_eligible": bool(record["economic_clock_eligible"]),
        "local_feature_valid": False,
        "local_invalid_reason": reason,
    }
    audit = {
        "ticker": feature["ticker"],
        "trade_date": feature["trade_date"],
        "local_feature_valid": False,
        "local_invalid_reason": reason,
    }
    return feature, audit


def build_local_features(
    sessions: pd.DataFrame, workers: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    features: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    records = sessions.to_dict(orient="records")
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(process_local_session, row): row for row in records}
        for future in as_completed(futures):
            record = futures[future]
            try:
                feature, audit = future.result()
            except Exception as error:  # noqa: BLE001 - preserve exact data-gate failure
                feature, audit = _invalid_local_result(record, error)
            features.append(feature)
            audits.append(audit)
    feature_frame = pd.DataFrame(features).sort_values(
        ["ticker", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    audit_frame = pd.DataFrame(audits).sort_values(
        ["ticker", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    if (
        len(feature_frame) != EXPECTED_SESSIONS
        or feature_frame.duplicated(["ticker", "trade_date"]).any()
    ):
        raise AssertionError("local feature output is not one-to-one")
    return feature_frame, audit_frame


def apply_cross_venue_mapping(local: pd.DataFrame) -> pd.DataFrame:
    lookup = local.set_index(["ticker", "trade_date"])
    if not lookup.index.is_unique:
        raise AssertionError("local feature keys are not unique")
    rows: list[dict[str, Any]] = []
    for source in local.to_dict(orient="records"):
        row = dict(source)
        ticker = str(row["ticker"])
        trade_date = str(row["trade_date"])
        sensor_ticker = SENSOR_MAP[ticker]
        row["sensor_ticker"] = sensor_ticker
        if not bool(row["local_feature_valid"]):
            row.update(
                {
                    "sensor_local_feature_valid": False,
                    "signal_pressure": np.nan,
                    "signal_action": 0,
                    "mapped_feature_valid": False,
                    "mapped_invalid_reason": str(row["local_invalid_reason"]),
                }
            )
        elif (sensor_ticker, trade_date) not in lookup.index:
            row.update(
                {
                    "sensor_local_feature_valid": False,
                    "signal_pressure": np.nan,
                    "signal_action": 0,
                    "mapped_feature_valid": False,
                    "mapped_invalid_reason": "missing exact-date sensor row",
                }
            )
        else:
            sensor = lookup.loc[(sensor_ticker, trade_date)]
            sensor_valid = bool(sensor["local_feature_valid"])
            pressure = pd.to_numeric(
                pd.Series([sensor.get("calendar_rr_pressure")]), errors="coerce"
            ).iloc[0]
            valid = sensor_valid and bool(np.isfinite(pressure))
            row.update(
                {
                    "sensor_local_feature_valid": sensor_valid,
                    "signal_pressure": float(pressure) if valid else np.nan,
                    "signal_action": int(np.sign(pressure)) if valid else 0,
                    "mapped_feature_valid": valid,
                    "mapped_invalid_reason": ""
                    if valid
                    else str(sensor.get("local_invalid_reason", "invalid sensor")),
                }
            )
        row["economic_event_valid"] = bool(
            row["mapped_feature_valid"]
            and row["economic_clock_eligible"]
            and row["signal_action"] in (-1, 1)
        )
        rows.append(row)
    output = pd.DataFrame(rows).sort_values(
        ["ticker", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    if len(output) != len(local) or output.duplicated(["ticker", "trade_date"]).any():
        raise AssertionError("cross-venue mapping is not one-to-one")
    return output


def evaluate_data_gate(
    features: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    coverage_rows: list[dict[str, Any]] = []
    distinct_rows: list[dict[str, Any]] = []
    monthly_rows: list[dict[str, Any]] = []
    months = pd.period_range("2024-01", "2025-12", freq="M").strftime("%Y%m")
    for ticker in TICKERS:
        ticker_rows = features.loc[features["ticker"].eq(ticker)]
        for year in YEARS:
            annual = ticker_rows.loc[ticker_rows["year"].eq(year)]
            local_valid = annual["local_feature_valid"].astype(bool)
            mapped_valid = annual["mapped_feature_valid"].astype(bool)
            coverage_rows.append(
                {
                    "ticker": ticker,
                    "year": year,
                    "total_sessions": int(len(annual)),
                    "local_valid_sessions": int(local_valid.sum()),
                    "mapped_valid_sessions": int(mapped_valid.sum()),
                    "local_coverage": float(local_valid.mean()) if len(annual) else 0.0,
                    "mapped_coverage": float(mapped_valid.mean()) if len(annual) else 0.0,
                }
            )
            eligible = annual.loc[
                annual["mapped_feature_valid"].astype(bool)
                & annual["economic_clock_eligible"].astype(bool)
            ]
            pressure = pd.to_numeric(eligible["signal_pressure"], errors="coerce")
            distinct_rows.append(
                {
                    "ticker": ticker,
                    "year": year,
                    "eligible_sessions": int(len(eligible)),
                    "distinct_states": int(pressure.nunique(dropna=True)),
                    "zero_fraction": float(pressure.eq(0.0).mean())
                    if len(pressure)
                    else 1.0,
                    "missing": int(pressure.isna().sum()),
                }
            )
        for month in months:
            monthly_rows.append(
                {
                    "ticker": ticker,
                    "month": month,
                    "valid_events": int(
                        (
                            ticker_rows["month"].eq(month)
                            & ticker_rows["economic_event_valid"].astype(bool)
                        ).sum()
                    ),
                }
            )
    coverage = pd.DataFrame(coverage_rows)
    distinctness = pd.DataFrame(distinct_rows)
    monthly = pd.DataFrame(monthly_rows)
    gate: dict[str, Any] = {
        "local_coverage_pass": bool(
            coverage["local_coverage"].ge(MIN_ANNUAL_COVERAGE).all()
        ),
        "mapped_coverage_pass": bool(
            coverage["mapped_coverage"].ge(MIN_ANNUAL_COVERAGE).all()
        ),
        "distinctness_pass": bool(
            distinctness["distinct_states"].ge(MIN_DISTINCT_STATES).all()
            and distinctness["zero_fraction"].lt(MAX_ZERO_FRACTION).all()
            and distinctness["missing"].eq(0).all()
        ),
        "frequency_pass": bool(
            monthly["valid_events"].gt(MIN_MONTH_EVENTS_EXCLUSIVE).all()
        ),
        "minimum_local_coverage": float(coverage["local_coverage"].min()),
        "minimum_mapped_coverage": float(coverage["mapped_coverage"].min()),
        "minimum_distinct_states": int(distinctness["distinct_states"].min()),
        "maximum_zero_fraction": float(distinctness["zero_fraction"].max()),
        "minimum_monthly_valid_events": int(monthly["valid_events"].min()),
        "local_source_errors": int((~features["local_feature_valid"].astype(bool)).sum()),
        "mapped_source_errors": int(
            (~features["mapped_feature_valid"].astype(bool)).sum()
        ),
    }
    gate["passed"] = bool(
        gate["local_coverage_pass"]
        and gate["mapped_coverage_pass"]
        and gate["distinctness_pass"]
        and gate["frequency_pass"]
    )
    return coverage, distinctness, monthly, gate


def build_source_inventory(
    sessions: pd.DataFrame, sidecar_root: Path, workers: int
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for record in sessions.to_dict(orient="records"):
        for role in ("front", "back"):
            capture_dir = (
                sidecar_root
                / str(record["ticker"])
                / str(record["trade_date"])
                / role
            )
            for kind, path in (
                ("greeks", Path(str(record[f"{role}_greeks_path"]))),
                ("iv", Path(str(record[f"{role}_iv_path"]))),
                ("sidecar_raw", capture_dir / "response.json"),
                ("sidecar_parquet", capture_dir / "quotes.parquet"),
                ("sidecar_manifest", capture_dir / "manifest.json"),
            ):
                rows.append(
                    {
                        "ticker": record["ticker"],
                        "trade_date": record["trade_date"],
                        "role": role,
                        "kind": kind,
                        "path": str(path.resolve()),
                        "size_bytes": int(path.stat().st_size),
                    }
                )
        underlying_path = Path(str(record["underlying_path"]))
        rows.append(
            {
                "ticker": record["ticker"],
                "trade_date": record["trade_date"],
                "role": "spot",
                "kind": "underlying",
                "path": str(underlying_path.resolve()),
                "size_bytes": int(underlying_path.stat().st_size),
            }
        )
    inventory = pd.DataFrame(rows).sort_values(
        ["ticker", "trade_date", "role", "kind"], kind="stable"
    ).reset_index(drop=True)
    unique_paths = sorted(set(inventory["path"]))
    hashes: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(sha256_file, path): path for path in unique_paths}
        for future in as_completed(futures):
            hashes[futures[future]] = future.result()
    inventory["sha256"] = inventory["path"].map(hashes)
    expected_rows = EXPECTED_SESSIONS + EXPECTED_CAPTURES * 5
    if (
        len(inventory) != expected_rows
        or inventory["sha256"].isna().any()
        or inventory["path"].duplicated().any()
    ):
        raise AssertionError("source inventory hash coverage mismatch")
    return inventory


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


def run(
    options_root: Path,
    underlying_root: Path,
    sidecar_root: Path,
    output_dir: Path,
    workers: int,
) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"immutable output already exists: {output_dir}")
    if workers < 1:
        raise ValueError("workers must be positive")
    for path, label in (
        (PREDECLARATION, "predeclaration"),
        (DATA_GATE_CONTRACT, "data gate contract"),
        (Path(__file__).resolve(), "builder"),
    ):
        tracked_clean(path, label)
    contract, seal, expected_index = validate_full_capture_seal(sidecar_root)
    specs, universe_audit = discover_full_specs(options_root)
    prepared_specs, capture_revalidation = revalidate_all_captures(
        specs,
        sidecar_root=sidecar_root,
        contract=contract,
        expected_index=expected_index,
        workers=workers,
    )
    sessions = build_session_table(prepared_specs, underlying_root, sidecar_root)
    source_inventory = build_source_inventory(sessions, sidecar_root, workers)
    local_features, session_audit = build_local_features(sessions, workers)
    features = apply_cross_venue_mapping(local_features)
    coverage, distinctness, monthly, gate = evaluate_data_gate(features)
    errors = features.loc[
        ~features["mapped_feature_valid"].astype(bool),
        [
            "ticker",
            "trade_date",
            "local_feature_valid",
            "local_invalid_reason",
            "sensor_ticker",
            "sensor_local_feature_valid",
            "mapped_invalid_reason",
        ],
    ]

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = output_dir.with_name(f".{output_dir.name}.staging-{os.getpid()}")
    if staging.exists():
        raise FileExistsError(staging)
    staging.mkdir()
    try:
        features.to_parquet(staging / "cross_venue_calendar_rr_features.parquet", index=False)
        _write_csv(staging / "session_audit.csv", session_audit)
        _write_csv(staging / "capture_revalidation.csv", capture_revalidation)
        _write_csv(staging / "source_inventory.csv", source_inventory)
        _write_csv(staging / "coverage.csv", coverage)
        _write_csv(staging / "distinctness.csv", distinctness)
        _write_csv(staging / "monthly_capacity.csv", monthly)
        _write_csv(staging / "errors.csv", errors)
        output_names = (
            "cross_venue_calendar_rr_features.parquet",
            "session_audit.csv",
            "capture_revalidation.csv",
            "source_inventory.csv",
            "coverage.csv",
            "distinctness.csv",
            "monthly_capacity.csv",
            "errors.csv",
        )
        environment = runtime_environment()
        manifest = {
            "schema": "cross_venue_calendar_rr_leader_v1_outcome_free_data_gate",
            "status": "PASS_DATA_GATE" if gate["passed"] else "REJECTED_DATA_GATE",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit": current_git_commit(),
            "scope": {
                "start_date": START_DATE,
                "end_date": END_DATE,
                "sessions": int(len(sessions)),
                "captures": int(len(capture_revalidation)),
            },
            "tickers": list(TICKERS),
            "rows": int(len(features)),
            "local_valid_rows": int(features["local_feature_valid"].sum()),
            "mapped_valid_rows": int(features["mapped_feature_valid"].sum()),
            "economic_event_rows": int(features["economic_event_valid"].sum()),
            "source_inventory_rows": int(len(source_inventory)),
            "universe_audit": universe_audit,
            "feature_contract": {
                "clocks": list(CLOCKS),
                "sidecar_role": "native option timestamp/key certification only",
                "economic_values": "vintage Greek/IV sources only",
                "same_contract_t0_t1": True,
                "target_abs_delta": 0.25,
                "maximum_delta_gap": 0.10,
                "mapping": SENSOR_MAP,
                "half_days_excluded_from_economic_clock": sorted(HALF_DAYS),
            },
            "data_gate": gate,
            "full_capture_contract_sha256": sha256_file(
                sidecar_root / "_state/capture_contract.json"
            ),
            "full_capture_seal_sha256": sha256_file(sidecar_root / "_seal/seal.json"),
            "full_capture_index_sha256": sha256_file(
                sidecar_root / "_seal/capture_index.csv"
            ),
            "capture_contract_git_commit": contract["git_commit"],
            "capture_seal_created_at_utc": seal["created_at_utc"],
            "predeclaration_sha256": sha256_file(PREDECLARATION),
            "data_gate_contract_sha256": sha256_file(DATA_GATE_CONTRACT),
            "builder_sha256": sha256_file(Path(__file__).resolve()),
            "runtime_environment": environment,
            "runtime_environment_sha256": hashlib.sha256(
                json.dumps(environment, sort_keys=True, separators=(",", ":")).encode(
                    "utf-8"
                )
            ).hexdigest(),
            "output_sha256": {name: sha256_file(staging / name) for name in output_names},
            "feature_view_sha256": dataframe_digest(
                features.drop(columns=["local_invalid_reason", "mapped_invalid_reason"])
            ),
            "labels_built": False,
            "outcome_accessed": False,
            "underlying_outcome_clocks_read": False,
            "outer_2024_opened": False,
            "outer_2025_opened": False,
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
    parser.add_argument("--sidecar-root", type=Path, default=DEFAULT_SIDECAR_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=8)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = run(
        args.options_root.resolve(),
        args.underlying_root.resolve(),
        args.sidecar_root.resolve(),
        args.output_dir.resolve(),
        args.workers,
    )
    print(json.dumps(manifest, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
