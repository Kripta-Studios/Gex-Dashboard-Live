from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_RESULT = Path(
    "research_papers/JEPA/results/"
    "event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_causal_2023_2026_v1"
)
DEFAULT_FROZEN = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "dense_candidate_frozen_through_202512_eval_202601_202605_v1"
)
DEFAULT_RAW_COMPLETE_FROZEN_VERIFICATION = DEFAULT_FROZEN / "verification_raw_complete_202601_202604.json"
DEFAULT_PRE2026_GUARD_SELECTION_AUDIT = (
    Path(
        "research_papers/JEPA/results/_diagnostics/"
        "dense_candidate_frozen2025_2026_daily_guard_l4p1_vp0"
    )
    / "pre2026_guard_selection_audit"
    / "pre2026_guard_selection_audit.json"
)
DEFAULT_FEATURE_DATASET = Path(
    "research_papers/JEPA/results/"
    "event_option_dataset_spxw_spy_qqq_zero_dte_dense15_2022_2026_v1_physics/event_option_dataset.parquet"
)

LEAKY_PATTERNS = (
    "future",
    "spot_long",
    "spot_short",
    "spot_best",
    "_opt_win",
    "_opt_status",
    "_opt_exit_ret",
    "_opt_exit_minutes",
    "_opt_max_ret",
    "_opt_min_ret",
    "call_return",
    "put_return",
    "realized_return",
    "exit",
    "label",
    "target",
)


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def split_months(value: object) -> list[str]:
    if value is None:
        return []
    return [
        part.strip()
        for part in str(value).replace("[", "").replace("]", "").replace("'", "").replace('"', "").split(",")
        if part.strip() and part.strip().lower() != "nan"
    ]


def audit_fold_lineage(folds_path: Path, start_month: str, end_month: str, max_evidence_month: str | None = None) -> dict[str, Any]:
    if not folds_path.exists():
        return {"passed": False, "path": str(folds_path), "folds_checked": 0, "issues": [f"missing {folds_path}"]}
    folds = pd.read_csv(folds_path, dtype=str)
    month_cols = [
        "train_months",
        "val_months",
        "select_months",
        "profile_train_months",
        "profile_inner_val_months",
        "inner_val_months",
        "core_months",
    ]
    issues: list[str] = []
    checked = 0
    for idx, row in folds.iterrows():
        test_month = str(row.get("test_month", row.get("month", ""))).strip()[:6]
        if not test_month or test_month < str(start_month) or test_month > str(end_month):
            continue
        checked += 1
        for col in month_cols:
            if col not in folds.columns:
                continue
            months = split_months(row.get(col))
            non_prior = [month for month in months if month >= test_month]
            if non_prior:
                issues.append(f"row {idx} test_month={test_month} {col} has non-prior months {non_prior}")
            if max_evidence_month:
                after_cutoff = [month for month in months if month > str(max_evidence_month)]
                if after_cutoff:
                    issues.append(
                        f"row {idx} test_month={test_month} {col} has months after {max_evidence_month}: {after_cutoff}"
                    )
        if len(issues) >= 50:
            break
    if checked <= 0:
        issues.append(f"no folds in {start_month}..{end_month}")
    return {"passed": not issues, "path": str(folds_path), "folds_checked": int(checked), "issues": issues}


def audit_model_features(model_roots: list[Path]) -> dict[str, Any]:
    checked = 0
    issues: list[str] = []
    rows: list[dict[str, Any]] = []
    for root in model_roots:
        for path in sorted(root.rglob("event_option_gate_direction_model.json")):
            payload = read_json(path)
            features = [str(item) for item in payload.get("feature_cols", [])]
            bad = [feature for feature in features if any(pattern in feature.lower() for pattern in LEAKY_PATTERNS)]
            checked += 1
            rows.append(
                {
                    "path": str(path),
                    "feature_count": len(features),
                    "leaky_feature_count": len(bad),
                    "leaky_features": bad[:25],
                    "train_months_last": (payload.get("train_months") or [None])[-1],
                    "select_months": payload.get("select_months", []),
                }
            )
            if bad:
                issues.append(f"{path}: leaky features present {bad[:10]}")
    if checked <= 0:
        issues.append("no exported event option model metadata found")
    return {"passed": not issues, "models_checked": int(checked), "models": rows, "issues": issues}


