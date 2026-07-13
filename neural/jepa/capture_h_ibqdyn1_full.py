"""Resumably capture and seal all eligible historical H-IBQDYN1 contracts."""

from __future__ import annotations

import argparse
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from neural.jepa.build_wall_quote_tick_dynamics_sidecar import sha256_file
from neural.jepa.capture_h_ibqdyn1_tick_preflight import (
    EXPECTED_ELIGIBLE_ID_SHA256,
    EXPECTED_ELIGIBLE_EVENTS,
    EXPECTED_FULL_CONTRACTS,
    EXPECTED_PROOF_MANIFEST_SHA256,
    EXPECTED_PROOF_SHA256,
    EXPECTED_SAMPLE_SHA256,
    PROOF_MANIFEST,
    RUNTIME_LOCK,
    canonical_bytes,
    capture_contract,
    load_frozen_contracts,
    source_provenance,
)
from neural.jepa.wall_surface_flow_environment import assert_runtime_lock

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PREDECLARATION = "research_papers/JEPA/H_IBQDYN1_FEASIBILITY_PREDECLARATION.md"
FEATURE_CLARIFICATION = (
    "research_papers/JEPA/H_IBQDYN1_FEATURE_SEMANTICS_CLARIFICATION.md"
)
FINAL_FIT_AMENDMENT = "research_papers/JEPA/H_IBQDYN1_2026_FINAL_FIT_AMENDMENT.md"
CODE_CLOSURE = (
    "neural/jepa/capture_h_ibqdyn1_full.py",
    "neural/jepa/capture_h_ibqdyn1_tick_preflight.py",
    "neural/jepa/build_h_ibqdyn1_feasibility.py",
    "neural/jepa/h_ibqdyn1_features.py",
    "neural/jepa/build_wall_native_quote_sidecar.py",
    "neural/jepa/build_wall_quote_tick_dynamics_sidecar.py",
    "neural/jepa/wall_surface_flow_environment.py",
    PREDECLARATION,
    FEATURE_CLARIFICATION,
    FINAL_FIT_AMENDMENT,
    PROOF_MANIFEST,
    RUNTIME_LOCK,
)


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
            raise AssertionError(f"H-IBQDYN1 full capture requires clean code: {relative}")
        hashes[relative] = sha256_file(PROJECT_ROOT / relative)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return commit, hashes


def candidate_csv(contracts: pd.DataFrame) -> str:
    columns = (
        "contract_id",
        "event_id",
        "ticker",
        "trade_date",
        "decision_dt",
        "minute",
        "nearest_level_name",
        "bucket",
        "right",
        "strike",
    )
    frame = contracts[list(columns)].copy()
    frame["decision_dt"] = pd.to_datetime(frame["decision_dt"]).map(
        lambda value: value.isoformat()
    )
    return frame.to_csv(index=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--terminal-jar")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=180.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 1 <= int(args.workers) <= 4:
        raise ValueError("H-IBQDYN1 full capture workers must be within 1..4")
    output = Path(args.output_root).resolve()
    seal = output / "_seal"
    seal_staging = output / "_seal.staging"
    if seal.exists():
        raise FileExistsError("immutable H-IBQDYN1 full seal already exists")
    if seal_staging.exists():
        suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        seal_staging.rename(output / f"_seal.staging.rejected-{suffix}")
    commit, code_hashes = committed_code_state()
    runtime = assert_runtime_lock(PROJECT_ROOT / RUNTIME_LOCK)
    contracts = load_frozen_contracts(sample_only=False)
    if len(contracts) != EXPECTED_FULL_CONTRACTS:
        raise AssertionError("H-IBQDYN1 full contract universe changed")
    output.mkdir(parents=True, exist_ok=True)
    candidates_path = output / "candidate_contracts.csv"
    frozen_csv = candidate_csv(contracts)
    if candidates_path.exists():
        if candidates_path.read_text(encoding="utf-8") != frozen_csv:
            raise AssertionError("existing H-IBQDYN1 candidate contracts changed")
    else:
        candidates_path.write_text(frozen_csv, encoding="utf-8")
    provenance, _remote_status_raw = source_provenance(
        args.base_url,
        terminal_jar=args.terminal_jar,
        timeout=float(args.timeout),
    )
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=int(args.workers)) as pool:
        futures = {
            pool.submit(
                capture_contract,
                contract,
                staging_root=output,
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
            if count % 100 == 0 or count == len(contracts):
                print(
                    f"[H-IBQDYN1_FULL] contracts={count}/{len(contracts)} "
                    f"errors={len(errors)}",
                    flush=True,
                )
    if errors or len(rows) != EXPECTED_FULL_CONTRACTS:
        error_path = output / "errors_latest.json"
        error_path.write_bytes(canonical_bytes({"errors": errors}))
        raise AssertionError(f"H-IBQDYN1 full capture incomplete: {errors[:20]}")
    index = pd.DataFrame(rows).sort_values(
        ["ticker", "trade_date", "decision_dt", "event_id", "right"], kind="stable"
    ).reset_index(drop=True)
    if (
        len(index) != EXPECTED_FULL_CONTRACTS
        or index["contract_id"].duplicated().any()
        or index["event_id"].nunique() != EXPECTED_ELIGIBLE_EVENTS
        or index["rows"].lt(0).any()
    ):
        raise AssertionError("H-IBQDYN1 final capture index invalid")
    seal_staging.mkdir(parents=True, exist_ok=False)
    index_path = seal_staging / "contract_index.csv"
    index.to_csv(index_path, index=False)
    manifest = {
        "schema": "h_ibqdyn1_full_capture_seal_v1",
        "status": "PASS_H_IBQDYN1_FULL_CAPTURE",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "git_commit": commit,
        "code_hashes": code_hashes,
        "proof_manifest_sha256": EXPECTED_PROOF_MANIFEST_SHA256,
        "proof_sha256": EXPECTED_PROOF_SHA256,
        "sample_sha256": EXPECTED_SAMPLE_SHA256,
        "eligible_event_id_sha256": EXPECTED_ELIGIBLE_ID_SHA256,
        "eligible_events": EXPECTED_ELIGIBLE_EVENTS,
        "contracts": int(len(index)),
        "rows": int(index["rows"].sum()),
        "call_rows": int(index.loc[index["right"].eq("CALL"), "rows"].sum()),
        "put_rows": int(index.loc[index["right"].eq("PUT"), "rows"].sum()),
        "zero_row_contracts": int(index["rows"].eq(0).sum()),
        "raw_bytes": int(index["raw_bytes"].sum()),
        "parquet_bytes": int(index["parquet_bytes"].sum()),
        "candidate_contracts_sha256": sha256_file(candidates_path),
        "contract_index_sha256": sha256_file(index_path),
        "provenance_evidence_sha256": sorted(
            index["provenance_sha256"].astype(str).unique().tolist()
        ),
        "source_identity": {
            field: provenance.get(field)
            for field in (
                "kind",
                "base_url",
                "status_endpoint",
                "status_value",
                "historical_provenance",
                "live_parity",
            )
        },
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment": runtime["environment"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "errors": [],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (seal_staging / "manifest.json").write_bytes(canonical_bytes(manifest))
    seal_staging.rename(seal)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
