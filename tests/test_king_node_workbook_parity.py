from __future__ import annotations

import json
from pathlib import Path

import pytest

from modules.king_node_engine import build_snapshot, initial_state


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "king_node_v2"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _value(snapshot: dict, dotted: str):
    current = snapshot
    for key in dotted.split("."):
        current = current[key]
    return current


def test_golden_v2_parity_has_no_unexplained_mismatch() -> None:
    input_payload = _load("golden_input.json")
    expected = _load("golden_expectations.json")
    reference = json.loads(
        (ROOT / "config" / "king_node_reference.json").read_text(encoding="utf-8")
    )
    snapshot, _ = build_snapshot(
        input_payload,
        state=initial_state(input_payload["session_date"]),
        reference=reference,
    )
    numeric_errors = []
    for path, expected_value in expected["numeric_fields"].items():
        actual = _value(snapshot, path)
        absolute = abs(actual - expected_value)
        relative = absolute / max(abs(expected_value), 1.0)
        numeric_errors.append((absolute, relative, path))
        assert actual == pytest.approx(
            expected_value,
            abs=expected["tolerances"]["absolute"],
            rel=expected["tolerances"]["relative"],
        )
    for path, expected_value in expected["exact_match_fields"].items():
        assert _value(snapshot, path) == expected_value
    assert max(value[0] for value in numeric_errors) <= expected["max_absolute_error"]
    assert max(value[1] for value in numeric_errors) <= expected["max_relative_error"]
    assert expected["mismatches"] == []
    assert expected["cached_workbook_value_claims"] == []
    assert set(expected["exercised_families"]) == {
        "King Node Model", "GEX Depth", "Level Engine", "Matrix", "IV Regime Map"
    }
