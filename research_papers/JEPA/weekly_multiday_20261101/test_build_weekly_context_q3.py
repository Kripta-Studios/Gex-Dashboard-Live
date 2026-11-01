from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("weekly_context_q3", HERE / "build_weekly_context_q3.py")
assert SPEC and SPEC.loader
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


@pytest.fixture(scope="module")
def frozen_modules():
    return builder.load_frozen_modules()[:2]


def synthetic_frames(
    *, minutes: int = 91, future_contract: bool = False,
    future_shift: float = 0.0, duplicate: bool = False,
    subminute: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    day = pd.Timestamp("2026-07-02")
    clocks = pd.date_range(day + pd.Timedelta(hours=9, minutes=30), periods=minutes, freq="min")
    rows = []
    for minute, clock in enumerate(clocks):
        shown = clock + (pd.Timedelta(seconds=30) if subminute else pd.Timedelta(0))
        spot = 100 + 0.02 * minute + (future_shift if minute > 60 else 0.0)
        for strike, right, delta in ((99.0, "CALL", 0.55), (101.0, "PUT", -0.45)):
            rows.append({
                "symbol": "SPY", "expiration": day, "trade_date": day,
                "strike": strike, "right": right, "timestamp": shown,
                "underlying_timestamp": shown, "underlying_price": spot,
                "bid": 1.0, "ask": 1.1, "delta": delta,
                "implied_vol": 0.2, "vega": 0.1, "theta": -0.01,
            })
        if future_contract and minute > 60:
            rows.append({
                "symbol": "SPY", "expiration": day, "trade_date": day,
                "strike": 110.0, "right": "CALL", "timestamp": shown,
                "underlying_timestamp": shown, "underlying_price": spot,
                "bid": 0.1, "ask": 0.2, "delta": 0.05,
                "implied_vol": 0.3, "vega": 0.02, "theta": -0.005,
            })
    greek = pd.DataFrame(rows)
    if duplicate:
        greek = pd.concat([greek, greek.iloc[[0]]], ignore_index=True)
    oi_rows = [
        {"symbol": "SPY", "expiration": day, "trade_date": day, "strike": 99.0, "right": "CALL", "timestamp": day + pd.Timedelta(hours=9, minutes=32), "open_interest": 1000},
        {"symbol": "SPY", "expiration": day, "trade_date": day, "strike": 101.0, "right": "PUT", "timestamp": day + pd.Timedelta(hours=9, minutes=32), "open_interest": 900},
    ]
    if future_contract:
        oi_rows.append({"symbol": "SPY", "expiration": day, "trade_date": day, "strike": 110.0, "right": "CALL", "timestamp": day + pd.Timedelta(hours=10, minutes=31), "open_interest": 50_000})
    return greek, pd.DataFrame(oi_rows)


def encoded_state(build_cache, features, **kwargs):
    greek, oi = synthetic_frames(**kwargs)
    raw, metadata = build_cache.normalize_day(greek, oi, "SPY", "20260702")
    assert metadata["clock_basis"] == metadata["oi_clock_basis"] == "NATIVE_STORED_TIMESTAMP"
    return features.encode_states(features.build_day_feature_cache(raw), indices=[60])


def test_state60_schema_fractional_mask_and_valid_invalid_ib(frozen_modules) -> None:
    build_cache, features = frozen_modules
    valid = encoded_state(build_cache, features)
    builder.validate_state(valid)
    assert bool(valid["state_valid"][0])
    assert np.any((valid["map_mask"] > 0) & (valid["map_mask"] < 1))
    invalid = encoded_state(build_cache, features, minutes=10)
    builder.validate_state(invalid)
    assert not bool(invalid["state_valid"][0])


def test_future_values_contracts_and_oi_do_not_change_state60(frozen_modules) -> None:
    build_cache, features = frozen_modules
    baseline = encoded_state(build_cache, features)
    changed = encoded_state(build_cache, features, future_contract=True, future_shift=500.0)
    for name in builder.ARRAY_SCHEMA:
        assert np.array_equal(baseline[name], changed[name])


def test_pre1030_change_is_detected(frozen_modules) -> None:
    build_cache, features = frozen_modules
    greek, oi = synthetic_frames()
    baseline, _ = build_cache.normalize_day(greek, oi, "SPY", "20260702")
    changed = greek.copy()
    changed.loc[changed["timestamp"] == pd.Timestamp("2026-07-02 10:00"), "underlying_price"] += 2.0
    altered, _ = build_cache.normalize_day(changed, oi, "SPY", "20260702")
    first = features.encode_states(features.build_day_feature_cache(baseline), indices=[60])
    second = features.encode_states(features.build_day_feature_cache(altered), indices=[60])
    assert not np.array_equal(first["base"], second["base"])


def test_duplicate_and_subminute_clocks_fail_closed(frozen_modules) -> None:
    build_cache, _features = frozen_modules
    greek, oi = synthetic_frames(duplicate=True)
    with pytest.raises(ValueError, match="duplicate"):
        build_cache.normalize_day(greek, oi, "SPY", "20260702")
    greek, oi = synthetic_frames(subminute=True)
    with pytest.raises(ValueError, match="No valid Greek"):
        build_cache.normalize_day(greek, oi, "SPY", "20260702")


def test_invalid_masks_and_noncausal_bar_end_rejected(frozen_modules) -> None:
    build_cache, features = frozen_modules
    arrays = encoded_state(build_cache, features)
    bad_mask = {name: value.copy() for name, value in arrays.items()}
    bad_mask["map_mask"][0, 0, 0] = 1.01
    with pytest.raises(builder.Q3ContextError, match="map mask"):
        builder.validate_state(bad_mask)
    bad_end = {name: value.copy() for name, value in arrays.items()}
    index = int(np.flatnonzero(bad_end["bar_mask"][0])[0])
    bad_end["bar_end_i"][0, index] = 60
    with pytest.raises(builder.Q3ContextError, match="bar_end"):
        builder.validate_state(bad_end)


def test_source_schema_native_clock_and_toctou(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(builder, "SOURCE_ROOT", tmp_path)
    source = tmp_path / "source.parquet"
    pq.write_table(pa.table({"timestamp": ["2026-07-02T09:30:00"], "x": [1]}), source)
    record = {"ticker": "SPY", "date": "20260702", "kind": "oi", **builder.inspect_source(source, ("timestamp", "x"), "fixture", tmp_path)}
    assert record["clock_basis"] == "NATIVE_STORED_TIMESTAMP" and record["rows"] == 1
    builder.verify_source(record, ("timestamp", "x"), tmp_path)
    pq.write_table(pa.table({"timestamp": ["2026-07-02T09:30:00"], "x": [2]}), source)
    with pytest.raises(builder.Q3ContextError, match="source changed"):
        builder.verify_source(record, ("timestamp", "x"), tmp_path)
    without_clock = tmp_path / "no_clock.parquet"
    pq.write_table(pa.table({"x": [1]}), without_clock)
    with pytest.raises(builder.Q3ContextError, match="native timestamp"):
        builder.inspect_source(without_clock, ("x",), "no-clock", tmp_path)


def test_generated_file_closing_pin_rejects_mutation(tmp_path: Path) -> None:
    generated = tmp_path / "state60" / "SPY" / "20260702.npz"
    generated.parent.mkdir(parents=True)
    generated.write_bytes(b"sealed")
    relative = str(generated.relative_to(tmp_path))
    records = {relative: {"path": str(generated.resolve()), **builder.pin(generated)}}
    builder.verify_generated_file_map(records, tmp_path, "state60")
    generated.write_bytes(b"mutated")
    with pytest.raises(builder.Q3ContextError, match="generated file changed"):
        builder.verify_generated_file_map(records, tmp_path, "state60")


def test_inventory_binding_rejects_link_guard_even_with_matching_bytes(tmp_path: Path, monkeypatch) -> None:
    inventory = tmp_path / "inventory.json"
    receipt = tmp_path / "inventory_manifest.json"
    inventory.write_text('{"schema":"fixture"}\n', encoding="utf-8")
    inventory_pin = builder.pin(inventory)
    receipt.write_text(
        '{"inventory.json":' + __import__("json").dumps(inventory_pin) + ',"schema":"weekly_context_q3_1030_inventory_manifest_v1"}\n',
        encoding="utf-8",
    )
    original = builder.is_link_or_reparse
    monkeypatch.setattr(builder, "is_link_or_reparse", lambda path: Path(path).name == "inventory.json" or original(path))
    with pytest.raises(builder.Q3ContextError, match="link/reparse inventory binding"):
        builder.validate_inventory_binding(tmp_path, inventory_pin["sha256"])


def test_frozen_module_guard_rejects_link_before_import(tmp_path: Path, monkeypatch) -> None:
    module = tmp_path / "frozen.py"
    module.write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.setattr(builder, "LEVEL", tmp_path)
    monkeypatch.setattr(builder, "is_link_or_reparse", lambda path: Path(path) == module)
    with pytest.raises(builder.Q3ContextError, match="link/reparse frozen module fixture"):
        builder.guarded_module_file(module, builder.sha256_file(module), "fixture")


def test_missing_row_is_retained_with_null_context() -> None:
    identity = {"ticker": "QQQ", "date": "20260701", "status": "MISSING_SOURCE"}
    sources = {"greeks": {"exists": False}, "oi": {"exists": True}, "cache": None, "cache_metadata": None, "state": None, "state_metadata": None}
    row = builder.context_row(identity, None, sources)
    assert row["status"] == "CONTEXT_MISSING_SOURCE" and row["state_valid"] is None
    assert all(row[name] is None for name in ("context_81", "token_mask_20", "bar_mask_20", "map_mask_20x5", "bar_end_i_20"))


def test_state_metadata_binds_identity_raw_pair_and_dependencies(tmp_path: Path) -> None:
    state, cache, cache_meta = tmp_path / "state.npz", tmp_path / "cache.npz", tmp_path / "cache.json"
    state.write_bytes(b"state")
    cache.write_bytes(b"cache")
    cache_meta.write_text("{}\n", encoding="utf-8")
    arrays = {name: np.zeros(shape, dtype=dtype) for name, (shape, dtype) in builder.ARRAY_SCHEMA.items()}
    metadata = builder.state_metadata(state, arrays, cache, cache_meta, "SPY", "20260702", {"features": "abc"})
    assert metadata["version"] == "weekly_context_q3_state60_v1"
    assert metadata["identity"] == {"ticker": "SPY", "date": "20260702", "state_i": 60}
    assert metadata["raw_cache"]["sha256"] == builder.sha256_file(cache)
    assert metadata["raw_metadata"]["sha256"] == builder.sha256_file(cache_meta)


def test_source_and_calendar_closures_are_exact() -> None:
    assert len(builder.DATES) == 55 and len(builder.MISSING_GREEKS) == 12
    assert len({(ticker, day, kind) for ticker in builder.TICKERS for day in builder.DATES for kind in builder.KINDS}) == 330
    source = (HERE / "build_weekly_context_q3.py").read_text(encoding="utf-8")
    execution = source.split("def execute_reviewed_extraction", 1)[1].split("def main", 1)[0]
    assert "action_features(" not in execution and "encode_actions(" not in execution
    assert "candidates.jsonl" not in source and "model.json" not in source
