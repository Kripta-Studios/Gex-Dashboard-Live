"""Freeze CROSS_MARKET_TRANSMISSION_V1R1 before opening 2024/2025 outcomes.

This command is intentionally unusable from a development worktree.  It binds
the exact outcome-free view, ordered feature arms, model, runner protocol and
code closure to a clean commit that is already present on ``origin/main``.
It does not read the executable outcome columns and it does not execute a fold.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from neural.jepa.audit_existing_data_edge_join_inventory_v1 import ROOT, sha256_file
from neural.jepa.build_cross_market_transmission_view_v1 import (
    CROSS_FEATURES,
    EARLY_CLOSE_DATES,
    ELIGIBLE_ROWS_V1R1,
    MASTER_SHA256,
)
from neural.jepa.evaluate_cross_market_transmission_v1 import (
    BUILD_SUMMARY,
    MASTER,
    OUTER_MONTHS,
    VIEW,
    VIEW_MANIFEST,
    FROZEN_CODE_CLOSURE,
    FROZEN_OUTER_OUTPUT,
    FROZEN_PROTOCOL_CLOSURE,
    _verify_view,
    runner_protocol,
    runner_protocol_sha256,
)
from neural.jepa.existing_data_quantile_distribution_v1 import (
    frozen_spec,
    frozen_spec_sha256,
)


DEFAULT_OUTPUT = (
    ROOT
    / "research_papers/JEPA/results/_diagnostics/"
    "cross_market_transmission_v1r1_frozen_runner/manifest.json"
)
CODE_CLOSURE = FROZEN_CODE_CLOSURE
PROTOCOL_CLOSURE = FROZEN_PROTOCOL_CLOSURE

EXPECTED_X0_SHA256 = "b68b6c2e17b333597281a7d7fa27237b1f1e2640deb8952867d25eced26cbe38"
EXPECTED_CROSS_SHA256 = "5df3d817d12c5d938427eabeca145f1d4e59420e1283fa3cf3bdaeef6b112058"
EXPECTED_X1_SHA256 = "3ef89d8da590dd548dd4c14a4cd8931becfa27d3d10c5fd71440146f402252d1"
EXPECTED_MODEL_SPEC_SHA256 = "53940684518834bed0f45272151f030d740428516ce5c86443d92cf318245499"
EXPECTED_RUNNER_PROTOCOL_SHA256 = "3f45cfdd1208417a1580340736aa5352e4419df5c26f85bc84510b3936d165d5"
EXPECTED_SOURCE_SESSIONS = 3_848


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _tracked_diff_clean(*, cached: bool) -> bool:
    command = ["git", "diff"]
    if cached:
        command.append("--cached")
    command.extend(["--quiet", "--"])
    return subprocess.run(command, cwd=ROOT, check=False).returncode == 0


def _canonical_ordered_sha(values: list[str]) -> str:
    import hashlib

    raw = json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "sha256": sha256_file(path),
        "bytes": int(path.stat().st_size),
    }


def _verify_git_state() -> tuple[str, str]:
    head = _git("rev-parse", "HEAD")
    origin = _git("rev-parse", "origin/main")
    if head != origin:
        raise AssertionError("freeze requires HEAD == origin/main")
    if not _tracked_diff_clean(cached=False):
        raise AssertionError("freeze requires no unstaged tracked modifications")
    if not _tracked_diff_clean(cached=True):
        raise AssertionError("freeze requires no staged tracked modifications")
    for relative in (*CODE_CLOSURE, *PROTOCOL_CLOSURE):
        try:
            tracked = _git("ls-files", "--error-unmatch", relative)
        except subprocess.CalledProcessError as exc:
            raise AssertionError(f"freeze closure is not committed: {relative}") from exc
        if tracked.replace("\\", "/") != relative:
            raise AssertionError(f"freeze closure is not committed exactly: {relative}")
    return head, origin


def _verify_feature_arms(view_manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    arms = {name: view_manifest.get(name) for name in ("X0", "X1")}
    if not all(isinstance(value, dict) for value in arms.values()):
        raise AssertionError("view manifest does not contain X0/X1 feature arms")
    x0 = arms["X0"]
    x1 = arms["X1"]
    if int(x0.get("feature_count", -1)) != 30 or int(x1.get("feature_count", -1)) != 58:
        raise AssertionError("cross-market feature counts must be X0=30 and X1=58")
    x0_features = x0.get("features")
    x1_features = x1.get("features")
    if not isinstance(x0_features, list) or not isinstance(x1_features, list):
        raise AssertionError("feature allowlists must be ordered JSON arrays")
    if len(x0_features) != len(set(x0_features)) or len(x1_features) != len(set(x1_features)):
        raise AssertionError("feature allowlists contain duplicate names")
    if x1_features[:30] != x0_features or x1_features[30:] != list(CROSS_FEATURES):
        raise AssertionError("X1 is not exact X0 plus the frozen 28-field transmission block")
    expected = {
        "X0": EXPECTED_X0_SHA256,
        "X1": EXPECTED_X1_SHA256,
    }
    for name, features in (("X0", x0_features), ("X1", x1_features)):
        calculated = _canonical_ordered_sha(features)
        recorded = arms[name].get("ordered_json_sha256")
        if calculated != expected[name] or recorded != expected[name]:
            raise AssertionError(f"{name} ordered allowlist hash changed")
    if _canonical_ordered_sha(list(CROSS_FEATURES)) != EXPECTED_CROSS_SHA256:
        raise AssertionError("active 28-field cross-market allowlist changed")
    return {"X0": x0, "X1": x1}


def _resolve_manifest_path(value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else ROOT / path


def _verify_view_inventory(view_manifest: dict[str, Any]) -> Path:
    if view_manifest.get("master_sha256") != MASTER_SHA256:
        raise AssertionError("view was not built from the authoritative outcome master")
    if view_manifest.get("outcomes_in_view") is not False:
        raise AssertionError("outcome-free view contract is not explicit")
    if view_manifest.get("live_parity") != "BLOCKED_IMPLEMENTATION":
        raise AssertionError("live parity must remain BLOCKED_IMPLEMENTATION at freeze")
    inventory_path = _resolve_manifest_path(view_manifest.get("source_inventory_path", ""))
    if not inventory_path.is_file():
        raise AssertionError("exact source inventory is missing")
    if view_manifest.get("source_inventory_sha256") != sha256_file(inventory_path):
        raise AssertionError("exact source inventory hash mismatch")
    if int(view_manifest.get("source_sessions", -1)) != EXPECTED_SOURCE_SESSIONS:
        raise AssertionError("source inventory must contain exactly 962 eligible sessions x 4 markets")
    if int(view_manifest.get("master_rows_preserved", -1)) != ELIGIBLE_ROWS_V1R1:
        raise AssertionError("V1R1 eligible row count changed")
    if view_manifest.get("excluded_early_close_dates") != list(EARLY_CLOSE_DATES):
        raise AssertionError("V1R1 early-close exclusion changed")
    return inventory_path


def _verify_model_and_protocol() -> tuple[dict[str, Any], dict[str, Any]]:
    model = frozen_spec()
    model_sha = frozen_spec_sha256()
    protocol = runner_protocol()
    protocol_sha = runner_protocol_sha256()
    if model_sha != EXPECTED_MODEL_SPEC_SHA256:
        raise AssertionError("quantile distribution model spec changed after predeclaration")
    if protocol_sha != EXPECTED_RUNNER_PROTOCOL_SHA256:
        raise AssertionError("runner protocol changed after predeclaration")
    if protocol.get("model_spec_sha256") != model_sha:
        raise AssertionError("runner protocol is not bound to the active model spec")
    if protocol.get("outer_months") != list(OUTER_MONTHS):
        raise AssertionError("runner protocol outer months changed")
    if protocol.get("holdout_2026_opened") is not False:
        raise AssertionError("runner protocol opened 2026")
    if protocol.get("june_2026_sealed") is not True:
        raise AssertionError("runner protocol does not seal June 2026")
    return model, protocol


def freeze(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    """Write an immutable pre-execution manifest; never read outcome columns."""

    if output.exists():
        raise FileExistsError(f"refusing to overwrite frozen manifest: {output}")
    head, origin = _verify_git_state()
    view_manifest = _verify_view(VIEW, VIEW_MANIFEST)
    feature_arms = _verify_feature_arms(view_manifest)
    inventory_path = _verify_view_inventory(view_manifest)
    model, protocol = _verify_model_and_protocol()

    payload = {
        "schema": "cross_market_transmission_v1r1_frozen_runner",
        "status": "PREEXECUTION_FROZEN",
        "experiment": "CROSS_MARKET_TRANSMISSION_V1R1",
        "git_head_at_freeze": head,
        "origin_main_at_freeze": origin,
        "inputs": {
            "outcome_free_view": _file(VIEW),
            "outcome_free_view_manifest": _file(VIEW_MANIFEST),
            "exact_source_inventory": _file(inventory_path),
            "master_executable_labels_metadata_only": _file(MASTER),
            "executable_build_summary": _file(BUILD_SUMMARY),
        },
        "view_sha256": view_manifest["view_sha256"],
        "feature_arms": feature_arms,
        "cross_market_block": {
            "feature_count": len(CROSS_FEATURES),
            "features": list(CROSS_FEATURES),
            "ordered_json_sha256": EXPECTED_CROSS_SHA256,
        },
        "model_spec": model,
        "model_spec_sha256": EXPECTED_MODEL_SPEC_SHA256,
        "runner_protocol": protocol,
        "runner_protocol_sha256": EXPECTED_RUNNER_PROTOCOL_SHA256,
        "outer_months": list(OUTER_MONTHS),
        "outer_output_dir": FROZEN_OUTER_OUTPUT,
        "code_hashes": {relative: sha256_file(ROOT / relative) for relative in CODE_CLOSURE},
        "protocol_hashes": {
            relative: sha256_file(ROOT / relative) for relative in PROTOCOL_CLOSURE
        },
        "outer_outcomes_opened_at_freeze": False,
        "holdout_2026_opened": False,
        "june_2026_sealed": True,
        "live_parity": "BLOCKED_IMPLEMENTATION",
        "production_modified": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return {
        **payload,
        "manifest_path": str(output.relative_to(ROOT)).replace("\\", "/"),
        "manifest_sha256": sha256_file(output),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT.relative_to(ROOT)))
    args = parser.parse_args()
    result = freeze(ROOT / args.output)
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "status",
                    "git_head_at_freeze",
                    "runner_protocol_sha256",
                    "live_parity",
                    "manifest_path",
                    "manifest_sha256",
                )
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
