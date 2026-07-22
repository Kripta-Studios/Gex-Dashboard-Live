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
)
from neural.jepa import (  # noqa: E402
    seal_cross_venue_calendar_rr_native_clock_composite_v1r1 as composite,
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
COMPOSITE_CLARIFICATION = PROJECT_ROOT / (
    "research_papers/JEPA/"
    "CROSS_VENUE_CALENDAR_RR_LEADER_V1_COMPOSITE_CONSUMER_CLARIFICATION.md"
)
COMPOSITE_EVIDENCE = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_calendar_rr_native_clock_composite_2024_2025_v1r1"
)
DEFAULT_OPTIONS_ROOT = Path("D:/ThetaData/data_options")
DEFAULT_UNDERLYING_ROOT = Path("D:/ThetaData/data_underlying_derived")
DEFAULT_SIDECAR_ROOT = composite.DEFAULT_OUTPUT
DEFAULT_OUTPUT = PROJECT_ROOT / (
    "tmp/cross_venue_calendar_rr_leader_v1_data_gate_202401_202512_v1r1"
)

EXPECTED_COMPOSITE_HASHES = {
    "seal.json": "5b97ebc5fc867e06ef51d0fcd2956a48a4c06d2291828f5e3ca0e8ae1c9cf84f",
    "composite_contract.json": (
        "68714d77ec693028f61b3cf08396ff896ff2415c24f7c21f169872916fd8c046"
    ),
    "capture_index.csv": (
        "e5a669b7bf5fc17ac1dff62284b9d5c63751554812c0085cf23fc089f1943a0e"
    ),
    "ticker_year_summary.csv": (
        "41deb0149075908052bfaf8f6069b10ae55760e8cf21639251a5e9fe6cf6df65"
    ),
    "universe.csv": (
        "98d416ea810c5bde657b6c23a9d7c599885d5eedfef3e332cd1885f6ddee45f4"
    ),
}

