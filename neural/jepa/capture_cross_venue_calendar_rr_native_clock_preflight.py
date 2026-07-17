"""Capture the frozen 2024-2025 calendar-RR native-clock preflight.

The capture is outcome-free.  It queries only six one-minute quote snapshots
for the exact front/back expirations and proves that the stored Greek/IV key
universe at 10:30 and 10:35 has a native option timestamp.  Provider prices are
audited but never replace the vintage values used by the research feature.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.build_wall_native_quote_sidecar import (  # noqa: E402
    flatten_quote_response,
    local_terminal_process_evidence,
    sha256_file,
)
from neural.jepa.wall_surface_flow_environment import assert_runtime_lock  # noqa: E402

TICKERS = ("QQQ", "SPXW", "SPY")
SAMPLE_DATES = ("20240102", "20241231", "20250102", "20251231")
TARGET_TIMES = ("10:30:00", "10:35:00")
START_TIME = "10:30:00"
END_TIME = "10:35:00"
ENDPOINT = "/option/history/quote"
STATUS_ENDPOINT = "/terminal/mdds/status"
REMOTE_BASE_URL = "http://91.99.90.39:25503/v3"
DEFAULT_OPTIONS_ROOT = Path("D:/ThetaData/data_options")
DEFAULT_OUTPUT = Path(
    "D:/ThetaData/cross_venue_calendar_rr_native_clock_preflight_2024_2025_v1"
)
RUNTIME_LOCK = (
    PROJECT_ROOT / "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt"
)
PREDECLARATION = (
    PROJECT_ROOT
    / "research_papers/JEPA/CROSS_VENUE_CALENDAR_RR_LEADER_V1_PREDECLARATION.md"
)
SEAL_CLARIFICATION = (
    PROJECT_ROOT
    / "research_papers/JEPA/CROSS_VENUE_CALENDAR_RR_NATIVE_CLOCK_PREFLIGHT_SEAL_CLARIFICATION.md"
)
CAPTURE_BASE_COMMIT = "167118b0e22c8f76208fed32fc555c4d06148039"
EXPECTED_SESSIONS = 12
EXPECTED_CAPTURES = 24
EXPECTED_FULL_SESSIONS = 1_503
EXPECTED_FULL_CAPTURES = EXPECTED_FULL_SESSIONS * 2
MAX_PROJECTED_ROWS = 50_000_000
MAX_PROJECTED_RAW_BYTES = 20 * 2**30
KEYS = ("symbol", "expiration", "trade_date", "timestamp", "strike", "right")
QUOTE_COLUMNS = (*KEYS, "bid", "ask", "bid_size", "ask_size")
CODE_CLOSURE = (
    "neural/jepa/capture_cross_venue_calendar_rr_native_clock_preflight.py",
    "neural/jepa/build_wall_native_quote_sidecar.py",
    "neural/jepa/wall_surface_flow_environment.py",
    "research_papers/JEPA/CROSS_VENUE_CALENDAR_RR_LEADER_V1_PREDECLARATION.md",
    "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt",
)
SEAL_CODE_CLOSURE = (
    *CODE_CLOSURE,
    "research_papers/JEPA/CROSS_VENUE_CALENDAR_RR_NATIVE_CLOCK_PREFLIGHT_SEAL_CLARIFICATION.md",
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
            raise AssertionError(
                f"calendar-RR preflight requires clean code: {relative}"
            )
        hashes[relative] = sha256_file(PROJECT_ROOT / relative)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return commit, hashes


def committed_blob_hashes(commit: str, paths: tuple[str, ...]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for relative in paths:
        result = subprocess.run(
            ["git", "show", f"{commit}:{relative}"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
        )
        hashes[relative] = sha256_bytes(result.stdout)
    return hashes


def source_file(
    options_root: Path, ticker: str, kind: str, day: str, expiry: str
) -> Path:
    path = (
        options_root
        / ticker
        / kind
        / day[:4]
        / day[4:6]
        / f"{ticker}_{expiry}_{day}_{kind}.parquet"
    )
    if not path.is_file():
        raise FileNotFoundError(f"missing frozen {kind} source: {path}")
    return path


def available_expirations(
    options_root: Path, ticker: str, kind: str, day: str
) -> set[str]:
    folder = options_root / ticker / kind / day[:4] / day[4:6]
    suffix = f"_{day}_{kind}.parquet"
    output: set[str] = set()
    for path in folder.glob(f"{ticker}_*{suffix}"):
        stem = path.name[: -len(suffix)]
        expiry = stem[len(ticker) + 1 :]
        if len(expiry) == 8 and expiry.isdigit():
            output.add(expiry)
    return output


def discover_frozen_specs(
    options_root: str | Path = DEFAULT_OPTIONS_ROOT,
) -> pd.DataFrame:
    root = Path(options_root)
    rows: list[dict[str, Any]] = []
    for ticker in TICKERS:
        for day in SAMPLE_DATES:
            greek_expiries = available_expirations(root, ticker, "greeks", day)
            iv_expiries = available_expirations(root, ticker, "iv", day)
            common = greek_expiries.intersection(iv_expiries)
            if day not in common:
                raise AssertionError(f"missing exact front expiry: {ticker} {day}")
            later = sorted(expiry for expiry in common if expiry > day)
            if not later:
                raise AssertionError(f"missing exact back expiry: {ticker} {day}")
            for role, expiry in (("front", day), ("back", later[0])):
                greek_path = source_file(root, ticker, "greeks", day, expiry)
                iv_path = source_file(root, ticker, "iv", day, expiry)
                capture_id = hashlib.sha256(
                    f"{ticker}|{day}|{role}|{expiry}".encode("utf-8")
                ).hexdigest()[:24]
                rows.append(
                    {
                        "capture_id": capture_id,
                        "ticker": ticker,
                        "trade_date": day,
                        "role": role,
                        "expiration": expiry,
                        "greeks_path": str(greek_path.resolve()),
                        "greeks_sha256": sha256_file(greek_path),
                        "iv_path": str(iv_path.resolve()),
                        "iv_sha256": sha256_file(iv_path),
                    }
                )
    specs = (
        pd.DataFrame(rows)
        .sort_values(["ticker", "trade_date", "role"], kind="stable")
        .reset_index(drop=True)
    )
    if (
        len(specs) != EXPECTED_CAPTURES
        or specs["capture_id"].duplicated().any()
        or specs[["ticker", "trade_date"]].drop_duplicates().shape[0]
        != EXPECTED_SESSIONS
    ):
        raise AssertionError("frozen calendar-RR preflight sample changed")
    return specs


def target_timestamp_values(day: str) -> list[str]:
    date = f"{day[:4]}-{day[4:6]}-{day[6:]}"
    values: list[str] = []
    for clock in TARGET_TIMES:
        values.extend(
            (
                f"{date}T{clock}",
                f"{date}T{clock}.000",
                f"{date} {clock}",
                f"{date} {clock}.000",
            )
        )
    return values


def _normalize_right(values: pd.Series) -> pd.Series:
    return values.astype(str).str.upper().replace({"CALL": "C", "PUT": "P"})


def read_vintage_targets(
    path: str | Path, spec: dict[str, Any], kind: str
) -> pd.DataFrame:
    required = {
        "symbol",
        "expiration",
        "trade_date",
        "underlying_timestamp",
        "strike",
        "right",
        "bid",
        "ask",
    }
    schema = set(pq.read_schema(path).names)
    missing = sorted(required.difference(schema))
    if missing:
        raise KeyError(f"{kind} source lacks required fields: {missing}")
    columns = sorted(required)
    frame = pd.read_parquet(
        path,
        columns=columns,
        filters=[
            (
                "underlying_timestamp",
                "in",
                target_timestamp_values(str(spec["trade_date"])),
            )
        ],
    )
    out = frame.rename(columns={"underlying_timestamp": "timestamp"}).copy()
    out["symbol"] = out["symbol"].astype(str).str.upper()
    out["expiration"] = (
        out["expiration"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    )
    out["trade_date"] = (
        out["trade_date"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    )
    out["right"] = _normalize_right(out["right"])
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")
    for column in ("strike", "bid", "ask"):
        out[column] = pd.to_numeric(out[column], errors="coerce")
    day = str(spec["trade_date"])
    expected_times = {
        pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} {clock}")
        for clock in TARGET_TIMES
    }
    numeric = out[["strike", "bid", "ask"]].to_numpy(dtype=float)
    if (
        out.empty
        or out.isna().any().any()
        or not out["symbol"].eq(str(spec["ticker"])).all()
        or not out["expiration"].eq(str(spec["expiration"])).all()
        or not out["trade_date"].eq(day).all()
        or set(out["timestamp"].unique()) != expected_times
        or not out["right"].isin(["C", "P"]).all()
        or not np.isfinite(numeric).all()
        or out.duplicated(list(KEYS)).any()
    ):
        raise AssertionError(f"invalid {kind} vintage target key universe")
    return out.sort_values(list(KEYS), kind="stable").reset_index(drop=True)


def request_params(spec: dict[str, Any]) -> dict[str, str]:
    return {
        "symbol": str(spec["ticker"]),
        "expiration": str(spec["expiration"]),
        "date": str(spec["trade_date"]),
        "strike": "*",
        "right": "both",
        "interval": "1m",
        "format": "json",
        "start_time": START_TIME,
        "end_time": END_TIME,
    }


def normalize_quote_response(raw: Any, spec: dict[str, Any]) -> pd.DataFrame:
    frame = flatten_quote_response(raw)
    source_columns = (
        "symbol",
        "expiration",
        "timestamp",
        "strike",
        "right",
        "bid",
        "ask",
        "bid_size",
        "ask_size",
    )
    missing = sorted(set(source_columns).difference(frame.columns))
    if missing:
        raise KeyError(f"quote response lacks fields: {missing}")
    out = frame.loc[:, source_columns].copy()
    out.insert(2, "trade_date", str(spec["trade_date"]))
    out["symbol"] = out["symbol"].astype(str).str.upper()
    out["expiration"] = (
        out["expiration"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    )
    out["right"] = _normalize_right(out["right"])
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")
    for column in ("strike", "bid", "ask", "bid_size", "ask_size"):
        out[column] = pd.to_numeric(out[column], errors="coerce")
    day = str(spec["trade_date"])
    start = pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} {START_TIME}")
    end = pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} {END_TIME}")
    numeric = out[["strike", "bid", "ask", "bid_size", "ask_size"]].to_numpy(
        dtype=float
    )
    if (
        out.empty
        or out.isna().any().any()
        or not out["symbol"].eq(str(spec["ticker"])).all()
        or not out["expiration"].eq(str(spec["expiration"])).all()
        or not out["timestamp"].between(start, end, inclusive="both").all()
        or not (
            out["timestamp"].dt.second.eq(0) & out["timestamp"].dt.microsecond.eq(0)
        ).all()
        or not out["right"].isin(["C", "P"]).all()
        or not np.isfinite(numeric).all()
        or (numeric[:, 0] <= 0).any()
        or (numeric[:, 1:] < 0).any()
        or out.duplicated(list(KEYS)).any()
    ):
        raise AssertionError("invalid native quote response")
    return (
        out.loc[:, QUOTE_COLUMNS]
        .sort_values(list(KEYS), kind="stable")
        .reset_index(drop=True)
    )


def _key_hash(frame: pd.DataFrame) -> str:
    ordered = frame.sort_values(list(KEYS), kind="stable")
    payload = "".join(
        f"{r.symbol}|{r.expiration}|{r.trade_date}|{pd.Timestamp(r.timestamp).isoformat()}|{float(r.strike):.8f}|{r.right}\n"
        for r in ordered.loc[:, KEYS].itertuples(index=False)
    ).encode("utf-8")
    return sha256_bytes(payload)


def crosscheck_vintage(
    quotes: pd.DataFrame,
    greeks: pd.DataFrame,
    iv: pd.DataFrame,
    *,
    tolerance: float = 1e-9,
) -> dict[str, Any]:
    greek_keys = greeks.loc[:, KEYS]
    iv_keys = iv.loc[:, KEYS]
    if _key_hash(greek_keys) != _key_hash(iv_keys):
        raise AssertionError("Greek/IV vintage target key sets differ")
    target_times = set(greeks["timestamp"].unique())
    native = quotes[quotes["timestamp"].isin(target_times)].copy()
    merged = greeks.merge(
        native,
        on=list(KEYS),
        how="left",
        suffixes=("_vintage", "_native"),
        indicator=True,
    )
    missing = int(merged["_merge"].ne("both").sum())
    if missing:
        raise AssertionError(f"native quote misses {missing} vintage target keys")
    native_extra = int(
        len(
            native.merge(greek_keys, on=list(KEYS), how="left", indicator=True).query(
                "_merge != 'both'"
            )
        )
    )
    bid_diff = (merged["bid_native"] - merged["bid_vintage"]).abs()
    ask_diff = (merged["ask_native"] - merged["ask_vintage"]).abs()
    mismatch = bid_diff.gt(tolerance) | ask_diff.gt(tolerance)
    return {
        "greek_rows": int(len(greeks)),
        "iv_rows": int(len(iv)),
        "native_rows": int(len(quotes)),
        "native_target_rows": int(len(native)),
        "shared_vintage_rows": int(len(merged)),
        "missing_vintage_key_rows": missing,
        "native_extra_target_key_rows": native_extra,
        "greek_iv_key_set_exact": True,
        "vintage_native_key_coverage_exact": True,
        "greek_target_key_sha256": _key_hash(greek_keys),
        "native_target_key_sha256": _key_hash(native.loc[:, KEYS]),
        "revised_bid_ask_rows": int(mismatch.sum()),
        "max_bid_abs_difference": float(bid_diff.max()),
        "max_ask_abs_difference": float(ask_diff.max()),
        "crossed_native_rows": int(quotes["bid"].gt(quotes["ask"]).sum()),
    }


def source_provenance(
    base_url: str,
    *,
    terminal_jar: str | Path | None,
    timeout: float,
    requester: Callable[..., Any] = requests.get,
) -> tuple[dict[str, Any], bytes]:
    normalized = base_url.rstrip("/")
    host = (urlparse(normalized).hostname or "").lower()
    if normalized == REMOTE_BASE_URL:
        response = requester(
            normalized + STATUS_ENDPOINT,
            headers={"Accept-Encoding": "identity"},
            timeout=timeout,
        )
        response.raise_for_status()
        raw = bytes(response.content)
        if not raw or terminal_status_value(raw) != "CONNECTED":
            raise AssertionError("remote ThetaData Terminal is not CONNECTED")
        return {
            "kind": "USER_SUPPLIED_REMOTE_THETA_TERMINAL",
            "base_url": normalized,
            "status_endpoint": STATUS_ENDPOINT,
            "status_value": "CONNECTED",
            "status_raw_sha256": sha256_bytes(raw),
            "historical_provenance": "CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION",
            "live_parity": "BLOCKED_PENDING_PROSPECTIVE_PARITY",
        }, raw
    if host not in {"127.0.0.1", "localhost", "::1"} or terminal_jar is None:
        raise AssertionError(
            "capture requires the frozen local or exact remote Terminal"
        )
    evidence = local_terminal_process_evidence(normalized, terminal_jar)
    return {
        "kind": "LOCAL_FROZEN_THETA_TERMINAL",
        **evidence,
        "historical_provenance": "CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION",
        "live_parity": "BLOCKED_PENDING_PROSPECTIVE_PARITY",
    }, b""


def capture_one(
    spec: dict[str, Any],
    *,
    staging: Path,
    base_url: str,
    provenance: dict[str, Any],
    runtime: dict[str, Any],
    code_hashes: dict[str, str],
    timeout: float,
    requester: Callable[..., Any] = requests.get,
) -> dict[str, Any]:
    greeks = read_vintage_targets(spec["greeks_path"], spec, "greeks")
    iv = read_vintage_targets(spec["iv_path"], spec, "iv")
    params = request_params(spec)
    response = requester(
        base_url.rstrip("/") + ENDPOINT,
        params=params,
        headers={"Accept-Encoding": "identity"},
        timeout=timeout,
    )
    response.raise_for_status()
    raw = bytes(response.content)
    if not raw:
        raise AssertionError("empty native quote response")
    quotes = normalize_quote_response(json.loads(raw), spec)
    audit = crosscheck_vintage(quotes, greeks, iv)
    directory = (
        staging / str(spec["ticker"]) / str(spec["trade_date"]) / str(spec["role"])
    )
    directory.mkdir(parents=True, exist_ok=False)
    raw_path = directory / "response.json"
    parquet_path = directory / "quotes.parquet"
    raw_path.write_bytes(raw)
    quotes.to_parquet(parquet_path, index=False)
    manifest = {
        "schema": "cross_venue_calendar_rr_native_clock_capture_v1",
        "status": "PASS_NATIVE_CLOCK_CAPTURE",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "capture_id": str(spec["capture_id"]),
        "ticker": str(spec["ticker"]),
        "trade_date": str(spec["trade_date"]),
        "role": str(spec["role"]),
        "expiration": str(spec["expiration"]),
        "request_params": params,
        "endpoint": ENDPOINT,
        "source_provenance": provenance,
        "greeks_path": str(spec["greeks_path"]),
        "greeks_sha256": str(spec["greeks_sha256"]),
        "iv_path": str(spec["iv_path"]),
        "iv_sha256": str(spec["iv_sha256"]),
        "raw_sha256": sha256_file(raw_path),
        "parquet_sha256": sha256_file(parquet_path),
        "raw_bytes": int(len(raw)),
        "parquet_bytes": int(parquet_path.stat().st_size),
        "rows": int(len(quotes)),
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "code_hashes": code_hashes,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        **audit,
    }
    manifest_path = directory / "manifest.json"
    manifest_path.write_bytes(canonical_bytes(manifest))
    rebuilt = normalize_quote_response(json.loads(raw_path.read_bytes()), spec)
    pd.testing.assert_frame_equal(
        pd.read_parquet(parquet_path), rebuilt, check_dtype=True
    )
    return {
        "capture_id": str(spec["capture_id"]),
        "ticker": str(spec["ticker"]),
        "trade_date": str(spec["trade_date"]),
        "role": str(spec["role"]),
        "expiration": str(spec["expiration"]),
        "rows": int(len(quotes)),
        "raw_bytes": int(len(raw)),
        "parquet_bytes": int(parquet_path.stat().st_size),
        "greek_rows": int(audit["greek_rows"]),
        "native_extra_target_key_rows": int(audit["native_extra_target_key_rows"]),
        "revised_bid_ask_rows": int(audit["revised_bid_ask_rows"]),
        "crossed_native_rows": int(audit["crossed_native_rows"]),
        "raw_sha256": sha256_file(raw_path),
        "parquet_sha256": sha256_file(parquet_path),
        "manifest_sha256": sha256_file(manifest_path),
    }


def validate_existing_capture(
    spec: dict[str, Any],
    *,
    staging: Path,
    capture_code_hashes: dict[str, str],
    runtime: dict[str, Any],
) -> dict[str, Any]:
    directory = (
        staging / str(spec["ticker"]) / str(spec["trade_date"]) / str(spec["role"])
    )
    raw_path = directory / "response.json"
    parquet_path = directory / "quotes.parquet"
    manifest_path = directory / "manifest.json"
    if not (raw_path.is_file() and parquet_path.is_file() and manifest_path.is_file()):
        raise FileNotFoundError(f"incomplete existing capture: {directory}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    required_identity = {
        "schema": "cross_venue_calendar_rr_native_clock_capture_v1",
        "status": "PASS_NATIVE_CLOCK_CAPTURE",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "capture_id": str(spec["capture_id"]),
        "ticker": str(spec["ticker"]),
        "trade_date": str(spec["trade_date"]),
        "role": str(spec["role"]),
        "expiration": str(spec["expiration"]),
        "request_params": request_params(spec),
        "endpoint": ENDPOINT,
        "greeks_path": str(spec["greeks_path"]),
        "greeks_sha256": str(spec["greeks_sha256"]),
        "iv_path": str(spec["iv_path"]),
        "iv_sha256": str(spec["iv_sha256"]),
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "code_hashes": capture_code_hashes,
    }
    if any(manifest.get(key) != value for key, value in required_identity.items()):
        raise AssertionError(f"existing capture identity changed: {spec['capture_id']}")
    if (
        sha256_file(spec["greeks_path"]) != str(spec["greeks_sha256"])
        or sha256_file(spec["iv_path"]) != str(spec["iv_sha256"])
        or sha256_file(raw_path) != manifest.get("raw_sha256")
        or sha256_file(parquet_path) != manifest.get("parquet_sha256")
    ):
        raise AssertionError(
            f"existing capture/source hash changed: {spec['capture_id']}"
        )
    raw = raw_path.read_bytes()
    rebuilt = normalize_quote_response(json.loads(raw), spec)
    stored = pd.read_parquet(parquet_path)
    try:
        pd.testing.assert_frame_equal(stored, rebuilt, check_dtype=True)
    except AssertionError as exc:
        raise AssertionError(
            f"raw/parquet reconstruction changed: {spec['capture_id']}"
        ) from exc
    greeks = read_vintage_targets(spec["greeks_path"], spec, "greeks")
    iv = read_vintage_targets(spec["iv_path"], spec, "iv")
    audit = crosscheck_vintage(rebuilt, greeks, iv)
    if any(manifest.get(key) != value for key, value in audit.items()):
        raise AssertionError(f"existing vintage audit changed: {spec['capture_id']}")
    if int(manifest.get("rows", -1)) != len(rebuilt):
        raise AssertionError(
            f"existing capture row count changed: {spec['capture_id']}"
        )
    return {
        "capture_id": str(spec["capture_id"]),
        "ticker": str(spec["ticker"]),
        "trade_date": str(spec["trade_date"]),
        "role": str(spec["role"]),
        "expiration": str(spec["expiration"]),
        "rows": int(len(rebuilt)),
        "raw_bytes": int(raw_path.stat().st_size),
        "parquet_bytes": int(parquet_path.stat().st_size),
        "greek_rows": int(audit["greek_rows"]),
        "native_extra_target_key_rows": int(audit["native_extra_target_key_rows"]),
        "revised_bid_ask_rows": int(audit["revised_bid_ask_rows"]),
        "crossed_native_rows": int(audit["crossed_native_rows"]),
        "raw_sha256": sha256_file(raw_path),
        "parquet_sha256": sha256_file(parquet_path),
        "manifest_sha256": sha256_file(manifest_path),
    }


def existing_staging_provenance(specs: pd.DataFrame, staging: Path) -> dict[str, Any]:
    values: list[dict[str, Any]] = []
    for spec in specs.to_dict("records"):
        path = (
            staging
            / str(spec["ticker"])
            / str(spec["trade_date"])
            / str(spec["role"])
            / "manifest.json"
        )
        manifest = json.loads(path.read_text(encoding="utf-8"))
        provenance = manifest.get("source_provenance")
        if not isinstance(provenance, dict):
            raise AssertionError("existing capture lacks source provenance")
        values.append(provenance)
    first = values[0]
    if any(canonical_bytes(value) != canonical_bytes(first) for value in values[1:]):
        raise AssertionError("existing capture provenance is not uniform")
    return first


def projected_cost(index: pd.DataFrame) -> dict[str, Any]:
    if len(index) != EXPECTED_CAPTURES:
        raise AssertionError("cost projection requires all preflight captures")
    factor = EXPECTED_FULL_CAPTURES / EXPECTED_CAPTURES
    rows = int(np.ceil(index["rows"].sum() * factor))
    raw = int(np.ceil(index["raw_bytes"].sum() * factor))
    parquet = int(np.ceil(index["parquet_bytes"].sum() * factor))
    return {
        "preflight_sessions": EXPECTED_SESSIONS,
        "preflight_captures": EXPECTED_CAPTURES,
        "full_sessions": EXPECTED_FULL_SESSIONS,
        "full_captures": EXPECTED_FULL_CAPTURES,
        "projection_factor": factor,
        "preflight_rows": int(index["rows"].sum()),
        "preflight_raw_bytes": int(index["raw_bytes"].sum()),
        "preflight_parquet_bytes": int(index["parquet_bytes"].sum()),
        "projected_rows": rows,
        "projected_raw_bytes": raw,
        "projected_raw_gib": raw / 2**30,
        "projected_parquet_bytes": parquet,
        "projected_parquet_gib": parquet / 2**30,
        "row_limit": MAX_PROJECTED_ROWS,
        "raw_byte_limit": MAX_PROJECTED_RAW_BYTES,
        "cost_gate_pass": rows <= MAX_PROJECTED_ROWS and raw <= MAX_PROJECTED_RAW_BYTES,
    }


def finalize_staging(
    *,
    output: Path,
    staging: Path,
    specs: pd.DataFrame,
    rows: list[dict[str, Any]],
    provenance: dict[str, Any],
    runtime: dict[str, Any],
    capture_git_commit: str,
    capture_code_hashes: dict[str, str],
    seal_git_commit: str,
    seal_code_hashes: dict[str, str],
) -> dict[str, Any]:
    if output.exists() or not staging.is_dir():
        raise AssertionError(
            "offline finalizer requires existing staging and absent output"
        )
    index = (
        pd.DataFrame(rows)
        .sort_values(["ticker", "trade_date", "role"], kind="stable")
        .reset_index(drop=True)
    )
    if len(index) != EXPECTED_CAPTURES or index["capture_id"].duplicated().any():
        raise AssertionError("offline finalizer capture index is incomplete")
    cost = projected_cost(index)
    status = (
        "PASS_CROSS_VENUE_CALENDAR_RR_NATIVE_CLOCK_PREFLIGHT"
        if bool(cost["cost_gate_pass"])
        else "REJECTED_CROSS_VENUE_CALENDAR_RR_NATIVE_CLOCK_PREFLIGHT"
    )
    index_path = staging / "capture_index.csv"
    cost_path = staging / "cost_projection.json"
    seal_path = staging / "seal.json"
    if index_path.exists() or cost_path.exists() or seal_path.exists():
        raise FileExistsError("aggregate staging artifact unexpectedly exists")
    index.to_csv(index_path, index=False)
    cost_path.write_bytes(canonical_bytes(cost))
    seal = {
        "schema": "cross_venue_calendar_rr_native_clock_preflight_seal_v1",
        "status": status,
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "offline_existing_staging_seal": True,
        "capture_git_commit": capture_git_commit,
        "capture_code_hashes": capture_code_hashes,
        "seal_git_commit": seal_git_commit,
        "seal_code_hashes": seal_code_hashes,
        "seal_clarification_sha256": sha256_file(SEAL_CLARIFICATION),
        "sessions": EXPECTED_SESSIONS,
        "captures": int(len(index)),
        "rows": int(index["rows"].sum()),
        "missing_vintage_key_rows": 0,
        "native_extra_target_key_rows": int(
            index["native_extra_target_key_rows"].sum()
        ),
        "revised_bid_ask_rows": int(index["revised_bid_ask_rows"].sum()),
        "crossed_native_rows": int(index["crossed_native_rows"].sum()),
        "capture_index_sha256": sha256_file(index_path),
        "cost_projection_sha256": sha256_file(cost_path),
        "cost_projection": cost,
        "sample_spec_sha256": sha256_bytes(
            specs.to_csv(index=False, lineterminator="\n").encode("utf-8")
        ),
        "source_provenance": provenance,
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment": runtime["environment"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    seal_path.write_bytes(canonical_bytes(seal))
    staging.rename(output)
    return seal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--options-root", type=Path, default=DEFAULT_OPTIONS_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--base-url", default=REMOTE_BASE_URL)
    parser.add_argument("--terminal-jar")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--seal-existing-staging", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 1 <= args.workers <= 4:
        raise ValueError("workers must be within 1..4")
    output = args.output_root.resolve()
    staging = output.with_name(output.name + ".staging")
    runtime = assert_runtime_lock(RUNTIME_LOCK)
    specs = discover_frozen_specs(args.options_root)
    if args.seal_existing_staging:
        if output.exists() or not staging.is_dir():
            raise FileExistsError(
                "offline seal requires absent output and existing default staging"
            )
        if (staging / "errors.json").exists():
            raise AssertionError("offline seal refuses staging with errors.json")
        seal_commit, seal_code_hashes = committed_code_state(SEAL_CODE_CLOSURE)
        capture_code_hashes = committed_blob_hashes(CAPTURE_BASE_COMMIT, CODE_CLOSURE)
        provenance = existing_staging_provenance(specs, staging)
        rows = [
            validate_existing_capture(
                spec,
                staging=staging,
                capture_code_hashes=capture_code_hashes,
                runtime=runtime,
            )
            for spec in specs.to_dict("records")
        ]
        seal = finalize_staging(
            output=output,
            staging=staging,
            specs=specs,
            rows=rows,
            provenance=provenance,
            runtime=runtime,
            capture_git_commit=CAPTURE_BASE_COMMIT,
            capture_code_hashes=capture_code_hashes,
            seal_git_commit=seal_commit,
            seal_code_hashes=seal_code_hashes,
        )
        print(json.dumps(seal, indent=2, sort_keys=True))
        return
    if output.exists() or staging.exists():
        raise FileExistsError("immutable calendar-RR preflight output already exists")
    commit, code_hashes = committed_code_state()
    provenance, status_raw = source_provenance(
        args.base_url,
        terminal_jar=args.terminal_jar,
        timeout=args.timeout,
    )
    staging.mkdir(parents=True, exist_ok=False)
    if status_raw:
        (staging / "remote_terminal_status.json").write_bytes(status_raw)
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                capture_one,
                spec,
                staging=staging,
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
                rows.append(future.result())
            except Exception as exc:
                errors.append(
                    {
                        "capture_id": str(spec["capture_id"]),
                        "ticker": str(spec["ticker"]),
                        "trade_date": str(spec["trade_date"]),
                        "role": str(spec["role"]),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
            print(
                f"[CAL_RR_NATIVE_PREFLIGHT] {count}/{len(specs)} errors={len(errors)}",
                flush=True,
            )
    if errors or len(rows) != EXPECTED_CAPTURES:
        (staging / "errors.json").write_bytes(canonical_bytes({"errors": errors}))
        raise AssertionError(f"calendar-RR native-clock preflight failed: {errors[:5]}")
    seal = finalize_staging(
        output=output,
        staging=staging,
        specs=specs,
        rows=rows,
        provenance=provenance,
        runtime=runtime,
        capture_git_commit=commit,
        capture_code_hashes=code_hashes,
        seal_git_commit=commit,
        seal_code_hashes=code_hashes,
    )
    print(json.dumps(seal, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
