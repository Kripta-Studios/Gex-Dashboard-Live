from __future__ import annotations

import pandas as pd
import pytest

from neural.jepa import (
    audit_cross_venue_calendar_rr_leader_v4r2_2026 as audit,
)
from neural.jepa import (
    cross_venue_calendar_rr_leader_v4r2_2026_outer_common as common,
)
from neural.jepa import (
    evaluate_cross_venue_calendar_rr_leader_v4r2_2026 as outer,
)
from neural.jepa import (
    freeze_cross_venue_calendar_rr_leader_v4r2_2026 as freezer,
)


def test_frozen_components_are_outcome_free_and_exact() -> None:
    events, model = freezer.build_frozen_components()
    assert len(events) == 394
    assert model["train_rows"] == 2_217
    assert model["train_start"] == "20230103"
    assert model["train_end"] == "20251231"
    assert not events.columns.str.contains(
        "entry_open|exit_open|underlying_return|gross_bps|net_bps|pnl|outcome",
        case=False,
        regex=True,
    ).any()
    assert events["direct_probability"].between(0.0, 1.0).all()
    assert events["side"].isin([-1, 1]).all()


def test_exact_clock_readers_agree_on_synthetic_source(tmp_path) -> None:
    frame = pd.DataFrame(
        {
            "symbol": ["QQQ", "QQQ", "QQQ"],
            "date": ["20260102"] * 3,
            "timestamp": pd.to_datetime(
                [
                    "2026-01-02 10:35:00",
                    "2026-01-02 10:36:00",
                    "2026-01-02 13:36:00",
                ]
            ),
            "open": [99.0, 100.0, 101.0],
        }
    )
    path = tmp_path / "QQQ_20260102.parquet"
    frame.to_parquet(path, index=False)
    assert outer.read_two_opens(path, "QQQ", "20260102") == (100.0, 101.0)
    assert audit.read_two_opens_independent(path, "QQQ", "20260102") == (
        100.0,
        101.0,
    )


def test_closed_h1_gate_requires_every_positive_month() -> None:
    rows = []
    for ticker in common.TICKERS:
        for month in common.CLOSED_MONTHS:
            rows.extend(
                {
                    "ticker": ticker,
                    "month": month,
                    "net_bps": value,
                }
                for value in ([2.0] * 10 + [-1.0] * 3)
            )
        rows.extend(
            {"ticker": ticker, "month": common.JULY_MTD, "net_bps": 1.0}
            for _ in range(13)
        )
    ledger = pd.DataFrame(rows)
    monthly = outer.summarize_monthly(ledger)
    summary = outer.summarize_closed_h1(ledger, monthly)
    assert summary["objective_gate_pass"].all()
    changed = ledger.copy()
    mask = changed["ticker"].eq("QQQ") & changed["month"].eq("202606")
    changed.loc[mask, "net_bps"] = -1.0
    changed_monthly = outer.summarize_monthly(changed)
    changed_summary = outer.summarize_closed_h1(changed, changed_monthly)
    assert not bool(
        changed_summary.loc[
            changed_summary["ticker"].eq("QQQ"), "objective_gate_pass"
        ].iloc[0]
    )


def test_outer_clis_have_no_scientific_overrides() -> None:
    for args in (freezer.parse_args([]), outer.parse_args([]), audit.parse_args([])):
        for forbidden in (
            "ticker",
            "date",
            "exclude",
            "threshold",
            "cost",
            "entry",
            "exit",
            "model",
        ):
            assert not hasattr(args, forbidden)


def test_bad_completed_frequency_fails_gate() -> None:
    ledger = pd.DataFrame(
        [
            {"ticker": ticker, "month": month, "net_bps": 1.0}
            for ticker in common.TICKERS
            for month in common.MONTHS
            for _ in range(13 if month != "202601" or ticker != "QQQ" else 12)
        ]
    )
    monthly = outer.summarize_monthly(ledger)
    summary = outer.summarize_closed_h1(ledger, monthly)
    qqq = summary.loc[summary["ticker"].eq("QQQ")].iloc[0]
    assert int(qqq["min_month_trades"]) == 12
    assert bool(qqq["objective_gate_pass"]) is False


def test_audit_comparison_detects_economic_change() -> None:
    expected = pd.DataFrame({"ticker": ["QQQ"], "net_bps": [1.0]})
    changed = pd.DataFrame({"ticker": ["QQQ"], "net_bps": [2.0]})
    with pytest.raises(AssertionError, match="differs"):
        audit.compare_frames(expected, changed, ["ticker"], "ledger")
