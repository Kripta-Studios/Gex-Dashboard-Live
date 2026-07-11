import numpy as np
import pandas as pd
import pytest

from neural.jepa.wall_state_features import (
    add_wall_persistence,
    assert_wall_state_schema,
    compute_wall_states,
    prepare_exposure_rows,
)


def synthetic_chain(timestamp="2025-01-02 10:35:00") -> pd.DataFrame:
    rows = []
    for strike in (99.0, 100.0, 101.0, 102.0):
        for right in ("CALL", "PUT"):
            oi = 100.0
            if right == "CALL" and strike == 101.0:
                oi = 5000.0
            if right == "PUT" and strike == 99.0:
                oi = 6000.0
            rows.append({
                "dt": timestamp,
                "strike": strike,
                "right": right,
                "underlying_price": 100.0,
                "implied_vol": 1.0,
                "open_interest": oi,
            })
    return pd.DataFrame(rows)


def test_current_snapshot_materializes_separate_gamma_and_delta_walls():
    states = compute_wall_states(synthetic_chain())
    assert len(states) == 1
    row = states.iloc[0]
    assert row["wall_call_gamma_strike"] == 101.0
    assert row["wall_put_gamma_strike"] == 99.0
    assert row["wall_call_delta_strike"] == 101.0
    assert row["wall_put_delta_strike"] == 99.0
    assert 0.0 <= row["wall_call_gamma_concentration"] <= 1.0
    assert 0.0 <= row["wall_put_delta_hhi"] <= 1.0
    assert row["wall_call_gamma_effective_strikes"] > 0.0
    assert row["wall_put_delta_magnitude_log"] < 0.0


def test_duplicate_quote_does_not_multiply_open_interest_exposure():
    base = synthetic_chain()
    duplicate = pd.concat([base, base.iloc[[0]]], ignore_index=True)
    one = prepare_exposure_rows(base)
    two = prepare_exposure_rows(duplicate)
    assert len(one) == len(two)
    np.testing.assert_allclose(one["net_gamma"], two["net_gamma"])


def test_persistence_resets_on_gap_and_new_session():
    frame = pd.DataFrame({
        "ticker": ["SPY"] * 5,
        "trade_date": ["20250102"] * 4 + ["20250103"],
        "minute": [635, 640, 645, 655, 635],
        "spot": [100.0] * 5,
        "wall_call_gamma_strike": [101.0, 101.0, 102.0, 102.0, 102.0],
        "wall_call_gamma_magnitude_log": [5.0, 5.2, 5.1, 5.3, 5.4],
    })
    out = add_wall_persistence(frame)
    assert out.loc[0, "wall_call_gamma_age_minutes"] == 0
    assert out.loc[1, "wall_call_gamma_age_minutes"] == 5
    assert out.loc[2, "wall_call_gamma_age_minutes"] == 0
    assert out.loc[3, "wall_call_gamma_age_minutes"] == 0
    assert out.loc[4, "wall_call_gamma_age_minutes"] == 0
    assert np.isnan(out.loc[3, "wall_call_gamma_move_5m_bps"])
    assert out.loc[4, "wall_call_gamma_same_5m"] == 0


def test_schema_rejects_future_and_2026():
    with pytest.raises(AssertionError, match="Outcome/future"):
        assert_wall_state_schema(pd.DataFrame({"future_return": [1.0]}))
    with pytest.raises(AssertionError, match="2026"):
        assert_wall_state_schema(pd.DataFrame({"trade_date": ["20260102"]}))
