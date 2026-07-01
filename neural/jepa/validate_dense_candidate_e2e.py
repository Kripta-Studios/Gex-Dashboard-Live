from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RESULT_DIR = Path(
    "research_papers/JEPA/results/"
    "event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_causal_2023_2026_v1"
)
WALKFORWARD_2026_DIR = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "dense_candidate_walkforward_2026_completed_jan_may_v1"
)
FROZEN_2025_TO_2026_DIR = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "dense_candidate_frozen_through_202512_eval_202601_202605_v1"
)
GUARDED_FROZEN_2025_TO_2026_DIR = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "dense_candidate_frozen2025_2026_daily_guard_l4p1_vp0"
)
GUARDED_STATISTICAL_ROBUSTNESS = GUARDED_FROZEN_2025_TO_2026_DIR / "statistical_robustness" / "statistical_robustness.json"
FIXED_HOLDOUT_MAY_DIR = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "dense_candidate_fixed_holdout_select_through_202604_eval_202605_completed_v1"
)
PARTIAL_JUNE_EVAL = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "dense_candidate_partial_20260601_20260626_eval_v1/partial_evaluation.json"
)
FORWARD_EVALUATION_DIR = Path(
    "research_papers/JEPA/results/"
    "event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_forward_evaluation_202607_pending_v1"
)
RAW_THETADATA_COVERAGE = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "thetadata_0dte_raw_coverage_spxw_spy_qqq/raw_coverage.json"
)
PAPER_ORDER_VALIDATION = RESULT_DIR / "paper_order_validation" / "paper_order_validation.json"
BOT_PAPER_ORDER_INTENT_VALIDATION = (
    RESULT_DIR / "bot_paper_order_intent_validation" / "bot_paper_order_intent_validation.json"
)
BOT_DAILY_LOSS_GUARD_VALIDATION = (
    RESULT_DIR / "bot_event_daily_loss_guard_validation" / "bot_event_daily_loss_guard_validation.json"
)
BROKER_ORDER_CONTRACT_VALIDATION = (
    RESULT_DIR / "broker_order_contract_validation" / "broker_order_contract_validation.json"
)
TRADE_RAW_COVERAGE_VALIDATION = (
    RESULT_DIR / "trade_raw_coverage_validation" / "trade_raw_coverage_validation.json"
)
BROKER_FILL_VALIDATION = RESULT_DIR / "broker_fill_validation" / "broker_fill_validation.json"
EXPORT_RAW_GUARD_VALIDATION = RESULT_DIR / "export_raw_guard_validation" / "export_raw_guard_validation.json"
CANDIDATE_DIR = Path("neural/models/jepa/jepa_production_event_options_dense15_strict_uniform_candidate")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads((PROJECT_ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def tail(text: str, max_lines: int = 60) -> str:
    lines = text.splitlines()
    return "\n".join(lines[-max_lines:])


def run_step(name: str, command: list[str], logs_dir: Path) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name.lower())
    stdout_path = logs_dir / f"{safe_name}.stdout.log"
    stderr_path = logs_dir / f"{safe_name}.stderr.log"
    stdout_path.write_text(result.stdout, encoding="utf-8")
    stderr_path.write_text(result.stderr, encoding="utf-8")
    return {
        "name": name,
        "command": command,
        "returncode": int(result.returncode),
        "passed": bool(result.returncode == 0),
        "stdout_log": str(stdout_path.relative_to(PROJECT_ROOT)),
        "stderr_log": str(stderr_path.relative_to(PROJECT_ROOT)),
        "stdout_tail": tail(result.stdout),
        "stderr_tail": tail(result.stderr),
    }


def assert_flag(payload: dict[str, Any], path: list[str], expected: Any, issues: list[str]) -> None:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict) or key not in current:
            issues.append("missing flag " + ".".join(path))
            return
        current = current[key]
    if current != expected:
        issues.append(f"{'.'.join(path)}={current!r} expected {expected!r}")


