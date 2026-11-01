from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import audit_weekly_context_q3 as auditor


def state_arrays(*, valid: bool = True) -> dict[str, np.ndarray]:
    arrays = {
        name: np.zeros(shape, dtype=dtype)
        for name, (shape, dtype) in auditor.ARRAY_SCHEMA.items()
    }
    arrays["state_i"][:] = auditor.STATE_I
    arrays["state_valid"][:] = valid
    arrays["bar_mask"][0, 0] = True
    arrays["token_mask"][0, 0] = True
    arrays["bar_end_i"][:] = -1
    arrays["bar_end_i"][0, 0] = 4
    arrays["map_mask"][0, 0, 0] = np.float32(0.6)
    return arrays


def test_state_schema_fractional_mask_causality_and_exact_comparison() -> None:
    arrays = state_arrays()
    auditor.validate_state_arrays(arrays, "fixture")
    assert arrays["map_mask"].dtype == np.float32
    assert 0 < arrays["map_mask"][0, 0, 0] < 1
    auditor.compare_arrays(arrays, copy.deepcopy(arrays), "fixture")
    changed = copy.deepcopy(arrays)
    changed["base"][0, 0] = np.float32(1e-7)
    with pytest.raises(auditor.Q3AuditError, match="array mismatch"):
        auditor.compare_arrays(arrays, changed, "fixture")
    changed = copy.deepcopy(arrays)
    changed["bar_end_i"][0, 0] = auditor.STATE_I
    with pytest.raises(auditor.Q3AuditError, match="causal bar ends"):
        auditor.validate_state_arrays(changed, "fixture")


def context_row(arrays: dict[str, np.ndarray] | None) -> dict:
    row = {
        "ticker": "SPY",
        "date": "20260702",
        "source_status": "MISSING_SOURCE" if arrays is None else "COMPLETE",
        "close_i": 390,
        "state_i": 60,
        "status": "CONTEXT_MISSING_SOURCE" if arrays is None else "CONTEXT_AVAILABLE",
        "state_valid": None if arrays is None else bool(arrays["state_valid"][0]),
        "context_81": None if arrays is None else arrays["base"][0].tolist(),
        "token_mask_20": None if arrays is None else arrays["token_mask"][0].tolist(),
        "bar_mask_20": None if arrays is None else arrays["bar_mask"][0].tolist(),
        "map_mask_20x5": None if arrays is None else arrays["map_mask"][0].tolist(),
        "bar_end_i_20": None if arrays is None else arrays["bar_end_i"][0].tolist(),
        "sources": {},
    }
    return row


def test_context_projection_retains_invalid_and_missing_separately() -> None:
    invalid = state_arrays(valid=False)
    auditor.validate_context_row(context_row(invalid), invalid)
    auditor.validate_context_row(context_row(None), None)
    broken = context_row(invalid)
    broken["map_mask_20x5"][0][0] = 1.0
    with pytest.raises(auditor.Q3AuditError, match="context projection"):
        auditor.validate_context_row(broken, invalid)


def artificial_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    greek_rows = []
    for minute in range(71):
        timestamp = pd.Timestamp("2026-07-02 09:30") + pd.Timedelta(minutes=minute)
        spot = 100.0 + minute / 100
        for strike, right, delta in ((100.0, "C", 0.5), (101.0, "P", -0.5)):
            greek_rows.append(
                {
                    "symbol": "SPY",
                    "expiration": "2026-07-02",
                    "trade_date": "2026-07-02",
                    "strike": strike,
                    "right": right,
                    "timestamp": timestamp.isoformat(),
                    "underlying_timestamp": timestamp.isoformat(),
                    "underlying_price": spot,
                    "bid": 1.0,
                    "ask": 1.1,
                    "delta": delta,
                    "implied_vol": 0.2,
                    "vega": 0.05,
                    "theta": -0.03,
                }
            )
    oi_rows = [
        {
            "symbol": "SPY",
            "expiration": "2026-07-02",
            "trade_date": "2026-07-02",
            "strike": strike,
            "right": right,
            "timestamp": "2026-07-02T09:32:00",
            "open_interest": value,
        }
        for strike, right, value in ((100.0, "C", 10), (101.0, "P", 20))
    ]
    return pd.DataFrame(greek_rows), pd.DataFrame(oi_rows)


def assert_arrays_equal(
    left: dict[str, np.ndarray], right: dict[str, np.ndarray]
) -> None:
    assert set(left) == set(right)
    for name in left:
        assert np.array_equal(left[name], right[name]), name


