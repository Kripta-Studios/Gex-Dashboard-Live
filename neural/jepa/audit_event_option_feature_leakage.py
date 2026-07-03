from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
JEPA_DIR = Path(__file__).resolve().parent
for item in (PROJECT_ROOT, JEPA_DIR):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from neural.jepa.evaluate_dense_candidate_fixed_holdout import FEATURE_PREFIXES
from neural.jepa.event_option_component_live import live_observable_feature_issues_for_columns
from neural.jepa.verify_event_option_result import audit_folds, parse_month_list
from neural.jepa.walkforward_event_option_gate import LEAKY_PATTERNS, build_features, parse_hhmm_to_minute, prepare_frame


DEFAULT_DATA = Path(
    "research_papers/JEPA/results/"
    "event_option_dataset_spxw_spy_qqq_zero_dte_dense15_2022_2026_v1_physics/event_option_dataset.parquet"
)
DEFAULT_RESULT = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "dense_candidate_walkforward_2026_completed_jan_may_v1"
)

EXTRA_LEAKY_TOKENS = (
    "label",
    "target",
    "realized",
    "pnl",
    "profit",
    "loss",
    "best",
)

TRADE_FILE_NAMES = (
    "combined_trades.csv",
    "monthly_volume_backfill_trades.csv",
    "nested_volume_backfill_trades.csv",
    "event_option_gate_trades.csv",
)

FOLD_FILE_NAMES = (
    "combined_folds.csv",
    "fold_configs.csv",
    "monthly_volume_backfill_config.csv",
)


def month_range(start_month: str, end_month: str) -> list[str]:
    year, month = int(start_month[:4]), int(start_month[4:6])
    end_year, end_month_i = int(end_month[:4]), int(end_month[4:6])
    out: list[str] = []
    while (year, month) <= (end_year, end_month_i):
        out.append(f"{year:04d}{month:02d}")
        month += 1
        if month == 13:
            year += 1
            month = 1
    return out


def find_existing(base: Path, names: tuple[str, ...]) -> Path | None:
    return next((base / name for name in names if (base / name).exists()), None)


def leaky_columns(columns: list[str], patterns: tuple[str, ...]) -> list[str]:
    return [col for col in columns if any(pattern in col.lower() for pattern in patterns)]


def audit_trade_file(path: Path | None, months: list[str]) -> dict[str, Any]:
    if path is None:
        return {
            "available": False,
            "passed": False,
            "issues": ["trade file missing"],
        }
    trades = pd.read_csv(path, low_memory=False, dtype={"month": str, "test_month": str})
    if "month" not in trades.columns and "test_month" in trades.columns:
        trades["month"] = trades["test_month"].astype(str)
    if "test_month" not in trades.columns and "month" in trades.columns:
        trades["test_month"] = trades["month"].astype(str)
    scoped = trades[trades["month"].astype(str).isin(months)].copy() if "month" in trades.columns else trades.iloc[0:0].copy()
    issues: list[str] = []
    expiry_modes = sorted(scoped["expiry_mode"].dropna().astype(str).unique()) if "expiry_mode" in scoped.columns else []
    if expiry_modes != ["zero_dte"]:
        issues.append(f"selected trades are not pure zero_dte: {expiry_modes!r}")
    if "realized_return" not in scoped.columns:
        issues.append("trade file missing realized_return")
    if "date" not in scoped.columns:
        issues.append("trade file missing date")
    return {
        "available": True,
        "passed": not issues,
        "path": str(path),
        "rows_in_scope": int(len(scoped)),
        "months": months,
        "expiry_modes": expiry_modes,
        "issues": issues,
    }


def audit_same_month_lineage(path: Path | None, months: list[str]) -> dict[str, Any]:
    if path is None:
        return {
            "available": False,
            "passed": False,
            "issues": ["fold file missing"],
        }
    folds = pd.read_csv(path, dtype=str)
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
        test_month = str(row.get("test_month", row.get("month", row.get("eval_month", "")))).strip()
        if not test_month or test_month not in months:
            continue
        checked += 1
        for col in month_cols:
            if col not in folds.columns:
                continue
            non_prior = [month for month in parse_month_list(row.get(col)) if month >= test_month]
            if non_prior:
                source = str(row.get("source_stream", row.get("source", ""))).strip()
                issues.append(f"row {idx} {source} {test_month}: {col} has non-prior months {non_prior}")
    return {
        "available": True,
        "passed": not issues,
        "path": str(path),
        "folds_checked": int(checked),
        "issues": issues,
    }


