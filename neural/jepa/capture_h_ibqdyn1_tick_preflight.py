"""Capture and seal the frozen 12-event/24-contract H-IBQDYN1 tick preflight."""

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
    local_terminal_process_evidence,
)
from neural.jepa.build_wall_quote_tick_dynamics_sidecar import (  # noqa: E402
    sha256_file,
)
from neural.jepa.wall_surface_flow_environment import assert_runtime_lock  # noqa: E402

ENDPOINT = "/option/history/quote"
REMOTE_STATUS_ENDPOINT = "/terminal/mdds/status"
REMOTE_BASE_URL = "http://91.99.90.39:25503/v3"
PROOF_DIR = (
    PROJECT_ROOT
    / "research_papers/JEPA/results/_diagnostics/"
    "h_ibqdyn1_listing_feasibility_202208_202512_v1"
)
EXPECTED_PROOF_MANIFEST_SHA256 = (
    "2095c75dce813368ea13a9fcaf0170c3087db806eec13212b069884119c867e9"
)
EXPECTED_PROOF_SHA256 = (
    "b1fc66137666ff723349bb14390c4d0e87f399dfcdcf0f819f43baffbac306d2"
)
EXPECTED_SAMPLE_SHA256 = (
    "485d8f91cebc088aa30a89c7c6e2a9a438c35343182037d6151c383fceb8ce3a"
)
EXPECTED_ELIGIBLE_ID_SHA256 = (
    "8e68c12c431aad63abce6fc2621738c5ba3622dd3b4acc6cfcdf376fe6dd652e"
)
EXPECTED_EVENTS = 16_926
EXPECTED_ELIGIBLE_EVENTS = 16_852
EXPECTED_SAMPLE_EVENTS = 12
EXPECTED_CONTRACTS = 24
MAX_PROJECTED_ROWS = 150_000_000
MAX_PROJECTED_RAW_BYTES = 20 * 2**30
PREDECLARATION = "research_papers/JEPA/H_IBQDYN1_FEASIBILITY_PREDECLARATION.md"
FINAL_FIT_AMENDMENT = "research_papers/JEPA/H_IBQDYN1_2026_FINAL_FIT_AMENDMENT.md"
RUNTIME_LOCK = "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt"
PROOF_MANIFEST = (
    "research_papers/JEPA/results/_diagnostics/"
    "h_ibqdyn1_listing_feasibility_202208_202512_v1/manifest.json"
)
CODE_CLOSURE = (
    "neural/jepa/capture_h_ibqdyn1_tick_preflight.py",
    "neural/jepa/build_h_ibqdyn1_feasibility.py",
    "neural/jepa/build_wall_native_quote_sidecar.py",
    "neural/jepa/build_wall_quote_tick_dynamics_sidecar.py",
    "neural/jepa/wall_surface_flow_environment.py",
    PREDECLARATION,
    FINAL_FIT_AMENDMENT,
    PROOF_MANIFEST,
    RUNTIME_LOCK,
)
OUTPUT_COLUMNS = (
    "ticker",
    "expiration",
    "trade_date",
    "event_id",
    "decision_dt",
    "strike",
    "right",
    "timestamp",
    "contract_ordinal",
    "bid",
    "ask",
    "bid_size",
    "ask_size",
    "bid_exchange",
    "ask_exchange",
    "bid_condition",
    "ask_condition",
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


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


def committed_code_state() -> tuple[str, dict[str, str]]:
    hashes: dict[str, str] = {}
    for relative in CODE_CLOSURE:
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
            raise AssertionError(f"H-IBQDYN1 preflight requires clean code: {relative}")
        hashes[relative] = sha256_file(PROJECT_ROOT / relative)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return commit, hashes


def load_frozen_contracts(proof_dir: str | Path = PROOF_DIR) -> pd.DataFrame:
    root = Path(proof_dir)
    manifest_path = root / "manifest.json"
    proof_path = root / "subscription_listing_proof.parquet"
    sample_path = root / "preflight_sample.csv"
    if sha256_file(manifest_path) != EXPECTED_PROOF_MANIFEST_SHA256:
        raise AssertionError("H-IBQDYN1 listing manifest hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("status") != "PASS_H_IBQDYN1_LISTING_FEASIBILITY"
        or manifest.get("outcome_free") is not True
        or manifest.get("holdout_2026_used") is not False
        or manifest.get("production_modified") is not False
        or manifest.get("events") != EXPECTED_EVENTS
        or manifest.get("eligible_events") != EXPECTED_ELIGIBLE_EVENTS
        or manifest.get("eligible_event_id_sha256") != EXPECTED_ELIGIBLE_ID_SHA256
        or manifest.get("proof_sha256") != EXPECTED_PROOF_SHA256
        or manifest.get("preflight_sample_sha256") != EXPECTED_SAMPLE_SHA256
    ):
        raise AssertionError("invalid H-IBQDYN1 listing manifest contract")
    if (
        sha256_file(proof_path) != EXPECTED_PROOF_SHA256
        or sha256_file(sample_path) != EXPECTED_SAMPLE_SHA256
    ):
        raise AssertionError("H-IBQDYN1 listing artifact tampering")
    columns = (
        "event_id",
        "ticker",
        "trade_date",
        "decision_dt",
        "minute",
        "nearest_level_name",
        "bucket",
        "call_strike",
        "put_strike",
        "preflight_sample",
        "exact_call_listed_tminus5m",
        "exact_put_listed_tminus5m",
        "causal_subscription_eligible",
    )
    proof = pd.read_parquet(proof_path, columns=list(columns))
    sample = proof[proof["preflight_sample"].astype(bool)].copy()
    if (
        len(proof) != EXPECTED_EVENTS
        or len(sample) != EXPECTED_SAMPLE_EVENTS
        or not sample["exact_call_listed_tminus5m"].astype(bool).all()
        or not sample["exact_put_listed_tminus5m"].astype(bool).all()
        or not sample["causal_subscription_eligible"].astype(bool).all()
        or sample["event_id"].duplicated().any()
    ):
        raise AssertionError("H-IBQDYN1 frozen sample changed")
    sample["decision_dt"] = pd.to_datetime(sample["decision_dt"], errors="coerce")
    if sample["decision_dt"].isna().any() or sample["trade_date"].astype(str).str.startswith(
        "2026"
    ).any():
        raise AssertionError("invalid H-IBQDYN1 sample clock")
    rows: list[dict[str, Any]] = []
    for event in sample.sort_values(["ticker", "trade_date"]).to_dict("records"):
        for right in ("CALL", "PUT"):
            strike = event["call_strike" if right == "CALL" else "put_strike"]
            contract_id = hashlib.sha256(
                f"{event['event_id']}|{right}|{float(strike):.6f}".encode("utf-8")
            ).hexdigest()[:24]
            rows.append(
                {
                    "contract_id": contract_id,
                    "event_id": str(event["event_id"]),
                    "ticker": str(event["ticker"]),
                    "trade_date": str(event["trade_date"]),
                    "decision_dt": pd.Timestamp(event["decision_dt"]),
                    "minute": int(event["minute"]),
                    "nearest_level_name": str(event["nearest_level_name"]),
                    "bucket": str(event["bucket"]),
                    "right": right,
                    "strike": float(strike),
                }
            )
    contracts = pd.DataFrame(rows)
    if len(contracts) != EXPECTED_CONTRACTS or contracts["contract_id"].duplicated().any():
        raise AssertionError("H-IBQDYN1 frozen contract expansion changed")
    return contracts


def request_params(contract: dict[str, Any]) -> dict[str, str]:
    decision = pd.Timestamp(contract["decision_dt"])
    start = decision - pd.Timedelta(seconds=32)
    end = decision - pd.Timedelta(seconds=2, milliseconds=1)
    return {
        "symbol": str(contract["ticker"]),
        "expiration": str(contract["trade_date"]),
        "date": str(contract["trade_date"]),
        "strike": f"{float(contract['strike']):.6f}",
        "right": str(contract["right"]).lower(),
        "interval": "tick",
        "format": "json",
        "start_time": start.strftime("%H:%M:%S.%f")[:-3],
        "end_time": end.strftime("%H:%M:%S.%f")[:-3],
    }


def normalize_tick_response(raw: dict[str, Any], contract: dict[str, Any]) -> pd.DataFrame:
    response = raw.get("response")
    if not isinstance(response, list) or len(response) != 1:
        raise AssertionError("H-IBQDYN1 response must contain one exact contract block")
    block = response[0]
    identity = block.get("contract", {})
    symbol = str(identity.get("symbol", "")).upper()
    expiration = "".join(
        char for char in str(identity.get("expiration", "")) if char.isdigit()
    )[:8]
    right = str(identity.get("right", "")).upper()
    strike = float(identity.get("strike", np.nan))
    if (
        symbol != str(contract["ticker"]).upper()
        or expiration != str(contract["trade_date"])
        or right != str(contract["right"]).upper()
        or not np.isfinite(strike)
        or strike != float(contract["strike"])
    ):
        raise AssertionError("H-IBQDYN1 response contract substitution")
    data = block.get("data", [])
    if not isinstance(data, list):
        raise AssertionError("H-IBQDYN1 contract data is not a list")
    decision = pd.Timestamp(contract["decision_dt"])
    start = decision - pd.Timedelta(seconds=32)
    end = decision - pd.Timedelta(seconds=2, milliseconds=1)
    rows = [
        {
            "ticker": symbol,
            "expiration": expiration,
            "trade_date": str(contract["trade_date"]),
            "event_id": str(contract["event_id"]),
            "decision_dt": decision,
            "strike": strike,
            "right": right,
            "timestamp": value.get("timestamp"),
            "contract_ordinal": ordinal,
            "bid": value.get("bid"),
            "ask": value.get("ask"),
            "bid_size": value.get("bid_size"),
            "ask_size": value.get("ask_size"),
            "bid_exchange": value.get("bid_exchange"),
            "ask_exchange": value.get("ask_exchange"),
            "bid_condition": value.get("bid_condition"),
            "ask_condition": value.get("ask_condition"),
        }
        for ordinal, value in enumerate(data)
    ]
    frame = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    if frame.empty:
        return frame
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    for column in (
        "bid",
        "ask",
        "bid_size",
        "ask_size",
        "bid_exchange",
        "ask_exchange",
        "bid_condition",
        "ask_condition",
    ):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if (
        frame["timestamp"].isna().any()
        or not frame["timestamp"].ge(start).all()
        or not frame["timestamp"].le(end).all()
        or not frame["contract_ordinal"].eq(np.arange(len(frame))).all()
    ):
        raise AssertionError("H-IBQDYN1 tick response violates guarded clock/order")
    return frame.reset_index(drop=True)


def field_profile(frame: pd.DataFrame) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for column in (
        "bid",
        "ask",
        "bid_size",
        "ask_size",
        "bid_exchange",
        "ask_exchange",
        "bid_condition",
        "ask_condition",
    ):
        values = pd.to_numeric(frame[column], errors="coerce") if len(frame) else values_empty()
        finite = values[np.isfinite(values)]
        output[column] = {
            "rows": int(len(values)),
            "finite": int(len(finite)),
            "zero": int(finite.eq(0).sum()),
            "distinct_finite": int(finite.nunique()),
        }
    return output


def values_empty() -> pd.Series:
    return pd.Series(dtype=float)


def validate_contract_directory(
    directory: Path,
    contract: dict[str, Any],
    *,
    base_url: str,
    provenance: dict[str, Any],
    code_hashes: dict[str, str],
    runtime: dict[str, Any],
) -> dict[str, Any]:
    manifest_path = directory / "manifest.json"
    raw_path = directory / "response.json"
    parquet_path = directory / "ticks.parquet"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("status") != "PASS_H_IBQDYN1_PREFLIGHT_CONTRACT"
        or manifest.get("outcome_free") is not True
        or manifest.get("holdout_2026_used") is not False
        or manifest.get("production_modified") is not False
        or manifest.get("contract_id") != str(contract["contract_id"])
        or manifest.get("event_id") != str(contract["event_id"])
        or manifest.get("base_url") != base_url.rstrip("/")
        or manifest.get("request_params") != request_params(contract)
        or manifest.get("source_provenance") != provenance
        or manifest.get("code_hashes") != code_hashes
        or manifest.get("runtime_lock_sha256") != runtime["lock_sha256"]
        or manifest.get("runtime_environment_sha256")
        != runtime["environment_sha256"]
        or manifest.get("raw_sha256") != sha256_file(raw_path)
        or manifest.get("parquet_sha256") != sha256_file(parquet_path)
    ):
        raise AssertionError("invalid immutable H-IBQDYN1 contract capture")
    rebuilt = normalize_tick_response(json.loads(raw_path.read_bytes()), contract)
    stored = pd.read_parquet(parquet_path)
    try:
        pd.testing.assert_frame_equal(stored, rebuilt, check_dtype=True)
    except AssertionError as exc:
        raise AssertionError("H-IBQDYN1 raw/parquet reconstruction mismatch") from exc
    if len(stored) != int(manifest.get("rows", -1)):
        raise AssertionError("H-IBQDYN1 stored row count mismatch")
    return manifest


