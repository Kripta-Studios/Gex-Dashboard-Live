"""Synthetic mathematical feature fixtures, no source data or outcomes."""

import copy
import json
import numpy as np
import pytest

import market_cues as m


def inputs():
    base = np.zeros(81)
    action = np.zeros(33)
    tokens = np.zeros((20, 45))
    for key, value in dict(
        spot_valid=1,
        ib_valid=1,
        ib_valid_fraction=1,
        spot_ib=0.5,
        ib_range_over_spot=0.01,
        change_1m_valid=1,
        change_5m_valid=1,
        change_15m_valid=1,
    ).items():
        base[m.B[key]] = value
    for key, value in dict(
        is_put=0,
        band_ib=0.05,
        target_distance_ib=0.5,
        stop_distance_ib=0.25,
        target_stop_ratio=2,
        ask_over_spot=0.01,
        bid_over_spot=0.009,
        spread_over_spot=0.001,
        quote_valid=1,
        greek_present=1,
        delta_valid=1,
        delta=0.5,
        iv_valid=1,
        iv=0.2,
        theta_valid=1,
        theta_over_spot=-0.001,
        vega_valid=1,
        vega_over_spot=0.002,
    ).items():
        action[m.A[key]] = value
    ends = np.r_[np.arange(0, 60, 5) + 4, np.full(4, -1), [14, 29, 44, 59]]
    tokens[:, m.T["spot_valid_fraction"]] = 1
    tokens[:, m.T["range_ib"]] = 0.1
    return dict(
        state_i=60,
        base=base,
        tokens=tokens,
        token_mask=(ends >= 0),
        bar_mask=(ends >= 0),
        bar_end_i=ends,
        action=action,
    )


def test_option_cost_and_spot_ratio_are_not_profit_or_dealer_inventory():
    result = m.extract_market_cues(**inputs())
    metrics = result["metrics"]
    assert metrics["spread_over_premium"]["value"] == pytest.approx(0.1)
    assert metrics["target_stop_ratio"]["value"] == 2
    assert metrics["delta"]["value"] == 0.5
    for missing in (
        "selected_option_gamma",
        "theta_cash_decay_per_minute",
        "target_stop_net_dollar_ratio",
        "dealer_signed_gamma",
    ):
        assert metrics[missing]["value"] is None and not metrics[missing]["valid"]
    json.dumps(result, allow_nan=False)
    with pytest.raises(TypeError):
        m.extract_market_cues(**inputs(), net_base=100)


def test_missing_oi_is_not_zero_but_observed_zero_is_valid():
    values = inputs()
    result = m.extract_market_cues(**values)["metrics"]
    assert result["call_observed_oi"]["value"] is None
    values["base"][m.B["current_call_oi_known_fraction"]] = 1
    result = m.extract_market_cues(**values)["metrics"]
    assert result["call_observed_oi"]["value"] == 0
    assert result["call_unsigned_gamma_proxy"]["value"] is None
    assert result["put_share_observed_oi"]["value"] is None


def test_masked_or_future_bar_perturbation_does_not_change_evidence():
    values = inputs()
    values["bar_end_i"][[0, 1]] = [60, 65]
    values["token_mask"][2] = False
    baseline = m.extract_market_cues(**values)
    changed = copy.deepcopy(values)
    changed["tokens"][:3] = np.nan
    changed["tokens"][12:16] = 9e20  # nonexistent 15m history
    assert m.extract_market_cues(**changed) == baseline


def test_partial_latest_bar_not_substituted_by_older_bar():
    values = inputs()
    values["tokens"][11, m.T["spot_valid_fraction"]] = 0.8
    metrics = m.extract_market_cues(**values)["metrics"]
    assert metrics["last_closed_5m_body_ib"]["value"] is None
    assert metrics["rejection_description"]["value"] is None
    values["action"][m.A["delta_valid"]] = 0
    values["action"][m.A["quote_valid"]] = 0
    metrics = m.extract_market_cues(**values)["metrics"]
    assert metrics["delta"]["value"] is None
    assert metrics["spread_over_premium"]["value"] is None


def test_rejection_is_preentry_geometry_and_has_symmetric_put_case():
    values = inputs()
    t = values["tokens"]
    t[9, m.T["close_rel_spot_ib"]] = 0.08
    t[10, m.T["close_rel_spot_ib"]] = 0.02
    for name, value in dict(
        low_rel_spot_ib=-0.02,
        high_rel_spot_ib=0.02,
        close_rel_spot_ib=0,
        body_ib=0.02,
        lower_wick_ib=0.02,
    ).items():
        t[11, m.T[name]] = value
    result = m.extract_market_cues(**values)
    assert result["metrics"]["rejection_description"]["value"] == 1
    assert "REJECTION_GEOMETRY_RELATIVE_TO_CURRENT_ANCHOR" in result["evidence_tags"]
    assert (
        result["anchor_asof_decision"]
        and not result["historical_anchor_availability_verified"]
    )
    values["action"][m.A["is_put"]] = 1
    t[:, m.T["close_rel_spot_ib"]] *= -1
    t[11, m.T["body_ib"]] *= -1
    t[11, m.T["upper_wick_ib"]] = 0.02
    assert (
        m.extract_market_cues(**values)["metrics"]["rejection_description"]["value"]
        == 1
    )


def test_unsigned_distribution_and_dynamic_log_average_need_masks():
    values = inputs()
    for side, oi, gamma in (("call", 100, 400), ("put", 300, 200)):
        for field, value in (
            ("oi_known_fraction", 1),
            ("present_fraction", 1),
            ("iv_valid_fraction", 1),
            ("oi_logsum", np.log1p(oi)),
            ("gamma_logsum", np.log1p(gamma)),
        ):
            values["base"][m.B[f"current_{side}_{field}"]] = value
            values["tokens"][:, m.T[f"{side}_{field}"]] = value
    metrics = m.extract_market_cues(**values)["metrics"]
    assert metrics["put_share_observed_oi"]["value"] == pytest.approx(0.75)
    assert metrics["put_share_observed_gamma"]["value"] == pytest.approx(1 / 3)
    key = "call_gamma_current_logmass_minus_closed_5m_meanlog"
    assert metrics[key]["value"] == 0
    values["tokens"][11, m.T["call_iv_valid_fraction"]] = 0.9
    assert m.extract_market_cues(**values)["metrics"][key]["value"] is None
