from __future__ import annotations

import numpy as np
import pandas as pd
import json

import neural.jepa.build_wall_quote_tick_dynamics_dataset as builder
from neural.jepa.build_wall_quote_tick_dynamics_dataset import (
    QDYN_FEATURES,
    right_features,
)
from neural.jepa.build_wall_quote_tick_dynamics_sidecar import (
    EXPECTED_CANDIDATE_SHA256,
    EXPECTED_WALL_STATE_SHA256,
    sha256_file,
)


DECISION = pd.Timestamp("2024-01-02 10:30:00")


def ticks(count: int = 30, *, right: str = "CALL") -> pd.DataFrame:
    rows = []
    start = DECISION - pd.Timedelta(seconds=31, milliseconds=900)
    for ordinal in range(count):
        rows.append(
            {
                "right": right,
                "timestamp": start + pd.Timedelta(seconds=ordinal),
                "contract_ordinal": ordinal,
                "bid": 1.0,
                "ask": 1.1,
                "bid_size": 10 + ordinal,
                "ask_size": 40 - ordinal,
                "bid_exchange": 1,
                "ask_exchange": 2,
                "bid_condition": 50,
                "ask_condition": 50,
            }
        )
    return pd.DataFrame(rows)


def test_frozen_feature_block_has_exactly_28_dynamic_measurements() -> None:
    assert len(QDYN_FEATURES) == 28
    assert len(set(QDYN_FEATURES)) == 28


def test_completed_window_and_size_transition_formulas() -> None:
    result = right_features(ticks(), DECISION, "CALL")
    assert result["qdyn_call_valid"] is True
    assert result["qdyn_call_dedup_rows"] == 30
    assert result["qdyn_call_unambiguous_pair_count"] == 29
    assert result["qdyn_call_unambiguous_price_change_fraction"] == 0.0
    assert result["qdyn_call_unambiguous_size_only_change_fraction"] == 1.0
    assert result["qdyn_call_log_bid_size_increase"] == np.log1p(29)
    assert result["qdyn_call_log_ask_size_decrease"] == np.log1p(29)
    assert result["qdyn_call_log_last_update_age_ms"] > 0
    assert all(np.isfinite(result[name]) for name in QDYN_FEATURES if name.startswith("qdyn_call_"))


def test_same_timestamp_collision_never_creates_ordered_transition() -> None:
    frame = ticks()
    collided = frame.iloc[[10]].copy()
    collided["contract_ordinal"] = 30
    collided["bid_size"] = 999
    frame = pd.concat([frame, collided], ignore_index=True)
    result = right_features(frame, DECISION, "CALL")
    assert result["qdyn_call_collision_rows"] == 2
    # The pair into and the pair out of the ambiguous timestamp are excluded.
    assert result["qdyn_call_unambiguous_pair_count"] == 27


def test_exact_duplicates_are_removed_from_intensity_and_quality_counted() -> None:
    frame = ticks()
    duplicate = frame.iloc[[5]].copy()
    duplicate["contract_ordinal"] = 30
    result = right_features(pd.concat([frame, duplicate], ignore_index=True), DECISION, "CALL")
    assert result["qdyn_call_raw_rows"] == 31
    assert result["qdyn_call_dedup_rows"] == 30
    assert result["qdyn_call_exact_duplicate_rows"] == 1
    assert result["qdyn_call_log_update_count"] == np.log1p(30)


def test_crossed_rows_do_not_form_valid_pairs() -> None:
    frame = ticks()
    frame.loc[10, "ask"] = 0.5
    result = right_features(frame, DECISION, "CALL")
    assert result["qdyn_call_unambiguous_pair_count"] == 27


def test_tick_at_guard_boundary_is_rejected() -> None:
    frame = ticks()
    frame.loc[0, "timestamp"] = DECISION - pd.Timedelta(seconds=2)
    try:
        right_features(frame, DECISION, "CALL")
    except AssertionError as exc:
        assert "guarded window" in str(exc)
    else:
        raise AssertionError("tick at t-2 entered completed interval")


def test_invalid_right_has_no_model_measurements() -> None:
    result = right_features(ticks(19), DECISION, "CALL")
    assert result["qdyn_call_valid"] is False
    assert all(np.isnan(result[name]) for name in QDYN_FEATURES if name.startswith("qdyn_call_"))


def test_actual_v1r1_subscription_proof_schema_is_enforced(tmp_path, monkeypatch) -> None:
    proof = pd.DataFrame(
        {
            "event_id": ["a", "b"],
            "ticker": ["SPY", "QQQ"],
            "trade_date": ["20240102", "20240102"],
            "wall_proximity_eligible_v1": [True, True],
            "exact_call_listed_tminus5m": [True, False],
            "exact_put_listed_tminus5m": [True, True],
            "causal_subscription_eligible_v1r1": [True, False],
        }
    )
    proof_path = tmp_path / "subscription_allowlist.parquet"
    proof.to_parquet(proof_path, index=False)
    monkeypatch.setattr(builder, "EXPECTED_CANDIDATES", 2)
    manifest = {
        "status": "PASS_SUBSCRIPTION_ALLOWLIST_V1R1",
        "outcome_free": True,
        "holdout_2026_used": False,
        "candidate_sha256": EXPECTED_CANDIDATE_SHA256,
        "wall_state_sha256": EXPECTED_WALL_STATE_SHA256,
        "candidates": 2,
        "eligible_events": 1,
        "eligible_event_id_sha256": builder._sha256_text(["a"]),
        "proof_sha256": sha256_file(proof_path),
        "errors": [],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    loaded, loaded_manifest = builder.load_subscription_proof(proof_path, manifest_path)
    assert loaded["causal_subscription_eligible_v1r1"].tolist() == [True, False]
    assert loaded_manifest["proof_sha256"] == sha256_file(proof_path)
