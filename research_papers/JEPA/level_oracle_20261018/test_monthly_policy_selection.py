import copy

import pytest

from monthly_policy_selection import MODES, TICKERS, select_monthly_mode


def example():
    expected = {(ticker, day) for ticker in TICKERS for day in ("20250102", "20250703")}
    data = {
        mode: [dict(ticker=ticker, date=day, source_status="COMPLETE", trades=1,
                    net_base=10., net_adverse=8.) for ticker, day in sorted(expected)]
        for mode in MODES
    }
    return data, expected, dict.fromkeys(TICKERS, 100.)


def test_shared_scale_and_deterministic_tie():
    data, expected, scales = example()
    result = select_monthly_mode(data, expected, scales)
    assert result["selected_mode"] == "static"
    assert result["approved"] is False
    assert result["choices"][0]["common_scale_mean_daily_score"] == pytest.approx(.1)
    data["rolling12"][0].update(net_base=20., net_adverse=18.)
    assert select_monthly_mode(data, expected, scales)["selected_mode"] == "rolling12"


def test_active_day_profit_does_not_rescue_daily_failure():
    data, expected, scales = example()
    for rows in data.values():
        rows[0].update(trades=0, net_base=0., net_adverse=0.)
        rows[1].update(net_base=10000., net_adverse=9998.)
    result = select_monthly_mode(data, expected, scales)
    assert result["selected_mode"] is None
    assert result["status"] == "FAIL_NO_DAILY_COMPLIANT_MODE"
    assert all(row["net_base"] > 0 for row in result["choices"])
    assert result["choices"][0]["active_ticker_days"] == 5


def test_missing_distinct_from_available_no_fill():
    data, expected, scales = example()
    for rows in data.values():
        rows[0].update(source_status="MISSING_SOURCE", trades=0, net_base=0., net_adverse=0.)
        rows[1].update(trades=0, net_base=0., net_adverse=0.)
    result = select_monthly_mode(data, expected, scales)
    assert result["selected_mode"] is None
    assert result["choices"][0]["missing_no_evaluable"] == 1
    assert result["choices"][0]["available_days_without_fill"] == 1


@pytest.mark.parametrize("mutation", ["omit", "duplicate", "future", "missing_diff", "nonfinite", "adverse", "zero_pnl", "fractional"])
def test_bad_or_incomplete_ledger_rejected(mutation):
    data, expected, scales = example()
    rows = data["rolling12"]
    if mutation == "omit":
        rows.pop()
    elif mutation == "duplicate":
        rows.append(copy.deepcopy(rows[0]))
    elif mutation == "future":
        rows[0]["date"] = "20260102"
    elif mutation == "missing_diff":
        rows[0].update(source_status="MISSING_SOURCE", trades=0, net_base=0., net_adverse=0.)
    elif mutation == "nonfinite":
        rows[0]["net_base"] = float("nan")
    elif mutation == "adverse":
        rows[0]["net_adverse"] = 11.
    elif mutation == "zero_pnl":
        rows[0]["trades"] = 0
    else:
        rows[0]["trades"] = 1.5
    with pytest.raises(ValueError):
        select_monthly_mode(data, expected, scales)


def test_negative_economics_remains_visible_when_daily_compliant():
    data, expected, scales = example()
    for rows in data.values():
        for row in rows:
            row.update(net_base=-10., net_adverse=-12.)
    result = select_monthly_mode(data, expected, scales)
    assert result["selected_mode"] == "static"
    assert result["choices"][0]["net_base"] == -60.
    assert result["approved"] is False


def test_input_not_mutated():
    data, expected, scales = example()
    before = copy.deepcopy(data)
    select_monthly_mode(data, expected, scales)
    assert data == before
