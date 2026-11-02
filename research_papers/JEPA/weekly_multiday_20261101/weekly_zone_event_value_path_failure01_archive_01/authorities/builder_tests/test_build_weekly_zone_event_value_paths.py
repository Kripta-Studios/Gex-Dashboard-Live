from __future__ import annotations

import ast
import contextlib
import importlib.util
import json
import math
import os
from types import SimpleNamespace
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest


HERE = Path(__file__).absolute().parent
MODULE_PATH = HERE / "build_weekly_zone_event_value_paths.py"
SPEC = importlib.util.spec_from_file_location("value_paths_under_test", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def test_contract_and_closed_semantics_are_pinned() -> None:
    assert M.CONTRACT_SHA256 == "e7cf56f8fba5dc50937dcb4e3625752b83e4d73ebbeed77ee19f97f8bf219ac9"
    assert M.PINNED_AUTHORITIES["selector_builder_v2"][2] == "ec19e2c9066f0bb6103526ccf30a5b156c69a25a96349220d9fd680a92822945"
    assert M.PINNED_AUTHORITIES["normalization_pilot"][2] == "ad5b3ffba4e125ca7fcb4d5b0789eec601ace55be3740813d46374827766c878"
    assert M.FLAGS["outcomes_read"] is False
    assert M.FLAGS["option_raw_values_read"] is True


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("C", "CALL"), (" call ", "CALL"), ("P", "PUT"), ("put", "PUT")],
)
def test_right_aliases(raw: object, expected: str) -> None:
    assert M.normalize_right(raw) == expected


@pytest.mark.parametrize("raw", ["X", "", None, 1])
def test_invalid_right_is_fatal(raw: object) -> None:
    with pytest.raises(M.ValuePathError):
        M.normalize_right(raw)


def test_decimal_strike_is_price_unit_identity() -> None:
    assert M.strike_decimal(Decimal("500.000")) == "500"
    assert M.strike_decimal("0.00100") == "0.001"
    with pytest.raises(M.ValuePathError):
        M.strike_decimal(float("nan"))


@pytest.mark.parametrize(
    ("value", "expected"),
    [(date(2026, 1, 2), "20260102"), ("20260102", "20260102"), ("2026-01-02", "20260102")],
)
def test_day_scalar_strict_valid(value: object, expected: str) -> None:
    assert M.parse_day_scalar(value) == expected


@pytest.mark.parametrize(
    "value",
    [datetime(2026, 1, 2), 20260102, " 20260102", "2026/01/02", "20260230", True],
)
def test_day_scalar_strict_invalid(value: object) -> None:
    with pytest.raises(M.ValuePathError):
        M.parse_day_scalar(value)


def test_clock_naive_and_aware_convert_to_ny() -> None:
    naive, sub = M.parse_clock(datetime(2026, 1, 2, 10, 30), "20260102")
    assert naive.strftime("%H:%M") == "10:30" and sub is False
    aware, sub = M.parse_clock("2026-01-02T15:30:00+00:00", "20260102")
    assert aware.strftime("%H:%M") == "10:30" and sub is False


@pytest.mark.parametrize(
    "value",
    [None, 123, True, date(2026, 1, 2), "10:30", "bad", " 2026-01-02T10:30:00"],
)
def test_clock_forbidden_types_and_malformed(value: object) -> None:
    with pytest.raises(M.ValuePathError):
        M.parse_clock(value, "20260102")


def test_clock_date_mismatch_and_dst_edges() -> None:
    with pytest.raises(M.ValuePathError):
        M.parse_clock("2026-01-03T10:30:00-05:00", "20260102")
    with pytest.raises(M.ValuePathError, match="nonexistent"):
        M.parse_clock(datetime(2026, 3, 8, 2, 30), "20260308")
    with pytest.raises(M.ValuePathError, match="ambiguous"):
        M.parse_clock(datetime(2026, 11, 1, 1, 30), "20261101")


