"""Capture the immutable full 2024-2025 calendar-RR native-clock sidecar."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.capture_cross_venue_calendar_rr_native_clock_preflight import (  # noqa: E402
    DEFAULT_OPTIONS_ROOT,
    REMOTE_BASE_URL,
    RUNTIME_LOCK,
    TICKERS,
    canonical_bytes,
    capture_one,
    committed_code_state,
    sha256_bytes,
    sha256_file,
    source_provenance,
    validate_existing_capture,
)
from neural.jepa.wall_surface_flow_environment import assert_runtime_lock  # noqa: E402

YEARS = ("2024", "2025")
EXPECTED_SESSIONS_PER_TICKER = 502
EXPECTED_SESSIONS = 1_506
EXPECTED_CAPTURES = 3_012
EXPECTED_CAPTURE_ID_SHA256 = (
    "447e771b391f12dcfd7cba3692e65a7586dd4db2f3205311034616ddc7de5ce4"
)
EXPECTED_LOGICAL_INVENTORY_SHA256 = (
    "e685affdc09715085e80f9828a36e71ebbd52d5e5da4a25e43f7e8ff2f4b07b0"
)
DEFAULT_OUTPUT = Path("D:/ThetaData/cross_venue_calendar_rr_native_clock_2024_2025_v1")
PREFLIGHT_SEAL = (
    PROJECT_ROOT / "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_calendar_rr_native_clock_preflight_2024_2025_v1/seal.json"
)
PREFLIGHT_SEAL_SHA256 = (
    "d33e01a6226eb89083be7aa77ed5e8554a1a7babe6342a9a7d9d243881feee6d"
)
COUNT_CLARIFICATION = (
    PROJECT_ROOT
    / "research_papers/JEPA/CROSS_VENUE_CALENDAR_RR_FULL_UNIVERSE_COUNT_CLARIFICATION.md"
)
FULL_CODE_CLOSURE = (
    "neural/jepa/capture_cross_venue_calendar_rr_native_clock_full.py",
    "neural/jepa/capture_cross_venue_calendar_rr_native_clock_preflight.py",
    "neural/jepa/build_wall_native_quote_sidecar.py",
    "neural/jepa/wall_surface_flow_environment.py",
    "research_papers/JEPA/CROSS_VENUE_CALENDAR_RR_LEADER_V1_PREDECLARATION.md",
    "research_papers/JEPA/CROSS_VENUE_CALENDAR_RR_NATIVE_CLOCK_PREFLIGHT_RESULT.md",
    "research_papers/JEPA/CROSS_VENUE_CALENDAR_RR_FULL_UNIVERSE_COUNT_CLARIFICATION.md",
    "research_papers/JEPA/results/_diagnostics/cross_venue_calendar_rr_native_clock_preflight_2024_2025_v1/seal.json",
    "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt",
)


def ordered_hash(values: list[str]) -> str:
    return sha256_bytes(("\n".join(sorted(values)) + "\n").encode("utf-8"))


def _source_maps(
    options_root: Path, ticker: str, kind: str
) -> dict[str, dict[str, Path]]:
    output: dict[str, dict[str, Path]] = defaultdict(dict)
    pattern = re.compile(
        rf"^{re.escape(ticker)}_(?P<expiry>\d{{8}})_(?P<trade>\d{{8}})_{kind}\.parquet$"
    )
    for year in YEARS:
        for path in sorted(
            (options_root / ticker / kind / year).rglob(f"*_{kind}.parquet")
        ):
            match = pattern.match(path.name)
            if not match or not match.group("trade").startswith(year):
                continue
            trade_date = match.group("trade")
            expiry = match.group("expiry")
            if expiry in output[trade_date]:
                raise AssertionError(
                    f"duplicate source file: {ticker} {kind} {trade_date} {expiry}"
                )
            output[trade_date][expiry] = path.resolve()
    return output


def discover_full_specs(
    options_root: str | Path = DEFAULT_OPTIONS_ROOT,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    root = Path(options_root)
    rows: list[dict[str, str]] = []
    logical_inventory: list[str] = []
    capture_ids: list[str] = []
    counts: dict[str, int] = {}
    for ticker in TICKERS:
        greeks = _source_maps(root, ticker, "greeks")
        iv = _source_maps(root, ticker, "iv")
        ticker_sessions = 0
        for day in sorted(set(greeks).intersection(iv)):
            common_expiries = set(greeks[day]).intersection(iv[day])
            later = sorted(expiry for expiry in common_expiries if expiry > day)
            if day not in common_expiries or not later:
                continue
            ticker_sessions += 1
            for role, expiry in (("front", day), ("back", later[0])):
                capture_id = hashlib.sha256(
                    f"{ticker}|{day}|{role}|{expiry}".encode("utf-8")
                ).hexdigest()[:24]
                capture_ids.append(f"{ticker}|{day}|{role}|{expiry}")
                for kind, mapping in (("greeks", greeks), ("iv", iv)):
                    logical_inventory.append(
                        f"{ticker}|{day}|{role}|{expiry}|{kind}|"
                        f"{mapping[day][expiry].relative_to(root.resolve()).as_posix()}"
                    )
                rows.append(
                    {
                        "capture_id": capture_id,
                        "ticker": ticker,
                        "trade_date": day,
                        "role": role,
                        "expiration": expiry,
                        "greeks_path": str(greeks[day][expiry]),
                        "iv_path": str(iv[day][expiry]),
                    }
                )
        counts[ticker] = ticker_sessions
    specs = (
        pd.DataFrame(rows)
        .sort_values(["ticker", "trade_date", "role"], kind="stable")
        .reset_index(drop=True)
    )
    capture_hash = ordered_hash(capture_ids)
    inventory_hash = ordered_hash(logical_inventory)
    if (
        counts != {ticker: EXPECTED_SESSIONS_PER_TICKER for ticker in TICKERS}
        or len(specs) != EXPECTED_CAPTURES
        or specs["capture_id"].duplicated().any()
        or specs[["ticker", "trade_date"]].drop_duplicates().shape[0]
        != EXPECTED_SESSIONS
        or capture_hash != EXPECTED_CAPTURE_ID_SHA256
        or inventory_hash != EXPECTED_LOGICAL_INVENTORY_SHA256
        or specs["trade_date"].str.startswith("2026").any()
    ):
        raise AssertionError("full calendar-RR source universe changed")
    audit = {
        "sessions_per_ticker": counts,
        "sessions": EXPECTED_SESSIONS,
        "captures": EXPECTED_CAPTURES,
        "logical_source_rows": len(logical_inventory),
        "capture_id_sha256": capture_hash,
        "logical_inventory_sha256": inventory_hash,
    }
    return specs, audit


def validate_preflight_evidence() -> dict[str, Any]:
    if sha256_file(PREFLIGHT_SEAL) != PREFLIGHT_SEAL_SHA256:
        raise AssertionError("preflight seal hash changed")
    seal = json.loads(PREFLIGHT_SEAL.read_text(encoding="utf-8"))
    if (
        seal.get("status") != "PASS_CROSS_VENUE_CALENDAR_RR_NATIVE_CLOCK_PREFLIGHT"
        or seal.get("outcome_free") is not True
        or seal.get("holdout_2026_used") is not False
        or seal.get("production_modified") is not False
        or seal.get("missing_vintage_key_rows") != 0
    ):
        raise AssertionError("preflight evidence is not a valid PASS")
    return seal


def prepare_spec(spec: dict[str, Any]) -> dict[str, Any]:
    output = dict(spec)
    output["greeks_sha256"] = sha256_file(output["greeks_path"])
    output["iv_sha256"] = sha256_file(output["iv_path"])
    return output


def capture_directory(root: Path, spec: dict[str, Any]) -> Path:
    return root / str(spec["ticker"]) / str(spec["trade_date"]) / str(spec["role"])


def capture_or_resume(
    logical_spec: dict[str, Any],
    *,
    output: Path,
    base_url: str,
    provenance: dict[str, Any],
    runtime: dict[str, Any],
    code_hashes: dict[str, str],
    timeout: float,
) -> tuple[dict[str, Any], bool]:
    spec = prepare_spec(logical_spec)
    directory = capture_directory(output, spec)
    working = directory.with_name(directory.name + ".staging")
    if working.exists():
        raise AssertionError(f"interrupted atomic capture requires audit: {working}")
    if directory.exists():
        row = validate_existing_capture(
            spec,
            staging=output,
            capture_code_hashes=code_hashes,
            runtime=runtime,
        )
        return row, True
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            row = capture_one(
                spec,
                staging=output,
                base_url=base_url,
                provenance=provenance,
                runtime=runtime,
                code_hashes=code_hashes,
                timeout=timeout,
            )
            return row, False
        except requests.RequestException as exc:
            last_error = exc
            if directory.exists() or working.exists() or attempt == 2:
                break
            time.sleep(1.0 + attempt)
    raise RuntimeError(f"capture request failed after retries: {last_error}")


def contract_payload(
    *,
    commit: str,
    code_hashes: dict[str, str],
    runtime: dict[str, Any],
    provenance: dict[str, Any],
    universe_audit: dict[str, Any],
    universe_sha256: str,
) -> dict[str, Any]:
    return {
        "schema": "cross_venue_calendar_rr_native_clock_full_contract_v1",
        "status": "CAPTURE_IN_PROGRESS",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "git_commit": commit,
        "code_hashes": code_hashes,
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "source_provenance": provenance,
        "preflight_seal_sha256": PREFLIGHT_SEAL_SHA256,
        "count_clarification_sha256": sha256_file(COUNT_CLARIFICATION),
        "universe_audit": universe_audit,
        "universe_sha256": universe_sha256,
    }


def initialize_or_validate_root(
    output: Path,
    *,
    specs: pd.DataFrame,
    payload: dict[str, Any],
    status_raw: bytes,
) -> None:
    state = output / "_state"
    contract_path = state / "capture_contract.json"
    universe_path = state / "universe.csv"
    if not output.exists():
        state.mkdir(parents=True, exist_ok=False)
        specs.to_csv(universe_path, index=False, lineterminator="\n")
        payload = {**payload, "universe_file_sha256": sha256_file(universe_path)}
        contract_path.write_bytes(canonical_bytes(payload))
        if status_raw:
            (state / "remote_terminal_status.json").write_bytes(status_raw)
        return
    if not (contract_path.is_file() and universe_path.is_file()):
        raise AssertionError("existing full capture lacks frozen state contract")
    stored = json.loads(contract_path.read_text(encoding="utf-8"))
    observed_universe = specs.to_csv(index=False, lineterminator="\n").encode("utf-8")
    if (
        stored != {**payload, "universe_file_sha256": sha256_file(universe_path)}
        or universe_path.read_bytes() != observed_universe
    ):
        raise AssertionError("full capture resume contract changed")


def write_progress(output: Path, completed: int, resumed: int, errors: int) -> None:
    payload = {
        "schema": "cross_venue_calendar_rr_native_clock_full_progress_v1",
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


def seal_full_capture(
    output: Path,
    *,
    rows: list[dict[str, Any]],
    contract: dict[str, Any],
) -> dict[str, Any]:
    index = (
        pd.DataFrame(rows)
        .sort_values(["ticker", "trade_date", "role"], kind="stable")
        .reset_index(drop=True)
    )
    if len(index) != EXPECTED_CAPTURES or index["capture_id"].duplicated().any():
        raise AssertionError("cannot seal incomplete full capture")
    seal_dir = output / "_seal"
    seal_staging = output / "_seal.staging"
    if seal_dir.exists() or seal_staging.exists():
        raise FileExistsError("full capture seal already exists")
    seal_staging.mkdir()
    index_path = seal_staging / "capture_index.csv"
    index.to_csv(index_path, index=False)
    seal = {
        "schema": "cross_venue_calendar_rr_native_clock_full_seal_v1",
        "status": "PASS_CROSS_VENUE_CALENDAR_RR_NATIVE_CLOCK_FULL_CAPTURE",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "git_commit": contract["git_commit"],
        "code_hashes": contract["code_hashes"],
        "source_provenance": contract["source_provenance"],
        "preflight_seal_sha256": PREFLIGHT_SEAL_SHA256,
        "count_clarification_sha256": contract["count_clarification_sha256"],
        "universe_audit": contract["universe_audit"],
        "sessions": EXPECTED_SESSIONS,
        "captures": int(len(index)),
        "rows": int(index["rows"].sum()),
        "raw_bytes": int(index["raw_bytes"].sum()),
        "parquet_bytes": int(index["parquet_bytes"].sum()),
        "missing_vintage_key_rows": 0,
        "native_extra_target_key_rows": int(
            index["native_extra_target_key_rows"].sum()
        ),
        "revised_bid_ask_rows": int(index["revised_bid_ask_rows"].sum()),
        "crossed_native_rows": int(index["crossed_native_rows"].sum()),
        "capture_index_sha256": sha256_file(index_path),
        "runtime_lock_sha256": contract["runtime_lock_sha256"],
        "runtime_environment_sha256": contract["runtime_environment_sha256"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (seal_staging / "seal.json").write_bytes(canonical_bytes(seal))
    seal_staging.rename(seal_dir)
    return seal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--options-root", type=Path, default=DEFAULT_OPTIONS_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--base-url", default=REMOTE_BASE_URL)
    parser.add_argument("--terminal-jar")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=180.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 1 <= args.workers <= 4:
        raise ValueError("workers must be within 1..4")
    validate_preflight_evidence()
    commit, code_hashes = committed_code_state(FULL_CODE_CLOSURE)
    runtime = assert_runtime_lock(RUNTIME_LOCK)
    specs, universe_audit = discover_full_specs(args.options_root)
    universe_sha256 = sha256_bytes(
        specs.to_csv(index=False, lineterminator="\n").encode("utf-8")
    )
    provenance, status_raw = source_provenance(
        args.base_url,
        terminal_jar=args.terminal_jar,
        timeout=args.timeout,
    )
    contract = contract_payload(
        commit=commit,
        code_hashes=code_hashes,
        runtime=runtime,
        provenance=provenance,
        universe_audit=universe_audit,
        universe_sha256=universe_sha256,
    )
    output = args.output_root.resolve()
    initialize_or_validate_root(
        output,
        specs=specs,
        payload=contract,
        status_raw=status_raw,
    )
    if (output / "_seal").exists():
        raise FileExistsError("full capture is already sealed")
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
                        "ticker": str(spec["ticker"]),
                        "trade_date": str(spec["trade_date"]),
                        "role": str(spec["role"]),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
            write_progress(output, len(rows), resumed, len(errors))
            if count % 10 == 0 or count == len(specs):
                print(
                    f"[CAL_RR_NATIVE_FULL] {count}/{len(specs)} "
                    f"completed={len(rows)} resumed={resumed} errors={len(errors)}",
                    flush=True,
                )
    if errors or len(rows) != EXPECTED_CAPTURES:
        (output / "_state/errors.json").write_bytes(canonical_bytes({"errors": errors}))
        raise AssertionError(f"full native-clock capture failed: {errors[:5]}")
    seal = seal_full_capture(output, rows=rows, contract=contract)
    write_progress(output, len(rows), resumed, 0)
    print(json.dumps(seal, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
