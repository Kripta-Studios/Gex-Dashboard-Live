from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import neural.jepa.build_h_ibqdyn1_dataset as mod
from neural.jepa.build_wall_quote_tick_dynamics_sidecar import sha256_file


def _identity(events: list[dict[str, object]]) -> pd.DataFrame:
    rows = []
    for row in events:
        decision = pd.Timestamp(row["decision_dt"])
        rows.append(
            {
                "event_id": row["event_id"],
                "ticker": row["ticker"],
                "trade_date": decision.strftime("%Y%m%d"),
                "year": decision.strftime("%Y"),
                "decision_dt": decision,
                "subscription_dt": decision - pd.Timedelta(minutes=5),
                "minute": decision.hour * 60 + decision.minute,
                "clock_block": 0,
                "spot": row["spot"],
                "nearest_level_name": row["nearest_level_name"],
                "nearest_level_abs_bps": abs(float(row["distance"])),
                "bucket": "d35",
                "call_strike": 101.0,
                "put_strike": 99.0,
                "preflight_sample": False,
            }
        )
    return pd.DataFrame(rows)


def _source(events: list[dict[str, object]]) -> pd.DataFrame:
    rows = []
    for row in events:
        distance = float(row["distance"])
        level = str(row["nearest_level_name"])
        values: dict[str, object] = {
            "ticker": row["ticker"],
            "trade_date": pd.Timestamp(row["decision_dt"]).strftime("%Y%m%d"),
            "timestamp": row["decision_dt"],
            "minute": pd.Timestamp(row["decision_dt"]).hour * 60
            + pd.Timestamp(row["decision_dt"]).minute,
            "spot": row["spot"],
            "nearest_level_name": level,
            "nearest_level_abs_bps": abs(distance),
            "ib_range_bps": 50.0,
            "ret_1m_bps": 1.0,
            "ret_5m_bps": 5.0,
            "ret_15m_bps": 8.0,
            "ret_30m_bps": 10.0,
        }
        for known_level, column in mod.LEVEL_DISTANCE_COLUMNS.items():
            values[column] = distance if known_level == level else 100.0
        rows.append(values)
    return pd.DataFrame(rows)


def _ticks(right: str) -> pd.DataFrame:
    start = pd.Timestamp("2024-01-02 10:34:28")
    rows = []
    for index in range(25):
        bid = 1.0 + (index % 4) * 0.01
        rows.append(
            {
                "ticker": "SPY",
                "expiration": "20240102",
                "trade_date": "20240102",
                "event_id": "event",
                "decision_dt": pd.Timestamp("2024-01-02 10:35:00"),
                "strike": 101.0 if right == "CALL" else 99.0,
                "right": right,
                "timestamp": start + pd.Timedelta(seconds=index),
                "contract_ordinal": index,
                "bid": bid,
                "ask": bid + 0.10 + (index % 3) * 0.01,
                "bid_size": 10 + index % 5,
                "ask_size": 15 - index % 5,
                "bid_exchange": 1,
                "ask_exchange": 2,
                "bid_condition": 0,
                "ask_condition": 0,
            }
        )
    return pd.DataFrame(rows)


def test_f0_and_f1_are_exactly_frozen_and_outcome_free() -> None:
    assert len(mod.CONTROL_FEATURES) == 18
    assert len(mod.ALPHA_FIELDS) == 20
    names = [*mod.SOURCE_CONTROL_COLUMNS, *mod.OUTPUT_IDENTITY_COLUMNS]
    forbidden = ("future", "target", "status", "win", "exit", "max_ret", "min_ret")
    assert not [
        name for name in names if any(token in name.lower() for token in forbidden)
    ]


def test_control_geometry_uses_exact_selected_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = [
        {
            "event_id": "resistance",
            "ticker": "SPY",
            "decision_dt": "2024-01-02 10:35:00",
            "spot": 100.0,
            "nearest_level_name": "ib_high",
            "distance": -10.0,
        },
        {
            "event_id": "support",
            "ticker": "QQQ",
            "decision_dt": "2024-01-02 10:35:00",
            "spot": 100.0,
            "nearest_level_name": "fib_127_dn",
            "distance": 20.0,
        },
    ]
    monkeypatch.setattr(mod, "EXPECTED_EVENTS", 2)
    monkeypatch.setattr(mod, "sha256_file", lambda _: mod.EXPECTED_SOURCE_SHA256)
    monkeypatch.setattr(mod, "load_opportunity_universe", lambda _: _identity(events))
    monkeypatch.setattr(
        mod.pd, "read_parquet", lambda *_args, **_kwargs: _source(events)
    )
    frame = mod.load_control_universe("frozen.parquet").set_index("event_id")
    assert frame.loc["resistance", "wall_role"] == "resistance"
    assert frame.loc["resistance", "candidate_right"] == "CALL"
    assert frame.loc["support", "wall_role"] == "support"
    assert frame.loc["support", "candidate_right"] == "PUT"
    assert frame.loc["resistance", "candidate_wall_strike"] == pytest.approx(100.1)
    assert frame.loc["support", "candidate_wall_strike"] == pytest.approx(99.8)


