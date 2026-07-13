from __future__ import annotations

import json

import pandas as pd
import pytest

import neural.jepa.capture_h_ibqdyn1_tick_preflight as mod


def contract(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "contract_id": "contract",
        "event_id": "event",
        "ticker": "SPY",
        "trade_date": "20240102",
        "decision_dt": pd.Timestamp("2024-01-02 10:35:00"),
        "minute": 635,
        "nearest_level_name": "ib_low",
        "bucket": "d35",
        "right": "CALL",
        "strike": 472.0,
    }
    row.update(overrides)
    return row


def raw_response(timestamp: str = "2024-01-02 10:34:30.000") -> dict:
    return {
        "response": [
            {
                "contract": {
                    "symbol": "SPY",
                    "expiration": "20240102",
                    "strike": 472.0,
                    "right": "CALL",
                },
                "data": [
                    {
                        "timestamp": timestamp,
                        "bid": 1.0,
                        "ask": 1.1,
                        "bid_size": 10,
                        "ask_size": 12,
                        "bid_exchange": 1,
                        "ask_exchange": 2,
                        "bid_condition": 0,
                        "ask_condition": 0,
                    }
                ],
            }
        ]
    }


def test_frozen_real_sample_expands_to_24_exact_contracts() -> None:
    contracts = mod.load_frozen_contracts()
    assert len(contracts) == 24
    assert contracts["event_id"].nunique() == 12
    assert set(contracts["right"]) == {"CALL", "PUT"}
    assert not contracts["trade_date"].astype(str).str.startswith("2026").any()


def test_frozen_full_proof_expands_only_eligible_contracts() -> None:
    contracts = mod.load_frozen_contracts(sample_only=False)
    assert len(contracts) == mod.EXPECTED_FULL_CONTRACTS
    assert contracts["event_id"].nunique() == mod.EXPECTED_ELIGIBLE_EVENTS
    assert set(contracts["right"]) == {"CALL", "PUT"}


def test_request_window_is_completed_and_guarded() -> None:
    params = mod.request_params(contract())
    assert params["start_time"] == "10:34:28.000"
    assert params["end_time"] == "10:34:57.999"
    assert params["right"] == "call"


def test_normalize_preserves_raw_quote_and_order() -> None:
    frame = mod.normalize_tick_response(raw_response(), contract())
    assert len(frame) == 1
    assert frame.iloc[0]["contract_ordinal"] == 0
    assert frame.iloc[0]["right"] == "CALL"
    assert frame.iloc[0]["bid_size"] == 10


def test_normalize_rejects_future_and_contract_substitution() -> None:
    with pytest.raises(AssertionError, match="guarded clock"):
        mod.normalize_tick_response(
            raw_response("2024-01-02 10:34:58.000"), contract()
        )
    substituted = raw_response()
    substituted["response"][0]["contract"]["strike"] = 471.0
    with pytest.raises(AssertionError, match="substitution"):
        mod.normalize_tick_response(substituted, contract())


def test_projection_uses_full_eligible_contract_count(monkeypatch) -> None:
    monkeypatch.setattr(mod, "EXPECTED_CONTRACTS", 2)
    monkeypatch.setattr(mod, "EXPECTED_ELIGIBLE_EVENTS", 10)
    index = pd.DataFrame(
        {
            "rows": [100, 200],
            "raw_bytes": [1_000, 2_000],
            "parquet_bytes": [500, 1_000],
        }
    )
    cost = mod.projected_cost(index)
    assert cost["full_contracts"] == 20
    assert cost["projected_rows"] == 3_000
    assert cost["projected_raw_bytes"] == 30_000
    assert cost["cost_gate_pass"]


def test_terminal_status_accepts_documented_shapes() -> None:
    assert mod.terminal_status_value(b"CONNECTED") == "CONNECTED"
    assert mod.terminal_status_value(json.dumps({"status": "connected"}).encode()) == (
        "CONNECTED"
    )


def test_remote_identity_is_exact(monkeypatch) -> None:
    with pytest.raises(AssertionError, match="not frozen"):
        mod.source_provenance(
            "http://example.com:25503/v3",
            terminal_jar=None,
            timeout=1,
        )
