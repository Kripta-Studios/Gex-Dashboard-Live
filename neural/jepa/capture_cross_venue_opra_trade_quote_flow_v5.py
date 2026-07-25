"""Capture immutable, outcome-free OPRA trade/quote sources for V5."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.wall_surface_flow_environment import (  # noqa: E402
    assert_runtime_lock,
    sha256_file,
)

SENSORS = ("QQQ", "SPY")
YEARS = ("2023", "2024", "2025")
START_DATE = "20230101"
END_DATE = "20251231"
EXPECTED_DATES = 752
EXPECTED_CAPTURES = EXPECTED_DATES * len(SENSORS)
EXPECTED_COUNTS = {"2023": 250, "2024": 252, "2025": 250}
EXPECTED_DATE_SHA256 = (
    "e7786a1a8861ef8aaaeb8aed5cfe08ccaea50c8bcec575800ec044e88890b8f9"
)
REMOTE_BASE_URL = "http://91.99.90.39:25503/v3"
STATUS_ENDPOINT = "/terminal/mdds/status"
ENDPOINT = "/option/history/trade_quote"
DEFAULT_OPTIONS_ROOT = Path("D:/ThetaData/data_options")
DEFAULT_OUTPUT = Path(
    "D:/ThetaData/cross_venue_opra_trade_quote_flow_v5_capture_2023_2025_v1"
)
RUNTIME_LOCK = PROJECT_ROOT / (
    "research_papers/JEPA/requirements-cross-venue-opra-trade-quote-flow-v5.txt"
)
PREDECLARATION = PROJECT_ROOT / (
    "research_papers/JEPA/"
    "CROSS_VENUE_OPRA_TRADE_QUOTE_FLOW_V5_PREDECLARATION.md"
)
SOURCE_INVENTORY = PROJECT_ROOT / (
    "research_papers/JEPA/CAUSAL_SOURCE_INVENTORY_20260725.md"
)
EXPECTED_PREDECLARATION_SHA256 = (
    "5fb6fe3dbece994a1eb48c42e3ca2d0ce40c2ff7cea92f91dfb9a58ea8f82e19"
)
EXPECTED_SOURCE_INVENTORY_SHA256 = (
    "bd673f74c7be365a1ef5204176beea7fb719ec93692aebf236fa7037ec9fbcfc"
)
CODE_CLOSURE = (
    "neural/jepa/capture_cross_venue_opra_trade_quote_flow_v5.py",
    "neural/jepa/build_cross_venue_opra_trade_quote_flow_v5.py",
    "neural/jepa/audit_cross_venue_opra_trade_quote_flow_v5.py",
    "neural/jepa/wall_surface_flow_environment.py",
    "research_papers/JEPA/CROSS_VENUE_OPRA_TRADE_QUOTE_FLOW_V5_PREDECLARATION.md",
    "research_papers/JEPA/CAUSAL_SOURCE_INVENTORY_20260725.md",
    "research_papers/JEPA/requirements-cross-venue-opra-trade-quote-flow-v5.txt",
)
TRADE_COLUMNS = (
    "symbol",
    "expiration",
    "trade_date",
    "strike",
    "right",
    "trade_timestamp",
    "quote_timestamp",
    "sequence",
    "condition",
    "size",
    "exchange",
    "price",
    "bid_size",
    "bid_exchange",
    "bid",
    "bid_condition",
    "ask_size",
    "ask_exchange",
    "ask",
    "ask_condition",
)
RESPONSE_COLUMNS = tuple(column for column in TRADE_COLUMNS if column != "trade_date")
DUPLICATE_KEY = (
    "symbol",
    "expiration",
    "strike",
    "right",
    "trade_timestamp",
    "sequence",
    "exchange",
    "price",
    "size",
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def committed_code_state(
    paths: tuple[str, ...] = CODE_CLOSURE,
) -> tuple[str, dict[str, str]]:
    hashes: dict[str, str] = {}
    for relative in paths:
        subprocess.run(
            ["git", "ls-files", "--error-unmatch", relative],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--", relative],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if dirty:
            raise AssertionError(f"V5 requires clean committed code: {relative}")
        hashes[relative] = sha256_file(PROJECT_ROOT / relative)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    origin = subprocess.run(
        ["git", "rev-parse", "origin/main"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if commit != origin or branch != "main":
        raise AssertionError("V5 capture requires main with HEAD == origin/main")
    return commit, hashes


def ordered_hash(values: list[str]) -> str:
    return sha256_bytes(("\n".join(sorted(values)) + "\n").encode("utf-8"))


def discover_sessions(
    options_root: str | Path = DEFAULT_OPTIONS_ROOT,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    root = Path(options_root)
    pattern_by_sensor = {
        sensor: re.compile(
            rf"^{sensor}_(?P<expiry>\d{{8}})_(?P<trade>\d{{8}})_ohlc\.parquet$"
        )
        for sensor in SENSORS
    }
    dates_by_sensor: dict[str, list[str]] = {}
    for sensor in SENSORS:
        dates: set[str] = set()
        for year in YEARS:
            folder = root / sensor / "ohlc" / year
            for path in folder.rglob(f"{sensor}_*_*_ohlc.parquet"):
                match = pattern_by_sensor[sensor].match(path.name)
                if not match:
                    continue
                expiry = match.group("expiry")
                trade_date = match.group("trade")
                if expiry == trade_date and trade_date.startswith(year):
                    dates.add(trade_date)
        dates_by_sensor[sensor] = sorted(dates)
    if dates_by_sensor["QQQ"] != dates_by_sensor["SPY"]:
        raise AssertionError("QQQ/SPY exact-0DTE filename date universes differ")
    dates = dates_by_sensor["QQQ"]
    counts = {
        year: sum(value.startswith(year) for value in dates) for year in YEARS
    }
    date_hash = ordered_hash(dates)
    if (
        len(dates) != EXPECTED_DATES
        or counts != EXPECTED_COUNTS
        or date_hash != EXPECTED_DATE_SHA256
        or any(not START_DATE <= value <= END_DATE for value in dates)
    ):
        raise AssertionError("V5 exact-0DTE session universe changed")
    rows = []
    for sensor in SENSORS:
        for trade_date in dates:
            rows.append(
                {
                    "capture_id": sha256_bytes(
                        f"{sensor}|{trade_date}|trade_quote_v5".encode("utf-8")
                    )[:24],
                    "sensor": sensor,
                    "trade_date": trade_date,
                    "expiration": trade_date,
                    "year": trade_date[:4],
                    "month": trade_date[:6],
                }
            )
    frame = pd.DataFrame(rows).sort_values(
        ["sensor", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    if len(frame) != EXPECTED_CAPTURES or frame["capture_id"].duplicated().any():
        raise AssertionError("V5 capture universe cardinality changed")
    audit = {
        "session_universe_source": (
            "LOCAL_EXACT_0DTE_OHLC_FILENAME_METADATA_ONLY_NO_FILE_READ"
        ),
        "dates_per_sensor": EXPECTED_DATES,
        "captures": EXPECTED_CAPTURES,
        "dates_by_year": counts,
        "date_sha256": date_hash,
        "no_source_file_values_read": True,
    }
    return frame, audit


def request_params(spec: dict[str, Any]) -> dict[str, str]:
    return {
        "symbol": str(spec["sensor"]),
        "expiration": str(spec["expiration"]),
        "strike": "*",
        "right": "both",
        "date": str(spec["trade_date"]),
        "start_time": "09:30:00.000",
        "end_time": "10:34:59.999",
        "exclusive": "true",
        "format": "ndjson",
    }


def _parse_ndjson(raw: bytes) -> list[dict[str, Any]]:
    if not raw.strip():
        raise AssertionError("empty V5 trade_quote response")
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise AssertionError(f"invalid NDJSON line {number}") from exc
        if not isinstance(value, dict):
            raise AssertionError(f"NDJSON line {number} is not an object")
        rows.append(value)
    if not rows:
        raise AssertionError("V5 trade_quote response contains no objects")
    return rows


def normalize_trade_quote(raw: bytes, spec: dict[str, Any]) -> pd.DataFrame:
    frame = pd.DataFrame(_parse_ndjson(raw))
    missing = sorted(set(RESPONSE_COLUMNS).difference(frame.columns))
    if missing:
        raise KeyError(f"trade_quote response lacks fields: {missing}")
    out = frame.loc[:, RESPONSE_COLUMNS].copy()
    out.insert(2, "trade_date", str(spec["trade_date"]))
    out["symbol"] = out["symbol"].astype(str).str.upper()
    out["expiration"] = (
        out["expiration"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    )
    out["right"] = (
        out["right"].astype(str).str.upper().replace({"CALL": "C", "PUT": "P"})
    )
    for column in ("trade_timestamp", "quote_timestamp"):
        out[column] = pd.to_datetime(out[column], errors="coerce", format="mixed")
        if getattr(out[column].dt, "tz", None) is not None:
            raise AssertionError("V5 timestamps must be native naive ET")
    integer_columns = (
        "sequence",
        "condition",
        "size",
        "exchange",
        "bid_size",
        "bid_exchange",
        "bid_condition",
        "ask_size",
        "ask_exchange",
        "ask_condition",
    )
    numeric_columns = ("strike", "price", "bid", "ask")
    for column in integer_columns:
        out[column] = pd.to_numeric(out[column], errors="coerce").astype("Int64")
    for column in numeric_columns:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    day = str(spec["trade_date"])
    start = pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} 09:30:00")
    end = pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} 10:35:00")
    numeric = out.loc[:, numeric_columns].to_numpy(dtype=float)
    if (
        out.empty
        or out.isna().any().any()
        or not out["symbol"].eq(str(spec["sensor"])).all()
        or not out["expiration"].eq(day).all()
        or not out["right"].isin(["C", "P"]).all()
        or not out["trade_timestamp"].ge(start).all()
        or not out["trade_timestamp"].lt(end).all()
        or not out["quote_timestamp"].lt(out["trade_timestamp"]).all()
        or not np.isfinite(numeric).all()
        or (numeric[:, 0] <= 0).any()
        or out.duplicated(list(DUPLICATE_KEY)).any()
    ):
        raise AssertionError("invalid or duplicate V5 trade_quote response")
    return out.sort_values(
        ["trade_timestamp", "sequence", "right", "strike", "exchange"],
        kind="stable",
    ).reset_index(drop=True)


def terminal_status_value(raw: bytes) -> str:
    try:
        value: Any = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        value = raw.decode("utf-8", errors="strict")
    if isinstance(value, dict):
        for key in ("status", "response", "value"):
            if key in value:
                value = value[key]
                break
    return str(value).strip().strip('"').upper()


def source_provenance(
    base_url: str,
    *,
    timeout: float,
    requester: Callable[..., Any] = requests.get,
) -> tuple[dict[str, Any], bytes]:
    normalized = base_url.rstrip("/")
    if normalized != REMOTE_BASE_URL:
        raise AssertionError("V5 capture requires the exact frozen remote Terminal")
    response = requester(
        normalized + STATUS_ENDPOINT,
        headers={"Accept-Encoding": "identity"},
        timeout=timeout,
    )
    response.raise_for_status()
    raw = bytes(response.content)
    if terminal_status_value(raw) != "CONNECTED":
        raise AssertionError("remote Theta Terminal is not CONNECTED")
    return {
        "kind": "USER_SUPPLIED_REMOTE_THETA_TERMINAL",
        "base_url": normalized,
        "status_endpoint": STATUS_ENDPOINT,
        "status_value": "CONNECTED",
        "status_raw_sha256": sha256_bytes(raw),
        "historical_provenance": "CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION",
        "live_parity": "BLOCKED_PENDING_PROSPECTIVE_PARITY",
    }, raw


def capture_directory(root: Path, spec: dict[str, Any]) -> Path:
    return root / str(spec["sensor"]) / str(spec["trade_date"])


def capture_one(
    spec: dict[str, Any],
    *,
    output: Path,
    base_url: str,
    provenance: dict[str, Any],
    runtime: dict[str, Any],
    code_hashes: dict[str, str],
    timeout: float,
    requester: Callable[..., Any] = requests.get,
) -> dict[str, Any]:
    directory = capture_directory(output, spec)
    staging = directory.with_name(directory.name + ".staging")
    if directory.exists() or staging.exists():
        raise FileExistsError(f"immutable V5 capture exists: {directory}")
    response = requester(
        base_url.rstrip("/") + ENDPOINT,
        params=request_params(spec),
        headers={"Accept-Encoding": "identity"},
        timeout=timeout,
    )
    response.raise_for_status()
    raw = bytes(response.content)
    trades = normalize_trade_quote(raw, spec)
    staging.mkdir(parents=True, exist_ok=False)
    raw_path = staging / "response.ndjson"
    parquet_path = staging / "trades.parquet"
    raw_path.write_bytes(raw)
    trades.to_parquet(parquet_path, index=False)
    safe_headers = {
        key.lower(): value
        for key, value in response.headers.items()
        if key.lower() in {"content-type", "content-length"}
    }
    manifest = {
        "schema": "cross_venue_opra_trade_quote_flow_v5_capture_v1",
        "status": "PASS_OUTCOME_FREE_SOURCE_CAPTURE",
        "market_values_accessed": True,
        "outcome_clock_accessed": False,
        "outcome_2026_accessed": False,
        "production_modified": False,
        "capture_id": str(spec["capture_id"]),
        "sensor": str(spec["sensor"]),
        "trade_date": str(spec["trade_date"]),
        "expiration": str(spec["expiration"]),
        "endpoint": ENDPOINT,
        "request_params": request_params(spec),
        "response_headers": safe_headers,
        "source_provenance": provenance,
        "rows": int(len(trades)),
        "raw_bytes": len(raw),
        "parquet_bytes": int(parquet_path.stat().st_size),
        "raw_sha256": sha256_file(raw_path),
        "parquet_sha256": sha256_file(parquet_path),
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "code_hashes": code_hashes,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path = staging / "manifest.json"
    manifest_path.write_bytes(canonical_bytes(manifest))
    rebuilt = normalize_trade_quote(raw_path.read_bytes(), spec)
    pd.testing.assert_frame_equal(
        pd.read_parquet(parquet_path), rebuilt, check_dtype=True
    )
    manifest_hash = sha256_file(manifest_path)
    staging.rename(directory)
    return {
        "capture_id": str(spec["capture_id"]),
        "sensor": str(spec["sensor"]),
        "trade_date": str(spec["trade_date"]),
        "expiration": str(spec["expiration"]),
        "rows": int(len(trades)),
        "raw_bytes": len(raw),
        "parquet_bytes": int((directory / "trades.parquet").stat().st_size),
        "raw_sha256": sha256_file(directory / "response.ndjson"),
        "parquet_sha256": sha256_file(directory / "trades.parquet"),
        "manifest_sha256": manifest_hash,
    }


def validate_existing_capture(
    spec: dict[str, Any],
    *,
    output: Path,
    provenance: dict[str, Any],
    runtime: dict[str, Any],
    code_hashes: dict[str, str],
) -> dict[str, Any]:
    directory = capture_directory(output, spec)
    raw_path = directory / "response.ndjson"
    parquet_path = directory / "trades.parquet"
    manifest_path = directory / "manifest.json"
    if not (raw_path.is_file() and parquet_path.is_file() and manifest_path.is_file()):
        raise FileNotFoundError(f"incomplete existing V5 capture: {directory}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = {
        "schema": "cross_venue_opra_trade_quote_flow_v5_capture_v1",
        "status": "PASS_OUTCOME_FREE_SOURCE_CAPTURE",
        "outcome_clock_accessed": False,
        "outcome_2026_accessed": False,
        "production_modified": False,
        "capture_id": str(spec["capture_id"]),
        "sensor": str(spec["sensor"]),
        "trade_date": str(spec["trade_date"]),
        "expiration": str(spec["expiration"]),
        "endpoint": ENDPOINT,
        "request_params": request_params(spec),
        "source_provenance": provenance,
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "code_hashes": code_hashes,
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise AssertionError(f"existing V5 capture identity changed: {directory}")
    if (
        sha256_file(raw_path) != manifest.get("raw_sha256")
        or sha256_file(parquet_path) != manifest.get("parquet_sha256")
    ):
        raise AssertionError(f"existing V5 capture hash changed: {directory}")
    rebuilt = normalize_trade_quote(raw_path.read_bytes(), spec)
    pd.testing.assert_frame_equal(
        pd.read_parquet(parquet_path), rebuilt, check_dtype=True
    )
    if int(manifest.get("rows", -1)) != len(rebuilt):
        raise AssertionError(f"existing V5 row count changed: {directory}")
    return {
        "capture_id": str(spec["capture_id"]),
        "sensor": str(spec["sensor"]),
        "trade_date": str(spec["trade_date"]),
        "expiration": str(spec["expiration"]),
        "rows": int(len(rebuilt)),
        "raw_bytes": int(raw_path.stat().st_size),
        "parquet_bytes": int(parquet_path.stat().st_size),
        "raw_sha256": sha256_file(raw_path),
        "parquet_sha256": sha256_file(parquet_path),
        "manifest_sha256": sha256_file(manifest_path),
    }


def capture_or_resume(
    spec: dict[str, Any],
    *,
    output: Path,
    base_url: str,
    provenance: dict[str, Any],
    runtime: dict[str, Any],
    code_hashes: dict[str, str],
    timeout: float,
) -> tuple[dict[str, Any], bool]:
    directory = capture_directory(output, spec)
    staging = directory.with_name(directory.name + ".staging")
    if staging.exists():
        raise AssertionError(f"interrupted V5 capture requires audit: {staging}")
    if directory.exists():
        return (
            validate_existing_capture(
                spec,
                output=output,
                provenance=provenance,
                runtime=runtime,
                code_hashes=code_hashes,
            ),
            True,
        )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            return (
                capture_one(
                    spec,
                    output=output,
                    base_url=base_url,
                    provenance=provenance,
                    runtime=runtime,
                    code_hashes=code_hashes,
                    timeout=timeout,
                ),
                False,
            )
        except requests.RequestException as exc:
            last_error = exc
            if directory.exists() or staging.exists() or attempt == 2:
                break
            time.sleep(1.0 + attempt)
    raise RuntimeError(f"V5 request failed after retries: {last_error}")


def initialize_root(
    output: Path,
    *,
    specs: pd.DataFrame,
    contract: dict[str, Any],
    status_raw: bytes,
) -> None:
    state = output / "_state"
    contract_path = state / "capture_contract.json"
    universe_path = state / "universe.csv"
    expected_universe = specs.to_csv(index=False, lineterminator="\n").encode(
        "utf-8"
    )
    if not output.exists():
        state.mkdir(parents=True, exist_ok=False)
        universe_path.write_bytes(expected_universe)
        payload = {**contract, "universe_file_sha256": sha256_file(universe_path)}
        contract_path.write_bytes(canonical_bytes(payload))
        (state / "remote_terminal_status.txt").write_bytes(status_raw)
        return
    if not (contract_path.is_file() and universe_path.is_file()):
        raise AssertionError("existing V5 root lacks immutable state")
    stored = json.loads(contract_path.read_text(encoding="utf-8"))
    expected = {**contract, "universe_file_sha256": sha256_file(universe_path)}
    if stored != expected or universe_path.read_bytes() != expected_universe:
        raise AssertionError("V5 capture resume contract changed")


def write_progress(output: Path, completed: int, resumed: int, errors: int) -> None:
    payload = {
        "schema": "cross_venue_opra_trade_quote_flow_v5_progress_v1",
        "status": "CAPTURE_IN_PROGRESS",
        "captures_completed": completed,
        "captures_resumed": resumed,
        "captures_expected": EXPECTED_CAPTURES,
        "errors": errors,
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    path = output / "_state/progress.json"
    staging = path.with_suffix(".json.staging")
    staging.write_bytes(canonical_bytes(payload))
    staging.replace(path)


def seal_capture(
    output: Path,
    *,
    rows: list[dict[str, Any]],
    contract: dict[str, Any],
) -> dict[str, Any]:
    index = pd.DataFrame(rows).sort_values(
        ["sensor", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    if len(index) != EXPECTED_CAPTURES or index["capture_id"].duplicated().any():
        raise AssertionError("cannot seal incomplete V5 capture")
    staging = output / "_seal.staging"
    final = output / "_seal"
    if staging.exists() or final.exists():
        raise FileExistsError("V5 capture seal already exists")
    staging.mkdir()
    index_path = staging / "capture_index.csv"
    index.to_csv(index_path, index=False, lineterminator="\n")
    seal = {
        "schema": "cross_venue_opra_trade_quote_flow_v5_capture_seal_v1",
        "status": "PASS_OUTCOME_FREE_SOURCE_CAPTURE",
        "market_values_accessed": True,
        "outcome_clock_accessed": False,
        "outcome_2026_accessed": False,
        "production_modified": False,
        "git_commit": contract["git_commit"],
        "code_hashes": contract["code_hashes"],
        "runtime_lock_sha256": contract["runtime_lock_sha256"],
        "runtime_environment_sha256": contract["runtime_environment_sha256"],
        "source_provenance": contract["source_provenance"],
        "universe_audit": contract["universe_audit"],
        "captures": int(len(index)),
        "rows": int(index["rows"].sum()),
        "raw_bytes": int(index["raw_bytes"].sum()),
        "parquet_bytes": int(index["parquet_bytes"].sum()),
        "capture_index_sha256": sha256_file(index_path),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (staging / "seal.json").write_bytes(canonical_bytes(seal))
    staging.rename(final)
    return seal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--options-root", type=Path, default=DEFAULT_OPTIONS_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--base-url", default=REMOTE_BASE_URL)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=600.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 1 <= args.workers <= 4:
        raise ValueError("workers must be within 1..4")
    if sha256_file(PREDECLARATION) != EXPECTED_PREDECLARATION_SHA256:
        raise AssertionError("V5 predeclaration hash changed")
    if sha256_file(SOURCE_INVENTORY) != EXPECTED_SOURCE_INVENTORY_SHA256:
        raise AssertionError("V5 source inventory hash changed")
    commit, code_hashes = committed_code_state()
    runtime = assert_runtime_lock(RUNTIME_LOCK)
    specs, universe_audit = discover_sessions(args.options_root)
    provenance, status_raw = source_provenance(
        args.base_url, timeout=args.timeout
    )
    contract = {
        "schema": "cross_venue_opra_trade_quote_flow_v5_capture_contract_v1",
        "status": "CAPTURE_IN_PROGRESS",
        "outcome_clock_accessed": False,
        "outcome_2026_accessed": False,
        "production_modified": False,
        "git_commit": commit,
        "code_hashes": code_hashes,
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "source_provenance": provenance,
        "universe_audit": universe_audit,
        "predeclaration_sha256": EXPECTED_PREDECLARATION_SHA256,
        "source_inventory_sha256": EXPECTED_SOURCE_INVENTORY_SHA256,
    }
    output = args.output_root.resolve()
    initialize_root(
        output, specs=specs, contract=contract, status_raw=status_raw
    )
    if (output / "_seal").exists():
        raise FileExistsError("V5 capture is already sealed")
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    resumed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                capture_or_resume,
                spec,
                output=output,
                base_url=args.base_url,
                provenance=provenance,
                runtime=runtime,
                code_hashes=code_hashes,
                timeout=args.timeout,
            ): spec
            for spec in specs.to_dict("records")
        }
        for count, future in enumerate(as_completed(futures), start=1):
            spec = futures[future]
            try:
                row, was_resumed = future.result()
                rows.append(row)
                resumed += int(was_resumed)
            except Exception as exc:
                errors.append(
                    {
                        "capture_id": str(spec["capture_id"]),
                        "sensor": str(spec["sensor"]),
                        "trade_date": str(spec["trade_date"]),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
            write_progress(output, len(rows), resumed, len(errors))
            if count % 10 == 0 or count == len(specs):
                print(
                    f"[OPRA_V5_CAPTURE] {count}/{len(specs)} "
                    f"completed={len(rows)} resumed={resumed} errors={len(errors)}",
                    flush=True,
                )
    if errors or len(rows) != EXPECTED_CAPTURES:
        (output / "_state/errors.json").write_bytes(
            canonical_bytes({"errors": errors})
        )
        raise AssertionError(f"V5 capture failed: {errors[:5]}")
    seal = seal_capture(output, rows=rows, contract=contract)
    write_progress(output, len(rows), resumed, 0)
    print(json.dumps(seal, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
