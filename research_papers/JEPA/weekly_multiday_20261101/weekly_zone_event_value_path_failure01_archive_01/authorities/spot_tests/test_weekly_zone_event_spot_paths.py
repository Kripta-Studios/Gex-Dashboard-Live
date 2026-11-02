"""Synthetic, outcome-free fixtures for weekly_zone_event_spot_paths."""

from __future__ import annotations

import ast
import os
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import weekly_zone_event_spot_paths as spot


def _weekdays(start: date, count: int, required: set[str] | None = None) -> list[str]:
    values = set(required or set())
    cursor = start
    while len(values) < count:
        if cursor.weekday() < 5:
            values.add(cursor.strftime("%Y%m%d"))
        cursor += timedelta(days=1)
    return sorted(values)[:count]


def _calendar() -> list[dict[str, object]]:
    dates = _weekdays(date(2023, 1, 3), 930)
    short_dates = set(dates[100:108])
    return [
        {
            "ticker": ticker,
            "date": value,
            "close_i": 210 if value in short_dates else 390,
        }
        for value in dates
        for ticker in ("SPY", "QQQ", "SPXW")
    ]


def _pin(path: Path, index: int) -> dict[str, object]:
    return {"path": str(path), "bytes": index + 1, "sha256": f"{index + 1:064x}"[-64:]}


def _authorities() -> tuple[dict[str, object], dict[str, object]]:
    h1_required = {value for _, value in spot.H1_MISSING}
    h1_dates = _weekdays(date(2023, 1, 3), 875, h1_required)
    h1_rows: list[dict[str, object]] = []
    feature_inputs: list[dict[str, object]] = []
    index = 10
    for ticker in ("QQQ", "SPY", "SPXW"):
        for value in h1_dates:
            key = (ticker, value)
            if key in spot.H1_MISSING:
                h1_rows.append(
                    {
                        "close_i": 390,
                        "date": value,
                        "features": None,
                        "features_metadata": None,
                        "reused_full_session": False,
                        "status": "MISSING_SOURCE",
                        "ticker": ticker,
                    }
                )
                continue
            feature = _pin(Path(fr"D:\fixture\features\{ticker}\{value}\features.npz"), index)
            index += 1
            metadata = _pin(Path(fr"D:\fixture\references\{ticker}\{value}\features.json"), index)
            index += 1
            h1_rows.append(
                {
                    "close_i": 390,
                    "date": value,
                    "features": feature,
                    "features_metadata": metadata,
                    "reused_full_session": True,
                    "status": "COMPLETE",
                    "ticker": ticker,
                }
            )
            feature_inputs.append(feature)

    q3_required = {value for _, value in spot.Q3_MISSING}
    q3_dates = _weekdays(date(2026, 7, 1), 55, q3_required)
    q3_rows: list[dict[str, object]] = []
    raw_files: dict[str, dict[str, object]] = {}
    for ticker in ("SPY", "QQQ", "SPXW"):
        for value in q3_dates:
            key = (ticker, value)
            missing = key in spot.Q3_MISSING
            q3_rows.append(
                {
                    "close_i": 390,
                    "date": value,
                    "sources": {},
                    "status": "MISSING_SOURCE" if missing else "COMPLETE",
                    "ticker": ticker,
                }
            )
            if not missing:
                for suffix in ("json", "npz"):
                    relative = fr"raw_cache\{ticker}\{value}.{suffix}"
                    path = spot.Q3_CONTEXT_ROOT / "raw_cache" / ticker / f"{value}.{suffix}"
                    raw_files[relative] = _pin(path, index)
                    index += 1

    documents = {
        "h1_inventory": {
            "schema": "weekly_context_1030_inventory_v1",
            "state_i": 60,
            "counts": {"full": 2595, "identities": 2625, "missing": 6, "short": 24},
            "identities": h1_rows,
        },
        "h1_inventory_manifest": {
            "schema": "weekly_context_1030_inventory_manifest_v1",
            "inventory.json": {
                "bytes": 1_829_496,
                "sha256": spot.EXPECTED_AUTHORITY_PINS["h1_inventory"]["sha256"],
            },
        },
        "h1_manifest": {
            "schema": "weekly_context_1030_manifest_v1",
            "status": "COMPLETE_CAUSAL_CONTEXT_1030_NOT_JOINED_NOT_EVALUATED",
            "state_i": 60,
            "counts": {"full": 2595, "identities": 2625, "missing": 6, "short": 24},
            "npz_inputs": feature_inputs,
        },
        "q3_inventory": {
            "schema": "weekly_context_q3_1030_inventory_v1",
            "state_i": 60,
            "counts": {
                "available": 153,
                "identities": 165,
                "missing": 12,
                "sources": 330,
                "sources_missing": 12,
                "sources_present": 318,
            },
            "identities": q3_rows,
        },
        "q3_inventory_manifest": {
            "schema": "weekly_context_q3_1030_inventory_manifest_v1",
            "inventory.json": {
                "bytes": 1_489_911,
                "sha256": spot.EXPECTED_AUTHORITY_PINS["q3_inventory"]["sha256"],
            },
        },
        "q3_manifest": {
            "schema": "weekly_context_q3_1030_manifest_v1",
            "status": "COMPLETE_CAUSAL_CONTEXT_Q3_1030_NOT_JOINED_NOT_EVALUATED",
            "state_i": 60,
            "counts": {
                "available": 153,
                "identities": 165,
                "missing": 12,
                "state_valid_false": 0,
                "state_valid_true": 153,
            },
            "raw_cache_files": raw_files,
        },
    }
    pins = {key: dict(value) for key, value in spot.EXPECTED_AUTHORITY_PINS.items()}
    return documents, pins