def test_ineligible_event_stays_explicit_and_missing() -> None:
    candidate = {"event_id": "blocked", "causal_subscription_eligible": False}
    result = mod._build_event_measurements(candidate, [], {})
    assert result["event_id"] == "blocked"
    assert not result["ibqdyn_both_valid"]
    assert not result["causal_subscription_eligible"]
    assert np.isnan(result[mod.ALPHA_FIELDS[0]])


def test_ineligible_event_rejects_any_captured_contract() -> None:
    candidate = {"event_id": "blocked", "causal_subscription_eligible": False}
    with pytest.raises(AssertionError, match="acquired capture"):
        mod._build_event_measurements(candidate, [{"right": "CALL"}], {})


def _write_contract(
    root: Path,
    right: str,
    seal: dict[str, object],
) -> dict[str, object]:
    directory = root / right.lower()
    directory.mkdir(parents=True)
    raw_path = directory / "response.json"
    parquet_path = directory / "ticks.parquet"
    manifest_path = directory / "manifest.json"
    raw_path.write_text("{}", encoding="utf-8")
    ticks = _ticks(right)
    ticks.to_parquet(parquet_path, index=False)
    contract_id = right.lower()
    manifest = {
        "status": "PASS_H_IBQDYN1_PREFLIGHT_CONTRACT",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "contract_id": contract_id,
        "event_id": "event",
        "ticker": "SPY",
        "trade_date": "20240102",
        "right": right,
        "strike": 101.0 if right == "CALL" else 99.0,
        "decision_dt": "2024-01-02T10:35:00",
        "raw_sha256": sha256_file(raw_path),
        "parquet_sha256": sha256_file(parquet_path),
        "rows": len(ticks),
        "code_hashes": seal.get("legacy_capture_code_hashes", seal["code_hashes"]),
        "runtime_lock_sha256": seal["runtime_lock_sha256"],
        "runtime_environment_sha256": seal["runtime_environment_sha256"],
        "source_provenance": seal["source_identity"],
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return {
        "contract_id": contract_id,
        "event_id": "event",
        "right": right,
        "raw_path": str(raw_path),
        "raw_sha256": sha256_file(raw_path),
        "parquet_path": str(parquet_path),
        "parquet_sha256": sha256_file(parquet_path),
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "rows": len(ticks),
        "capture_kind": "HTTP_200_TICKS",
    }


def test_eligible_event_revalidates_two_contracts_and_builds_features(
    tmp_path: Path,
) -> None:
    seal: dict[str, object] = {
        "code_hashes": {"capture.py": "a" * 64},
        "legacy_capture_code_hashes": {"capture.py": "a" * 64},
        "runtime_lock_sha256": "b" * 64,
        "runtime_environment_sha256": "c" * 64,
        "source_identity": {
            "kind": "remote",
            "base_url": "http://example/v3",
            "status_value": "CONNECTED",
        },
    }
    rows = [_write_contract(tmp_path, right, seal) for right in ("CALL", "PUT")]
    candidate = {
        "event_id": "event",
        "causal_subscription_eligible": True,
        "ticker": "SPY",
        "trade_date": "20240102",
        "decision_dt": pd.Timestamp("2024-01-02 10:35:00"),
        "call_strike": 101.0,
        "put_strike": 99.0,
    }
    result = mod._build_event_measurements(candidate, rows, seal)
    assert result["ibqdyn_both_valid"]
    assert result["causal_subscription_eligible"]
    assert np.isfinite([result[field] for field in mod.ALPHA_FIELDS]).all()


def _write_no_data_contract(
    root: Path, right: str, seal: dict[str, object]
) -> dict[str, object]:
    directory = root / right.lower()
    directory.mkdir(parents=True)
    raw_path = directory / "response.txt"
    parquet_path = directory / "ticks.parquet"
    manifest_path = directory / "manifest.json"
    raw_path.write_bytes(mod.NO_DATA_BODY)
    ticks = _ticks(right).iloc[0:0]
    ticks.to_parquet(parquet_path, index=False)
    contract_id = "call" if right == "CALL" else "put"
    manifest = {
        "schema": "h_ibqdyn1_http472_no_data_contract_v1",
        "status": "PASS_H_IBQDYN1_HTTP472_NO_DATA_CONTRACT",
        "capture_kind": "HTTP_472_NO_DATA",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "contract_id": contract_id,
        "event_id": "event",
        "ticker": "SPY",
        "trade_date": "20240102",
        "right": right,
        "strike": 101.0 if right == "CALL" else 99.0,
        "decision_dt": "2024-01-02T10:35:00",
        "raw_sha256": sha256_file(raw_path),
        "parquet_sha256": sha256_file(parquet_path),
        "rows": 0,
        "legacy_capture_code_hashes": seal["legacy_capture_code_hashes"],
        "sealer_code_hashes": seal["code_hashes"],
        "runtime_lock_sha256": seal["runtime_lock_sha256"],
        "runtime_environment_sha256": seal["runtime_environment_sha256"],
        "source_provenance": seal["source_identity"],
        "http_status": 472,
        "http_error_name": "NO_DATA",
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return {
        "contract_id": contract_id,
        "event_id": "event",
        "right": right,
        "raw_path": str(raw_path),
        "raw_sha256": sha256_file(raw_path),
        "parquet_path": str(parquet_path),
        "parquet_sha256": sha256_file(parquet_path),
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "rows": 0,
        "capture_kind": "HTTP_472_NO_DATA",
    }


def test_http472_rights_remain_eligible_but_both_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seal: dict[str, object] = {
        "code_hashes": {"sealer.py": "a" * 64},
        "legacy_capture_code_hashes": {"capture.py": "b" * 64},
        "runtime_lock_sha256": "c" * 64,
        "runtime_environment_sha256": "d" * 64,
        "source_identity": {
            "kind": "remote",
            "base_url": "http://example/v3",
            "status_value": "CONNECTED",
        },
    }
    candidate = {
        "event_id": "event",
        "causal_subscription_eligible": True,
        "ticker": "SPY",
        "trade_date": "20240102",
        "decision_dt": pd.Timestamp("2024-01-02 10:35:00"),
        "call_strike": 101.0,
        "put_strike": 99.0,
    }
    expected = {
        "call": {
            "event_id": "event",
            "ticker": "SPY",
            "trade_date": "20240102",
            "decision_dt": "2024-01-02T10:35:00",
            "right": "CALL",
            "strike": 101.0,
        },
        "put": {
            "event_id": "event",
            "ticker": "SPY",
            "trade_date": "20240102",
            "decision_dt": "2024-01-02T10:35:00",
            "right": "PUT",
            "strike": 99.0,
        },
    }
    monkeypatch.setattr(mod, "EXPECTED_NO_DATA_CONTRACTS", expected)
    rows = [_write_no_data_contract(tmp_path, right, seal) for right in ("CALL", "PUT")]
    result = mod._build_event_measurements(candidate, rows, seal)
    assert result["causal_subscription_eligible"]
    assert not result["ibqdyn_both_valid"]
    assert np.isnan(result[mod.ALPHA_FIELDS[0]])


def _gate_frame() -> pd.DataFrame:
    rows = []
    for ticker in ("QQQ", "SPXW", "SPY"):
        for year in ("2022", "2023", "2024", "2025"):
            for state in (0.0, 1.0):
                row: dict[str, object] = {
                    "event_id": f"{ticker}-{year}-{state}",
                    "ticker": ticker,
                    "trade_date": f"{year}0102",
                    "causal_subscription_eligible": True,
                    "ibqdyn_both_valid": True,
                }
                row.update({field: 1.0 for field in mod.CONTROL_FEATURES})
                row.update({field: state for field in mod.ALPHA_FIELDS})
                rows.append(row)
    return pd.DataFrame(rows)


def test_data_gate_requires_coverage_distinctness_and_identical_complete_cases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = _gate_frame()
    monkeypatch.setattr(mod, "EXPECTED_EVENTS", len(frame))
    _, _, gate = mod.data_gate_profile(frame)
    assert gate["passed"]
    degenerate = frame.copy()
    degenerate[mod.ALPHA_FIELDS[0]] = 0.0
    _, _, bad = mod.data_gate_profile(degenerate)
    assert not bad["distinctness_pass"]
    assert not bad["passed"]
    mismatch = frame.copy()
    mismatch.loc[0, mod.ALPHA_FIELDS[1]] = np.nan
    _, _, bad_mask = mod.data_gate_profile(mismatch)
    assert not bad_mask["identical_complete_case_pass"]
    assert not bad_mask["passed"]
