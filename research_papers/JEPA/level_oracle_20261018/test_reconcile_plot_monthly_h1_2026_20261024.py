"""Small artificial tables only; never opens a report, market file or model."""

from copy import deepcopy

import pandas as pd
import pytest

import reconcile_plot_monthly_h1_2026_20261024 as plot


def synthetic_daily():
    dates = list(pd.bdate_range("2025-01-02", periods=250).strftime("%Y%m%d"))
    dates += list(pd.bdate_range("2026-01-02", periods=123).strftime("%Y%m%d"))
    rows = []
    for mode in plot.MODES:
        for ticker in plot.TICKERS:
            for day in dates:
                missing = (ticker, day) in plot.MISSING
                rows.append(dict(mode=mode, ticker=ticker, date=day,
                    source_status="MISSING_SOURCE" if missing else "COMPLETE",
                    evaluation_status="NO_EVALUABLE" if missing else "EVALUABLE",
                    **{k: None if missing else 0 for k in
                       ("trades", "net_base", "net_adverse", "attempts", "no_fill_attempts")}))
    return pd.DataFrame(rows)


def test_full_calendar_and_eighteen_missing_mode_rows():
    daily = synthetic_daily()
    plot.validate_daily(daily)
    assert len(daily) == 3357 and (daily.source_status == "MISSING_SOURCE").sum() == 18


@pytest.mark.parametrize("fault", ["missing_zero", "drop", "duplicate", "wrong_identity", "available_null", "mode"])
def test_calendar_or_missingness_changes_rejected(fault):
    daily = synthetic_daily()
    missing = daily.index[daily.source_status == "MISSING_SOURCE"][0]
    if fault == "missing_zero":
        daily.loc[missing, "net_base"] = 0.0
    elif fault == "drop":
        daily = daily.iloc[1:]
    elif fault == "duplicate":
        daily.iloc[1] = daily.iloc[0]
    elif fault == "wrong_identity":
        daily.loc[missing, "date"] = "20260402"
    elif fault == "available_null":
        daily.loc[0, "trades"] = None
    else:
        daily.loc[0, "mode"] = "chosen_only"
    with pytest.raises(ValueError):
        plot.validate_daily(daily)


def test_h1_prefix_and_unknown_period():
    assert plot.period_prefix("2026H1") == "2026"
    assert plot.period_prefix("2025") == "2025"
    assert plot.period_prefix("202606") == "202606"
    with pytest.raises(ValueError):
        plot.period_prefix("202607")


def group():
    frame = pd.DataFrame(dict(mode=["static"] * 2, ticker=["SPY"] * 2,
        date=["20260402"] * 2, action_id=[0, 1], exit_i=[80, 90],
        net_base=[5.0, -2.0], net_adverse=[3.0, -4.0], hold_minutes=[2, 3],
        reason=["TARGET", "STOP"], status=["FILLED"] * 2))
    daily = pd.DataFrame([
        dict(mode="static", ticker="SPY", date="20260402", source_status="COMPLETE", trades=2),
        dict(mode="static", ticker="SPY", date="20260406", source_status="COMPLETE", trades=0),
        dict(mode="static", ticker="SPY", date="20260401", source_status="MISSING_SOURCE", trades=None)])
    economy = dict(trades=2, net_base=3.0, net_adverse=-1.0,
        net_base_pf=2.5, net_adverse_pf=.75, net_base_win_rate=.5, net_adverse_win_rate=.5,
        net_base_pf_infinite=False, net_adverse_pf_infinite=False,
        net_base_max_drawdown=2.0, net_adverse_max_drawdown=4.0,
        holding_minutes=dict(min=2.0, median=2.5, max=3.0),
        exit_reasons=dict(TARGET=dict(trades=1, net_base=5.0, net_adverse=3.0),
                          STOP=dict(trades=1, net_base=-2.0, net_adverse=-4.0),
                          EOD=dict(trades=0, net_base=0.0, net_adverse=0.0)))
    row = dict(available_economics=economy, expected_ticker_days=3, available_ticker_days=2,
        missing_no_evaluable=1, missing_day_economics=None, available_days_with_fill=1,
        available_days_without_fill=1, observable_daily_pass=False,
        full_calendar_daily_status="NO_EVALUABLE_MISSING_SOURCE", daily_requirement_satisfied=False,
        attempts=2, no_fill_attempts=0, net_base_per_available_day=1.5)
    return row, frame, daily, frame.copy()


def test_missing_group_uses_available_denominator_and_literal_metrics():
    plot.reconcile_group(*group())


@pytest.mark.parametrize("field,value", [("net_base_per_available_day", 1.0),
    ("missing_no_evaluable", 0), ("full_calendar_daily_status", "FAIL_OBSERVED_ZERO"),
    ("daily_requirement_satisfied", True), ("missing_day_economics", 0.0)])
def test_missing_group_cannot_be_observed_zero(field, value):
    args = list(group())
    args[0] = deepcopy(args[0])
    args[0][field] = value
    with pytest.raises(ValueError):
        plot.reconcile_group(*args)


def test_missing_day_cannot_have_ledger_or_attempt_and_duplicate_id_rejected():
    _, frame, daily, _ = group()
    plot.validate_ledger_calendar(frame, daily)
    missing = frame.copy()
    missing["date"] = "20260401"
    with pytest.raises(ValueError):
        plot.validate_ledger_calendar(missing, daily)
    repeated = pd.concat([frame, frame], ignore_index=True)
    with pytest.raises(ValueError):
        plot.validate_ledger_calendar(repeated, daily)