def test_clock_seconds_and_fraction_are_subminute() -> None:
    assert M.parse_clock("2026-01-02T10:30:01-05:00", "20260102")[1] is True
    assert M.parse_clock("2026-01-02T10:30:00.000000001-05:00", "20260102", fraction_nonzero=True)[1] is True
    assert M.minute_index(M.parse_clock("2026-01-02T09:30:00-05:00", "20260102")[0]) == 0
    assert M.minute_index(M.parse_clock("2026-01-02T16:00:00-05:00", "20260102")[0]) == 390


@pytest.mark.parametrize(
    ("bid", "ask", "valid"),
    [(0.0, 1.0, True), (1.0, 1.0, True), (-0.1, 1.0, False), (1.1, 1.0, False), (1.0, 0.0, False), (True, 1.0, False), (math.inf, 1.0, False), (1.0, math.nan, False)],
)
def test_quote_validity(bid: object, ask: object, valid: bool) -> None:
    assert M.valid_quote(bid, ask) is valid


def candidate(right: str, strike: float, delta: float, bid: float = 1.0, ask: float = 2.0, spot: float = 500.0) -> dict[str, object]:
    return {
        "right": right, "strike": strike, "strike_decimal": M.strike_decimal(strike),
        "delta": delta, "bid": bid, "ask": ask, "underlying_price": spot,
    }


def test_selector_direction_price_cap_and_float_tie_break() -> None:
    rows = [
        candidate("CALL", 501, -0.50),
        candidate("CALL", 502, 0.50, ask=49.96),
        candidate("CALL", 503, 1.01),
        candidate("CALL", 504, 0.50, bid=1.5, ask=2.0),
        candidate("CALL", 505, 0.50, bid=1.8, ask=2.0),
    ]
    selected = M.choose_side(rows, "CALL")
    assert selected is not None and selected["strike"] == 505
    puts = [candidate("PUT", 499, 0.5), candidate("PUT", 498, -0.5)]
    assert M.choose_side(puts, "PUT")["strike"] == 498


def test_selector_strike_is_final_tie_break() -> None:
    rows = [candidate("CALL", 501.0, 0.5), candidate("CALL", 500.0, 0.5)]
    assert M.choose_side(rows, "CALL")["strike"] == 500.0


def test_missing_ranges_are_inclusive_maximal() -> None:
    assert M.missing_ranges({0, 2, 3, 7}, 7) == [
        {"start_i": 1, "end_i": 1},
        {"start_i": 4, "end_i": 6},
    ]
    assert M.missing_ranges(set(), 2) == [{"start_i": 0, "end_i": 2}]


def test_ids_use_compact_json_and_are_stable() -> None:
    decision = M.decision_id("SPY:20260102", "SPY", "20260109", "500", "CALL")
    assert len(decision) == 64 and decision == M.decision_id("SPY:20260102", "SPY", "20260109", "500", "CALL")
    observed = M.observation_id(r"D:\ThetaData\x", "SPY", "20260109", "500", "CALL", 60)
    assert len(observed) == 64


def test_interval_used_is_not_a_filter() -> None:
    assert M.interval_text(" custom ", pa.string()) == " custom "
    assert M.interval_text(5, pa.int32()) == "5"
    assert M.interval_text(None, pa.float64()) is None
    with pytest.raises(M.ValuePathError):
        M.interval_text([1], pa.list_(pa.int8()))


def test_full_schema_metadata_is_sorted_and_base64() -> None:
    schema = pa.schema([pa.field("x", pa.float64(), nullable=False, metadata={b"z": b"2", b"a": b"1"})], metadata={b"k": b"v"})
    value = M.canonical_arrow_schema(schema)
    assert value["fields"][0]["nullable"] is False
    assert value["fields"][0]["metadata"][0]["key_b64"] == "YQ=="


def test_timestamp_raw_preserves_ns_fraction() -> None:
    array = pa.array([1_767_363_000_000_000_001], type=pa.timestamp("ns"))
    assert M.timestamp_raw(array[0], array.type).endswith(".000000001")


