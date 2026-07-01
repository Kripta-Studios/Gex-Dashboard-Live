from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_RESULT = Path(
    "research_papers/JEPA/results/"
    "event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_causal_2023_2026_v1"
)
DEFAULT_REGISTRY = Path("neural/models/jepa/jepa_production_event_options_dense15_strict_uniform_candidate/component_registry.json")
DEFAULT_POLICY = Path("neural/models/jepa/jepa_production_event_options_dense15_strict_uniform_candidate/event_option_policy.json")
DEFAULT_FREEZE = Path(
    "research_papers/JEPA/results/"
    "event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_forward_freeze_202607_v1/"
    "research_selection_manifest.json"
)
DEFAULT_FORWARD_EVALUATION = Path(
    "research_papers/JEPA/results/"
    "event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_forward_evaluation_202607_pending_v1/"
    "forward_freeze_evaluation.json"
)
DEFAULT_COMPLETED_2026_WALKFORWARD = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "dense_candidate_walkforward_2026_completed_jan_may_v1/verification.json"
)
DEFAULT_RAW_COMPLETE_2026_WALKFORWARD = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "dense_candidate_walkforward_2026_completed_jan_may_v1/verification_raw_complete_202601_202604.json"
)
DEFAULT_BROAD_RAW_COMPLETE_WALKFORWARD = (
    DEFAULT_RESULT / "verification_raw_complete_202301_202604.json"
)
DEFAULT_FROZEN_2025_TO_2026 = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "dense_candidate_frozen_through_202512_eval_202601_202605_v1/verification.json"
)
DEFAULT_RAW_COMPLETE_FROZEN_2025_TO_2026 = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "dense_candidate_frozen_through_202512_eval_202601_202605_v1/verification_raw_complete_202601_202604.json"
)
DEFAULT_GUARDED_FROZEN_2025_TO_2026 = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "dense_candidate_frozen2025_2026_daily_guard_l4p1_vp0/verification.json"
)
DEFAULT_GUARDED_FROZEN_2025_TO_2026_CURVE = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "dense_candidate_frozen2025_2026_daily_guard_l4p1_vp0/curve_health/curve_health.json"
)
DEFAULT_GUARDED_RAW_COMPLETE_2026 = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "dense_candidate_frozen2025_2026_daily_guard_l4p1_vp0/verification_raw_complete_202601_202604.json"
)
DEFAULT_GUARDED_RAW_COMPLETE_2026_CURVE = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "dense_candidate_frozen2025_2026_daily_guard_l4p1_vp0/curve_health/curve_health.json"
)
DEFAULT_GUARDED_STRICT_RESEARCH_SELECTION_AUDIT = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "dense_candidate_frozen2025_2026_daily_guard_l4p1_vp0/research_selection_audit_strict/research_selection_audit.json"
)
DEFAULT_GUARDED_ANTI_SNOOPING_AUDIT = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "dense_candidate_frozen2025_2026_daily_guard_l4p1_vp0/anti_snooping_audit/anti_snooping_audit.json"
)
DEFAULT_GUARDED_STATISTICAL_ROBUSTNESS = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "dense_candidate_frozen2025_2026_daily_guard_l4p1_vp0/statistical_robustness/statistical_robustness.json"
)
DEFAULT_FIXED_HOLDOUT_MAY = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "dense_candidate_fixed_holdout_select_through_202604_eval_202605_completed_v1/verification.json"
)
DEFAULT_PARTIAL_JUNE_DIAGNOSTIC = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "dense_candidate_partial_20260601_20260626_eval_v1/partial_evaluation.json"
)
DEFAULT_PAPER_ORDER_VALIDATION = DEFAULT_RESULT / "paper_order_validation" / "paper_order_validation.json"
DEFAULT_BOT_DAILY_LOSS_GUARD_VALIDATION = (
    DEFAULT_RESULT / "bot_event_daily_loss_guard_validation" / "bot_event_daily_loss_guard_validation.json"
)
DEFAULT_BROKER_ORDER_CONTRACT_VALIDATION = (
    DEFAULT_RESULT / "broker_order_contract_validation" / "broker_order_contract_validation.json"
)
DEFAULT_TRADE_RAW_COVERAGE_VALIDATION = (
    DEFAULT_RESULT / "trade_raw_coverage_validation" / "trade_raw_coverage_validation.json"
)
DEFAULT_BROKER_FILL_VALIDATION = (
    DEFAULT_RESULT / "broker_fill_validation" / "broker_fill_validation.json"
)
DEFAULT_RAW_THETADATA_COVERAGE = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "thetadata_0dte_raw_coverage_spxw_spy_qqq/raw_coverage.json"
)
DEFAULT_ANTI_SNOOPING_AUDIT = DEFAULT_RESULT / "anti_snooping_audit" / "anti_snooping_audit.json"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def parse_month_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, float) and math.isnan(value):
        return []
    text = str(value).strip().replace('"', "")
    if not text or text.lower() == "nan":
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def audit_fold_temporal_integrity(folds_path: Path, start_month: str, end_month: str) -> dict[str, Any]:
    if not folds_path.exists():
        return {"passed": False, "folds_checked": 0, "issues": [f"missing {folds_path}"]}
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
        test_month = str(row.get("test_month", row.get("month", ""))).strip()
        if not test_month:
            continue
        if start_month <= test_month <= end_month:
            checked += 1
        for col in month_cols:
            if col not in folds.columns:
                continue
            bad = [month for month in parse_month_list(row.get(col)) if month >= test_month]
            if bad:
                issues.append(f"row {idx} test_month={test_month} {col} has non-prior months {bad}")
                if len(issues) >= 25:
                    break
        if len(issues) >= 25:
            break
    return {"passed": bool(checked > 0 and not issues), "folds_checked": int(checked), "issues": issues}


