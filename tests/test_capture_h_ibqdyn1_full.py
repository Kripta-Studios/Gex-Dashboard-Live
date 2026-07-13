from __future__ import annotations

import pandas as pd

import neural.jepa.capture_h_ibqdyn1_full as mod


def test_candidate_csv_is_deterministic_and_outcome_free() -> None:
    contracts = pd.DataFrame(
        [
            {
                "contract_id": "c1",
                "event_id": "e1",
                "ticker": "SPY",
                "trade_date": "20240102",
                "decision_dt": pd.Timestamp("2024-01-02 10:35:00"),
                "minute": 635,
                "nearest_level_name": "ib_low",
                "bucket": "d35",
                "right": "CALL",
                "strike": 472.0,
            }
        ]
    )
    first = mod.candidate_csv(contracts)
    second = mod.candidate_csv(contracts.copy())
    assert first == second
    assert "2024-01-02T10:35:00" in first
    assert not any(token in first for token in ("future", "opt_win", "exit_ret"))
