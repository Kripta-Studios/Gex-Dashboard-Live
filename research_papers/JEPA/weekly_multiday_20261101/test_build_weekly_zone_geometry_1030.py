"""Artificial-only focal tests for the C state-60 geometry producer."""

from __future__ import annotations

import ast
from copy import deepcopy
from datetime import date, timedelta
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

import numpy as np
import pytest


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "build_weekly_zone_geometry_1030.py"
ENGINE_ROOT = HERE.parent / "level_oracle_20261018"


@pytest.fixture(scope="session")
def producer():
    spec = importlib.util.spec_from_file_location("c_geometry_producer_under_test", SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def engines(producer):
    paths = {name: ENGINE_ROOT / name for name in producer.ENGINE_PINS}
    return producer.load_pure_engines(paths)


def artificial_unit(producer, close_i=390, day="20240103"):
    n = close_i + 1
    strikes = np.array([95.0, 100.0, 105.0, 95.0, 100.0, 105.0])
    rights = np.array([0, 0, 0, 1, 1, 1], dtype=np.int8)
    times = producer.local_ns(day, 9, 30) + np.arange(n, dtype=np.int64) * 60_000_000_000
    shape = (n, len(strikes))
    spot = np.linspace(100.0, 102.0, n, dtype=np.float64)
    cache = {
        "time_ns": times, "strike": strikes, "right": rights,
        "bid": np.full(shape, 1.0), "ask": np.full(shape, 1.1),
        "delta": np.tile(np.array([.7, .5, .3, -.7, -.5, -.3]), (n, 1)),
        "iv": np.full(shape, .2), "vega": np.full(shape, .1),
        "theta": np.full(shape, -.01), "row_flags": np.full(shape, 7, dtype=np.uint8),
        "spot": spot, "spot_valid": np.ones(n, dtype=bool),
        "oi_contract_idx": np.arange(len(strikes), dtype=np.int32),
        "oi_value": np.array([100, 200, 300, 150, 250, 350], dtype=np.int64),
        "oi_available_ns": np.full(len(strikes), times[0], dtype=np.int64),
        "oi_valid": np.ones(len(strikes), dtype=bool),
    }
    session_kind = "FULL" if close_i == 390 else "SHORT"
    calendar = {
        "calendar_ordinal": 0, "ticker": "SPY", "date": day,
        "close_i": close_i, "session_kind": session_kind,
    }
    admission = {
        "ticker": "SPY", "date": day, "ticker_ordinal": 0,
        "session_kind": session_kind, "close_i": close_i,
        "cache_status": "AVAILABLE", "missing_reason": None, "authority": "H1",
        "cache_metadata_path": "X:/synthetic/cache.json",
        "cache_metadata_sha256": "1" * 64, "npz_path": "X:/synthetic/cache.npz",
        "npz_sha256": "2" * 64,
    }
    metadata = {
        "clock_basis": "NATIVE_STORED_TIMESTAMP",
        "oi_clock_basis": "NATIVE_STORED_TIMESTAMP",
        "oi_assumed_availability": None, "clock_delay_applied": False,
    }
    return calendar, admission, metadata, cache


def project_state(producer, row):
    return {key: row[key] for key in producer.SEMANTIC_STATE_COLUMNS}


def project_levels(producer, rows):
    return [{key: row[key] for key in producer.SEMANTIC_LEVEL_COLUMNS} for row in rows]


def test_exact_schema_names_types_and_nullability(producer):
    states = producer.states_schema()
    levels = producer.levels_schema()
    assert len(states) == 39 and len(levels) == 20
    assert states.names == list(producer.SEMANTIC_STATE_COLUMNS) + [
        "cache_metadata_path", "cache_metadata_sha256", "cache_npz_path",
        "cache_npz_sha256", "clock_basis", "oi_clock_basis",
        "oi_assumed_availability", "clock_delay_applied", "receipt_status",
    ]
    assert levels.names == list(producer.SEMANTIC_LEVEL_COLUMNS) + [
        "provenance_components_json", "cache_npz_path", "cache_npz_sha256",
        "clock_basis", "oi_clock_basis", "receipt_status",
    ]
    assert [field.nullable for field in states][:9] == [False] * 8 + [True]
    assert all(not field.nullable for field in levels)
    assert str(states.field("trade_date").type) == "date32[day]"
    assert str(states.field("state_clock_local").type) == "timestamp[ns]"
    assert str(levels.field("source_mask").type) == "uint8"
    with pytest.raises((TypeError, ValueError, OverflowError)):
        producer.pa.array([-1], type=levels.field("source_mask").type)
    nan_values = producer.pa.array([float("nan")], type=levels.field("center").type)
    assert np.isnan(nan_values[0].as_py())


@pytest.mark.parametrize("close_i,expected_tau", [
    (390, 330 * 60 / (365 * 86400)),
    (210, 150 * 60 / (365 * 86400)),
])
def test_state60_full_short_geometry_and_tau(producer, engines, close_i, expected_tau):
    engine, clocks = engines
    calendar, admission, metadata, cache = artificial_unit(producer, close_i)
    state, levels = producer.compute_identity_geometry(calendar, admission, metadata, cache, engine, clocks)
    assert state["geometry_status"] == "AVAILABLE_GEOMETRY"
    assert state["state_i"] == 60 and state["first_available_at"] == cache["time_ns"][60]
    assert state["fib_component_count"] == 13
    assert state["call_oi_wall_count"] == state["put_oi_wall_count"] == 3
    assert state["call_gamma_wall_count"] == state["put_gamma_wall_count"] == 3
    assert state["tau_years"] == expected_tau
    assert len(levels) == state["level_count"] and len({row["anchor_id"] for row in levels}) == len(levels)
    assert [row["cluster_ordinal"] for row in levels] == list(range(len(levels)))


def test_missing_invalid_ib_and_invalid_state60(producer, engines):
    engine, clocks = engines
    calendar, admission, metadata, cache = artificial_unit(producer)
    missing = dict(admission, cache_status="MISSING", missing_reason="MISSING_SOURCE",
                   cache_metadata_path=None, cache_metadata_sha256=None,
                   npz_path=None, npz_sha256=None)
    state = producer._base_state(calendar, missing)
    assert state["geometry_status"] == "MISSING_SOURCE" and state["receipt_status"] == "NOT_APPLICABLE"
    invalid_ib = deepcopy(cache)
    invalid_ib["spot_valid"][:4] = False
    state, levels = producer.compute_identity_geometry(calendar, admission, metadata, invalid_ib, engine, clocks)
    assert state["geometry_status"] == "INVALID_IB" and state["ib_observed"] is None and not levels
    invalid_spot = deepcopy(cache)
    invalid_spot["spot_valid"][60] = False
    state, levels = producer.compute_identity_geometry(calendar, admission, metadata, invalid_spot, engine, clocks)
    assert state["geometry_status"] == "INVALID_STATE60"
    assert state["ib_low"] is not None and state["spot_1030"] is None and not levels


def test_ib_exact_57_vs_56_and_zero_range(producer, engines):
    engine, clocks = engines
    calendar, admission, metadata, cache = artificial_unit(producer)
    exactly_57 = deepcopy(cache)
    exactly_57["spot_valid"][:3] = False
    state, _ = producer.compute_identity_geometry(calendar, admission, metadata, exactly_57, engine, clocks)
    assert state["geometry_status"] == "AVAILABLE_GEOMETRY" and state["ib_observed"] == 57
    exactly_56 = deepcopy(cache)
    exactly_56["spot_valid"][:4] = False
    state, _ = producer.compute_identity_geometry(calendar, admission, metadata, exactly_56, engine, clocks)
    assert state["geometry_status"] == "INVALID_IB" and state["ib_observed"] is None
    zero_range = deepcopy(cache)
    zero_range["spot"][:60] = 100.0
    state, _ = producer.compute_identity_geometry(calendar, admission, metadata, zero_range, engine, clocks)
    assert state["geometry_status"] == "INVALID_IB" and state["ib_observed"] is None


def test_gamma_full_short_is_tau_sensitive(producer, engines):
    engine, clocks = engines
    units = []
    for close_i in (390, 210):
        calendar, admission, metadata, cache = artificial_unit(producer, close_i)
        _state, levels = producer.compute_identity_geometry(calendar, admission, metadata, cache, engine, clocks)
        weights = [
            component["weight_f64"]
            for level in levels
            for component in json.loads(level["semantic_components_json"])
            if component["kind"] == "WALL" and component["name"] == "BS_GAMMA_PROXY"
        ]
        units.append(weights)
    assert units[0] and units[1] and units[0] != units[1]


def test_clustering_is_non_chaining_and_oi_tie_breaks_by_strike(producer, engines):
    engine, clocks = engines
    raw = [
        {"center": 0.0, "source_mask": 1, "name": "A"},
        {"center": 1.5, "source_mask": 2, "name": "B"},
        {"center": 3.0, "source_mask": 4, "name": "C"},
    ]
    clustered = engine.deduplicate_levels(raw, .75)
    assert [row["n_components"] for row in clustered] == [2, 1]
    _calendar, _admission, _metadata, cache = artificial_unit(producer)
    cache["oi_value"][:] = 100
    oi = engine.available_oi_matrix(cache, clocks.FULL)[60]
    levels = engine.causal_levels(cache, oi, 60, 100.0, 102.0, .1, clocks.FULL)
    call_oi = [
        item for level in levels for item in json.loads(level["components_json"])
        if item["name"] == "OI" and item["source_mask"] == 2
    ]
    assert [item["center"] for item in call_oi] == [95.0, 100.0, 105.0]


def test_oi_new_invalid_record_does_not_backfill(producer, engines):
    engine, clocks = engines
    _, _, _, cache = artificial_unit(producer)
    cache["oi_contract_idx"] = np.array([0, 0], dtype=np.int32)
    cache["oi_value"] = np.array([100, -1], dtype=np.int64)
    cache["oi_available_ns"] = np.array([cache["time_ns"][0], cache["time_ns"][50]], dtype=np.int64)
    cache["oi_valid"] = np.array([True, False])
    row = engine.available_oi_matrix(cache, clocks.FULL)[60]
    assert np.isnan(row[0])


def test_suffix_mutation_preserves_semantic_projection(producer, engines):
    engine, clocks = engines
    calendar, admission, metadata, cache = artificial_unit(producer)
    state_a, levels_a = producer.compute_identity_geometry(calendar, admission, metadata, cache, engine, clocks)
    changed = deepcopy(cache)
    changed["spot"][61:] = 999.0
    changed["spot_valid"][61:] = False
    for name in ("bid", "ask", "delta", "iv", "vega", "theta"):
        changed[name][61:] = 777.0
    changed["row_flags"][61:] = 0
    changed["oi_contract_idx"] = np.append(changed["oi_contract_idx"], 0).astype(np.int32)
    changed["oi_value"] = np.append(changed["oi_value"], 999999).astype(np.int64)
    changed["oi_available_ns"] = np.append(changed["oi_available_ns"], changed["time_ns"][100]).astype(np.int64)
    changed["oi_valid"] = np.append(changed["oi_valid"], True)
    state_b, levels_b = producer.compute_identity_geometry(calendar, admission, metadata, changed, engine, clocks)
    assert project_state(producer, state_a) == project_state(producer, state_b)
    assert project_levels(producer, levels_a) == project_levels(producer, levels_b)


def permute_contracts(cache, order):
    result = deepcopy(cache)
    order = np.asarray(order)
    inverse = np.empty(len(order), dtype=np.int32)
    inverse[order] = np.arange(len(order), dtype=np.int32)
    for name in ("strike", "right"):
        result[name] = result[name][order]
    for name in ("bid", "ask", "delta", "iv", "vega", "theta", "row_flags"):
        result[name] = result[name][:, order]
    result["oi_contract_idx"] = inverse[result["oi_contract_idx"]]
    return result


def add_future_only_contract(cache):
    result = deepcopy(cache)
    result["strike"] = np.append(result["strike"], 110.0)
    result["right"] = np.append(result["right"], np.int8(0))
    n = len(result["time_ns"])
    for name in ("bid", "ask", "delta", "iv", "vega", "theta"):
        column = np.full((n, 1), np.nan)
        column[61:] = .25
        result[name] = np.concatenate([result[name], column], axis=1)
    flags = np.zeros((n, 1), dtype=np.uint8)
    flags[61:] = 1
    result["row_flags"] = np.concatenate([result["row_flags"], flags], axis=1)
    return result


def test_column_permutation_and_future_only_contract_preserve_ids(producer, engines):
    engine, clocks = engines
    calendar, admission, metadata, cache = artificial_unit(producer)
    baseline_state, baseline_levels = producer.compute_identity_geometry(calendar, admission, metadata, cache, engine, clocks)
    for variant in (permute_contracts(cache, [3, 0, 4, 1, 5, 2]), add_future_only_contract(cache)):
        state, levels = producer.compute_identity_geometry(calendar, admission, metadata, variant, engine, clocks)
        assert project_state(producer, baseline_state) == project_state(producer, state)
        assert project_levels(producer, baseline_levels) == project_levels(producer, levels)


def test_anchor_canonical_negative_zero_and_contract_index_exclusion(producer):
    assert producer.canonical_f64(-0.0) == producer.canonical_f64(0.0) == "0x0.0p+0"
    with pytest.raises(producer.GeometryError):
        producer.canonical_f64(float("nan"))
    components = producer.semantic_components(
        '[{"center":100.0,"contract_i":1,"name":"CALL_OI","source_mask":2,"weight":7.0}]',
        np.array([90.0, 100.0]), np.array([1, 0]),
    )
    assert "contract_i" not in components[0]


def test_entry_frozen_reuses_anchor_and_session_reset_changes_it(producer, engines):
    engine, clocks = engines
    calendar, admission, metadata, cache = artificial_unit(producer, day="20240103")
    _state, baseline = producer.compute_identity_geometry(calendar, admission, metadata, cache, engine, clocks)
    for _horizon in ("D", "D1", "H2"):
        _state, repeated = producer.compute_identity_geometry(calendar, admission, metadata, cache, engine, clocks)
        assert [row["anchor_id"] for row in repeated] == [row["anchor_id"] for row in baseline]
    reset_calendar, reset_admission, reset_metadata, reset_cache = artificial_unit(producer, day="20240104")
    _state, reset = producer.compute_identity_geometry(reset_calendar, reset_admission, reset_metadata, reset_cache, engine, clocks)
    assert set(row["anchor_id"] for row in reset).isdisjoint(row["anchor_id"] for row in baseline)


def test_calendar_2790_canonical_order_and_short_count(producer):
    days = [(date(2023, 1, 1) + timedelta(days=i)).strftime("%Y%m%d") for i in range(930)]
    short = set(days[:8])
    rows = [
        {"ticker": ticker, "date": day, "close_i": 210 if day in short else 390}
        for ticker in ("QQQ", "SPXW", "SPY") for day in days
    ]
    calendar, semantic = producer.normalize_calendar(
        {"schema": "weekly_h2_boundary_unified_calendar_v1", "rows": rows},
        expected_first={"calendar_ordinal": 0, "ticker": "SPY", "date": days[0], "close_i": 210, "session_kind": "SHORT"},
        expected_last={"calendar_ordinal": 2789, "ticker": "SPXW", "date": days[-1], "close_i": 390, "session_kind": "FULL"},
    )
    assert len(calendar) == 2790 and sum(row["close_i"] == 210 for row in calendar) == 24
    assert [(row["ticker"], row["date"]) for row in calendar[:3]] == [("SPY", days[0]), ("QQQ", days[0]), ("SPXW", days[0])]
    assert semantic.count(b"\n") == 2790


def test_validate_rows_reconciles_levels_and_oi(producer, engines):
    engine, clocks = engines
    states, levels = [], []
    for ordinal in range(2790):
        day = (date(2020, 1, 1) + timedelta(days=ordinal)).strftime("%Y%m%d")
        close_i = 210 if 2595 <= ordinal < 2619 else 390
        calendar, admission, metadata, cache = artificial_unit(producer, close_i=close_i, day=day)
        calendar["calendar_ordinal"] = ordinal
        admission["authority"] = "Q3" if 2619 <= ordinal < 2772 or ordinal >= 2778 else "H1"
        if ordinal >= 2772:
            admission.update(cache_status="MISSING", missing_reason="MISSING_SOURCE",
                             cache_metadata_path=None, cache_metadata_sha256=None,
                             npz_path=None, npz_sha256=None)
            state, unit_levels = producer._base_state(calendar, admission), []
        else:
            state, unit_levels = producer.compute_identity_geometry(calendar, admission, metadata, cache, engine, clocks)
        states.append(state)
        levels.extend(unit_levels)
    counts = producer.validate_rows(states, levels)
    assert counts["AVAILABLE_GEOMETRY"] == 2772 and counts["MISSING_SOURCE"] == 18
    assert {key: counts[key] for key in ("h1_full_available", "h1_short_available", "q3_available", "h1_missing", "q3_missing")} == {
        "h1_full_available": 2595, "h1_short_available": 24, "q3_available": 153,
        "h1_missing": 6, "q3_missing": 12,
    }
    producer.validate_final_counts(states, levels, counts)
    broken_levels = deepcopy(levels)
    broken_levels[0]["ticker"] = "QQQ"
    with pytest.raises(producer.GeometryError):
        producer.validate_rows(states, broken_levels)


def test_binding_pending_fails_before_runtime_roots(producer, tmp_path):
    binding = tmp_path / "binding.json"
    binding.write_text('{"status":"PENDING"}', encoding="utf-8")
    digest = hashlib.sha256(binding.read_bytes()).hexdigest()
    output, observer = tmp_path / "out", tmp_path / "observer"
    code = producer.main([
        "--binding-json", str(binding), "--binding-sha256", digest,
        "--output-dir", str(output), "--observer-dir", str(observer),
        "--journal", str(observer / "journal.jsonl"),
    ])
    assert code == 10 and not output.exists() and not observer.exists()


def synthetic_binding(producer):
    def pin(name, sha="0" * 64, size=1):
        return {"path": "C:/synthetic/" + name, "bytes": size, "sha256": sha}
    contracts = {name: pin(name, sha) for name, sha in producer.CONTRACT_PINS.items()}
    engines = {name: pin(name, sha) for name, sha in producer.ENGINE_PINS.items()}
    implementation = producer.compact_pin(Path(producer.__file__).resolve())
    return {
        "schema": producer.BINDING_SCHEMA, "status": producer.BINDING_STATUS,
        "contracts": contracts, "engines": engines,
        "b_final": {
            "bundle": pin("bundle.json"), "review": pin("review.md"),
            "cache_admission": pin("cache_admission.jsonl", producer.CACHE_ADMISSION_SHA256, producer.CACHE_ADMISSION_BYTES),
            "raw_calendar": pin("calendar.json"),
            "calendar_semantic": {"bytes": producer.CALENDAR_SEMANTIC_BYTES, "sha256": producer.CALENDAR_SEMANTIC_SHA256, "rows": 2790, "order": "DATE_ASC_TICKER_ORDINAL_SPY_QQQ_SPXW"},
        },
        "resource_helper": pin("resource.py", producer.RESOURCE_HELPER_SHA256, producer.RESOURCE_HELPER_BYTES),
        "runtime": {"python": producer.sys.version, "numpy": producer.np.__version__, "pyarrow": producer.pa.__version__, "producer": implementation},
        "runtime_roots": {"output_dir": "C:/synthetic/output", "observer_dir": "C:/synthetic/observer", "journal": "C:/synthetic/observer/journal.jsonl"},
        "windows_publication": {"api": "MoveFileExW", "flags": 8, "same_volume": True, "replace": False},
    }


def test_complete_runtime_binding_accepts_only_exact_helper_versions_and_roots(producer):
    binding = synthetic_binding(producer)
    assert producer.validate_runtime_binding(binding)["runtime_roots"]["output_dir"].endswith("/output")
    for mutation in (
        lambda value: value["resource_helper"].update(bytes=1),
        lambda value: value["runtime"].update(numpy="0.0"),
        lambda value: value.pop("runtime_roots"),
    ):
        bad = deepcopy(binding)
        mutation(bad)
        with pytest.raises(producer.GeometryError):
            producer.validate_runtime_binding(bad)


def test_final_b_bundle_rejects_partial_or_self_asserted_pass(producer):
    binding = synthetic_binding(producer)
    def pin(role): return {"path": "C:/synthetic/" + role, "bytes": 1, "sha256": "0" * 64}
    flags = {name: False for name in producer.FINAL_B_FLAG_KEYS}
    flags.update(option_raw_values_read=True, parquet_footers_read=True, spot_cache_arrays_read=True, selected_policy=None)
    authority = {name: pin("authority_" + name) for name in producer.B_AUTHORITY_KEYS}
    authority["unified_calendar"] = binding["b_final"]["raw_calendar"]
    complete = {
        "schema": "weekly_zone_event_value_paths_final_admission_v1", "status": "PASS_FINAL_B_ADMISSION",
        "producer": {"manifest": pin("producer_manifest"), "outputs": {name: pin("producer_output_" + name) for name in producer.B_OUTPUT_NAMES}, "observer": {name: pin("producer_observer_" + name) for name in ("exit", "process", "journal")}},
        "auditor": {name: pin("auditor_" + name) for name in ("audit", "manifest", "exit", "process", "journal")},
        "authority_inputs": authority,
        "calendar": {"raw_file_pin": binding["b_final"]["raw_calendar"], "semantic_jsonl": binding["b_final"]["calendar_semantic"], "identity_set_preserved": True, "close_i_preserved": True},
        "flags": flags, "data_scope": "SEEN_DEVELOPMENT",
    }
    complete["producer"]["outputs"]["cache_admission.jsonl"] = binding["b_final"]["cache_admission"]
    producer.validate_final_b_bundle(complete, binding)
    illegal_alias = deepcopy(complete)
    illegal_alias["auditor"]["audit"] = illegal_alias["producer"]["manifest"]
    for bad in ({"status": "PASS_FINAL_B_ADMISSION"}, dict(complete, auditor={}), dict(complete, authority_inputs={}), illegal_alias):
        with pytest.raises(producer.GeometryError):
            producer.validate_final_b_bundle(bad, binding)


def test_final_b_closure_reconstructs_manifests_exits_and_journals(producer, tmp_path):
    def write(name, value):
        path = tmp_path / name
        path.write_bytes(producer.canonical_json_bytes(value, newline=True))
        return producer.compact_pin(path)
    def write_lines(name, values):
        path = tmp_path / name
        path.write_bytes(b"".join(producer.canonical_json_bytes(value, newline=True) for value in values))
        return producer.compact_pin(path)
    authority = {name: write("authority_" + name + ".json", {"sealed": name}) for name in producer.B_AUTHORITY_KEYS}
    outputs = {name: write("output_" + name, {"sealed": name}) for name in producer.B_OUTPUT_NAMES}
    manifest_outputs = {name: {**pin, "rows": producer.B_OUTPUT_ROWS[name]} for name, pin in outputs.items()}
    producer_manifest = write("producer_manifest.json", {
        "schema": "weekly_zone_event_value_paths_manifest_v2_calendar_normalized",
        "status": "COMPLETE_OUTCOME_FREE_VALUE_PATHS", "outputs": manifest_outputs,
        "authority_inputs": authority,
    })
    producer_process = write("producer_process.json", {"pid": 101, "creation_epoch": 1.5})
    producer_exit = write("producer_exit.json", {"exit_code": 0, "value_child_exit_code": 0, "changed_pins": [], "metadata_error": None, "retry": False, "pid": 101, "creation_epoch": 1.5})
    producer_journal_rows = [
        {"at_utc": "2026-11-02T00:00:00+00:00", "event": "STARTED", "kind": "CLOSING_REHASH", "identity": "OUTPUT:manifest.json", "paths": [], "gate": {"available_ram_bytes": 3_000_000_000, "free_commit_bytes": 3_000_000_000, "disk_free_bytes": 3_000_000_000}},
        {"at_utc": "2026-11-02T00:00:01+00:00", "event": "COMPLETED", "kind": "CLOSING_REHASH", "identity": "OUTPUT:manifest.json", "paths": [], "gate": {"available_ram_bytes": 3_000_000_000, "free_commit_bytes": 3_000_000_000, "disk_free_bytes": 3_000_000_000}, "details": {}},
    ]
    producer_journal = write_lines("producer_journal.jsonl", producer_journal_rows)
    audit = write("audit.json", {"schema": "weekly_zone_event_value_paths_audit_v2_calendar_normalized", "status": "PASS"})
    audit_manifest = write("audit_manifest.json", {"schema": "weekly_zone_event_value_paths_audit_manifest_v2_calendar_normalized", "status": "PASS", "authority_inputs": authority})
    audit_process = write("audit_process.json", {"pid": 202, "creation_epoch": 2.5})
    audit_exit = write("audit_exit.json", {"exit_code": 0, "value_child_exit_code": 0, "changed_pins": [], "metadata_error": None, "retry": False, "pid": 202, "creation_epoch": 2.5})
    audit_journal = write("audit_journal.jsonl", {
        "utc": "2026-11-02T00:00:00+00:00", "stage": "WRITE_AUDIT_OUTPUT",
        "event": "COMPLETED", "identity": "manifest.json", "pins_before": {},
        "pins_after": {}, "details": {},
    })
    bundle = {
        "producer": {"manifest": producer_manifest, "outputs": outputs, "observer": {"exit": producer_exit, "process": producer_process, "journal": producer_journal}},
        "auditor": {"audit": audit, "manifest": audit_manifest, "exit": audit_exit, "process": audit_process, "journal": audit_journal},
        "authority_inputs": authority,
    }
    producer.validate_final_b_closure(bundle)
    mixed_rows = deepcopy(producer_journal_rows)
    mixed_rows[0]["stage"] = mixed_rows[0].pop("kind")
    bundle["producer"]["observer"]["journal"] = write_lines("producer_journal.jsonl", mixed_rows)
    with pytest.raises(producer.GeometryError):
        producer.validate_final_b_closure(bundle)
    bundle["producer"]["observer"]["journal"] = write_lines("producer_journal.jsonl", producer_journal_rows)
    invalid_manifest = json.loads((tmp_path / "producer_manifest.json").read_text(encoding="utf-8"))
    invalid_manifest["outputs"]["summary.json"]["rows"] = None
    (tmp_path / "producer_manifest.json").write_bytes(producer.canonical_json_bytes(invalid_manifest, newline=True))
    bundle["producer"]["manifest"] = producer.compact_pin(tmp_path / "producer_manifest.json")
    with pytest.raises(producer.GeometryError):
        producer.validate_final_b_closure(bundle)
    invalid_manifest["outputs"]["summary.json"]["rows"] = 1
    (tmp_path / "producer_manifest.json").write_bytes(producer.canonical_json_bytes(invalid_manifest, newline=True))
    bundle["producer"]["manifest"] = producer.compact_pin(tmp_path / "producer_manifest.json")
    bad_exit = json.loads((tmp_path / "audit_exit.json").read_text(encoding="utf-8"))
    bad_exit["value_child_exit_code"] = 1
    (tmp_path / "audit_exit.json").write_bytes(producer.canonical_json_bytes(bad_exit, newline=True))
    bundle["auditor"]["exit"] = producer.compact_pin(tmp_path / "audit_exit.json")
    with pytest.raises(producer.GeometryError):
        producer.validate_final_b_closure(bundle)
    with pytest.raises(producer.GeometryError):
        producer._validate_retained_exit({
            "exit_code": 0, "audit_child_exit_code": 0, "changed_pins": [],
            "metadata_error": None, "retry": False, "pid": 202,
            "creation_epoch": 2.5,
        }, "auditor")


def test_source_never_calls_build_day_or_reads_forbidden_science():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert not any(isinstance(node.func, ast.Attribute) and node.func.attr == "build_day" for node in calls)
    assert not any(isinstance(node.func, ast.Name) and node.func.id == "build_day" for node in calls)
    source = SOURCE.read_text(encoding="utf-8")
    for forbidden in ("labels.parquet", "outcomes.parquet", "oracle_value", "selected_contracts("):
        assert forbidden not in source
    run_source = source[source.index("def run("):source.index("def parser()")]
    assert run_source.index("validate_final_b_closure(bundle_value)") < run_source.index("load_cache_arrays(npz_path)")
    assert run_source.index('Journal(journal_path') < run_source.index('bundle_path.read_text')


def test_windows_binding_and_output_keysets_are_fail_closed(producer):
    assert producer.WindowsPublisher.MOVEFILE_WRITE_THROUGH == 0x8
    assert producer.OUTPUT_NAMES == (
        "geometry_states_1030.parquet", "geometry_levels_1030.parquet",
        "coverage.json", "manifest.json",
    )
    assert "manifest.json" not in producer.OUTPUT_NAMES[:3]


def test_optional_underlying_age_is_listed_but_never_opened(producer, monkeypatch):
    accessed = []
    values = {name: np.array([1]) for name in producer.ARRAY_NAMES}
    values[producer.OPTIONAL_UNOPENED_ARRAY] = np.array([999])

    class Stored:
        files = list(values)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def __getitem__(self, name):
            accessed.append(name)
            return values[name]

    monkeypatch.setattr(producer.np, "load", lambda *_args, **_kwargs: Stored())
    arrays, physical = producer.load_cache_arrays(Path("synthetic.npz"))
    assert set(arrays) == set(producer.ARRAY_NAMES)
    assert producer.OPTIONAL_UNOPENED_ARRAY in physical
    assert producer.OPTIONAL_UNOPENED_ARRAY not in accessed


def test_undeclared_extra_array_is_fatal(producer, monkeypatch):
    values = {name: np.array([1]) for name in producer.ARRAY_NAMES}
    values["future_oracle"] = np.array([999])

    class Stored:
        files = list(values)
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def __getitem__(self, name): return values[name]

    monkeypatch.setattr(producer.np, "load", lambda *_args, **_kwargs: Stored())
    with pytest.raises(producer.GeometryError):
        producer.load_cache_arrays(Path("synthetic.npz"))


@pytest.mark.parametrize("bad", [True, 2_000_000_000.0, "2000000000"])
def test_resource_gate_rejects_coercible_non_integers(producer, monkeypatch, tmp_path, bad):
    monkeypatch.setattr(producer.shutil, "disk_usage", lambda _root: type("Usage", (), {"free": 3_000_000_000})())
    with pytest.raises(producer.GeometryError):
        producer.disk_gate(tmp_path, {"available_ram_bytes": bad, "free_commit_bytes": 3_000_000_000})


def test_publish_failure_and_postmove_drift_are_durably_unadoptable(producer, monkeypatch, tmp_path):
    monkeypatch.setattr(producer.shutil, "disk_usage", lambda _root: type("Usage", (), {"free": 3_000_000_000})())

    class Journal:
        def __init__(self): self.rows = []
        def append(self, *args): self.rows.append(args)

    class Publisher:
        def __init__(self, fail=False, mutate=False): self.fail, self.mutate = fail, mutate
        def volume_id(self, _path): return "same"
        def move(self, source, target):
            if self.fail:
                raise producer.GeometryError("synthetic MoveFileExW failure", 15)
            source.rename(target)
            if self.mutate:
                (target / "manifest.json").write_bytes(b"corrupt")

    observe = lambda: {"available_ram_bytes": 3_000_000_000, "free_commit_bytes": 3_000_000_000}
    for fail, mutate in ((True, False), (False, True)):
        staging = tmp_path / ("stage-fail" if fail else "stage-drift")
        final = tmp_path / ("final-fail" if fail else "final-drift")
        staging.mkdir()
        output = staging / "manifest.json"
        output.write_bytes(b"sealed")
        expected = {output.name: producer.compact_pin(output)}
        journal = Journal()
        with pytest.raises(producer.GeometryError):
            producer.publish_checked(staging, final, expected, Publisher(fail, mutate), journal, observe)
        assert journal.rows[-1][2] == "ERROR"
        assert journal.rows[-1][-1]["adoptable"] is False
        if mutate:
            assert final.exists()  # post-rename crash/failure is retained but unadoptable


def test_closing_output_binds_write_pin_and_flushes(producer, tmp_path):
    path = tmp_path / "output.bin"
    path.write_bytes(b"original")
    expected = producer.compact_pin(path)

    class Publisher:
        def __init__(self): self.flushed = False
        def flush_regular_file(self, _path): self.flushed = True

    publisher = Publisher()
    before, after = producer.close_output_checked(path, expected, publisher)
    assert publisher.flushed and before == after == expected
    path.write_bytes(b"mutated")
    with pytest.raises(producer.GeometryError):
        producer.close_output_checked(path, expected, publisher)


def test_same_byte_replacement_fails_physical_snapshot(producer, tmp_path):
    path = tmp_path / "authority.json"
    replacement = tmp_path / "replacement.json"
    path.write_bytes(b"same")
    snapshot = producer.admitted_snapshot(path, "synthetic authority")
    replacement.write_bytes(b"same")
    os.replace(replacement, path)
    with pytest.raises(producer.GeometryError):
        producer.require_snapshot(path, snapshot, "synthetic authority closing")


def test_level_row_groups_never_split_identity(producer):
    rows = []
    for identity, count in ((0, 4), (1, 5), (2, 2)):
        rows.extend({"calendar_ordinal": identity} for _ in range(count))
    groups = producer.level_row_groups(rows, limit=6)
    assert groups == [(0, 4), (4, 5), (9, 2)]
    for start, length in groups:
        identities = [row["calendar_ordinal"] for row in rows[start:start + length]]
        assert identities == sorted(identities)


def test_anchor_digest_matches_independent_canonical_payload(producer):
    level = {"level_id": 2, "center": 101.25, "source_mask": 3}
    components = [{
        "kind": "FIB", "name": "FIB", "source_mask": 1,
        "ratio_f64": float(.5).hex(), "center_f64": float(101.25).hex(),
    }]
    payload = {
        "anchor_schema": "C_GEOMETRY_1030_ANCHOR_V1", "ticker": "SPY",
        "date": "2024-01-03", "state_i": 60, "close_i": 390,
        "cluster_ordinal": 2, "center_f64": float(101.25).hex(),
        "band_f64": float(.25).hex(), "source_mask": 3, "components": components,
    }
    expected = hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()
    assert producer.anchor_id("SPY", "20240103", 390, level, components, .25) == expected


def test_metadata_clock_cross_rules(producer):
    _calendar, admission, _, cache = artificial_unit(producer)
    schema = {name: {"shape": list(value.shape), "dtype": str(value.dtype)} for name, value in cache.items()}
    metadata = {
        "ticker": "SPY", "date": "20240103", "version": "LEVEL_DAILY_CACHE_V1",
        "sha256": admission["npz_sha256"], "timezone_convention": "America/New_York naive",
        "clock_basis": "NATIVE_STORED_TIMESTAMP", "oi_clock_basis": "NATIVE_STORED_TIMESTAMP",
        "oi_assumed_availability": None, "clock_delay_applied": False, "array_schema": schema,
    }
    admission["cache_version"] = "LEVEL_DAILY_CACHE_V1"
    producer.validate_cache_metadata(metadata, admission, cache)
    bad = dict(metadata, oi_assumed_availability="2024-01-03 09:30:00")
    with pytest.raises(producer.GeometryError):
        producer.validate_cache_metadata(bad, admission, cache)
