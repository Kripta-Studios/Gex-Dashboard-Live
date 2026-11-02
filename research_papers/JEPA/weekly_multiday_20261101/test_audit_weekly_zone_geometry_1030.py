"""Artificial-only fixtures for the independent C geometry auditor."""
from __future__ import annotations

import ast
from copy import deepcopy
from datetime import date, timedelta
import hashlib
import json
import os
from pathlib import Path
import shutil

import numpy as np
import pyarrow as pa
import pytest

import audit_weekly_zone_geometry_1030 as audit
import build_weekly_zone_geometry_1030 as producer


HERE = Path(__file__).resolve().parent


def compact_file_pin(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def synthetic_cache(close_i: int = 390) -> dict[str, np.ndarray]:
    slots = close_i + 1
    strikes = np.array([95.0, 100.0, 105.0, 110.0, 95.0, 100.0, 105.0, 110.0])
    rights = np.array([0, 0, 0, 0, 1, 1, 1, 1], dtype=np.int8)
    shape = (slots, len(strikes))
    start = np.datetime64("2026-01-05T09:30:00", "ns").astype(np.int64)
    time_ns = start + np.arange(slots, dtype=np.int64) * 60_000_000_000
    spot = np.full(slots, 102.0)
    spot[:60] = np.linspace(100.0, 104.0, 60)
    arrays: dict[str, np.ndarray] = {
        "time_ns": time_ns, "strike": strikes, "right": rights,
        "spot": spot, "spot_valid": np.ones(slots, dtype=bool),
        "oi_contract_idx": np.arange(len(strikes), dtype=np.int32),
        "oi_value": np.array([100, 300, 200, 50, 120, 320, 220, 60], dtype=np.int64),
        "oi_available_ns": np.full(len(strikes), time_ns[0], dtype=np.int64),
        "oi_valid": np.ones(len(strikes), dtype=bool),
    }
    for name in ("bid", "ask", "delta", "iv", "vega", "theta"):
        arrays[name] = np.full(shape, np.nan)
    arrays["row_flags"] = np.zeros(shape, dtype=np.uint8)
    arrays["iv"][60] = 0.2
    arrays["row_flags"][60] = 1
    return arrays


def metadata(arrays: dict[str, np.ndarray], close_i: int = 390) -> dict[str, object]:
    result: dict[str, object] = {
        "version": "SESSION_CLOCK_CACHE_V1" if close_i == 210 else "LEVEL_DAILY_CACHE_V1",
        "ticker": "SPY", "date": "2026-01-05", "clock_basis": "NATIVE_STORED_TIMESTAMP",
        "sha256": "2" * 64, "timezone_convention": "America/New_York naive",
        "oi_clock_basis": "NATIVE_STORED_TIMESTAMP", "oi_assumed_availability": None,
        "clock_delay_applied": False,
        "array_schema": {name: {"shape": list(value.shape), "dtype": str(value.dtype)}
                         for name, value in arrays.items()},
    }
    if close_i == 210:
        result["session_clock"] = {"close_i": 210, "n_slots": 211}
    return result


def source(close_i: int = 390) -> dict[str, object]:
    return {
        "ticker": "SPY", "ticker_ordinal": 0, "date": "2026-01-05",
        "trade_date": date(2026, 1, 5), "session_kind": "FULL" if close_i == 390 else "SHORT",
        "close_i": close_i, "cache_status": "AVAILABLE", "missing_reason": None,
        "authority": "Q3", "calendar_ordinal": 0,
        "cache_metadata_path": "C:/synthetic/cache.json", "cache_metadata_bytes": 1,
        "cache_metadata_sha256": "1" * 64, "npz_path": "C:/synthetic/cache.npz",
        "npz_bytes": 1, "npz_sha256": "2" * 64,
        "cache_version": "SESSION_CLOCK_CACHE_V1" if close_i == 210 else "LEVEL_DAILY_CACHE_V1",
    }


@pytest.fixture(scope="module")
def engines() -> audit.Engines:
    return audit.bind_engines()


def test_exact_arrow_schemas_and_semantic_prefixes() -> None:
    states, levels = audit.state_schema(), audit.level_schema()
    assert len(states) == 39 and len(levels) == 20
    assert states.names[:30] == list(audit.STATE_SEMANTIC_COLUMNS)
    assert levels.names[:14] == list(audit.LEVEL_SEMANTIC_COLUMNS)
    assert states.field("missing_reason").nullable
    assert not states.field("calendar_ordinal").nullable
    assert all(not field.nullable for field in levels)
    assert states.field("trade_date").type == pa.date32()
    assert states.field("state_clock_local").type == pa.timestamp("ns")


def test_state60_full_and_short_use_real_pinned_graph(engines: audit.Engines) -> None:
    for close_i, expected_tau in ((390, 330 * 60 / (365 * 86400)),
                                  (210, 150 * 60 / (365 * 86400))):
        arrays = synthetic_cache(close_i)
        state, levels = audit.reconstruct_identity(source(close_i), engines, arrays, metadata(arrays, close_i))
        assert state["geometry_status"] == "AVAILABLE_GEOMETRY"
        assert state["fib_component_count"] == 13
        assert state["tau_years"] == expected_tau
        assert state["level_count"] == len(levels) > 0
        assert state["known_contract_count"] == 8
        assert state["oi_known_count"] == 8 and state["oi_missing_count"] == 0
        assert (state["call_oi_wall_count"], state["put_oi_wall_count"],
                state["call_gamma_wall_count"], state["put_gamma_wall_count"]) == (3, 3, 3, 3)
        for row in levels:
            payload = audit.anchor_payload(
                source(close_i), row["cluster_ordinal"], row["center"], row["band"],
                row["source_mask"], json.loads(row["semantic_components_json"]),
            )
            assert row["anchor_id"] == hashlib.sha256(audit.canonical_json(payload)).hexdigest()


def test_invalid_precedence_and_missing_never_loads(engines: audit.Engines) -> None:
    missing = source()
    missing.update(cache_status="MISSING", missing_reason="MISSING_SOURCE")
    state, levels = audit.reconstruct_identity(missing, engines)
    assert state["geometry_status"] == "MISSING_SOURCE" and not levels
    arrays = synthetic_cache()
    arrays["spot_valid"][:4] = False
    invalid_ib, _ = audit.reconstruct_identity(source(), engines, arrays, metadata(arrays))
    assert invalid_ib["geometry_status"] == "INVALID_IB"
    arrays = synthetic_cache()
    arrays["spot_valid"][60] = False
    invalid_state, _ = audit.reconstruct_identity(source(), engines, arrays, metadata(arrays))
    assert invalid_state["geometry_status"] == "INVALID_STATE60"
    assert invalid_state["ib_observed"] == 60 and invalid_state["band"] is None


def tables_for(arrays: dict[str, np.ndarray], engines: audit.Engines,
               item: dict[str, object] | None = None) -> tuple[pa.Table, pa.Table]:
    item = item or source()
    state, levels = audit.reconstruct_identity(item, engines, arrays, metadata(arrays, int(item["close_i"])))
    return audit.tables_from_rows([state], levels)


def test_all_post_state60_values_have_no_semantic_influence(engines: audit.Engines) -> None:
    original = synthetic_cache()
    variant = deepcopy(original)
    for name in ("bid", "ask", "delta", "iv", "vega", "theta"):
        variant[name][61:] = 999.0
    variant["spot"][61:] = np.linspace(1.0, 999.0, len(variant["spot"]) - 61)
    variant["spot_valid"][61:] = ~variant["spot_valid"][61:]
    variant["row_flags"][61:] = 7
    audit.assert_future_invariance(tables_for(original, engines), tables_for(variant, engines))


def permuted_cache(arrays: dict[str, np.ndarray], order: np.ndarray) -> dict[str, np.ndarray]:
    result = deepcopy(arrays)
    inverse = np.empty(len(order), dtype=np.int32)
    inverse[order] = np.arange(len(order), dtype=np.int32)
    for name in ("strike", "right"):
        result[name] = result[name][order]
    for name in ("bid", "ask", "delta", "iv", "vega", "theta", "row_flags"):
        result[name] = result[name][:, order]
    result["oi_contract_idx"] = inverse[result["oi_contract_idx"]]
    return result


def test_contract_column_permutation_preserves_semantics_and_ids(engines: audit.Engines) -> None:
    original = synthetic_cache()
    variant = permuted_cache(original, np.array([7, 0, 4, 2, 6, 1, 5, 3]))
    audit.assert_future_invariance(tables_for(original, engines), tables_for(variant, engines))


def test_future_only_contract_preserves_semantics_and_ids(engines: audit.Engines) -> None:
    original = synthetic_cache()
    variant = deepcopy(original)
    variant["strike"] = np.append(variant["strike"], 500.0)
    variant["right"] = np.append(variant["right"], np.int8(0))
    for name in ("bid", "ask", "delta", "iv", "vega", "theta"):
        column = np.full((len(variant["time_ns"]), 1), np.nan)
        variant[name] = np.concatenate((variant[name], column), axis=1)
    flags = np.zeros((len(variant["time_ns"]), 1), dtype=np.uint8)
    flags[61:] = 1
    variant["row_flags"] = np.concatenate((variant["row_flags"], flags), axis=1)
    variant["iv"][61:, -1] = 0.3
    variant["oi_contract_idx"] = np.append(variant["oi_contract_idx"], np.int32(8))
    variant["oi_value"] = np.append(variant["oi_value"], np.int64(9999))
    variant["oi_available_ns"] = np.append(variant["oi_available_ns"], variant["time_ns"][61])
    variant["oi_valid"] = np.append(variant["oi_valid"], True)
    audit.assert_future_invariance(tables_for(original, engines), tables_for(variant, engines))


def test_anchor_normalizes_signed_zero_and_rejects_nonfinite() -> None:
    assert audit.float_hex(-0.0) == audit.float_hex(0.0) == "0x0.0p+0"
    with pytest.raises(audit.AuditError, match="nonfinite"):
        audit.float_hex(float("nan"))
    with pytest.raises(audit.AuditError, match="nonfinite"):
        audit.float_hex(float("inf"))


def test_oi_invalidating_update_never_backfills(engines: audit.Engines) -> None:
    arrays = synthetic_cache()
    arrays["oi_contract_idx"] = np.array([0, 0], dtype=np.int32)
    arrays["oi_value"] = np.array([100, -1], dtype=np.int64)
    arrays["oi_available_ns"] = np.array([arrays["time_ns"][0], arrays["time_ns"][60]], dtype=np.int64)
    arrays["oi_valid"] = np.array([True, False])
    row = engines.session_level.available_oi_matrix(arrays, engines.clock.FULL)[60]
    assert np.isnan(row[0])


def test_cluster_diameter_uses_group_first_not_neighbor_chaining(engines: audit.Engines) -> None:
    raw = [{"center": center, "source_mask": 1, "name": "FIB", "ratio": center}
           for center in (0.0, 1.5, 3.0)]
    clusters = engines.level.deduplicate_levels(raw, 1.0)
    assert [row["n_components"] for row in clusters] == [2, 1]


def test_table_comparison_detects_content_order_null_and_extra_schema() -> None:
    missing = source()
    missing.update(cache_status="MISSING", missing_reason="MISSING_SOURCE")
    unused_engines = audit.Engines(None, None, None)
    state, levels = audit.reconstruct_identity(missing, unused_engines)
    expected, expected_levels = audit.tables_from_rows([state], levels)
    audit.assert_tables_equal(expected, expected, "states")
    audit.assert_tables_equal(expected_levels, expected_levels, "levels")
    ticker_index = expected.schema.get_field_index("ticker")
    changed = expected.set_column(ticker_index, expected.schema.field(ticker_index), pa.array(["QQQ"]))
    with pytest.raises(audit.AuditError, match="content/order/null"):
        audit.assert_tables_equal(expected, changed, "states")
    extra = expected.append_column("extra", pa.array([1], type=pa.int8()))
    with pytest.raises(audit.AuditError, match="schema"):
        audit.assert_tables_equal(expected, extra, "states")


def admission_row(ticker: str, day: date, period: str, status: str,
                  session: str = "FULL") -> dict[str, object]:
    available = status == "AVAILABLE"
    return {
        "ticker": ticker, "ticker_ordinal": audit.TICKER_ORDINAL[ticker],
        "date": day.strftime("%Y%m%d"), "session_kind": session,
        "close_i": 210 if session == "SHORT" else 390, "cache_status": status,
        "missing_reason": None if available else "MISSING_SOURCE", "authority": period,
        "feature_metadata_path": None, "feature_metadata_bytes": None,
        "feature_metadata_sha256": None,
        "cache_metadata_path": f"C:/synthetic/{ticker}-{day}.json" if available else None,
        "cache_metadata_bytes": 1 if available else None,
        "cache_metadata_sha256": "1" * 64 if available else None,
        "npz_path": f"C:/synthetic/{ticker}-{day}.npz" if available else None,
        "npz_bytes": 1 if available else None, "npz_sha256": "2" * 64 if available else None,
        "cache_version": "LEVEL_DAILY_CACHE_V1" if available else None,
        "binding_source_sha256": "2" * 64 if available else "3" * 64,
        "binding_source_metadata_sha256": "1" * 64 if available else "4" * 64,
        "stats": {},
    }


def population() -> list[dict[str, object]]:
    start = date(2023, 1, 3)
    rows = []
    for day_index in range(930):
        current = start + timedelta(days=day_index)
        period = "H1" if day_index < 875 else "Q3"
        missing = day_index < 2 or 875 <= day_index < 879
        session = "SHORT" if 2 <= day_index < 10 else "FULL"
        for ticker in ("SPY", "QQQ", "SPXW"):
            rows.append(admission_row(ticker, current, period,
                                      "MISSING" if missing else "AVAILABLE", session))
    return rows


def test_exact_2790_population_without_expectation_monkeypatch() -> None:
    rows = audit.validate_cache_admission(population())
    assert len(rows) == 2790
    assert sum(row["cache_status"] == "AVAILABLE" for row in rows) == 2772
    assert sum(row["session_kind"] == "SHORT" and row["cache_status"] == "AVAILABLE" for row in rows) == 24
    assert rows[0]["calendar_ordinal"] == 0 and rows[-1]["calendar_ordinal"] == 2789


def test_calendar_validator_reaches_fixed_digest_on_structurally_valid_synthetic() -> None:
    start = date(2023, 1, 3)
    days = [(start + timedelta(days=index)).strftime("%Y%m%d") for index in range(930)]
    rows = [{"ticker": ticker, "date": day, "close_i": 210 if index < 8 else 390}
            for ticker in ("QQQ", "SPXW", "SPY") for index, day in enumerate(days)]
    document = {"schema": "weekly_h2_boundary_unified_calendar_v1", "rows": rows}
    with pytest.raises(audit.AuditError, match="canonical digest"):
        audit.validate_calendar_document(document)
    changed = deepcopy(document)
    changed["rows"][0]["date"] = "20230230"
    with pytest.raises(audit.AuditError, match="calendar date"):
        audit.validate_calendar_document(changed)


@pytest.mark.parametrize("mutation,message", [
    (lambda rows: rows.pop(), "population"),
    (lambda rows: rows[0].update(ticker_ordinal=2), "ticker"),
    (lambda rows: rows[3].update(date=rows[0]["date"]), "duplicate"),
    (lambda rows: rows[0].update(extra=True), "schema"),
    (lambda rows: rows[30].update(close_i=210), "clock"),
    (lambda rows: rows[0].update(missing_reason=None), "missing reason"),
    (lambda rows: rows[6].update(binding_source_sha256="f" * 64), "crosspin"),
])
def test_population_mutations_fail(mutation: object, message: str) -> None:
    rows = population()
    mutation(rows)
    with pytest.raises(audit.AuditError, match=message):
        audit.validate_cache_admission(rows)


def valid_binding(tmp_path: Path) -> dict[str, object]:
    pin = {"path": str(tmp_path / "placeholder"), "bytes": 1, "sha256": "a" * 64}
    authorities = {name: {"path": str(path), "bytes": size, "sha256": sha}
                   for name, (path, size, sha) in audit.AUTHORITY_PINS.items()}
    implementations = {name: {"path": str(audit.LEVEL_ROOT / name), "bytes": size, "sha256": sha}
                       for name, (size, sha) in audit.ENGINE_PINS.items()}
    helper_size, helper_sha = audit.RESOURCE_HELPER_PIN
    implementations.update(producer=pin, producer_tests=pin,
                           resource_helper={"path": str(audit.RESOURCE_HELPER),
                                            "bytes": helper_size, "sha256": helper_sha},
                           auditor=pin, auditor_tests=pin)
    return {"schema": "c_geometry_1030_runtime_binding_v1",
            "status": "BOUND_REAL_C_GEOMETRY_1030", "producer_output_root": str(tmp_path / "producer"),
            "producer_observer_root": str(tmp_path / "producer_observer"),
            "producer_manifest": pin, "producer_journal": pin, "producer_exit": pin,
            "producer_process": pin, "b_final_bundle": pin, "b_final_review": pin,
            "calendar": pin,
            "cache_admission": pin, "authority_pins": authorities,
            "implementation_pins": implementations, "audit_output_root": str(tmp_path / "audit"),
            "audit_observer_root": str(tmp_path / "observer")}


def write_binding(tmp_path: Path, value: dict[str, object]) -> tuple[Path, str]:
    path = tmp_path / "binding.json"
    raw = audit.canonical_json(value) + b"\n"
    path.write_bytes(raw)
    return path, hashlib.sha256(raw).hexdigest()


def test_unresolved_binding_fails_before_roots_or_downstream(tmp_path: Path,
                                                            monkeypatch: pytest.MonkeyPatch) -> None:
    value = valid_binding(tmp_path)
    value["status"] = "PENDING"
    path, digest = write_binding(tmp_path, value)
    def trap(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("downstream action reached")
    monkeypatch.setattr(audit, "require_runtime_roots", trap)
    monkeypatch.setattr(audit, "verify_static_authorities", trap)
    monkeypatch.setattr(audit, "bind_engines", trap)
    with pytest.raises(audit.AuditError, match="status"):
        audit.run(path, digest, tmp_path / "audit", tmp_path / "observer")
    assert not (tmp_path / "audit").exists() and not (tmp_path / "observer").exists()


def test_wrong_runtime_roots_fail_before_helper_or_producer_open(tmp_path: Path,
                                                                monkeypatch: pytest.MonkeyPatch) -> None:
    value = valid_binding(tmp_path)
    path, digest = write_binding(tmp_path, value)
    def trap(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("downstream action reached")
    monkeypatch.setattr(audit, "verify_static_authorities", trap)
    monkeypatch.setattr(audit, "bind_resource_helper", trap)
    monkeypatch.setattr(audit, "load_compact_json", trap)
    with pytest.raises(audit.AuditError, match="exclusive audit roots"):
        audit.run(path, digest, tmp_path / "wrong", Path(value["audit_observer_root"]))


def test_binding_exact_schema_and_pins(tmp_path: Path) -> None:
    value = valid_binding(tmp_path)
    path, digest = write_binding(tmp_path, value)
    assert audit.load_runtime_binding(path, digest) == value
    value["extra"] = True
    path, digest = write_binding(tmp_path, value)
    with pytest.raises(audit.AuditError, match="schema"):
        audit.load_runtime_binding(path, digest)


def test_static_implementation_pins_require_exact_canonical_paths(tmp_path: Path) -> None:
    value = valid_binding(tmp_path)
    implementations = value["implementation_pins"]
    assert isinstance(implementations, dict)
    paths = {
        "producer": HERE / "build_weekly_zone_geometry_1030.py",
        "producer_tests": HERE / "test_build_weekly_zone_geometry_1030.py",
        "auditor": HERE / "audit_weekly_zone_geometry_1030.py",
        "auditor_tests": HERE / "test_audit_weekly_zone_geometry_1030.py",
    }
    for role, path in paths.items():
        implementations[role] = compact_file_pin(path)
    audit.verify_static_authorities(value)
    wrong_root = tmp_path / "wrong_root"
    wrong_root.mkdir()
    copied = wrong_root / paths["producer"].name
    shutil.copyfile(paths["producer"], copied)
    implementations["producer"] = compact_file_pin(copied)
    with pytest.raises(audit.AuditError, match="implementation exact path: producer"):
        audit.verify_static_authorities(value)


def test_audit_closing_population_includes_all_consumed_c_evidence_and_rejects_alias(
        tmp_path: Path) -> None:
    names = ["admitted.npz", "binding.json", "exit.json", "process.json", "journal.jsonl",
             "manifest.json", "geometry_states_1030.parquet",
             "geometry_levels_1030.parquet", "coverage.json"]
    pins: dict[str, audit.Pin] = {}
    for ordinal, name in enumerate(names):
        path = tmp_path / name
        path.write_bytes(f"evidence-{ordinal}".encode())
        pins[str(path)] = audit.Pin(**compact_file_pin(path))
    source = {str(tmp_path / "admitted.npz"): pins[str(tmp_path / "admitted.npz")]}
    evidence = {path_text: pin for path_text, pin in pins.items() if path_text not in source}
    closing = audit.merge_closing_pins(source, evidence)
    assert set(closing) == {str(tmp_path / name) for name in names}
    audit.require_distinct_physical_files(closing.values())
    conflicting = deepcopy(evidence)
    manifest_path = str(tmp_path / "manifest.json")
    conflicting[manifest_path] = audit.Pin(manifest_path, pins[manifest_path].bytes,
                                           "f" * 64)
    with pytest.raises(audit.AuditError, match="conflicting audit closing pin"):
        audit.merge_closing_pins(source, evidence, conflicting)
    alias = tmp_path / "journal_alias.jsonl"
    os.link(tmp_path / "journal.jsonl", alias)
    alias_pin = audit.Pin(**compact_file_pin(alias))
    with pytest.raises(audit.AuditError, match="exclusive regular file|physical file alias"):
        audit.require_distinct_physical_files([pins[str(tmp_path / "journal.jsonl")], alias_pin])


def test_final_b_bundle_exact_schema_crosspins_and_flags(tmp_path: Path) -> None:
    binding = valid_binding(tmp_path)
    def pin(label: str) -> dict[str, object]:
        return {"path": str(tmp_path / label), "bytes": len(label),
                "sha256": hashlib.sha256(label.encode()).hexdigest()}
    binding["cache_admission"] = pin("cache_admission")
    binding["calendar"] = pin("calendar")
    flags = {name: name in {"option_raw_values_read", "parquet_footers_read", "spot_cache_arrays_read"}
             for name in audit.FINAL_B_FLAG_KEYS}
    flags["selected_policy"] = None
    outputs = {name: pin("output_" + name) for name in audit.B_OUTPUT_NAMES}
    outputs["cache_admission.jsonl"] = deepcopy(binding["cache_admission"])
    value = {"schema": "weekly_zone_event_value_paths_final_admission_v1",
             "status": "PASS_FINAL_B_ADMISSION", "data_scope": "SEEN_DEVELOPMENT",
             "producer": {"manifest": pin("producer_manifest"), "outputs": outputs,
                          "observer": {name: pin("producer_" + name) for name in ("exit", "process", "journal")}},
             "auditor": {name: pin("auditor_" + name) for name in ("audit", "manifest", "exit", "process", "journal")},
             "authority_inputs": {**{name: pin("authority_" + name)
                                      for name in audit.B_AUTHORITY_KEYS - {"unified_calendar"}},
                                  "unified_calendar": deepcopy(binding["calendar"])},
             "calendar": {"raw_file_pin": deepcopy(binding["calendar"]),
                          "semantic_jsonl": {"bytes": audit.CANONICAL_CALENDAR_BYTES,
                                             "sha256": audit.CANONICAL_CALENDAR_SHA256,
                                             "order": "DATE_ASC_TICKER_ORDINAL_SPY_QQQ_SPXW", "rows": 2790},
                          "identity_set_preserved": True, "close_i_preserved": True},
             "flags": flags}
    audit.validate_final_b_bundle(value, binding)
    changed = deepcopy(value)
    changed["flags"]["labels_read"] = True
    with pytest.raises(audit.AuditError, match="flags values"):
        audit.validate_final_b_bundle(changed, binding)
    changed = deepcopy(value)
    changed["producer"]["outputs"]["cache_admission.jsonl"]["sha256"] = "f" * 64
    with pytest.raises(audit.AuditError, match="crosspin"):
        audit.validate_final_b_bundle(changed, binding)
    changed = deepcopy(value)
    changed["authority_inputs"]["stage_a_entry_plan"] = deepcopy(changed["authority_inputs"]["stage_a_weekly_sources"])
    with pytest.raises(audit.AuditError, match="physical role cardinality"):
        audit.validate_final_b_bundle(changed, binding)


def test_final_b_closure_reconstructs_retained_evidence(tmp_path: Path) -> None:
    def write_json_pin(name: str, value: object) -> dict[str, object]:
        path = tmp_path / name
        producer.write_json(path, value)
        return {"path": str(path), "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    authority_inputs = {name: {"path": f"C:/synthetic/{name}", "bytes": 1,
                               "sha256": hashlib.sha256(name.encode()).hexdigest()}
                        for name in audit.B_AUTHORITY_KEYS}
    outputs = {name: {"path": f"C:/synthetic/{name}", "bytes": len(name),
                      "sha256": hashlib.sha256(name.encode()).hexdigest()}
               for name in audit.B_OUTPUT_NAMES}
    expected_rows = {"cache_admission.jsonl": 2790, "decision_contracts.parquet": 3240,
                     "option_quote_observations.parquet": 3_606_310,
                     "segment_coverage.parquet": 9720, "source_admission.jsonl": 2784,
                     "spot_coverage.jsonl": 2790, "spot_paths.parquet": 1_086_570,
                     "summary.json": 1}
    manifest_output_records = {name: {**pin, "rows": expected_rows[name]}
                               for name, pin in outputs.items()}
    producer_manifest = write_json_pin("b-producer-manifest.json", {
        "schema": "weekly_zone_event_value_paths_manifest_v2_calendar_normalized",
        "status": "COMPLETE_OUTCOME_FREE_VALUE_PATHS", "outputs": manifest_output_records,
        "authority_inputs": authority_inputs,
    })
    producer_exit_value = {"exit_code": 0, "value_child_exit_code": 0, "changed_pins": [],
                           "metadata_error": None, "retry": False, "pid": 11, "creation_epoch": 22.5}
    producer_exit = write_json_pin("b-producer-exit.json", producer_exit_value)
    producer_process = write_json_pin("b-producer-process.json", {"pid": 11, "creation_epoch": 22.5})
    audit_document = write_json_pin("b-audit.json", {
        "schema": "weekly_zone_event_value_paths_audit_v2_calendar_normalized", "status": "PASS"})
    audit_manifest = write_json_pin("b-audit-manifest.json", {
        "schema": "weekly_zone_event_value_paths_audit_manifest_v2_calendar_normalized",
        "status": "PASS", "authority_inputs": authority_inputs})
    audit_exit = write_json_pin("b-audit-exit.json", {
        "exit_code": 0, "value_child_exit_code": 0, "changed_pins": [], "metadata_error": None,
        "retry": False, "pid": 33, "creation_epoch": 44.5})
    audit_process = write_json_pin("b-audit-process.json", {"pid": 33, "creation_epoch": 44.5})
    producer_journal = write_json_pin("b-producer-journal.jsonl", {
        "event": "COMPLETED", "kind": "CLOSING_REHASH"})
    audit_journal = write_json_pin("b-audit-journal.jsonl", {
        "event": "COMPLETED", "stage": "WRITE_AUDIT_OUTPUT"})
    value = {"producer": {"manifest": producer_manifest, "outputs": outputs,
                          "observer": {"exit": producer_exit, "process": producer_process,
                                       "journal": producer_journal}},
             "auditor": {"audit": audit_document, "manifest": audit_manifest,
                         "exit": audit_exit, "process": audit_process, "journal": audit_journal},
             "authority_inputs": authority_inputs}
    audit.validate_final_b_closure(value)
    bad_dialect = write_json_pin("b-audit-bad-dialect.jsonl", {
        "event": "COMPLETED", "stage": "WRITE_AUDIT_OUTPUT", "kind": "WRONG"})
    changed = deepcopy(value)
    changed["auditor"]["journal"] = bad_dialect
    with pytest.raises(audit.AuditError, match="journal closure"):
        audit.validate_final_b_closure(changed)
    bad_records = deepcopy(manifest_output_records)
    bad_records["decision_contracts.parquet"]["rows"] = None
    bad_manifest = write_json_pin("b-producer-bad-rows.json", {
        "schema": "weekly_zone_event_value_paths_manifest_v2_calendar_normalized",
        "status": "COMPLETE_OUTCOME_FREE_VALUE_PATHS", "outputs": bad_records,
        "authority_inputs": authority_inputs})
    changed = deepcopy(value)
    changed["producer"]["manifest"] = bad_manifest
    with pytest.raises(audit.AuditError, match="output record"):
        audit.validate_final_b_closure(changed)
    for ordinal, invalid_rows in enumerate((None, True, 1.0)):
        bad_records = deepcopy(manifest_output_records)
        bad_records["summary.json"]["rows"] = invalid_rows
        bad_manifest = write_json_pin(f"b-producer-bad-summary-rows-{ordinal}.json", {
            "schema": "weekly_zone_event_value_paths_manifest_v2_calendar_normalized",
            "status": "COMPLETE_OUTCOME_FREE_VALUE_PATHS", "outputs": bad_records,
            "authority_inputs": authority_inputs})
        changed = deepcopy(value)
        changed["producer"]["manifest"] = bad_manifest
        with pytest.raises(audit.AuditError, match="output record"):
            audit.validate_final_b_closure(changed)
    bad_records = deepcopy(manifest_output_records)
    bad_records["decision_contracts.parquet"]["sha256"] = "f" * 64
    bad_manifest = write_json_pin("b-producer-bad-projection.json", {
        "schema": "weekly_zone_event_value_paths_manifest_v2_calendar_normalized",
        "status": "COMPLETE_OUTCOME_FREE_VALUE_PATHS", "outputs": bad_records,
        "authority_inputs": authority_inputs})
    changed = deepcopy(value)
    changed["producer"]["manifest"] = bad_manifest
    with pytest.raises(audit.AuditError, match="producer closure"):
        audit.validate_final_b_closure(changed)
    failed_audit = write_json_pin("b-audit-failed.json", {
        "schema": "weekly_zone_event_value_paths_audit_v2_calendar_normalized", "status": "FAIL"})
    changed = deepcopy(value)
    changed["auditor"]["audit"] = failed_audit
    with pytest.raises(audit.AuditError, match="auditor closure"):
        audit.validate_final_b_closure(changed)


def test_retained_exit_and_process_identity_are_both_required() -> None:
    exit_value = {"exit_code": 0, "geometry_child_exit_code": 0, "pid": 123,
                  "creation_epoch": 456.5, "changed_pins": [], "metadata_error": None, "retry": False}
    process = {"pid": 123, "creation_epoch": 456.5}
    audit.validate_retained_closure(exit_value, process)
    changed = deepcopy(exit_value)
    changed["geometry_child_exit_code"] = 1
    with pytest.raises(audit.AuditError, match="outcome"):
        audit.validate_retained_closure(changed, process)
    changed = deepcopy(process)
    changed["creation_epoch"] = 457.0
    with pytest.raises(audit.AuditError, match="identity"):
        audit.validate_retained_closure(exit_value, changed)


def test_official_resource_gate_requires_all_three_values(monkeypatch: pytest.MonkeyPatch,
                                                          tmp_path: Path) -> None:
    observed = {"available_ram_bytes": 3_000_000_000, "free_commit_bytes": 4_000_000_000}
    calls = []
    def gate(value: dict[str, int]) -> None:
        calls.append(dict(value))
    disk = type("Disk", (), {"free": 5_000_000_000})()
    monkeypatch.setattr(audit.shutil, "disk_usage", lambda _path: disk)
    assert audit.resource_gate(lambda: observed, gate, tmp_path) == {
        **observed, "disk_free_bytes": 5_000_000_000,
    }
    assert calls == [observed]
    with pytest.raises(audit.AuditError, match="2GB"):
        audit.resource_gate(lambda: {**observed, "free_commit_bytes": 1}, gate, tmp_path)


def test_auditor_journal_snapshots_and_durable_output(monkeypatch: pytest.MonkeyPatch,
                                                      tmp_path: Path) -> None:
    disk = type("Disk", (), {"free": 5_000_000_000})()
    monkeypatch.setattr(audit.shutil, "disk_usage", lambda _path: disk)
    observed = lambda: {"available_ram_bytes": 3_000_000_000,
                        "free_commit_bytes": 3_000_000_000}
    journal = audit.AuditJournal(tmp_path / "journal.jsonl", observed, lambda _value: None, tmp_path)
    with journal.unit("AUDIT_GEOMETRY_IDENTITY", "SPY:20260105", []) as details:
        details["geometry_status"] = "MISSING_SOURCE"
    with journal.unit("VERIFY_PRODUCER_OUTPUTS", "FINAL_OUTPUTS", ["states", "coverage"]) as details:
        details.update({"before": {"states": "pin"}, "after": {"states": "pin"}})
    with journal.unit("VERIFY_PRODUCER_JOURNAL", "PRODUCER_JOURNAL", ["producer.jsonl"]) as details:
        details.update({"before": "pin", "after": "pin"})
    with journal.unit("AUDIT_CLOSING_INPUT", "binding.json", ["binding.json"]) as details:
        details.update({"before": "pin", "after": "pin"})
    journal.close()
    rows = audit.parse_jsonl(tmp_path / "journal.jsonl")
    assert [row["seq"] for row in rows] == list(range(8))
    assert [row["phase"] for row in rows] == ["START", "COMPLETE"] * 4
    assert [rows[index]["kind"] for index in range(0, len(rows), 2)] == [
        "AUDIT_GEOMETRY_IDENTITY", "VERIFY_PRODUCER_OUTPUTS",
        "VERIFY_PRODUCER_JOURNAL", "AUDIT_CLOSING_INPUT",
    ]
    assert all(min(row["gate"].values()) >= 2_000_000_000 for row in rows)
    output_pin = audit.write_durable_json(tmp_path / "audit.json", {"status": "SYNTHETIC"})
    before = audit.file_snapshot(tmp_path / "audit.json", output_pin)
    assert before["pin"] == output_pin.__dict__ and len(before["stat_identity"]) == 4


def test_metadata_array_whitelist_and_oi_rules() -> None:
    arrays = synthetic_cache()
    value = metadata(arrays)
    audit.validate_metadata(value, source())
    value = deepcopy(value)
    value["array_schema"]["labels"] = {"shape": [1], "dtype": "float64"}
    with pytest.raises(audit.AuditError, match="whitelist"):
        audit.validate_metadata(value, source())
    value = metadata(arrays)
    value["array_schema"]["underlying_age_ms"] = {"shape": [391, 8], "dtype": "float64"}
    audit.validate_metadata(value, source())
    value["oi_assumed_availability"] = "2026-01-05 09:30:00"
    with pytest.raises(audit.AuditError, match="native OI"):
        audit.validate_metadata(value, source())
    value = metadata(arrays)
    value["timezone_convention"] = "UTC"
    with pytest.raises(audit.AuditError, match="timezone"):
        audit.validate_metadata(value, source())
    short_arrays = synthetic_cache(210)
    value = metadata(short_arrays, 210)
    value["session_clock"] = {"close_i": 390, "n_slots": 391}
    with pytest.raises(audit.AuditError, match="short metadata clock"):
        audit.validate_metadata(value, source(210))
    value = metadata(arrays)
    value["array_schema"]["spot"]["extra"] = True
    with pytest.raises(audit.AuditError, match="descriptor"):
        audit.validate_metadata(value, source())


def state_rows_for_coverage() -> list[dict[str, object]]:
    rows = []
    for item in audit.validate_cache_admission(population()):
        status = "MISSING_SOURCE" if item["cache_status"] == "MISSING" else "AVAILABLE_GEOMETRY"
        rows.append({"source_status": item["cache_status"], "geometry_status": status,
                     "authority_period": item["authority"], "session_kind": item["session_kind"]})
    return rows


def test_coverage_exact_keyset_and_equations() -> None:
    coverage = audit.coverage_from_states(state_rows_for_coverage(), 12345)
    assert len(coverage) == 21 and coverage["available_sources"] == 2772
    assert coverage["h1_full_available"] == 2595 and coverage["h1_short_available"] == 24
    assert coverage["q3_available"] == 153 and coverage["h1_missing"] == 6
    assert coverage["q3_missing"] == 12 and coverage["level_rows"] == 12345
    audit.validate_coverage(deepcopy(coverage), coverage)
    changed = deepcopy(coverage)
    changed["level_rows"] += 1
    with pytest.raises(audit.AuditError, match="coverage exact"):
        audit.validate_coverage(changed, coverage)


def manifest_fixture(tmp_path: Path, binding: dict[str, object], coverage: dict[str, object]) -> dict[str, object]:
    outputs = {}
    for name, rows in (("geometry_states_1030.parquet", 2790),
                       ("geometry_levels_1030.parquet", coverage["level_rows"]),
                       ("coverage.json", None)):
        path = tmp_path / name
        path.write_bytes(name.encode())
        outputs[name] = {"path": str(path), "bytes": path.stat().st_size,
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "rows": rows}
    contracts = {path.name: binding["authority_pins"][name]
                 for name, (path, _size, _sha) in audit.AUTHORITY_PINS.items()}
    count_keys = ("calendar_rows", "available_sources", "missing_sources", "geometry_available",
                  "invalid_ib", "invalid_state60", "state_rows", "level_rows")
    return {"status": "C_GEOMETRY_1030_CLOSED", "contract": contracts,
            "implementation": binding["implementation_pins"]["producer"],
            "authorities": {"b_bundle": binding["b_final_bundle"], "b_review": binding["b_final_review"]},
            "authority_pins": {"calendar": binding["calendar"],
                               "cache_admission": binding["cache_admission"],
                               "engines": {name: binding["implementation_pins"][name] for name in audit.ENGINE_PINS}},
            "input_count": 3, "inputs_digest": "d" * 64, "outputs": outputs,
            "counts": {key: coverage[key] for key in count_keys},
            "journal_closure": {"prepublish_last_seq": 10, "prepublish_prefix_sha256": "e" * 64},
            "resource_policy": {"minimum_bytes": 2_000_000_000, "cpu_affinity": [0], "threads": 1},
            "created_at_utc": "2026-11-02T00:00:00+00:00", "no_events": True,
            "no_labels": True, "no_weekly_selection": True, "no_economics": True}


def test_manifest_exact_authorities_counts_outputs_and_scope(tmp_path: Path,
                                                             monkeypatch: pytest.MonkeyPatch) -> None:
    binding = valid_binding(tmp_path)
    coverage = audit.coverage_from_states(state_rows_for_coverage(), 123)
    value = manifest_fixture(tmp_path, binding, coverage)
    inputs = {f"C:/synthetic/{index}": audit.Pin(f"C:/synthetic/{index}", 1, "1" * 64)
              for index in range(3)}
    monkeypatch.setattr(audit, "physical_inputs_digest", lambda _pins: "d" * 64)
    manifest_path = tmp_path / "closed-manifest-envelope.json"
    coverage_path = tmp_path / "closed-coverage-envelope.json"
    producer.write_json(manifest_path, value)
    producer.write_json(coverage_path, coverage)
    loaded_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    loaded_coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    audit.validate_coverage(loaded_coverage, coverage)
    audit.validate_manifest(loaded_manifest, coverage, tmp_path, binding, inputs)
    mutations = (
        ("producer manifest contracts", lambda item: item["contract"].pop(next(iter(item["contract"])))),
        ("producer manifest authority pins", lambda item: item["authority_pins"]["engines"].pop("level_engine.py")),
        ("producer manifest counts", lambda item: item["counts"].update(level_rows=124)),
        ("producer manifest resource policy", lambda item: item["resource_policy"].update(threads=2)),
        ("producer manifest scope", lambda item: item.update(no_events=False)),
    )
    for message, mutation in mutations:
        changed = deepcopy(value)
        mutation(changed)
        with pytest.raises(audit.AuditError, match=message):
            audit.validate_manifest(changed, coverage, tmp_path, binding, inputs)


def test_authority_units(inputs: dict[str, audit.Pin]) -> dict[str, audit.Pin]:
    authorities = {"binding_bundle", "binding_review", "calendar", "cache_admission",
                   "implementation", "resource_helper"}
    authorities.update(f"contract:{name}" for name in (
        audit.CONTRACT.name, audit.DRAFT.name, audit.AMENDMENT.name,
        audit.AMENDMENT_REVIEW.name, audit.BINDING_NOTE.name, audit.WINDOWS_NOTE.name,
    ))
    authorities.update(f"engine:{name}" for name in audit.ENGINE_PINS)
    admitted = next(iter(inputs.values()))
    return {identity: admitted for identity in authorities}


def closing_journal(identities: list[dict[str, object]], inputs: dict[str, audit.Pin],
                    outputs: dict[str, audit.Pin], producer_root: Path) -> list[dict[str, object]]:
    rows, seq = [], 0
    gate = {"available_ram_bytes": 3_000_000_000, "free_commit_bytes": 3_000_000_000,
            "disk_free_bytes": 3_000_000_000}
    def pair(kind: str, identity: str, details: dict[str, object] | None = None,
             unit_paths: list[str] | None = None) -> None:
        nonlocal seq
        for phase in ("START", "COMPLETE"):
            paths = (unit_paths if unit_paths is not None else
                     ([details["before"]["path"]]
                      if kind in {"CLOSING_INPUT", "CLOSING_OUTPUT"} and details else []))
            rows.append({"seq": seq, "utc": "2026-11-02T00:00:00+00:00", "kind": kind,
                         "identity": identity, "phase": phase, "paths": paths,
                         "gate": dict(gate),
                         "details": deepcopy(details) if phase == "COMPLETE" and details else {}})
            seq += 1
    authority_units = test_authority_units(inputs)
    admitted = next(iter(inputs.values()))
    admitted_info = Path(admitted.path).stat()
    authority_details = {"before": admitted.__dict__, "after": admitted.__dict__,
                         "physical_identity": [int(admitted_info.st_dev), int(admitted_info.st_ino)]}
    for identity in sorted(authority_units):
        pair("ADMIT_AUTHORITY", identity, authority_details, [admitted.path])
    for item in identities:
        if item["cache_status"] == "MISSING":
            details = {"geometry_status": "MISSING_SOURCE", "level_rows": 0,
                       "opened_array_names": [], "physical_array_names": [], "inputs": {}}
            unit_paths: list[str] = []
        else:
            metadata_pin = audit.Pin(item["cache_metadata_path"], item["cache_metadata_bytes"],
                                     item["cache_metadata_sha256"])
            npz_pin = audit.Pin(item["npz_path"], item["npz_bytes"], item["npz_sha256"])
            details = {"geometry_status": item.get("audited_geometry_status", "AVAILABLE_GEOMETRY"),
                       "level_rows": item.get("audited_level_rows", 1),
                       "opened_array_names": list(audit.ARRAYS),
                       "physical_array_names": list(audit.ARRAYS),
                       "inputs": {"metadata": {"before": metadata_pin.__dict__, "after": metadata_pin.__dict__},
                                  "npz": {"before": npz_pin.__dict__, "after": npz_pin.__dict__}}}
            unit_paths = [metadata_pin.path, npz_pin.path]
        pair("GEOMETRY_IDENTITY", f'{item["ticker"]}:{item["date"]}', details, unit_paths)
    for name in ("geometry_states_1030.parquet", "geometry_levels_1030.parquet", "coverage.json", "manifest.json"):
        final = outputs[name]
        staging_path = producer_root.parent / ".synthetic-staging" / name
        pin_path = str(staging_path) if name == "manifest.json" else final.path
        output_rows = (len(identities) if name == "geometry_states_1030.parquet" else
                       sum(int(item.get("audited_level_rows", 0)) for item in identities)
                       if name == "geometry_levels_1030.parquet" else None)
        pair("WRITE_OUTPUT", name,
             {"pin": {"path": pin_path, "bytes": final.bytes, "sha256": final.sha256, "rows": output_rows}},
             [str(staging_path)])
    for name, pin in inputs.items():
        info = Path(pin.path).stat()
        pair("CLOSING_INPUT", name, {"before": pin.__dict__, "after": pin.__dict__,
                                     "physical_identity": [int(info.st_dev), int(info.st_ino)]})
    for name, pin in outputs.items():
        staging = audit.Pin(str(Path(pin.path).parent.parent / ".synthetic-staging" / name),
                            pin.bytes, pin.sha256)
        pair("CLOSING_OUTPUT", name, {"before": staging.__dict__, "after": staging.__dict__})
    staging_root = producer_root.parent / ".synthetic-staging"
    staging_identity = [1, 2]
    rows.append({"seq": seq, "utc": "2026-11-02T00:00:00+00:00", "kind": "PUBLISH_ROOT",
                 "identity": producer_root.name, "phase": "START",
                 "paths": [str(staging_root), str(producer_root)], "gate": dict(gate),
                 "details": {"staging_identity": staging_identity}})
    seq += 1
    rows.append({"seq": seq, "utc": "2026-11-02T00:00:00+00:00", "kind": "PUBLISH_ROOT",
                 "identity": producer_root.name, "phase": "COMPLETE", "paths": [str(producer_root)],
                 "gate": dict(gate), "details": {"status": "C_GEOMETRY_1030_CLOSED",
                                                  "staging_identity": staging_identity}})
    return rows


def test_journal_exact_lifecycles_identities_and_closing_pins(tmp_path: Path) -> None:
    identities = population()[:3]
    input_path = tmp_path / "input"
    input_path.write_bytes(b"x")
    input_pin = audit.Pin(str(input_path), 1, hashlib.sha256(b"x").hexdigest())
    inputs = {str(input_path): input_pin}
    producer_root = tmp_path / "final"
    outputs = {name: audit.Pin(str(producer_root / name), 2, "2" * 64) for name in
               ("geometry_states_1030.parquet", "geometry_levels_1030.parquet", "coverage.json", "manifest.json")}
    rows = closing_journal(identities, inputs, outputs, producer_root)
    journal_path = tmp_path / "real-producer-journal.jsonl"
    writer = producer.Journal(journal_path, lambda: {}, tmp_path)
    for row in rows:
        writer.append(row["kind"], row["identity"], row["phase"], row["paths"], row["gate"], row["details"])
    writer.close()
    rows = audit.parse_jsonl(journal_path)
    authority_units = test_authority_units(inputs)
    audit.validate_producer_journal(rows, identities, inputs, outputs, producer_root, authority_units)
    changed = deepcopy(rows)
    completed = next(row for row in changed if row["kind"] == "CLOSING_INPUT" and row["phase"] == "COMPLETE")
    completed["details"]["after"]["sha256"] = "f" * 64
    with pytest.raises(audit.AuditError, match="closing pin"):
        audit.validate_producer_journal(changed, identities, inputs, outputs, producer_root, authority_units)
    changed = deepcopy(rows)
    changed.pop(next(index for index, row in enumerate(changed)
                     if row["kind"] == "GEOMETRY_IDENTITY" and row["phase"] == "COMPLETE"))
    for index, row in enumerate(changed):
        row["seq"] = index
    with pytest.raises(audit.AuditError, match="lifecycle"):
        audit.validate_producer_journal(changed, identities, inputs, outputs, producer_root, authority_units)
    changed = deepcopy(rows)
    first_closing = next(index for index, row in enumerate(changed) if row["kind"] == "CLOSING_INPUT")
    pair = changed[first_closing:first_closing + 2]
    del changed[first_closing:first_closing + 2]
    changed[0:0] = pair
    for index, row in enumerate(changed):
        row["seq"] = index
    with pytest.raises(audit.AuditError, match="block order"):
        audit.validate_producer_journal(changed, identities, inputs, outputs, producer_root, authority_units)


def test_journal_available_identity_proves_exact_opened_arrays(tmp_path: Path) -> None:
    identity = population()[6]
    identity["audited_geometry_status"] = "AVAILABLE_GEOMETRY"
    identity["audited_level_rows"] = 1
    metadata_path, npz_path = tmp_path / "cache.json", tmp_path / "cache.npz"
    metadata_path.write_bytes(b"m")
    npz_path.write_bytes(b"n")
    metadata_pin = audit.Pin(str(metadata_path), 1, hashlib.sha256(b"m").hexdigest())
    npz_pin = audit.Pin(str(npz_path), 1, hashlib.sha256(b"n").hexdigest())
    identity.update(cache_metadata_path=metadata_pin.path, cache_metadata_bytes=metadata_pin.bytes,
                    cache_metadata_sha256=metadata_pin.sha256, npz_path=npz_pin.path,
                    npz_bytes=npz_pin.bytes, npz_sha256=npz_pin.sha256)
    inputs = {metadata_pin.path: metadata_pin, npz_pin.path: npz_pin}
    producer_root = tmp_path / "final"
    outputs = {name: audit.Pin(str(producer_root / name), 2, "2" * 64) for name in
               ("geometry_states_1030.parquet", "geometry_levels_1030.parquet", "coverage.json", "manifest.json")}
    rows = closing_journal([identity], inputs, outputs, producer_root)
    authority_units = test_authority_units(inputs)
    audit.validate_producer_journal(rows, [identity], inputs, outputs, producer_root, authority_units)
    changed = deepcopy(rows)
    completed = next(row for row in changed if row["kind"] == "GEOMETRY_IDENTITY" and row["phase"] == "COMPLETE")
    completed["details"]["opened_array_names"].append("underlying_age_ms")
    with pytest.raises(audit.AuditError, match="opened array whitelist"):
        audit.validate_producer_journal(changed, [identity], inputs, outputs, producer_root, authority_units)


def test_ast_forbids_producer_build_day_and_forbidden_dataset_vocabulary() -> None:
    path = HERE / "audit_weekly_zone_geometry_1030.py"
    source_text = path.read_text(encoding="utf-8")
    tree = ast.parse(source_text)
    imports = {alias.name for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
               for alias in node.names}
    assert not any("value_paths_builder" in name or "build_weekly_zone_geometry" in name for name in imports)
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert not any(isinstance(node.func, ast.Attribute) and node.func.attr == "build_day" for node in calls)
    assert 'stored[OPTIONAL_DECLARED_ARRAY]' not in source_text
    for forbidden in ("candidates.jsonl", "outcomes.jsonl", "advantages.parquet",
                      "oracle_value.npy", "weekly_contract.parquet"):
        assert forbidden not in source_text


def test_run_wires_critical_evidence_into_fresh_gates_and_final_closing() -> None:
    source_text = (HERE / "audit_weekly_zone_geometry_1030.py").read_text(encoding="utf-8")
    tree = ast.parse(source_text)
    run_node = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == "run")
    run_text = ast.get_source_segment(source_text, run_node)
    assert run_text is not None
    for binding_role in ("producer_exit", "producer_process", "producer_journal",
                         "producer_manifest"):
        assert f'"{binding_role}"' in run_text
    for unit_kind in ("VERIFY_PRODUCER_OUTPUTS", "VERIFY_PRODUCER_JOURNAL",
                      "AUDIT_CLOSING_INPUT"):
        assert f'"{unit_kind}"' in run_text
    merge_calls = [node for node in ast.walk(run_node) if isinstance(node, ast.Call)
                   and isinstance(node.func, ast.Name) and node.func.id == "merge_closing_pins"]
    assert len(merge_calls) == 1
    assert [argument.id for argument in merge_calls[0].args if isinstance(argument, ast.Name)] == [
        "input_pins", "evidence_pins",
    ]
    assert "audit_initial_snapshots = {**initial_snapshots, **evidence_snapshots}" in run_text


def test_parser_has_no_real_root_defaults() -> None:
    actions = {action.dest: action for action in audit.parser()._actions}
    for name in ("binding_json", "binding_sha256", "output_dir", "observer_dir"):
        assert actions[name].required and actions[name].default is None


def test_synthetic_producer_to_independent_auditor_core_boundary(
    tmp_path: Path, engines: audit.Engines,
) -> None:
    arrays = synthetic_cache()
    source_row = source()
    source_row["date"] = "20260105"
    source_row["cache_version"] = "LEVEL_DAILY_CACHE_V1"
    cache_metadata = metadata(arrays)
    cache_metadata["date"] = "20260105"
    calendar_row = {"calendar_ordinal": 0, "ticker": "SPY", "date": "20260105",
                    "close_i": 390, "session_kind": "FULL"}
    producer_state, producer_levels = producer.compute_identity_geometry(
        calendar_row, source_row, cache_metadata, arrays, engines.session_level, engines.clock,
    )
    auditor_source = {**source_row, "trade_date": date(2026, 1, 5), "calendar_ordinal": 0}
    auditor_state, auditor_levels = audit.reconstruct_identity(
        auditor_source, engines, arrays, cache_metadata,
    )
    expected_states, expected_levels = audit.tables_from_rows([auditor_state], auditor_levels)
    producer_states = producer.table_from_rows([producer_state], producer.states_schema())
    producer_level_table = producer.table_from_rows(producer_levels, producer.levels_schema())
    audit.assert_tables_equal(expected_states, producer_states, "integrated states")
    audit.assert_tables_equal(expected_levels, producer_level_table, "integrated levels")
    state_path = tmp_path / "geometry_states_1030.parquet"
    level_path = tmp_path / "geometry_levels_1030.parquet"
    producer.write_parquet(state_path, producer_states, [(0, len(producer_states))])
    producer.write_parquet(level_path, producer_level_table, producer.level_row_groups(producer_levels))
    coverage_path, manifest_path = tmp_path / "coverage.json", tmp_path / "manifest.json"
    producer.write_json(coverage_path, {"synthetic_only": True, "state_rows": 1,
                                        "level_rows": len(producer_levels)})
    producer.write_json(manifest_path, {"synthetic_only": True,
                                        "outputs": list(producer.OUTPUT_NAMES[:3])})
    assert {path.name for path in tmp_path.iterdir()} == set(producer.OUTPUT_NAMES)
    audit.assert_tables_equal(expected_states, audit.pq.read_table(state_path), "integrated states disk")
    audit.assert_tables_equal(expected_levels, audit.pq.read_table(level_path), "integrated levels disk")
    missing_admission = {**source_row, "cache_status": "MISSING", "missing_reason": "MISSING_SOURCE",
                         "cache_metadata_path": None, "cache_metadata_sha256": None,
                         "npz_path": None, "npz_sha256": None}
    missing_state = producer._base_state(calendar_row, missing_admission)
    assert missing_state["geometry_status"] == "MISSING_SOURCE"
    assert missing_state["missing_reason"] == "SOURCE_PLAN_MISSING"
    journal_path = tmp_path / "producer-real-envelope.jsonl"
    writer = producer.Journal(journal_path, lambda: {}, tmp_path)
    synthetic_gate = {"available_ram_bytes": 3_000_000_000,
                      "free_commit_bytes": 3_000_000_000, "disk_free_bytes": 3_000_000_000}
    writer.append("PUBLISH_ROOT", tmp_path.name, "START", [str(tmp_path / ".staging"), str(tmp_path)],
                  synthetic_gate, {"staging_identity": [1, 2]})
    writer.append("PUBLISH_ROOT", tmp_path.name, "COMPLETE", [str(tmp_path)], synthetic_gate,
                  {"status": "C_GEOMETRY_1030_CLOSED", "staging_identity": [1, 2]})
    writer.close()
    envelope = audit.parse_jsonl(journal_path)
    assert [row["seq"] for row in envelope] == [0, 1]
    assert [row["identity"] for row in envelope] == [tmp_path.name, tmp_path.name]