def capture_contract(
    contract: dict[str, Any],
    *,
    staging_root: Path,
    base_url: str,
    provenance: dict[str, Any],
    code_hashes: dict[str, str],
    runtime: dict[str, Any],
    timeout: float,
    requester: Callable[..., Any] = requests.get,
) -> dict[str, Any]:
    directory = (
        staging_root
        / str(contract["ticker"])
        / str(contract["trade_date"])
        / str(contract["event_id"])
        / str(contract["right"]).lower()
    )
    params = request_params(contract)
    response = requester(
        base_url.rstrip("/") + ENDPOINT,
        params=params,
        headers={"Accept-Encoding": "identity"},
        timeout=timeout,
    )
    response.raise_for_status()
    raw = bytes(response.content)
    if not raw:
        raise AssertionError("empty H-IBQDYN1 tick response")
    frame = normalize_tick_response(json.loads(raw), contract)
    directory.mkdir(parents=True, exist_ok=False)
    raw_path = directory / "response.json"
    parquet_path = directory / "ticks.parquet"
    raw_path.write_bytes(raw)
    frame.to_parquet(parquet_path, index=False)
    schema = [
        (field.name, str(field.type))
        for field in pq.ParquetFile(parquet_path).schema_arrow
    ]
    manifest = {
        "schema": "h_ibqdyn1_tick_preflight_contract_v1",
        "status": "PASS_H_IBQDYN1_PREFLIGHT_CONTRACT",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "contract_id": str(contract["contract_id"]),
        "event_id": str(contract["event_id"]),
        "ticker": str(contract["ticker"]),
        "trade_date": str(contract["trade_date"]),
        "decision_dt": pd.Timestamp(contract["decision_dt"]).isoformat(),
        "nearest_level_name": str(contract["nearest_level_name"]),
        "bucket": str(contract["bucket"]),
        "right": str(contract["right"]),
        "strike": float(contract["strike"]),
        "base_url": base_url.rstrip("/"),
        "request_params": params,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_provenance": provenance,
        "code_hashes": code_hashes,
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "http_status": int(getattr(response, "status_code", 200)),
        "http_headers": dict(
            sorted(
                (str(key), str(value))
                for key, value in getattr(response, "headers", {}).items()
            )
        ),
        "server_date": str(getattr(response, "headers", {}).get("Date", "")),
        "raw_sha256": sha256_file(raw_path),
        "parquet_sha256": sha256_file(parquet_path),
        "raw_bytes": int(len(raw)),
        "parquet_bytes": int(parquet_path.stat().st_size),
        "rows": int(len(frame)),
        "first_timestamp": frame["timestamp"].min().isoformat() if len(frame) else None,
        "last_timestamp": frame["timestamp"].max().isoformat() if len(frame) else None,
        "response_schema": schema,
        "response_schema_sha256": sha256_bytes(canonical_bytes({"schema": schema})),
        "field_profile": field_profile(frame),
    }
    manifest_path = directory / "manifest.json"
    manifest_path.write_bytes(canonical_bytes(manifest))
    manifest = validate_contract_directory(
        directory,
        contract,
        base_url=base_url,
        provenance=provenance,
        code_hashes=code_hashes,
        runtime=runtime,
    )
    return {
        "contract_id": str(contract["contract_id"]),
        "event_id": str(contract["event_id"]),
        "ticker": str(contract["ticker"]),
        "trade_date": str(contract["trade_date"]),
        "decision_dt": pd.Timestamp(contract["decision_dt"]).isoformat(),
        "right": str(contract["right"]),
        "strike": float(contract["strike"]),
        "contract_dir": str(directory),
        "raw_path": str(raw_path),
        "raw_sha256": manifest["raw_sha256"],
        "parquet_path": str(parquet_path),
        "parquet_sha256": manifest["parquet_sha256"],
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "rows": int(manifest["rows"]),
        "raw_bytes": int(manifest["raw_bytes"]),
        "parquet_bytes": int(manifest["parquet_bytes"]),
    }