def test_calendar_accepts_exact_dense_order_and_three_keys() -> None:
    rows = _calendar()
    assert spot._validate_calendar(rows) == rows


@pytest.mark.parametrize("mutation", ["extra", "duplicate", "reorder", "bad_close"])
def test_calendar_rejects_schema_identity_order_and_clock_drift(mutation: str) -> None:
    rows = _calendar()
    if mutation == "extra":
        rows[0] = {**rows[0], "session_kind": "FULL"}
    elif mutation == "duplicate":
        rows[1] = dict(rows[0])
    elif mutation == "reorder":
        rows[0], rows[1] = rows[1], rows[0]
    else:
        rows[0]["close_i"] = 211
    with pytest.raises(spot.SpotPathError):
        spot._validate_calendar(rows)


def test_authorities_cross_validate_without_reopening_top_documents() -> None:
    documents, pins = _authorities()
    h1, q3, raw = spot._validate_authorities(documents, pins)
    assert len(h1) == 2625
    assert len(q3) == 165
    assert len(raw) == 306
    assert {key for key, row in h1.items() if row["status"] != "COMPLETE"} == spot.H1_MISSING
    assert {key for key, row in q3.items() if row["status"] != "COMPLETE"} == spot.Q3_MISSING


def test_authority_pin_drift_is_fatal() -> None:
    documents, pins = _authorities()
    pins["q3_manifest"] = {**pins["q3_manifest"], "bytes": 1}
    with pytest.raises(spot.SpotPathError, match="authority bytes drift"):
        spot._validate_authorities(documents, pins)


def test_authority_missing_set_includes_nonweekly_july_tenth() -> None:
    assert ("QQQ", "20260710") in spot.Q3_MISSING
    assert ("SPY", "20260710") in spot.Q3_MISSING
    assert len(spot.H1_MISSING) == 6
    assert len(spot.Q3_MISSING) == 12


def test_h1_paths_are_derived_before_metadata_is_opened() -> None:
    feature = spot.LEVEL_ROOT / "session_clock_dataset_v1" / "references" / "QQQ" / "20230103" / "features.json"
    assert spot._expected_h1_paths("QQQ", "20230103", 390, feature) == (
        feature,
        spot.LEVEL_ROOT / "cache_v1" / "QQQ" / "20230103.json",
        spot.LEVEL_ROOT / "cache_v1" / "QQQ" / "20230103.npz",
    )
    short_feature = spot.LEVEL_ROOT / "session_clock_dataset_v1" / "short" / "SPY" / "20230703" / "features.json"
    _, short_metadata, short_npz = spot._expected_h1_paths("SPY", "20230703", 210, short_feature)
    assert short_metadata.name == "cache.json"
    assert short_npz.name == "cache.npz"


