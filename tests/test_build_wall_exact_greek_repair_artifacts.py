import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import neural.jepa.build_wall_exact_greek_repair_artifacts as repair_module
from neural.jepa.build_wall_exact_greek_repair_artifacts import (
    EVENT_COLUMNS,
    INDEX_COLUMNS,
    OUTPUT_STATUS,
    apply_repair_overlay,
    build_repair_artifacts,
    event_repair_keys_from_base,
    expected_repair_keys,
    load_repair_bundle,
    repair_key_hash,
    validate_sealed_sidecar,
)
from neural.jepa.build_wall_exact_greek_repair_sidecar import (
    DECISION_TIMES,
    OPTIONAL_RESPONSE_COLUMNS,
    PREDECLARATION,
    contract_key_hash,
)
from neural.jepa.build_wall_native_quote_sidecar import canonical_json_bytes, sha256_file
from neural.jepa.wall_state_features import add_wall_persistence, compute_wall_states
from neural.jepa.wall_surface_flow_environment import assert_runtime_lock
from neural.jepa.build_wall_exact_greek_repair_artifacts import ENVIRONMENT_LOCK


DAY = "20221230"


def _underlying(ticker: str, base: float) -> pd.DataFrame:
    timestamps = pd.date_range("2022-12-30 10:05:00", "2022-12-30 14:30:00", freq="1min")
    return pd.DataFrame(
        {
            "symbol": ticker,
            "date": DAY,
            "timestamp": timestamps,
            "open": base + np.arange(len(timestamps), dtype=float) * 0.01,
        }
    )


def _exact_frame(ticker: str, strike: float, right: str, underlying: pd.DataFrame) -> pd.DataFrame:
    timestamps = pd.DatetimeIndex([pd.Timestamp(f"2022-12-30 {time}") for time in DECISION_TIMES])
    spot = underlying.set_index("timestamp")["open"].reindex(timestamps).to_numpy(float)
    frame = pd.DataFrame(
        {
            "symbol": ticker,
            "expiration": DAY,
            "trade_date": DAY,
            "strike": float(strike),
            "right": right,
            "timestamp": timestamps,
            "underlying_timestamp": timestamps,
            "underlying_price": spot,
            "implied_vol": 0.20,
            "delta": 0.5 if right == "CALL" else -0.5,
            "theta": -0.01,
            "vega": 0.02,
            "rho": 0.001,
            "bid": 1.0,
            "ask": 1.05,
            "iv_error": 0.0,
            "epsilon": 0.0,
            "lambda": 1.0,
        }
    )
    return frame