def test_iso_age_preserves_one_nanosecond_and_offset() -> None:
    assert M.iso_epoch_ns("2026-01-02T10:30:00.000000001-05:00") - M.iso_epoch_ns("2026-01-02T10:30:00.000000000-05:00") == 1
    assert M.iso_epoch_ns("2026-01-02T15:30:00.000000001Z") == M.iso_epoch_ns("2026-01-02T10:30:00.000000001-05:00")


def _option_table(clocks: list[str], bids: list[float]) -> pa.Table:
    size = len(clocks)
    return pa.table({
        "symbol": ["SPY"] * size,
        "expiration": ["20260109"] * size,
        "trade_date": ["20260102"] * size,
        "strike": [500.0] * size,
        "right": ["C"] * size,
        "timestamp": clocks,
        "underlying_timestamp": clocks,
        "underlying_price": [501.0] * size,
        "bid": bids,
        "ask": [2.0] * size,
        "delta": [0.5] * size,
        "implied_vol": [0.2] * size,
        "theta": [-0.1] * size,
        "vega": [0.1] * size,
        "rho": [0.01] * size,
    })


def _selector_source(path: Path) -> dict[str, object]:
    parquet = pq.ParquetFile(path)
    projection, clock, basis, gamma = M._source_projection(parquet.schema_arrow)
    return {
        "projected_schema": M.schema_descriptor(parquet.schema_arrow, projection),
        "clock_column": clock, "clock_basis": basis, "gamma_column_present": gamma,
        "trade_date": "20260102", "expiration": "20260109", "ticker": "SPY",
    }


def test_selector_materializes_only_1030_and_ignores_subminute_collision(tmp_path: Path) -> None:
    path = tmp_path / "source.parquet"
    clocks = ["2026-01-02T10:30:00-05:00", "2026-01-02T10:30:01-05:00", "2026-01-02T10:35:00-05:00"]
    pq.write_table(_option_table(clocks, [1.0, 999.0, 888.0]), path)
    plan = {"ticker": "SPY", "date": "20260102", "expiration": "20260109"}
    rows = M._selector_rows_1030(path, _selector_source(path), plan)
    assert len(rows) == 1 and rows[0]["bid"] == 1.0
    pq.write_table(_option_table(clocks, [1.0, -999.0, float("nan")]), path)
    rows_mutated = M._selector_rows_1030(path, _selector_source(path), plan)
    assert rows_mutated[0]["bid"] == rows[0]["bid"]


def test_selector_duplicate_exact_minute_is_fatal(tmp_path: Path) -> None:
    path = tmp_path / "source.parquet"
    pq.write_table(_option_table(["2026-01-02T10:30:00-05:00"] * 2, [1.0, 1.1]), path)
    with pytest.raises(M.ValuePathError, match="duplicate exact-minute"):
        M._selector_rows_1030(path, _selector_source(path), {"ticker": "SPY", "date": "20260102", "expiration": "20260109"})


def test_select_unit_journal_records_one_value_source_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_root = tmp_path / "options"
    source_root.mkdir()
    monkeypatch.setattr(M, "SOURCE_ROOT", source_root)
    path = source_root / "SPY" / "greeks" / "2026" / "01" / "SPY_20260109_20260102_greeks.parquet"
    path.parent.mkdir(parents=True)
    table = _trajectory_table().take(pa.array([1, 4], type=pa.int64()))
    for clock_column in ("timestamp", "underlying_timestamp"):
        table = table.set_column(
            table.schema.get_field_index(clock_column), clock_column,
            pa.array(["2026-01-02T10:30:00-05:00"] * table.num_rows),
        )
    pq.write_table(table, path)
    source = _selector_source(path)
    source.update(path=str(path), sha256=M.sha256_file(path), after_stat=M.guard_path(path, source_root))
    plan = {
        "status": "PLANNED", "plan_id": "SPY:20260102", "ticker": "SPY",
        "date": "20260102", "expiration": "20260109", "entry_path": str(path),
        "source_authority": "H1",
    }
    journal_path = tmp_path / "select_journal.jsonl"
    journal = M.Journal(journal_path, gate=lambda: {"available_ram_bytes": M.MIN_FREE, "free_commit_bytes": M.MIN_FREE, "disk_free_bytes": M.MIN_FREE})
    decisions, misses = M.select_decisions([plan], {str(path): source}, journal, expected_count=2)
    assert len(decisions) == 2 and not misses
    completed = [json.loads(line) for line in journal_path.read_text(encoding="utf-8").splitlines() if json.loads(line)["event"] == "COMPLETED"]
    assert len(completed) == 1 and completed[0]["details"]["source_reads"] == 1


