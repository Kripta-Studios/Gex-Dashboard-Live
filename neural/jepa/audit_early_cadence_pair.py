from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


KEYS = ["ticker", "trade_date", "minute", "expiry_mode"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def compare_frames(control_path: Path, candidate_path: Path) -> tuple[dict, list[str]]:
    control = pd.read_parquet(control_path)
    candidate = pd.read_parquet(candidate_path)
    issues: list[str] = []
    if control.duplicated(KEYS).any() or candidate.duplicated(KEYS).any():
        issues.append("cadence dataset keys are not unique")
    control_minutes = pd.to_numeric(control["minute"], errors="coerce")
    candidate_minutes = pd.to_numeric(candidate["minute"], errors="coerce")
    if not control_minutes.mod(5).eq(0).all():
        issues.append("control is not a five-minute grid")
    if set(candidate_minutes.dropna().astype(int).unique()) != set(range(600, 626)):
        issues.append("candidate does not contain every minute from 10:00 through 10:25")
    candidate_control_grid = candidate[candidate_minutes.mod(5).eq(0)].copy()
    common_columns = [column for column in control.columns if column in candidate.columns]
    left = control[common_columns].sort_values(KEYS).reset_index(drop=True)
    right = candidate_control_grid[common_columns].sort_values(KEYS).reset_index(drop=True)
    key_parity = bool(len(left) == len(right) and left[KEYS].equals(right[KEYS]))
    if not key_parity:
        issues.append("one-minute candidate does not reproduce all five-minute control keys")
    differing_columns: list[str] = []
    max_numeric_abs_diff = 0.0
    if key_parity:
        for column in common_columns:
            if column in KEYS:
                continue
            a = left[column]
            b = right[column]
            if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
                av = pd.to_numeric(a, errors="coerce").to_numpy(dtype=float)
                bv = pd.to_numeric(b, errors="coerce").to_numpy(dtype=float)
                finite = np.isfinite(av) & np.isfinite(bv)
                diff = float(np.max(np.abs(av[finite] - bv[finite]))) if finite.any() else 0.0
                nan_parity = bool(np.array_equal(np.isnan(av), np.isnan(bv)))
                max_numeric_abs_diff = max(max_numeric_abs_diff, diff)
                if diff > 1e-9 or not nan_parity:
                    differing_columns.append(column)
            else:
                if not a.fillna("<NA>").astype(str).equals(b.fillna("<NA>").astype(str)):
                    differing_columns.append(column)
    if differing_columns:
        issues.append(
            "five-minute subset differs from control in columns: "
            + ", ".join(differing_columns[:20])
        )
    payload = {
        "schema_version": 1,
        "audit": "early_candidate_cadence_pair",
        "control_path": str(control_path),
        "control_sha256": sha256(control_path),
        "candidate_path": str(candidate_path),
        "candidate_sha256": sha256(candidate_path),
        "control_rows": int(len(control)),
        "candidate_rows": int(len(candidate)),
        "candidate_control_grid_rows": int(len(candidate_control_grid)),
        "candidate_extra_rows": int(len(candidate) - len(candidate_control_grid)),
        "common_columns": int(len(common_columns)),
        "key_parity": key_parity,
        "max_numeric_abs_diff": max_numeric_abs_diff,
        "differing_columns": differing_columns,
        "issues": issues,
        "passed": not issues,
    }
    return payload, issues


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify that a one-minute early dataset is a strict cadence expansion of the five-minute control."
    )
    parser.add_argument("--control-data", required=True)
    parser.add_argument("--candidate-data", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    payload, issues = compare_frames(Path(args.control_data), Path(args.candidate_data))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
