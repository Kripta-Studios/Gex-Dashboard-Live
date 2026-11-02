"""Synthetic, outcome-free tests for the independent weekly value-path auditor."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
import ast
import hashlib
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import audit_weekly_zone_event_value_paths_v2 as audit


NY = ZoneInfo("America/New_York")


def option_schema(*, gamma: bool = True, interval_type: pa.DataType = pa.string()) -> pa.Schema:
    fields = [
        pa.field("symbol", pa.string()), pa.field("expiration", pa.string()),
        pa.field("trade_date", pa.string()), pa.field("strike", pa.float64()),
        pa.field("right", pa.string()), pa.field("timestamp", pa.string()),
        pa.field("underlying_timestamp", pa.string()),
        pa.field("underlying_price", pa.float64()), pa.field("bid", pa.float64()),
        pa.field("ask", pa.float64()), pa.field("delta", pa.float64()),
        pa.field("implied_vol", pa.float64()),
    ]
    if gamma:
        fields.append(pa.field("gamma", pa.float64()))
    fields.extend([pa.field("theta", pa.float64()), pa.field("vega", pa.float64()),
                   pa.field("rho", pa.float64()), pa.field("interval_used", interval_type)])
    return pa.schema(fields)


def option_row(clock: str = "2026-01-05T10:30:00", *, right: str = "C", strike: float = 500.0,
               bid: float = 1.0, ask: float = 1.1, delta: float = 0.5) -> dict[str, object]:
    return {"symbol": "SPY", "expiration": "20260109", "trade_date": "20260105",
            "strike": strike, "right": right, "timestamp": clock,
            "underlying_timestamp": "2026-01-05T10:29:59", "underlying_price": 500.0,
            "bid": bid, "ask": ask, "delta": delta, "implied_vol": 0.2,
            "gamma": 0.01, "theta": -0.1, "vega": 0.2, "rho": 0.01,
            "interval_used": "1m"}


def write_option(path: Path, rows: list[dict[str, object]], *, gamma: bool = True) -> None:
    schema = option_schema(gamma=gamma)
    if not gamma:
        rows = [{key: value for key, value in row.items() if key != "gamma"} for row in rows]
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), path)


@pytest.mark.parametrize(("value", "expected"), [
    (date(2026, 1, 5), "20260105"), ("20260105", "20260105"), ("2026-01-05", "20260105"),
])
def test_parse_day_allowed(value: object, expected: str) -> None:
    assert audit.parse_day(value, "fixture") == expected


@pytest.mark.parametrize("value", [20260105, True, datetime(2026, 1, 5), " 20260105", "20260230"])
def test_parse_day_rejects_ambiguous_or_invalid(value: object) -> None:
    with pytest.raises(audit.AuditError):
        audit.parse_day(value, "fixture")


def test_clock_naive_and_aware_normalize_to_new_york() -> None:
    naive = audit.parse_clock("2026-01-05T10:30:00", "20260105")
    aware = audit.parse_clock("2026-01-05T15:30:00+00:00", "20260105")
    assert naive == aware
    assert audit.minute_index("2026-01-05T10:30:00", "20260105")[:2] == (60, True)


@pytest.mark.parametrize("value", [None, 1_700_000_000, True, "2026-01-05", "junk",
                                    "2026-01-06T14:30:00+00:00"])
def test_clock_rejects_null_epoch_bool_incomplete_malformed_or_local_date_mismatch(value: object) -> None:
    with pytest.raises(audit.AuditError):
        audit.parse_clock(value, "20260105")


def test_utc_calendar_date_crossing_that_is_still_prior_ny_date_is_valid() -> None:
    value = audit.parse_clock("2026-01-06T00:30:00+00:00", "20260105")
    assert value.strftime("%Y%m%d %H:%M") == "20260105 19:30"


def test_dst_nonexistent_and_ambiguous_naive_are_fatal() -> None:
    with pytest.raises(audit.AuditError):
        audit.parse_clock("2026-03-08T02:30:00", "20260308")
    with pytest.raises(audit.AuditError):
        audit.parse_clock("2026-11-01T01:30:00", "20261101")


def test_subminute_is_not_exact_and_is_never_rounded() -> None:
    minute, exact, _local = audit.minute_index("2026-01-05T10:30:00.001", "20260105")
    assert (minute, exact) == (60, False)


@pytest.mark.parametrize(("raw", "expected"), [("C", "CALL"), (" call ", "CALL"),
                                                 ("P", "PUT"), ("put", "PUT")])
def test_right_aliases(raw: str, expected: str) -> None:
    assert audit.normalize_right(raw) == expected


def test_decimal_identity_stays_in_price_units() -> None:
    assert audit.canonical_strike(500.0)[0] == "500"
    assert audit.canonical_strike("500.1250")[0] == "500.125"


@pytest.mark.parametrize(("bid", "ask", "valid"), [
    (0.0, 0.01, True), (1.0, 1.0, True), (-0.1, 1.0, False),
    (1.1, 1.0, False), (1.0, 0.0, False), (math.nan, 1.0, False), (True, 1.0, False),
])
def test_quote_validity(bid: object, ask: object, valid: bool) -> None:
    assert audit.quote_valid(bid, ask) is valid


def test_selector_side_delta_ask_limit_and_tie_break() -> None:
    base = option_row()
    assert audit.candidate_key(base, "CALL") == pytest.approx((0.0, 1 / 11, 500.0))
    assert audit.candidate_key({**base, "delta": -0.5}, "CALL") is None
    assert audit.candidate_key({**base, "ask": 49.95}, "CALL") is not None
    assert audit.candidate_key({**base, "ask": 49.9500001}, "CALL") is None


def test_scan_only_exact_1030_for_selector_and_counts_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "quotes.parquet"
    rows = [option_row("2026-01-05T10:29:00"), option_row("2026-01-05T10:30:00"),
            option_row("2026-01-05T10:30:00.001", strike=501.0),
            option_row("2026-01-05T16:01:00", strike=502.0)]
    write_option(path, rows)
    monkeypatch.setattr(audit, "SOURCE_ROOT", tmp_path)
    selected, footer, counts = audit.scan_option_source(path, "SPY", "20260105", "20260109", 390, None, True)
    assert [row["minute_i"] for row in selected] == [60]
    assert footer["clock_basis"] == "NATIVE_STORED_TIMESTAMP"
    assert counts["ignored_subminute_rows"] == 1
    assert counts["ignored_out_of_session_rows"] == 1


def test_scan_duplicate_contract_minute_is_fatal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "quotes.parquet"
    write_option(path, [option_row(), option_row()])
    monkeypatch.setattr(audit, "SOURCE_ROOT", tmp_path)
    with pytest.raises(audit.AuditError, match="duplicate"):
        audit.scan_option_source(path, "SPY", "20260105", "20260109", 390, None, False)


def test_scan_duplicate_nonwanted_contract_is_still_fatal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "quotes.parquet"
    write_option(path, [option_row(strike=600.0), option_row(strike=600.0)])
    monkeypatch.setattr(audit, "SOURCE_ROOT", tmp_path)
    with pytest.raises(audit.AuditError, match="duplicate"):
        audit.scan_option_source(path, "SPY", "20260105", "20260109", 390, {("500", "CALL")}, False)


def test_gamma_absent_is_explicit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "quotes.parquet"
    write_option(path, [option_row()], gamma=False)
    monkeypatch.setattr(audit, "SOURCE_ROOT", tmp_path)
    rows, footer, _counts = audit.scan_option_source(path, "SPY", "20260105", "20260109", 390, None, False)
    assert rows[0]["gamma_column_present"] is False
    assert footer["gamma_column_present"] is False


def test_interval_used_type_guard() -> None:
    with pytest.raises(audit.AuditError, match="interval_used"):
        audit.validate_option_schema(option_schema(interval_type=pa.list_(pa.int32())))


def test_missing_ranges_are_maximal_inclusive() -> None:
    assert audit.missing_ranges({0, 1, 4, 6}, 6) == [
        {"start_i": 2, "end_i": 3}, {"start_i": 5, "end_i": 5},
    ]
    assert audit.missing_ranges(set(), 2) == [{"start_i": 0, "end_i": 2}]


def test_stable_ids_use_compact_json_contract() -> None:
    parts = ["SPY:20260105", "SPY", "20260109", "500", "CALL"]
    expected = __import__("hashlib").sha256(b'["SPY:20260105","SPY","20260109","500","CALL"]').hexdigest()
    assert audit.stable_id(parts) == expected


def test_npz_reads_only_triplet_and_preserves_invalid_nan(tmp_path: Path) -> None:
    path = tmp_path / "cache.npz"
    start = np.datetime64("2026-01-05T09:30", "ns").astype(np.int64)
    axis = start + np.arange(391, dtype=np.int64) * 60_000_000_000
    spot = np.full(391, 500.0, dtype=np.float64)
    valid = np.ones(391, dtype=np.bool_)
    spot[7], valid[7] = np.nan, False
    np.savez(path, time_ns=axis, spot=spot, spot_valid=valid, forbidden=np.arange(3))
    rows, counts = audit.validate_npz(path, "SPY", "20260105", 390)
    assert math.isnan(rows[7]["spot"]) and rows[7]["spot_valid"] is False
    assert counts["invalid_count"] == 1


def test_npz_axis_dtype_shape_and_true_mask_are_strict(tmp_path: Path) -> None:
    path = tmp_path / "bad.npz"
    axis = np.arange(391, dtype=np.int64)
    np.savez(path, time_ns=axis, spot=np.ones(391, dtype=np.float64), spot_valid=np.ones(391, dtype=np.bool_))
    with pytest.raises(audit.AuditError, match="time axis"):
        audit.validate_npz(path, "SPY", "20260105", 390)


def test_cache_metadata_triplet_schema_and_version(tmp_path: Path) -> None:
    json_path, npz_path = tmp_path / "cache.json", tmp_path / "cache.npz"
    npz_path.write_bytes(b"fixture")
    pin = audit.file_pin(npz_path)
    document = {"version": "SESSION_CLOCK_CACHE_V1", "ticker": "SPY", "date": "20261127",
                "npz_bytes": pin["bytes"], "sha256": pin["sha256"],
                "array_schema": {"time_ns": {"shape": [211], "dtype": "int64"},
                                 "spot": {"shape": [211], "dtype": "float64"},
                                 "spot_valid": {"shape": [211], "dtype": "bool"},
                                 "fourth": {"shape": [211], "dtype": "float64"}}}
    assert audit.validate_cache_metadata(document, json_path, npz_path, "SPY", "20261127", 210, pin) == "SESSION_CLOCK_CACHE_V1"


def test_guard_rejects_traversal_symlink_hardlink_and_alias(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.write_text("x", encoding="utf-8")
    with pytest.raises(audit.AuditError):
        audit.guard_file(tmp_path / ".." / tmp_path.name / "source", (tmp_path,))
    link = tmp_path / "link"
    try:
        link.symlink_to(source)
    except OSError:
        link = None
    if link is not None:
        with pytest.raises(audit.AuditError):
            audit.guard_file(link, (tmp_path,))
    hard = tmp_path / "hard"
    try:
        hard.hardlink_to(source)
    except OSError:
        hard = None
    if hard is not None:
        with pytest.raises(audit.AuditError):
            audit.guard_file(source, (tmp_path,))


def test_compare_rows_is_order_schema_and_nan_exact() -> None:
    audit.compare_rows([{"a": 1, "b": float("nan")}], [{"a": 1, "b": float("nan")}], "fixture")
    with pytest.raises(audit.AuditError):
        audit.compare_rows([{"b": 2, "a": 1}], [{"a": 1, "b": 2}], "fixture")


def test_exact_output_map_rejects_wrong_path_rows_missing_extra_and_nested_keys(tmp_path: Path) -> None:
    path = tmp_path / "data.jsonl"
    path.write_text("{}\n", encoding="utf-8")
    pin = audit.file_pin(path) | {"rows": 1}
    audit.validate_output_map({path.name: pin}, tmp_path, {path.name: 1}, "fixture")
    for bad in (
        {path.name: pin | {"path": str(tmp_path / "other.jsonl")}},
        {path.name: pin | {"rows": 2}},
        {},
        {path.name: pin, "extra": pin},
        {path.name: pin | {"unexpected": 1}},
    ):
        with pytest.raises(audit.AuditError):
            audit.validate_output_map(bad, tmp_path, {path.name: 1}, "fixture")


def test_exact_top_keys_reject_missing_and_extra() -> None:
    audit.require_keys({"a": 1}, {"a"}, "fixture")
    with pytest.raises(audit.AuditError):
        audit.require_keys({"a": 1, "b": 2}, {"a"}, "fixture")
    with pytest.raises(audit.AuditError):
        audit.require_keys({}, {"a"}, "fixture")


def test_journal_unit_persists_error_and_does_not_swallow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audit, "resource_gate", lambda: {
        "available_ram_bytes": 3_000_000_000, "free_commit_bytes": 3_000_000_000,
        "disk_free_bytes": 3_000_000_000,
    })
    journal = audit.Journal(tmp_path / "journal.jsonl")
    with pytest.raises(RuntimeError):
        with journal.unit("CACHE_SPOT_PATH", "SPY:20260105", []):
            raise RuntimeError("fixture")
    rows = [json.loads(line) for line in (tmp_path / "journal.jsonl").read_text().splitlines()]
    assert [row["event"] for row in rows] == ["STARTED", "ERROR"]


def test_unit_started_is_fsynced_before_body_open(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audit, "resource_gate", lambda: {
        "available_ram_bytes": 3_000_000_000, "free_commit_bytes": 3_000_000_000,
        "disk_free_bytes": 3_000_000_000,
    })
    journal = audit.Journal(tmp_path / "journal.jsonl")
    with journal.unit("CACHE_SPOT_PATH", "SPY:20260105", []):
        rows = [json.loads(line) for line in journal.path.read_text().splitlines()]
        assert [row["event"] for row in rows] == ["STARTED"]


def test_source_has_no_producer_or_spot_import_and_names_forbidden_sources() -> None:
    source = Path(audit.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imports |= {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert "build_weekly_zone_event_value_paths" not in imports
    assert "weekly_zone_event_spot_paths" not in imports
    for forbidden in ("candidates.jsonl", "context.jsonl", "state60", "features.npz"):
        assert forbidden in source


@pytest.mark.parametrize("name", ["candidates.jsonl", "outcomes.jsonl", "features.npz", "state60.npz"])
def test_forbidden_path_fails_before_any_lstat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    called = False

    def forbidden_lstat(self: Path):
        nonlocal called
        called = True
        raise AssertionError("lstat/open must not occur")

    monkeypatch.setattr(Path, "lstat", forbidden_lstat)
    with pytest.raises(audit.AuditError, match="forbidden path"):
        audit.guard_file(tmp_path / name, (tmp_path,))
    assert called is False


def test_full_producer_journal_lifecycle_and_source_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gate = {"available_ram_bytes": 3_000_000_000, "free_commit_bytes": 3_000_000_000,
            "disk_free_bytes": 3_000_000_000}
    rows = []

    fake_stat = {"exists": True, "bytes": 1, "mtime_ns": 7, "physical_id": [1, 2]}
    monkeypatch.setattr(audit, "stat_record", lambda _path: dict(fake_stat))
    monkeypatch.setattr(audit, "file_pin", lambda path: {"path": str(path), "bytes": 1, "sha256": "0" * 64})
    monkeypatch.setattr(audit, "guard_file", lambda path, _roots, _seen=None: Path(path))

    def pair(kind: str, identity: str, details: dict[str, object] | None = None,
             paths: list[str] | None = None) -> None:
        paths = paths or []
        rows.append({"kind": kind, "identity": identity, "event": "STARTED", "paths": paths, "gate": gate})
        completed = {"kind": kind, "identity": identity, "event": "COMPLETED", "paths": paths,
                     "gate": gate, "details": deepcopy(details) if details is not None else {}}
        rows.append(completed)

    def fake_pin(path: Path | str) -> dict[str, object]:
        return {"path": str(path), "bytes": 1, "sha256": "0" * 64}

    implementation_document_path = str((tmp_path / "implementation_pins.json").absolute())
    authority_pins = {f"authority_{index}": fake_pin((tmp_path / f"authority_{index}.json").absolute())
                      for index in range(29)}
    implementation_pins = {name: fake_pin((tmp_path / f"implementation_{name}.txt").absolute())
                           for name in audit.IMPLEMENTATION_PATHS}
    pair("ADMIT_AUTHORITIES", "IMPLEMENTATION_PINS", {"pins": 10}, [implementation_document_path])
    pair("ADMIT_AUTHORITIES", "PINNED_AUTHORITIES", {"authorities": 29},
         [value["path"] for value in authority_pins.values()])
    calendar_path = str((tmp_path / "unified_calendar.json").absolute())
    calendar_details = {
        "raw_pin": {"path": calendar_path, "bytes": 232573, "sha256": "b" * 64},
        "raw_schema": "weekly_h2_boundary_unified_calendar_v1", "raw_rows": 2790,
        "raw_order": audit.RAW_CALENDAR_ORDER, "canonical_order": audit.CANONICAL_CALENDAR_ORDER,
        "canonical_rows": 2790, "canonical_jsonl_bytes": audit.CANONICAL_CALENDAR_BYTES,
        "canonical_jsonl_sha256": audit.CANONICAL_CALENDAR_SHA256,
        "identity_set_preserved": True, "close_i_preserved": True,
    }
    pair("NORMALIZE_CALENDAR", "UNIFIED_CALENDAR", calendar_details, [calendar_path])
    for kind in ("ADMIT_OPTION_FOOTERS", "SELECT_1030", "STREAM_OPTION_PATHS",
                 "WRITE_OUTPUTS"):
        pair(kind, "GLOBAL_PASS")
    tickers = ("SPY", "QQQ", "SPXW")
    trajectory_list = [str((tmp_path / f"source_{index}.parquet").absolute()) for index in range(2768)]
    trajectory_ids = set(trajectory_list)
    selector_ids = {f"{tickers[index % 3]}:{20230101 + index:08d}":
                    trajectory_list[index] for index in range(1620)}
    for identity, entry_path in selector_ids.items():
        pair("SELECT_1030", identity, {"source_reads": 1, "before_stat": fake_stat, "after_stat": fake_stat,
                                      "sha256_before": "0" * 64, "sha256_after": "0" * 64}, [entry_path])
    for identity in trajectory_ids:
        pair("STREAM_OPTION_PATHS", identity, {"source_reads": 1, "before_stat": fake_stat,
                                               "after_stat": fake_stat, "sha256_before": "0" * 64,
                                               "sha256_after": "0" * 64}, [identity])
    missing = {
        *(f"{ticker}:{day}" for ticker in ("QQQ", "SPY") for day in ("20260401", "20260409", "20260415")),
        *(f"{ticker}:{day}" for ticker in ("QQQ", "SPY") for day in
          ("20260701", "20260707", "20260710", "20260716", "20260826", "20260901")),
    }
    identities = list(missing)
    identities.extend(f"SPXW:{20230000 + index:08d}" for index in range(2790 - len(identities)))
    for identity in identities:
        steps = ["DECLARED_MISSING"] if identity in missing else ["ADMIT_SPOT_METADATA", "LOAD_SPOT_TRIPLETS"]
        pair("CACHE_SPOT_PATH", identity, {"substeps": steps})
    source_pins = {path: fake_pin(path) for path in trajectory_ids}
    spot_pins = {str((tmp_path / f"spot_{index}.bin").absolute()):
                 fake_pin((tmp_path / f"spot_{index}.bin").absolute()) for index in range(8163)}
    expected_missing = {str((tmp_path / f"missing_{index}.parquet").absolute()) for index in range(16)}
    runtime_inputs = {**authority_pins, **source_pins, **spot_pins, **implementation_pins,
                      "runtime_implementation_pins_document": fake_pin(implementation_document_path)}
    for identity, pin in runtime_inputs.items():
        pair("CLOSING_REHASH", identity, {"before": pin, "after": pin}, [pin["path"]])
    missing_stat = {"exists": False, "bytes": None, "mtime_ns": None, "physical_id": None}
    for path in expected_missing:
        pair("CLOSING_REHASH", f"EXPECTED_MISSING:{path}",
             {"before": missing_stat, "after": missing_stat}, [path])
    output_names = (*audit.DATA_OUTPUTS, "summary.json")
    output_pins = {name: {**fake_pin((audit.PRODUCER / name).absolute()), "rows": 1}
                   for name in output_names}
    staging = audit.PRODUCER.parent / f".{audit.PRODUCER.name}.fixture"
    for name in (*output_names, "manifest.json"):
        final_pin = output_pins.get(name, fake_pin((audit.PRODUCER / name).absolute()))
        staging_pin = {"path": str((staging / name).absolute()), "bytes": final_pin["bytes"],
                       "sha256": final_pin["sha256"]}
        pair("CLOSING_REHASH", f"OUTPUT:{name}",
             {"before": staging_pin, "after": staging_pin}, [staging_pin["path"]])
    producer_manifest = {"outputs": output_pins}
    journal = tmp_path / "journal.jsonl"
    def encode(row: dict[str, object]) -> str:
        return json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
    journal.write_text("".join(encode(row) for row in rows), encoding="utf-8")
    cache_ids = set(identities)

    def validate() -> dict[str, int]:
        return audit.validate_producer_journal(
            tmp_path / "exit.json", selector_ids, trajectory_ids, cache_ids, source_pins,
            calendar_details, authority_pins, implementation_pins, spot_pins,
            expected_missing, producer_manifest,
        )

    result = validate()
    assert result["selector_source_contexts"] == 1620
    assert result["trajectory_source_contexts"] == 2768
    assert result["cache_contexts"] == 2790
    pinned_completed = next(row for row in rows if row.get("kind") == "ADMIT_AUTHORITIES" and
                            row.get("identity") == "PINNED_AUTHORITIES" and row.get("event") == "COMPLETED")
    pinned_completed["details"]["authorities"] = 28
    journal.write_text("".join(encode(row) for row in rows), encoding="utf-8")
    with pytest.raises(audit.AuditError, match="authority admission lifecycle"):
        validate()
    pinned_completed["details"]["authorities"] = 29
    pinned_completed["identity"] = "WRONG_AUTHORITIES"
    journal.write_text("".join(encode(row) for row in rows), encoding="utf-8")
    with pytest.raises(audit.AuditError, match="authority admission identities"):
        validate()
    pinned_completed["identity"] = "PINNED_AUTHORITIES"
    normalization_completed = next(row for row in rows if row.get("kind") == "NORMALIZE_CALENDAR" and
                                   row.get("event") == "COMPLETED")
    normalization_completed["details"]["canonical_rows"] = 2789
    journal.write_text("".join(encode(row) for row in rows), encoding="utf-8")
    with pytest.raises(audit.AuditError, match="normalization details"):
        validate()
    normalization_completed["details"]["canonical_rows"] = 2790
    rows.remove(normalization_completed)
    footer_started_i = next(index for index, row in enumerate(rows)
                            if row.get("kind") == "ADMIT_OPTION_FOOTERS" and row.get("event") == "STARTED")
    rows.insert(footer_started_i + 1, normalization_completed)
    journal.write_text("".join(encode(row) for row in rows), encoding="utf-8")
    with pytest.raises(audit.AuditError, match="journal order"):
        validate()
    rows.remove(normalization_completed)
    normalize_started_i = next(index for index, row in enumerate(rows)
                               if row.get("kind") == "NORMALIZE_CALENDAR" and row.get("event") == "STARTED")
    rows.insert(normalize_started_i + 1, normalization_completed)
    original = next(iter(selector_ids))
    for row in rows:
        if row.get("kind") == "SELECT_1030" and row.get("identity") == original:
            row["identity"] = "SPY:20991231"
    journal.write_text("".join(encode(row) for row in rows), encoding="utf-8")
    with pytest.raises(audit.AuditError, match="exact identity set"):
        validate()
    for row in rows:
        if row.get("identity") == "SPY:20991231":
            row["identity"] = original
    completed_selector = next(row for row in rows if row.get("kind") == "SELECT_1030" and
                              row.get("event") == "COMPLETED" and row.get("identity") == original)
    saved_paths = completed_selector["paths"]
    wrong_path = str((tmp_path / "wrong_selector.parquet").absolute())
    completed_selector["paths"] = [wrong_path]
    journal.write_text("".join(encode(row) for row in rows), encoding="utf-8")
    with pytest.raises(audit.AuditError, match="event path identity"):
        validate()
    completed_selector["paths"] = saved_paths
    completed_source = next(row for row in rows if row.get("kind") == "STREAM_OPTION_PATHS" and
                            row.get("event") == "COMPLETED" and row.get("identity") in trajectory_ids)
    completed_source["details"]["source_reads"] = 2
    journal.write_text("".join(encode(row) for row in rows), encoding="utf-8")
    with pytest.raises(audit.AuditError, match="source_reads"):
        validate()
    completed_source["details"]["source_reads"] = 1
    closing_completed = next(row for row in rows if row.get("kind") == "CLOSING_REHASH" and
                             row.get("identity") == "authority_0" and row.get("event") == "COMPLETED")
    closing_expected = closing_completed["details"]["before"]
    closing_completed["details"]["before"] = {**closing_expected, "sha256": "f" * 64}
    closing_completed["details"]["after"] = {**closing_expected, "sha256": "f" * 64}
    journal.write_text("".join(encode(row) for row in rows), encoding="utf-8")
    with pytest.raises(audit.AuditError, match="closing input pin"):
        validate()
    closing_completed["details"]["before"] = closing_expected
    closing_completed["details"]["after"] = closing_expected
    authority_one = [row for row in rows if row.get("kind") == "CLOSING_REHASH" and
                     row.get("identity") == "authority_1"]
    rows[:] = [row for row in rows if row not in authority_one]
    journal.write_text("".join(encode(row) for row in rows), encoding="utf-8")
    with pytest.raises(audit.AuditError, match="closing exact identity set"):
        validate()
    rows.extend(authority_one)
    pair("CLOSING_REHASH", "EXTRA_INPUT", {"before": fake_pin("D:\\extra"),
                                             "after": fake_pin("D:\\extra")}, ["D:\\extra"])
    journal.write_text("".join(encode(row) for row in rows), encoding="utf-8")
    with pytest.raises(audit.AuditError, match="closing exact identity set"):
        validate()
    rows[:] = [row for row in rows if row.get("identity") != "EXTRA_INPUT"]
    rows.extend(dict(row) for row in authority_one)
    journal.write_text("".join(encode(row) for row in rows), encoding="utf-8")
    with pytest.raises(audit.AuditError, match="closing exact identity set"):
        validate()


def test_cli_default_is_readiness_only(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    assert audit.main([]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "READY_NOT_EXECUTED"


def test_expected_cardinality_is_parameterized_and_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audit, "scan_option_source", lambda *args, **kwargs: (
        [option_row() | {"strike_decimal": "500", "right_normalized": "CALL"}],
        {"clock_basis": "NATIVE_STORED_TIMESTAMP", "gamma_column_present": True}, {},
    ))
    plan = {"status": "PLANNED", "entry_path": __file__, "ticker": "SPY", "date": "20260105",
            "expiration": "20260109", "close_i": 390, "plan_id": "SPY:20260105", "source_authority": "H1"}
    with pytest.raises(audit.AuditError, match="cardinality"):
        audit.select_contracts([plan], expected=2)


def test_spot_population_exact_h1_q3_full_short_without_runtime_monkeypatch() -> None:
    rows = []
    rows += [{"authority": "H1", "cache_status": "AVAILABLE", "session_kind": "FULL"}] * 2595
    rows += [{"authority": "H1", "cache_status": "AVAILABLE", "session_kind": "SHORT"}] * 24
    rows += [{"authority": "H1", "cache_status": "MISSING", "session_kind": "FULL"}] * 6
    rows += [{"authority": "Q3", "cache_status": "AVAILABLE", "session_kind": "FULL"}] * 153
    rows += [{"authority": "Q3", "cache_status": "MISSING", "session_kind": "FULL"}] * 12
    audit.validate_cache_population(rows)
    rows.pop()
    with pytest.raises(audit.AuditError):
        audit.validate_cache_population(rows)


def synthetic_calendar() -> list[dict[str, object]]:
    rows = []
    for ticker in ("QQQ", "SPXW", "SPY"):
        for day in ("20260105", "20260106"):
            rows.append({"close_i": 210 if (ticker, day) == ("SPY", "20260105") else 390,
                         "date": day, "ticker": ticker})
    return rows


def test_v2_calendar_normalization_digest_copy_and_envelope() -> None:
    rows = synthetic_calendar()
    upstream_snapshot = [dict(row) for row in rows]
    canonical_expected = sorted(rows, key=lambda row: (row["date"], audit.TICKER_ORDINAL[row["ticker"]]))
    payload = b"".join(json.dumps(row, sort_keys=True, separators=(",", ":")).encode() + b"\n"
                       for row in canonical_expected)
    digest = hashlib.sha256(payload).hexdigest()
    raw_pin = {"path": "D:\\fixture\\unified_calendar.json", "bytes": 10, "sha256": "a" * 64}
    canonical, envelope, details = audit.normalize_calendar_v2(
        {"schema": "weekly_h2_boundary_unified_calendar_v1", "rows": rows}, raw_pin,
        expected_sessions=2, expected_short=1, expected_full=5,
        expected_bytes=len(payload), expected_sha256=digest,
    )
    assert canonical == canonical_expected and canonical is not rows
    assert rows == upstream_snapshot
    assert all(canonical_row is not upstream_row for canonical_row in canonical for upstream_row in rows)
    assert envelope["canonical_jsonl_sha256"] == digest
    assert details["raw_schema"] == "weekly_h2_boundary_unified_calendar_v1"
    assert details["canonical_rows"] == 6


@pytest.mark.parametrize("mutation", [
    "order", "duplicate", "ticker_date_set", "close_i", "extra_key", "ticker_domain",
    "date_type", "close_type",
])
def test_v2_calendar_rejects_drift_before_values(mutation: str) -> None:
    rows = synthetic_calendar()
    if mutation == "order":
        rows[0], rows[1] = rows[1], rows[0]
    elif mutation == "duplicate":
        rows[1] = dict(rows[0])
    elif mutation == "ticker_date_set":
        rows[1] = {**rows[1], "date": "20260107"}
    elif mutation == "close_i":
        rows[0] = {**rows[0], "close_i": 210}
    elif mutation == "extra_key":
        rows[0] = {**rows[0], "extra": 1}
    elif mutation == "ticker_domain":
        rows[0] = {**rows[0], "ticker": "IWM"}
    elif mutation == "date_type":
        rows[0] = {**rows[0], "date": 20260105}
    else:
        rows[0] = {**rows[0], "close_i": 390.0}
    with pytest.raises(audit.AuditError):
        audit.normalize_calendar_v2(
            {"schema": "weekly_h2_boundary_unified_calendar_v1", "rows": rows},
            {"path": "D:\\fixture\\calendar.json", "bytes": 1, "sha256": "a" * 64},
            expected_sessions=2, expected_short=1, expected_full=5,
            expected_bytes=1, expected_sha256="0" * 64,
        )


def test_v2_prior_failure_envelope_and_mutations() -> None:
    gate = {"available_ram_bytes": 3_000_000_000, "disk_free_bytes": 3_000_000_000,
            "free_commit_bytes": 3_000_000_000}
    implementation_paths = [str((audit.PRIOR_PRODUCER_OBSERVER / "implementation_pins.json").absolute())]
    extra_names = {"original_value_path_contract", "prior_producer_exit", "prior_producer_failure",
                   "prior_producer_journal"}
    authority_paths = [str((path if path.is_absolute() else audit.HERE / path).absolute())
                       for name, (path, _size, _digest) in audit.PINS.items() if name not in extra_names]

    def prior_row(identity: str, event: str, paths: list[str],
                  details: dict[str, int] | None = None) -> dict[str, object]:
        row: dict[str, object] = {"at_utc": "2026-11-02T12:33:10+00:00", "event": event,
                                  "gate": dict(gate), "identity": identity,
                                  "kind": "ADMIT_AUTHORITIES", "paths": paths}
        if details is not None:
            row["details"] = details
        return row

    rows = [
        prior_row("IMPLEMENTATION_PINS", "STARTED", implementation_paths),
        prior_row("IMPLEMENTATION_PINS", "COMPLETED", implementation_paths, {"pins": 10}),
        prior_row("PINNED_AUTHORITIES", "STARTED", authority_paths),
        prior_row("PINNED_AUTHORITIES", "COMPLETED", authority_paths, {"authorities": 25}),
    ]
    documents = {
        "prior_producer_exit": {"exit_code": 1, "value_child_exit_code": 1, "retry": False,
                                "changed_pins": []},
        "prior_producer_failure": {"exit_code": 1, "value_child_exit_code": 1,
                                   "partial_output_not_authorized_for_adoption": True, "retry": False},
        "prior_producer_journal": rows,
    }
    audit.validate_prior_failure_v2(documents)
    error_rows = [dict(row) for row in rows]
    error_rows[-1] = {**error_rows[-1], "event": "ERROR"}
    wrong_path_rows = [dict(row) for row in rows]
    wrong_path_rows[-1] = {**wrong_path_rows[-1], "paths": [*authority_paths[:-1], "D:\\wrong.json"]}
    for bad in (
        {**documents, "prior_producer_exit": {**documents["prior_producer_exit"], "exit_code": 0}},
        {**documents, "prior_producer_failure": {**documents["prior_producer_failure"],
                                                  "partial_output_not_authorized_for_adoption": False}},
        {**documents, "prior_producer_journal": error_rows},
        {**documents, "prior_producer_journal": wrong_path_rows},
    ):
        with pytest.raises(audit.AuditError):
            audit.validate_prior_failure_v2(bad)


def test_v2_authority_population_roots_and_contract_pins() -> None:
    assert len(audit.PINS) == 29
    assert set(audit.PINS) >= {"original_value_path_contract", "prior_producer_exit",
                               "prior_producer_failure", "prior_producer_journal"}
    assert audit.PRODUCER.name.endswith("_02") and audit.OUTPUT.name.endswith("_02")
    assert audit.OBSERVER.name.endswith("_02") and audit.PRODUCER_OBSERVER.name.endswith("_02")
    assert audit.PRIOR_PRODUCER_OBSERVER.name.endswith("_01")
    assert audit.CONTRACT_SHA256 == "65fd1aaef25ddea13957ce07e6c21285771adc889f097d603f93e00572cf1146"


def test_v2_rejects_active_v1_roots_before_open() -> None:
    producer01 = audit.BASE / "weekly_zone_event_value_paths_01"
    observer01_exit = audit.BASE / "weekly_zone_event_value_paths_observer_01" / "exit.json"
    with pytest.raises(audit.AuditError, match="fixed producer root"):
        audit.validate_producer_manifest(producer01, "0" * 64, observer01_exit, "0" * 64, {})
    with pytest.raises(audit.AuditError, match="exclusive audit roots"):
        audit.run(producer01, "0" * 64, observer01_exit, "0" * 64, "0" * 64, "0" * 64,
                  {}, {}, {}, audit.BASE / "weekly_zone_event_value_paths_audit_01",
                  audit.BASE / "weekly_zone_event_value_paths_audit_observer_01")


def test_v2_implementation_pin_rejects_same_hash_at_wrong_path(tmp_path: Path) -> None:
    copied_builder = tmp_path / "build_weekly_zone_event_value_paths_v2.py"
    copied_builder.write_bytes(audit.IMPLEMENTATION_PATHS["builder"].read_bytes())
    pins = {name: {"path": str(path.absolute()), "bytes": 1, "sha256": "0" * 64}
            for name, path in audit.IMPLEMENTATION_PATHS.items()}
    pins["builder"] = audit.file_pin(copied_builder)
    with pytest.raises(audit.AuditError, match="implementation pin exact path: builder"):
        audit.validate_implementation_pins({"implementation_pins": pins})


def test_v2_ast_diff_whitelist_preserves_shared_science() -> None:
    v1_path = Path(audit.__file__).with_name("audit_weekly_zone_event_value_paths.py")
    v1_tree = ast.parse(v1_path.read_text(encoding="utf-8"))
    v2_tree = ast.parse(Path(audit.__file__).read_text(encoding="utf-8"))
    v1_functions = {node.name: node for node in v1_tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    v2_functions = {node.name: node for node in v2_tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    allowed = {"admit_pins", "expected_cache_admission", "validate_producer_manifest",
               "validate_implementation_pins", "validate_producer_journal", "run"}
    shared = set(v1_functions) & set(v2_functions)
    extras = {"validate_prior_failure_v2", "normalize_calendar_v2", "validate_calendar_envelope"}
    assert set(v1_functions) <= set(v2_functions)
    assert set(v2_functions) - set(v1_functions) == extras
    assert allowed <= shared
    changed = {name for name in shared if ast.dump(v1_functions[name], include_attributes=False) !=
               ast.dump(v2_functions[name], include_attributes=False)}
    assert changed == allowed
    imports = {alias.name for node in ast.walk(v2_tree) if isinstance(node, ast.Import) for alias in node.names}
    imports |= {node.module for node in ast.walk(v2_tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert "build_weekly_zone_event_value_paths_v2" not in imports
    assert "weekly_zone_event_spot_paths" not in imports

