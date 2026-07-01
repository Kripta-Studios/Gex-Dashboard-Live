from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.event_option_component_live import EventOptionComponentRegistry


DEFAULT_CANDIDATE_DIR = Path("neural/models/jepa/jepa_production_event_options_dense15_strict_uniform_candidate")
DEFAULT_RESULT_DIR = Path(
    "research_papers/JEPA/results/"
    "event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_causal_2023_2026_v1"
)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def is_live_ready_status(value: object) -> bool:
    text = str(value).lower()
    return bool("live_ready" in text and "research" not in text and "candidate" not in text and "not_live_ready" not in text)


def production_policy_guard_would_accept(policy: dict[str, Any]) -> bool:
    live_contract = policy.get("live_contract") if isinstance(policy.get("live_contract"), dict) else {}
    return bool(is_live_ready_status(policy.get("status", "")) and live_contract.get("event_option_live_ready") is True)


def production_registry_guard_would_accept(registry: dict[str, Any]) -> bool:
    return bool(is_live_ready_status(registry.get("status", "")))


def check_json_bool(path: Path, keys: list[str]) -> tuple[bool, dict[str, Any]]:
    payload = read_json(path)
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return False, payload
        current = current.get(key)
    return bool(current), payload


def systemd_candidate_path_check(paths: list[Path], candidate_dir: Path) -> dict[str, Any]:
    needle = str(candidate_dir).replace("\\", "/")
    issues: list[str] = []
    checked: list[str] = []
    for path in paths:
        if not path.exists():
            issues.append(f"missing {path}")
            continue
        checked.append(str(path))
        text = path.read_text(encoding="utf-8", errors="ignore").replace("\\", "/")
        if needle in text or candidate_dir.name in text:
            issues.append(f"{path} references candidate package")
    return {"passed": not issues, "checked": checked, "issues": issues}