def _write_synthetic_bundle(root: Path) -> dict[str, Path]:
    root.mkdir(parents=True)
    runtime = assert_runtime_lock(ENVIRONMENT_LOCK)
    sidecar_builder = Path("neural/jepa/build_wall_exact_greek_repair_sidecar.py")
    commit = "1" * 40
    jar_hash = "2" * 64
    manifest_rows = []
    session_data = {}
    contract_specs = {
        "QQQ": [(100.0, "CALL", 120), (99.0, "PUT", 100)],
        "SPY": [(200.0, "CALL", 150), (199.0, "PUT", 130)],
    }
    for ticker, specs in contract_specs.items():
        source_dir = root / "sources" / ticker
        source_dir.mkdir(parents=True)
        underlying = _underlying(ticker, 99.0 if ticker == "QQQ" else 199.0)
        underlying_path = source_dir / "underlying.parquet"
        underlying.to_parquet(underlying_path, index=False)
        exact_parts = [_exact_frame(ticker, strike, right, underlying) for strike, right, _oi in specs]
        greek = pd.concat(exact_parts, ignore_index=True)
        greek_path = source_dir / "greeks.parquet"
        greek.to_parquet(greek_path, index=False)
        oi = pd.DataFrame(
            [
                {
                    "symbol": ticker,
                    "expiration": DAY,
                    "strike": strike,
                    "right": right,
                    "open_interest": open_interest,
                }
                for strike, right, open_interest in specs
            ]
        )
        oi_path = source_dir / "oi.parquet"
        oi.to_parquet(oi_path, index=False)
        manifest_rows.append(
            {
                "ticker": ticker,
                "trade_date": DAY,
                "expiration": DAY,
                "dte_days": 0,
                "expiry_mode": "zero_dte",
                "has_greeks": True,
                "has_oi": True,
                "has_underlying": True,
                "greeks_path": str(greek_path),
                "oi_path": str(oi_path),
                "underlying_path": str(underlying_path),
            }
        )
        session_data[ticker] = (underlying, greek, oi, greek_path, oi_path, underlying_path)
    manifest_path = root / "canonical_manifest.csv"
    pd.DataFrame(manifest_rows).to_csv(manifest_path, index=False)
    manifest_hash = sha256_file(manifest_path)

    index_rows = []
    sidecar_root = root / "sidecar"
    for ticker, specs in contract_specs.items():
        underlying, greek, _oi, greek_path, oi_path, underlying_path = session_data[ticker]
        for strike, right, _open_interest in specs:
            exact = greek[
                np.isclose(greek["strike"], strike, rtol=0.0, atol=1e-9) & greek["right"].eq(right)
            ].copy().reset_index(drop=True)
            contract_dir = sidecar_root / ticker / DAY / f"{right[0]}_{strike:.6f}".replace(".", "p")
            contract_dir.mkdir(parents=True)
            raw_path = contract_dir / "first_order_response.json"
            raw_path.write_bytes(json.dumps({"synthetic_contract": [ticker, strike, right]}).encode("utf-8"))
            exact_path = contract_dir / "exact_greeks.parquet"
            exact.to_parquet(exact_path, index=False)
            contract_manifest_path = contract_dir / "manifest.json"
            contract_manifest = {
                "schema": "wall_exact_greek_repair_contract_v1r2",
                "outcome_free": True,
                "holdout_2026_used": False,
                "ticker": ticker,
                "trade_date": DAY,
                "expiration": DAY,
                "strike": strike,
                "right": right,
                "raw_response_sha256": sha256_file(raw_path),
                "exact_greeks_sha256": sha256_file(exact_path),
                "source_greeks_path": str(greek_path),
                "source_greeks_sha256": sha256_file(greek_path),
                "source_oi_path": str(oi_path),
                "source_oi_sha256": sha256_file(oi_path),
                "source_underlying_path": str(underlying_path),
                "source_underlying_sha256": sha256_file(underlying_path),
                "source_source_manifest_path": str(manifest_path),
                "source_source_manifest_sha256": manifest_hash,
                "terminal_jar_sha256": jar_hash,
                "builder_sha256": sha256_file(sidecar_builder),
                "predeclaration_sha256": sha256_file(PREDECLARATION),
                "runtime_lock_sha256": runtime["lock_sha256"],
                "runtime_environment_sha256": runtime["environment_sha256"],
                "git_commit": commit,
                "rows": len(exact),
                "columns": list(exact.columns),
            }
            contract_manifest_path.write_bytes(canonical_json_bytes(contract_manifest))
            index_rows.append(
                {
                    "ticker": ticker,
                    "trade_date": DAY,
                    "strike": strike,
                    "right": right,
                    "contract_dir": str(contract_dir),
                    "exact_greeks_path": str(exact_path),
                    "exact_greeks_sha256": sha256_file(exact_path),
                    "raw_response_path": str(raw_path),
                    "raw_response_sha256": sha256_file(raw_path),
                    "contract_manifest_path": str(contract_manifest_path),
                    "contract_manifest_sha256": sha256_file(contract_manifest_path),
                    "rows": len(exact),
                    "stored_bid_ask_exact": True,
                    "git_commit": commit,
                    "max_spot_difference_bps": 0.0,
                    "source_greeks_sha256": sha256_file(greek_path),
                    "source_oi_sha256": sha256_file(oi_path),
                    "source_underlying_sha256": sha256_file(underlying_path),
                    "terminal_jar_sha256": jar_hash,
                    "terminal_process_id": 1,
                    "java_executable_sha256": "3" * 64,
                }
            )
    index = pd.DataFrame(index_rows, columns=list(INDEX_COLUMNS)).sort_values(
        ["ticker", "trade_date", "strike", "right"], kind="stable"
    ).reset_index(drop=True)
    seal_dir = sidecar_root / "_seal"
    seal_dir.mkdir(parents=True)
    index_path = seal_dir / "exact_greek_index.csv"
    index.to_csv(index_path, index=False)
    counts = index.groupby("ticker").size().astype(int).to_dict()
    seal = {
        "schema": "wall_exact_greek_repair_seal_v1r2",
        "status": "PASS_EXACT_GREEK_REPAIR_CAPTURE",
        "outcome_free": True,
        "holdout_2026_used": False,
        "historical_provenance": "CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION",
        "git_commit": commit,
        "builder_sha256": sha256_file(sidecar_builder),
        "predeclaration_sha256": sha256_file(PREDECLARATION),
        "source_manifest_sha256": manifest_hash,
        "contracts": len(index),
        "contracts_by_ticker": counts,
        "contract_key_sha256": contract_key_hash(index),
        "exact_rows": len(index) * 48,
        "timestamps_per_contract": 48,
        "decision_times": list(DECISION_TIMES),
        "index_sha256": sha256_file(index_path),
        "terminal_jar_sha256": jar_hash,
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment_sha256": runtime["environment_sha256"],
    }
    seal_path = seal_dir / "manifest.json"
    seal_path.write_bytes(canonical_json_bytes(seal))

    wall_frames = []
    event_frames = []
    for ticker, (_underlying_frame, greek, oi, _greek_path, _oi_path, _underlying_path) in session_data.items():
        chain = greek.merge(oi[["strike", "right", "open_interest"]], on=["strike", "right"], validate="many_to_one")
        states = compute_wall_states(
            chain.rename(columns={"timestamp": "dt"})[
                ["dt", "strike", "right", "underlying_price", "implied_vol", "open_interest"]
            ]
        )
        states.insert(0, "ticker", ticker)
        states.insert(1, "trade_date", DAY)
        wall_frames.append(add_wall_persistence(states))
        timestamps = pd.DatetimeIndex(pd.to_datetime(greek["timestamp"].drop_duplicates().sort_values()))
        lookup = _underlying_frame.set_index("timestamp")["open"]
        current = lookup.reindex(timestamps).to_numpy(float)
        controls = pd.DataFrame(
            {
                "ticker": ticker,
                "trade_date": DAY,
                "minute": timestamps.hour * 60 + timestamps.minute,
                "spot": current,
            }
        )
        for lag in (1, 5, 15, 30):
            prior = lookup.reindex(timestamps - pd.Timedelta(minutes=lag)).to_numpy(float)
            controls[f"ret_{lag}m_bps"] = (current / prior - 1.0) * 10_000.0
        event_frames.append(controls.iloc[:27].copy() if ticker == "QQQ" else controls.iloc[:20].copy())
    walls_path = root / "base_walls.parquet"
    pd.concat(wall_frames, ignore_index=True).to_parquet(walls_path, index=False)
    events_path = root / "base_events.parquet"
    pd.concat(event_frames, ignore_index=True)[list(EVENT_COLUMNS)].to_parquet(events_path, index=False)
    return {
        "index": index_path,
        "seal": seal_path,
        "manifest": manifest_path,
        "walls": walls_path,
        "events": events_path,
    }