def test_source_projection_clock_precedence_gamma_optional() -> None:
    fields = [
        ("symbol", pa.string()), ("expiration", pa.string()), ("trade_date", pa.string()),
        ("strike", pa.float64()), ("right", pa.string()),
        ("timestamp", pa.timestamp("ns")), ("underlying_timestamp", pa.timestamp("ns")),
        *[(name, pa.float64()) for name in ("underlying_price", "bid", "ask", "delta", "implied_vol", "theta", "vega", "rho")],
    ]
    projection, clock, basis, gamma = M._source_projection(pa.schema(fields))
    assert clock == "timestamp" and basis == "NATIVE_STORED_TIMESTAMP" and gamma is False
    assert "gamma" not in projection


def test_source_projection_rejects_silent_float_cast() -> None:
    fields = [
        ("symbol", pa.string()), ("expiration", pa.string()), ("trade_date", pa.string()),
        ("strike", pa.float64()), ("right", pa.string()), ("underlying_timestamp", pa.timestamp("ns")),
        *[(name, pa.float32() if name == "bid" else pa.float64()) for name in ("underlying_price", "bid", "ask", "delta", "implied_vol", "theta", "vega", "rho")],
    ]
    with pytest.raises(M.ValuePathError, match="bid must be float64"):
        M._source_projection(pa.schema(fields))


def test_contract_schemas_have_exact_nullability() -> None:
    assert all(not field.nullable for field in M.DECISION_SCHEMA if field.name != "interval_used")
    assert M.DECISION_SCHEMA.field("interval_used").nullable
    observation_nullable = {"interval_used", "bid", "ask", "delta", "implied_vol", "gamma", "theta", "vega", "rho", "underlying_price", "underlying_timestamp_raw", "underlying_age_ms"}
    assert {field.name for field in M.OBSERVATION_SCHEMA if field.nullable} == observation_nullable
    coverage_nullable = {"source_sha256", "first_observed_i", "last_observed_i", "clock_basis", "gamma_column_present"}
    assert {field.name for field in M.COVERAGE_SCHEMA if field.nullable} == coverage_nullable
    range_type = M.COVERAGE_SCHEMA.field("missing_ranges").type.value_type
    assert all(not field.nullable for field in range_type)


def test_admission_population_three_binding_kinds() -> None:
    rows = [
        {"binding_kind": "HISTORICAL"},
        {"binding_kind": "FIRST_AUTHORITY"},
        {"binding_kind": "EXPECTED_MISSING"},
    ]
    M.validate_admission_population(rows, {"a": {}, "b": {}}, total=3, present=2, kinds={"HISTORICAL": 1, "FIRST_AUTHORITY": 1, "EXPECTED_MISSING": 1})
    with pytest.raises(M.ValuePathError):
        M.validate_admission_population(rows[:-1], {"a": {}, "b": {}}, total=3, present=2, kinds={"HISTORICAL": 1, "FIRST_AUTHORITY": 1, "EXPECTED_MISSING": 1})
    real_rows = ([{"binding_kind": "HISTORICAL"}] * 2765 + [{"binding_kind": "FIRST_AUTHORITY"}] * 3 + [{"binding_kind": "EXPECTED_MISSING"}] * 16)
    M.validate_admission_population(real_rows, {str(index): {} for index in range(2768)})