def projected_cost(index: pd.DataFrame) -> dict[str, Any]:
    if len(index) != EXPECTED_CONTRACTS:
        raise AssertionError("H-IBQDYN1 cost projection requires all 24 contracts")
    factor = EXPECTED_ELIGIBLE_EVENTS * 2 / EXPECTED_CONTRACTS
    rows = int(np.ceil(float(index["rows"].sum()) * factor))
    raw_bytes = int(np.ceil(float(index["raw_bytes"].sum()) * factor))
    parquet_bytes = int(np.ceil(float(index["parquet_bytes"].sum()) * factor))
    return {
        "preflight_events": EXPECTED_SAMPLE_EVENTS,
        "preflight_contracts": EXPECTED_CONTRACTS,
        "full_eligible_events": EXPECTED_ELIGIBLE_EVENTS,
        "full_contracts": EXPECTED_ELIGIBLE_EVENTS * 2,
        "projection_factor": factor,
        "preflight_rows": int(index["rows"].sum()),
        "preflight_raw_bytes": int(index["raw_bytes"].sum()),
        "preflight_parquet_bytes": int(index["parquet_bytes"].sum()),
        "projected_rows": rows,
        "projected_raw_bytes": raw_bytes,
        "projected_raw_gib": raw_bytes / 2**30,
        "projected_parquet_bytes": parquet_bytes,
        "projected_parquet_gib": parquet_bytes / 2**30,
        "row_limit": MAX_PROJECTED_ROWS,
        "raw_byte_limit": MAX_PROJECTED_RAW_BYTES,
        "cost_gate_pass": rows <= MAX_PROJECTED_ROWS
        and raw_bytes <= MAX_PROJECTED_RAW_BYTES,
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
            normalized + REMOTE_STATUS_ENDPOINT,
            params={},
            headers={"Accept-Encoding": "identity"},
            timeout=timeout,
        )
        response.raise_for_status()
        raw = bytes(response.content)
        if not raw or terminal_status_value(raw) != "CONNECTED":
            raise AssertionError("remote H-IBQDYN1 Terminal is not CONNECTED")
        return {
            "kind": "USER_SUPPLIED_REMOTE_THETA_TERMINAL",
            "base_url": normalized,
            "status_endpoint": REMOTE_STATUS_ENDPOINT,
            "status_value": "CONNECTED",
            "status_raw_sha256": sha256_bytes(raw),
            "http_status": int(getattr(response, "status_code", 200)),
            "http_headers": dict(
                sorted(
                    (str(key), str(value))
                    for key, value in getattr(response, "headers", {}).items()
                )
            ),
            "server_date": str(getattr(response, "headers", {}).get("Date", "")),
            "historical_provenance": "CONDITIONAL_REMOTE_TERMINAL_RECONSTRUCTION",
            "live_parity": "BLOCKED",
        }, raw
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise AssertionError("H-IBQDYN1 base URL is not frozen local/remote Terminal")
    if terminal_jar is None:
        raise AssertionError("local H-IBQDYN1 capture requires terminal JAR")
    jar = Path(terminal_jar).resolve()
    evidence = local_terminal_process_evidence(normalized, jar)
    if evidence.get("terminal_jar_sha256") != sha256_file(jar):
        raise AssertionError("local H-IBQDYN1 active JAR mismatch")
    return {
        **evidence,
        "historical_provenance": "CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION",
        "live_parity": "BLOCKED_PENDING_PROSPECTIVE_PARITY",
    }, b""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:25503/v3")
    parser.add_argument("--terminal-jar")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=180.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 1 <= int(args.workers) <= 4:
        raise ValueError("H-IBQDYN1 preflight workers must be within 1..4")
    output = Path(args.output_root).resolve()
    staging = output.with_name(output.name + ".staging")
    if output.exists() or staging.exists():
        raise FileExistsError("immutable H-IBQDYN1 tick preflight output exists")
    commit, code_hashes = committed_code_state()
    runtime = assert_runtime_lock(PROJECT_ROOT / RUNTIME_LOCK)
    contracts = load_frozen_contracts()
    provenance, remote_status_raw = source_provenance(
        args.base_url,
        terminal_jar=args.terminal_jar,
        timeout=float(args.timeout),
    )
    staging.mkdir(parents=True, exist_ok=False)
    if remote_status_raw:
        (staging / "remote_terminal_status.json").write_bytes(remote_status_raw)
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=int(args.workers)) as pool:
        futures = {
            pool.submit(
                capture_contract,
                contract,
                staging_root=staging,
                base_url=args.base_url,
                provenance=provenance,
                code_hashes=code_hashes,
                runtime=runtime,
                timeout=float(args.timeout),
            ): contract
            for contract in contracts.to_dict("records")
        }
        for count, future in enumerate(as_completed(futures), start=1):
            contract = futures[future]
            try:
                rows.append(future.result())
            except Exception as exc:
                errors.append(
                    {
                        "contract_id": str(contract["contract_id"]),
                        "ticker": str(contract["ticker"]),
                        "trade_date": str(contract["trade_date"]),
                        "right": str(contract["right"]),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
            print(
                f"[H-IBQDYN1_PREFLIGHT] contracts={count}/{len(contracts)} "
                f"errors={len(errors)}",
                flush=True,
            )
    if errors or len(rows) != EXPECTED_CONTRACTS:
        (staging / "errors.json").write_bytes(canonical_bytes({"errors": errors}))
        raise AssertionError(f"H-IBQDYN1 tick preflight failed: {errors[:10]}")
    index = pd.DataFrame(rows).sort_values(
        ["ticker", "trade_date", "event_id", "right"], kind="stable"
    ).reset_index(drop=True)
    for column in (
        "contract_dir",
        "raw_path",
        "parquet_path",
        "manifest_path",
    ):
        index[column] = index[column].astype(str).str.replace(
            str(staging), str(output), n=1, regex=False
        )
    cost = projected_cost(index)
    both_nonempty = bool(index["rows"].gt(0).all())
    status = (
        "PASS_H_IBQDYN1_TICK_PREFLIGHT"
        if both_nonempty and bool(cost["cost_gate_pass"])
        else "REJECTED_H_IBQDYN1_TICK_PREFLIGHT"
    )
    index_path = staging / "contract_index.csv"
    cost_path = staging / "cost_projection.json"
    index.to_csv(index_path, index=False)
    cost_path.write_bytes(canonical_bytes(cost))
    seal = {
        "schema": "h_ibqdyn1_tick_preflight_seal_v1",
        "status": status,
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "git_commit": commit,
        "code_hashes": code_hashes,
        "proof_manifest_sha256": EXPECTED_PROOF_MANIFEST_SHA256,
        "proof_sha256": EXPECTED_PROOF_SHA256,
        "sample_sha256": EXPECTED_SAMPLE_SHA256,
        "eligible_event_id_sha256": EXPECTED_ELIGIBLE_ID_SHA256,
        "events": int(index["event_id"].nunique()),
        "contracts": int(len(index)),
        "rows": int(index["rows"].sum()),
        "call_rows": int(index.loc[index["right"].eq("CALL"), "rows"].sum()),
        "put_rows": int(index.loc[index["right"].eq("PUT"), "rows"].sum()),
        "zero_row_contracts": int(index["rows"].eq(0).sum()),
        "both_rights_nonempty": both_nonempty,
        "contract_index_sha256": sha256_file(index_path),
        "cost_projection_sha256": sha256_file(cost_path),
        "cost_projection": cost,
        "source_provenance": provenance,
        "remote_status_raw_sha256": sha256_bytes(remote_status_raw)
        if remote_status_raw
        else None,
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment": runtime["environment"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "errors": [],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (staging / "manifest.json").write_bytes(canonical_bytes(seal))
    staging.rename(output)
    print(json.dumps(seal, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