def test_h1_traversal_or_wrong_layout_is_rejected() -> None:
    expected = spot.LEVEL_ROOT / "session_clock_dataset_v1" / "references" / "QQQ" / "20230103" / "features.json"
    wrong = spot.LEVEL_ROOT / "session_clock_dataset_v1" / "references" / "QQQ" / "other" / "features.json"
    with pytest.raises(spot.SpotPathError, match="not nominal"):
        spot._expected_h1_paths("QQQ", "20230103", 390, wrong)
    with pytest.raises(spot.SpotPathError, match="traversal"):
        spot._validate_nominal_path(Path(str(expected.parent / ".." / "20230103" / "features.json")), expected, "fixture")


def test_feature_metadata_binds_cache_but_does_not_require_feature_array_open() -> None:
    npz = spot.LEVEL_ROOT / "cache_v1" / "QQQ" / "20230103.npz"
    inventory = {"features": {"sha256": "1" * 64}}
    document = {
        "version": "SESSION_CLOCK_FEATURES_V1",
        "ticker": "QQQ",
        "date": "20230103",
        "outcomes_read": False,
        "source_path": str(npz),
        "sha256": "1" * 64,
        "binding": {"source_sha256": "2" * 64, "source_metadata_sha256": "3" * 64},
    }
    assert spot._validate_feature_metadata(document, "QQQ", "20230103", npz, inventory) == ("2" * 64, "3" * 64)
    document["outcomes_read"] = True
    with pytest.raises(spot.SpotPathError, match="outcomes"):
        spot._validate_feature_metadata(document, "QQQ", "20230103", npz, inventory)


def test_cache_metadata_requires_only_three_member_schemas() -> None:
    pin = {"path": r"D:\fixture\cache.npz", "bytes": 11, "sha256": "a" * 64}
    metadata = {
        "version": "LEVEL_DAILY_CACHE_V1",
        "ticker": "SPXW",
        "date": "20240102",
        "timezone_convention": "America/New_York naive",
        "npz_bytes": 11,
        "sha256": "a" * 64,
        "array_schema": {
            "time_ns": {"shape": [391], "dtype": "int64"},
            "spot": {"shape": [391], "dtype": "float64"},
            "spot_valid": {"shape": [391], "dtype": "bool"},
            "forbidden_but_unread": {"shape": [1], "dtype": "float64"},
        },
    }
    spot._validate_cache_metadata(metadata, "SPXW", "20240102", 390, "LEVEL_DAILY_CACHE_V1", pin)
    metadata["array_schema"]["spot"]["dtype"] = "float32"
    with pytest.raises(spot.SpotPathError, match="array schema spot"):
        spot._validate_cache_metadata(metadata, "SPXW", "20240102", 390, "LEVEL_DAILY_CACHE_V1", pin)


class _TrackingArchive:
    files = ["time_ns", "spot", "spot_valid", "forbidden_fourth"]

    def __init__(self, values: dict[str, np.ndarray]) -> None:
        self.values = values
        self.accessed: list[str] = []
        self.closed = False

    def __enter__(self) -> "_TrackingArchive":
        return self

    def __exit__(self, *args: object) -> None:
        self.closed = True

    def __getitem__(self, key: str) -> np.ndarray:
        self.accessed.append(key)
        return self.values[key]


def _clock(value: str, n: int) -> np.ndarray:
    start = np.datetime64(value, "ns").astype(np.int64)
    return start + np.arange(n, dtype=np.int64) * 60_000_000_000


def test_loader_indexes_only_three_arrays_and_closes_before_return(monkeypatch: pytest.MonkeyPatch) -> None:
    archive = _TrackingArchive(
        {
            "time_ns": _clock("2023-01-03T09:30", 391),
            "spot": np.full(391, 100.0, dtype=np.float64),
            "spot_valid": np.ones(391, dtype=np.bool_),
        }
    )
    calls: list[tuple[Path, bool]] = []

    def fake_load(path: Path, allow_pickle: bool) -> _TrackingArchive:
        calls.append((path, allow_pickle))
        return archive

    monkeypatch.setattr(np, "load", fake_load)
    time_ns, values, valid = spot._load_spot_triplet(np, Path("fixture.npz"), "20230103", 391)
    assert calls == [(Path("fixture.npz"), False)]
    assert archive.accessed == ["time_ns", "spot", "spot_valid"]
    assert archive.closed
    assert str(np.datetime64(int(time_ns[60]), "ns")) == "2023-01-03T10:30:00.000000000"
    assert values.shape == valid.shape == (391,)