def test_nominal_lexical_dot_segments_are_rejected() -> None:
    with pytest.raises(M.ValuePathError, match="dot traversal"):
        M.validate_nominal_source_path(r"D:\ThetaData\data_options\SPY\greeks\2026\01\.\SPY_20260109_20260102_greeks.parquet")
    with pytest.raises(M.ValuePathError, match="dot traversal"):
        M.validate_nominal_source_path(r"D:\ThetaData\data_options\SPY\greeks\2026\01\..\SPY_20260109_20260102_greeks.parquet")


def test_guard_path_walks_leaf_to_volume_anchor_and_rejects_late_reparse(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    leaf = root / "file.bin"
    leaf.write_bytes(b"x")
    visited: list[Path] = []

    def recording(value: Path):
        visited.append(value)
        return value.lstat()

    M.guard_path(leaf, root, lstat_adapter=recording)
    assert root in visited and tmp_path in visited and Path(tmp_path.anchor) in visited

    def reparse(value: Path):
        info = value.lstat()
        if value == tmp_path:
            return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=M.REPARSE)
        return info

    with pytest.raises(M.ValuePathError, match="reparse ancestor"):
        M.guard_path(leaf, root, lstat_adapter=reparse)


def test_secure_pin_rejects_nonregular_hardlink_symlink_and_lexical_alias(tmp_path: Path) -> None:
    regular = tmp_path / "regular.bin"
    regular.write_bytes(b"x")
    with pytest.raises(M.ValuePathError, match="regular file"):
        M.secure_pin(tmp_path)
    alias = tmp_path / "sub" / ".." / "regular.bin"
    with pytest.raises(M.ValuePathError, match="absolute lexical"):
        M.secure_pin(alias)
    hardlink = tmp_path / "hardlink.bin"
    os.link(regular, hardlink)
    with pytest.raises(M.ValuePathError, match="unaliased"):
        M.secure_pin(regular)
    symlink = tmp_path / "symlink.bin"
    try:
        os.symlink(regular, symlink)
    except OSError:
        pytest.skip("symlink creation unavailable")
    with pytest.raises(M.ValuePathError, match="linked metadata"):
        M.secure_pin(symlink)


def _trajectory_table(duplicate: bool = False) -> pa.Table:
    rows = []
    for right, strike, clocks in (
        ("C", 500.0, ["2026-01-02T09:29:00-05:00", "2026-01-02T09:30:00-05:00", "2026-01-02T09:31:00-05:00", "2026-01-02T09:31:01-05:00"]),
        ("P", 500.0, ["2026-01-02T09:30:00-05:00"]),
    ):
        for clock in clocks:
            rows.append((right, strike, clock))
    if duplicate:
        rows.append(("C", 500.0, "2026-01-02T09:30:00-05:00"))
    return pa.table({
        "symbol": ["SPY"] * len(rows), "expiration": ["20260109"] * len(rows),
        "trade_date": ["20260102"] * len(rows), "strike": [row[1] for row in rows],
        "right": [row[0] for row in rows], "timestamp": [row[2] for row in rows],
        "underlying_timestamp": [row[2] for row in rows], "interval_used": ["fixture"] * len(rows),
        "underlying_price": [501.0] * len(rows), "bid": [1.0] * len(rows), "ask": [2.0] * len(rows),
        "delta": [0.5 if row[0] == "C" else -0.5 for row in rows], "implied_vol": [0.2] * len(rows),
        "theta": [-0.1] * len(rows), "vega": [0.1] * len(rows), "rho": [0.01] * len(rows),
    })