def test_frozen_normalize_and_state60_are_causal_with_valid_and_invalid_ib() -> None:
    build_cache, features, _engine, imports, previous = auditor.import_frozen_modules()
    try:
        greek, oi = artificial_frames()
        raw, metadata = build_cache.normalize_day(greek, oi, "SPY", "20260702")
        assert metadata["clock_basis"] == "NATIVE_STORED_TIMESTAMP"
        assert metadata["oi_clock_basis"] == "NATIVE_STORED_TIMESTAMP"
        encoded = features.encode_states(
            features.build_day_feature_cache(raw), indices=[60]
        )
        auditor.validate_state_arrays(encoded, "frozen artificial")
        assert bool(encoded["state_valid"][0])
        assert np.any((encoded["map_mask"] > 0) & (encoded["map_mask"] < 1))

        future = {name: value.copy() for name, value in raw.items()}
        future["spot"][61:] = 10000 + np.arange(330)
        for name in ("bid", "ask", "delta", "iv", "vega", "theta"):
            future[name][61:] = 999.0
        future["oi_contract_idx"] = np.append(future["oi_contract_idx"], np.int32(0))
        future["oi_value"] = np.append(future["oi_value"], np.int64(10**9))
        future["oi_available_ns"] = np.append(
            future["oi_available_ns"], raw["time_ns"][61]
        )
        future["oi_valid"] = np.append(future["oi_valid"], True)
        future_encoded = features.encode_states(
            features.build_day_feature_cache(future), indices=[60]
        )
        assert_arrays_equal(encoded, future_encoded)

        invalid = {name: value.copy() for name, value in raw.items()}
        invalid["spot_valid"][:4] = False
        invalid_encoded = features.encode_states(
            features.build_day_feature_cache(invalid), indices=[60]
        )
        assert not bool(invalid_encoded["state_valid"][0])
        assert np.isfinite(invalid_encoded["base"]).all()
        assert set(imports["imports"]) == {"build_cache", "features", "level_engine"}
    finally:
        auditor.restore_frozen_modules(previous)


def test_file_pin_detects_mutation(tmp_path: Path) -> None:
    path = tmp_path / "source.bin"
    path.write_bytes(b"first")
    frozen = auditor.pin(path)
    auditor.verify_pin(path, frozen, "fixture")
    path.write_bytes(b"other")
    with pytest.raises(auditor.Q3AuditError, match="pin mismatch"):
        auditor.verify_pin(path, frozen, "fixture")


def test_npz_rejects_schema_and_fractional_mask_coercion(tmp_path: Path) -> None:
    path = tmp_path / "state.npz"
    with path.open("xb") as handle:
        np.savez_compressed(handle, **state_arrays())
    frozen = auditor.pin(path)
    loaded = auditor.load_npz(path, frozen, "fixture state")
    assert loaded["map_mask"].dtype == np.float32
    broken = state_arrays()
    broken["map_mask"] = broken["map_mask"].astype(bool)
    other = tmp_path / "broken.npz"
    with other.open("xb") as handle:
        np.savez_compressed(handle, **broken)
    with pytest.raises(auditor.Q3AuditError, match="array schema"):
        auditor.load_npz(other, auditor.pin(other), "broken state")


def compact_pin(path: Path) -> dict:
    value = auditor.pin(path)
    return {"path": str(path), "bytes": value["bytes"], "sha256": value["sha256"]}


def raw_record(path: Path, kind: str) -> dict:
    value = auditor.pin(path)
    return {
        "ticker": "SPY",
        "date": "20260702",
        "kind": kind,
        "path": str(path),
        "exists": True,
        "bytes": value["bytes"],
        "mtime_ns": value["mtime_ns"],
        "sha256": value["sha256"],
        "rows": 1,
        "schema": [{"name": "timestamp", "type": "string", "nullable": False}],
        "clock_basis": "NATIVE_STORED_TIMESTAMP",
        "physical_id": f"fixture-{kind}",
    }


