from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any


DEFAULT_GUARD_DIR = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "dense_candidate_frozen2025_2026_daily_guard_l4p1_vp0"
)
DEFAULT_RECENT_SCAN = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "dense_candidate_pre2026_recent_daily_guard_selection_scan_v1.csv"
)
DEFAULT_LONG_SCAN = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "dense_candidate_pre2026_daily_guard_selection_scan_v1.csv"
)
DEFAULT_RAW_COMPLETE_VERIFICATION = DEFAULT_GUARD_DIR / "verification_raw_complete_202601_202604.json"

CONFIG_FIELDS = (
    "trigger_losses",
    "pause_days",
    "loss_threshold",
    "rolling_sum_window",
    "rolling_sum_threshold",
    "volume_protect_monthly_target",
)

PRE2026_RANK_FIELDS = (
    "valid_pass",
    "pretest_health_flag_count",
    "pretest_max_negative_day_streak",
    "valid_pf_min",
    "valid_wr_min",
    "valid_min_month_min",
    "valid_overall_pnl_return",
    "skipped_days",
    *CONFIG_FIELDS,
)


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def as_bool(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def config_key(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "trigger_losses": as_int(row.get("trigger_losses")),
        "pause_days": as_int(row.get("pause_days")),
        "loss_threshold": as_float(row.get("loss_threshold")),
        "rolling_sum_window": as_int(row.get("rolling_sum_window")),
        "rolling_sum_threshold": as_float(row.get("rolling_sum_threshold")),
        "volume_protect_monthly_target": as_int(row.get("volume_protect_monthly_target")),
    }


def rank_key(row: dict[str, str]) -> tuple[Any, ...]:
    return (
        as_int(row.get("pretest_health_flag_count"), 999),
        as_int(row.get("pretest_max_negative_day_streak"), 999),
        -as_float(row.get("valid_pf_min")),
        -as_float(row.get("valid_wr_min")),
        -as_int(row.get("valid_min_month_min")),
        -as_float(row.get("valid_overall_pnl_return")),
        as_int(row.get("skipped_days"), 999999),
        as_int(row.get("trigger_losses"), 999),
        as_int(row.get("pause_days"), 999),
        as_int(row.get("rolling_sum_window"), 999),
        as_float(row.get("rolling_sum_threshold"), 999.0),
        as_int(row.get("volume_protect_monthly_target"), 999),
    )


def rank_scan(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    candidates = [row for row in rows if as_bool(row.get("valid_pass"))]
    return sorted(candidates, key=rank_key)


def top_preview(rows: list[dict[str, str]], limit: int = 8) -> list[dict[str, Any]]:
    preview: list[dict[str, Any]] = []
    for idx, row in enumerate(rows[:limit], start=1):
        preview.append(
            {
                "rank": idx,
                **config_key(row),
                "valid_pf_min": as_float(row.get("valid_pf_min")),
                "valid_wr_min": as_float(row.get("valid_wr_min")),
                "valid_min_month_min": as_int(row.get("valid_min_month_min")),
                "pretest_health_flag_count": as_int(row.get("pretest_health_flag_count")),
                "pretest_max_negative_day_streak": as_int(row.get("pretest_max_negative_day_streak")),
                "forward_pass_diagnostic_only": as_bool(row.get("forward_pass")),
            }
        )
    return preview


def verify_no_forward_rank_fields() -> list[str]:
    return [field for field in PRE2026_RANK_FIELDS if field.startswith("forward_")]


def ticker_gate_summary(verification: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for ticker, payload in sorted((verification.get("tickers") or {}).items()):
        metrics = payload.get("metrics") or {}
        checks = payload.get("checks") or {}
        rows[str(ticker)] = {
            "passed": bool(checks.get("passed")),
            "trades": as_int(metrics.get("trades")),
            "win_rate": as_float(metrics.get("win_rate")),
            "profit_factor": as_float(metrics.get("profit_factor")),
            "min_month_trades": as_int(metrics.get("min_month_trades")),
            "pnl_return": as_float(metrics.get("pnl_return")),
        }
    return rows


def write_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Dense Candidate Pre-2026 Guard Selection Audit",
        "",
        f"- Passed: {payload['passed']}",
        f"- Guard dir: `{payload['guard_dir']}`",
        f"- Recent scan: `{payload['recent_scan']}`",
        f"- Raw-complete verification: `{payload['raw_complete_verification']}`",
        "",
        "## Checks",
        "",
        "```json",
        json.dumps(payload["checks"], indent=2, allow_nan=True),
        "```",
        "",
        "## Selected Row",
        "",
        "```json",
        json.dumps(payload["selected_row"], indent=2, allow_nan=True),
        "```",
        "",
        "## Raw-Complete Holdout",
        "",
        "```json",
        json.dumps(payload["raw_complete_holdout"], indent=2, allow_nan=True),
        "```",
        "",
        "## Top Pre-2026 Ranked Rows",
        "",
        "```json",
        json.dumps(payload["top_pre2026_ranked_rows"], indent=2, allow_nan=True),
        "```",
        "",
        "## Issues",
        "",
    ]
    lines.extend([f"- {issue}" for issue in payload["issues"]] or ["- none"])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit that the dense 2026 daily guard was selected with pre-2026 columns only."
    )
    parser.add_argument("--guard-dir", default=str(DEFAULT_GUARD_DIR))
    parser.add_argument("--recent-scan", default=str(DEFAULT_RECENT_SCAN))
    parser.add_argument("--long-scan", default=str(DEFAULT_LONG_SCAN))
    parser.add_argument("--raw-complete-verification", default=str(DEFAULT_RAW_COMPLETE_VERIFICATION))
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--exit-zero-on-failed-audit", action="store_true")
    args = parser.parse_args()

    guard_dir = Path(args.guard_dir)
    output_dir = Path(args.output_dir) if args.output_dir else guard_dir / "pre2026_guard_selection_audit"
    output_dir.mkdir(parents=True, exist_ok=True)

    recent_scan = Path(args.recent_scan)
    long_scan = Path(args.long_scan)
    raw_complete_path = Path(args.raw_complete_verification)
    metrics_path = guard_dir / "metrics.json"

    issues: list[str] = []
    if not recent_scan.exists():
        issues.append(f"missing recent scan {recent_scan}")
        recent_rows: list[dict[str, str]] = []
    else:
        recent_rows = read_csv(recent_scan)
    if not long_scan.exists():
        issues.append(f"missing long scan {long_scan}")
        long_rows: list[dict[str, str]] = []
    else:
        long_rows = read_csv(long_scan)

    ranked = rank_scan(recent_rows)
    selected = ranked[0] if ranked else {}
    selected_config = config_key(selected) if selected else {}
    target_config = {
        "trigger_losses": 4,
        "pause_days": 1,
        "loss_threshold": 0.0,
        "rolling_sum_window": 0,
        "rolling_sum_threshold": 0.0,
        "volume_protect_monthly_target": 0,
    }

    if selected_config != target_config:
        issues.append(f"pre-2026 rank-1 guard config {selected_config} != expected {target_config}")

    forbidden_rank_fields = verify_no_forward_rank_fields()
    if forbidden_rank_fields:
        issues.append(f"rank fields include forward columns: {forbidden_rank_fields}")

    if metrics_path.exists():
        metrics_payload = read_json(metrics_path)
        artifact_config = config_key(metrics_payload.get("config") or {})
        source_result_dir = str((metrics_payload.get("config") or {}).get("result_dir", ""))
    else:
        metrics_payload = {}
        artifact_config = {}
        source_result_dir = ""
        issues.append(f"missing guard metrics {metrics_path}")

    if artifact_config != target_config:
        issues.append(f"guard artifact config {artifact_config} != expected {target_config}")

    if raw_complete_path.exists():
        verification = read_json(raw_complete_path)
    else:
        verification = {}
        issues.append(f"missing raw-complete verification {raw_complete_path}")

    raw_tickers = ticker_gate_summary(verification)
    raw_passed = bool(verification.get("passed"))
    integrity_passed = bool((verification.get("integrity") or {}).get("passed"))
    backfill_passed = bool((verification.get("backfill") or {}).get("passed"))
    if not raw_passed:
        issues.append("raw-complete 202601..202604 verification did not pass")
    if not integrity_passed:
        issues.append("raw-complete fold integrity did not pass")
    if not backfill_passed:
        issues.append("raw-complete backfill audit did not pass")

    long_valid_pass_rows = sum(1 for row in long_rows if as_bool(row.get("valid_pass")))
    payload = {
        "schema_version": 1,
        "audit": "dense_candidate_pre2026_guard_selection",
        "passed": not issues,
        "guard_dir": str(guard_dir),
        "source_result_dir": source_result_dir,
        "recent_scan": str(recent_scan),
        "long_scan": str(long_scan),
        "raw_complete_verification": str(raw_complete_path),
        "checks": {
            "recent_scan_exists": recent_scan.exists(),
            "long_scan_exists": long_scan.exists(),
            "rank_fields_are_pre2026_only": not forbidden_rank_fields,
            "recent_valid_pass_rows": len(ranked),
            "long_valid_pass_rows": long_valid_pass_rows,
            "selected_config_matches_rank1": selected_config == target_config,
            "artifact_config_matches_selected": artifact_config == target_config,
            "raw_complete_holdout_passed": raw_passed,
            "raw_complete_integrity_passed": integrity_passed,
            "raw_complete_backfill_passed": backfill_passed,
        },
        "selection_windows": {
            "recent_select": "202407..202412",
            "recent_validation": "202501..202512",
            "recent_forward_columns": "diagnostic only, not used by rank_key",
            "long_select": "202301..202406",
            "long_validation": "202407..202512",
        },
        "rank_fields": list(PRE2026_RANK_FIELDS),
        "selected_row": {
            "rank": 1 if selected else None,
            **selected_config,
            "valid_pass": as_bool(selected.get("valid_pass")) if selected else False,
            "valid_pf_min": as_float(selected.get("valid_pf_min")) if selected else 0.0,
            "valid_wr_min": as_float(selected.get("valid_wr_min")) if selected else 0.0,
            "valid_min_month_min": as_int(selected.get("valid_min_month_min")) if selected else 0,
            "pretest_health_flag_count": as_int(selected.get("pretest_health_flag_count")) if selected else 0,
            "pretest_max_negative_day_streak": as_int(selected.get("pretest_max_negative_day_streak")) if selected else 0,
            "forward_pass_diagnostic_only": as_bool(selected.get("forward_pass")) if selected else False,
        },
        "raw_complete_holdout": {
            "passed": raw_passed,
            "months": (verification.get("gates") or {}).get("months", []),
            "tickers": raw_tickers,
            "integrity": verification.get("integrity", {}),
            "backfill": verification.get("backfill", {}),
        },
        "top_pre2026_ranked_rows": top_preview(ranked),
        "issues": issues,
    }

    (output_dir / "pre2026_guard_selection_audit.json").write_text(
        json.dumps(payload, indent=2, allow_nan=True),
        encoding="utf-8",
    )
    write_report(output_dir / "PRE2026_GUARD_SELECTION_AUDIT.md", payload)
    print(json.dumps(payload, indent=2, allow_nan=True))
    if args.exit_zero_on_failed_audit:
        return 0
    return 0 if payload["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
