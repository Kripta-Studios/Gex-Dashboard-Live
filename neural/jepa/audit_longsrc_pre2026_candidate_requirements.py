from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_RESULT_DIR = Path(
    "research_papers/JEPA/results/"
    "event_static_union_longsrc_2024h2select_objpass_simpler_spy_daily_guard_l5p2_risk5000_v1"
)
DEFAULT_SCAN_SUMMARY = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "scan_existing_results_pre2026_select_2025_eval_202601_202604/summary.json"
)
DEFAULT_SCAN_RESULTS = DEFAULT_SCAN_SUMMARY.with_name("scan_results.csv")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def month_range(start: str, end: str) -> list[str]:
    start_i = int(start)
    end_i = int(end)
    months: list[str] = []
    year = start_i // 100
    month = start_i % 100
    while True:
        item = f"{year:04d}{month:02d}"
        months.append(item)
        if int(item) >= end_i:
            break
        month += 1
        if month == 13:
            year += 1
            month = 1
    return months


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def verify_holdout(
    verification: dict[str, Any],
    expected_months: list[str],
    tickers: list[str],
    min_win_rate: float,
    min_profit_factor: float,
    min_month_trades: int,
) -> dict[str, Any]:
    gates = verification.get("gates") if isinstance(verification.get("gates"), dict) else {}
    months = [str(month) for month in gates.get("months", [])]
    integrity = verification.get("integrity") if isinstance(verification.get("integrity"), dict) else {}
    backfill = verification.get("backfill") if isinstance(verification.get("backfill"), dict) else {}
    ticker_payload = verification.get("tickers") if isinstance(verification.get("tickers"), dict) else {}

    issues: list[str] = []
    if not bool(verification.get("passed")):
        issues.append("verification passed=false")
    if months != expected_months:
        issues.append(f"verification months {months} != expected {expected_months}")
    if not bool(integrity.get("passed")):
        issues.append("fold integrity failed")
    if not bool(backfill.get("passed")):
        issues.append("backfill audit failed")

    by_ticker: dict[str, Any] = {}
    for ticker in tickers:
        item = ticker_payload.get(ticker)
        if not isinstance(item, dict):
            by_ticker[ticker] = {"passed": False, "issues": ["missing ticker"]}
            issues.append(f"{ticker}: missing ticker block")
            continue
        metrics = item.get("metrics") if isinstance(item.get("metrics"), dict) else {}
        monthly = item.get("monthly") if isinstance(item.get("monthly"), dict) else {}
        checks = item.get("checks") if isinstance(item.get("checks"), dict) else {}
        ticker_issues: list[str] = []
        if not bool(checks.get("passed")):
            ticker_issues.append("ticker checks passed=false")
        if safe_float(metrics.get("win_rate")) < min_win_rate:
            ticker_issues.append("win_rate below gate")
        if safe_float(metrics.get("profit_factor")) < min_profit_factor:
            ticker_issues.append("profit_factor below gate")
        if safe_int(metrics.get("min_month_trades")) < min_month_trades:
            ticker_issues.append("min_month_trades below gate")
        missing_months = [month for month in expected_months if month not in monthly]
        if missing_months:
            ticker_issues.append(f"missing monthly rows {missing_months}")
        negative_months = [
            month
            for month, row in monthly.items()
            if isinstance(row, dict) and safe_float(row.get("pnl_return")) <= 0.0
        ]
        by_ticker[ticker] = {
            "passed": not ticker_issues,
            "metrics": metrics,
            "negative_months": negative_months,
            "issues": ticker_issues,
        }
        issues.extend(f"{ticker}: {issue}" for issue in ticker_issues)

    return {
        "passed": not issues,
        "months": months,
        "tickers": by_ticker,
        "folds_checked": safe_int(integrity.get("folds_checked")),
        "backfill_rows_checked": safe_int(backfill.get("rows_checked")),
        "issues": issues,
    }


