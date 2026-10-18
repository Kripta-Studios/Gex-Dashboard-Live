import copy

import numpy as np
import pytest

import common_greek_dynamics as dynamic


def raw_fixture():
    times = np.arange(391, dtype=np.int64) * 60_000_000_000
    return dict(
        time_ns=times,
        spot=np.linspace(100.0, 101.0, 391),
        spot_valid=np.ones(391, bool),
        strike=np.array([99.0, 100.0, 101.0, 102.0]),
        right=np.array([0, 0, 1, 1]),
        iv=np.full((391, 4), 0.2),
        delta=np.tile([0.5, 0.4, -0.4, -0.5], (391, 1)),
        vega=np.full((391, 4), 40.0),
        theta=np.full((391, 4), -2.0),
        row_flags=np.full((391, 4), 5, np.uint8),
        oi_contract_idx=np.arange(4),
        oi_available_ns=np.zeros(4, np.int64),
        oi_value=np.array([100, 200, 150, 250]),
        oi_valid=np.ones(4, bool),
    )


def named(values):
    return dict(zip(dynamic.FEATURE_NAMES, values))


def test_greek_specific_cohorts_and_units_not_iv_gate_for_all():
    raw = raw_fixture()
    raw["iv"][:, :2] = 0.0
    values = named(dynamic.encode_state(dynamic.prepare_day(raw, close_i=390), 100))
    assert values["gamma_bs_proxy_CALL_5m_available"] == 0
    assert values["delta_stored_CALL_5m_available"] == 1
    assert values[
        "vega_per_vol_point_CALL_5m_common_signed_logmass_now"
    ] == pytest.approx(np.log1p(120.0))
    assert values["theta_stored_CALL_5m_common_signed_logmass_now"] == pytest.approx(
        -np.log1p(600.0)
    )
    assert values["delta_stored_PUT_5m_common_signed_logmass_now"] < 0


def test_stale_underlying_and_invalidating_oi_are_not_filled():
    raw = raw_fixture()
    raw["row_flags"][100, 0] = 1
    raw["oi_contract_idx"] = np.r_[raw["oi_contract_idx"], 1]
    raw["oi_available_ns"] = np.r_[raw["oi_available_ns"], raw["time_ns"][99]]
    raw["oi_value"] = np.r_[raw["oi_value"], 200]
    raw["oi_valid"] = np.r_[raw["oi_valid"], False]
    values = named(dynamic.encode_state(dynamic.prepare_day(raw, close_i=390), 100))
    for greek in dynamic.GREEKS:
        assert values[f"{greek}_CALL_5m_available"] == 0
        assert values[f"{greek}_PUT_5m_available"] == 1


def test_future_values_and_new_contract_do_not_change_past():
    raw = raw_fixture()
    before = dynamic.encode_state(dynamic.prepare_day(raw, close_i=390), 100)
    future = copy.deepcopy(raw)
    for field in ("iv", "delta", "vega", "theta"):
        future[field][101:] *= 1.1
        future[field] = np.c_[future[field], np.full(391, 0.3)]
    future["row_flags"] = np.c_[
        future["row_flags"], np.r_[np.zeros(101, np.uint8), np.full(290, 5, np.uint8)]
    ]
    future["spot"][101:] += 10
    future["strike"] = np.r_[future["strike"], 104.0]
    future["right"] = np.r_[future["right"], 0]
    future["oi_contract_idx"] = np.r_[future["oi_contract_idx"], 4]
    future["oi_available_ns"] = np.r_[future["oi_available_ns"], future["time_ns"][101]]
    future["oi_value"] = np.r_[future["oi_value"], 500]
    future["oi_valid"] = np.r_[future["oi_valid"], True]
    np.testing.assert_array_equal(
        before, dynamic.encode_state(dynamic.prepare_day(future, close_i=390), 100)
    )


def test_signed_mass_coverage_and_oi_decomposition():
    raw = raw_fixture()
    raw["theta"][:, 1] = 1.0
    raw["theta"][100, 0] = -1.0
    raw["oi_contract_idx"] = np.r_[raw["oi_contract_idx"], 0]
    raw["oi_available_ns"] = np.r_[raw["oi_available_ns"], raw["time_ns"][100]]
    raw["oi_value"] = np.r_[raw["oi_value"], 150]
    raw["oi_valid"] = np.r_[raw["oi_valid"], True]
    values = named(dynamic.encode_state(dynamic.prepare_day(raw, close_i=390), 100))
    prefix = "theta_stored_CALL_5m_"
    assert values[prefix + "observed_abs_mass_past_fraction"] == 1
    assert values[prefix + "common_signed_logmass_past"] == 0
    assert values[prefix + "common_relative_change"] == pytest.approx(
        values[prefix + "fixed_oi_greek_relative_change"]
        + values[prefix + "reported_oi_relative_change"],
        abs=1e-7,
    )
    assert values[prefix + "common_oi_relative_change"] > 0


def test_calendar_close_is_explicit_and_changes_only_gamma_proxy():
    raw = raw_fixture()
    full = dynamic.prepare_day(raw, close_i=390)
    early = dynamic.prepare_day(raw, close_i=210)
    x, y = dynamic.encode_state(full, 195), dynamic.encode_state(early, 195)
    assert not np.array_equal(x[:68], y[:68])
    np.testing.assert_array_equal(x[68:], y[68:])
    with pytest.raises(ValueError, match="session"):
        dynamic.encode_state(early, 196)
    with pytest.raises(ValueError, match="close"):
        dynamic.prepare_day(raw, close_i=300)


def test_exact_compact_prefix_shape_and_zero_oi_is_known_zero():
    raw = raw_fixture()
    raw["oi_value"][:] = 0
    vector = dynamic.encode_state(dynamic.prepare_day(raw, close_i=390), 100)
    values = named(vector)
    assert values["gamma_bs_proxy_CALL_5m_available"] == 1
    assert values["gamma_bs_proxy_CALL_5m_observed_abs_mass_now_positive"] == 0
    prefix = np.arange(304, dtype=np.float32).reshape(2, 152)
    prefix[0, 0] = -0.0
    combined = dynamic.append_to_compact(prefix, np.tile(vector, (2, 1)))
    assert combined.shape == (2, 424)
    np.testing.assert_array_equal(
        combined[:, :152].view(np.uint32), prefix.view(np.uint32)
    )
    assert len(set(dynamic.FEATURE_NAMES)) == 272
    with pytest.raises(ValueError, match="float32"):
        dynamic.append_to_compact(prefix.astype(np.float64), np.tile(vector, (2, 1)))


def test_state_join_order_duplicates_and_empty_rows():
    day = dynamic.prepare_day(raw_fixture(), close_i=390)
    result = dynamic.encode_states(day, np.array([100, 90, 100]))
    np.testing.assert_array_equal(result[0], dynamic.encode_state(day, 100))
    np.testing.assert_array_equal(result[1], dynamic.encode_state(day, 90))
    np.testing.assert_array_equal(result[0], result[2])
    assert dynamic.encode_states(day, np.array([], dtype=int)).shape == (0, 272)
    with pytest.raises(ValueError, match="integer"):
        dynamic.encode_states(day, np.array([100.5]))
