from __future__ import annotations

import pytest
import pandas as pd

from neural.jepa.analyze_exact_objective_ablation import _months, passes, ticker_summary
from neural.jepa.audit_early_causal_option_dataset import minute_grid_issues
from neural.jepa.event_option_component_live import live_observable_feature_issues_for_columns
from neural.jepa.walkforward_event_option_profile_selector import (
    apply_direction_mode,
    default_profiles,
    filter_profiles,
    parse_ticker_str_grid_map,
    validate_physical_data_cutoff,
)


def test_filter_profiles_keeps_exact_names_in_canonical_order() -> None:
    profiles = default_profiles("production_zero_dte", ["SPXW", "QQQ", "SPY"])
    selected = filter_profiles(
        profiles,
        ["target_zero_dte_d35_win", "target_zero_dte_d25_return"],
    )
    assert [profile.name for profile in selected] == [
        "target_zero_dte_d25_return",
        "target_zero_dte_d35_win",
    ]


def test_filter_profiles_empty_allowlist_preserves_all_profiles() -> None:
    profiles = default_profiles("production_zero_dte", ["SPXW", "QQQ", "SPY"])
    assert filter_profiles(profiles, []) == profiles


def test_filter_profiles_rejects_unknown_name() -> None:
    profiles = default_profiles("production_zero_dte", ["SPXW", "QQQ", "SPY"])
    with pytest.raises(ValueError, match="unknown --profile-allowlist"):
        filter_profiles(profiles, ["target_zero_dte_d99_win"])


def test_parse_ticker_profile_allowlists_preserves_declared_order() -> None:
    assert parse_ticker_str_grid_map(
        ["SPXW=target_zero_dte_d25_return,target_zero_dte_d25_win"],
        field_name="profiles",
    ) == {"SPXW": ["target_zero_dte_d25_return", "target_zero_dte_d25_win"]}


def test_exact_objective_gate_requires_every_month_and_minimum_hold() -> None:
    rows = []
    for month in ("202601", "202602", "202603", "202604", "202605"):
        for index in range(18):
            rows.append(
                {
                    "date": f"{month}{index + 1:02d}",
                    "month": month,
                    "action": "CALL" if index % 2 else "PUT",
                    "realized_return": 0.5 if index < 10 else -0.3,
                    "exit_minutes": 30,
                }
            )
    summary = ticker_summary(pd.DataFrame(rows))
    assert passes(summary)
    rows[0]["exit_minutes"] = 29
    assert not passes(ticker_summary(pd.DataFrame(rows)))


def test_abstained_fold_nan_month_lists_are_empty() -> None:
    assert _months(float("nan")) == []
    assert _months("") == []


def test_pre_ib_contract_rejects_ib_features_but_keeps_backward_returns() -> None:
    assert live_observable_feature_issues_for_columns(
        "early",
        ["dist_ib_high_bps", "ret_5m_bps"],
        entry_start_minute_et=600,
    )
    assert not live_observable_feature_issues_for_columns(
        "early",
        ["ret_5m_bps", "ret_15m_bps", "ret_30m_bps"],
        entry_start_minute_et=600,
    )


def test_early_grid_auditor_distinguishes_one_and_five_minute_cadence() -> None:
    one_minute = pd.Series(range(600, 626))
    five_minute = pd.Series(range(600, 626, 5))
    assert not minute_grid_issues(one_minute, 1)
    assert minute_grid_issues(one_minute, 5)
    assert not minute_grid_issues(five_minute, 5)
    assert not minute_grid_issues(five_minute, 1)


def test_invalid_candidate_rank_can_break_negative_1e18_float_ties() -> None:
    # IEEE-754 rounds both additions to the same value at this magnitude.
    low = float(-1e18 + 10)
    high = float(-1e18 + 20)
    assert low == high
    assert (high, 20) > (low, 10)


def test_direction_modes_bind_score_and_outcome_to_causal_spot_side() -> None:
    frame = pd.DataFrame(
        [
            {
                "pred_call_return": 0.7,
                "pred_put_return": 0.4,
                "call_return": 0.5,
                "put_return": -0.2,
                "ret_5m_bps": -3.0,
                "call_d25_opt_exit_minutes": 30,
                "put_d25_opt_exit_minutes": 45,
            }
        ]
    )
    trend = apply_direction_mode(frame, "spot_5m_trend", 25).iloc[0]
    counter = apply_direction_mode(frame, "spot_5m_counter", 25).iloc[0]
    assert trend["action"] == "PUT"
    assert trend["score"] == pytest.approx(0.4)
    assert trend["realized_return"] == pytest.approx(-0.2)
    assert trend["exit_minutes"] == pytest.approx(45)
    assert counter["action"] == "CALL"
    assert counter["score"] == pytest.approx(0.7)


def test_direction_mode_drops_rows_without_required_observable_momentum() -> None:
    frame = pd.DataFrame(
        [
            {
                "pred_call_return": 0.6,
                "pred_put_return": 0.4,
                "call_return": 0.2,
                "put_return": -0.1,
                "ret_15m_bps": float("nan"),
            }
        ]
    )
    assert apply_direction_mode(frame, "spot_15m_trend", 35).empty


def test_physical_data_cutoff_defaults_fail_closed_but_can_advance_explicitly() -> None:
    frame = pd.DataFrame({"trade_date": [20260529, 20260630]})
    with pytest.raises(ValueError, match="physical data seal exceeded"):
        validate_physical_data_cutoff(frame, "202605")
    assert validate_physical_data_cutoff(frame, "202606") == "202606"


@pytest.mark.parametrize("cutoff", ["", "20261", "202613", "not-a-month"])
def test_physical_data_cutoff_rejects_invalid_month(cutoff: str) -> None:
    with pytest.raises(ValueError, match="invalid --physical-data-cutoff-month"):
        validate_physical_data_cutoff(pd.DataFrame({"trade_date": [20260529]}), cutoff)
