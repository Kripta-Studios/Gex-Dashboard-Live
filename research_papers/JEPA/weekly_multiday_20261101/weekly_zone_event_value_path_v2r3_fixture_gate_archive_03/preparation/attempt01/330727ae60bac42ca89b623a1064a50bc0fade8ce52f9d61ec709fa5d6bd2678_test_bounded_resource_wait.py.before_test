"""Artificial-only focal tests for B06/R3 bounded resource scheduling."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

import audit_weekly_zone_event_value_paths_v2r3 as audit
import bounded_resource_wait as wait


HERE = Path(__file__).resolve().parent
BASELINE_PATH = HERE / "audit_weekly_zone_event_value_paths_v2r2_attempt05.py"
R3_PATH = HERE / "audit_weekly_zone_event_value_paths_v2r3.py"


class Clock:
    def __init__(self) -> None:
        self.value = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def official_gate(value):
    if any(value[key] < wait.THRESHOLD_BYTES for key in wait.OBSERVATION_KEYS):
        raise ValueError("2GB RAM/commit gate unmet")


def waiter(tmp_path: Path, observations, disks, clock: Clock | None = None, sleeper=None):
    clock = clock or Clock()
    observation_values = iter(observations)
    disk_values = iter(disks)
    return wait.ResourceWaiter(
        observation=lambda: next(observation_values), official_gate=official_gate,
        disk_probe=lambda: next(disk_values), evidence_path=tmp_path / "resource_wait.jsonl",
        monotonic=clock.monotonic, sleeper=sleeper or clock.sleep,
        utc_now=lambda: "2026-11-02T00:00:00+00:00",
    ), clock


def test_pass_immediate_and_exact_threshold_creates_no_evidence(tmp_path: Path) -> None:
    unit, _clock = waiter(tmp_path, [{"available_ram_bytes": 2_000_000_000, "free_commit_bytes": 2_000_000_000}], [2_000_000_000])
    assert unit.acquire("ADMIT_AUTHORITIES", "ALL") == {
        "available_ram_bytes": 2_000_000_000,
        "free_commit_bytes": 2_000_000_000,
        "disk_free_bytes": 2_000_000_000,
    }
    assert not (tmp_path / "resource_wait.jsonl").exists()


def test_actual_pinned_official_gate_uses_exact_valueerror_without_observation() -> None:
    helper_path = HERE.parent / "level_oracle_20261018" / "launch_monthly_test_index_v2_audit_20261024.py"
    assert hashlib.sha256(helper_path.read_bytes()).hexdigest() == audit.HELPER_SHA256
    spec = importlib.util.spec_from_file_location("b06_test_official_resource_helper", helper_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    low = {"available_ram_bytes": 1, "free_commit_bytes": 3_000_000_000}
    with pytest.raises(ValueError, match="^2GB RAM/commit gate unmet$"):
        module.gate(low)
    module.gate({"available_ram_bytes": 2_000_000_000, "free_commit_bytes": 2_000_000_000})


@pytest.mark.parametrize("low_fields", [
    {"available_ram_bytes"}, {"free_commit_bytes"}, {"disk_free_bytes"},
    {"available_ram_bytes", "free_commit_bytes", "disk_free_bytes"},
])
def test_low_then_recover_persists_every_wait(tmp_path: Path, low_fields: set[str]) -> None:
    low = {
        "available_ram_bytes": 1 if "available_ram_bytes" in low_fields else 3_000_000_000,
        "free_commit_bytes": 1 if "free_commit_bytes" in low_fields else 3_000_000_000,
    }
    disk = 1 if "disk_free_bytes" in low_fields else 3_000_000_000
    high = {"available_ram_bytes": 3_000_000_000, "free_commit_bytes": 3_000_000_000}
    unit, clock = waiter(tmp_path, [low, high], [disk, 3_000_000_000])
    assert unit.acquire("SELECT_1030", "ALL")["disk_free_bytes"] == 3_000_000_000
    evidence = rows(tmp_path / "resource_wait.jsonl")
    assert len(evidence) == 1 and evidence[0]["status"] == "WAIT"
    assert evidence[0]["deficient_fields"] == sorted(low_fields)
    assert clock.sleeps == [5.0]
    wait.validate_resource_wait_rows(evidence)


def test_always_low_exact_600_seconds_wait_timeout_and_no_action(tmp_path: Path) -> None:
    clock = Clock()
    low = {"available_ram_bytes": 1, "free_commit_bytes": 1}
    unit = wait.ResourceWaiter(
        observation=lambda: dict(low), official_gate=official_gate,
        disk_probe=lambda: 1, evidence_path=tmp_path / "resource_wait.jsonl",
        monotonic=clock.monotonic, sleeper=clock.sleep,
        utc_now=lambda: "wall-clock-jump-is-irrelevant",
    )
    scientific_action_called = False
    with pytest.raises(wait.ResourceWaitTimeout):
        unit.acquire("STREAM_OPTION_PATHS", "ALL")
        scientific_action_called = True
    evidence = rows(tmp_path / "resource_wait.jsonl")
    assert evidence[-2]["status"] == "WAIT" and evidence[-2]["planned_sleep_seconds"] == 0.0
    assert evidence[-1]["status"] == "TIMEOUT" and evidence[-1]["final_wait_seq"] == evidence[-2]["seq"]
    assert sum(clock.sleeps) == 600.0 and all(value == 5.0 for value in clock.sleeps)
    assert scientific_action_called is False
    wait.validate_resource_wait_rows(evidence)


@pytest.mark.parametrize("bad", [
    {"available_ram_bytes": True, "free_commit_bytes": 3_000_000_000},
    {"available_ram_bytes": -1, "free_commit_bytes": 3_000_000_000},
    {"available_ram_bytes": 3_000_000_000},
    {"available_ram_bytes": 3_000_000_000, "free_commit_bytes": 3_000_000_000, "extra": 1},
])
def test_malformed_observation_is_immediate_fatal_without_sleep(tmp_path: Path, bad) -> None:
    unit, clock = waiter(tmp_path, [bad], [3_000_000_000])
    with pytest.raises(wait.ResourceWaitError):
        unit.acquire("WRITE_AUDIT_OUTPUT", "audit.json")
    assert clock.sleeps == [] and not (tmp_path / "resource_wait.jsonl").exists()


@pytest.mark.parametrize("bad_disk", [True, -1, 3_000_000_000.0, "3000000000"])
def test_malformed_disk_is_immediate_fatal(tmp_path: Path, bad_disk) -> None:
    unit, clock = waiter(tmp_path, [{"available_ram_bytes": 3_000_000_000, "free_commit_bytes": 3_000_000_000}], [bad_disk])
    with pytest.raises(wait.ResourceWaitError):
        unit.acquire("NORMALIZE_CALENDAR", "UNIFIED_CALENDAR")
    assert clock.sleeps == []


def test_last_sleep_uses_remainder_without_overshoot(tmp_path: Path) -> None:
    clock = Clock()
    clock.value = 0.0
    low = {"available_ram_bytes": 1, "free_commit_bytes": 1}
    unit = wait.ResourceWaiter(
        observation=lambda: dict(low), official_gate=official_gate,
        disk_probe=lambda: 3_000_000_000, evidence_path=tmp_path / "resource_wait.jsonl",
        monotonic=clock.monotonic,
        sleeper=lambda seconds: (clock.sleeps.append(seconds), setattr(clock, "value", clock.value + (597.0 if not clock.sleeps[:-1] else seconds)))[0],
        utc_now=lambda: "wall-clock-backward",
    )
    with pytest.raises(wait.ResourceWaitTimeout):
        unit.acquire("CLOSING_REHASH", "x")
    assert clock.sleeps[:2] == [5.0, 3.0]


def test_interrupt_during_sleep_is_durable_and_propagated(tmp_path: Path) -> None:
    clock = Clock()
    low = {"available_ram_bytes": 1, "free_commit_bytes": 1}
    def interrupt(_seconds: float) -> None:
        raise KeyboardInterrupt()
    unit, _ = waiter(tmp_path, [low], [1], clock, interrupt)
    with pytest.raises(KeyboardInterrupt):
        unit.acquire("CACHE_SPOT_PATH", "SPY:20240103")
    evidence = rows(tmp_path / "resource_wait.jsonl")
    assert [row["status"] for row in evidence] == ["WAIT", "INTERRUPTED"]
    assert evidence[-1]["final_wait_seq"] == evidence[0]["seq"]
    wait.validate_resource_wait_rows(evidence)


def test_interrupt_before_first_observation_has_null_operational_snapshot(tmp_path: Path) -> None:
    def interrupt():
        raise KeyboardInterrupt()
    unit = wait.ResourceWaiter(
        observation=interrupt, official_gate=official_gate,
        disk_probe=lambda: 3_000_000_000,
        evidence_path=tmp_path / "resource_wait.jsonl",
        monotonic=lambda: 0.0, sleeper=lambda _seconds: None,
        utc_now=lambda: "2026-11-02T00:00:00+00:00",
    )
    with pytest.raises(KeyboardInterrupt):
        unit.acquire("ADMIT_AUTHORITIES", "ALL")
    evidence = rows(tmp_path / "resource_wait.jsonl")
    assert evidence[0]["status"] == "INTERRUPTED"
    assert evidence[0]["observation"] is None and evidence[0]["disk_free_bytes"] is None
    assert evidence[0]["final_wait_seq"] is None
    wait.validate_resource_wait_rows(evidence)


def test_helper_or_disk_exception_is_fatal_without_wait(tmp_path: Path) -> None:
    for label, observation, disk_probe in (
        ("helper", lambda: (_ for _ in ()).throw(RuntimeError("helper")), lambda: 3_000_000_000),
        ("disk", lambda: {"available_ram_bytes": 3_000_000_000, "free_commit_bytes": 3_000_000_000}, lambda: (_ for _ in ()).throw(OSError("disk"))),
    ):
        path = tmp_path / (label + ".jsonl")
        unit = wait.ResourceWaiter(
            observation=observation, official_gate=official_gate,
            disk_probe=disk_probe, evidence_path=path,
            monotonic=lambda: 0.0, sleeper=lambda _seconds: pytest.fail("must not sleep"),
        )
        with pytest.raises((RuntimeError, OSError)):
            unit.acquire("NORMALIZE_CALENDAR", label)
        assert not path.exists()


def test_unexpected_official_gate_error_is_not_reclassified_as_low(tmp_path: Path) -> None:
    cases = (
        ({"available_ram_bytes": 1, "free_commit_bytes": 3_000_000_000}, ValueError("unrelated")),
        ({"available_ram_bytes": 3_000_000_000, "free_commit_bytes": 3_000_000_000}, ValueError("2GB RAM/commit gate unmet")),
    )
    for index, (observed, gate_error) in enumerate(cases):
        evidence = tmp_path / f"resource_wait_{index}.jsonl"
        unit = wait.ResourceWaiter(
            observation=lambda value=observed: value,
            official_gate=lambda _value, error=gate_error: (_ for _ in ()).throw(error),
            disk_probe=lambda: 3_000_000_000,
            evidence_path=evidence,
            monotonic=lambda: 0.0, sleeper=lambda _seconds: pytest.fail("must not sleep"),
        )
        with pytest.raises(wait.ResourceWaitError):
            unit.acquire("SELECT_1030", "ALL")
        assert not evidence.exists()


def test_evidence_fsync_failure_is_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    low = {"available_ram_bytes": 1, "free_commit_bytes": 1}
    unit, clock = waiter(tmp_path, [low], [1])
    monkeypatch.setattr(wait.os, "fsync", lambda _fd: (_ for _ in ()).throw(OSError("fsync")))
    with pytest.raises(OSError):
        unit.acquire("ADMIT_OPTION_FOOTER", "synthetic")
    assert clock.sleeps == []


def function_map(path: Path) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def test_scientific_function_ast_is_preserved_outside_operational_allowlist() -> None:
    before, after = function_map(BASELINE_PATH), function_map(R3_PATH)
    operational = {"resource_gate", "bind_resource_helper", "bind_resource_waiter", "admit_pins", "expected_cache_admission", "reconstruct_sources", "run"}
    assert set(before) <= set(after)
    for name in set(before) - operational:
        assert ast.dump(before[name], include_attributes=False) == ast.dump(after[name], include_attributes=False), name


def test_roots_cli_and_all_gate_callsites_are_r3() -> None:
    assert audit.OUTPUT == audit.BASE / "weekly_zone_event_value_paths_audit_06"
    assert audit.OBSERVER == audit.BASE / "weekly_zone_event_value_paths_audit_observer_06"
    assert audit.TESTS == HERE / "test_audit_weekly_zone_event_value_paths_v2r3.py"
    args = audit.parser().parse_args([])
    assert args.output == audit.OUTPUT and args.observer == audit.OBSERVER
    source = R3_PATH.read_text(encoding="utf-8")
    assert 'resource_gate("CACHE_SPOT_PATH", f"{ticker}:{day}")' in source
    assert "gate = resource_gate(stage, identity)" in source
    assert "weekly_zone_event_value_paths_audit_05" not in source


def test_wait_evidence_schema_keyset_is_exact(tmp_path: Path) -> None:
    low = {"available_ram_bytes": 1, "free_commit_bytes": 3_000_000_000}
    high = {"available_ram_bytes": 3_000_000_000, "free_commit_bytes": 3_000_000_000}
    unit, _clock = waiter(tmp_path, [low, high], [3_000_000_000, 3_000_000_000])
    unit.acquire("CACHE_SPOT_PATH", "QQQ:20240103")
    row = rows(tmp_path / "resource_wait.jsonl")[0]
    assert set(row) == wait.ROW_KEYS and row["seq"] == 0 and row["attempt"] == 0
    assert wait.load_resource_wait_rows(tmp_path / "resource_wait.jsonl") == [row]
    pin = wait.resource_wait_pin(tmp_path / "resource_wait.jsonl")
    assert set(pin) == {"path", "bytes", "sha256"} and pin["bytes"] > 0


def test_truncated_wait_evidence_is_invalid(tmp_path: Path) -> None:
    path = tmp_path / "resource_wait.jsonl"
    path.write_bytes(b'{"schema":"truncated"}')
    with pytest.raises(wait.ResourceWaitError):
        wait.load_resource_wait_rows(path)


def test_noncanonical_and_bool_sequence_wait_evidence_are_invalid(tmp_path: Path) -> None:
    low = {"available_ram_bytes": 1, "free_commit_bytes": 3_000_000_000}
    high = {"available_ram_bytes": 3_000_000_000, "free_commit_bytes": 3_000_000_000}
    unit, _clock = waiter(tmp_path, [low, high], [3_000_000_000, 3_000_000_000])
    unit.acquire("SELECT_1030", "ALL")
    valid = rows(tmp_path / "resource_wait.jsonl")[0]
    noncanonical = tmp_path / "noncanonical.jsonl"
    noncanonical.write_text(json.dumps(valid, ensure_ascii=False) + "\n", encoding="utf-8")
    with pytest.raises(wait.ResourceWaitError):
        wait.load_resource_wait_rows(noncanonical)
    invalid = dict(valid, seq=True)
    with pytest.raises(wait.ResourceWaitError):
        wait.validate_resource_wait_rows([invalid])


def test_wait_timing_relationships_are_strict(tmp_path: Path) -> None:
    low = {"available_ram_bytes": 1, "free_commit_bytes": 3_000_000_000}
    high = {"available_ram_bytes": 3_000_000_000, "free_commit_bytes": 3_000_000_000}
    unit, _clock = waiter(tmp_path, [low, high], [3_000_000_000, 3_000_000_000])
    unit.acquire("SELECT_1030", "ALL")
    valid = rows(tmp_path / "resource_wait.jsonl")[0]
    for bad in (
        {**valid, "planned_sleep_seconds": 4.0},
        {**valid, "remaining_monotonic_seconds": 599.0},
        {**valid, "attempt": 1},
    ):
        with pytest.raises(wait.ResourceWaitError):
            wait.validate_resource_wait_rows([bad])


def test_rows_after_terminal_status_are_rejected(tmp_path: Path) -> None:
    clock = Clock()
    low = {"available_ram_bytes": 1, "free_commit_bytes": 1}
    unit = wait.ResourceWaiter(
        observation=lambda: dict(low), official_gate=official_gate,
        disk_probe=lambda: 1, evidence_path=tmp_path / "resource_wait.jsonl",
        monotonic=clock.monotonic, sleeper=lambda seconds: setattr(clock, "value", clock.value + 600.0),
        utc_now=lambda: "2026-11-02T00:00:00+00:00",
    )
    with pytest.raises(wait.ResourceWaitTimeout):
        unit.acquire("STREAM_OPTION_PATHS", "ALL")
    evidence = rows(tmp_path / "resource_wait.jsonl")
    trailing = dict(
        evidence[-2], seq=len(evidence), attempt=0,
        stage="WRITE_AUDIT_OUTPUT", identity="audit.json",
        elapsed_monotonic_seconds=0.0, remaining_monotonic_seconds=600.0,
        planned_sleep_seconds=5.0,
    )
    with pytest.raises(wait.ResourceWaitError, match="after terminal"):
        wait.validate_resource_wait_rows([*evidence, trailing])


def test_journal_gate_precedes_any_input_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class TrapPath:
        def exists(self):
            pytest.fail("input probed before resource PASS")
    monkeypatch.setattr(audit, "resource_gate", lambda _stage, _identity: (_ for _ in ()).throw(wait.ResourceWaitTimeout("low")))
    journal = audit.Journal(tmp_path / "journal.jsonl")
    with pytest.raises(wait.ResourceWaitTimeout):
        with journal.unit("ADMIT_OPTION_FOOTER", "synthetic", [TrapPath()]):
            pytest.fail("unit body entered before resource PASS")
    assert not (tmp_path / "journal.jsonl").exists()


def test_reconstruct_source_own_gate_precedes_stat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audit, "resource_gate", lambda _stage, _identity: (_ for _ in ()).throw(wait.ResourceWaitTimeout("low")))
    monkeypatch.setattr(audit, "stat_record", lambda _path: pytest.fail("source stat before own PASS"))
    row = {
        "path": str(tmp_path / "missing.parquet"), "observation": {"exists": False},
        "references": [{"close_i": 390}],
    }
    with pytest.raises(wait.ResourceWaitTimeout):
        audit.reconstruct_sources([row], {}, journal=audit.Journal(tmp_path / "journal.jsonl"))


def test_stream_observation_own_gate_precedes_parquet_open(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audit, "resource_gate", lambda _stage, _identity: (_ for _ in ()).throw(wait.ResourceWaitTimeout("low")))
    monkeypatch.setattr(audit.pq, "ParquetFile", lambda *_args, **_kwargs: pytest.fail("Parquet opened before STREAM PASS"))
    with pytest.raises(wait.ResourceWaitTimeout):
        audit.stream_option_paths_checked(tmp_path, [], [], {}, audit.Journal(tmp_path / "journal.jsonl"))


def test_all_scientific_unit_entrypoints_route_through_bounded_gate() -> None:
    source = R3_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    unit_stages = {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr == "unit" and node.args and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }
    assert {
        "ADMIT_AUTHORITIES", "NORMALIZE_CALENDAR", "ADMIT_OPTION_FOOTERS",
        "SELECT_1030", "STREAM_OPTION_PATHS", "CLOSING_REHASH",
        "WRITE_AUDIT_OUTPUT", "ADMIT_OPTION_FOOTER",
    } <= unit_stages
    assert 'gate = resource_gate(stage, identity)' in source
    assert 'resource_gate("CACHE_SPOT_PATH", f"{ticker}:{day}")' in source
