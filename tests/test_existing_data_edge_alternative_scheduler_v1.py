from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from neural.jepa.build_event_option_dataset import executable_quote_path_label
from neural.jepa.existing_data_edge_alternative_v1 import (
    FROZEN_HUBER_PARAMS,
    SIDE_MARGIN_PERCENTILES,
    UTILITY_THRESHOLD_PERCENTILES,
    apply_utility_policy,
    assert_development_only,
    fit_robust_utility,
    frozen_spec,
    frozen_spec_sha256,
    training_percentile_grid,
)
from neural.jepa.existing_data_edge_scheduler_v1 import (
    SCHEDULER,
    attach_selected_payoff,
    replay_live_equivalent,
    verify_executable_build_summary,
)


def test_alternative_spec_is_materially_distinct_and_frozen() -> None:
    spec = frozen_spec()
    assert spec["family"] == "direct_huber_executable_return_v1"
    assert spec["utility"].startswith("side-specific LightGBM Huber")
    assert spec["target_clipping"] is None
    assert FROZEN_HUBER_PARAMS["objective"] == "huber"
    assert FROZEN_HUBER_PARAMS["alpha"] == 0.90
    assert len(frozen_spec_sha256()) == 64


def test_robust_fit_imputes_from_train_only_and_scores_deterministically() -> None:
    train = pd.DataFrame(
        {
            "trade_date": ["20230102"] * 12,
            "x": [0.0, 1.0, np.nan, 3.0] * 3,
            "all_missing": [np.nan] * 12,
            "call_ret": np.linspace(-0.4, 0.7, 12),
            "put_ret": np.linspace(0.5, -0.3, 12),
        }
    )
    fitted = fit_robust_utility(
        train,
        ["x", "all_missing"],
        call_return_col="call_ret",
        put_return_col="put_ret",
        base_seed=20230142,
    )
    assert fitted.medians["x"] == pytest.approx(1.0)
    assert fitted.medians["all_missing"] == 0.0
    scored_a = fitted.score(train)
    scored_b = fitted.score(train)
    np.testing.assert_allclose(scored_a["utility_call"], scored_b["utility_call"])
    np.testing.assert_allclose(scored_a["utility_put"], scored_b["utility_put"])
    duplicate_columns = pd.concat([train[["x"]], train[["x"]]], axis=1)
    with pytest.raises(AssertionError, match="duplicate column"):
        fitted.score(duplicate_columns)


def test_threshold_grid_uses_fixed_percentiles_and_exact_ties_abstain() -> None:
    scores = pd.DataFrame(
        {
            "utility_call": [0.1, 0.2, 0.4, 0.3],
            "utility_put": [0.1, 0.1, -0.2, 0.5],
        }
    )
    scores["utility_max"] = scores[["utility_call", "utility_put"]].max(axis=1)
    scores["side_margin_raw"] = (scores["utility_call"] - scores["utility_put"]).abs()
    grid = training_percentile_grid(scores)
    assert len(grid) == len(UTILITY_THRESHOLD_PERCENTILES) * len(SIDE_MARGIN_PERCENTILES)
    assert {row["utility_percentile"] for row in grid} == set(UTILITY_THRESHOLD_PERCENTILES)
    assert {row["margin_percentile"] for row in grid} == set(SIDE_MARGIN_PERCENTILES)
    active = apply_utility_policy(scores, utility_threshold=0.0, side_margin=0.0)
    assert active.index.tolist() == [1, 2, 3]
    assert active["action"].tolist() == ["CALL", "CALL", "PUT"]


def test_development_guard_rejects_every_2024_plus_row() -> None:
    assert_development_only(pd.DataFrame({"trade_date": ["20220103", "20231229"]}))
    with pytest.raises(AssertionError, match="sealed"):
        assert_development_only(pd.DataFrame({"trade_date": ["20231229", "20240102"]}))


def _candidates(ticker: str, minutes: list[int], *, scores: list[float] | None = None) -> pd.DataFrame:
    if scores is None:
        scores = [0.1] * len(minutes)
    return pd.DataFrame(
        {
            "ticker": ticker,
            "trade_date": "20230103",
            "minute": minutes,
            "score": scores,
            "action": "CALL",
            "realized_return": 0.1,
            "exit_minutes": 30.0,
        }
    )


def test_scheduler_accepts_equal_exit_and_rejects_overlap() -> None:
    trades = replay_live_equivalent(_candidates("SPXW", [635, 640, 665]))
    assert trades["minute"].tolist() == [635, 665]


def test_scheduler_uses_ticker_caps_and_entry_based_cooldown() -> None:
    qqq = _candidates("QQQ", [635, 650, 665, 695])
    spy = _candidates("SPY", [635, 665, 695])
    spxw = _candidates("SPXW", [635, 665, 695, 725, 755])
    trades = replay_live_equivalent(pd.concat([qqq, spy, spxw], ignore_index=True))
    assert trades.loc[trades.ticker.eq("QQQ"), "minute"].tolist() == [635, 665]
    assert trades.loc[trades.ticker.eq("SPY"), "minute"].tolist() == [635]
    assert trades.loc[trades.ticker.eq("SPXW"), "minute"].tolist() == [635, 665, 695, 725]
    assert len(trades.loc[trades.ticker.eq("QQQ")]) == SCHEDULER["QQQ"]["max_trades_per_day"]


