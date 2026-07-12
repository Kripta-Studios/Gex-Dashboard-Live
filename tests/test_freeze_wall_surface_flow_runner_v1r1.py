from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from neural.jepa.freeze_wall_surface_flow_runner_v1r1 import (  # noqa: E402
    CODE_CLOSURE,
    PROTOCOL_CLOSURE,
    sha256_file,
    validate_exact_greek_repair_provenance,
    validate_historical_provenance_status,
)


REPAIR_DIR = (
    ROOT
    / "research_papers/JEPA/results/_diagnostics/"
    "wall_exact_greek_repair_artifacts_20221230_v1r2"
)


def _provenance() -> dict:
    manifest = json.loads((REPAIR_DIR / "manifest.json").read_text(encoding="utf-8"))
    return {
        "schema": "wall_exact_greek_repair_artifacts_v1r2",
        "status": "PASS_EXACT_GREEK_REPAIR_ARTIFACTS",
        "manifest_path": str((REPAIR_DIR / "manifest.json").relative_to(ROOT)),
        "manifest_sha256": sha256_file(REPAIR_DIR / "manifest.json"),
        "wall_repair_path": str((REPAIR_DIR / "wall_repair.parquet").relative_to(ROOT)),
        "wall_repair_sha256": sha256_file(REPAIR_DIR / "wall_repair.parquet"),
        "event_control_repair_path": str(
            (REPAIR_DIR / "event_control_repair.parquet").relative_to(ROOT)
        ),
        "event_control_repair_sha256": sha256_file(REPAIR_DIR / "event_control_repair.parquet"),
        "frozen_hashes_match": True,
        "target_sessions": [
            {"ticker": "QQQ", "trade_date": "20221230"},
            {"ticker": "SPY", "trade_date": "20221230"},
        ],
        "wall_target_rows": 96,
        "full_control_grid_rows": 96,
        "event_target_rows": 47,
        "event_target_rows_by_ticker": {"QQQ": 27, "SPY": 20},
        "event_target_key_sha256": manifest["event_target_key_sha256"],
        "builder_sha256": manifest["builder_sha256"],
        "sidecar_builder_sha256": manifest["sidecar_builder_sha256"],
        "wall_feature_module_sha256": manifest["wall_feature_module_sha256"],
        "predeclaration_sha256": manifest["predeclaration_sha256"],
        "runtime_lock_sha256": manifest["runtime_lock_sha256"],
        "runtime_environment_sha256": manifest["runtime_environment_sha256"],
        "historical_provenance": "CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION",
    }


def test_exact_greek_repair_provenance_is_required_and_copied() -> None:
    with pytest.raises(AssertionError, match="requires exact_greek_repair_provenance"):
        validate_exact_greek_repair_provenance(None)
    source = _provenance()
    frozen = validate_exact_greek_repair_provenance(source)
    assert frozen == source
    assert frozen is not source


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("status", "REJECTED", "is not PASS"),
        ("frozen_hashes_match", "true", "frozen hashes did not match"),
        ("event_target_rows", 96, "event_target_rows mismatch"),
        ("event_target_key_sha256", "", "missing valid event_target_key_sha256"),
    ],
)
def test_exact_greek_repair_provenance_fails_closed(
    field: str, value: object, message: str
) -> None:
    provenance = _provenance()
    provenance[field] = value
    with pytest.raises(AssertionError, match=message):
        validate_exact_greek_repair_provenance(provenance)


def test_exact_greek_repair_artifact_hash_mismatch_is_rejected() -> None:
    provenance = _provenance()
    provenance["wall_repair_sha256"] = "0" * 64
    with pytest.raises(AssertionError, match="artifact hash mismatch"):
        validate_exact_greek_repair_provenance(provenance)


def test_conditional_exact_repair_cannot_freeze_historical_provenance_as_pass() -> None:
    provenance = validate_exact_greek_repair_provenance(_provenance())
    with pytest.raises(AssertionError, match="cannot be PASS"):
        validate_historical_provenance_status(provenance, "PASS")
    validate_historical_provenance_status(provenance, "CONDITIONAL")
    validate_historical_provenance_status(provenance, "BLOCKED")


def test_freeze_hash_closures_cover_v1r2_build_and_protocol() -> None:
    assert "neural/jepa/build_wall_surface_flow_dataset.py" in CODE_CLOSURE
    assert "neural/jepa/build_wall_exact_greek_repair_artifacts.py" in CODE_CLOSURE
    assert "neural/jepa/build_wall_exact_greek_repair_sidecar.py" in CODE_CLOSURE
    assert (
        "research_papers/JEPA/WALL_SURFACE_FLOW_V1R2_EXACT_SPOT_REPAIR_PREDECLARATION.md"
        in PROTOCOL_CLOSURE
    )
    assert (
        "research_papers/JEPA/WALL_SURFACE_FLOW_V1R2_DATA_GATE_CLARIFICATION.md"
        in PROTOCOL_CLOSURE
    )
    assert len(CODE_CLOSURE) == len(set(CODE_CLOSURE))
    assert len(PROTOCOL_CLOSURE) == len(set(PROTOCOL_CLOSURE))
    for relative in CODE_CLOSURE + PROTOCOL_CLOSURE:
        assert (ROOT / relative).is_file()