def write_report(path: Path, payload: dict[str, Any]) -> None:
    feature = payload["feature_audit"]
    trade = payload["trade_audit"]
    lineage = payload["lineage_audit"]
    lines = [
        "# Event Option Feature Leakage Audit",
        "",
        f"- Passed: `{payload['passed']}`",
        f"- Data: `{payload['data']}`",
        f"- Result dir: `{payload['result_dir']}`",
        f"- Months: `{', '.join(payload['months'])}`",
        "",
        "## Feature Audit",
        "",
        f"- Raw columns: `{feature['raw_column_count']}`",
        f"- Raw leaky/outcome columns present: `{feature['raw_leaky_column_count']}`",
        f"- Selected features: `{feature['selected_feature_count']}`",
        f"- Selected leaky features: `{feature['selected_leaky_feature_count']}`",
        f"- Live feature-contract issues: `{feature.get('live_contract_issue_count', 0)}`",
        "",
        "## Trade And Lineage",
        "",
        f"- Trade file pure 0DTE: `{trade['passed']}`",
        f"- Expiry modes: `{trade.get('expiry_modes', [])}`",
        f"- Fold lineage passed: `{lineage['passed']}`",
        f"- Folds checked: `{lineage.get('folds_checked', 0)}`",
        "",
        "## Issues",
        "",
    ]
    lines.extend([f"- {issue}" for issue in payload["issues"]] or ["- None."])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit event-option features and folds for leakage/lookahead.")
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--result-dir", default=str(DEFAULT_RESULT))
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202604")
    parser.add_argument("--delta-bucket", type=int, default=25)
    parser.add_argument("--clip-return", type=float, default=2.0)
    parser.add_argument("--entry-time-min-et", default="10:00")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--exit-zero-on-fail", action="store_true")
    args = parser.parse_args()

    data = Path(args.data)
    result_dir = Path(args.result_dir)
    output_dir = Path(args.output_dir) if str(args.output_dir).strip() else result_dir / "feature_leakage_audit"
    output_dir.mkdir(parents=True, exist_ok=True)
    months = month_range(str(args.start_month), str(args.end_month))

    raw = pd.read_parquet(data)
    raw_columns = list(raw.columns)
    feature_args = SimpleNamespace(
        delta_bucket=int(args.delta_bucket),
        clip_return=float(args.clip_return),
        expiry_modes=["zero_dte"],
        feature_include_prefixes=FEATURE_PREFIXES,
        feature_exclude_prefixes=[],
        live_observable_features_only=False,
        entry_time_min_et=str(args.entry_time_min_et),
    )
    frame = prepare_frame(data, feature_args)
    _, features = build_features(frame, feature_args)
    leaky_patterns = tuple(LEAKY_PATTERNS) + tuple(EXTRA_LEAKY_TOKENS)
    selected_leaky = leaky_columns(features, leaky_patterns)
    raw_leaky = leaky_columns(raw_columns, leaky_patterns)
    live_contract_issues = live_observable_feature_issues_for_columns(
        "selected_features",
        features,
        entry_start_minute_et=parse_hhmm_to_minute(str(args.entry_time_min_et)),
    )

    trade_path = find_existing(result_dir, TRADE_FILE_NAMES)
    fold_path = find_existing(result_dir, FOLD_FILE_NAMES)
    trade_audit = audit_trade_file(trade_path, months)
    lineage_audit = audit_same_month_lineage(fold_path, months)
    verifier_lineage = audit_folds(result_dir, months, disallow_weak_modes=True)

    feature_issues = [f"selected leaky feature {name}" for name in selected_leaky]
    issues = [
        *feature_issues,
        *[f"live feature contract: {issue}" for issue in live_contract_issues],
        *[f"trade audit: {issue}" for issue in trade_audit.get("issues", [])],
        *[f"lineage audit: {issue}" for issue in lineage_audit.get("issues", [])],
        *[f"verifier lineage: {issue}" for issue in verifier_lineage.get("issues", [])],
    ]
    payload = {
        "schema_version": 1,
        "audit": "event_option_feature_leakage",
        "passed": not issues,
        "data": str(data),
        "result_dir": str(result_dir),
        "months": months,
        "feature_audit": {
            "raw_column_count": int(len(raw_columns)),
            "raw_leaky_column_count": int(len(raw_leaky)),
            "raw_leaky_columns_sample": raw_leaky[:80],
            "selected_feature_count": int(len(features)),
            "selected_leaky_feature_count": int(len(selected_leaky)),
            "selected_leaky_features": selected_leaky,
            "live_contract_issue_count": int(len(live_contract_issues)),
            "live_contract_issues": live_contract_issues,
            "selected_features_sample": features[:160],
            "leaky_patterns": list(leaky_patterns),
        },
        "trade_audit": trade_audit,
        "lineage_audit": lineage_audit,
        "verifier_lineage_audit": verifier_lineage,
        "issues": issues,
    }
    (output_dir / "feature_leakage_audit.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    write_report(output_dir / "FEATURE_LEAKAGE_AUDIT.md", payload)
    print(json.dumps(payload, indent=2, allow_nan=True))
    return 0 if payload["passed"] or bool(args.exit_zero_on_fail) else 1


if __name__ == "__main__":
    raise SystemExit(main())
