import pandas as pd
import pytest

from report_fixed_comparison_monthly import metrics, summarize


def test_daily_losses_and_inactive_observable_day_remain_in_calendar():
    days = [
        dict(date="20250102", source_status="COMPLETE", trades=1, attempts=1, net_base=-10., net_adverse=-12.),
        dict(date="20250103", source_status="COMPLETE", trades=1, attempts=1, net_base=6., net_adverse=4.),
        dict(date="20250106", source_status="COMPLETE", trades=0, attempts=1, net_base=0., net_adverse=0.),
    ]
    attempts = pd.DataFrame(dict(date=[d["date"] for d in days], status=["FILLED", "FILLED", "NO_FILL"], net_base=[-10., 6., 0.], net_adverse=[-12., 4., 0.]))
    result = summarize(days, attempts)
    assert result["base"]["net_usd"] == -4
    assert result["base"]["profit_factor"] == .6
    assert result["available_daily_close_drawdown_usd"] == 10
    assert result["observed_days_without_fill"] == 1
    assert result["universal_daily_status"] == "FAIL"


def test_missing_is_not_cash_loss_or_observed_failure_and_fabrication_rejected():
    days = [dict(date="20260401", source_status="MISSING_SOURCE", trades=0, attempts=0, net_base=0., net_adverse=0.)]
    empty = pd.DataFrame(columns=["date", "status", "net_base", "net_adverse"])
    result = summarize(days, empty)
    assert result["missing_days"] == 1
    assert result["available_days"] == 0
    assert result["observed_days_without_fill"] == 0
    assert result["universal_daily_status"] == "NO_EVALUABLE"
    assert result["best_available_day_usd"] is None
    fake = pd.DataFrame(dict(date=["20260401"], status=["FILLED"], net_base=[0.], net_adverse=[0.]))
    days[0].update(trades=1, attempts=1)
    with pytest.raises(ValueError, match="Fabricated"):
        summarize(days, fake)


def test_profit_factor_zero_loss_and_no_trade_are_not_confused():
    assert metrics([2.])["profit_factor_infinite"] is True
    assert metrics([])["profit_factor_infinite"] is False
    assert metrics([])["win_rate"] is None
    assert metrics([-2.])["profit_factor"] == 0