def test_false_mask_preserves_nan_and_inf_but_true_requires_positive_finite(monkeypatch: pytest.MonkeyPatch) -> None:
    values = np.full(211, 100.0, dtype=np.float64)
    values[1] = np.nan
    values[2] = np.inf
    mask = np.ones(211, dtype=np.bool_)
    mask[[1, 2]] = False
    archive = _TrackingArchive(
        {"time_ns": _clock("2023-07-03T09:30", 211), "spot": values, "spot_valid": mask}
    )
    monkeypatch.setattr(np, "load", lambda *_args, **_kwargs: archive)
    _, loaded, loaded_mask = spot._load_spot_triplet(np, Path("fixture.npz"), "20230703", 211)
    assert np.isnan(loaded[1]) and np.isinf(loaded[2])
    assert not loaded_mask[1] and not loaded_mask[2]

    bad = _TrackingArchive(
        {"time_ns": _clock("2023-07-03T09:30", 211), "spot": values, "spot_valid": np.ones(211, dtype=np.bool_)}
    )
    monkeypatch.setattr(np, "load", lambda *_args, **_kwargs: bad)
    with pytest.raises(spot.SpotPathError, match="finite positive"):
        spot._load_spot_triplet(np, Path("fixture.npz"), "20230703", 211)


def test_loader_rejects_clock_dtype_shape_and_minute_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    time_ns = _clock("2023-01-03T09:30", 391)
    time_ns[60] += 1
    archive = _TrackingArchive(
        {"time_ns": time_ns, "spot": np.ones(391, dtype=np.float64), "spot_valid": np.ones(391, dtype=np.bool_)}
    )
    monkeypatch.setattr(np, "load", lambda *_args, **_kwargs: archive)
    with pytest.raises(spot.SpotPathError, match="clock differs"):
        spot._load_spot_triplet(np, Path("fixture.npz"), "20230103", 391)


def _unit(*, missing: bool, values: np.ndarray | None = None) -> dict[str, object]:
    n = 2
    return {
        "ticker": "SPY",
        "ticker_ordinal": 0,
        "date": "20230103",
        "session_kind": "FULL",
        "close_i": n - 1,
        "cache_status": "MISSING" if missing else "AVAILABLE",
        "missing_reason": "MISSING_SOURCE" if missing else None,
        "authority": "H1",
        "feature_metadata_path": None if missing else r"D:\fixture\features.json",
        "feature_metadata_sha256": None if missing else "1" * 64,
        "cache_metadata_path": None if missing else r"D:\fixture\cache.json",
        "cache_metadata_sha256": None if missing else "2" * 64,
        "npz_path": None if missing else r"D:\fixture\cache.npz",
        "npz_sha256": None if missing else "3" * 64,
        "cache_version": None if missing else "LEVEL_DAILY_CACHE_V1",
        "time_ns": _clock("2023-01-03T09:30", n),
        "spot": None if missing else values,
        "spot_valid": np.zeros(n, dtype=np.bool_),
    }


def test_parquet_preserves_available_nan_inf_as_nonnull_and_missing_as_null(tmp_path: Path) -> None:
    available = _unit(missing=False, values=np.array([np.nan, np.inf], dtype=np.float64))
    missing = _unit(missing=True)
    missing["ticker"] = "QQQ"
    missing["ticker_ordinal"] = 1
    path = tmp_path / "spot_paths.parquet"
    spot._write_spot_parquet(path, [available, missing], np, pa, pq)
    table = pq.read_table(path)
    values = table.column("spot").combine_chunks()
    assert values.null_count == 2
    assert np.isnan(values[0].as_py())
    assert np.isinf(values[1].as_py())
    metadata = pq.read_metadata(path)
    assert metadata.num_row_groups == 2
    assert metadata.num_rows == 4


def test_parquet_schema_is_exact_and_fixed() -> None:
    schema = spot._parquet_schema(pa, "2.3.5", "23.0.1")
    assert schema.names == [
        "ticker", "ticker_ordinal", "date", "session_kind", "cache_status",
        "minute_i", "time_ns", "spot", "spot_valid", "missing_reason",
        "authority", "feature_metadata_path", "feature_metadata_sha256",
        "cache_metadata_path", "cache_metadata_sha256", "cache_npz_path",
        "cache_npz_sha256", "cache_version",
    ]
    assert schema.field("spot").nullable
    assert not schema.field("spot_valid").nullable