def write_markdown(output_dir: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Dense Candidate E2E Validation",
        "",
        f"- Passed: {payload['passed']}",
        f"- Generated at UTC: `{payload['generated_at_utc']}`",
        f"- Result dir: `{payload['result_dir']}`",
        f"- Candidate dir: `{payload['candidate_dir']}`",
        "",
        "## Steps",
        "",
        "| Step | Passed | Return Code |",
        "| --- | ---: | ---: |",
    ]
    for step in payload["steps"]:
        lines.append(f"| {step['name']} | {step['passed']} | {step['returncode']} |")
    lines += [
        "",
        "## Assertions",
        "",
        "```json",
        json.dumps(payload["assertions"], indent=2, allow_nan=True),
        "```",
    ]
    if payload["issues"]:
        lines += ["", "## Issues", "", *[f"- {issue}" for issue in payload["issues"]]]
    lines += [
        "",
        "## Logs",
        "",
    ]
    for step in payload["steps"]:
        lines.append(f"- {step['name']}: `{step['stdout_log']}`, `{step['stderr_log']}`")
    (output_dir / "E2E_VALIDATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run reproducible dense15 candidate validation suite.")
    parser.add_argument("--output-dir", default=str(RESULT_DIR / "e2e_validation"))
    parser.add_argument("--skip-regenerate", action="store_true", help="Only validate existing JSON artifacts.")
    args = parser.parse_args()

    output_dir = PROJECT_ROOT / Path(args.output_dir)
    logs_dir = output_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    py = sys.executable
    compile_targets = [
        "bots/tradingbot_wrapper_jepa.py",
        "neural/jepa/audit_dense_candidate_requirements.py",
        "neural/jepa/audit_dense_candidate_anti_snooping.py",
        "neural/jepa/audit_dense_candidate_pre2026_guard_selection.py",
        "neural/jepa/audit_dense_candidate_statistical_robustness.py",
        "neural/jepa/audit_event_option_research_selection.py",
        "neural/jepa/evaluate_dense_candidate_fixed_holdout.py",
        "neural/jepa/evaluate_dense_candidate_forward_freeze.py",
        "neural/jepa/evaluate_dense_candidate_partial_dataset.py",
        "neural/jepa/validate_bot_paper_order_intents.py",
        "neural/jepa/validate_bot_event_daily_loss_guard.py",
        "neural/jepa/validate_dense_candidate_paper_orders.py",
        "neural/jepa/validate_dense_candidate_broker_order_contract.py",
        "neural/jepa/validate_dense_candidate_trade_raw_coverage.py",
        "neural/jepa/validate_dense_candidate_broker_fill_evidence.py",
        "neural/jepa/validate_event_option_export_raw_guard.py",
        "neural/jepa/audit_thetadata_0dte_raw_coverage.py",
        "neural/jepa/verify_event_option_result.py",
        "neural/jepa/validate_dense_candidate_shadow_deployment.py",
        "neural/jepa/validate_dense_candidate_e2e.py",
    ]
    steps: list[tuple[str, list[str]]] = [
        ("py_compile", [py, "-m", "py_compile", *compile_targets]),
        ("json_policy", [py, "-m", "json.tool", str(CANDIDATE_DIR / "event_option_policy.json")]),
        ("json_registry", [py, "-m", "json.tool", str(CANDIDATE_DIR / "component_registry.json")]),
        ("json_partial_june", [py, "-m", "json.tool", str(PARTIAL_JUNE_EVAL)]),
        ("json_raw_thetadata_coverage", [py, "-m", "json.tool", str(RAW_THETADATA_COVERAGE)]),
        (
            "verify_main_202301_202605",
            [
                py,
                "neural/jepa/verify_event_option_result.py",
                "--result-dir",
                str(RESULT_DIR),
                "--start-month",
                "202301",
                "--end-month",
                "202605",
                "--tickers",
                "SPXW",
                "SPY",
                "QQQ",
                "--min-win-rate",
                "0.45",
                "--min-profit-factor",
                "1.30",
                "--min-month-trades",
                "18",
                "--disallow-weak-fold-modes",
            ],
        ),
        (
            "verify_main_raw_complete_202301_202604",
            [
                py,
                "neural/jepa/verify_event_option_result.py",
                "--result-dir",
                str(RESULT_DIR),
                "--start-month",
                "202301",
                "--end-month",
                "202604",
                "--exclude-months",
                "202403",
                "--tickers",
                "SPXW",
                "SPY",
                "QQQ",
                "--min-win-rate",
                "0.45",
                "--min-profit-factor",
                "1.30",
                "--min-month-trades",
                "18",
                "--disallow-weak-fold-modes",
                "--report-suffix",
                "raw_complete_202301_202604",
            ],
        ),
        (
            "verify_completed_2026",
            [
                py,
                "neural/jepa/verify_event_option_result.py",
                "--result-dir",
                str(WALKFORWARD_2026_DIR),
                "--start-month",
                "202601",
                "--end-month",
                "202605",
                "--tickers",
                "SPXW",
                "SPY",
                "QQQ",
                "--min-win-rate",
                "0.45",
                "--min-profit-factor",
                "1.30",
                "--min-month-trades",
                "18",
                "--disallow-weak-fold-modes",
            ],
        ),
        (
            "verify_raw_complete_2026",
            [
                py,
                "neural/jepa/verify_event_option_result.py",
                "--result-dir",
                str(WALKFORWARD_2026_DIR),
                "--start-month",
                "202601",
                "--end-month",
                "202604",
                "--tickers",
                "SPXW",
                "SPY",
                "QQQ",
                "--min-win-rate",
                "0.45",
                "--min-profit-factor",
                "1.30",
                "--min-month-trades",
                "18",
                "--disallow-weak-fold-modes",
                "--report-suffix",
                "raw_complete_202601_202604",
            ],
        ),
        (
            "verify_frozen_2025_to_2026",
            [
                py,
                "neural/jepa/verify_event_option_result.py",
                "--result-dir",
                str(FROZEN_2025_TO_2026_DIR),
                "--start-month",
                "202601",
                "--end-month",
                "202605",
                "--tickers",
                "SPXW",
                "SPY",
                "QQQ",
                "--min-win-rate",
                "0.45",
                "--min-profit-factor",
                "1.30",
                "--min-month-trades",
                "18",
                "--disallow-weak-fold-modes",
            ],
        ),
        (
            "verify_raw_complete_frozen_2025_to_2026",
            [
                py,
                "neural/jepa/verify_event_option_result.py",
                "--result-dir",
                str(FROZEN_2025_TO_2026_DIR),
                "--start-month",
                "202601",
                "--end-month",
                "202604",
                "--tickers",
                "SPXW",
                "SPY",
                "QQQ",
                "--min-win-rate",
                "0.45",
                "--min-profit-factor",
                "1.30",
                "--min-month-trades",
                "18",
                "--disallow-weak-fold-modes",
                "--report-suffix",
                "raw_complete_202601_202604",
            ],
        ),
        (
            "verify_guarded_frozen_2025_to_2026",
            [
                py,
                "neural/jepa/verify_event_option_result.py",
                "--result-dir",
                str(GUARDED_FROZEN_2025_TO_2026_DIR),
                "--start-month",
                "202601",
                "--end-month",
                "202605",
                "--tickers",
                "SPXW",
                "SPY",
                "QQQ",
                "--min-win-rate",
                "0.45",
                "--min-profit-factor",
                "1.30",
                "--min-month-trades",
                "18",
                "--disallow-weak-fold-modes",
            ],
        ),
        (
            "verify_guarded_raw_complete_2026",
            [
                py,
                "neural/jepa/verify_event_option_result.py",
                "--result-dir",
                str(GUARDED_FROZEN_2025_TO_2026_DIR),
                "--start-month",
                "202601",
                "--end-month",
                "202604",
                "--tickers",
                "SPXW",
                "SPY",
                "QQQ",
                "--min-win-rate",
                "0.45",
                "--min-profit-factor",
                "1.30",
                "--min-month-trades",
                "18",
                "--disallow-weak-fold-modes",
                "--report-suffix",
                "raw_complete_202601_202604",
            ],
        ),
        (
            "curve_guarded_raw_complete_2026",
            [
                py,
                "neural/jepa/analyze_event_option_curve_health.py",
                "--result-dir",
                str(GUARDED_FROZEN_2025_TO_2026_DIR),
                "--start-month",
                "202601",
                "--end-month",
                "202604",
                "--risk-capital",
                "5000",
            ],
        ),
        (
            "verify_fixed_holdout_may",
            [
                py,
                "neural/jepa/verify_event_option_result.py",
                "--result-dir",
                str(FIXED_HOLDOUT_MAY_DIR),
                "--start-month",
                "202605",
                "--end-month",
                "202605",
                "--tickers",
                "SPXW",
                "SPY",
                "QQQ",
                "--min-win-rate",
                "0.45",
                "--min-profit-factor",
                "1.30",
                "--min-month-trades",
                "18",
                "--disallow-weak-fold-modes",
            ],
        ),
    ]
    if not args.skip_regenerate:
        steps.extend(
            [
                ("bot_paper_order_intents", [py, "neural/jepa/validate_bot_paper_order_intents.py"]),
                ("bot_event_daily_loss_guard", [py, "neural/jepa/validate_bot_event_daily_loss_guard.py"]),
                ("paper_order_validation", [py, "neural/jepa/validate_dense_candidate_paper_orders.py"]),
                ("broker_order_contract_validation", [py, "neural/jepa/validate_dense_candidate_broker_order_contract.py"]),
                ("trade_raw_coverage_validation", [py, "neural/jepa/validate_dense_candidate_trade_raw_coverage.py"]),
                (
                    "broker_fill_evidence_validation",
                    [py, "neural/jepa/validate_dense_candidate_broker_fill_evidence.py", "--exit-zero-on-fail"],
                ),
                (
                    "export_raw_guard_validation",
                    [py, "neural/jepa/validate_event_option_export_raw_guard.py"],
                ),
                (
                    "forward_freeze_evaluation",
                    [
                        py,
                        "neural/jepa/evaluate_dense_candidate_forward_freeze.py",
                        "--output-dir",
                        str(FORWARD_EVALUATION_DIR),
                        "--start-month",
                        "202607",
                        "--strict-features",
                    ],
                ),
                (
                    "strict_research_selection_audit",
                    [
                        py,
                        "neural/jepa/audit_event_option_research_selection.py",
                        "--result-dir",
                        str(RESULT_DIR),
                        "--start-month",
                        "202301",
                        "--end-month",
                        "202605",
                        "--strict",
                        "--manifest",
                        "research_papers/JEPA/results/event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_forward_freeze_202607_v1/research_selection_manifest.json",
                        "--report-dir",
                        str(RESULT_DIR / "research_selection_audit_strict"),
                        "--exit-zero-on-failed-audit",
                    ],
                ),
                (
                    "pre2026_guard_selection_audit",
                    [py, "neural/jepa/audit_dense_candidate_pre2026_guard_selection.py"],
                ),
                (
                    "guarded_strict_research_selection_audit",
                    [
                        py,
                        "neural/jepa/audit_event_option_research_selection.py",
                        "--result-dir",
                        str(GUARDED_FROZEN_2025_TO_2026_DIR),
                        "--start-month",
                        "202601",
                        "--end-month",
                        "202604",
                        "--strict",
                        "--report-dir",
                        str(GUARDED_FROZEN_2025_TO_2026_DIR / "research_selection_audit_strict"),
                    ],
                ),
                (
                    "anti_snooping_audit",
                    [py, "neural/jepa/audit_dense_candidate_anti_snooping.py", "--exit-zero-on-failed-audit"],
                ),
                (
                    "guarded_statistical_robustness",
                    [py, "neural/jepa/audit_dense_candidate_statistical_robustness.py", "--exit-zero-on-fail"],
                ),
                (
                    "requirement_audit",
                    [py, "neural/jepa/audit_dense_candidate_requirements.py", "--exit-zero-on-incomplete-objective"],
                ),
                ("shadow_deployment_validation", [py, "neural/jepa/validate_dense_candidate_shadow_deployment.py"]),
            ]
        )
    steps.extend(
        [
            ("json_requirement_audit", [py, "-m", "json.tool", str(RESULT_DIR / "requirement_audit/requirement_audit.json")]),
            ("json_anti_snooping_audit", [py, "-m", "json.tool", str(RESULT_DIR / "anti_snooping_audit/anti_snooping_audit.json")]),
            ("json_guarded_statistical_robustness", [py, "-m", "json.tool", str(GUARDED_STATISTICAL_ROBUSTNESS)]),
            (
                "json_shadow_validation",
                [py, "-m", "json.tool", str(RESULT_DIR / "shadow_deployment_validation/shadow_deployment_validation.json")],
            ),
            ("json_paper_order_validation", [py, "-m", "json.tool", str(PAPER_ORDER_VALIDATION)]),
            ("json_bot_paper_order_intents", [py, "-m", "json.tool", str(BOT_PAPER_ORDER_INTENT_VALIDATION)]),
            ("json_bot_daily_loss_guard", [py, "-m", "json.tool", str(BOT_DAILY_LOSS_GUARD_VALIDATION)]),
            ("json_broker_order_contract", [py, "-m", "json.tool", str(BROKER_ORDER_CONTRACT_VALIDATION)]),
            ("json_trade_raw_coverage", [py, "-m", "json.tool", str(TRADE_RAW_COVERAGE_VALIDATION)]),
            ("json_broker_fill_validation", [py, "-m", "json.tool", str(BROKER_FILL_VALIDATION)]),
            ("json_export_raw_guard_validation", [py, "-m", "json.tool", str(EXPORT_RAW_GUARD_VALIDATION)]),
        ]
    )

    step_results = [run_step(name, command, logs_dir) for name, command in steps]
    issues = [
        f"{step['name']} failed with return code {step['returncode']}"
        for step in step_results
        if not step["passed"]
    ]

    requirement = read_json(RESULT_DIR / "requirement_audit/requirement_audit.json")
    anti_snooping = read_json(RESULT_DIR / "anti_snooping_audit/anti_snooping_audit.json")
    shadow = read_json(RESULT_DIR / "shadow_deployment_validation/shadow_deployment_validation.json")
    partial = read_json(PARTIAL_JUNE_EVAL)
    paper_order = read_json(PAPER_ORDER_VALIDATION)
    bot_paper = read_json(BOT_PAPER_ORDER_INTENT_VALIDATION)
    bot_daily_loss_guard = read_json(BOT_DAILY_LOSS_GUARD_VALIDATION)
    broker_order_contract = read_json(BROKER_ORDER_CONTRACT_VALIDATION)
    trade_raw_coverage = read_json(TRADE_RAW_COVERAGE_VALIDATION)
    broker_fill = read_json(BROKER_FILL_VALIDATION)
    export_raw_guard = read_json(EXPORT_RAW_GUARD_VALIDATION)
    guarded_statistical_robustness = read_json(GUARDED_STATISTICAL_ROBUSTNESS)
    raw_coverage = (
        requirement.get("evidence", {}).get("raw_thetadata_coverage", {})
        if isinstance(requirement.get("evidence"), dict)
        else {}
    )
    assert_flag(requirement, ["metric_walkforward_objective_passed"], True, issues)
    assert_flag(requirement, ["causal_research_walkforward_passed"], True, issues)
    assert_flag(requirement, ["requested_walkforward_objective_passed"], True, issues)
    assert_flag(requirement, ["objective_checks", "guarded_raw_complete_2026"], True, issues)
    assert_flag(requirement, ["objective_checks", "guarded_raw_complete_2026_curve"], True, issues)
    assert_flag(requirement, ["objective_checks", "guarded_strict_research_selection_audit"], True, issues)
    assert_flag(requirement, ["objective_checks", "guarded_anti_snooping_audit"], True, issues)
    assert_flag(requirement, ["objective_checks", "bot_daily_loss_guard_runtime"], True, issues)
    assert_flag(requirement, ["objective_checks", "broker_order_contract_validation"], True, issues)
    assert_flag(requirement, ["objective_checks", "trade_raw_coverage_validation"], True, issues)
    assert_flag(requirement, ["broad_historical_diagnostic_checks", "completed_2026_walkforward"], True, issues)
    assert_flag(requirement, ["broad_historical_diagnostic_checks", "raw_complete_2026_walkforward"], True, issues)
    assert_flag(requirement, ["broad_historical_diagnostic_checks", "broad_raw_complete_walkforward"], True, issues)
    assert_flag(requirement, ["broad_historical_diagnostic_checks", "frozen_2025_to_2026"], True, issues)
    assert_flag(requirement, ["broad_historical_diagnostic_checks", "raw_complete_frozen_2025_to_2026"], True, issues)
    assert_flag(requirement, ["broad_historical_diagnostic_checks", "frozen_2025_to_2026_lineage"], True, issues)
    assert_flag(requirement, ["broad_historical_diagnostic_checks", "guarded_frozen_2025_to_2026_full_month_diagnostic"], True, issues)
    assert_flag(requirement, ["broad_historical_diagnostic_checks", "guarded_frozen_2025_to_2026_full_curve_diagnostic"], False, issues)
    assert_flag(requirement, ["broad_historical_diagnostic_checks", "fixed_holdout_may2026"], True, issues)
    assert_flag(requirement, ["broad_historical_diagnostic_checks", "guarded_statistical_robustness"], False, issues)
    assert_flag(requirement, ["evidence", "guarded_statistical_robustness", "checks", "observed_gate_passed"], True, issues)
    assert_flag(requirement, ["evidence", "guarded_statistical_robustness", "checks", "leave_one_month_out_passed"], True, issues)
    assert_flag(requirement, ["evidence", "guarded_statistical_robustness", "checks", "bootstrap_lower_quantile_passed"], False, issues)
    assert_flag(requirement, ["evidence", "guarded_statistical_robustness", "checks", "top_winner_stress_passed"], False, issues)
    assert_flag(guarded_statistical_robustness, ["passed"], False, issues)
    assert_flag(requirement, ["broad_historical_diagnostic_checks", "broad_historical_anti_snooping_audit"], False, issues)
    assert_flag(anti_snooping, ["checks", "historical_fold_chronology"], True, issues)
    assert_flag(anti_snooping, ["checks", "pre2026_guard_selection"], True, issues)
    assert_flag(anti_snooping, ["checks", "model_feature_leakage"], True, issues)
    assert_flag(anti_snooping, ["checks", "strict_research_selection"], False, issues)
    assert_flag(requirement, ["live_ready_passed"], False, issues)
    assert_flag(requirement, ["live_ready_checks", "paper_order_payload_validation"], True, issues)
    assert_flag(requirement, ["live_ready_checks", "bot_daily_loss_guard_runtime"], True, issues)
    assert_flag(requirement, ["live_ready_checks", "broker_order_contract_validation"], True, issues)
    assert_flag(requirement, ["live_ready_checks", "trade_raw_coverage_validation"], True, issues)
    assert_flag(requirement, ["live_ready_checks", "broker_fill_validation"], False, issues)
    assert_flag(requirement, ["evidence", "broker_fill_validation", "passed"], False, issues)
    assert_flag(requirement, ["evidence", "raw_thetadata_coverage", "available"], True, issues)
    assert_flag(requirement, ["evidence", "raw_thetadata_coverage", "official_forward_evidence"], False, issues)
    assert_flag(requirement, ["evidence", "raw_thetadata_coverage", "true_zero_dte_filter"], True, issues)
    assert_flag(requirement, ["evidence", "forward_evaluation", "raw_thetadata_coverage", "available"], True, issues)
    assert_flag(requirement, ["evidence", "forward_evaluation", "raw_thetadata_coverage", "true_zero_dte_filter"], True, issues)
    assert_flag(shadow, ["passed"], True, issues)
    assert_flag(shadow, ["production_policy_guard_rejects_candidate"], True, issues)
    assert_flag(shadow, ["production_registry_guard_rejects_candidate"], True, issues)
    assert_flag(partial, ["official_forward_evidence"], False, issues)
    assert_flag(paper_order, ["passed"], True, issues)
    assert_flag(bot_paper, ["passed"], True, issues)
    assert_flag(bot_daily_loss_guard, ["passed"], True, issues)
    assert_flag(broker_order_contract, ["passed"], True, issues)
    assert_flag(trade_raw_coverage, ["passed"], True, issues)
    assert_flag(broker_fill, ["passed"], False, issues)
    assert_flag(broker_fill, ["broker_submission_evidence"], False, issues)
    assert_flag(export_raw_guard, ["passed"], True, issues)
    assert_flag(export_raw_guard, ["checks", "reject_partial_202605"], True, issues)
    assert_flag(export_raw_guard, ["checks", "allow_raw_complete_202601_202604"], True, issues)
    raw_latest = raw_coverage.get("latest_common_date_all_tickers")
    if not raw_latest or str(raw_latest) < "20260626":
        issues.append(f"raw coverage latest_common_date_all_tickers={raw_latest!r} expected >= '20260626'")
    raw_partial_months = [str(month) for month in raw_coverage.get("partial_months", [])]
    if "202605" not in raw_partial_months or "202606" not in raw_partial_months:
        issues.append(f"raw coverage partial_months missing 202605/202606: {raw_partial_months!r}")
    raw_completed_months = [str(month) for month in raw_coverage.get("completed_months", [])]
    future_completed = [month for month in raw_completed_months if month >= "202607"]
    if future_completed:
        issues.append(f"raw coverage has unexpected completed >=202607 months: {future_completed!r}")

    payload = {
        "schema_version": 1,
        "validation": "dense_candidate_e2e",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "passed": not issues,
        "result_dir": str(RESULT_DIR),
        "candidate_dir": str(CANDIDATE_DIR),
        "steps": step_results,
        "assertions": {
            "metric_walkforward_objective_passed": requirement.get("metric_walkforward_objective_passed"),
            "causal_research_walkforward_passed": requirement.get("causal_research_walkforward_passed"),
            "requested_walkforward_objective_passed": requirement.get("requested_walkforward_objective_passed"),
            "guarded_raw_complete_2026": requirement.get("objective_checks", {}).get("guarded_raw_complete_2026"),
            "guarded_raw_complete_2026_curve": requirement.get("objective_checks", {}).get("guarded_raw_complete_2026_curve"),
            "guarded_strict_research_selection_audit": requirement.get("objective_checks", {}).get(
                "guarded_strict_research_selection_audit"
            ),
            "guarded_anti_snooping_audit": requirement.get("objective_checks", {}).get("guarded_anti_snooping_audit"),
            "broad_historical_anti_snooping_audit": requirement.get("broad_historical_diagnostic_checks", {}).get(
                "broad_historical_anti_snooping_audit"
            ),
            "anti_snooping_pre2026_guard_selection": anti_snooping.get("checks", {}).get("pre2026_guard_selection"),
            "anti_snooping_strict_research_selection": anti_snooping.get("checks", {}).get("strict_research_selection"),
            "live_ready_passed": requirement.get("live_ready_passed"),
            "completed_2026_walkforward_diagnostic": requirement.get("broad_historical_diagnostic_checks", {}).get(
                "completed_2026_walkforward"
            ),
            "raw_complete_2026_walkforward_diagnostic": requirement.get("broad_historical_diagnostic_checks", {}).get(
                "raw_complete_2026_walkforward"
            ),
            "broad_raw_complete_walkforward_diagnostic": requirement.get("broad_historical_diagnostic_checks", {}).get(
                "broad_raw_complete_walkforward"
            ),
            "frozen_2025_to_2026_diagnostic": requirement.get("broad_historical_diagnostic_checks", {}).get(
                "frozen_2025_to_2026"
            ),
            "raw_complete_frozen_2025_to_2026_diagnostic": requirement.get(
                "broad_historical_diagnostic_checks", {}
            ).get("raw_complete_frozen_2025_to_2026"),
            "frozen_2025_to_2026_lineage_diagnostic": requirement.get("broad_historical_diagnostic_checks", {}).get(
                "frozen_2025_to_2026_lineage"
            ),
            "guarded_full_month_diagnostic": requirement.get("broad_historical_diagnostic_checks", {}).get(
                "guarded_frozen_2025_to_2026_full_month_diagnostic"
            ),
            "guarded_full_curve_diagnostic": requirement.get("broad_historical_diagnostic_checks", {}).get(
                "guarded_frozen_2025_to_2026_full_curve_diagnostic"
            ),
            "fixed_holdout_may2026_diagnostic": requirement.get("broad_historical_diagnostic_checks", {}).get(
                "fixed_holdout_may2026"
            ),
            "guarded_statistical_robustness_passed": requirement.get("broad_historical_diagnostic_checks", {}).get(
                "guarded_statistical_robustness"
            ),
            "guarded_statistical_observed_gate_passed": requirement.get("evidence", {}).get("guarded_statistical_robustness", {}).get("checks", {}).get("observed_gate_passed"),
            "guarded_statistical_leave_one_month_out_passed": requirement.get("evidence", {}).get("guarded_statistical_robustness", {}).get("checks", {}).get("leave_one_month_out_passed"),
            "guarded_statistical_bootstrap_lower_quantile_passed": requirement.get("evidence", {}).get("guarded_statistical_robustness", {}).get("checks", {}).get("bootstrap_lower_quantile_passed"),
            "guarded_statistical_top_winner_stress_passed": requirement.get("evidence", {}).get("guarded_statistical_robustness", {}).get("checks", {}).get("top_winner_stress_passed"),
            "bot_daily_loss_guard_runtime": requirement.get("objective_checks", {}).get("bot_daily_loss_guard_runtime"),
            "broker_order_contract_validation": requirement.get("objective_checks", {}).get("broker_order_contract_validation"),
            "trade_raw_coverage_validation": requirement.get("objective_checks", {}).get("trade_raw_coverage_validation"),
            "broker_fill_validation_live_ready": requirement.get("live_ready_checks", {}).get("broker_fill_validation"),
            "raw_thetadata_coverage_available": raw_coverage.get("available"),
            "raw_thetadata_schema_version": raw_coverage.get("schema_version"),
            "raw_thetadata_true_zero_dte_filter": raw_coverage.get("true_zero_dte_filter"),
            "raw_thetadata_latest_common_date": raw_coverage.get("latest_common_date_all_tickers"),
            "raw_thetadata_partial_months": raw_coverage.get("partial_months"),
            "raw_thetadata_official_forward_evidence": raw_coverage.get("official_forward_evidence"),
            "paper_order_payload_validation": requirement.get("live_ready_checks", {}).get("paper_order_payload_validation"),
            "shadow_passed": shadow.get("passed"),
            "production_policy_guard_rejects_candidate": shadow.get("production_policy_guard_rejects_candidate"),
            "production_registry_guard_rejects_candidate": shadow.get("production_registry_guard_rejects_candidate"),
            "partial_june_official_forward_evidence": partial.get("official_forward_evidence"),
            "paper_order_validation_passed": paper_order.get("passed"),
            "bot_paper_order_intents_passed": bot_paper.get("passed"),
            "bot_daily_loss_guard_passed": bot_daily_loss_guard.get("passed"),
            "broker_order_contract_passed": broker_order_contract.get("passed"),
            "trade_raw_coverage_passed": trade_raw_coverage.get("passed"),
            "trade_raw_coverage_records": trade_raw_coverage.get("records_checked"),
            "broker_fill_validation_passed": broker_fill.get("passed"),
            "broker_fill_fills_checked": broker_fill.get("fills_checked"),
            "broker_fill_submission_evidence": broker_fill.get("broker_submission_evidence"),
            "broker_fill_expected_orders": broker_fill.get("expected_orders"),
            "export_raw_guard_passed": export_raw_guard.get("passed"),
            "export_raw_guard_reject_partial_202605": export_raw_guard.get("checks", {}).get("reject_partial_202605"),
            "export_raw_guard_allow_raw_complete": export_raw_guard.get("checks", {}).get("allow_raw_complete_202601_202604"),
        },
        "issues": issues,
    }
    (output_dir / "e2e_validation.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    write_markdown(output_dir, payload)
    print(json.dumps(payload, indent=2, allow_nan=True))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