def test_builds_exact_96_wall_and_control_rows_with_causal_returns(tmp_path):
    paths = _write_synthetic_bundle(tmp_path / "bundle")
    output = tmp_path / "repair"
    manifest = build_repair_artifacts(
        sidecar_index=paths["index"],
        sidecar_seal=paths["seal"],
        base_walls=paths["walls"],
        base_events=paths["events"],
        canonical_manifest=paths["manifest"],
        output_dir=output,
        enforce_frozen=False,
        require_committed=False,
    )
    assert manifest["status"] == OUTPUT_STATUS
    assert manifest["outcome_free"] is True and manifest["holdout_2026_used"] is False
    assert manifest["wall_repair_rows"] == 96
    assert manifest["event_control_repair_rows"] == 47
    assert manifest["event_target_rows_by_ticker"] == {"QQQ": 27, "SPY": 20}
    assert manifest["full_control_grid_rows"] == 96
    assert manifest["maximum_full_wall_control_spot_difference_bps"] == 0.0
    assert manifest["maximum_event_wall_control_spot_difference_bps"] == 0.0
    walls = pd.read_parquet(output / "wall_repair.parquet")
    controls = pd.read_parquet(output / "event_control_repair.parquet")
    assert walls[["ticker", "trade_date", "minute"]].equals(expected_repair_keys())
    expected_event_keys = pd.read_parquet(paths["events"], columns=["ticker", "trade_date", "minute"])
    pd.testing.assert_frame_equal(
        controls[["ticker", "trade_date", "minute"]], expected_event_keys, check_dtype=False
    )
    assert list(controls.columns) == list(EVENT_COLUMNS)
    assert np.isfinite(controls.select_dtypes(include=np.number).to_numpy()).all()
    assert json.loads((output / "manifest.json").read_text())["status"] == OUTPUT_STATUS
    loaded_walls, loaded_controls, loaded_manifest = load_repair_bundle(
        output / "manifest.json", enforce_frozen=False, require_committed=False
    )
    pd.testing.assert_frame_equal(loaded_walls, walls)
    pd.testing.assert_frame_equal(loaded_controls, controls)
    assert loaded_manifest["status"] == OUTPUT_STATUS
    with pytest.raises(FileExistsError, match="immutable"):
        build_repair_artifacts(
            sidecar_index=paths["index"], sidecar_seal=paths["seal"],
            base_walls=paths["walls"], base_events=paths["events"],
            canonical_manifest=paths["manifest"], output_dir=output,
            enforce_frozen=False, require_committed=False,
        )