def test_available_identity_recomputes_exact_and_rejects_clock_or_source_mutation(
    tmp_path: Path,
) -> None:
    root = tmp_path / "producer"
    cache_path = root / "raw_cache" / "SPY" / "20260702.npz"
    state_path = root / "state60" / "SPY" / "20260702.npz"
    cache_path.parent.mkdir(parents=True)
    state_path.parent.mkdir(parents=True)
    cache_path.write_bytes(b"sealed synthetic cache")
    greek_path, oi_path = tmp_path / "greeks.parquet", tmp_path / "oi.parquet"
    greek_path.write_bytes(b"greek metadata-only fixture")
    oi_path.write_bytes(b"oi metadata-only fixture")
    greek, oi = raw_record(greek_path, "greeks"), raw_record(oi_path, "oi")
    cache_meta = {
        "ticker": "SPY",
        "date": "20260702",
        "producer_sha256": auditor.BUILD_CACHE_SHA256,
        "clock_basis": "NATIVE_STORED_TIMESTAMP",
        "oi_clock_basis": "NATIVE_STORED_TIMESTAMP",
        "source_hashes": {
            greek["path"]: {key: greek[key] for key in ("sha256", "bytes", "mtime_ns")},
            oi["path"]: {key: oi[key] for key in ("sha256", "bytes", "mtime_ns")},
        },
    }
    cache_meta_path = cache_path.with_suffix(".json")
    cache_meta_path.write_text(json.dumps(cache_meta), encoding="utf-8")
    arrays = state_arrays(valid=False)
    with state_path.open("xb") as handle:
        np.savez_compressed(handle, **arrays)
    state_pin = compact_pin(state_path)
    cache_pin = compact_pin(cache_path)
    cache_meta_pin = compact_pin(cache_meta_path)
    state_meta = {
        "version": "weekly_context_q3_state60_v1",
        "identity": {"ticker": "SPY", "date": "20260702", "state_i": 60},
        "sha256": state_pin["sha256"],
        "bytes": state_pin["bytes"],
        "raw_cache": cache_pin,
        "raw_metadata": cache_meta_pin,
        "dependencies": {
            "build_cache": auditor.BUILD_CACHE_SHA256,
            "features": auditor.FEATURES_SHA256,
            "level_engine": auditor.LEVEL_ENGINE_SHA256,
        },
        "array_schema": {
            name: {"shape": list(shape), "dtype": dtype}
            for name, (shape, dtype) in auditor.ARRAY_SCHEMA.items()
        },
        "state_valid": False,
        "outcomes_read": False,
    }
    state_meta_path = state_path.with_suffix(".json")
    state_meta_path.write_text(json.dumps(state_meta), encoding="utf-8")
    sources = {
        "greeks": greek,
        "oi": oi,
        "cache": cache_pin,
        "cache_metadata": cache_meta_pin,
        "state": state_pin,
        "state_metadata": compact_pin(state_meta_path),
    }
    identity = {
        "ticker": "SPY",
        "date": "20260702",
        "close_i": 390,
        "status": "COMPLETE",
        "sources": {"greeks": greek, "oi": oi},
    }
    row = context_row(arrays)
    row["sources"] = sources

    class Cache:
        @staticmethod
        def load_day_cache(_path: Path) -> dict:
            return {"fixture": np.asarray([1])}

    class Features:
        @staticmethod
        def build_day_feature_cache(raw: dict) -> dict:
            assert set(raw) == {"fixture"}
            return raw

        @staticmethod
        def encode_states(_cache: dict, indices: list[int]) -> dict:
            assert indices == [60]
            return copy.deepcopy(arrays)

    result = auditor.audit_identity(
        identity=identity,
        context_row=row,
        root=root,
        build_cache=Cache,
        features=Features,
    )
    assert result["status"] == "RECOMPUTED_EXACT" and not result["state_valid"]
    bad_clock = copy.deepcopy(cache_meta)
    bad_clock["oi_clock_basis"] = "ASSUMED_PRIOR_CLOSE_UNVERIFIED_RECEIPT"
    cache_meta_path.write_text(json.dumps(bad_clock), encoding="utf-8")
    changed = compact_pin(cache_meta_path)
    row["sources"]["cache_metadata"] = changed
    with pytest.raises(auditor.Q3AuditError, match="raw cache metadata binding"):
        auditor.audit_identity(
            identity=identity,
            context_row=row,
            root=root,
            build_cache=Cache,
            features=Features,
        )


def test_coverage_rejects_duplicate_identity() -> None:
    counts = {
        "identities": 165,
        "available": 153,
        "missing": 12,
        "state_valid_true": 100,
        "state_valid_false": 53,
    }
    flags = {
        "outcomes_read": False,
        "actions_read": False,
        "labels_read": False,
        "oracle_read": False,
        "models_fit": False,
        "development_seen": True,
        "promotion_approved": False,
    }
    duplicate = {
        "ticker": "SPY",
        "date": "20260702",
        "source_status": "COMPLETE",
        "status": "CONTEXT_AVAILABLE",
        "state_valid": True,
    }
    coverage = {
        "schema": "weekly_context_q3_1030_coverage_v1",
        "state_i": 60,
        "feature_names": [f"f{index}" for index in range(81)],
        "counts": counts,
        "rows": [duplicate] * 165,
        "flags": flags,
    }
    manifest = {
        "feature_names": coverage["feature_names"],
        "counts": counts,
        "flags": flags,
    }
    with pytest.raises(auditor.Q3AuditError, match="duplicate coverage"):
        auditor.validate_coverage(coverage, manifest)


def test_inventory_symlink_is_rejected_before_json_values(tmp_path: Path) -> None:
    root = tmp_path / "producer"
    root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    try:
        os.symlink(outside, root / "inventory.json")
    except OSError as exc:
        pytest.skip(f"symlink unavailable: {exc}")
    (root / "inventory_manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(auditor.Q3AuditError, match="link/reparse inventory"):
        auditor.validate_inventory_binding(
            root, root / "inventory.json", "0" * 64, "1" * 64
        )


def test_recomputed_state_valid_counts_must_reconcile() -> None:
    results = [
        {"status": "RECOMPUTED_EXACT", "state_valid": index < 100}
        for index in range(153)
    ] + [{"status": "MISSING_SOURCE"} for _ in range(12)]
    auditor.validate_result_counts(
        results, {"state_valid_true": 100, "state_valid_false": 53}
    )
    with pytest.raises(auditor.Q3AuditError, match="state-valid"):
        auditor.validate_result_counts(
            results, {"state_valid_true": 99, "state_valid_false": 54}
        )
