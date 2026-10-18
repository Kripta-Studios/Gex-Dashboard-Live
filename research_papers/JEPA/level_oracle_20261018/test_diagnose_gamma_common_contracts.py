import copy

import numpy as np
import pandas as pd
import pytest

import diagnose_gamma_common_contracts as diagnostic


def fixture():
    time = np.arange(391, dtype=np.int64) * 60_000_000_000
    raw = dict(
        time_ns=time,
        spot=np.linspace(100.0, 101.0, 391),
        spot_valid=np.ones(391, bool),
        strike=np.array([99.0, 100.0, 110.0]),
        right=np.array([0, 0, 0]),
        iv=np.full((391, 3), 0.2),
        row_flags=np.ones((391, 3), np.uint8),
        oi_contract_idx=np.array([0, 1, 2]),
        oi_available_ns=np.array([0, 0, 0], np.int64),
        oi_value=np.array([100, 200, 0]),
        oi_valid=np.ones(3, bool),
    )
    states = pd.DataFrame(
        [
            dict(
                ticker="SYNTHETIC",
                date="20230103",
                state_i=100,
                action_count=3,
                ipw_weight=9.0,
            )
        ]
    )
    return raw, states


def test_one_zero_oi_invalid_iv_rejects_strict_but_common_mass_retained():
    raw, states = fixture()
    raw["iv"][:, 2] = 0.0
    result = diagnostic.diagnose_day(raw, states).query("side == 'CALL'")
    assert (~result.old_cue_available).all()
    assert result.common_available.all()
    assert (result.common_count == 2).all()
    assert (result.iv_invalid_oi_zero == 1).all()
    assert (result.common_gamma_now_fraction == 1.0).all()
    assert (result.common_known_now_fraction == 2 / 3).all()


def test_prior_bar_not_endpoint_comparison():
    raw, states = fixture()
    raw["iv"][99, 0] = np.nan
    result = (
        diagnostic.diagnose_day(raw, states)
        .query("side == 'CALL' and lag == 5")
        .iloc[0]
    )
    assert not result.old_cue_available
    assert result.common_count == 3
    assert result.common_available


def test_invalidating_oi_report_not_filled_and_arithmetic_decomposition():
    raw, states = fixture()
    raw["oi_contract_idx"] = np.r_[raw["oi_contract_idx"], 0]
    raw["oi_available_ns"] = np.r_[raw["oi_available_ns"], raw["time_ns"][98]]
    raw["oi_value"] = np.r_[raw["oi_value"], 123]
    raw["oi_valid"] = np.r_[raw["oi_valid"], False]
    raw["iv"][100] = 0.21
    rows = diagnostic.diagnose_day(raw, states).query("side == 'CALL'")
    assert (rows.oi_latest_invalid == 1).all()
    assert (rows.common_count == 2).all()
    for row in rows.itertuples():
        assert row.delta_common == pytest.approx(
            row.spot_component
            + row.iv_component
            + row.time_component
            + row.reported_oi_component,
            abs=1e-8,
        )


def test_future_only_contract_and_future_values_do_not_change_prior_diagnostic():
    raw, states = fixture()
    before = diagnostic.diagnose_day(raw, states)
    changed = copy.deepcopy(raw)
    changed["iv"][101:] = 0.8
    changed["spot"][101:] += 30
    changed["strike"] = np.r_[changed["strike"], 103.0]
    changed["right"] = np.r_[changed["right"], 0]
    changed["iv"] = np.c_[changed["iv"], np.full(391, 0.4)]
    changed["row_flags"] = np.c_[
        changed["row_flags"], np.r_[np.zeros(101, np.uint8), np.ones(290, np.uint8)]
    ]
    changed["oi_contract_idx"] = np.r_[changed["oi_contract_idx"], 3]
    changed["oi_available_ns"] = np.r_[
        changed["oi_available_ns"], changed["time_ns"][101]
    ]
    changed["oi_value"] = np.r_[changed["oi_value"], 500]
    changed["oi_valid"] = np.r_[changed["oi_valid"], True]
    pd.testing.assert_frame_equal(before, diagnostic.diagnose_day(changed, states))


def test_density_matches_existing_proxy_and_ipw_summary_is_explicit():
    raw, states = fixture()
    oi = diagnostic.engine.available_oi_matrix(raw)
    expected = diagnostic.engine.bs_gamma_density(raw, 100, oi[100])
    actual = diagnostic.density(
        raw["spot"][100], raw["strike"], raw["iv"][100], 290, oi[100]
    )
    np.testing.assert_allclose(actual, expected, rtol=1e-14)
    frame = pd.DataFrame(
        {"action_count": [3, 1], "ipw_weight": [1.0, 9.0], "signal": [0.0, 1.0]}
    )
    summary = diagnostic.summarize(frame)["fields"]["signal"]
    assert summary["state_mean"] == 0.5
    assert summary["action_weighted_mean"] == 0.25
    assert summary["ipw_weighted_mean"] == 0.9