def test_sealed_validation_detects_raw_snapshot_and_contract_manifest_tampering(tmp_path):
    paths = _write_synthetic_bundle(tmp_path / "bundle")
    index = pd.read_csv(paths["index"])
    raw_path = Path(index.loc[0, "raw_response_path"])
    raw_path.write_bytes(b"tampered")
    with pytest.raises(AssertionError, match="raw exact-Greek response hash mismatch"):
        validate_sealed_sidecar(paths["index"], paths["seal"], paths["manifest"], enforce_frozen=False)

    paths = _write_synthetic_bundle(tmp_path / "bundle2")
    index = pd.read_csv(paths["index"])
    snapshot = Path(index.loc[0, "exact_greeks_path"])
    frame = pd.read_parquet(snapshot)
    frame.loc[0, "implied_vol"] = 0.99
    frame.to_parquet(snapshot, index=False)
    with pytest.raises(AssertionError, match="exact-Greek snapshot hash mismatch"):
        validate_sealed_sidecar(paths["index"], paths["seal"], paths["manifest"], enforce_frozen=False)

    paths = _write_synthetic_bundle(tmp_path / "bundle3")
    index = pd.read_csv(paths["index"])
    contract_manifest = Path(index.loc[0, "contract_manifest_path"])
    contract_manifest.write_text("{}", encoding="utf-8")
    with pytest.raises(AssertionError, match="contract manifest hash mismatch"):
        validate_sealed_sidecar(paths["index"], paths["seal"], paths["manifest"], enforce_frozen=False)


def test_snapshot_schema_and_exact_completed_clock_fail_closed(tmp_path):
    paths = _write_synthetic_bundle(tmp_path / "bundle")
    index = pd.read_csv(paths["index"])
    snapshot = Path(index.loc[0, "exact_greeks_path"])
    contract_manifest_path = Path(index.loc[0, "contract_manifest_path"])
    frame = pd.read_parquet(snapshot)
    frame["future_outcome"] = 1.0
    frame.to_parquet(snapshot, index=False)
    contract = json.loads(contract_manifest_path.read_text())
    contract["columns"] = list(frame.columns)
    contract["exact_greeks_sha256"] = sha256_file(snapshot)
    contract_manifest_path.write_bytes(canonical_json_bytes(contract))
    index.loc[0, "exact_greeks_sha256"] = sha256_file(snapshot)
    index.loc[0, "contract_manifest_sha256"] = sha256_file(contract_manifest_path)
    index.to_csv(paths["index"], index=False)
    seal = json.loads(paths["seal"].read_text())
    seal["index_sha256"] = sha256_file(paths["index"])
    paths["seal"].write_bytes(canonical_json_bytes(seal))
    with pytest.raises(AssertionError, match="unexpected optional columns"):
        validate_sealed_sidecar(paths["index"], paths["seal"], paths["manifest"], enforce_frozen=False)

    paths = _write_synthetic_bundle(tmp_path / "bundle2")
    index = pd.read_csv(paths["index"])
    snapshot = Path(index.loc[0, "exact_greeks_path"])
    contract_manifest_path = Path(index.loc[0, "contract_manifest_path"])
    frame = pd.read_parquet(snapshot)
    frame.loc[0, "timestamp"] += pd.Timedelta(seconds=1)
    frame.loc[0, "underlying_timestamp"] += pd.Timedelta(seconds=1)
    frame.to_parquet(snapshot, index=False)
    contract = json.loads(contract_manifest_path.read_text())
    contract["exact_greeks_sha256"] = sha256_file(snapshot)
    contract_manifest_path.write_bytes(canonical_json_bytes(contract))
    index.loc[0, "exact_greeks_sha256"] = sha256_file(snapshot)
    index.loc[0, "contract_manifest_sha256"] = sha256_file(contract_manifest_path)
    index.to_csv(paths["index"], index=False)
    seal = json.loads(paths["seal"].read_text())
    seal["index_sha256"] = sha256_file(paths["index"])
    paths["seal"].write_bytes(canonical_json_bytes(seal))
    with pytest.raises(AssertionError, match="exact 48 decision timestamps"):
        validate_sealed_sidecar(paths["index"], paths["seal"], paths["manifest"], enforce_frozen=False)