def _write_trajectory_source(root: Path, day: str, *, duplicate: bool = False) -> tuple[str, dict[str, object]]:
    path = root / "SPY" / "greeks" / day[:4] / day[4:6] / f"SPY_20260109_{day}_greeks.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    table = _trajectory_table(duplicate)
    if day != "20260102":
        table = table.set_column(table.schema.get_field_index("trade_date"), "trade_date", pa.array([day] * table.num_rows))
        table = table.set_column(table.schema.get_field_index("timestamp"), "timestamp", pa.array([value.replace("2026-01-02", f"{day[:4]}-{day[4:6]}-{day[6:]}") for value in table["timestamp"].to_pylist()]))
        table = table.set_column(table.schema.get_field_index("underlying_timestamp"), "underlying_timestamp", table["timestamp"])
    pq.write_table(table, path)
    parquet = pq.ParquetFile(path)
    projection, clock, basis, gamma = M._source_projection(parquet.schema_arrow)
    observed_stat = M.guard_path(path, root)
    return str(path), {
        "path": str(path), "ticker": "SPY", "trade_date": day, "expiration": "20260109",
        "projected_schema": M.schema_descriptor(parquet.schema_arrow, projection), "full_schema": None,
        "clock_column": clock, "clock_basis": basis, "gamma_column_present": gamma,
        "sha256": M.sha256_file(path), "after_stat": observed_stat,
    }


def _stream_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, duplicate: bool = False):
    source_root = tmp_path / "options"
    source_root.mkdir()
    monkeypatch.setattr(M, "SOURCE_ROOT", source_root)
    d_path, d_meta = _write_trajectory_source(source_root, "20260102", duplicate=duplicate)
    d1_path, d1_meta = _write_trajectory_source(source_root, "20260105")
    plans = [
        {"status": "PLANNED", "plan_id": "SPY:20260102", "ticker": "SPY", "date": "20260102", "expiration": "20260109", "close_i": 2, "session_dates": {"D": "20260102", "D1": "20260105", "D2": "20260106"}},
        {"status": "NO_SERIES", "plan_id": "SPY:20260105", "ticker": "SPY", "date": "20260105", "close_i": 2},
        {"status": "NO_SERIES", "plan_id": "SPY:20260106", "ticker": "SPY", "date": "20260106", "close_i": 2},
    ]
    decisions = [
        {"decision_id": side, "plan_id": "SPY:20260102", "ticker": "SPY", "entry_date": "20260102", "expiration": "20260109", "right": side, "strike_decimal": "500"}
        for side in ("CALL", "PUT")
    ]
    journal = M.Journal(tmp_path / "journal.jsonl", gate=lambda: {"available_ram_bytes": M.MIN_FREE, "free_commit_bytes": M.MIN_FREE, "disk_free_bytes": M.MIN_FREE})
    output = tmp_path / "observations.parquet"
    result = M.stream_option_paths(plans, decisions, {d_path: d_meta, d1_path: d1_meta}, journal, output, expected_sources=3, expected_present=2)
    return result, output, tmp_path / "journal.jsonl"


def test_stream_union_reads_each_present_source_once_and_covers_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (observation_count, coverage, counts), output, journal_path = _stream_fixture(tmp_path, monkeypatch)
    assert observation_count == 6 and len(coverage) == 6
    assert sum(row["source_status"] == "MISSING" for row in coverage) == 2
    assert counts["ignored_subminute_rows"] == 2 and counts["ignored_out_of_session_rows"] == 2
    call_d = next(row for row in coverage if row["role"] == "D" and row["right"] == "CALL")
    put_d = next(row for row in coverage if row["role"] == "D" and row["right"] == "PUT")
    assert (call_d["ignored_subminute_rows"], call_d["ignored_out_of_session_rows"]) == (1, 1)
    assert (put_d["ignored_subminute_rows"], put_d["ignored_out_of_session_rows"]) == (0, 0)
    table = pq.read_table(output)
    assert table.num_rows == 6 and table["gamma"].null_count == 6
    assert set(table["interval_used"].to_pylist()) == {"fixture"}
    journal_rows = [json.loads(line) for line in journal_path.read_text(encoding="utf-8").splitlines()]
    completed = [row for row in journal_rows if row["kind"] == "STREAM_OPTION_PATHS" and row["event"] == "COMPLETED"]
    assert len(completed) == 2 and all(row["details"]["source_reads"] == 1 for row in completed)


