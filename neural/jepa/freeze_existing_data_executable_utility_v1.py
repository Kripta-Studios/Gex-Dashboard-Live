"""Freeze the exact E0/E1 executable-utility outer runner before outcomes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from neural.jepa.audit_existing_data_edge_join_inventory_v1 import ROOT, sha256_file
from neural.jepa.evaluate_existing_data_executable_utility_v1 import (
    BUILD_SUMMARY,
    MASTER,
    OUTER_MONTHS,
    runner_protocol,
    runner_protocol_sha256,
)
from neural.jepa.existing_data_edge_alternative_v1 import frozen_spec as huber_spec
from neural.jepa.existing_data_edge_alternative_v1 import frozen_spec_sha256 as huber_sha
from neural.jepa.existing_data_edge_hurdle_v1 import frozen_spec as hurdle_spec
from neural.jepa.existing_data_edge_hurdle_v1 import frozen_spec_sha256 as hurdle_sha


VIEW = ROOT / "tmp/existing_data_edge_sprint_v1/modeling_view_features.parquet"
VIEW_MANIFEST = ROOT / "tmp/existing_data_edge_sprint_v1/modeling_view_manifest.json"
JOIN_INVENTORY = ROOT / "tmp/existing_data_edge_sprint_v1/join_feature_inventory_v1.json"
DEVELOPMENT_SUMMARY = ROOT / "tmp/existing_data_edge_sprint_v1/development_202312_v2/SUMMARY.json"
DEFAULT_OUTPUT = ROOT / "research_papers/JEPA/results/_diagnostics/existing_data_executable_utility_v1_frozen_runner/manifest.json"
CODE_CLOSURE = (
    "neural/jepa/audit_existing_data_edge_join_inventory_v1.py",
    "neural/jepa/build_existing_data_edge_modeling_view_v1.py",
    "neural/jepa/evaluate_existing_data_executable_utility_v1.py",
    "neural/jepa/existing_data_edge_alternative_v1.py",
    "neural/jepa/existing_data_edge_hurdle_v1.py",
    "neural/jepa/existing_data_edge_scheduler_v1.py",
)
PROTOCOL_CLOSURE = ("research_papers/JEPA/EXISTING_DATA_EXECUTABLE_UTILITY_V1_PREDECLARATION.md",)


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _file(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def freeze(output: Path) -> dict[str, Any]:
    head = _git("rev-parse", "HEAD")
    origin = _git("rev-parse", "origin/main")
    if head != origin:
        raise AssertionError("freeze requires HEAD == origin/main")
    if subprocess.run(["git", "diff", "--quiet"], cwd=ROOT, check=False).returncode != 0:
        raise AssertionError("freeze requires no tracked working-tree modifications")
    for relative in (*CODE_CLOSURE, *PROTOCOL_CLOSURE):
        if _git("ls-files", "--error-unmatch", relative) != relative:
            raise AssertionError(f"freeze closure is not tracked: {relative}")

    view = json.loads(VIEW_MANIFEST.read_text(encoding="utf-8"))
    inventory = json.loads(JOIN_INVENTORY.read_text(encoding="utf-8"))
    development = json.loads(DEVELOPMENT_SUMMARY.read_text(encoding="utf-8"))
    if (
        view.get("status") != "PASS_EXACT_EXISTING_DATA_VIEW"
        or view.get("view_sha256") != sha256_file(VIEW)
        or development.get("mode") != "development"
        or development.get("outer_months") != ["202312"]
        or development.get("runner_protocol_sha256") != runner_protocol_sha256()
        or development.get("holdout_2026_opened") is not False
        or inventory.get("outcomes_read") is not False
    ):
        raise AssertionError("outcome-free view or development smoke is not freeze-ready")
    feature_arms = {arm: view[arm] for arm in ("E0", "E1")}
    if (
        feature_arms["E0"]["feature_count"] != 30
        or feature_arms["E1"]["feature_count"] != 527
        or feature_arms["E0"]["ordered_json_sha256"] != "b68b6c2e17b333597281a7d7fa27237b1f1e2640deb8952867d25eced26cbe38"
        or feature_arms["E1"]["ordered_json_sha256"] != "e15469c0d1dce8176afd5c7fd48af4c477f830b4fc58651fb982f89fb8986abc"
    ):
        raise AssertionError("E0/E1 allowlist differs from predeclaration")

    payload = {
        "schema": "existing_data_executable_utility_v1_frozen_runner",
        "status": "PREEXECUTION_FROZEN",
        "experiment": "EXISTING_DATA_EXECUTABLE_UTILITY_V1",
        "git_head_at_freeze": head,
        "origin_main_at_freeze": origin,
        "inputs": {
            "modeling_view": _file(VIEW),
            "modeling_view_manifest": _file(VIEW_MANIFEST),
            "join_inventory": _file(JOIN_INVENTORY),
            "master_executable_labels": _file(MASTER),
            "executable_build_summary": _file(BUILD_SUMMARY),
            "development_smoke_summary": _file(DEVELOPMENT_SUMMARY),
        },
        "feature_arms": feature_arms,
        "block_classifications": {
            name: block["classification"] for name, block in inventory["blocks"].items()
        },
        "model_specs": {
            "primary": {"spec": hurdle_spec(), "sha256": hurdle_sha()},
            "alternative": {"spec": huber_spec(), "sha256": huber_sha()},
        },
        "runner_protocol": runner_protocol(),
        "runner_protocol_sha256": runner_protocol_sha256(),
        "outer_months": list(OUTER_MONTHS),
        "code_hashes": {relative: sha256_file(ROOT / relative) for relative in CODE_CLOSURE},
        "protocol_hashes": {relative: sha256_file(ROOT / relative) for relative in PROTOCOL_CLOSURE},
        "outer_outcomes_opened_at_freeze": False,
        "holdout_2026_opened": False,
        "june_2026_sealed": True,
        "production_modified": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {**payload, "manifest_path": str(output.relative_to(ROOT)).replace("\\", "/"), "manifest_sha256": sha256_file(output)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT.relative_to(ROOT)))
    args = parser.parse_args()
    payload = freeze(ROOT / args.output)
    print(json.dumps({key: payload[key] for key in (
        "status", "git_head_at_freeze", "runner_protocol_sha256", "manifest_path", "manifest_sha256",
    )}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