def audit_frozen_walkforward_lineage(
    folds_path: Path,
    expected_months: list[str],
    max_evidence_month: str,
) -> dict[str, Any]:
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
    expected_set = {str(month) for month in expected_months}
    issues: list[str] = []
    checked = 0
    seen_months: set[str] = set()
    evidence_months: set[str] = set()
    for idx, row in folds.iterrows():
        test_month = str(row.get("test_month", row.get("month", ""))).strip()
        if not test_month or test_month not in expected_set:
            continue
        checked += 1
        seen_months.add(test_month)
        deploy_month = str(row.get("deploy_month", "")).strip()
        if deploy_month and deploy_month > min(expected_set):
            issues.append(f"row {idx} deploy_month={deploy_month} is after first expected month {min(expected_set)}")
        select_end = str(row.get("select_end_month", "")).strip()
        if select_end and select_end > str(max_evidence_month):
            issues.append(f"row {idx} select_end_month={select_end} > max_evidence_month {max_evidence_month}")
        for col in month_cols:
            if col not in folds.columns:
                continue
            months = parse_month_list(row.get(col))
            evidence_months.update(months)
            non_prior = [month for month in months if month >= test_month]
            after_cutoff = [month for month in months if month > str(max_evidence_month)]
            if non_prior:
                issues.append(f"row {idx} test_month={test_month} {col} has non-prior months {non_prior}")
            if after_cutoff:
                issues.append(f"row {idx} test_month={test_month} {col} has months after {max_evidence_month}: {after_cutoff}")
        if len(issues) >= 50:
            break
    missing_months = sorted(expected_set.difference(seen_months))
    if missing_months:
        issues.append(f"missing fold rows for expected test months {missing_months}")
    return {
        "passed": bool(checked > 0 and not issues),
        "path": str(folds_path),
        "folds_checked": int(checked),
        "expected_months": sorted(expected_set),
        "seen_months": sorted(seen_months),
        "max_evidence_month": str(max_evidence_month),
        "max_observed_evidence_month": max(evidence_months) if evidence_months else None,
        "issues": issues,
    }


def gate_check(value: float, threshold: float, op: str) -> bool:
    if op == ">=":
        return bool(value >= threshold)
    if op == ">":
        return bool(value > threshold)
    raise ValueError(op)


def audit_metric_gates(metrics: dict[str, Any], tickers: list[str], args: argparse.Namespace) -> dict[str, Any]:
    by_ticker = metrics.get("by_ticker", {})
    out: dict[str, Any] = {}
    for ticker in tickers:
        row = by_ticker.get(ticker)
        if not isinstance(row, dict):
            out[ticker] = {"passed": False, "issues": ["missing ticker metrics"]}
            continue
        checks = {
            "win_rate": {
                "value": float(row.get("win_rate", 0.0)),
                "threshold": float(args.min_win_rate),
                "passed": gate_check(float(row.get("win_rate", 0.0)), float(args.min_win_rate), ">="),
            },
            "profit_factor": {
                "value": float(row.get("profit_factor", 0.0)),
                "threshold": float(args.min_profit_factor),
                "passed": gate_check(float(row.get("profit_factor", 0.0)), float(args.min_profit_factor), ">="),
            },
            "min_month_trades": {
                "value": int(row.get("min_month_trades", 0)),
                "threshold": int(args.min_month_trades),
                "passed": int(row.get("min_month_trades", 0)) >= int(args.min_month_trades),
            },
            "call_rate_floor": {
                "value": float(row.get("call_rate", 0.0)),
                "threshold": float(args.min_call_rate),
                "passed": float(row.get("call_rate", 0.0)) >= float(args.min_call_rate),
            },
            "call_rate_ceiling": {
                "value": float(row.get("call_rate", 0.0)),
                "threshold": float(args.max_call_rate),
                "passed": float(row.get("call_rate", 0.0)) <= float(args.max_call_rate),
            },
            "pnl_positive": {
                "value": float(row.get("pnl_return", 0.0)),
                "threshold": 0.0,
                "passed": float(row.get("pnl_return", 0.0)) > 0.0,
            },
        }
        out[ticker] = {
            "passed": bool(all(item["passed"] for item in checks.values())),
            "metrics": row,
            "checks": checks,
        }
    return out


def audit_zero_dte(trades_path: Path) -> dict[str, Any]:
    if not trades_path.exists():
        return {"passed": False, "issues": [f"missing {trades_path}"]}
    trades = pd.read_csv(trades_path, usecols=lambda col: col in {"expiry_mode", "ticker"}, low_memory=False)
    if "expiry_mode" not in trades.columns:
        return {"passed": False, "issues": ["combined_trades.csv missing expiry_mode"]}
    modes = sorted(trades["expiry_mode"].astype(str).unique().tolist())
    return {
        "passed": bool(modes == ["zero_dte"]),
        "rows": int(len(trades)),
        "expiry_modes": modes,
        "tickers": sorted(trades["ticker"].astype(str).str.upper().unique().tolist()) if "ticker" in trades.columns else [],
    }


def audit_registry_artifacts(registry: dict[str, Any]) -> dict[str, Any]:
    components = registry.get("available_components", {})
    issues: list[str] = []
    checked = 0
    if not isinstance(components, dict) or not components:
        return {"passed": False, "components_checked": 0, "issues": ["available_components missing"]}
    for name, entry in components.items():
        if not isinstance(entry, dict):
            issues.append(f"{name}: entry is not an object")
            continue
        for key in ["path", "metadata"]:
            raw = str(entry.get(key, "")).strip()
            if not raw:
                issues.append(f"{name}: missing {key}")
                continue
            path = Path(raw)
            if not path.is_absolute():
                path = Path.cwd() / path
            if not path.exists():
                issues.append(f"{name}: missing {key} artifact {raw}")
        checked += 1
    return {"passed": not issues, "components_checked": int(checked), "issues": issues[:25]}


def audit_forward_evaluation(path: Path, freeze_month: str) -> dict[str, Any]:
    if not path.exists():
        return {
            "passed": False,
            "path": str(path),
            "issues": [f"missing {path}"],
        }
    payload = read_json(path)
    months = [str(month) for month in payload.get("months", [])]
    selected_partial = [str(month) for month in payload.get("selected_partial_months", [])]
    gate_result = payload.get("gate_result") if isinstance(payload.get("gate_result"), dict) else {}
    raw_coverage = payload.get("raw_thetadata_coverage") if isinstance(payload.get("raw_thetadata_coverage"), dict) else {}
    issues: list[str] = []
    if payload.get("status") != "evaluated":
        issues.append(f"status={payload.get('status')}")
    if not bool(payload.get("official_forward_mode")):
        issues.append("official_forward_mode is false")
    if bool(payload.get("diagnostic_pre_freeze")):
        issues.append("diagnostic_pre_freeze is true")
    if bool(payload.get("diagnostic_partial_forward")) or selected_partial:
        issues.append("partial forward months were included")
    if not months:
        issues.append("no evaluated months")
    bad_months = [month for month in months if month < str(freeze_month)]
    if bad_months:
        issues.append(f"months before freeze {freeze_month}: {bad_months}")
    if not bool(gate_result.get("passed")):
        issues.append("forward gate_result did not pass")
    raw_completed_missing = [
        str(month)
        for month in raw_coverage.get("completed_months_missing_from_event_dataset", [])
        if str(month) >= str(freeze_month)
    ]
    if raw_completed_missing:
        issues.append(f"raw completed months missing from event dataset: {raw_completed_missing}")
    return {
        "passed": not issues,
        "path": str(path),
        "status": payload.get("status"),
        "official_forward_mode": bool(payload.get("official_forward_mode")),
        "diagnostic_pre_freeze": bool(payload.get("diagnostic_pre_freeze")),
        "diagnostic_partial_forward": bool(payload.get("diagnostic_partial_forward")),
        "months": months,
        "selected_partial_months": selected_partial,
        "completed_months_at_or_after_start": payload.get("completed_months_at_or_after_start", []),
        "partial_months_at_or_after_start": payload.get("partial_months_at_or_after_start", []),
        "data_latest_available_date": payload.get("data_latest_available_date"),
        "raw_thetadata_coverage": raw_coverage,
        "gate_result_passed": bool(gate_result.get("passed")),
        "issues": issues,
    }