def write_markdown(output_dir: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Dense Candidate Shadow Deployment Validation",
        "",
        f"- Passed: {payload['passed']}",
        f"- Candidate package: `{payload['candidate_dir']}`",
        f"- Policy status: `{payload['policy_status']}`",
        f"- Registry status: `{payload['registry_status']}`",
        f"- Production policy guard rejects candidate: `{payload['production_policy_guard_rejects_candidate']}`",
        f"- Production registry guard rejects candidate: `{payload['production_registry_guard_rejects_candidate']}`",
        "",
        "## Checks",
        "",
        "```json",
        json.dumps(payload["checks"], indent=2, allow_nan=True),
        "```",
        "",
        "## Evidence",
        "",
        "```json",
        json.dumps(payload["evidence"], indent=2, allow_nan=True),
        "```",
    ]
    if payload["issues"]:
        lines += ["", "## Issues", "", *[f"- {issue}" for issue in payload["issues"]]]
    (output_dir / "SHADOW_DEPLOYMENT_VALIDATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate dense15 candidate as shadow-only deployment package.")
    parser.add_argument("--candidate-dir", default=str(DEFAULT_CANDIDATE_DIR))
    parser.add_argument("--result-dir", default=str(DEFAULT_RESULT_DIR))
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--policy", default="")
    parser.add_argument("--registry", default="")
    parser.add_argument(
        "--systemd-units",
        nargs="*",
        default=["systemd/ai_bot.service", "systemd/realtime_feed.service"],
    )
    args = parser.parse_args()

    candidate_dir = Path(args.candidate_dir)
    result_dir = Path(args.result_dir)
    output_dir = Path(args.output_dir) if args.output_dir else result_dir / "shadow_deployment_validation"
    output_dir.mkdir(parents=True, exist_ok=True)

    policy_path = Path(args.policy) if str(args.policy).strip() else candidate_dir / "event_option_policy.json"
    registry_path = Path(args.registry) if str(args.registry).strip() else candidate_dir / "component_registry.json"
    policy = read_json(policy_path)
    registry_payload = read_json(registry_path)
    registry = EventOptionComponentRegistry.from_path(registry_path, require_complete_live_equivalence=False)
    registry_summary = registry.summary()

    requirement_audit_path = result_dir / "requirement_audit" / "requirement_audit.json"
    runtime_replay_path = result_dir / "runtime_policy_replay" / "runtime_policy_replay_summary.json"
    batch_smoke_path = result_dir / "snapshot_to_order_batch_smoke" / "snapshot_to_order_batch_smoke.json"
    offline_fill_path = result_dir / "offline_fill_simulation" / "offline_fill_simulation.json"
    paper_order_path = result_dir / "paper_order_validation" / "paper_order_validation.json"
    bot_paper_order_path = result_dir / "bot_paper_order_intent_validation" / "bot_paper_order_intent_validation.json"
    broker_order_contract_path = result_dir / "broker_order_contract_validation" / "broker_order_contract_validation.json"

    requirement_metric_ok, requirement_payload = check_json_bool(requirement_audit_path, ["metric_walkforward_objective_passed"])
    requested_objective_complete = bool(requirement_payload.get("requested_walkforward_objective_passed", False))
    live_ready_complete = bool(requirement_payload.get("live_ready_passed", False))
    runtime_ok, runtime_payload = check_json_bool(runtime_replay_path, ["passed"])
    batch_ok, batch_payload = check_json_bool(batch_smoke_path, ["passed"])
    offline_payload = read_json(offline_fill_path)
    offline_ok = bool(
        offline_payload.get("market_data_path_passed", offline_payload.get("passed", False))
        and offline_payload.get("strict_execution_cost_passed", False)
    )
    paper_order_payload = read_json(paper_order_path)
    paper_order_ok = bool(paper_order_payload.get("passed", False))
    bot_paper_order_payload = read_json(bot_paper_order_path)
    bot_paper_order_ok = bool(bot_paper_order_payload.get("passed", False))
    broker_order_contract_payload = read_json(broker_order_contract_path)
    broker_order_contract_ok = bool(broker_order_contract_payload.get("passed", False))

    policy_guard_accepts = production_policy_guard_would_accept(policy)
    registry_guard_accepts = production_registry_guard_would_accept(registry_payload)
    systemd_check = systemd_candidate_path_check([Path(item) for item in args.systemd_units], candidate_dir)
    live_contract = policy.get("live_contract") if isinstance(policy.get("live_contract"), dict) else {}

    checks = {
        "policy_exists": policy_path.exists(),
        "registry_exists": registry_path.exists(),
        "registry_loads_shadow_mode": bool(registry_summary.get("component_count", 0) > 0),
        "policy_marked_not_live_ready": not production_policy_guard_would_accept(policy),
        "registry_marked_not_live_ready": not production_registry_guard_would_accept(registry_payload),
        "policy_live_contract_not_live_ready": live_contract.get("event_option_live_ready") is not True,
        "production_systemd_units_do_not_reference_candidate": bool(systemd_check["passed"]),
        "metric_walkforward_objective_passed": requirement_metric_ok,
        "live_ready_remains_incomplete": not live_ready_complete,
        "runtime_replay_passed": runtime_ok,
        "batch_snapshot_to_order_passed": batch_ok,
        "offline_fill_market_and_cost_passed": offline_ok,
        "paper_order_payload_validation_passed": paper_order_ok,
        "bot_paper_order_intents_passed": bot_paper_order_ok,
        "broker_order_contract_validation_passed": broker_order_contract_ok,
    }
    issues: list[str] = []
    for key, value in checks.items():
        if not bool(value):
            issues.append(f"{key}=false")
    issues.extend(str(item) for item in systemd_check.get("issues", []))

    payload = {
        "schema_version": 1,
        "validation": "dense_candidate_shadow_deployment",
        "passed": not issues,
        "candidate_dir": str(candidate_dir),
        "policy_path": str(policy_path),
        "registry_path": str(registry_path),
        "policy_status": policy.get("status"),
        "registry_status": registry_payload.get("status"),
        "registry_summary": registry_summary,
        "production_policy_guard_rejects_candidate": not policy_guard_accepts,
        "production_registry_guard_rejects_candidate": not registry_guard_accepts,
        "checks": checks,
        "evidence": {
            "requirement_audit": {
                "path": str(requirement_audit_path),
                "metric_walkforward_objective_passed": requirement_metric_ok,
                "requested_walkforward_objective_passed": requested_objective_complete,
                "live_ready_passed": live_ready_complete,
                "objective_checks": requirement_payload.get("objective_checks", {}),
                "live_ready_checks": requirement_payload.get("live_ready_checks", {}),
            },
            "runtime_replay": {
                "path": str(runtime_replay_path),
                "passed": runtime_ok,
                "comparisons": runtime_payload.get("comparisons", []),
            },
            "batch_snapshot_to_order": {
                "path": str(batch_smoke_path),
                "passed": batch_ok,
                "passed_cases": batch_payload.get("passed_cases"),
                "total_cases": batch_payload.get("total_cases"),
            },
            "offline_fill_simulation": {
                "path": str(offline_fill_path),
                "passed": offline_ok,
                "total_orders": offline_payload.get("total_orders"),
                "passed_orders": offline_payload.get("passed_orders"),
                "entry_limit_covers_ask_orders": offline_payload.get("entry_limit_covers_ask_orders"),
            },
            "paper_order_validation": {
                "path": str(paper_order_path),
                "passed": paper_order_ok,
                "total_orders": paper_order_payload.get("total_orders"),
                "passed_orders": paper_order_payload.get("passed_orders"),
                "risk_capital": paper_order_payload.get("risk_capital"),
            },
            "bot_paper_order_intents": {
                "path": str(bot_paper_order_path),
                "passed": bot_paper_order_ok,
                "total_orders": bot_paper_order_payload.get("total_orders"),
                "passed_orders": bot_paper_order_payload.get("passed_orders"),
            },
            "broker_order_contract_validation": {
                "path": str(broker_order_contract_path),
                "passed": broker_order_contract_ok,
                "total_orders": broker_order_contract_payload.get("total_orders"),
                "passed_orders": broker_order_contract_payload.get("passed_orders"),
                "broker_submission_performed": broker_order_contract_payload.get("broker_submission_performed"),
                "live_fill_evidence": broker_order_contract_payload.get("live_fill_evidence"),
            },
            "systemd_units": systemd_check,
        },
        "issues": issues,
    }
    (output_dir / "shadow_deployment_validation.json").write_text(
        json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8"
    )
    write_markdown(output_dir, payload)
    print(json.dumps(payload, indent=2, allow_nan=True))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

