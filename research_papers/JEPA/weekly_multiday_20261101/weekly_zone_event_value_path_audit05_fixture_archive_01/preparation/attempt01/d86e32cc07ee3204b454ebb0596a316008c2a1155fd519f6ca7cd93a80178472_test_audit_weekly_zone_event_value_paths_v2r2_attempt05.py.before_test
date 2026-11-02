"""Focal invariants for the path-only audit05 clone."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

import audit_weekly_zone_event_value_paths_v2r2 as baseline
import audit_weekly_zone_event_value_paths_v2r2_attempt05 as audit


HERE = Path(__file__).resolve().parent
BASELINE_PATH = HERE / "audit_weekly_zone_event_value_paths_v2r2.py"
CLONE_PATH = HERE / "audit_weekly_zone_event_value_paths_v2r2_attempt05.py"
OUTPUT_ASSIGNMENT_04 = b'OUTPUT = BASE / "weekly_zone_event_value_paths_audit_04"'
OUTPUT_ASSIGNMENT_05 = b'OUTPUT = BASE / "weekly_zone_event_value_paths_audit_05"'
OBSERVER_ASSIGNMENT_04 = b'OBSERVER = BASE / "weekly_zone_event_value_paths_audit_observer_04"'
OBSERVER_ASSIGNMENT_05 = b'OBSERVER = BASE / "weekly_zone_event_value_paths_audit_observer_05"'


def assignments(tree: ast.Module) -> dict[str, ast.Assign]:
    result: dict[str, ast.Assign] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            result[node.targets[0].id] = node
    return result


def test_attempt05_exact_reversible_byte_delta() -> None:
    source = BASELINE_PATH.read_bytes()
    clone = CLONE_PATH.read_bytes()
    assert source.count(OUTPUT_ASSIGNMENT_04) == source.count(OBSERVER_ASSIGNMENT_04) == 1
    assert source.count(OUTPUT_ASSIGNMENT_05) == source.count(OBSERVER_ASSIGNMENT_05) == 0
    expected = source.replace(OUTPUT_ASSIGNMENT_04, OUTPUT_ASSIGNMENT_05)
    expected = expected.replace(OBSERVER_ASSIGNMENT_04, OBSERVER_ASSIGNMENT_05)
    assert clone == expected
    restored = clone.replace(OUTPUT_ASSIGNMENT_05, OUTPUT_ASSIGNMENT_04)
    restored = restored.replace(OBSERVER_ASSIGNMENT_05, OBSERVER_ASSIGNMENT_04)
    assert restored == source


def test_attempt05_full_ast_equal_after_two_literal_normalization() -> None:
    source_tree = ast.parse(BASELINE_PATH.read_text(encoding="utf-8"))
    clone_tree = ast.parse(CLONE_PATH.read_text(encoding="utf-8"))
    source_assignments = assignments(source_tree)
    clone_assignments = assignments(clone_tree)
    changed = {
        name for name in source_assignments
        if ast.dump(source_assignments[name], include_attributes=False) !=
        ast.dump(clone_assignments[name], include_attributes=False)
    }
    assert set(source_assignments) == set(clone_assignments)
    assert changed == {"OUTPUT", "OBSERVER"}
    for name in changed:
        clone_assignments[name].value = source_assignments[name].value
    assert ast.dump(clone_tree, include_attributes=False) == ast.dump(source_tree, include_attributes=False)


def test_attempt05_preserves_authorities_producer_and_immutable_tests() -> None:
    assert len(audit.PINS) == 29 and audit.PINS == baseline.PINS
    assert audit.IMPLEMENTATION_PATHS == baseline.IMPLEMENTATION_PATHS
    assert audit.PRODUCER == baseline.PRODUCER == audit.BASE / "weekly_zone_event_value_paths_02"
    assert audit.PRODUCER_OBSERVER == baseline.PRODUCER_OBSERVER
    assert audit.TESTS == baseline.TESTS == HERE / "test_audit_weekly_zone_event_value_paths_v2r2.py"
    assert audit.OUTPUT == audit.BASE / "weekly_zone_event_value_paths_audit_05"
    assert audit.OBSERVER == audit.BASE / "weekly_zone_event_value_paths_audit_observer_05"


def test_attempt05_actual_parser_defaults_bind_new_roots() -> None:
    args = audit.parser().parse_args([])
    assert args.producer_root == audit.PRODUCER
    assert args.output == audit.OUTPUT
    assert args.observer == audit.OBSERVER


def test_attempt05_wrong_roots_fail_before_any_downstream_action(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def trap(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("downstream action reached")

    monkeypatch.setattr(audit, "validate_environment", trap)
    monkeypatch.setattr(audit, "bind_resource_helper", trap)
    monkeypatch.setattr(audit, "guard_file", trap)
    monkeypatch.setattr(audit, "file_pin", trap)
    monkeypatch.setattr(audit, "load_json", trap)
    monkeypatch.setattr(Path, "exists", trap)
    monkeypatch.setattr(Path, "open", trap)
    monkeypatch.setattr(Path, "read_bytes", trap)
    monkeypatch.setattr(Path, "read_text", trap)
    monkeypatch.setattr(Path, "mkdir", trap)
    cases = (
        (tmp_path / "wrong_output", audit.OBSERVER),
        (audit.OUTPUT, tmp_path / "wrong_observer"),
    )
    for output, observer in cases:
        with pytest.raises(audit.AuditError, match="exclusive audit roots"):
            audit.run(
                audit.PRODUCER, "0" * 64, audit.PRODUCER_OBSERVER / "exit.json", "0" * 64,
                "0" * 64, "0" * 64, {}, {}, {}, output, observer,
            )
