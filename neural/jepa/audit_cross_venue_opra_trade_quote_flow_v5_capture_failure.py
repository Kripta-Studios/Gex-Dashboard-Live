"""Audit the fail-closed, incomplete V5 OPRA source capture from raw bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa import (  # noqa: E402
    audit_cross_venue_opra_trade_quote_flow_v5 as independent,
)

DEFAULT_CAPTURE_ROOT = Path(
    "D:/ThetaData/cross_venue_opra_trade_quote_flow_v5_capture_2023_2025_v1"
)
DEFAULT_OUTPUT = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_opra_trade_quote_flow_v5_capture_failure_audit_2023_2025_v1"
)
EXPECTED_CAPTURES = 1_504
EXPECTED_COMPLETED = 1_364
EXPECTED_FAILURES = 140
EXPECTED_ERRORS_SHA256 = (
    "3f5757465d8067c02ef54ae77020c774af449570d7cedd462c460be566fbc3d3"
)
EXPECTED_UNIVERSE_SHA256 = (
    "cf6fe71f43e517776ca4b1f98501d02c75e93874e94681854aadc3312be02254"
)
EXPECTED_CONTRACT_SHA256 = (
    "210ea579d5278eccc8add95ace703e4c615fa70595ee7662ba303781daa205a6"
)
EXPECTED_DATE_SHA256 = (
    "e7786a1a8861ef8aaaeb8aed5cfe08ccaea50c8bcec575800ec044e88890b8f9"
)
EXPECTED_CAPTURE_COMMIT = "e6bdac64ffa37f4164024de82f7b535a83ee660b"
ERROR_TEXT = "AssertionError: invalid or duplicate V5 trade_quote response"
CODE_CLOSURE = (
    "neural/jepa/audit_cross_venue_opra_trade_quote_flow_v5_capture_failure.py",
    "neural/jepa/audit_cross_venue_opra_trade_quote_flow_v5.py",
    "neural/jepa/capture_cross_venue_opra_trade_quote_flow_v5.py",
    "research_papers/JEPA/CROSS_VENUE_OPRA_TRADE_QUOTE_FLOW_V5_PREDECLARATION.md",
)


def sha256_file(path: str | Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def committed_state() -> tuple[str, dict[str, str]]:
    hashes: dict[str, str] = {}
    for relative in CODE_CLOSURE:
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
            raise AssertionError(f"V5 failure audit requires clean code: {relative}")
        hashes[relative] = sha256_file(PROJECT_ROOT / relative)
    head = subprocess.run(
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
    if head != origin:
        raise AssertionError("V5 failure audit requires HEAD == origin/main")
    return head, hashes


def ordered_hash(values: list[str]) -> str:
    payload = ("\n".join(sorted(values)) + "\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_frozen_state(
    root: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    universe_path = root / "_state/universe.csv"
    contract_path = root / "_state/capture_contract.json"
    errors_path = root / "_state/errors.json"
    if (
        sha256_file(universe_path) != EXPECTED_UNIVERSE_SHA256
        or sha256_file(contract_path) != EXPECTED_CONTRACT_SHA256
        or sha256_file(errors_path) != EXPECTED_ERRORS_SHA256
    ):
        raise AssertionError("V5 failed-capture authority hash changed")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    universe = pd.read_csv(
        universe_path, dtype={"trade_date": str, "expiration": str, "year": str}
    )
    errors = pd.DataFrame(json.loads(errors_path.read_text(encoding="utf-8"))["errors"])
    if (
        len(universe) != EXPECTED_CAPTURES
        or universe["capture_id"].duplicated().any()
        or universe["trade_date"].str.startswith("2026").any()
        or len(errors) != EXPECTED_FAILURES
        or errors["capture_id"].duplicated().any()
        or not errors["error"].eq(ERROR_TEXT).all()
        or not set(errors["capture_id"]).issubset(set(universe["capture_id"]))
        or contract.get("git_commit") != EXPECTED_CAPTURE_COMMIT
        or contract.get("outcome_clock_accessed") is not False
        or contract.get("outcome_2026_accessed") is not False
        or contract.get("production_modified") is not False
        or contract.get("universe_audit", {}).get("date_sha256")
        != EXPECTED_DATE_SHA256
    ):
        raise AssertionError("V5 failed-capture frozen state is invalid")
    dates = sorted(universe.loc[universe["sensor"].eq("QQQ"), "trade_date"].unique())
    if ordered_hash(dates) != EXPECTED_DATE_SHA256:
        raise AssertionError("V5 failure audit date universe changed")
    return universe, errors, contract


def capture_directory(root: Path, sensor: str, trade_date: str) -> Path:
    return root / sensor / trade_date


def audit_sources(
    root: Path, universe: pd.DataFrame, errors: pd.DataFrame
) -> pd.DataFrame:
    if (root / "_seal").exists():
        raise AssertionError("failed V5 capture unexpectedly has a PASS seal")
    stagers = list(root.rglob("*.staging"))
    if stagers:
        raise AssertionError(f"failed V5 capture has partial stagers: {stagers[:5]}")
    failed_ids = set(errors["capture_id"])
    rows: list[dict[str, Any]] = []
    completed_ids: set[str] = set()
    for record in universe.sort_values(["sensor", "trade_date"], kind="stable").to_dict(
        "records"
    ):
        capture_id = str(record["capture_id"])
        sensor = str(record["sensor"])
        trade_date = str(record["trade_date"])
        directory = capture_directory(root, sensor, trade_date)
        if capture_id in failed_ids:
            if directory.exists():
                raise AssertionError("failed V5 capture ID has a completed directory")
            continue
        raw_path = directory / "response.ndjson"
        parquet_path = directory / "trades.parquet"
        manifest_path = directory / "manifest.json"
        if not (raw_path.is_file() and parquet_path.is_file() and manifest_path.is_file()):
            raise FileNotFoundError(f"unaccounted V5 capture source: {directory}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        observed = {
            "raw_sha256": sha256_file(raw_path),
            "parquet_sha256": sha256_file(parquet_path),
            "manifest_sha256": sha256_file(manifest_path),
        }
        if (
            observed["raw_sha256"] != manifest.get("raw_sha256")
            or observed["parquet_sha256"] != manifest.get("parquet_sha256")
            or manifest.get("capture_id") != capture_id
            or manifest.get("sensor") != sensor
            or manifest.get("trade_date") != trade_date
            or manifest.get("outcome_clock_accessed") is not False
            or manifest.get("outcome_2026_accessed") is not False
            or manifest.get("production_modified") is not False
        ):
            raise AssertionError(f"V5 completed source identity/hash changed: {directory}")
        rebuilt = independent._parse_raw(
            raw_path.read_bytes(), sensor=sensor, trade_date=trade_date
        )
        pd.testing.assert_frame_equal(
            pd.read_parquet(parquet_path), rebuilt, check_dtype=True
        )
        if int(manifest.get("rows", -1)) != len(rebuilt):
            raise AssertionError(f"V5 completed source rows changed: {directory}")
        completed_ids.add(capture_id)
        rows.append(
            {
                "capture_id": capture_id,
                "sensor": sensor,
                "trade_date": trade_date,
                "year": trade_date[:4],
                "month": trade_date[:6],
                "rows": int(len(rebuilt)),
                "raw_bytes": int(raw_path.stat().st_size),
                "parquet_bytes": int(parquet_path.stat().st_size),
                **observed,
            }
        )
    expected_completed = set(universe["capture_id"]).difference(failed_ids)
    if (
        completed_ids != expected_completed
        or len(rows) != EXPECTED_COMPLETED
        or completed_ids.intersection(failed_ids)
    ):
        raise AssertionError("V5 completed/failed universe partition changed")
    return pd.DataFrame(rows).sort_values(
        ["sensor", "trade_date"], kind="stable"
    ).reset_index(drop=True)


def gate_tables(
    universe: pd.DataFrame, errors: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    failed = errors[["capture_id", "sensor", "trade_date", "error"]].copy()
    failed["year"] = failed["trade_date"].str[:4]
    failed["month"] = failed["trade_date"].str[:6]
    annual_rows = []
    monthly_rows = []
    for (sensor, year), expected in universe.groupby(
        ["sensor", "year"], observed=True, sort=True
    ):
        failures = failed[
            failed["sensor"].eq(sensor) & failed["year"].eq(year)
        ]
        complete = len(expected) - len(failures)
        annual_rows.append(
            {
                "sensor": sensor,
                "year": year,
                "expected_captures": int(len(expected)),
                "completed_captures": int(complete),
                "failed_captures": int(len(failures)),
                "source_coverage": complete / len(expected),
                "zero_missing_pass": len(failures) == 0,
                "pre_feature_coverage_90_pass": complete / len(expected) >= 0.90,
            }
        )
    universe_with_month = universe.copy()
    universe_with_month["month"] = universe_with_month["trade_date"].str[:6]
    for (sensor, month), expected in universe_with_month.groupby(
        ["sensor", "month"], observed=True, sort=True
    ):
        failures = failed[
            failed["sensor"].eq(sensor) & failed["month"].eq(month)
        ]
        complete = len(expected) - len(failures)
        monthly_rows.append(
            {
                "sensor": sensor,
                "month": month,
                "expected_captures": int(len(expected)),
                "completed_captures": int(complete),
                "failed_captures": int(len(failures)),
                "minimum_13_source_captures_pass": complete >= 13,
                "zero_missing_pass": len(failures) == 0,
            }
        )
    return pd.DataFrame(annual_rows), pd.DataFrame(monthly_rows)


def write_audit(
    output: Path,
    *,
    universe: pd.DataFrame,
    errors: pd.DataFrame,
    rehash: pd.DataFrame,
    annual: pd.DataFrame,
    monthly: pd.DataFrame,
    capture_contract: dict[str, Any],
    git_commit: str,
    code_hashes: dict[str, str],
) -> dict[str, Any]:
    staging = output.with_name(output.name + ".staging")
    if output.exists() or staging.exists():
        raise FileExistsError(f"immutable V5 failure audit exists: {output}")
    staging.mkdir(parents=True)
    failures = errors.copy()
    failures["year"] = failures["trade_date"].str[:4]
    failures["month"] = failures["trade_date"].str[:6]
    frames = {
        "failure_inventory.csv": failures.sort_values(
            ["sensor", "trade_date"], kind="stable"
        ),
        "source_rehash.csv": rehash,
        "sensor_year_capture_gate.csv": annual,
        "sensor_month_capture_gate.csv": monthly,
    }
    for name, frame in frames.items():
        frame.to_csv(staging / name, index=False, lineterminator="\n")
    artifact_hashes = {name: sha256_file(staging / name) for name in frames}
    summary = {
        "schema": "cross_venue_opra_trade_quote_flow_v5_capture_failure_audit_v1",
        "status": "PASS_INDEPENDENT_AUDIT_OF_FAILED_SOURCE_CAPTURE_GATE",
        "audited_capture_status": "FAILED_OUTCOME_FREE_SOURCE_CAPTURE_GATE",
        "advance_to_feature_gate": False,
        "advance_to_outcomes": False,
        "market_values_accessed": True,
        "outcome_clock_accessed": False,
        "outcome_2026_accessed": False,
        "production_modified": False,
        "expected_captures": int(len(universe)),
        "completed_captures_rehashed_and_reparsed": int(len(rehash)),
        "failed_captures": int(len(errors)),
        "source_hash_mismatches": 0,
        "unaccounted_capture_ids": 0,
        "staging_directories": 0,
        "capture_seal_present": False,
        "all_errors_exact_contract_violation": bool(errors["error"].eq(ERROR_TEXT).all()),
        "all_sensor_year_zero_missing_pass": bool(annual["zero_missing_pass"].all()),
        "all_sensor_month_zero_missing_pass": bool(monthly["zero_missing_pass"].all()),
        "minimum_completed_captures_in_any_sensor_month": int(
            monthly["completed_captures"].min()
        ),
        "capture_commit": capture_contract["git_commit"],
        "audit_commit": git_commit,
        "code_hashes": code_hashes,
        "errors_json_sha256": EXPECTED_ERRORS_SHA256,
        "universe_csv_sha256": EXPECTED_UNIVERSE_SHA256,
        "capture_contract_sha256": EXPECTED_CONTRACT_SHA256,
        "artifact_hashes": artifact_hashes,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    summary_path = staging / "audit_summary.json"
    summary_path.write_bytes(canonical_bytes(summary))
    seal = {
        "schema": "cross_venue_opra_trade_quote_flow_v5_capture_failure_audit_seal_v1",
        "status": summary["status"],
        "audited_capture_status": summary["audited_capture_status"],
        "advance_to_feature_gate": False,
        "advance_to_outcomes": False,
        "outcome_clock_accessed": False,
        "outcome_2026_accessed": False,
        "production_modified": False,
        "audit_summary_sha256": sha256_file(summary_path),
        "failure_inventory_sha256": artifact_hashes["failure_inventory.csv"],
        "source_rehash_sha256": artifact_hashes["source_rehash.csv"],
    }
    (staging / "seal.json").write_bytes(canonical_bytes(seal))
    staging.rename(output)
    return {**summary, **seal}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-root", type=Path, default=DEFAULT_CAPTURE_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    git_commit, code_hashes = committed_state()
    root = args.capture_root.resolve()
    universe, errors, contract = load_frozen_state(root)
    rehash = audit_sources(root, universe, errors)
    annual, monthly = gate_tables(universe, errors)
    summary = write_audit(
        args.output_root.resolve(),
        universe=universe,
        errors=errors,
        rehash=rehash,
        annual=annual,
        monthly=monthly,
        capture_contract=contract,
        git_commit=git_commit,
        code_hashes=code_hashes,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