def audit_verification_artifact(path: Path, expected_months: list[str]) -> dict[str, Any]:
    if not path.exists():
        return {
            "passed": False,
            "path": str(path),
            "months": [],
            "issues": [f"missing {path}"],
        }
    payload = read_json(path)
    gates = payload.get("gates") if isinstance(payload.get("gates"), dict) else {}
    months = [str(month) for month in gates.get("months", [])]
    integrity = payload.get("integrity") if isinstance(payload.get("integrity"), dict) else {}
    backfill = payload.get("backfill") if isinstance(payload.get("backfill"), dict) else {}
    tickers = payload.get("tickers") if isinstance(payload.get("tickers"), dict) else {}
    issues: list[str] = []
    if not bool(payload.get("passed")):
        issues.append("verification passed=false")
    if months != [str(month) for month in expected_months]:
        issues.append(f"months {months} != expected {expected_months}")
    if not bool(integrity.get("passed")):
        issues.append("fold integrity failed")
    if not bool(backfill.get("passed")):
        issues.append("backfill audit failed")
    failed_tickers = [ticker for ticker, item in tickers.items() if not bool((item or {}).get("checks", {}).get("passed"))]
    if failed_tickers:
        issues.append(f"ticker gates failed: {failed_tickers}")
    return {
        "passed": not issues,
        "path": str(path),
        "months": months,
        "tickers": {
            ticker: {
                "passed": bool((item or {}).get("checks", {}).get("passed")),
                "metrics": (item or {}).get("metrics", {}),
            }
            for ticker, item in tickers.items()
        },
        "folds_checked": int(integrity.get("folds_checked", 0) or 0),
        "backfill_rows_checked": int(backfill.get("rows_checked", 0) or 0),
        "issues": issues,
    }


def audit_curve_health_artifact(path: Path, expected_months: list[str]) -> dict[str, Any]:
    if not path.exists():
        return {
            "passed": False,
            "path": str(path),
            "months": [],
            "issues": [f"missing {path}"],
        }
    payload = read_json(path)
    gates = payload.get("gates") if isinstance(payload.get("gates"), dict) else {}
    months = [str(month) for month in gates.get("months", [])]
    tickers = payload.get("tickers") if isinstance(payload.get("tickers"), dict) else {}
    issues: list[str] = []
    if months != [str(month) for month in expected_months]:
        issues.append(f"months {months} != expected {expected_months}")
    if not bool(payload.get("passed")):
        issues.append("curve-health passed=false")
    flagged = {
        ticker: (item or {}).get("health_flags", [])
        for ticker, item in tickers.items()
        if (item or {}).get("health_flags", [])
    }
    if flagged:
        issues.append(f"ticker curve-health flags present: {flagged}")
    return {
        "passed": not issues,
        "path": str(path),
        "months": months,
        "tickers": {
            ticker: {
                "health_flags": (item or {}).get("health_flags", []),
                "negative_months": int((item or {}).get("negative_months", 0) or 0),
                "max_negative_day_streak": int((item or {}).get("max_negative_day_streak", 0) or 0),
                "daily_profit_factor": (item or {}).get("daily_profit_factor"),
                "max_drawdown_to_pnl": (item or {}).get("max_drawdown_to_pnl"),
            }
            for ticker, item in tickers.items()
        },
        "issues": issues,
    }


def audit_partial_june_diagnostic(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "available": False,
            "path": str(path),
            "official_forward_evidence": False,
            "issues": [f"missing {path}"],
        }
    payload = read_json(path)
    return {
        "available": True,
        "path": str(path),
        "official_forward_evidence": bool(payload.get("official_forward_evidence", False)),
        "months": [str(month) for month in payload.get("months", [])],
        "selected_rows": int(payload.get("selected_rows", 0) or 0),
        "overall": payload.get("overall", {}),
        "by_ticker": payload.get("by_ticker", {}),
        "reason_not_official": payload.get("reason_not_official", ""),
        "issues": [] if not bool(payload.get("official_forward_evidence", False)) else ["partial diagnostic is marked official"],
    }


def audit_raw_thetadata_coverage(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "available": False,
            "path": str(path),
            "official_forward_evidence": False,
            "schema_version": None,
            "true_zero_dte_filter": False,
            "issues": [f"missing {path}"],
        }
    payload = read_json(path)
    combined = payload.get("combined") if isinstance(payload.get("combined"), dict) else {}
    per_ticker = payload.get("per_ticker") if isinstance(payload.get("per_ticker"), dict) else {}
    options = payload.get("options") if isinstance(payload.get("options"), dict) else {}
    try:
        schema_version = int(payload.get("schema_version", 0) or 0)
    except (TypeError, ValueError):
        schema_version = 0
    issues: list[str] = []
    if bool(payload.get("official_forward_evidence", False)):
        issues.append("raw coverage is marked official")
    if schema_version < 2:
        issues.append("raw coverage schema_version < 2; expected true 0DTE audit with expiration==date")
    tickers = payload.get("tickers") if isinstance(payload.get("tickers"), list) else sorted(options.keys())
    zero_dte_file_counts: dict[str, Any] = {}
    for ticker in [str(t).upper() for t in tickers]:
        row = options.get(ticker)
        if not isinstance(row, dict):
            issues.append(f"{ticker}: raw coverage options section missing")
            continue
        zero_count = row.get("zero_dte_option_files")
        non_zero_count = row.get("non_zero_dte_option_files")
        zero_dte_file_counts[ticker] = {
            "zero_dte_option_files": zero_count,
            "non_zero_dte_option_files": non_zero_count,
        }
        if zero_count is None or non_zero_count is None:
            issues.append(f"{ticker}: raw coverage lacks 0DTE/non-0DTE file counters")
    return {
        "available": True,
        "path": str(path),
        "official_forward_evidence": bool(payload.get("official_forward_evidence", False)),
        "schema_version": schema_version,
        "true_zero_dte_filter": bool(schema_version >= 2 and not any("0DTE" in issue or "schema_version" in issue for issue in issues)),
        "latest_common_date_all_tickers": combined.get("latest_common_date_all_tickers"),
        "completed_months": combined.get("completed_months", []),
        "partial_months": combined.get("partial_months", []),
        "zero_dte_file_counts": zero_dte_file_counts,
        "ticker_latest": {
            ticker: {
                "min_latest_available_date_across_parts": row.get("min_latest_available_date_across_parts"),
                "max_latest_available_date_across_parts": row.get("max_latest_available_date_across_parts"),
                "missing_parts": row.get("missing_parts", []),
            }
            for ticker, row in per_ticker.items()
            if isinstance(row, dict)
        },
        "issues": issues,
    }

