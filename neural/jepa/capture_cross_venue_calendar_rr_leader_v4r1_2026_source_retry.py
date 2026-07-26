#!/usr/bin/env python3
"""Capture the ten user-authorized, outcome-free V4R1 Greek/IV retries."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import requests

SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from neural.jepa import (  # noqa: E402
    cross_venue_calendar_rr_leader_v4r1_2026_common as common,
)
from neural.jepa.build_calendar_risk_reversal_pressure_v1 import (  # noqa: E402
    tracked_clean,
)


PROJECT_ROOT = SCRIPT_REPO_ROOT
DEFAULT_OUTPUT = common.RETRY_ROOT
BUILDER = (
    PROJECT_ROOT
    / "neural/jepa/build_cross_venue_calendar_rr_leader_v4r1_2026_data_gate.py"
)
AUDITOR = (
    PROJECT_ROOT
    / "neural/jepa/audit_cross_venue_calendar_rr_leader_v4r1_2026_data_gate.py"
)
CODE_CLOSURE = (
    Path(__file__).resolve(),
    Path(common.__file__).resolve(),
    BUILDER,
    AUDITOR,
    common.PREDECLARATION,
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


def verify_preexecution() -> dict[str, str]:
    if common.sha256_file(common.PREDECLARATION) != common.PREDECLARATION_SHA256:
        raise AssertionError("V4R1 predeclaration changed")
    hashes: dict[str, str] = {}
    for path in CODE_CLOSURE:
        tracked_clean(path, f"V4R1 code closure {path.name}")
        hashes[path.relative_to(PROJECT_ROOT).as_posix()] = common.sha256_file(path)
    return hashes


def logical_directory(staging: Path, spec: dict[str, Any], kind: str) -> Path:
    return (
        staging
        / str(spec["ticker"])
        / str(spec["trade_date"])
        / str(spec["role"])
        / kind
    )


def request_with_fallback(
    spec: dict[str, Any],
    kind: str,
    *,
    base_url: str,
    timeout: float,
    requester: Callable[..., Any] = requests.get,
) -> tuple[bytes, str | None, list[dict[str, Any]], int | None]:
    audit: list[dict[str, Any]] = []
    last_raw = b""
    last_status: int | None = None
    for interval in common.INTERVALS:
        params = common.request_params(spec, interval)
        for attempt in range(1, 4):
            started = time.monotonic()
            try:
                response = requester(
                    base_url.rstrip("/") + common.ENDPOINTS[kind],
                    params=params,
                    headers={"Accept-Encoding": "identity"},
                    timeout=timeout,
                )
                elapsed = time.monotonic() - started
                status = int(response.status_code)
                raw = bytes(response.content)
                last_raw = raw
                last_status = status
                audit.append(
                    {
                        "interval": interval,
                        "attempt": attempt,
                        "status_code": status,
                        "elapsed_seconds": elapsed,
                        "exception": "",
                    }
                )
                if status == 404:
                    return raw, None, audit, status
                if status >= 400:
                    break
                payload = json.loads(raw)
                if not common.parse_response(payload):
                    return raw, None, audit, status
                return raw, interval, audit, status
            except (requests.RequestException, json.JSONDecodeError) as error:
                elapsed = time.monotonic() - started
                audit.append(
                    {
                        "interval": interval,
                        "attempt": attempt,
                        "status_code": None,
                        "elapsed_seconds": elapsed,
                        "exception": f"{type(error).__name__}: {error}",
                    }
                )
                if attempt < 3:
                    time.sleep(float(2**attempt))
        # The next interval is an operational fallback, not a new scientific spec.
    return last_raw, None, audit, last_status


def capture_logical_request(
    staging: Path,
    spec: dict[str, Any],
    kind: str,
    *,
    base_url: str,
    timeout: float,
    code_hashes: dict[str, str],
    requester: Callable[..., Any] = requests.get,
) -> dict[str, Any]:
    directory = logical_directory(staging, spec, kind)
    directory.mkdir(parents=True, exist_ok=False)
    raw, interval, request_audit, status_code = request_with_fallback(
        spec,
        kind,
        base_url=base_url,
        timeout=timeout,
        requester=requester,
    )
    raw_path = directory / "response.json"
    raw_path.write_bytes(raw)
    request_audit_path = directory / "request_audit.csv"
    pd.DataFrame(request_audit).to_csv(
        request_audit_path, index=False, lineterminator="\n"
    )
    normalized_path = directory / "normalized.parquet"
    error = ""
    rows = 0
    if interval is not None:
        try:
            normalized = common.normalize_response(
                json.loads(raw), spec, kind, interval
            )
            normalized.to_parquet(normalized_path, index=False)
            rows = int(len(normalized))
        except Exception as caught:  # noqa: BLE001 - persisted source failure
            error = f"{type(caught).__name__}: {caught}"
    else:
        error = f"NO_USABLE_RESPONSE_HTTP_{status_code}"
    usable_response = bool(normalized_path.is_file() and not error)
    manifest = {
        "schema": "cross_venue_calendar_rr_leader_v4r1_retry_request_v1",
        "status": "PASS_NORMALIZED_RESPONSE" if usable_response else "FAILED_RESPONSE",
        "outcome_free": True,
        "outcome_2026_accessed": False,
        "capture_id": str(spec["capture_id"]),
        "ticker": str(spec["ticker"]),
        "trade_date": str(spec["trade_date"]),
        "role": str(spec["role"]),
        "expiration": str(spec["expiration"]),
        "kind": kind,
        "endpoint": common.ENDPOINTS[kind],
        "interval_used": interval,
        "request_params_by_interval": [
            common.request_params(spec, value) for value in common.INTERVALS
        ],
        "http_status": status_code,
        "rows": rows,
        "error": error,
        "raw_sha256": common.sha256_file(raw_path),
        "request_audit_sha256": common.sha256_file(request_audit_path),
        "normalized_sha256": common.sha256_file(normalized_path)
        if normalized_path.is_file()
        else None,
        "code_hashes": code_hashes,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (directory / "manifest.json").write_bytes(common.canonical_bytes(manifest))
    return {
        **manifest,
        "directory": str(directory),
        "normalized_path": str(normalized_path) if normalized_path.is_file() else "",
        "manifest_sha256": common.sha256_file(directory / "manifest.json"),
    }


def build_pair_gate(
    request_rows: pd.DataFrame, specs: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    indexed = request_rows.set_index(["capture_id", "kind"])
    pairs: list[dict[str, Any]] = []
    exclusions: list[dict[str, str]] = []
    for spec in specs.to_dict(orient="records"):
        capture_id = str(spec["capture_id"])
        greeks = indexed.loc[(capture_id, "greeks")]
        iv = indexed.loc[(capture_id, "iv")]
        usable = bool(
            greeks["status"] == "PASS_NORMALIZED_RESPONSE"
            and iv["status"] == "PASS_NORMALIZED_RESPONSE"
        )
        if usable:
            try:
                gate = common.target_pair_gate(
                    Path(str(greeks["normalized_path"])),
                    Path(str(iv["normalized_path"])),
                    spec,
                )
            except Exception as error:  # noqa: BLE001 - fail closed
                gate = {
                    "usable": False,
                    "greek_rows": 0,
                    "iv_rows": 0,
                    "shared_rows": 0,
                    "greek_only_rows": 0,
                    "iv_only_rows": 0,
                    "reason": f"{type(error).__name__}: {error}",
                }
        else:
            gate = {
                "usable": False,
                "greek_rows": int(greeks["rows"]),
                "iv_rows": int(iv["rows"]),
                "shared_rows": 0,
                "greek_only_rows": 0,
                "iv_only_rows": 0,
                "reason": "ONE_OR_BOTH_RETRY_RESPONSES_FAILED",
            }
        row = {
            **{key: str(spec[key]) for key in ("capture_id", "ticker", "trade_date", "role", "expiration")},
            **gate,
            "greeks_path": str(greeks["normalized_path"]),
            "iv_path": str(iv["normalized_path"]),
        }
        pairs.append(row)
        if not bool(gate["usable"]):
            exclusions.append(
                {
                    "sensor_ticker": str(spec["ticker"]),
                    "trade_date": str(spec["trade_date"]),
                    "capture_id": capture_id,
                    "reason": str(gate["reason"]),
                }
            )
    pair_frame = pd.DataFrame(pairs).sort_values("capture_id", kind="stable")
    exclusion_frame = (
        pd.DataFrame(exclusions)
        .sort_values(["sensor_ticker", "trade_date"], kind="stable")
        .reset_index(drop=True)
        if exclusions
        else pd.DataFrame(
            columns=["sensor_ticker", "trade_date", "capture_id", "reason"]
        )
    )
    if exclusion_frame.duplicated(["sensor_ticker", "trade_date"]).any():
        raise AssertionError("V4R1 retry produced duplicate exclusion key")
    return pair_frame.reset_index(drop=True), exclusion_frame


def run(
    output_dir: Path,
    *,
    base_url: str,
    timeout: float,
    requester: Callable[..., Any] = requests.get,
) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"immutable V4R1 retry root exists: {output_dir}")
    if base_url.rstrip("/") != common.REMOTE_BASE_URL:
        raise AssertionError("V4R1 retry base URL changed")
    code_hashes = verify_preexecution()
    universe = common.discover_universe()
    specs = common.retry_specs(universe)
    staging = output_dir.with_name(f".{output_dir.name}.staging-{os.getpid()}")
    if staging.exists():
        raise FileExistsError(staging)
    staging.mkdir(parents=True)
    try:
        state = staging / "_state"
        state.mkdir()
        specs.to_csv(state / "retry_specs.csv", index=False, lineterminator="\n")
        contract = {
            "schema": "cross_venue_calendar_rr_leader_v4r1_retry_contract_v1",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "execution_commit": current_git_commit(),
            "base_url": common.REMOTE_BASE_URL,
            "logical_capture_ids": list(common.RETRY_IDS),
            "logical_pairs": len(common.RETRY_IDS),
            "logical_requests": len(common.RETRY_IDS) * 2,
            "interval_fallback": list(common.INTERVALS),
            "date_sha256": common.DATE_SHA256,
            "capture_id_sha256": common.CAPTURE_ID_SHA256,
            "predeclaration_sha256": common.PREDECLARATION_SHA256,
            "code_hashes": code_hashes,
            "outcome_free": True,
            "outcome_2026_accessed": False,
            "production_modified": False,
        }
        (state / "capture_contract.json").write_bytes(common.canonical_bytes(contract))
        request_records: list[dict[str, Any]] = []
        for spec in specs.to_dict(orient="records"):
            for kind in ("greeks", "iv"):
                request_records.append(
                    capture_logical_request(
                        staging,
                        spec,
                        kind,
                        base_url=base_url,
                        timeout=timeout,
                        code_hashes=code_hashes,
                        requester=requester,
                    )
                )
        requests_frame = pd.DataFrame(request_records).sort_values(
            ["capture_id", "kind"], kind="stable"
        ).reset_index(drop=True)
        pair_gate, exclusions = build_pair_gate(requests_frame, specs)
        for column in ("directory", "normalized_path"):
            requests_frame[column] = requests_frame[column].map(
                lambda value: str(
                    output_dir / Path(str(value)).relative_to(staging)
                )
                if str(value)
                else ""
            )
        for column in ("greeks_path", "iv_path"):
            pair_gate[column] = pair_gate[column].map(
                lambda value: str(
                    output_dir / Path(str(value)).relative_to(staging)
                )
                if str(value)
                else ""
            )
        requests_frame.to_csv(
            staging / "request_index.csv", index=False, lineterminator="\n"
        )
        pair_gate.to_csv(staging / "pair_gate.csv", index=False, lineterminator="\n")
        exclusions.to_csv(
            staging / "exclusions.csv", index=False, lineterminator="\n"
        )
        seal = {
            "schema": "cross_venue_calendar_rr_leader_v4r1_retry_seal_v1",
            "status": "PASS_SOURCE_RETRY_GATE_WITH_FIXED_EXCLUSIONS",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "execution_commit": current_git_commit(),
            "logical_requests": int(len(requests_frame)),
            "normalized_responses": int(
                requests_frame["status"].eq("PASS_NORMALIZED_RESPONSE").sum()
            ),
            "usable_pairs": int(pair_gate["usable"].sum()),
            "excluded_sensor_dates": int(len(exclusions)),
            "retry_specs_sha256": common.sha256_file(state / "retry_specs.csv"),
            "contract_sha256": common.sha256_file(state / "capture_contract.json"),
            "request_index_sha256": common.sha256_file(staging / "request_index.csv"),
            "pair_gate_sha256": common.sha256_file(staging / "pair_gate.csv"),
            "exclusions_sha256": common.sha256_file(staging / "exclusions.csv"),
            "predeclaration_sha256": common.PREDECLARATION_SHA256,
            "date_sha256": common.DATE_SHA256,
            "capture_id_sha256": common.CAPTURE_ID_SHA256,
            "outcome_free": True,
            "feature_2026_opened": False,
            "outcome_2026_accessed": False,
            "production_modified": False,
        }
        (staging / "seal.json").write_bytes(common.canonical_bytes(seal))
        os.replace(staging, output_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return seal


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--base-url", default=common.REMOTE_BASE_URL)
    parser.add_argument("--timeout", type=float, default=300.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.timeout <= 0:
        raise ValueError("timeout must be positive")
    summary = run(
        args.output_dir.resolve(),
        base_url=args.base_url,
        timeout=args.timeout,
    )
    print(json.dumps(summary, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
