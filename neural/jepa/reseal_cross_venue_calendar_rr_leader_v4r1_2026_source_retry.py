#!/usr/bin/env python3
"""Reparse the immutable V4R1 retry raw offline after the timestamp dtype fix."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from neural.jepa import (  # noqa: E402
    capture_cross_venue_calendar_rr_leader_v4r1_2026_source_retry as capture,
)
from neural.jepa import (  # noqa: E402
    cross_venue_calendar_rr_leader_v4r1_2026_common as common,
)
from neural.jepa.build_calendar_risk_reversal_pressure_v1 import (  # noqa: E402
    tracked_clean,
)


PROJECT_ROOT = SCRIPT_REPO_ROOT
DEFAULT_INPUT = common.RETRY_ROOT
DEFAULT_OUTPUT = common.RETRY_RESEAL_ROOT
BUILDER = PROJECT_ROOT / (
    "neural/jepa/build_cross_venue_calendar_rr_leader_v4r1_2026_data_gate.py"
)
AUDITOR = PROJECT_ROOT / (
    "neural/jepa/audit_cross_venue_calendar_rr_leader_v4r1_2026_data_gate.py"
)
CLARIFICATION = PROJECT_ROOT / (
    "research_papers/JEPA/"
    "CROSS_VENUE_CALENDAR_RR_LEADER_V4R1_RETRY_TIMESTAMP_DTYPE_CLARIFICATION.md"
)
CODE_CLOSURE = (
    Path(__file__).resolve(),
    Path(common.__file__).resolve(),
    Path(capture.__file__).resolve(),
    BUILDER,
    AUDITOR,
    common.PREDECLARATION,
    CLARIFICATION,
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


def verify_code() -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in CODE_CLOSURE:
        tracked_clean(path, f"V4R1 offline reseal closure {path.name}")
        hashes[path.relative_to(PROJECT_ROOT).as_posix()] = common.sha256_file(path)
    if common.sha256_file(common.PREDECLARATION) != common.PREDECLARATION_SHA256:
        raise AssertionError("V4R1 predeclaration changed")
    return hashes


def verify_source_root(source_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    seal_path = source_root / "seal.json"
    if common.sha256_file(seal_path) != common.ORIGINAL_RETRY_SEAL_SHA256:
        raise AssertionError("immutable V4R1 retry source seal changed")
    source_seal = json.loads(seal_path.read_text(encoding="utf-8"))
    if (
        source_seal.get("schema")
        != "cross_venue_calendar_rr_leader_v4r1_retry_seal_v1"
        or source_seal.get("outcome_free") is not True
        or source_seal.get("outcome_2026_accessed") is not False
        or source_seal.get("normalized_responses") != 10
    ):
        raise AssertionError("invalid V4R1 retry source seal")
    request_path = source_root / "request_index.csv"
    if common.sha256_file(request_path) != source_seal["request_index_sha256"]:
        raise AssertionError("V4R1 retry request index changed")
    requests = pd.read_csv(
        request_path,
        dtype={
            "capture_id": str,
            "ticker": str,
            "trade_date": str,
            "expiration": str,
        },
    )
    specs = common.retry_specs(common.discover_universe())
    if (
        len(requests) != 10
        or requests.duplicated(["capture_id", "kind"]).any()
        or not requests["status"].eq("PASS_NORMALIZED_RESPONSE").all()
    ):
        raise AssertionError("V4R1 retry request closure changed")
    spec_lookup = {
        str(row["capture_id"]): row for row in specs.to_dict(orient="records")
    }
    for row in requests.to_dict(orient="records"):
        directory = Path(str(row["directory"]))
        manifest_path = directory / "manifest.json"
        raw_path = directory / "response.json"
        normalized_path = Path(str(row["normalized_path"]))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (
            common.sha256_file(manifest_path) != str(row["manifest_sha256"])
            or common.sha256_file(raw_path) != manifest["raw_sha256"]
            or common.sha256_file(normalized_path) != manifest["normalized_sha256"]
            or manifest.get("outcome_2026_accessed") is not False
        ):
            raise AssertionError("V4R1 retry raw/normalized closure changed")
        rebuilt = common.normalize_response(
            json.loads(raw_path.read_bytes()),
            spec_lookup[str(row["capture_id"])],
            str(row["kind"]),
            str(row["interval_used"]),
        )
        stored = pd.read_parquet(normalized_path)
        pd.testing.assert_frame_equal(rebuilt, stored, check_dtype=True)
    return requests, specs


def run(source_root: Path, output_dir: Path) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"immutable V4R1 offline reseal exists: {output_dir}")
    code_hashes = verify_code()
    requests, specs = verify_source_root(source_root)
    pair_gate, exclusions = capture.build_pair_gate(requests, specs)
    if int(pair_gate["usable"].sum()) != 5 or not exclusions.empty:
        raise AssertionError("V4R1 offline reparse did not recover all five pairs")
    staging = output_dir.with_name(f".{output_dir.name}.staging-{os.getpid()}")
    if staging.exists():
        raise FileExistsError(staging)
    staging.mkdir(parents=True)
    try:
        shutil.copyfile(source_root / "request_index.csv", staging / "request_index.csv")
        pair_gate.to_csv(staging / "pair_gate.csv", index=False, lineterminator="\n")
        exclusions.to_csv(staging / "exclusions.csv", index=False, lineterminator="\n")
        source_rehash = requests[
            ["capture_id", "kind", "directory", "normalized_path"]
        ].copy()
        source_rehash["manifest_sha256"] = source_rehash["directory"].map(
            lambda value: common.sha256_file(Path(str(value)) / "manifest.json")
        )
        source_rehash["raw_sha256"] = source_rehash["directory"].map(
            lambda value: common.sha256_file(Path(str(value)) / "response.json")
        )
        source_rehash["normalized_sha256"] = source_rehash["normalized_path"].map(
            common.sha256_file
        )
        source_rehash.to_csv(
            staging / "source_rehash.csv", index=False, lineterminator="\n"
        )
        seal = {
            "schema": "cross_venue_calendar_rr_leader_v4r1_retry_offline_reseal_v2",
            "status": "PASS_OFFLINE_REPARSE_RETRY_GATE",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "execution_commit": current_git_commit(),
            "source_root": str(source_root),
            "source_seal_sha256": common.ORIGINAL_RETRY_SEAL_SHA256,
            "logical_requests": 10,
            "usable_pairs": 5,
            "excluded_sensor_dates": 0,
            "greek_rows": int(pair_gate["greek_rows"].sum()),
            "iv_rows": int(pair_gate["iv_rows"].sum()),
            "shared_rows": int(pair_gate["shared_rows"].sum()),
            "greek_only_rows": 0,
            "iv_only_rows": 0,
            "request_index_sha256": common.sha256_file(
                staging / "request_index.csv"
            ),
            "pair_gate_sha256": common.sha256_file(staging / "pair_gate.csv"),
            "exclusions_sha256": common.sha256_file(staging / "exclusions.csv"),
            "source_rehash_sha256": common.sha256_file(
                staging / "source_rehash.csv"
            ),
            "predeclaration_sha256": common.PREDECLARATION_SHA256,
            "date_sha256": common.DATE_SHA256,
            "capture_id_sha256": common.CAPTURE_ID_SHA256,
            "code_hashes": code_hashes,
            "network_accessed": False,
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
    parser.add_argument("--source-root", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    seal = run(args.source_root.resolve(), args.output_dir.resolve())
    print(json.dumps(seal, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