def audit_trade_raw_coverage_validation(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "passed": False,
            "path": str(path),
            "records_checked": 0,
            "records_passed": 0,
            "scope": "trade/order-level raw 0DTE file coverage; not official partial-month completion evidence",
            "issues": [f"missing {path}"],
        }
    payload = read_json(path)
    return {
        "passed": bool(payload.get("passed", False)),
        "path": str(path),
        "records_checked": int(payload.get("records_checked", 0) or 0),
        "records_passed": int(payload.get("records_passed", 0) or 0),
        "by_source": payload.get("by_source", {}),
        "unique_root_dates": payload.get("unique_root_dates", []),
        "scope": payload.get(
            "scope",
            "trade/order-level raw 0DTE file coverage; not official partial-month completion evidence",
        ),
        "not_covered": payload.get("not_covered", []),
        "issues": [str(issue) for issue in payload.get("issues", [])],
    }

def audit_broker_fill_validation(path_text: str) -> dict[str, Any]:
    path_text = str(path_text).strip()
    if not path_text:
        return {
            "passed": False,
            "path": None,
            "fills_checked": 0,
            "fills_passed": 0,
            "broker_submission_evidence": False,
            "live_fill_evidence": False,
            "issues": ["no broker fill validation artifact supplied"],
        }
    path = Path(path_text)
    if not path.exists():
        return {
            "passed": False,
            "path": str(path),
            "fills_checked": 0,
            "fills_passed": 0,
            "broker_submission_evidence": False,
            "live_fill_evidence": False,
            "issues": [f"missing {path}"],
        }
    payload = read_json(path)
    issues = [str(issue) for issue in payload.get("issues", [])]
    if payload.get("validation") != "dense_candidate_broker_fill_evidence":
        issues.append("broker fill validation artifact has unexpected validation type")
    fills_checked = int(payload.get("fills_checked", 0) or 0)
    fills_passed = int(payload.get("fills_passed", 0) or 0)
    broker_submission_evidence = bool(payload.get("broker_submission_evidence", False))
    if fills_checked <= 0:
        issues.append("no broker/paper/live fills were checked")
    if fills_passed <= 0:
        issues.append("no broker/paper/live fills passed validation")
    if not broker_submission_evidence:
        issues.append("broker_submission_evidence is false")
    passed = bool(payload.get("passed") and fills_checked > 0 and fills_passed > 0 and broker_submission_evidence and not issues)
    return {
        "passed": passed,
        "path": str(path),
        "validation": payload.get("validation"),
        "expected_orders": payload.get("expected_orders"),
        "fills_checked": fills_checked,
        "fills_passed": fills_passed,
        "broker_submission_evidence": broker_submission_evidence,
        "live_fill_evidence": bool(payload.get("live_fill_evidence", False)),
        "require_live": bool(payload.get("require_live", False)),
        "require_entry_and_exit": bool(payload.get("require_entry_and_exit", False)),
        "min_filled_orders": payload.get("min_filled_orders"),
        "not_covered": payload.get("not_covered", []),
        "issues": issues if not passed else [],
    }

def audit_offline_fill_simulation(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "passed": False,
            "path": str(path),
            "issues": [f"missing {path}"],
        }
    payload = read_json(path)
    total = int(payload.get("total_orders", 0) or 0)
    path_passed = bool(payload.get("market_data_path_passed", payload.get("passed", False)))
    strict_cost = bool(payload.get("strict_execution_cost_passed", False))
    ask_covered = int(payload.get("entry_limit_covers_ask_orders", 0) or 0)
    issues: list[str] = []
    if not path_passed:
        issues.append("offline market-data fill path did not pass")
    if not strict_cost:
        issues.append(f"model entry premium covers ask for only {ask_covered}/{total} orders")
    return {
        "passed": bool(path_passed),
        "strict_execution_cost_passed": strict_cost,
        "path": str(path),
        "total_orders": total,
        "passed_orders": int(payload.get("passed_orders", 0) or 0),
        "entry_limit_covers_ask_orders": ask_covered,
        "issues": issues,
    }


def audit_paper_order_validation(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "passed": False,
            "path": str(path),
            "issues": [f"missing {path}"],
        }
    payload = read_json(path)
    total = int(payload.get("total_orders", 0) or 0)
    passed_orders = int(payload.get("passed_orders", 0) or 0)
    issues: list[str] = []
    if not bool(payload.get("passed")):
        issues.append("paper order payload validation did not pass")
    if total <= 0:
        issues.append("no paper orders validated")
    if passed_orders != total:
        issues.append(f"only {passed_orders}/{total} paper orders passed")
    return {
        "passed": bool(payload.get("passed") and total > 0 and passed_orders == total),
        "path": str(path),
        "total_orders": total,
        "passed_orders": passed_orders,
        "risk_capital": payload.get("risk_capital"),
        "min_contracts": payload.get("min_contracts"),
        "max_contracts": payload.get("max_contracts"),
        "not_covered": payload.get("not_covered", []),
        "issues": issues,
    }


def audit_broker_order_contract_validation(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "passed": False,
            "path": str(path),
            "issues": [f"missing {path}"],
        }
    payload = read_json(path)
    total = int(payload.get("total_orders", 0) or 0)
    passed_orders = int(payload.get("passed_orders", 0) or 0)
    issues = list(payload.get("issues", [])) if isinstance(payload.get("issues"), list) else []
    if not bool(payload.get("passed")):
        issues.append("broker order contract validation did not pass")
    if total <= 0:
        issues.append("no broker-order contract rows validated")
    if passed_orders != total:
        issues.append(f"only {passed_orders}/{total} broker-order contract rows passed")
    if bool(payload.get("broker_submission_performed", False)):
        issues.append("validation unexpectedly performed broker submission")
    return {
        "passed": bool(payload.get("passed") and total > 0 and passed_orders == total and not issues),
        "path": str(path),
        "total_orders": total,
        "passed_orders": passed_orders,
        "source_counts": payload.get("source_counts", {}),
        "broker_submission_performed": bool(payload.get("broker_submission_performed", False)),
        "live_fill_evidence": bool(payload.get("live_fill_evidence", False)),
        "not_covered": payload.get("not_covered", []),
        "issues": issues,
    }


