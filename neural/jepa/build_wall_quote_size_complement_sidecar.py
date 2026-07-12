"""Capture the frozen 1,078-session native-clock complement for H-QSIZE1.

The original native quote sidecar covers only Greek files missing an option
timestamp.  H-QSIZE1 needs bid/ask sizes for the disjoint complement whose Greek
files already have a native timestamp.  This module reuses the audited immutable
per-session downloader and writes a separate sealed index; it never reads labels
or outcomes and never overwrites a session artifact.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.build_wall_native_quote_sidecar import (  # noqa: E402
    CANONICAL_MANIFEST_SHA256,
    DEFAULT_START_TIME,
    download_session,
    research_end_time,
    session_key_hash,
    sha256_file,
    validate_session,
)
from neural.jepa.build_wall_surface_flow_dataset import (  # noqa: E402
    EXPECTED_SESSION_COUNT,
    EXPECTED_SESSION_KEY_SHA256,
    filter_manifest,
)
from neural.jepa.wall_surface_flow_environment import assert_runtime_lock  # noqa: E402


EXPECTED_COMPLEMENT_SESSIONS = 1078
EXPECTED_COMPLEMENT_KEY_SHA256 = (
    "10665f9070736651ee0d04a63f01a28165b3cd818c42e711437f256be342e3dd"
)
PREDECLARATION = (
    "research_papers/JEPA/WALL_QUOTE_SIZE_PRESSURE_AT_TOUCH_V1_PREDECLARATION.md"
)
RUNTIME_LOCK = "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt"
CODE_CLOSURE = (
    "neural/jepa/build_wall_quote_size_complement_sidecar.py",
    "neural/jepa/build_wall_native_quote_sidecar.py",
    PREDECLARATION,
    RUNTIME_LOCK,
)


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def committed_code_hashes() -> tuple[str, dict[str, str]]:
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
            raise AssertionError(f"authoritative H-QSIZE1 capture requires clean code: {relative}")
        hashes[relative] = sha256_file(PROJECT_ROOT / relative)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return commit, hashes


def discover_native_timestamp_sessions(manifest_path: str | Path) -> pd.DataFrame:
    path = Path(manifest_path)
    if sha256_file(path) != CANONICAL_MANIFEST_SHA256:
        raise AssertionError("canonical source manifest hash mismatch")
    sessions = filter_manifest(pd.read_csv(path), start_date="20220801", end_date="20251231")
    if (
        len(sessions) != EXPECTED_SESSION_COUNT
        or session_key_hash(sessions) != EXPECTED_SESSION_KEY_SHA256
    ):
        raise AssertionError("canonical H-QSIZE1 session universe mismatch")
    rows: list[dict[str, str]] = []
    for row in sessions.sort_values(["ticker", "trade_date"], kind="stable").itertuples(
        index=False
    ):
        greeks_path = Path(str(row.greeks_path))
        if not greeks_path.is_file():
            raise FileNotFoundError(f"missing Greek source: {greeks_path}")
        names = set(pq.ParquetFile(greeks_path).schema_arrow.names)
        if "timestamp" in names:
            rows.append(
                {
                    "ticker": str(row.ticker).upper(),
                    "trade_date": str(row.trade_date),
                    "greeks_path": str(greeks_path),
                }
            )
        elif "underlying_timestamp" not in names:
            raise AssertionError(f"Greek source has no usable clock: {greeks_path}")
    result = pd.DataFrame(rows)
    if (
        len(result) != EXPECTED_COMPLEMENT_SESSIONS
        or result.duplicated(["ticker", "trade_date"]).any()
        or session_key_hash(result) != EXPECTED_COMPLEMENT_KEY_SHA256
        or result["trade_date"].str.startswith("2026").any()
    ):
        raise AssertionError("frozen native-timestamp complement changed")
    return result


def backfill_complement(
    *,
    manifest_path: str | Path,
    output_root: str | Path,
    base_url: str,
    terminal_jar: str | Path,
    workers: int = 4,
    timeout: float = 180.0,
) -> dict[str, Any]:
    if not 1 <= int(workers) <= 4:
        raise ValueError("H-QSIZE1 complement workers must be within 1..4")
    commit, code_hashes = committed_code_hashes()
    runtime = assert_runtime_lock(PROJECT_ROOT / RUNTIME_LOCK)
    sessions = discover_native_timestamp_sessions(manifest_path)
    root = Path(output_root)
    seal_dir = root / "_seal"
    seal_staging = root / "_seal.staging"
    if seal_dir.exists() or seal_staging.exists():
        raise FileExistsError("immutable H-QSIZE1 complement seal already exists")
    jar = Path(terminal_jar).resolve()
    jar_hash = sha256_file(jar)

    def one(record: dict[str, str]) -> dict[str, Any]:
        ticker, day = record["ticker"], record["trade_date"]
        session_dir = root / ticker / day
        if session_dir.exists():
            manifest = validate_session(session_dir, record["greeks_path"])
        else:
            manifest = download_session(
                ticker=ticker,
                trade_date=day,
                greeks_path=record["greeks_path"],
                output_root=root,
                base_url=base_url,
                terminal_jar=jar,
                start_time=DEFAULT_START_TIME,
                end_time=research_end_time(ticker, day),
                timeout=timeout,
            )
        session_manifest = session_dir / "manifest.json"
        return {
            "ticker": ticker,
            "trade_date": day,
            "greeks_path": record["greeks_path"],
            "greeks_sha256": str(manifest["greeks_sha256"]),
            "quotes_path": str(session_dir / "quotes.parquet"),
            "quotes_sha256": str(manifest["quote_parquet_sha256"]),
            "raw_response_path": str(session_dir / "quote_response.json"),
            "raw_response_sha256": str(manifest["raw_response_sha256"]),
            "session_manifest_path": str(session_manifest),
            "session_manifest_sha256": sha256_file(session_manifest),
            "rows": int(manifest["rows"]),
            "crossed_quote_rows": int(manifest["crossed_quote_rows"]),
            "terminal_jar_sha256": str(manifest["terminal_jar_sha256"]),
            "stored_timestamp_key_coverage_exact": bool(
                manifest["stored_timestamp_key_coverage_exact"]
            ),
            "missing_stored_key_rows": int(manifest["missing_stored_key_rows"]),
            "native_extra_key_rows": int(manifest["native_extra_key_rows"]),
            "stored_bid_ask_exact": bool(manifest["stored_bid_ask_exact"]),
            "stored_either_mismatch_rows": int(manifest["stored_either_mismatch_rows"]),
        }

    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    records = sessions.to_dict("records")
    with ThreadPoolExecutor(max_workers=int(workers)) as pool:
        futures = {pool.submit(one, record): record for record in records}
        for index, future in enumerate(as_completed(futures), start=1):
            record = futures[future]
            try:
                rows.append(future.result())
            except Exception as exc:
                errors.append(
                    {
                        "ticker": str(record["ticker"]),
                        "trade_date": str(record["trade_date"]),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
            if index % 25 == 0 or index == len(futures):
                print(
                    f"[QSIZE_COMPLEMENT] sessions={index}/{len(futures)} errors={len(errors)}",
                    flush=True,
                )
    if errors:
        raise AssertionError(f"H-QSIZE1 complement incomplete; no seal: {errors[:10]}")
    index_frame = pd.DataFrame(rows).sort_values(
        ["ticker", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    if (
        len(index_frame) != EXPECTED_COMPLEMENT_SESSIONS
        or index_frame.duplicated(["ticker", "trade_date"]).any()
        or session_key_hash(index_frame) != EXPECTED_COMPLEMENT_KEY_SHA256
        or not index_frame["stored_timestamp_key_coverage_exact"].astype(bool).all()
        or not index_frame["missing_stored_key_rows"].eq(0).all()
        or set(index_frame["terminal_jar_sha256"].astype(str)) != {jar_hash}
        or sha256_file(jar) != jar_hash
    ):
        raise AssertionError("H-QSIZE1 complement index failed exact coverage gate")
    seal_staging.mkdir(parents=True, exist_ok=False)
    index_path = seal_staging / "quote_size_complement_index.csv"
    index_frame.to_csv(index_path, index=False)
    payload = {
        "schema": "wall_quote_size_native_complement_seal_v1",
        "status": "PASS_QSIZE_NATIVE_COMPLEMENT",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit,
        "code_hashes": code_hashes,
        "source_manifest_path": str(Path(manifest_path)),
        "source_manifest_sha256": sha256_file(manifest_path),
        "sessions": int(len(index_frame)),
        "session_key_sha256": EXPECTED_COMPLEMENT_KEY_SHA256,
        "rows": int(index_frame["rows"].sum()),
        "rows_by_ticker": index_frame.groupby("ticker", observed=True)["rows"]
        .sum()
        .astype(int)
        .to_dict(),
        "crossed_quote_rows": int(index_frame["crossed_quote_rows"].sum()),
        "native_extra_key_rows": int(index_frame["native_extra_key_rows"].sum()),
        "stored_bid_ask_exact_sessions": int(
            index_frame["stored_bid_ask_exact"].astype(bool).sum()
        ),
        "stored_bid_ask_revised_sessions": int(
            (~index_frame["stored_bid_ask_exact"].astype(bool)).sum()
        ),
        "stored_either_mismatch_rows": int(
            index_frame["stored_either_mismatch_rows"].sum()
        ),
        "index_path": str(seal_dir / index_path.name),
        "index_sha256": sha256_file(index_path),
        "base_url": base_url.rstrip("/"),
        "terminal_jar_path": str(jar),
        "terminal_jar_sha256": jar_hash,
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment": runtime["environment"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "historical_provenance": "CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION",
        "errors": [],
    }
    (seal_staging / "manifest.json").write_bytes(canonical_bytes(payload))
    seal_staging.rename(seal_dir)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit-universe")
    audit.add_argument("--manifest", required=True)
    backfill = sub.add_parser("backfill")
    backfill.add_argument("--manifest", required=True)
    backfill.add_argument("--output-root", required=True)
    backfill.add_argument("--base-url", default="http://127.0.0.1:25503/v3")
    backfill.add_argument("--terminal-jar", required=True)
    backfill.add_argument("--workers", type=int, default=4)
    backfill.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    if args.command == "audit-universe":
        frame = discover_native_timestamp_sessions(args.manifest)
        result = {
            "sessions": len(frame),
            "session_key_sha256": session_key_hash(frame),
            "rows_by_ticker": frame.groupby("ticker").size().astype(int).to_dict(),
        }
    else:
        result = backfill_complement(
            manifest_path=args.manifest,
            output_root=args.output_root,
            base_url=args.base_url,
            terminal_jar=args.terminal_jar,
            workers=args.workers,
            timeout=args.timeout,
        )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