def audit_dataset_contains_outcomes(dataset_path: Path) -> dict[str, Any]:
    if not dataset_path.exists():
        return {"available": False, "path": str(dataset_path), "outcome_columns": [], "issues": [f"missing {dataset_path}"]}
    columns = [str(col) for col in pd.read_parquet(dataset_path, engine="pyarrow").columns]
    outcome_columns = [col for col in columns if any(pattern in col.lower() for pattern in LEAKY_PATTERNS)]
    return {
        "available": True,
        "path": str(dataset_path),
        "column_count": len(columns),
        "outcome_columns": outcome_columns,
        "note": "Outcome/future columns may exist in the label dataset; this is acceptable only if excluded from feature_cols.",
        "issues": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit dense candidate for leakage, lookahead, and research snooping risk.")
    parser.add_argument("--result-dir", default=str(DEFAULT_RESULT))
    parser.add_argument("--frozen-dir", default=str(DEFAULT_FROZEN))
    parser.add_argument("--raw-complete-frozen-verification", default=str(DEFAULT_RAW_COMPLETE_FROZEN_VERIFICATION))
    parser.add_argument("--pre2026-guard-selection-audit", default=str(DEFAULT_PRE2026_GUARD_SELECTION_AUDIT))
    parser.add_argument("--feature-dataset", default=str(DEFAULT_FEATURE_DATASET))
    parser.add_argument("--candidate-dir", default="neural/models/jepa/jepa_production_event_options_dense15_strict_uniform_candidate")
    parser.add_argument("--output-dir", default="")
    parser.add_argument(
        "--exit-zero-on-failed-audit",
        action="store_true",
        help="Write the failed audit payload but return 0. Useful for status-report E2E suites.",
    )
    args = parser.parse_args()

    result_dir = Path(args.result_dir)
    frozen_dir = Path(args.frozen_dir)
    output_dir = Path(args.output_dir) if args.output_dir else result_dir / "anti_snooping_audit"
    output_dir.mkdir(parents=True, exist_ok=True)

    strict_selection = result_dir / "research_selection_audit_strict" / "research_selection_audit.json"
    strict_selection_payload = read_json(strict_selection) if strict_selection.exists() else {
        "passed": False,
        "strict": True,
        "issues": [f"missing {strict_selection}"],
        "warnings": [],
    }
    raw_complete_frozen = read_json(Path(args.raw_complete_frozen_verification))
    guard_selection_path = Path(args.pre2026_guard_selection_audit)
    guard_selection_payload = read_json(guard_selection_path) if guard_selection_path.exists() else {
        "passed": False,
        "issues": [f"missing {guard_selection_path}"],
    }
    main_lineage = audit_fold_lineage(result_dir / "combined_folds.csv", "202301", "202605")
    frozen_lineage = audit_fold_lineage(frozen_dir / "combined_folds.csv", "202601", "202604", max_evidence_month="202512")
    feature_audit = audit_model_features([Path(args.candidate_dir), result_dir, frozen_dir])
    dataset_audit = audit_dataset_contains_outcomes(Path(args.feature_dataset))

    hard_issues: list[str] = []
    if not main_lineage["passed"]:
        hard_issues.append("historical fold chronology failed")
    if not frozen_lineage["passed"]:
        hard_issues.append("frozen pre-2026 lineage failed")
    if not bool(raw_complete_frozen.get("passed")):
        hard_issues.append("raw-complete frozen 2026 verification failed")
    if not bool(guard_selection_payload.get("passed")):
        hard_issues.append("pre-2026 guard selection audit failed")
    if not feature_audit["passed"]:
        hard_issues.append("leaky model features detected")
    if not bool(strict_selection_payload.get("passed")):
        hard_issues.append(
            "strict research-selection audit failed; the 202301..202605 table is not final anti-snooping proof"
        )

    payload = {
        "schema_version": 1,
        "audit": "dense_candidate_anti_snooping",
        "passed": not hard_issues,
        "result_dir": str(result_dir),
        "checks": {
            "historical_fold_chronology": bool(main_lineage["passed"]),
            "raw_complete_frozen_pre2026_holdout": bool(raw_complete_frozen.get("passed")),
            "pre2026_guard_selection": bool(guard_selection_payload.get("passed")),
            "frozen_pre2026_lineage": bool(frozen_lineage["passed"]),
            "model_feature_leakage": bool(feature_audit["passed"]),
            "strict_research_selection": bool(strict_selection_payload.get("passed")),
        },
        "evidence": {
            "historical_fold_lineage": main_lineage,
            "frozen_pre2026_lineage": frozen_lineage,
            "raw_complete_frozen_verification": {
                "path": str(Path(args.raw_complete_frozen_verification)),
                "passed": bool(raw_complete_frozen.get("passed")),
            },
            "pre2026_guard_selection": {
                "path": str(guard_selection_path),
                "passed": bool(guard_selection_payload.get("passed")),
                "checks": guard_selection_payload.get("checks", {}),
                "selected_row": guard_selection_payload.get("selected_row", {}),
                "raw_complete_holdout": guard_selection_payload.get("raw_complete_holdout", {}),
                "issues": guard_selection_payload.get("issues", []),
            },
            "model_feature_audit": feature_audit,
            "dataset_outcome_columns": dataset_audit,
            "strict_research_selection": {
                "path": str(strict_selection),
                "passed": bool(strict_selection_payload.get("passed")),
                "issues": strict_selection_payload.get("issues", []),
                "warnings": strict_selection_payload.get("warnings", []),
            },
        },
        "issues": hard_issues,
    }
    (output_dir / "anti_snooping_audit.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Dense Candidate Anti-Snooping Audit",
        "",
        f"- Passed: {payload['passed']}",
        f"- Result dir: `{payload['result_dir']}`",
        "",
        "## Checks",
        "",
        "```json",
        json.dumps(payload["checks"], indent=2, allow_nan=True),
        "```",
        "",
        "## Issues",
        "",
    ]
    lines.extend([f"- {issue}" for issue in hard_issues] or ["- none"])
    lines += [
        "",
        "## Interpretation",
        "",
        "- Fold chronology and feature leakage are necessary but not sufficient.",
        "- If strict research selection fails, the historical table remains diagnostic even when its folds are causal.",
        "- The raw-complete frozen pre-2026 holdout is the current strongest anti-lookahead evidence.",
        "",
    ]
    (output_dir / "ANTI_SNOOPING_AUDIT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload, indent=2, allow_nan=True))
    if bool(args.exit_zero_on_failed_audit):
        return 0
    return 0 if payload["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