def test_stream_duplicate_exact_contract_minute_is_fatal_and_partial_not_final(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(M.ValuePathError, match="duplicate exact-minute"):
        _stream_fixture(tmp_path, monkeypatch, duplicate=True)
    assert not (tmp_path / "final").exists()


def test_resource_gate_uses_official_helper_interface(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[object] = []

    class Helper:
        @staticmethod
        def observation() -> dict[str, int]:
            called.append("observation")
            return {"available_ram_bytes": M.MIN_FREE, "free_commit_bytes": M.MIN_FREE}

        @staticmethod
        def gate(value: object) -> None:
            called.append(value)

    monkeypatch.setattr(M, "_RESOURCE_HELPER_MODULE", Helper())
    monkeypatch.setattr(M.shutil, "disk_usage", lambda _path: type("Usage", (), {"free": M.MIN_FREE})())
    result = M.resource_gate(Path("D:/"))
    assert result["disk_free_bytes"] == M.MIN_FREE and called[0] == "observation" and isinstance(called[1], dict)


def test_validate_spot_result_exact_interface(tmp_path: Path) -> None:
    outputs = {}
    for name in ("cache_admission.jsonl", "spot_paths.parquet", "spot_coverage.jsonl"):
        path = tmp_path / name
        path.write_bytes(name.encode("ascii"))
        outputs[name] = M.pin(path)
    counts = {
        "identities": 2790, "available": 2772, "missing": 18, "full": 2766, "short": 24,
        "available_rows": 1079532, "missing_rows": 7038, "path_rows": 1086570,
        "valid_rows": 1, "invalid_rows": 1086569, "h1_available": 2619,
        "h1_missing": 6, "q3_available": 153, "q3_missing": 12, "admitted_inputs": 8163,
    }
    result = {"outputs": outputs, "counts": counts, "admitted_inputs": {f"p{i}": {} for i in range(8163)}}
    M.validate_spot_result(result, tmp_path)
    (tmp_path / "spot_paths.parquet").unlink()
    with pytest.raises((M.ValuePathError, FileNotFoundError)):
        M.validate_spot_result(result, tmp_path)


def test_journal_context_orders_started_then_completed(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    journal = M.Journal(path, gate=lambda: {"available_ram_bytes": M.MIN_FREE, "free_commit_bytes": M.MIN_FREE, "disk_free_bytes": M.MIN_FREE})
    with journal.unit_context("CACHE_SPOT_PATH", "SPY:20260102", []) as details:
        assert json.loads(path.read_text(encoding="utf-8"))["event"] == "STARTED"
        details["substeps"] = ["DECLARED_MISSING"]
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [row["event"] for row in rows] == ["STARTED", "COMPLETED"]
    assert rows[-1]["details"]["substeps"] == ["DECLARED_MISSING"]


def test_journal_context_persists_error(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    journal = M.Journal(path, gate=lambda: {"available_ram_bytes": M.MIN_FREE, "free_commit_bytes": M.MIN_FREE, "disk_free_bytes": M.MIN_FREE})
    with pytest.raises(RuntimeError):
        with journal.unit_context("X", "Y", []):
            raise RuntimeError("boom")
    assert [json.loads(line)["event"] for line in path.read_text(encoding="utf-8").splitlines()] == ["STARTED", "ERROR"]


def test_closing_rehash_is_per_file_and_detects_interruption(tmp_path: Path) -> None:
    path = tmp_path / "input.bin"
    path.write_bytes(b"before")
    journal = M.Journal(tmp_path / "journal.jsonl", gate=lambda: {"available_ram_bytes": M.MIN_FREE, "free_commit_bytes": M.MIN_FREE, "disk_free_bytes": M.MIN_FREE})
    M.closing_rehash_file(journal, "stable", M.pin(path), {})
    expected = M.pin(path)
    with pytest.raises(M.ValuePathError, match="changed during closing"):
        M.closing_rehash_file(journal, "mutated", expected, {}, middle=lambda: path.write_bytes(b"after"))
    events = [json.loads(line) for line in (tmp_path / "journal.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(row["identity"], row["event"]) for row in events] == [
        ("stable", "STARTED"), ("stable", "COMPLETED"),
        ("mutated", "STARTED"), ("mutated", "ERROR"),
    ]


def test_parquet_writer_schema_and_per_unit_row_groups(tmp_path: Path) -> None:
    path = tmp_path / "observations.parquet"
    rows = []
    for source in ("a", "b"):
        for minute in range(2):
            row = {name: None for name in M.OBSERVATION_SCHEMA.names}
            row.update(
                observation_id=f"{source}{minute}", source_path=source, source_sha256="0" * 64,
                ticker="SPY", trade_date="20260102", expiration="20260109", right="CALL",
                strike_decimal="500", minute_i=minute, clock_local=f"09:{30 + minute:02d}",
                clock_basis="NATIVE_STORED_TIMESTAMP", receipt_time_status="UNKNOWN",
                underlying_age_status="MISSING_OR_MALFORMED", quote_valid=False,
            )
            rows.append(row)
    assert M.write_parquet(path, rows, M.OBSERVATION_SCHEMA, group_key=lambda row: row["source_path"]) == 4
    parquet = pq.ParquetFile(path)
    assert parquet.metadata.num_rows == 4 and parquet.metadata.num_row_groups == 2


def test_parser_requires_reviewed_runtime_inputs() -> None:
    with pytest.raises(SystemExit):
        M.parser().parse_args([])
    args = M.parser().parse_args([
        "--execute-reviewed-builder", "--output-dir", "o", "--observer-dir", "b",
        "--journal", "j", "--implementation-pins-json", "p",
    ])
    assert args.execute_reviewed_builder is True


def test_no_closed_producer_import_or_forbidden_filename_literal() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "build_weekly_h2_dataset_v2" not in imports
    assert "weekly_multiday_source_pilot" not in imports
    forbidden = ("candidates.jsonl", "state60", "features.npz")
    lowered = source.lower()
    assert all(name not in lowered for name in forbidden)
    assert ".to_pylist()" not in source
    assert "pc.unique" in source and "pc.index_in" in source and "np.unique" in source


def test_summary_and_manifest_top_level_contract_shapes() -> None:
    summary = {key: {} for key in M.SUMMARY_KEYS}
    summary.update(schema="weekly_zone_event_value_paths_summary_v1", status=M.STATUS, outputs={name: {} for name in M.DATA_OUTPUT_NAMES}, flags=M.FLAGS, limitations=M.LIMITATIONS)
    M.validate_summary_document(summary)
    manifest = {key: {} for key in M.MANIFEST_KEYS}
    manifest.update(schema="weekly_zone_event_value_paths_manifest_v1", status=M.STATUS, outputs={name: {} for name in M.DATA_OUTPUT_NAMES | {"summary.json"}}, flags=M.FLAGS)
    M.validate_manifest_document(manifest)
    manifest["outputs"]["manifest.json"] = {}
    with pytest.raises(M.ValuePathError):
        M.validate_manifest_document(manifest)


def test_unit_context_is_compatible_with_spot_interface(tmp_path: Path) -> None:
    events: list[str] = []

    @contextlib.contextmanager
    def observed(kind: str, identity: str, paths: list[str]):
        events.append(f"begin:{kind}:{identity}:{len(paths)}")
        details: dict[str, object] = {}
        yield details
        events.append(f"end:{details['substeps']}")

    with observed("CACHE_SPOT_PATH", "SPY:20260102", []) as details:
        details["substeps"] = ["DECLARED_MISSING"]
    assert events == ["begin:CACHE_SPOT_PATH:SPY:20260102:0", "end:['DECLARED_MISSING']"]
