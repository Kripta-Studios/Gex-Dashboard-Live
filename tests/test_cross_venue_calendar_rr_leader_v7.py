from __future__ import annotations

import pandas as pd
import pytest

from neural.jepa import audit_cross_venue_calendar_rr_leader_v7 as audit
from neural.jepa import cross_venue_calendar_rr_leader_v7_common as common
from neural.jepa import evaluate_cross_venue_calendar_rr_leader_v7 as evaluator


def test_exact_fold_inventory_is_causal_without_fitting() -> None:
    common.validate_inputs()
    history = common.load_history()
    labeled = common.load_labeled_2026()
    combined = common.combined_training(history, labeled)
    assert len(history) == 2_217
    assert len(labeled) == 394
    for month in common.MONTHS:
        training = common.training_for_month(combined, month)
        test = common.testing_for_month(labeled, month)
        expected = common.EXPECTED_FOLDS[month]
        assert len(training) == sum(expected["train"])
        assert len(test) == sum(expected["test"])
        assert training["month"].max() < month
        assert test["month"].eq(month).all()


def _profitable_synthetic_ledger() -> pd.DataFrame:
    rows = []
    for ticker in common.TICKERS:
        for month in common.MONTHS:
            rows.extend(
                {"ticker": ticker, "month": month, "net_bps": value}
                for value in ([3.0] * 10 + [-1.0] * 3)
            )
    return pd.DataFrame(rows)


def test_h1_gate_requires_every_completed_month_positive() -> None:
    ledger = _profitable_synthetic_ledger()
    monthly = evaluator.summarize_monthly(ledger)
    h1 = evaluator.summarize_h1(ledger, monthly)
    assert h1["development_gate_pass"].all()

    changed = ledger.copy()
    mask = changed["ticker"].eq("QQQ") & changed["month"].eq("202603")
    changed.loc[mask, "net_bps"] = -1.0
    changed_h1 = evaluator.summarize_h1(
        changed, evaluator.summarize_monthly(changed)
    )
    qqq = changed_h1.loc[changed_h1["ticker"].eq("QQQ")].iloc[0]
    assert int(qqq["positive_months"]) == 5
    assert bool(qqq["development_gate_pass"]) is False


def test_july_health_does_not_hide_a_losing_ticker() -> None:
    ledger = _profitable_synthetic_ledger()
    mask = ledger["ticker"].eq("SPY") & ledger["month"].eq(common.JULY_MTD)
    ledger.loc[mask, "net_bps"] = -1.0
    july = evaluator.summarize_july(evaluator.summarize_monthly(ledger))
    assert july.loc[july["ticker"].eq("QQQ"), "july_mtd_health_pass"].iloc[0]
    assert not july.loc[
        july["ticker"].eq("SPY"), "july_mtd_health_pass"
    ].iloc[0]


def test_audit_comparison_detects_probability_change() -> None:
    expected = pd.DataFrame(
        {"ticker": ["QQQ"], "trade_date": ["20260102"], "probability": [0.5]}
    )
    changed = expected.copy()
    changed["probability"] = 0.6
    with pytest.raises(AssertionError, match="differs"):
        audit.compare_frames(
            expected, changed, ["ticker", "trade_date"], "predictions"
        )


def test_v7_clis_have_no_scientific_overrides() -> None:
    for args in (evaluator.parse_args([]), audit.parse_args([])):
        for forbidden in (
            "ticker",
            "date",
            "exclude",
            "threshold",
            "cost",
            "entry",
            "exit",
            "window",
            "model",
        ):
            assert not hasattr(args, forbidden)