def audit_bot_daily_loss_guard_validation(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "passed": False,
            "path": str(path),
            "issues": [f"missing {path}"],
        }
    payload = read_json(path)
    checks = payload.get("checks") if isinstance(payload.get("checks"), dict) else {}
    issues = list(payload.get("issues", [])) if isinstance(payload.get("issues"), list) else []
    required_checks = [
        "first_candidate_blocked",
        "skip_state_written",
        "same_day_repeat_blocked",
        "next_candidate_allowed_after_pause_consumed",
        "other_ticker_trade_ignored",
    ]
    for check in required_checks:
        if not bool(checks.get(check)):
            issues.append(f"{check} did not pass")
    return {
        "passed": bool(payload.get("passed")) and not issues,
        "path": str(path),
        "checks": checks,
        "first_reason": payload.get("first_reason"),
        "repeat_reason": payload.get("repeat_reason"),
        "next_reason": payload.get("next_reason"),
        "issues": issues,
    }


def audit_anti_snooping(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "passed": False,
            "path": str(path),
            "checks": {},
            "issues": [f"missing {path}"],
        }
    payload = read_json(path)
    issues = list(payload.get("issues", [])) if isinstance(payload.get("issues"), list) else []
    return {
        "passed": bool(payload.get("passed")) and not issues,
        "path": str(path),
        "checks": payload.get("checks", {}),
        "issues": issues,
    }


def audit_statistical_robustness(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "passed": False,
            "path": str(path),
            "checks": {},
            "tickers": {},
            "issues": [f"missing {path}"],
        }
    payload = read_json(path)
    tickers = payload.get("tickers") if isinstance(payload.get("tickers"), dict) else {}
    return {
        "passed": bool(payload.get("passed", False)),
        "path": str(path),
        "checks": payload.get("checks", {}),
        "thresholds": payload.get("thresholds", {}),
        "months": [str(month) for month in payload.get("months", [])],
        "tickers": {
            ticker: {
                "observed": (row or {}).get("observed", {}),
                "wilson_95_win_rate": (row or {}).get("wilson_95_win_rate", {}),
                "bootstrap": (row or {}).get("bootstrap", {}),
                "leave_one_month_out_passed": bool((row or {}).get("leave_one_month_out_passed", False)),
                "top_winner_stress_passed": bool((row or {}).get("top_winner_stress_passed", False)),
                "issues": (row or {}).get("issues", []),
            }
            for ticker, row in tickers.items()
        },
        "issues": [str(issue) for issue in payload.get("issues", [])],
    }


def audit_research_selection_artifact(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "passed": False,
            "path": str(path),
            "strict": False,
            "issues": [f"missing {path}"],
            "warnings": [],
        }
    payload = read_json(path)
    issues = list(payload.get("issues", [])) if isinstance(payload.get("issues"), list) else []
    warnings = list(payload.get("warnings", [])) if isinstance(payload.get("warnings"), list) else []
    return {
        "passed": bool(payload.get("passed")) and bool(payload.get("strict")) and not issues and not warnings,
        "path": str(path),
        "strict": bool(payload.get("strict")),
        "months": [str(month) for month in payload.get("months", [])],
        "manifest_present": bool(payload.get("manifest_present")),
        "ticker_status": {
            ticker: {
                "selection_status": (row or {}).get("selection_status"),
                "selector_evidence": bool((row or {}).get("selector_evidence")),
                "causal_model_evidence": bool((row or {}).get("causal_model_evidence")),
                "source_streams": (row or {}).get("source_streams", []),
            }
            for ticker, row in (payload.get("tickers", {}) or {}).items()
        },
        "issues": issues,
        "warnings": warnings,
    }