def test_scheduler_never_uses_future_score_ranking_or_end_of_day_backfill() -> None:
    # The low-scored 10:35 decision is observable first and opens the position.
    # A future 11:05 high score cannot replace it retrospectively.
    frame = _candidates("SPY", [635, 665], scores=[0.01, 999.0])
    trades = replay_live_equivalent(frame)
    assert trades["minute"].tolist() == [635]
    assert trades["score"].tolist() == [0.01]


def test_scheduler_fails_closed_on_duplicate_timestamp_or_bad_hold() -> None:
    duplicate = _candidates("SPXW", [635, 635])
    with pytest.raises(AssertionError, match="one policy decision"):
        replay_live_equivalent(duplicate)
    bad_hold = _candidates("SPXW", [635])
    bad_hold["exit_minutes"] = 29
    with pytest.raises(AssertionError, match="30..180"):
        replay_live_equivalent(bad_hold)


def test_selected_side_binds_only_its_executable_return_and_hold() -> None:
    scored = pd.DataFrame(
        {
            "ticker": ["QQQ", "QQQ"],
            "action": ["CALL", "PUT"],
            "option_price_mode": ["executable_quote", "executable_quote"],
            "call_d35_opt_exit_ret": [0.2, 8.0],
            "put_d35_opt_exit_ret": [9.0, -0.3],
            "call_d35_opt_exit_minutes": [30, 31],
            "put_d35_opt_exit_minutes": [32, 180],
        }
    )
    selected = attach_selected_payoff(scored)
    assert selected["realized_return"].tolist() == [0.2, -0.3]
    assert selected["exit_minutes"].tolist() == [30.0, 180.0]


def test_build_summary_requires_exact_ask_bid_trailing_contract(tmp_path: Path) -> None:
    args = {
        "option_price_mode": "executable_quote",
        "option_exit_mode": "trailing",
        "horizon_minutes": 180,
        "option_tp_pct": 10.0,
        "option_sl_pct": 0.6,
        "option_min_hold_minutes": 30,
        "option_trail_activation_pct": 0.5,
        "option_trail_drawdown_pct": 0.25,
        "require_open_interest": True,
    }
    summary = tmp_path / "SUMMARY.json"
    summary.write_text(json.dumps({"args": args}), encoding="utf-8")
    verify_executable_build_summary(summary)
    args["option_sl_pct"] = 0.5
    summary.write_text(json.dumps({"args": args}), encoding="utf-8")
    with pytest.raises(AssertionError, match="contract mismatch"):
        verify_executable_build_summary(summary)


def _contract() -> pd.Series:
    return pd.Series({"strike": 100.0, "right": "CALL", "bid": 0.90, "ask": 1.00})


def _quotes(ts: pd.Timestamp, minutes: list[int], bids: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "quote_dt": [ts + pd.Timedelta(minutes=value) for value in minutes],
            "strike": 100.0,
            "right": "CALL",
            "bid": bids,
            "ask": np.asarray(bids) + 0.05,
        }
    )


def test_execution_path_enters_ask_ignores_prehold_stop_and_trails_at_30m() -> None:
    ts = pd.Timestamp("2023-01-03 10:35:00")
    label = executable_quote_path_label(
        _quotes(ts, [5, 29, 30], [0.30, 1.60, 1.30]),
        _contract(),
        ts,
        horizon_minutes=180,
        tp_pct=10.0,
        sl_pct=0.6,
        prefix="call_d25",
        exit_mode="trailing",
        min_hold_minutes=30,
        trail_activation_pct=0.5,
        trail_drawdown_pct=0.25,
    )
    assert label["call_d25_opt_exit_minutes"] == 30
    # Ask entry is 1.00 and the observed exit bid is 1.30.
    assert label["call_d25_opt_exit_ret"] == pytest.approx(0.30)


@pytest.mark.parametrize(
    ("bids", "expected_return"),
    [([0.35], -0.65), ([11.20], 10.20)],
)
def test_execution_path_records_observed_bid_at_stop_or_take_profit(
    bids: list[float], expected_return: float
) -> None:
    ts = pd.Timestamp("2023-01-03 10:35:00")
    label = executable_quote_path_label(
        _quotes(ts, [30], bids),
        _contract(),
        ts,
        horizon_minutes=180,
        tp_pct=10.0,
        sl_pct=0.6,
        prefix="call_d25",
        exit_mode="trailing",
        min_hold_minutes=30,
        trail_activation_pct=0.5,
        trail_drawdown_pct=0.25,
    )
    assert label["call_d25_opt_exit_minutes"] == 30
    assert label["call_d25_opt_exit_ret"] == pytest.approx(expected_return)


def test_execution_path_forces_max_hold_at_180_minutes() -> None:
    ts = pd.Timestamp("2023-01-03 10:35:00")
    label = executable_quote_path_label(
        _quotes(ts, [30, 180], [1.05, 1.20]),
        _contract(),
        ts,
        horizon_minutes=180,
        tp_pct=10.0,
        sl_pct=0.6,
        prefix="call_d25",
        exit_mode="trailing",
        min_hold_minutes=30,
        trail_activation_pct=0.5,
        trail_drawdown_pct=0.25,
    )
    assert label["call_d25_opt_exit_minutes"] == 180
    assert label["call_d25_opt_exit_ret"] == pytest.approx(0.20)