KEY_COLUMNS = ("symbol", "expiration", "trade_date", "timestamp", "strike", "right")
GREEK_VALUE_COLUMNS = ("delta", "bid", "ask")
IV_VALUE_COLUMNS = ("bid", "ask", "bid_implied_vol", "ask_implied_vol")
CAPTURE_INDEX_COLUMNS = (
    "capture_id",
    "ticker",
    "trade_date",
    "role",
    "expiration",
    "storage_generation",
    "storage_root",
    "rows",
    "raw_bytes",
    "parquet_bytes",
    "greek_rows",
    "iv_rows",
    "shared_key_rows",
    "greek_only_key_rows",
    "iv_only_key_rows",
    "missing_shared_key_rows",
    "native_extra_target_key_rows",
    "revised_bid_ask_rows",
    "crossed_native_rows",
    "raw_sha256",
    "parquet_sha256",
    "manifest_sha256",
)
CAPTURE_INDEX_STRING_COLUMNS = (
    "capture_id",
    "ticker",
    "trade_date",
    "role",
    "expiration",
    "storage_generation",
    "storage_root",
    "raw_sha256",
    "parquet_sha256",
    "manifest_sha256",
)
CAPTURE_INDEX_NUMERIC_COLUMNS = tuple(
    column
    for column in CAPTURE_INDEX_COLUMNS
    if column not in CAPTURE_INDEX_STRING_COLUMNS
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
    for column in CAPTURE_INDEX_STRING_COLUMNS:
        output[column] = output[column].astype(str)
    for column in CAPTURE_INDEX_NUMERIC_COLUMNS:
        output[column] = pd.to_numeric(output[column], errors="raise").astype(np.int64)
    return output.sort_values(["ticker", "trade_date", "role"], kind="stable").reset_index(
        drop=True
    )


def validate_full_capture_seal(
    sidecar_root: str | Path,
) -> tuple[dict[str, Any], dict[str, Any], pd.DataFrame]:
    root = Path(sidecar_root)
    contract_path = root / "_state/composite_contract.json"
    universe_path = root / "_state/universe.csv"
    seal_path = root / "_seal/seal.json"
    index_path = root / "_seal/capture_index.csv"
    summary_path = root / "_seal/ticker_year_summary.csv"
    for path in (contract_path, universe_path, seal_path, index_path, summary_path):
        if not path.is_file():
            raise FileNotFoundError(f"composite native-clock PASS artifact missing: {path}")
    local_paths = {
        "seal.json": seal_path,
        "composite_contract.json": contract_path,
        "capture_index.csv": index_path,
        "ticker_year_summary.csv": summary_path,
        "universe.csv": universe_path,
    }
    for name, expected in EXPECTED_COMPOSITE_HASHES.items():
        evidence = COMPOSITE_EVIDENCE / name
        if (
            not evidence.is_file()
            or sha256_file(evidence) != expected
            or sha256_file(local_paths[name]) != expected
            or evidence.read_bytes() != local_paths[name].read_bytes()
        ):
            raise AssertionError(f"composite compact/local evidence changed: {name}")
    contract = _read_json(contract_path)
    seal = _read_json(seal_path)
    required_contract = {
        "schema": "cross_venue_calendar_rr_native_clock_composite_v1r1_contract",
        "status": "PASS_COMPOSITE_REVALIDATION",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "git_commit": "963f91c9fde298a8820e7dafa55c625f1220f88f",
    }
    if any(contract.get(key) != value for key, value in required_contract.items()):
        raise AssertionError("composite capture contract identity changed")
    code_hashes = contract.get("code_hashes")
    if not isinstance(code_hashes, dict) or not code_hashes:
        raise AssertionError("full capture code-hash closure is missing")
    for relative, expected_sha256 in code_hashes.items():
        source_path = PROJECT_ROOT / str(relative)
        if not source_path.is_file() or sha256_file(source_path) != expected_sha256:
            raise AssertionError(f"composite capture code blob changed: {relative}")
    universe = contract.get("universe_audit", {})
    if (
        universe.get("sessions") != EXPECTED_SESSIONS
        or universe.get("captures") != EXPECTED_CAPTURES
        or universe.get("capture_id_sha256") != EXPECTED_CAPTURE_ID_SHA256
        or universe.get("logical_inventory_sha256")
        != EXPECTED_LOGICAL_INVENTORY_SHA256
        or universe.get("sessions_per_ticker")
        != {ticker: EXPECTED_SESSIONS_PER_TICKER for ticker in TICKERS}
        or contract.get("universe_sha256") != sha256_file(universe_path)
    ):
        raise AssertionError("composite capture universe contract changed")
    required_seal = {
        "schema": "cross_venue_calendar_rr_native_clock_composite_v1r1_seal",
        "status": "PASS_CROSS_VENUE_CALENDAR_RR_NATIVE_CLOCK_COMPOSITE_V1R1",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "sessions": EXPECTED_SESSIONS,
        "captures": EXPECTED_CAPTURES,
        "v1_captures": composite.EXPECTED_V1_CAPTURES,
        "repair_captures": composite.EXPECTED_REPAIR_CAPTURES,
        "unilateral_key_rows": 8,
        "missing_shared_key_rows": 0,
    }
    if any(seal.get(key) != value for key, value in required_seal.items()):
        raise AssertionError("full native-clock seal is not a valid PASS")
    if (
        seal.get("git_commit") != contract.get("git_commit")
        or seal.get("code_hashes") != contract.get("code_hashes")
        or seal.get("capture_index_sha256") != sha256_file(index_path)
        or seal.get("ticker_year_summary_sha256") != sha256_file(summary_path)
        or seal.get("composite_contract_sha256") != sha256_file(contract_path)
        or seal.get("universe_sha256") != sha256_file(universe_path)
    ):
        raise AssertionError("composite seal provenance/hash contract changed")
    index = _canonical_capture_index(pd.read_csv(index_path, dtype=str))
    counts = index.groupby("ticker", observed=True)["trade_date"].nunique().to_dict()
    generation_counts = index["storage_generation"].value_counts().to_dict()
    roots = {
        "V1": str(Path(str(contract["v1_root"]))),
        "V1R1_REPAIR": str(Path(str(contract["repair_root"]))),
    }
    storage_ok = all(
        index.loc[index["storage_generation"].eq(generation), "storage_root"].eq(
            expected_root
        ).all()
        for generation, expected_root in roots.items()
    )
    repair_rows = index.loc[index["storage_generation"].eq("V1R1_REPAIR")]
    expected_repairs = {
        capture_id: {
            "shared_key_rows": values["shared_key_rows"],
            "greek_only_key_rows": (
                2 if values["unilateral_source"] == "greek_only" else 0
            ),
            "iv_only_key_rows": (
                2 if values["unilateral_source"] == "iv_only" else 0
            ),
        }
        for capture_id, values in composite.repair.EXPECTED_REPAIRS.items()
    }
    if (
        len(index) != EXPECTED_CAPTURES
        or index["capture_id"].duplicated().any()
        or index.duplicated(["ticker", "trade_date", "role"]).any()
        or set(index["ticker"]) != set(TICKERS)
        or set(index["role"]) != {"front", "back"}
        or counts != {ticker: EXPECTED_SESSIONS_PER_TICKER for ticker in TICKERS}
        or generation_counts
        != {
            "V1": composite.EXPECTED_V1_CAPTURES,
            "V1R1_REPAIR": composite.EXPECTED_REPAIR_CAPTURES,
        }
        or not storage_ok
        or set(repair_rows["capture_id"]) != set(expected_repairs)
        or int(index["missing_shared_key_rows"].sum()) != 0
        or int(index["greek_only_key_rows"].sum()) != 2
        or int(index["iv_only_key_rows"].sum()) != 6
        or not index.loc[index["storage_generation"].eq("V1"), "greek_only_key_rows"].eq(0).all()
        or not index.loc[index["storage_generation"].eq("V1"), "iv_only_key_rows"].eq(0).all()
        or not index["trade_date"].str[:4].isin(YEARS).all()
    ):
        raise AssertionError("composite capture index identity changed")
    for record in repair_rows.to_dict("records"):
        frozen = expected_repairs[str(record["capture_id"])]
        if (
            int(record["greek_only_key_rows"]) != int(frozen["greek_only_key_rows"])
            or int(record["iv_only_key_rows"]) != int(frozen["iv_only_key_rows"])
            or int(record["shared_key_rows"]) != int(frozen["shared_key_rows"])
        ):
            raise AssertionError("repair capture intersection counts changed")
    return contract, seal, index


def revalidate_all_captures(
    specs: pd.DataFrame,
    *,
    sidecar_root: Path,
    contract: dict[str, Any],
    expected_index: pd.DataFrame,
    workers: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
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
    v1_root = Path(str(contract["v1_root"]))
    repair_root = Path(str(contract["repair_root"]))
    if not (Path(sidecar_root) / "_seal/seal.json").is_file():
        raise FileNotFoundError("composite seal disappeared during revalidation")
    v1_contract = _read_json(v1_root / "_state/capture_contract.json")
    repair_contract, _repair_seal = composite.validate_repair_root(repair_root)
    actual = _canonical_capture_index(
        composite.revalidate_composite(
            prepared_frame,
            v1_root=v1_root,
            repair_root=repair_root,
            v1_contract=v1_contract,
            repair_contract=repair_contract,
            workers=workers,
        )
    )
    try:
        pd.testing.assert_frame_equal(expected_index, actual, check_dtype=True)
    except AssertionError as exc:
        raise AssertionError("composite capture revalidation differs from sealed index") from exc
    metadata_columns = (
        "capture_id",
        "storage_generation",
        "storage_root",
        "shared_key_rows",
        "greek_only_key_rows",
        "iv_only_key_rows",
        "missing_shared_key_rows",
    )
    prepared_frame = prepared_frame.merge(
        actual.loc[:, metadata_columns],
        on="capture_id",
        how="left",
        validate="one_to_one",
    )
    if prepared_frame[list(metadata_columns[1:])].isna().any().any():
        raise AssertionError("prepared capture metadata lacks composite provenance")
    return prepared_frame, actual


def build_session_table(
    specs: pd.DataFrame, underlying_root: str | Path
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
                "storage_generation",
                "storage_root",
                "shared_key_rows",
                "greek_only_key_rows",
                "iv_only_key_rows",
                "missing_shared_key_rows",
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
                    Path(str(row[f"{capture_role}_storage_root"]))
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


def align_vintage_modalities(
    greeks: pd.DataFrame,
    iv: pd.DataFrame,
    *,
    storage_generation: str,
    expected_shared_key_rows: int,
    expected_greek_only_key_rows: int,
    expected_iv_only_key_rows: int,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    if storage_generation not in {"V1", "V1R1_REPAIR"}:
        raise AssertionError("unknown composite storage generation")
    greek_keys = greeks.loc[:, KEY_COLUMNS]
    iv_keys = iv.loc[:, KEY_COLUMNS]
    comparison = greek_keys.merge(
        iv_keys,
        on=list(KEY_COLUMNS),
        how="outer",
        indicator=True,
        validate="one_to_one",
    )
    shared = comparison.loc[
        comparison["_merge"].eq("both"), list(KEY_COLUMNS)
    ].copy()
    greek_only = int(comparison["_merge"].eq("left_only").sum())
    iv_only = int(comparison["_merge"].eq("right_only").sum())
    if (
        len(shared) != int(expected_shared_key_rows)
        or greek_only != int(expected_greek_only_key_rows)
        or iv_only != int(expected_iv_only_key_rows)
    ):
        raise AssertionError("vintage Greek/IV intersection differs from composite")
    if storage_generation == "V1" and (greek_only or iv_only):
        raise AssertionError("V1 capture lost exact Greek/IV key equality")
    if storage_generation == "V1R1_REPAIR" and not (greek_only or iv_only):
        raise AssertionError("V1R1 repair no longer has its frozen unilateral keys")
    aligned_greeks = greeks.merge(
        shared,
        on=list(KEY_COLUMNS),
        how="inner",
        validate="one_to_one",
    )
    aligned_iv = iv.merge(
        shared,
        on=list(KEY_COLUMNS),
        how="inner",
        validate="one_to_one",
    )
    aligned_greeks = aligned_greeks.sort_values(
        list(KEY_COLUMNS), kind="stable"
    ).reset_index(drop=True)
    aligned_iv = aligned_iv.sort_values(
        list(KEY_COLUMNS), kind="stable"
    ).reset_index(drop=True)
    return aligned_greeks, aligned_iv, {
        "shared_key_rows": int(len(shared)),
        "greek_only_key_rows": greek_only,
        "iv_only_key_rows": iv_only,
    }


def read_certified_chain(
    *,
    greeks_path: Path,
    iv_path: Path,
    sidecar_path: Path,
    ticker: str,
    trade_date: str,
    expiration: str,
    storage_generation: str,
    expected_shared_key_rows: int,
    expected_greek_only_key_rows: int,
    expected_iv_only_key_rows: int,
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
    greeks, iv, modality_audit = align_vintage_modalities(
        greeks,
        iv,
        storage_generation=storage_generation,
        expected_shared_key_rows=expected_shared_key_rows,
        expected_greek_only_key_rows=expected_greek_only_key_rows,
        expected_iv_only_key_rows=expected_iv_only_key_rows,
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
        "storage_generation": storage_generation,
        **modality_audit,
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
            storage_generation=str(record[f"{role}_storage_generation"]),
            expected_shared_key_rows=int(record[f"{role}_shared_key_rows"]),
            expected_greek_only_key_rows=int(
                record[f"{role}_greek_only_key_rows"]
            ),
            expected_iv_only_key_rows=int(record[f"{role}_iv_only_key_rows"]),
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


def build_source_inventory(sessions: pd.DataFrame, workers: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for record in sessions.to_dict(orient="records"):
        for role in ("front", "back"):
            capture_dir = Path(str(record[f"{role}_sidecar_path"])).parent
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
        (COMPOSITE_CLARIFICATION, "composite consumer clarification"),
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
    sessions = build_session_table(prepared_specs, underlying_root)
    source_inventory = build_source_inventory(sessions, workers)
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
                "composite_multi_root": True,
                "v1_exact_greek_iv_keys": True,
                "v1r1_intersection_capture_ids": sorted(
                    composite.repair.EXPECTED_REPAIR_IDS
                ),
                "target_abs_delta": 0.25,
                "maximum_delta_gap": 0.10,
                "mapping": SENSOR_MAP,
                "half_days_excluded_from_economic_clock": sorted(HALF_DAYS),
            },
            "data_gate": gate,
            "full_capture_contract_sha256": sha256_file(
                sidecar_root / "_state/composite_contract.json"
            ),
            "full_capture_seal_sha256": sha256_file(sidecar_root / "_seal/seal.json"),
            "full_capture_index_sha256": sha256_file(
                sidecar_root / "_seal/capture_index.csv"
            ),
            "capture_contract_git_commit": contract["git_commit"],
            "capture_seal_created_at_utc": seal["created_at_utc"],
            "predeclaration_sha256": sha256_file(PREDECLARATION),
            "data_gate_contract_sha256": sha256_file(DATA_GATE_CONTRACT),
            "composite_clarification_sha256": sha256_file(
                COMPOSITE_CLARIFICATION
            ),
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