def audit_research_selection(
    audit: dict[str, Any],
    manifest: dict[str, Any],
    scan_summary: dict[str, Any],
    result_dir: Path,
) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    if not bool(audit.get("passed")):
        issues.append("strict research-selection audit did not pass")
    if not bool(audit.get("strict")):
        issues.append("research-selection audit was not strict")
    if not bool(audit.get("manifest_present")):
        issues.append("research-selection manifest missing")
    if str(manifest.get("frozen_before_month", "")) != "202601":
        issues.append("manifest is not frozen before 202601")
    if not bool(manifest.get("selection_scan_rank_fields_are_pre2026_only")):
        issues.append("manifest rank fields are not marked pre-2026-only")
    if not bool(scan_summary.get("rank_fields_are_pre2026_only")):
        issues.append("scan rank fields are not pre-2026-only")

    selected = scan_summary.get("top_lineage_clean_holdout")
    selected_dir = str((selected or {}).get("dir", "")) if isinstance(selected, dict) else ""
    if not selected_dir:
        issues.append("scan summary does not expose top_lineage_clean_holdout")
    elif Path(selected_dir).as_posix() != result_dir.as_posix():
        issues.append(f"scan selected {selected_dir}, not {result_dir}")

    if isinstance(selected, dict) and not bool(selected.get("test_pass_with_lineage")):
        issues.append("scan top lineage-clean holdout does not pass test lineage")

    caveat = str(manifest.get("source_universe_caveat", "")).strip()
    source_universe_timestamp_proof = False
    if not caveat:
        warnings.append("manifest has no explicit source-universe timestamp caveat")

    return {
        "passed": not issues,
        "strict_audit_passed": bool(audit.get("passed")) and bool(audit.get("strict")),
        "manifest_frozen_before_month": manifest.get("frozen_before_month"),
        "scan_rank_fields_are_pre2026_only": bool(scan_summary.get("rank_fields_are_pre2026_only")),
        "selected_branch_is_top_lineage_clean": bool(not issues and selected_dir),
        "source_universe_timestamp_proof": source_universe_timestamp_proof,
        "source_universe_caveat": caveat,
        "selection_scan_counts": manifest.get("selection_scan_counts", {}),
        "issues": issues,
        "warnings": warnings,
    }


def scan_rank(scan_results_path: Path, result_dir: Path) -> dict[str, Any]:
    if not scan_results_path.exists():
        return {"available": False, "rank": None, "issues": [f"missing {scan_results_path}"]}
    target = result_dir.as_posix()
    rows: list[dict[str, str]] = []
    with scan_results_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(row)
    for idx, row in enumerate(rows, start=1):
        if Path(str(row.get("dir", ""))).as_posix() == target:
            return {
                "available": True,
                "rank_by_scan_file_order": idx,
                "select_score": safe_float(row.get("select_score")),
                "eligible_pre2026_selection": str(row.get("eligible_pre2026_selection", "")).lower() == "true",
                "test_pass_with_lineage": str(row.get("test_pass_with_lineage", "")).lower() == "true",
                "issues": [],
            }
    return {"available": True, "rank": None, "issues": [f"{result_dir} not found in scan results"]}


