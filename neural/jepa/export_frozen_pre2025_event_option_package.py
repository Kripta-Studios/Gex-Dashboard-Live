from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESULT_DIR = (
    PROJECT_ROOT
    / "research_papers"
    / "JEPA"
    / "results"
    / "_diagnostics"
    / "frozen_source_selector_dense15_pre2025_static_202501_202604_v1"
    / "combined"
)
DEFAULT_DEPLOY_MODELS_DIR = DEFAULT_RESULT_DIR.parent / "deploy_models"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "neural" / "models" / "jepa" / "jepa_production_event_options_frozen_pre2025"
DEFAULT_RAW_THETADATA_COVERAGE = (
    PROJECT_ROOT
    / "research_papers"
    / "JEPA"
    / "results"
    / "_diagnostics"
    / "thetadata_0dte_raw_coverage_spxw_spy_qqq"
    / "raw_coverage.json"
)
DEFAULT_RUNTIME_REPLAY_SUMMARY = DEFAULT_RESULT_DIR.parent / "runtime_replay_monthly_backfill18" / "runtime_replay_summary.json"


MODEL_SPECS = {
    "SPXW.primary_d25_win": ("SPXW_primary_d25_win", 25, "primary"),
    "SPXW.fallback_d50_return": ("SPXW_fallback_d50_return", 50, "fallback"),
    "SPY.primary_d25_win": ("SPY_primary_d25_win", 25, "primary"),
    "SPY.fallback_d50_return": ("SPY_fallback_d50_return", 50, "fallback"),
    "QQQ.primary_d25_win": ("QQQ_primary_d25_win", 25, "primary"),
    "QQQ.fallback_d50_return": ("QQQ_fallback_d50_return", 50, "fallback"),
}


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT.resolve())).replace("\\", "/")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def copy_tree_file(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def raw_coverage_summary(path: Path, months: list[str], tickers: list[str]) -> dict[str, Any]:
    payload = read_json(path)
    combined = payload.get("combined") if isinstance(payload.get("combined"), dict) else {}
    completed = {str(item) for item in combined.get("completed_months", [])}
    missing = [month for month in months if month not in completed]
    return {
        "path": rel(path),
        "schema_version": int(payload.get("schema_version", 0) or 0),
        "completed_months_cover_validation": not missing,
        "missing_validation_months": missing,
        "latest_common_date_all_tickers": combined.get("latest_common_date_all_tickers"),
        "partial_months": [str(item) for item in combined.get("partial_months", [])],
        "tickers": tickers,
    }


def component_entry(
    *,
    component_name: str,
    model_dir: Path,
    output_dir: Path,
    deploy_models_dir: Path,
) -> dict[str, Any]:
    source_dir_name, delta_bucket, role = MODEL_SPECS[component_name]
    source_deploy = deploy_models_dir / source_dir_name / "deploy_model"
    source_pkl = source_deploy / "event_option_gate_direction_model.pkl"
    source_json = source_deploy / "event_option_gate_direction_model.json"
    target_deploy = model_dir / source_dir_name / "deploy_model"
    target_pkl = target_deploy / "event_option_gate_direction_model.pkl"
    target_json = target_deploy / "event_option_gate_direction_model.json"
    copy_tree_file(source_pkl, target_pkl)
    copy_tree_file(source_json, target_json)
    metadata = read_json(target_json)
    select_metrics = metadata.get("select_metrics", {}) if isinstance(metadata.get("select_metrics"), dict) else {}
    return {
        "component": "event_option_gate_direction_model",
        "path": rel(target_pkl),
        "metadata": rel(target_json),
        "train_months": [str(item) for item in metadata.get("train_months", [])],
        "select_months": [str(item) for item in metadata.get("select_months", [])],
        "deploy_month": str(metadata.get("deploy_month", "")),
        "deploy_select_end_month": str(metadata.get("deploy_select_end_month", "")),
        "deploy_config": str(metadata.get("deploy_config_name", "")),
        "delta_bucket": int(delta_bucket),
        "role": role,
        "select_score": float(metadata.get("select_score", 0.0) or 0.0),
        "select_metrics": {
            "trades": int(select_metrics.get("trades", 0) or 0),
            "win_rate": float(select_metrics.get("win_rate", 0.0) or 0.0),
            "profit_factor": float(select_metrics.get("profit_factor", 0.0) or 0.0),
            "pnl_return": float(select_metrics.get("pnl_return", 0.0) or 0.0),
            "min_month_trades": int(select_metrics.get("min_month_trades", 0) or 0),
            "positive_month_rate": float(select_metrics.get("positive_month_rate", 0.0) or 0.0),
        },
    }


def write_backfill_policy(
    output_dir: Path,
    ticker: str,
    *,
    runtime_replay_passed: bool,
    runtime_replay_path: Path | None,
) -> tuple[str, dict[str, Any]]:
    name = f"{ticker}.monthly_backfill18"
    payload = {
        "schema_version": 1,
        "component": "event_monthly_volume_backfill_policy",
        "ticker": ticker,
        "primary_component": f"{ticker}.primary_d25_win",
        "primary_name": "win_valthr_wr45_d25",
        "primary_delta_bucket": 25,
        "fallback_component": f"{ticker}.fallback_d50_return",
        "fallback_name": "forcedmax3_d50",
        "fallback_delta_bucket": 50,
        "min_month_trades": 18,
        "max_day": 3,
        "cooldown_minutes": 30,
        "expiry_mode": "zero_dte",
        "runtime_state_required": [
            "month_to_date_count",
            "per_day_count",
            "cooldown",
            "dedupe",
        ],
        "live_equivalence_status": (
            "stateful_runtime_replay_passed_candidate_stream"
            if runtime_replay_passed
            else "stateful_runtime_replay_required"
        ),
        "live_equivalence_reason": (
            "The deterministic runtime policy replay matched frozen causal candidate-stream selections. "
            "Live promotion still requires deploy-scorer/paper or broker order-fill evidence."
            if runtime_replay_passed
            else "The offline monthly backfill is deterministic, but live promotion still "
            "requires stateful replay against event_option_snapshots_latest rows and "
            "paper/broker order-fill evidence."
        ),
    }
    if runtime_replay_passed and runtime_replay_path is not None:
        payload["live_equivalence_evidence"] = {"runtime_policy_replay": rel(runtime_replay_path)}
    target = output_dir / "components" / f"{ticker.lower()}_monthly_backfill18" / "deploy_model" / "monthly_volume_backfill_policy.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    return name, {
        "component": "event_monthly_volume_backfill_policy",
        "path": rel(target),
        "metadata": rel(target),
        "primary_component": payload["primary_component"],
        "fallback_component": payload["fallback_component"],
        "primary_name": payload["primary_name"],
        "fallback_name": payload["fallback_name"],
        "min_month_trades": payload["min_month_trades"],
        "max_day": payload["max_day"],
        "cooldown_minutes": payload["cooldown_minutes"],
        "live_equivalence_status": payload["live_equivalence_status"],
        "live_equivalence_evidence": payload.get("live_equivalence_evidence", {}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the pre-2025 frozen Dense15 0DTE candidate as a blocked live package.")
    parser.add_argument("--result-dir", default=str(DEFAULT_RESULT_DIR))
    parser.add_argument("--deploy-models-dir", default=str(DEFAULT_DEPLOY_MODELS_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--deploy-month", default="202607")
    parser.add_argument("--completed-start-month", default="202501")
    parser.add_argument("--completed-end-month", default="202604")
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    parser.add_argument("--raw-thetadata-coverage", default=str(DEFAULT_RAW_THETADATA_COVERAGE))
    parser.add_argument("--runtime-replay-summary", default=str(DEFAULT_RUNTIME_REPLAY_SUMMARY))
    args = parser.parse_args()

    result_dir = Path(args.result_dir)
    deploy_models_dir = Path(args.deploy_models_dir)
    output_dir = Path(args.output_dir)
    components_dir = output_dir / "components"
    output_dir.mkdir(parents=True, exist_ok=True)
    components_dir.mkdir(parents=True, exist_ok=True)

    metrics = read_json(result_dir / "metrics.json")
    verification = read_json(result_dir / "verification_raw_complete_202501_202604.json")
    feature_audit = read_json(result_dir / "feature_leakage_audit_raw_complete_202501_202604" / "feature_leakage_audit.json")
    research_audit = read_json(result_dir / "research_selection_audit_raw_complete_202501_202604_v2" / "research_selection_audit.json")
    robustness = read_json(result_dir / "statistical_robustness_raw_complete_202501_202604" / "statistical_robustness.json")
    curve_health_path = result_dir / "curve_health" / "curve_health.json"
    curve_health = read_json(curve_health_path) if curve_health_path.exists() else {"passed": False, "issues": ["curve_health missing"]}
    manifest = read_json(result_dir / "research_selection_manifest.json")
    runtime_replay_path = Path(args.runtime_replay_summary)
    runtime_replay = read_json(runtime_replay_path) if runtime_replay_path.exists() else {}
    runtime_replay_passed = bool(runtime_replay.get("passed", False))

    months = [str(item) for item in verification.get("gates", {}).get("months", [])]
    tickers = ["SPXW", "SPY", "QQQ"]
    available_components: dict[str, Any] = {}
    for component_name in MODEL_SPECS:
        available_components[component_name] = component_entry(
            component_name=component_name,
            model_dir=components_dir,
            output_dir=output_dir,
            deploy_models_dir=deploy_models_dir,
        )
    for ticker in tickers:
        name, entry = write_backfill_policy(
            output_dir,
            ticker,
            runtime_replay_passed=runtime_replay_passed,
            runtime_replay_path=runtime_replay_path if runtime_replay_path.exists() else None,
        )
        available_components[name] = entry

    live_blockers = [
        "paper/broker order-fill evidence is not yet present",
        "deploy scorer was smoke-tested, but historical fold-scorer replay from event_option_snapshots_latest is not yet proven",
    ]
    if not runtime_replay_passed:
        live_blockers.insert(0, "stateful runtime replay for monthly_backfill18 is not yet proven")
    if not bool(curve_health.get("passed", False)):
        live_blockers.append("curve_health failed or is missing")
    if not bool(robustness.get("passed", False)):
        live_blockers.append("statistical robustness failed")
    live_blockers.append("research manifest is reproducible but not timestamp proof of source-universe freeze")

    registry = {
        "schema_version": 1,
        "status": "forward_frozen_research_candidate_not_live_ready",
        "deploy_month": str(args.deploy_month),
        "completed_data_through_month": "202604",
        "reason_completed_data_through_month": "202605 and 202606 are partial in true 0DTE raw coverage.",
        "available_components": available_components,
        "live_equivalence_evidence": {
            "monthly_backfill18_runtime_policy_replay": rel(runtime_replay_path)
            if runtime_replay_passed and runtime_replay_path.exists()
            else None,
            "monthly_backfill18_runtime_policy_replay_passed": runtime_replay_passed,
        },
        "missing_for_full_live_equivalence": live_blockers,
        "invalidated_components": {"components": []},
    }
    registry_path = output_dir / "component_registry.json"
    registry_path.write_text(json.dumps(registry, indent=2, allow_nan=True), encoding="utf-8")

    policy = {
        "schema_version": 1,
        "policy": f"event_option_frozen_pre2025_dense15_0dte_{args.deploy_month}",
        "status": "forward_frozen_research_candidate_not_live_ready",
        "deploy_month": str(args.deploy_month),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "risk_capital_dollars": float(args.risk_capital),
        "component_registry": rel(registry_path),
        "validated_label_exit_contract": {
            "source": "neural/jepa/build_event_option_dataset.py",
            "horizon_minutes": 180,
            "option_take_profit_pct": 0.5,
            "option_stop_loss_pct": 0.3,
            "live_equivalence_note": (
                "Walk-forward metrics are based on the +50%/-30%/180m option path label contract. "
                "Live execution must use the same exit contract unless separately revalidated."
            ),
        },
        "live_contract": {
            "tickers": ["SPX", "SPY", "QQQ"],
            "options_symbols": {"SPX": "SPXW", "SPY": "SPY", "QQQ": "QQQ"},
            "expiry_mode": "zero_dte",
            "entry_sample_minutes": 5,
            "entry_time_min_et": "10:00",
            "entry_time_max_et": "15:45",
            "cooldown_minutes": 30,
            "hard_stop_pct": -0.60,
            "trailing_stop_activate_pct": 0.50,
            "trailing_stop_giveback_pct": 0.25,
            "emergency_take_profit_pct": 10.0,
            "event_option_exit_contract": {
                "take_profit_pct": 0.5,
                "stop_loss_pct": -0.3,
                "max_hold_minutes": 180,
                "trailing_enabled": False,
            },
            "event_option_live_ready": False,
            "live_ready_blockers": live_blockers,
        },
        "completed_month_validation": {
            "result_dir": rel(result_dir),
            "verification_file": "verification_raw_complete_202501_202604.json",
            "curve_health_file": "curve_health/curve_health.json",
            "months": months,
            "raw_thetadata_coverage": raw_coverage_summary(Path(args.raw_thetadata_coverage), months, tickers),
            "gates": {
                "min_win_rate": 0.45,
                "min_profit_factor": 1.30,
                "min_month_trades": 18,
                "require_positive_months": False,
            },
            "overall": metrics.get("overall", {}),
            "by_ticker": metrics.get("by_ticker", {}),
            "verification_passed": bool(verification.get("passed", False)),
            "feature_leakage_passed": bool(feature_audit.get("passed", False)),
            "research_selection_passed": bool(research_audit.get("passed", False)),
            "statistical_robustness_passed": bool(robustness.get("passed", False)),
            "curve_health_passed": bool(curve_health.get("passed", False)),
            "runtime_policy_replay_passed": runtime_replay_passed,
            "runtime_policy_replay_file": rel(runtime_replay_path)
            if runtime_replay_passed and runtime_replay_path.exists()
            else None,
        },
        "live_equivalence": {
            "runtime_policy_replay": runtime_replay,
            "monthly_backfill18_runtime_policy_replay": runtime_replay,
            "runtime_policy_replay_scope": (
                "Candidate-stream deterministic replay. This closes the monthly_backfill18 state-machine "
                "equivalence check, but not broker fills or historical deploy-scorer equivalence."
            ),
        },
        "freeze_manifest": manifest,
        "research_caveat": (
            "This package contains deployable scorer components for the frozen pre-2025 "
            "Dense15 0DTE research candidate, but it is intentionally not live-ready "
            "until stateful runtime replay and broker/paper fill evidence pass."
        ),
    }
    policy_path = output_dir / "event_option_policy.json"
    policy_path.write_text(json.dumps(policy, indent=2, allow_nan=True), encoding="utf-8")

    for name, src in {
        "completed_month_metrics.json": result_dir / "metrics.json",
        "completed_month_verification.json": result_dir / "verification_raw_complete_202501_202604.json",
        "completed_month_curve_health.json": curve_health_path,
        "feature_leakage_audit.json": result_dir / "feature_leakage_audit_raw_complete_202501_202604" / "feature_leakage_audit.json",
        "research_selection_audit.json": result_dir / "research_selection_audit_raw_complete_202501_202604_v2" / "research_selection_audit.json",
        "statistical_robustness.json": result_dir / "statistical_robustness_raw_complete_202501_202604" / "statistical_robustness.json",
        "research_selection_manifest.json": result_dir / "research_selection_manifest.json",
    }.items():
        if src.exists():
            copy_tree_file(src, output_dir / name)

    lines = [
        "# Frozen Pre-2025 Dense15 0DTE Event-Option Package",
        "",
        f"- Policy: `{policy['policy']}`",
        f"- Status: `{policy['status']}`",
        f"- Deploy month: `{policy['deploy_month']}`",
        f"- Registry: `{policy['component_registry']}`",
        f"- Components: `{len(available_components)}`",
        f"- Verification passed: `{policy['completed_month_validation']['verification_passed']}`",
        f"- Feature leakage passed: `{policy['completed_month_validation']['feature_leakage_passed']}`",
        f"- Research selection passed: `{policy['completed_month_validation']['research_selection_passed']}`",
        f"- Statistical robustness passed: `{policy['completed_month_validation']['statistical_robustness_passed']}`",
        f"- Curve health passed: `{policy['completed_month_validation']['curve_health_passed']}`",
        f"- Runtime policy replay passed: `{policy['completed_month_validation']['runtime_policy_replay_passed']}`",
        "",
        "## Metrics",
        "",
    ]
    for ticker, row in sorted((metrics.get("by_ticker") or {}).items()):
        lines.append(
            f"- {ticker}: trades={row.get('trades')}, WR={float(row.get('win_rate', 0.0)):.2%}, "
            f"PF={float(row.get('profit_factor', 0.0)):.3f}, min_month={row.get('min_month_trades')}, "
            f"PnL=${float(row.get('pnl_return', 0.0)) * float(args.risk_capital):,.0f}"
        )
    lines.extend(["", "## Live Blockers", ""])
    lines.extend([f"- {item}" for item in live_blockers])
    lines.append("")
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