def test_overlay_rejects_scope_expansion_and_preserves_non_target_rows():
    repair = expected_repair_keys().assign(value=np.arange(96, dtype=float))
    extra = pd.DataFrame([{"ticker": "SPXW", "trade_date": "20251231", "minute": 635, "value": 9.0}])
    base = pd.concat([repair.assign(value=-1.0), extra], ignore_index=True)
    overlaid = apply_repair_overlay(base, repair, label="synthetic")
    assert len(overlaid) == len(base)
    assert overlaid.loc[overlaid["ticker"].eq("SPXW"), "value"].item() == 9.0
    incomplete = repair.iloc[:-1].copy()
    with pytest.raises(AssertionError):
        apply_repair_overlay(base, incomplete, label="synthetic")

    event_base = pd.concat([repair.iloc[:27], repair.iloc[48:68], extra], ignore_index=True)
    event_repair = event_base[event_base["ticker"].ne("SPXW")].assign(value=5.0)
    event_overlay = apply_repair_overlay(event_base, event_repair, label="event controls")
    assert len(event_overlay) == len(event_base)
    assert event_overlay.loc[event_overlay["ticker"].ne("SPXW"), "value"].eq(5.0).all()


def test_non_pass_seal_is_rejected_before_artifact_reads(tmp_path):
    paths = _write_synthetic_bundle(tmp_path / "bundle")
    seal = json.loads(paths["seal"].read_text())
    seal["status"] = "FAILED"
    paths["seal"].write_bytes(canonical_json_bytes(seal))
    with pytest.raises(AssertionError, match="not a PASS"):
        validate_sealed_sidecar(paths["index"], paths["seal"], paths["manifest"], enforce_frozen=False)


def test_event_executable_subset_count_and_hash_are_fail_closed(tmp_path, monkeypatch):
    paths = _write_synthetic_bundle(tmp_path / "bundle")
    events = pd.read_parquet(paths["events"])
    counts = events.groupby("ticker").size().astype(int).to_dict()
    digest = repair_key_hash(events)
    monkeypatch.setattr(repair_module, "EXPECTED_EVENT_REPAIR_ROWS", len(events))
    monkeypatch.setattr(repair_module, "EXPECTED_EVENT_REPAIR_ROWS_BY_TICKER", counts)
    monkeypatch.setattr(repair_module, "EXPECTED_EVENT_REPAIR_KEY_SHA256", digest)
    accepted = event_repair_keys_from_base(events, enforce_frozen=True)
    assert len(accepted) == 47

    extra = expected_repair_keys().query("ticker == 'SPY'").iloc[[20]].copy()
    for column in EVENT_COLUMNS[3:]:
        extra[column] = 0.0
    expanded = pd.concat([events, extra[list(EVENT_COLUMNS)]], ignore_index=True)
    with pytest.raises(AssertionError, match="frozen executable subset"):
        event_repair_keys_from_base(expanded, enforce_frozen=True)