def test_invalid_ranges_are_inclusive_maximal_and_missing_is_dense() -> None:
    assert spot._ranges([False, True, True, False, True]) == [
        {"start_i": 1, "end_i": 2},
        {"start_i": 4, "end_i": 4},
    ]
    assert spot._ranges([True] * 391) == [{"start_i": 0, "end_i": 390}]
    assert spot._ranges([False] * 211) == []


def test_jsonl_is_compact_sorted_utf8_with_final_lf(tmp_path: Path) -> None:
    path = tmp_path / "rows.jsonl"
    spot._write_jsonl(path, [{"z": 1, "a": "á"}])
    assert path.read_bytes() == b'{"a":"\xc3\xa1","z":1}\n'


def test_source_contains_no_builder_import_and_only_three_archive_indexes() -> None:
    source_path = Path(spot.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not any("build_weekly_zone_event_value_paths" in value for value in imports)
    archive_keys = [
        node.slice.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id == "archive"
        and isinstance(node.slice, ast.Constant)
        and isinstance(node.slice.value, str)
    ]
    assert sorted(archive_keys) == ["spot", "spot_valid", "time_ns"]


def test_structural_counts_reconcile_contract() -> None:
    assert 2748 * 391 + 24 * 211 == 1_079_532
    assert 18 * 391 == 7_038
    assert 1_079_532 + 7_038 == 1_086_570
    assert 2619 * 3 + 153 * 2 == 8163


def test_final_counts_require_all_h1_full_and_short_available() -> None:
    counts = {
        "identities": 2790,
        "available": 2772,
        "missing": 18,
        "full": 2766,
        "short": 24,
        "available_rows": 1_079_532,
        "missing_rows": 7_038,
        "path_rows": 1_086_570,
        "valid_rows": 1_000_000,
        "invalid_rows": 86_570,
        "h1_available": 2619,
        "h1_missing": 6,
        "q3_available": 153,
        "q3_missing": 12,
        "admitted_inputs": 8163,
    }
    spot._validate_final_counts(counts)
    assert counts["available"] == counts["h1_available"] + counts["q3_available"]
    assert counts["full"] + counts["short"] == counts["identities"]
    assert counts["missing"] == counts["h1_missing"] + counts["q3_missing"]

    counts["h1_available"] = 2595
    with pytest.raises(spot.SpotPathError, match="h1_available"):
        spot._validate_final_counts(counts)


def _install_integral_mocks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    fail_output: str | None = None,
) -> tuple[list[dict[str, object]], dict[str, object], list[dict[str, object]]]:
    calendar = [
        {"ticker": "SPY", "date": "20230103", "close_i": 390},
        {"ticker": "QQQ", "date": "20260401", "close_i": 390},
        {"ticker": "SPXW", "date": "20260702", "close_i": 390},
    ]
    feature_path = (
        spot.LEVEL_ROOT / "session_clock_dataset_v1" / "references" / "SPY" / "20230103" / "features.json"
    )
    feature_npz = spot.LEVEL_ROOT / "features_v1" / "SPY" / "20230103" / "features.npz"
    h1_cache_json = spot.LEVEL_ROOT / "cache_v1" / "SPY" / "20230103.json"
    h1_cache_npz = spot.LEVEL_ROOT / "cache_v1" / "SPY" / "20230103.npz"
    q3_cache_json, q3_cache_npz = spot._expected_q3_paths("SPXW", "20260702")
    h1 = {
        ("SPY", "20230103"): {
            "ticker": "SPY",
            "date": "20230103",
            "close_i": 390,
            "status": "COMPLETE",
            "features": {"path": str(feature_npz), "bytes": 1, "sha256": "9" * 64},
            "features_metadata": {"path": str(feature_path), "bytes": 11, "sha256": "a" * 64},
        },
        ("QQQ", "20260401"): {
            "ticker": "QQQ",
            "date": "20260401",
            "close_i": 390,
            "status": "MISSING_SOURCE",
            "features": None,
            "features_metadata": None,
        },
    }
    q3 = {
        ("SPXW", "20260702"): {
            "ticker": "SPXW",
            "date": "20260702",
            "close_i": 390,
            "status": "COMPLETE",
        }
    }
    q3_pins = {
        spot._canonical_key(q3_cache_json): {
            "path": str(q3_cache_json), "bytes": 44, "sha256": "d" * 64,
        },
        spot._canonical_key(q3_cache_npz): {
            "path": str(q3_cache_npz), "bytes": 55, "sha256": "e" * 64,
        },
    }
    monkeypatch.setattr(spot, "_validate_calendar", lambda _rows: calendar)
    monkeypatch.setattr(spot, "_validate_authorities", lambda _docs, _pins: (h1, q3, q3_pins))
    monkeypatch.setattr(spot, "_validate_final_counts", lambda _counts: None)

    events: list[dict[str, object]] = []
    active = {"value": False}

    @contextmanager
    def unit_context(kind: str, identity: str, paths: list[str]):
        assert not active["value"]
        active["value"] = True
        details: dict[str, object] = {}
        event: dict[str, object] = {
            "kind": kind,
            "identity": identity,
            "paths": list(paths),
            "details": details,
            "status": "STARTED",
        }
        events.append(event)
        try:
            yield details
        except BaseException:
            event["status"] = "ERROR"
            raise
        else:
            event["status"] = "COMPLETED"
        finally:
            active["value"] = False

    opened: list[str] = []
    fake_pins = {
        spot._canonical_key(feature_path): {"path": str(feature_path), "bytes": 11, "sha256": "a" * 64},
        spot._canonical_key(h1_cache_json): {"path": str(h1_cache_json), "bytes": 22, "sha256": "b" * 64},
        spot._canonical_key(h1_cache_npz): {"path": str(h1_cache_npz), "bytes": 33, "sha256": "c" * 64},
        spot._canonical_key(q3_cache_json): q3_pins[spot._canonical_key(q3_cache_json)],
        spot._canonical_key(q3_cache_npz): q3_pins[spot._canonical_key(q3_cache_npz)],
    }

    def fake_before(path: Path, expected_bytes: int | None, expected_sha: str | None, _seen: object):
        assert active["value"], "open occurred before unit-context STARTED"
        opened.append(str(path))
        pin = dict(fake_pins[spot._canonical_key(path)])
        if expected_bytes is not None:
            assert pin["bytes"] == expected_bytes
        if expected_sha is not None:
            assert pin["sha256"] == expected_sha
        stat_value = {"exists": True, "bytes": pin["bytes"], "mtime_ns": 1, "physical_id": [1, len(opened)]}
        return stat_value, pin

    def fake_after(path: Path, before_stat: object, before_pin: object, _seen: object):
        assert active["value"]
        return before_stat, before_pin

    def fake_json(path: Path) -> dict[str, object]:
        assert active["value"]
        if path == feature_path:
            return {
                "version": "SESSION_CLOCK_FEATURES_V1",
                "ticker": "SPY",
                "date": "20230103",
                "outcomes_read": False,
                "source_path": str(h1_cache_npz),
                "sha256": "9" * 64,
                "binding": {"source_sha256": "c" * 64, "source_metadata_sha256": "b" * 64},
            }
        ticker, value, pin, version = (
            ("SPY", "20230103", fake_pins[spot._canonical_key(h1_cache_npz)], "LEVEL_DAILY_CACHE_V1")
            if path == h1_cache_json
            else ("SPXW", "20260702", fake_pins[spot._canonical_key(q3_cache_npz)], "LEVEL_DAILY_CACHE_V1")
        )
        return {
            "version": version,
            "ticker": ticker,
            "date": value,
            "timezone_convention": "America/New_York naive",
            "npz_bytes": pin["bytes"],
            "sha256": pin["sha256"],
            "array_schema": {
                "time_ns": {"shape": [391], "dtype": "int64"},
                "spot": {"shape": [391], "dtype": "float64"},
                "spot_valid": {"shape": [391], "dtype": "bool"},
            },
        }

    def fake_load(_np: object, path: Path, value: str, n: int):
        assert active["value"]
        opened.append(str(path) + "#three-arrays-only")
        return (
            _clock(f"{value[:4]}-{value[4:6]}-{value[6:]}T09:30", n),
            np.full(n, 100.0, dtype=np.float64),
            np.ones(n, dtype=np.bool_),
        )

    captured: dict[str, object] = {"jsonl": [], "parquet": None, "opened": opened}

    def fake_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
        assert active["value"] and events[-1]["kind"] == "WRITE_OUTPUTS"
        if fail_output == path.name:
            raise RuntimeError("synthetic output failure")
        captured["jsonl"].append((path.name, rows))

    def fake_parquet(path: Path, units: list[dict[str, object]], *_args: object) -> None:
        assert active["value"] and events[-1]["kind"] == "WRITE_OUTPUTS"
        if fail_output == path.name:
            raise RuntimeError("synthetic output failure")
        captured["parquet"] = units

    def fake_output_pin(path: Path) -> dict[str, object]:
        assert active["value"]
        return {"path": str(path), "bytes": 1, "sha256": "f" * 64}

    monkeypatch.setattr(spot, "_pin_before", fake_before)
    monkeypatch.setattr(spot, "_pin_after", fake_after)
    monkeypatch.setattr(spot, "_json_file", fake_json)
    monkeypatch.setattr(spot, "_load_spot_triplet", fake_load)
    monkeypatch.setattr(spot, "_write_jsonl", fake_jsonl)
    monkeypatch.setattr(spot, "_write_spot_parquet", fake_parquet)
    monkeypatch.setattr(spot, "_output_pin", fake_output_pin)
    result = {
        "calendar": calendar,
        "documents": {},
        "pins": {},
        "unit_context": unit_context,
        "output_dir": tmp_path,
    }
    return events, captured, [result]