def demoted_high_metric_rows(scan_summary: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    rows = scan_summary.get("top_rows")
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if bool(row.get("test_pass")) and not bool(row.get("fold_2026_ok")):
            out.append(
                {
                    "name": row.get("name"),
                    "select_score": row.get("select_score"),
                    "test_wr_min": row.get("test_wr_min"),
                    "test_pf_min": row.get("test_pf_min"),
                    "fold_2026_issues": row.get("fold_2026_issues"),
                }
            )
        if len(out) >= limit:
            break
    return out


def curve_review(curve: dict[str, Any], expected_months: list[str]) -> dict[str, Any]:
    gates = curve.get("gates") if isinstance(curve.get("gates"), dict) else {}
    months = [str(month) for month in gates.get("months", [])]
    tickers = curve.get("tickers") if isinstance(curve.get("tickers"), dict) else {}
    issues: list[str] = []
    if months != expected_months:
        issues.append(f"curve months {months} != expected {expected_months}")
    flagged = {
        ticker: list((row or {}).get("health_flags", []))
        for ticker, row in tickers.items()
        if isinstance(row, dict) and (row or {}).get("health_flags")
    }
    if flagged:
        issues.append(f"curve-health flags present: {flagged}")
    if not bool(curve.get("passed")):
        issues.append("curve_health passed=false")
    return {
        "passed": not issues,
        "months": months,
        "flagged_tickers": flagged,
        "ticker_summaries": {
            ticker: {
                "daily_profit_factor": (row or {}).get("daily_profit_factor"),
                "active_day_win_rate": (row or {}).get("daily_win_rate_active_days"),
                "max_drawdown_to_pnl": (row or {}).get("max_drawdown_to_pnl"),
                "negative_months": (row or {}).get("negative_months"),
                "max_negative_day_streak": (row or {}).get("max_negative_day_streak"),
                "max_month_pnl_share": (row or {}).get("max_month_pnl_share"),
                "health_flags": (row or {}).get("health_flags", []),
            }
            for ticker, row in tickers.items()
            if isinstance(row, dict)
        },
        "issues": issues,
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Longsrc Pre-2026 Requirement Audit",
        "",
        f"- Walk-forward metrics and fold integrity passed: {payload['walkforward_metric_and_integrity_passed']}",
        f"- Strict anti-leakage reconstruction passed: {payload['anti_leakage_reconstruction_passed']}",
        f"- Overfit/robustness review passed: {payload['overfit_risk_review_passed']}",
        f"- Production ready passed: {payload['production_ready_passed']}",
        f"- Result dir: `{payload['result_dir']}`",
        "",
        "## Holdout Metrics",
        "",
        "| Ticker | Passed | Trades | WR | PF | PnL Return | Min Trades/Month | Negative Months |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for ticker, row in payload["holdout_verification"]["tickers"].items():
        metrics = row.get("metrics", {})
        negative = ", ".join(row.get("negative_months", [])) or "none"
        lines.append(
            f"| {ticker} | {row.get('passed')} | {safe_int(metrics.get('trades'))} | "
            f"{safe_float(metrics.get('win_rate')):.2%} | {safe_float(metrics.get('profit_factor')):.3f} | "
            f"{safe_float(metrics.get('pnl_return')):.3f} | {safe_int(metrics.get('min_month_trades'))} | "
            f"{negative} |"
        )
    lines += [
        "",
        "## Objective Checks",
        "",
        "```json",
        json.dumps(payload["objective_checks"], indent=2, allow_nan=True),
        "```",
        "",
        "## Leakage And Snooping Notes",
        "",
    ]
    for item in payload["bias_review_notes"]:
        lines.append(f"- {item}")
    lines += [
        "",
        "## Demoted High-Metric Candidates",
        "",
        "These rows had stronger-looking metrics but were not accepted because their 2026 fold lineage was not clean.",
        "",
        "| Name | Select Score | Test WR Min | Test PF Min | Fold Issue Summary |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for row in payload["demoted_high_metric_candidates"]:
        issue = str(row.get("fold_2026_issues", "")).replace("|", "/")
        if len(issue) > 180:
            issue = issue[:177] + "..."
        lines.append(
            f"| {row.get('name')} | {safe_float(row.get('select_score')):.3f} | "
            f"{safe_float(row.get('test_wr_min')):.2%} | {safe_float(row.get('test_pf_min')):.3f} | {issue} |"
        )
    lines += [
        "",
        "## Remaining Gaps",
        "",
    ]
    for item in payload["remaining_gaps"]:
        lines.append(f"- {item}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit the longsrc pre-2026-selected event-option candidate for leakage and overfit risk."
    )
    parser.add_argument("--result-dir", default=str(DEFAULT_RESULT_DIR))
    parser.add_argument("--scan-summary", default=str(DEFAULT_SCAN_SUMMARY))
    parser.add_argument("--scan-results", default=str(DEFAULT_SCAN_RESULTS))
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202604")
    parser.add_argument("--min-win-rate", type=float, default=0.45)
    parser.add_argument("--min-profit-factor", type=float, default=1.30)
    parser.add_argument("--min-month-trades", type=int, default=18)
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--output-dir", default="")
    parser.add_argument(
        "--exit-zero-on-fail",
        action="store_true",
        help="Write the audit artifact but return 0 even when production readiness is false.",
    )
    args = parser.parse_args()

    result_dir = Path(args.result_dir)
    expected_months = month_range(str(args.start_month), str(args.end_month))
    output_dir = Path(args.output_dir) if args.output_dir else result_dir / "requirement_audit_pre2026_longsrc"
    output_dir.mkdir(parents=True, exist_ok=True)

    verification = read_json(result_dir / "verification_raw_complete_202601_202604.json")
    research_audit = read_json(result_dir / "research_selection_audit_strict_raw_complete_202601_202604" / "research_selection_audit.json")
    manifest = read_json(result_dir / "research_selection_manifest.json")
    scan_summary = read_json(Path(args.scan_summary))
    curve = read_json(result_dir / "curve_health" / "curve_health.json")

    holdout = verify_holdout(
        verification=verification,
        expected_months=expected_months,
        tickers=[str(item).upper() for item in args.tickers],
        min_win_rate=float(args.min_win_rate),
        min_profit_factor=float(args.min_profit_factor),
        min_month_trades=int(args.min_month_trades),
    )
    selection = audit_research_selection(research_audit, manifest, scan_summary, result_dir)
    rank = scan_rank(Path(args.scan_results), result_dir)
    curve_result = curve_review(curve, expected_months)

    walkforward_metric_and_integrity_passed = bool(holdout["passed"])
    anti_leakage_reconstruction_passed = bool(selection["passed"])
    source_universe_timestamp_proof = bool(selection["source_universe_timestamp_proof"])
    overfit_risk_review_passed = bool(
        walkforward_metric_and_integrity_passed
        and anti_leakage_reconstruction_passed
        and source_universe_timestamp_proof
        and curve_result["passed"]
    )
    production_ready_passed = False

    objective_checks = {
        "raw_complete_walkforward_metric_gates": walkforward_metric_and_integrity_passed,
        "fold_integrity_and_backfill": bool(
            holdout["folds_checked"] > 0 and holdout["backfill_rows_checked"] == 0 and not holdout["issues"]
        ),
        "strict_research_selection_audit": bool(selection["strict_audit_passed"]),
        "pre2026_selection_scan_rank_fields": bool(selection["scan_rank_fields_are_pre2026_only"]),
        "selected_branch_is_top_lineage_clean": bool(selection["selected_branch_is_top_lineage_clean"]),
        "source_universe_timestamp_proof": source_universe_timestamp_proof,
        "curve_health": bool(curve_result["passed"]),
        "future_post_freeze_completed_month": False,
        "production_artifacts_for_this_branch": False,
    }

    bias_review_notes = [
        "The previously higher WR/PF dense candidates are not accepted as evidence because their 2026 folds contain post-202512 validation months.",
        "The accepted longsrc branch is selected by a reconstructed scan whose rank fields are pre-2026 only.",
        "The strict research-selection audit and fold integrity audit pass for 202601-202604.",
        "The manifest explicitly lacks timestamp proof that the full result-directory universe was frozen before 2026.",
        "Curve-health is not clean: aggregate WR/PF pass, but QQQ/SPY show negative months or short-horizon concentration.",
    ]

    remaining_gaps = []
    if not source_universe_timestamp_proof:
        remaining_gaps.append(
            "No timestamp proof that the full research-result universe was frozen before 2026; current evidence is a retrospective reconstruction."
        )
    if not curve_result["passed"]:
        remaining_gaps.append("Curve-health failed: " + "; ".join(curve_result["issues"]))
    remaining_gaps.append("No official completed post-freeze month has been observed for this branch.")
    remaining_gaps.append("This branch is not packaged as the live production policy/artifact set.")

    payload = {
        "schema_version": 1,
        "audit": "longsrc_pre2026_candidate_requirements",
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "result_dir": str(result_dir),
        "months": expected_months,
        "walkforward_metric_and_integrity_passed": walkforward_metric_and_integrity_passed,
        "anti_leakage_reconstruction_passed": anti_leakage_reconstruction_passed,
        "overfit_risk_review_passed": overfit_risk_review_passed,
        "production_ready_passed": production_ready_passed,
        "objective_checks": objective_checks,
        "holdout_verification": holdout,
        "research_selection": selection,
        "scan_rank": rank,
        "curve_health": curve_result,
        "demoted_high_metric_candidates": demoted_high_metric_rows(scan_summary),
        "bias_review_notes": bias_review_notes,
        "remaining_gaps": remaining_gaps,
    }

    (output_dir / "requirement_audit.json").write_text(
        json.dumps(payload, indent=2, allow_nan=True),
        encoding="utf-8",
    )
    write_markdown(output_dir / "REQUIREMENT_AUDIT.md", payload)
    print(json.dumps(payload, indent=2, allow_nan=True))
    if bool(args.exit_zero_on_fail):
        return 0
    return 0 if production_ready_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
