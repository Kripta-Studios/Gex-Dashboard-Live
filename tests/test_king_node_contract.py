from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from modules.king_node_contract import (
    FORMULA_CLASSIFICATIONS,
    INPUT_SCHEMA_VERSION,
    KingNodeInputError,
    KingNodeReferenceError,
    canonical_reference_checksum,
    validate_normalized_input,
    validate_reference,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "king_node_v2"


def _input() -> dict:
    return json.loads((FIXTURES / "golden_input.json").read_text(encoding="utf-8"))


def _reference() -> dict:
    return json.loads((ROOT / "config" / "king_node_reference.json").read_text(encoding="utf-8"))


def test_classification_enum_is_frozen() -> None:
    assert FORMULA_CLASSIFICATIONS == (
        "runtime_calculation",
        "static_reference_export",
        "presentation_rule",
        "conditional_formatting",
        "input_validation",
        "historical_log",
        "not_runtime_applicable",
    )


def test_normalized_theta_input_is_typed_and_json_round_trips() -> None:
    validated = validate_normalized_input(_input())
    serialized = validated.as_dict()
    assert serialized["schema_version"] == INPUT_SCHEMA_VERSION
    assert len(serialized["option_rows"]) == 10
    assert serialized["option_rows"][0]["right"] == "CALL"
    assert serialized["option_rows"][0]["greeks"]["gamma"]["provenance"] == "observed"


def test_model_derived_greek_requires_traceable_basis() -> None:
    payload = _input()
    payload["option_rows"][0]["greeks"]["gamma"] = {
        "value": 0.02,
        "provenance": "model_derived",
    }
    with pytest.raises(KingNodeInputError, match="methodology and source_fields"):
        validate_normalized_input(payload)


def test_reference_is_hash_pinned_and_checksum_verified() -> None:
    reference = _reference()
    validated = validate_reference(reference)
    assert len(validated.matrix) == 78
    assert len(validated.iv_regime_map) == 54
    assert canonical_reference_checksum(reference) == reference["canonical_checksum"]
    broken = deepcopy(reference)
    broken["authority"]["workbook_sha256"] = "f" * 64
    with pytest.raises(KingNodeReferenceError, match="workbook SHA256"):
        validate_reference(broken)
    empty = deepcopy(reference)
    empty["matrix"] = {}
    empty["canonical_checksum"] = canonical_reference_checksum(empty)
    with pytest.raises(KingNodeReferenceError, match="non-empty"):
        validate_reference(empty)
