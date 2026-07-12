from __future__ import annotations

import pandas as pd
import pytest

from neural.jepa.build_wall_quote_tick_dynamics_sidecar import (
    contract_block_audit,
    event_id,
    normalize_tick_response,
)


def candidate() -> dict:
    return {
        "ticker": "SPY",
        "trade_date": "20240102",
        "decision_dt": pd.Timestamp("2024-01-02 10:30:00"),
        "candidate_wall_strike": 475.0,
        "event_id": "abc",
    }


def raw(timestamp: str = "2024-01-02T10:29:57.999") -> dict:
    return {
        "response": [
            {
                "contract": {
                    "symbol": "SPY",
                    "expiration": "2024-01-02",
                    "right": right,
                    "strike": 475.0,
                },
                "data": [
                    {
                        "timestamp": timestamp,
                        "bid": 1.0,
                        "ask": 1.1,
                        "bid_size": 10,
                        "ask_size": 20,
                        "bid_exchange": 1,
                        "ask_exchange": 2,
                        "bid_condition": 50,
                        "ask_condition": 50,
                    }
                ],
            }
            for right in ("CALL", "PUT")
        ]
    }


def test_event_id_is_deterministic_and_geometry_specific() -> None:
    first = event_id(candidate())
    second = event_id(candidate())
    changed = candidate()
    changed["candidate_wall_strike"] = 476.0
    assert first == second
    assert first != event_id(changed)


def test_tick_response_preserves_same_timestamp_rows_and_both_rights() -> None:
    value = raw()
    value["response"][0]["data"].append(value["response"][0]["data"][0].copy())
    frame = normalize_tick_response(value, candidate())
    assert len(frame) == 3
    assert set(frame["right"]) == {"CALL", "PUT"}
    assert frame["timestamp"].duplicated().any()
    assert frame[frame["right"].eq("CALL")]["contract_ordinal"].tolist() == [0, 1]


def test_tick_response_rejects_decision_or_future_timestamp() -> None:
    with pytest.raises(AssertionError, match="causal"):
        normalize_tick_response(raw("2024-01-02T10:30:00.000"), candidate())


def test_tick_response_accepts_start_and_rejects_guard_boundary() -> None:
    assert len(normalize_tick_response(raw("2024-01-02T10:29:28.000"), candidate())) == 2
    with pytest.raises(AssertionError, match="causal"):
        normalize_tick_response(raw("2024-01-02T10:29:27.999"), candidate())
    with pytest.raises(AssertionError, match="causal"):
        normalize_tick_response(raw("2024-01-02T10:29:58.000"), candidate())


def test_tick_response_rejects_contract_substitution() -> None:
    value = raw()
    value["response"][0]["contract"]["strike"] = 476.0
    with pytest.raises(AssertionError, match="substitution"):
        normalize_tick_response(value, candidate())


def test_contract_block_audit_rejects_duplicate_right() -> None:
    value = raw()
    value["response"].append(value["response"][0].copy())
    with pytest.raises(AssertionError, match="duplicate contract block"):
        contract_block_audit(value, candidate())


def test_contract_block_audit_records_missing_right() -> None:
    value = raw()
    value["response"] = value["response"][:1]
    assert contract_block_audit(value, candidate()) == {
        "call_contract_blocks": 1,
        "put_contract_blocks": 0,
        "missing_rights": ["PUT"],
    }