def test_extract_integral_context_order_paths_details_outputs_and_null_schemas(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events, captured, args_box = _install_integral_mocks(monkeypatch, tmp_path)
    args = args_box[0]
    result = spot.extract_spot_paths(
        args["calendar"], args["output_dir"], args["documents"], args["pins"], args["unit_context"]
    )
    assert [(event["kind"], event["identity"]) for event in events] == [
        ("CACHE_SPOT_PATH", "SPY:20230103"),
        ("CACHE_SPOT_PATH", "QQQ:20260401"),
        ("CACHE_SPOT_PATH", "SPXW:20260702"),
        ("WRITE_OUTPUTS", "cache_admission.jsonl"),
        ("WRITE_OUTPUTS", "spot_paths.parquet"),
        ("WRITE_OUTPUTS", "spot_coverage.jsonl"),
    ]
    assert [len(events[index]["paths"]) for index in range(3)] == [3, 0, 2]
    assert events[0]["details"]["substeps"] == ["ADMIT_SPOT_METADATA", "LOAD_SPOT_TRIPLETS"]
    assert events[1]["details"]["substeps"] == ["DECLARED_MISSING"]
    assert events[2]["details"]["substeps"] == ["ADMIT_SPOT_METADATA", "LOAD_SPOT_TRIPLETS"]
    assert events[1]["details"]["counts"] == {"expected": 391, "valid": 0, "invalid": 391}
    assert events[1]["details"]["pins_pre"] == events[1]["details"]["pins_post"] == {}
    assert len(events[0]["details"]["pins_pre"]) == len(events[0]["details"]["pins_post"]) == 3
    assert len(events[2]["details"]["pins_pre"]) == len(events[2]["details"]["pins_post"]) == 2
    assert all(event["status"] == "COMPLETED" for event in events)
    assert [events[index]["details"]["rows"] for index in range(3, 6)] == [2790, 1_086_570, 2790]
    assert set(result) == {"outputs", "counts", "admitted_inputs"}
    assert set(result["outputs"]) == set(spot.OUTPUT_NAMES)
    assert len(result["admitted_inputs"]) == 5
    assert not any("features.npz" in path for path in result["admitted_inputs"])
    assert not any("features.npz" in path for path in captured["opened"])

    admission = dict(captured["jsonl"])["cache_admission.jsonl"]
    coverage = dict(captured["jsonl"])["spot_coverage.jsonl"]
    assert len(admission) == len(coverage) == 3
    q3_row = admission[2]
    assert q3_row["feature_metadata_path"] is None
    assert q3_row["stats"]["feature_metadata"] is None
    missing = admission[1]
    assert missing["missing_reason"] == "MISSING_SOURCE"
    assert all(
        missing[name] is None
        for name in (
            "feature_metadata_path", "feature_metadata_bytes", "feature_metadata_sha256",
            "cache_metadata_path", "cache_metadata_bytes", "cache_metadata_sha256",
            "npz_path", "npz_bytes", "npz_sha256", "cache_version",
            "binding_source_sha256", "binding_source_metadata_sha256", "stats",
        )
    )
    missing_coverage = coverage[1]
    assert missing_coverage["valid_count"] == 0
    assert missing_coverage["invalid_count"] == 391
    assert missing_coverage["invalid_ranges"] == [{"start_i": 0, "end_i": 390}]
    assert missing_coverage["first_valid_i"] is None and missing_coverage["last_valid_i"] is None
    assert missing_coverage["metadata_path"] is None and missing_coverage["npz_path"] is None
    assert captured["parquet"][1]["spot"] is None


def test_extract_output_failure_records_error_and_does_not_enter_later_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events, _captured, args_box = _install_integral_mocks(
        monkeypatch, tmp_path, fail_output="spot_paths.parquet"
    )
    args = args_box[0]
    with pytest.raises(RuntimeError, match="synthetic output failure"):
        spot.extract_spot_paths(
            args["calendar"], args["output_dir"], args["documents"], args["pins"], args["unit_context"]
        )
    assert [(event["kind"], event["identity"], event["status"]) for event in events[-2:]] == [
        ("WRITE_OUTPUTS", "cache_admission.jsonl", "COMPLETED"),
        ("WRITE_OUTPUTS", "spot_paths.parquet", "ERROR"),
    ]
    assert not any(event["identity"] == "spot_coverage.jsonl" for event in events)


def test_pin_after_rejects_stat_or_hash_drift(tmp_path: Path) -> None:
    path = tmp_path / "input.bin"
    path.write_bytes(b"before")
    seen: dict[tuple[int, int], str] = {}
    before_stat, before_pin = spot._pin_before(path, 6, None, seen)
    path.write_bytes(b"after!")
    with pytest.raises(spot.SpotPathError, match="changed during unit"):
        spot._pin_after(path, before_stat, before_pin, seen)


def test_lstat_rejects_hardlink_and_reparse_leaf(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    alias = tmp_path / "alias.bin"
    source.write_bytes(b"x")
    os.link(source, alias)
    with pytest.raises(spot.SpotPathError, match="hardlinked"):
        spot._lstat_regular(source, {})

    regular = tmp_path / "regular.bin"
    regular.write_bytes(b"x")
    original_lstat = Path.lstat

    class ReparseStat:
        def __init__(self, value: os.stat_result) -> None:
            self._value = value
            self.st_mode = value.st_mode
            self.st_nlink = value.st_nlink
            self.st_dev = value.st_dev
            self.st_ino = value.st_ino
            self.st_size = value.st_size
            self.st_mtime_ns = value.st_mtime_ns
            self.st_file_attributes = spot.REPARSE_FLAG

    def fake_lstat(path: Path) -> object:
        value = original_lstat(path)
        return ReparseStat(value) if path == regular else value

    monkeypatch.setattr(Path, "lstat", fake_lstat)
    with pytest.raises(spot.SpotPathError, match="reparse file"):
        spot._lstat_regular(regular, {})


def test_lstat_rejects_symlink_when_supported(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    link = tmp_path / "link.bin"
    source.write_bytes(b"x")
    try:
        link.symlink_to(source)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    with pytest.raises(spot.SpotPathError, match="symlink|regular"):
        spot._lstat_regular(link, {})


def test_lstat_global_registry_rejects_distinct_path_with_same_physical_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    first = tmp_path / "first.bin"
    second = tmp_path / "second.bin"
    first.write_bytes(b"a")
    second.write_bytes(b"b")
    first_stat = first.lstat()
    original_lstat = Path.lstat

    class AliasStat:
        def __init__(self, value: os.stat_result) -> None:
            self.st_mode = value.st_mode
            self.st_nlink = 1
            self.st_dev = first_stat.st_dev
            self.st_ino = first_stat.st_ino
            self.st_size = value.st_size
            self.st_mtime_ns = value.st_mtime_ns
            self.st_file_attributes = 0

    def fake_lstat(path: Path) -> object:
        value = original_lstat(path)
        return AliasStat(value) if path == second else value

    seen: dict[tuple[int, int], str] = {}
    spot._lstat_regular(first, seen)
    monkeypatch.setattr(Path, "lstat", fake_lstat)
    with pytest.raises(spot.SpotPathError, match="physical alias"):
        spot._lstat_regular(second, seen)