def write_markdown(output_dir: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Dense Candidate Requirement Audit",
        "",
        f"- Causal research walk-forward passed: {payload['causal_research_walkforward_passed']}",
        f"- Requested walk-forward objective passed: {payload['requested_walkforward_objective_passed']}",
        f"- Live-ready passed: {payload['live_ready_passed']}",
        f"- Result dir: `{payload['result_dir']}`",
        "",
        "## Explicit Gates",
        "",
        "| Ticker | Passed | WR | PF | Min Trades/Month | Call Rate |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for ticker, item in payload["metric_gates"].items():
        metrics = item.get("metrics", {})
        lines.append(
            f"| {ticker} | {item['passed']} | {float(metrics.get('win_rate', 0.0)):.2%} | "
            f"{float(metrics.get('profit_factor', 0.0)):.3f} | "
            f"{int(metrics.get('min_month_trades', 0))} | {float(metrics.get('call_rate', 0.0)):.2%} |"
        )
    lines += [
        "",
        "## Objective Checks",
        "",
        "```json",
        json.dumps(payload["objective_checks"], indent=2, allow_nan=True),
        "```",
        "",
        "## Live-Ready Checks",
        "",
        "```json",
        json.dumps(payload["live_ready_checks"], indent=2, allow_nan=True),
        "```",
        "",
        "## Evidence",
        "",
        "```json",
        json.dumps(payload["evidence"], indent=2, allow_nan=True),
        "```",
        "",
        "## Remaining Live Gaps",
        "",
    ]
    for gap in payload["remaining_live_gaps"]:
        lines.append(f"- {gap}")
    (output_dir / "REQUIREMENT_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit dense 0DTE candidate against the user objective and live-readiness gaps.")
    parser.add_argument("--result-dir", default=str(DEFAULT_RESULT))
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--freeze-manifest", default=str(DEFAULT_FREEZE))
    parser.add_argument("--forward-evaluation", default=str(DEFAULT_FORWARD_EVALUATION))
    parser.add_argument("--completed-2026-walkforward", default=str(DEFAULT_COMPLETED_2026_WALKFORWARD))
    parser.add_argument("--raw-complete-2026-walkforward", default=str(DEFAULT_RAW_COMPLETE_2026_WALKFORWARD))
    parser.add_argument("--broad-raw-complete-walkforward", default=str(DEFAULT_BROAD_RAW_COMPLETE_WALKFORWARD))
    parser.add_argument("--frozen-2025-to-2026", default=str(DEFAULT_FROZEN_2025_TO_2026))
    parser.add_argument("--raw-complete-frozen-2025-to-2026", default=str(DEFAULT_RAW_COMPLETE_FROZEN_2025_TO_2026))
    parser.add_argument("--guarded-frozen-2025-to-2026", default=str(DEFAULT_GUARDED_FROZEN_2025_TO_2026))
    parser.add_argument(
        "--guarded-frozen-2025-to-2026-curve",
        default=str(DEFAULT_GUARDED_FROZEN_2025_TO_2026_CURVE),
    )
    parser.add_argument("--guarded-raw-complete-2026", default=str(DEFAULT_GUARDED_RAW_COMPLETE_2026))
    parser.add_argument(
        "--guarded-raw-complete-2026-curve",
        default=str(DEFAULT_GUARDED_RAW_COMPLETE_2026_CURVE),
    )
    parser.add_argument(
        "--guarded-strict-research-selection-audit",
        default=str(DEFAULT_GUARDED_STRICT_RESEARCH_SELECTION_AUDIT),
    )
    parser.add_argument("--guarded-anti-snooping-audit", default=str(DEFAULT_GUARDED_ANTI_SNOOPING_AUDIT))
    parser.add_argument("--guarded-statistical-robustness", default=str(DEFAULT_GUARDED_STATISTICAL_ROBUSTNESS))
    parser.add_argument("--fixed-holdout-may", default=str(DEFAULT_FIXED_HOLDOUT_MAY))
    parser.add_argument("--partial-june-diagnostic", default=str(DEFAULT_PARTIAL_JUNE_DIAGNOSTIC))
    parser.add_argument("--offline-fill-simulation", default="")
    parser.add_argument("--paper-order-validation", default=str(DEFAULT_PAPER_ORDER_VALIDATION))
    parser.add_argument("--bot-daily-loss-guard-validation", default=str(DEFAULT_BOT_DAILY_LOSS_GUARD_VALIDATION))
    parser.add_argument("--broker-order-contract-validation", default=str(DEFAULT_BROKER_ORDER_CONTRACT_VALIDATION))
    parser.add_argument("--trade-raw-coverage-validation", default=str(DEFAULT_TRADE_RAW_COVERAGE_VALIDATION))
    parser.add_argument("--raw-thetadata-coverage", default=str(DEFAULT_RAW_THETADATA_COVERAGE))
    parser.add_argument("--anti-snooping-audit", default=str(DEFAULT_ANTI_SNOOPING_AUDIT))
    parser.add_argument("--broker-fill-validation", default=str(DEFAULT_BROKER_FILL_VALIDATION))
    parser.add_argument("--output-dir", default="")
    parser.add_argument(
        "--exit-zero-on-incomplete-objective",
        action="store_true",
        help="Write the incomplete-objective audit payload but return 0 for status-report suites.",
    )
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--start-month", default="202301")
    parser.add_argument("--end-month", default="202605")
    parser.add_argument("--min-win-rate", type=float, default=0.45)
    parser.add_argument("--min-profit-factor", type=float, default=1.30)
    parser.add_argument("--min-month-trades", type=int, default=18)
    parser.add_argument("--min-call-rate", type=float, default=0.20)
    parser.add_argument("--max-call-rate", type=float, default=0.80)
    args = parser.parse_args()

    result_dir = Path(args.result_dir)
    output_dir = Path(args.output_dir) if args.output_dir else result_dir / "requirement_audit"
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics = read_json(result_dir / "metrics.json")
    verification = read_json(result_dir / "verification.json")
    selection_audit = read_json(result_dir / "research_selection_audit_non_strict" / "research_selection_audit.json")
    runtime_replay = read_json(result_dir / "runtime_policy_replay" / "runtime_policy_replay_summary.json")
    batch_smoke = read_json(result_dir / "snapshot_to_order_batch_smoke" / "snapshot_to_order_batch_smoke.json")
    curve = read_json(result_dir / "curve_health" / "curve_health.json")
    freeze = read_json(Path(args.freeze_manifest))
    registry = read_json(Path(args.registry))
    policy = read_json(Path(args.policy))

    metric_gates = audit_metric_gates(metrics, [str(t).upper() for t in args.tickers], args)
    fold_integrity = audit_fold_temporal_integrity(result_dir / "combined_folds.csv", str(args.start_month), str(args.end_month))
    zero_dte = audit_zero_dte(result_dir / "combined_trades.csv")
    registry_artifacts = audit_registry_artifacts(registry)
    forward_evaluation = audit_forward_evaluation(Path(args.forward_evaluation), str(freeze.get("frozen_before_month", "")))
    completed_2026_walkforward = audit_verification_artifact(
        Path(args.completed_2026_walkforward),
        ["202601", "202602", "202603", "202604", "202605"],
    )
    raw_complete_2026_walkforward = audit_verification_artifact(
        Path(args.raw_complete_2026_walkforward),
        ["202601", "202602", "202603", "202604"],
    )
    broad_raw_complete_months = [
        month
        for year in ["2023", "2024", "2025", "2026"]
        for month in [f"{year}{idx:02d}" for idx in range(1, 13)]
        if "202301" <= month <= "202604" and month != "202403"
    ]
    broad_raw_complete_walkforward = audit_verification_artifact(
        Path(args.broad_raw_complete_walkforward),
        broad_raw_complete_months,
    )
    frozen_2025_expected_months = ["202601", "202602", "202603", "202604", "202605"]
    frozen_2025_to_2026 = audit_verification_artifact(
        Path(args.frozen_2025_to_2026),
        frozen_2025_expected_months,
    )
    raw_complete_frozen_2025_to_2026 = audit_verification_artifact(
        Path(args.raw_complete_frozen_2025_to_2026),
        ["202601", "202602", "202603", "202604"],
    )
    frozen_2025_to_2026_lineage = audit_frozen_walkforward_lineage(
        Path(args.frozen_2025_to_2026).parent / "combined_folds.csv",
        frozen_2025_expected_months,
        "202512",
    )
    guarded_frozen_2025_to_2026 = audit_verification_artifact(
        Path(args.guarded_frozen_2025_to_2026),
        ["202601", "202602", "202603", "202604", "202605"],
    )
    guarded_frozen_2025_to_2026_curve = audit_curve_health_artifact(
        Path(args.guarded_frozen_2025_to_2026_curve),
        ["202601", "202602", "202603", "202604", "202605"],
    )
    guarded_raw_complete_months = ["202601", "202602", "202603", "202604"]
    guarded_raw_complete_2026 = audit_verification_artifact(
        Path(args.guarded_raw_complete_2026),
        guarded_raw_complete_months,
    )
    guarded_raw_complete_2026_curve = audit_curve_health_artifact(
        Path(args.guarded_raw_complete_2026_curve),
        guarded_raw_complete_months,
    )
    guarded_strict_research_selection_audit = audit_research_selection_artifact(
        Path(args.guarded_strict_research_selection_audit)
    )
    guarded_anti_snooping_audit = audit_anti_snooping(Path(args.guarded_anti_snooping_audit))
    guarded_statistical_robustness = audit_statistical_robustness(Path(args.guarded_statistical_robustness))
    fixed_holdout_may = audit_verification_artifact(Path(args.fixed_holdout_may), ["202605"])
    partial_june_diagnostic = audit_partial_june_diagnostic(Path(args.partial_june_diagnostic))
    offline_fill_path = (
        Path(args.offline_fill_simulation)
        if str(args.offline_fill_simulation).strip()
        else result_dir / "offline_fill_simulation" / "offline_fill_simulation.json"
    )
    offline_fill_simulation = audit_offline_fill_simulation(offline_fill_path)
    paper_order_validation = audit_paper_order_validation(Path(args.paper_order_validation))
    bot_daily_loss_guard_validation = audit_bot_daily_loss_guard_validation(Path(args.bot_daily_loss_guard_validation))
    broker_order_contract_validation = audit_broker_order_contract_validation(Path(args.broker_order_contract_validation))
    trade_raw_coverage_validation = audit_trade_raw_coverage_validation(Path(args.trade_raw_coverage_validation))
    raw_thetadata_coverage = audit_raw_thetadata_coverage(Path(args.raw_thetadata_coverage))
    anti_snooping_audit = audit_anti_snooping(Path(args.anti_snooping_audit))
    broker_fill_validation = audit_broker_fill_validation(str(args.broker_fill_validation))

    evidence = {
        "metrics_loaded": True,
        "formal_verifier_passed": bool(verification.get("passed")),
        "formal_verifier_folds_checked": int((verification.get("integrity") or {}).get("folds_checked", 0)),
        "formal_verifier_backfill_passed": bool((verification.get("backfill") or {}).get("passed")),
        "formal_verifier_backfill_rows_checked": int((verification.get("backfill") or {}).get("rows_checked", 0)),
        "fold_temporal_integrity": fold_integrity,
        "zero_dte": zero_dte,
        "research_selection_audit_passed": bool(selection_audit.get("passed")),
        "research_selection_audit_strict": bool(selection_audit.get("strict", False)),
        "runtime_policy_replay_passed": bool(runtime_replay.get("passed")),
        "runtime_policy_replay_cases": [
            {
                "name": row.get("name"),
                "passed": row.get("passed"),
                "actual_rows": row.get("actual_rows"),
                "expected_rows": row.get("expected_rows"),
            }
            for row in runtime_replay.get("comparisons", [])
        ],
        "snapshot_to_order_batch_passed": bool(batch_smoke.get("passed")),
        "snapshot_to_order_batch_cases": f"{batch_smoke.get('passed_cases')}/{batch_smoke.get('total_cases')}",
        "forward_freeze_manifest_exists": True,
        "forward_freeze_month": freeze.get("frozen_before_month"),
        "registry_status": registry.get("status"),
        "policy_status": policy.get("status"),
        "registry_artifacts": registry_artifacts,
        "completed_2026_walkforward": completed_2026_walkforward,
        "raw_complete_2026_walkforward": raw_complete_2026_walkforward,
        "broad_raw_complete_walkforward": broad_raw_complete_walkforward,
        "frozen_2025_to_2026": frozen_2025_to_2026,
        "raw_complete_frozen_2025_to_2026": raw_complete_frozen_2025_to_2026,
        "frozen_2025_to_2026_lineage": frozen_2025_to_2026_lineage,
        "guarded_frozen_2025_to_2026": guarded_frozen_2025_to_2026,
        "guarded_frozen_2025_to_2026_curve": guarded_frozen_2025_to_2026_curve,
        "guarded_raw_complete_2026": guarded_raw_complete_2026,
        "guarded_raw_complete_2026_curve": guarded_raw_complete_2026_curve,
        "guarded_strict_research_selection_audit": guarded_strict_research_selection_audit,
        "guarded_anti_snooping_audit": guarded_anti_snooping_audit,
        "guarded_statistical_robustness": guarded_statistical_robustness,
        "fixed_holdout_may2026": fixed_holdout_may,
        "partial_june_diagnostic": partial_june_diagnostic,
        "broad_result_curve_health_passed": bool(curve.get("passed")),
        "forward_evaluation": forward_evaluation,
        "offline_fill_simulation": offline_fill_simulation,
        "paper_order_validation": paper_order_validation,
        "bot_daily_loss_guard_validation": bot_daily_loss_guard_validation,
        "broker_order_contract_validation": broker_order_contract_validation,
        "trade_raw_coverage_validation": trade_raw_coverage_validation,
        "raw_thetadata_coverage": raw_thetadata_coverage,
        "anti_snooping_audit": anti_snooping_audit,
        "broker_fill_validation": broker_fill_validation,
    }
    broad_historical_diagnostic_checks = {
        "per_ticker_metric_gates": bool(all(item["passed"] for item in metric_gates.values())),
        "formal_verifier": bool(verification.get("passed")),
        "fold_temporal_integrity": bool(fold_integrity["passed"]),
        "zero_dte_only": bool(zero_dte["passed"]),
        "research_selection_audit_non_strict": bool(selection_audit.get("passed")),
        "runtime_stream_replay": bool(runtime_replay.get("passed")),
        "snapshot_to_order_batch_smoke": bool(batch_smoke.get("passed")),
        "deploy_package_artifacts": bool(registry_artifacts["passed"]),
        "completed_2026_walkforward": bool(completed_2026_walkforward["passed"]),
        "raw_complete_2026_walkforward": bool(raw_complete_2026_walkforward["passed"]),
        "broad_raw_complete_walkforward": bool(broad_raw_complete_walkforward["passed"]),
        "frozen_2025_to_2026": bool(frozen_2025_to_2026["passed"]),
        "raw_complete_frozen_2025_to_2026": bool(raw_complete_frozen_2025_to_2026["passed"]),
        "frozen_2025_to_2026_lineage": bool(frozen_2025_to_2026_lineage["passed"]),
        "guarded_frozen_2025_to_2026_full_month_diagnostic": bool(guarded_frozen_2025_to_2026["passed"]),
        "guarded_frozen_2025_to_2026_full_curve_diagnostic": bool(guarded_frozen_2025_to_2026_curve["passed"]),
        "guarded_statistical_robustness": bool(guarded_statistical_robustness["passed"]),
        "fixed_holdout_may2026": bool(fixed_holdout_may["passed"]),
        "broad_historical_anti_snooping_audit": bool(anti_snooping_audit["passed"]),
    }
    causal_research_walkforward_checks = {
        "guarded_raw_complete_2026": bool(guarded_raw_complete_2026["passed"]),
        "guarded_raw_complete_2026_curve": bool(guarded_raw_complete_2026_curve["passed"]),
        "guarded_strict_research_selection_audit": bool(guarded_strict_research_selection_audit["passed"]),
        "guarded_anti_snooping_audit": bool(guarded_anti_snooping_audit["passed"]),
        "bot_daily_loss_guard_runtime": bool(bot_daily_loss_guard_validation["passed"]),
        "broker_order_contract_validation": bool(broker_order_contract_validation["passed"]),
        "trade_raw_coverage_validation": bool(trade_raw_coverage_validation["passed"]),
    }
    metric_objective_checks = causal_research_walkforward_checks
    metric_walkforward_objective_passed = bool(all(metric_objective_checks.values()))
    causal_research_walkforward_passed = metric_walkforward_objective_passed
    objective_checks = {
        **causal_research_walkforward_checks,
        "zero_dte_only": bool(zero_dte["passed"]),
        "runtime_stream_replay": bool(runtime_replay.get("passed")),
        "snapshot_to_order_batch_smoke": bool(batch_smoke.get("passed")),
        "deploy_package_artifacts": bool(registry_artifacts["passed"]),
    }
    requested_walkforward_objective_passed = bool(all(objective_checks.values()))
    live_ready_checks = {
        "requested_walkforward_objective": requested_walkforward_objective_passed,
        "policy_status_live_ready": "live_ready" in str(policy.get("status", "")).lower()
        and "research" not in str(policy.get("status", "")).lower(),
        "registry_status_live_ready": "live_ready" in str(registry.get("status", "")).lower()
        and "research" not in str(registry.get("status", "")).lower(),
        "curve_health": bool(guarded_raw_complete_2026_curve["passed"]),
        "future_forward_freeze_observed": bool(forward_evaluation["passed"]),
        "offline_fill_simulation_market_data": bool(offline_fill_simulation["passed"]),
        "offline_fill_simulation_strict_execution_cost": bool(offline_fill_simulation["strict_execution_cost_passed"]),
        "paper_order_payload_validation": bool(paper_order_validation["passed"]),
        "bot_daily_loss_guard_runtime": bool(bot_daily_loss_guard_validation["passed"]),
        "broker_order_contract_validation": bool(broker_order_contract_validation["passed"]),
        "trade_raw_coverage_validation": bool(trade_raw_coverage_validation["passed"]),
        "broker_fill_validation": bool(broker_fill_validation["passed"]),
    }
    live_ready_passed = bool(all(live_ready_checks.values()))
    remaining_live_gaps = []
    if not live_ready_checks["policy_status_live_ready"] or not live_ready_checks["registry_status_live_ready"]:
        remaining_live_gaps.append("Candidate package is still marked forward_frozen_research_candidate_not_live_ready.")
    if not causal_research_walkforward_checks["guarded_anti_snooping_audit"]:
        remaining_live_gaps.append(
            "Anti-snooping/research-selection audit is not proven: "
            + "; ".join(guarded_anti_snooping_audit.get("issues", []))
        )
    if not guarded_statistical_robustness["passed"]:
        remaining_live_gaps.append(
            "Guarded 202601..202604 research evidence is statistically thin/concentrated: "
            + "; ".join(guarded_statistical_robustness.get("issues", []))
        )
    if not live_ready_checks["curve_health"]:
        remaining_live_gaps.append("Strict curve-health gate is false for this candidate.")
    if not live_ready_checks["future_forward_freeze_observed"]:
        remaining_live_gaps.append(
            "No official completed-month 202607+ forward-freeze evaluation has passed yet: "
            + "; ".join(forward_evaluation.get("issues", []))
        )
    if not live_ready_checks["offline_fill_simulation_market_data"]:
        remaining_live_gaps.append(
            "Offline fill simulation is not proven: " + "; ".join(offline_fill_simulation.get("issues", []))
        )
    elif not live_ready_checks["offline_fill_simulation_strict_execution_cost"]:
        remaining_live_gaps.append(
            "Offline fill simulation has market-data path coverage, but the modeled entry premium does not cover ask on every order: "
            + "; ".join(offline_fill_simulation.get("issues", []))
        )
    if not live_ready_checks["paper_order_payload_validation"]:
        remaining_live_gaps.append(
            "Paper order payload validation is not proven: " + "; ".join(paper_order_validation.get("issues", []))
        )
    if not live_ready_checks["bot_daily_loss_guard_runtime"]:
        remaining_live_gaps.append(
            "Bot runtime daily-loss guard validation is not proven: "
            + "; ".join(bot_daily_loss_guard_validation.get("issues", []))
        )
    if not live_ready_checks["broker_order_contract_validation"]:
        remaining_live_gaps.append(
            "Broker-order contract validation is not proven: "
            + "; ".join(broker_order_contract_validation.get("issues", []))
        )
    if not live_ready_checks["trade_raw_coverage_validation"]:
        remaining_live_gaps.append(
            "Trade/order raw 0DTE coverage validation is not proven: "
            + "; ".join(trade_raw_coverage_validation.get("issues", []))
        )
    if raw_thetadata_coverage.get("available"):
        latest_raw = raw_thetadata_coverage.get("latest_common_date_all_tickers")
        partial_months = [str(month) for month in raw_thetadata_coverage.get("partial_months", []) if str(month) >= "202605"]
        if latest_raw:
            remaining_live_gaps.append(
                "Raw ThetaData coverage reaches "
                + str(latest_raw)
                + "; partial/non-official months at or after 202605: "
                + (", ".join(partial_months) if partial_months else "none")
                + "."
            )
    if not live_ready_checks["broker_fill_validation"]:
        remaining_live_gaps.append(
            "Broker/order execution fill validation is not proven: "
            + "; ".join(broker_fill_validation.get("issues", []))
        )
    payload = {
        "schema_version": 1,
        "audit": "dense_candidate_requirements",
        "result_dir": str(result_dir),
        "metric_walkforward_objective_passed": metric_walkforward_objective_passed,
        "causal_research_walkforward_passed": causal_research_walkforward_passed,
        "requested_walkforward_objective_passed": requested_walkforward_objective_passed,
        "live_ready_passed": live_ready_passed,
        "objective_checks": objective_checks,
        "broad_historical_diagnostic_checks": broad_historical_diagnostic_checks,
        "live_ready_checks": live_ready_checks,
        "metric_gates": metric_gates,
        "evidence": evidence,
        "remaining_live_gaps": remaining_live_gaps,
    }
    (output_dir / "requirement_audit.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    write_markdown(output_dir, payload)
    print(json.dumps(payload, indent=2, allow_nan=True))
    if bool(args.exit_zero_on_incomplete_objective):
        return 0
    return 0 if requested_walkforward_objective_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())


