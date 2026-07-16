from __future__ import annotations

import pandas as pd

from neural.jepa import evaluate_short_premium_defined_risk_v1 as v1
from neural.jepa import evaluate_short_premium_fixed_horizon_v2 as module


def structure() -> v1.Structure:
    return v1.Structure(
        structure_id="IC_d20_w1",
        kind="IC",
        short_delta=0.2,
        width=1.0,
        short_call_strike=101.0,
        short_put_strike=99.0,
        long_call_strike=102.0,
        long_put_strike=98.0,
        entry_credit=0.4,
        max_risk_points=0.68,
    )


def greek_path(crossed_exit: bool = False) -> pd.DataFrame:
    rows = []
    for clock in ("10:35", "11:05"):
        for right, strike in (("C", 101.0), ("P", 99.0), ("C", 102.0), ("P", 98.0)):
            bid, ask = (0.1, 0.2) if strike in (102.0, 98.0) else (0.3, 0.4)
            if crossed_exit and clock == "11:05" and strike == 99.0:
                bid, ask = 0.5, 0.4
            rows.append(
                {
                    "qdt": pd.Timestamp(f"2025-01-02 {clock}"),
                    "right": right,
                    "strike": strike,
                    "bid": bid,
                    "ask": ask,
                }
            )
    return pd.DataFrame(rows)


def test_exact_exit_uses_executable_four_leg_debit() -> None:
    result = module.exact_exit(
        greek_path(), structure(), pd.Timestamp("2025-01-02 10:35"), 30
    )
    assert result is not None
    assert result["hold_minutes"] == 30
    assert result["exit_dt"] == pd.Timestamp("2025-01-02 11:05")


def test_crossed_required_exit_is_unresolved() -> None:
    result = module.exact_exit(
        greek_path(crossed_exit=True),
        structure(),
        pd.Timestamp("2025-01-02 10:35"),
        30,
    )
    assert result is None


def test_horizons_are_frozen_before_previous_bad_snapshot() -> None:
    assert module.HOLD_MINUTES == (30, 60, 90, 120)
