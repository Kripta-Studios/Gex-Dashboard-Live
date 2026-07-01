from __future__ import annotations

import argparse
import json
import shutil
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
GUARDED_RESULT_DIR = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "dense_candidate_frozen2025_2026_daily_guard_l4p1_vp0"
)
RAW_THETADATA_COVERAGE = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "thetadata_0dte_raw_coverage_spxw_spy_qqq/raw_coverage.json"
)
DEFAULT_OUTPUT_DIR = RESULT_DIR / "export_raw_guard_validation"


def tail(text: str, max_lines: int = 40) -> str:
    return "\n".join(text.splitlines()[-max_lines:])


def assert_under_project(path: Path) -> Path:
    resolved = path.resolve()
    root = PROJECT_ROOT.resolve()
    if root != resolved and root not in resolved.parents:
        raise RuntimeError(f"refusing to use path outside project root: {resolved}")
    return resolved


def remove_tree(path: Path) -> None:
    resolved = assert_under_project(path)
    if resolved.exists():
        shutil.rmtree(resolved)


def run_export(args: argparse.Namespace, end_month: str, tmp_dir: Path) -> dict[str, Any]:
    command = [
        sys.executable,
        "neural/jepa/export_event_option_production_policy.py",
        "--result-dir",
        str(args.result_dir),
        "--partial-result-dir",
        str(args.partial_result_dir),
        "--freeze-dir",
        str(args.freeze_dir),
        "--output-dir",
        str(tmp_dir),
        "--completed-start-month",
        str(args.completed_start_month),
        "--completed-end-month",
        str(end_month),
        "--raw-thetadata-coverage",
        str(args.raw_thetadata_coverage),
    ]
    result = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True, check=False)
    return {
        "command": command,
        "returncode": int(result.returncode),
        "stdout_tail": tail(result.stdout),
        "stderr_tail": tail(result.stderr),
        "combined_tail": tail(result.stdout + "\n" + result.stderr),
    }


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def write_markdown(output_dir: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Event-Option Export Raw Coverage Guard Validation",
        "",
        f"- Passed: `{payload['passed']}`",
        f"- Generated at UTC: `{payload['generated_at_utc']}`",
        f"- Reject partial `202605`: `{payload['checks']['reject_partial_202605']}`",
        f"- Allow raw-complete `202601..202604`: `{payload['checks']['allow_raw_complete_202601_202604']}`",
        "",
    ]
    if payload["issues"]:
        lines += ["## Issues", ""]
        lines.extend(f"- {issue}" for issue in payload["issues"])
        lines.append("")
    lines += [
        "## Scope",
        "",
        "This validates the export-time completed-month guard only. It does not mark the event-option package live-ready.",
    ]
    (output_dir / "EXPORT_RAW_GUARD_VALIDATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate export-time raw completed-month guard for event-option policies.")
    parser.add_argument("--result-dir", default=str(GUARDED_RESULT_DIR))
    parser.add_argument("--partial-result-dir", default=str(GUARDED_RESULT_DIR))
    parser.add_argument("--freeze-dir", default=str(GUARDED_RESULT_DIR))
    parser.add_argument("--raw-thetadata-coverage", default=str(RAW_THETADATA_COVERAGE))
    parser.add_argument("--completed-start-month", default="202601")
    parser.add_argument("--partial-end-month", default="202605")
    parser.add_argument("--raw-complete-end-month", default="202604")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    output_dir = PROJECT_ROOT / Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = output_dir / "_tmp_export_policy"
    remove_tree(tmp_dir)

    issues: list[str] = []
    reject = run_export(args, str(args.partial_end_month), tmp_dir)
    reject_text = str(reject.get("combined_tail", ""))
    reject_ok = bool(
        reject["returncode"] != 0
        and str(args.partial_end_month) in reject_text
        and "not completed in raw all-ticker 0DTE coverage" in reject_text
    )
    if not reject_ok:
        issues.append(
            f"export did not reject partial month {args.partial_end_month}: "
            f"returncode={reject['returncode']} tail={reject_text!r}"
        )
    remove_tree(tmp_dir)

    allow = run_export(args, str(args.raw_complete_end_month), tmp_dir)
    policy_path = tmp_dir / "event_option_policy.json"
    allow_policy: dict[str, Any] = {}
    allow_ok = bool(allow["returncode"] == 0 and policy_path.exists())
    if allow_ok:
        allow_policy = read_json(policy_path)
        validation = allow_policy.get("completed_month_validation", {})
        months = [str(month) for month in validation.get("months", [])]
        raw_summary = validation.get("raw_thetadata_coverage") if isinstance(validation, dict) else None
        if str(args.partial_end_month) in months:
            allow_ok = False
            issues.append(f"raw-complete export unexpectedly includes {args.partial_end_month}")
        if str(args.raw_complete_end_month) not in months:
            allow_ok = False
            issues.append(f"raw-complete export missing {args.raw_complete_end_month}")
        if not isinstance(raw_summary, dict) or int(raw_summary.get("schema_version", 0) or 0) < 2:
            allow_ok = False
            issues.append("raw-complete export missing schema v2 raw_thetadata_coverage summary")
    else:
        issues.append(
            f"export did not allow raw-complete end month {args.raw_complete_end_month}: "
            f"returncode={allow['returncode']} tail={allow.get('combined_tail')!r}"
        )
    remove_tree(tmp_dir)

    payload = {
        "schema_version": 1,
        "validation": "event_option_export_raw_guard",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "passed": bool(not issues and reject_ok and allow_ok),
        "result_dir": str(args.result_dir),
        "raw_thetadata_coverage": str(args.raw_thetadata_coverage),
        "checks": {
            "reject_partial_202605": reject_ok,
            "allow_raw_complete_202601_202604": allow_ok,
        },
        "reject_partial_result": reject,
        "allow_raw_complete_result": allow,
        "allow_completed_months": (
            allow_policy.get("completed_month_validation", {}).get("months", []) if allow_policy else []
        ),
        "not_covered": [
            "broker or exchange fills",
            "future completed-month forward evidence",
            "full production live readiness",
        ],
        "issues": issues,
    }
    (output_dir / "export_raw_guard_validation.json").write_text(
        json.dumps(payload, indent=2, allow_nan=True) + "\n", encoding="utf-8"
    )
    write_markdown(output_dir, payload)
    print(json.dumps(payload, indent=2, allow_nan=True))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())