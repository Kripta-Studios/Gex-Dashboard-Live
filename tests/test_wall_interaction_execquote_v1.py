import numpy as np
import pandas as pd

from neural.jepa.audit_wall_interaction_execquote_v1 import (
    add_contiguous_spot_lags,
    build_level_universe,
    join_inputs,
    level_from_distance,
    rejection_pierce_mask,
)


def test_level_distance_roundtrip():
    spot = pd.Series([100.0, 200.0])
    distance = pd.Series([10.0, -25.0])
    level = level_from_distance(spot, distance)
    np.testing.assert_allclose(level, [99.9, 200.5])


def test_lags_never_cross_session_or_gap():
    frame = pd.DataFrame({
        "ticker": ["SPY"] * 5,
        "trade_date": ["20250102"] * 3 + ["20250103"] * 2,
        "minute": [635, 640, 650, 635, 640],
        "spot": [100.0, 101.0, 103.0, 200.0, 201.0],
    })
    out = add_contiguous_spot_lags(frame)
    assert np.isnan(out.loc[2, "spot_lag_5m"])
    assert np.isnan(out.loc[3, "spot_lag_5m"])
    assert out.loc[4, "spot_lag_5m"] == 200.0


def test_prior_ib_fibonacci_uses_only_stored_distances():
    frame = pd.DataFrame({
        "spot": [100.0],
        "dist_to_max_gamma": [10.0], "dist_to_min_gamma": [-10.0],
        "dist_to_zero_gamma": [0.0], "dist_to_max_dgex": [20.0], "dist_to_min_dgex": [-20.0],
        "dist_ib_high_bps": [-100.0], "dist_ib_low_bps": [100.0],
        "dist_fib_127_up_bps": [-127.2], "dist_fib_161_up_bps": [-161.8], "dist_fib_200_up_bps": [-200.0],
        "dist_fib_127_dn_bps": [127.2], "dist_fib_161_dn_bps": [161.8], "dist_fib_200_dn_bps": [200.0],
        **{f"dist_ib_high_D{day}": [-100.0] for day in range(1, 6)},
        **{f"dist_ib_low_D{day}": [100.0] for day in range(1, 6)},
    })
    levels = build_level_universe(frame)
    assert np.isclose(levels["d1_ib_high"][0].iloc[0], 101.0)
    assert np.isclose(levels["d1_ib_low"][0].iloc[0], 99.0)
    assert np.isclose(levels["d1_fib_200_up"][0].iloc[0], 103.0)
    assert np.isclose(levels["d1_fib_200_dn"][0].iloc[0], 97.0)


def test_join_is_exact_and_excludes_2026():
    event = pd.DataFrame({
        "ticker": ["SPXW", "SPY"], "trade_date": ["20250102", "20260102"],
        "minute": [635, 635], "spot": [6000.0, 600.0],
    })
    base = {
        "ticker": ["SPX"], "date": ["20250102"], "time": ["10:35"], "spot_price": [6000.0],
        "dist_to_max_gamma": [1.0], "dist_to_min_gamma": [-1.0], "dist_to_zero_gamma": [0.0],
        "dist_to_max_dgex": [2.0], "dist_to_min_dgex": [-2.0],
    }
    for day in range(1, 6):
        base[f"dist_ib_high_D{day}"] = [-10.0]
        base[f"dist_ib_low_D{day}"] = [10.0]
    joined = join_inputs(event, pd.DataFrame(base))
    assert len(joined) == 1
    assert joined.iloc[0]["ticker"] == "SPXW"
    assert not joined["trade_date"].str.startswith("2026").any()


def test_rejection_pierce_requires_opposite_side_of_fixed_level():
    lag5 = np.array([4.0, -1.0, -5.0])
    lag10 = np.array([2.0, 3.0, -2.0])
    lag15 = np.array([1.0, 2.0, -3.0])
    np.testing.assert_array_equal(
        rejection_pierce_mask("support", lag5, lag10, lag15),
        [False, True, True],
    )
    np.testing.assert_array_equal(
        rejection_pierce_mask("resistance", lag5, lag10, lag15),
        [True, True, False],
    )
