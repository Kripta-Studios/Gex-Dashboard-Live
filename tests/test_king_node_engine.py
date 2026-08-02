from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from modules.king_node_engine import (
    KingNodeDataError,
    _apply_level_lock,
    aggregate_by_strike,
    build_snapshot,
    initial_state,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "king_node_v2"


def _input() -> dict:
    return json.loads((FIXTURES / "golden_input.json").read_text(encoding="utf-8"))


def _reference() -> dict:
    return json.loads((ROOT / "config" / "king_node_reference.json").read_text(encoding="utf-8"))


def _dotted(value: dict, path: str):
    current = value
    for part in path.split("."):
        current = current[part]
    return current


def _keys(value: object):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield str(key)
            yield from _keys(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _keys(nested)


def test_raw_gamma_is_multiplied_per_leg_before_strike_aggregation() -> None:
    rows = [
        {
            "strike_price": 6000,
            "call_gamma": 1,
            "put_gamma": 2,
            "call_open_int": 10,
            "put_open_int": 20,
        },
        {
            "strike_price": 6000,
            "call_gamma": 3,
            "put_gamma": 4,
            "call_open_int": 5,
            "put_open_int": 7,
        },
    ]
    aggregate = aggregate_by_strike(rows)[0]
    assert aggregate["raw_call_gamma"] == 25
    assert aggregate["raw_put_gamma"] == 68
    assert aggregate["raw_gamma"] == 93


def test_build_snapshot_requires_v2_input_and_verified_reference() -> None:
    fixture = _input()
    snapshot, state = build_snapshot(
        fixture,
        state=initial_state("2026-08-02"),
        reference=_reference(),
    )
    assert snapshot["schema"] == "king-node.v2"
    assert snapshot["schema_version"] == "king-node.v2"
    assert snapshot["quality"]["reference_mode"] == "verified_static_reference"
    assert snapshot["reference"]["matrix_rows"] == 78
    assert snapshot["reference"]["iv_regime_rows"] == 54
    assert snapshot["formula_coverage"]["current_formula_cells"] == 7959
    assert snapshot["formula_coverage"]["catalogue_only"] == 107
    assert len(snapshot["rows"]) == 5
    assert state["schema_version"] == "king-node.v2-state"
    assert "semantic_fallback" not in json.dumps(snapshot, sort_keys=True)
    assert not any("path" in key.lower() for key in _keys(snapshot))


def test_build_snapshot_rejects_legacy_input_and_bad_reference() -> None:
    with pytest.raises(KingNodeDataError, match="king-node.v2-input"):
        build_snapshot({"option_data": {}}, reference=_reference())
    bad_reference = deepcopy(_reference())
    bad_reference["canonical_checksum"] = "0" * 64
    with pytest.raises(KingNodeDataError, match="checksum"):
        build_snapshot(_input(), reference=bad_reference)
    with pytest.raises(KingNodeDataError, match="requires a verified"):
        build_snapshot(_input())


def test_level_challenger_must_hold_for_three_cycles() -> None:
    locked, pending = _apply_level_lock(
        [6100.0], {}, [6110.0, 6100.0], 6000.0, "resistance"
    )
    assert locked == [6100.0, 6110.0]
    locked, pending = _apply_level_lock(
        locked, pending, [6110.0, 6100.0], 6000.0, "resistance"
    )
    locked, pending = _apply_level_lock(
        locked, pending, [6110.0, 6100.0], 6000.0, "resistance"
    )
    assert locked == [6110.0, 6100.0]
    assert pending == {}


def test_golden_fixture_records_exact_fields_and_numeric_tolerance() -> None:
    expectation = json.loads(
        (FIXTURES / "golden_expectations.json").read_text(encoding="utf-8")
    )
    snapshot, _ = build_snapshot(
        _input(), state=initial_state("2026-08-02"), reference=_reference()
    )
    for path, expected in expectation["exact_match_fields"].items():
        assert _dotted(snapshot, path) == expected
    for path, expected in expectation["numeric_fields"].items():
        assert _dotted(snapshot, path) == pytest.approx(
            expected,
            abs=expectation["tolerances"]["absolute"],
            rel=expectation["tolerances"]["relative"],
        )
    assert expectation["max_absolute_error"] == 0.0
    assert expectation["max_relative_error"] == 0.0
    assert expectation["mismatches"] == []
    assert expectation["cached_workbook_value_claims"] == []
