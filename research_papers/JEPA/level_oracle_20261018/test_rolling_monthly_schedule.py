"""Synthetic clock/calendar checks only; no source reads or fits."""

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import rolling_monthly_schedule as m


def find(mode, month=date(2025, 1, 1)):
    return next(
        f for f in m.build_schedule() if f.mode == mode and f.evaluation_month == month
    )


def test_54_evaluations_36_unique_fits_and_exact_initial_static_reuse():
    schedule = m.build_schedule()
    assert len(schedule) == 54
    assert len(m.unique_fit_windows(schedule)) == 36
    initial = find("expanding")
    assert all(f.fit_key == initial.fit_key for f in schedule if f.mode == "static")
    for mode in m.MODES:
        folds = [f for f in schedule if f.mode == mode]
        assert len(folds) == 18
        assert sum(f.period == "validation" for f in folds) == 12
        assert sum(f.period == "development_test" for f in folds) == 6
    assert find("rolling12").train_start == date(2024, 1, 1)
    assert find("rolling12", date(2026, 6, 1)).train_start == date(2025, 6, 1)
    assert find("expanding", date(2026, 6, 1)).train_stop == date(2026, 6, 1)


def test_every_rolling_window_is_exactly_twelve_complete_months():
    for fold in m.build_schedule():
        assert fold.train_stop <= fold.evaluation_month
        if fold.mode == "rolling12":
            assert m.month_shift(fold.train_start, 12) == fold.train_stop
    assert m.month_shift(date(2024, 1, 1), -1) == date(2023, 12, 1)
    with pytest.raises(ValueError):
        m.month_shift(date(2024, 1, 2), 1)
    with pytest.raises(ValueError):
        replace(find("rolling12"), train_start=date(2023, 1, 1))


def row(short=False):
    session = m.Session("SPY", date(2024, 12, 24), 210 if short else 390)
    return m.TrainingRowClock(
        session,
        session.clock(195 if short else 375),
        session.clock(194 if short else 374),
        session.clock(205 if short else 385),
        "FILLED",
    )


@pytest.mark.parametrize("short", [False, True])
def test_exact_full_and_short_entry_exit_bounds(short):
    item = row(short)
    m.require_training_row(find("expanding"), item)
    m.require_training_row(
        find("expanding"),
        replace(
            item,
            status="NO_FILL",
            outcome_closed_at=item.decision_at + timedelta(minutes=1),
        ),
    )
    with pytest.raises(ValueError, match="horizon"):
        m.require_training_row(
            find("expanding"),
            replace(item, decision_at=item.decision_at + timedelta(minutes=1)),
        )
    with pytest.raises(ValueError, match="exit bounds"):
        m.require_training_row(
            find("expanding"),
            replace(
                item, outcome_closed_at=item.outcome_closed_at + timedelta(minutes=1)
            ),
        )


def test_no_future_features_overnight_naive_or_unclosed_label():
    item = row()
    cases = [
        replace(
            item,
            latest_feature_available_at=item.decision_at + timedelta(microseconds=1),
        ),
        replace(item, outcome_closed_at=item.outcome_closed_at + timedelta(days=1)),
        replace(item, decision_at=item.decision_at.replace(tzinfo=None)),
        replace(item, status="NO_FILL"),
        replace(item, status="UNKNOWN"),
        replace(item, session=replace(item.session, source_status="MISSING_SOURCE")),
    ]
    for changed in cases:
        with pytest.raises(ValueError):
            m.require_training_row(find("expanding"), changed)


def test_utc_conversion_and_rolling_lower_bound_exclusive_upper_bound():
    item = row()
    utc_item = replace(
        item,
        decision_at=item.decision_at.astimezone(timezone.utc),
        outcome_closed_at=item.outcome_closed_at.astimezone(timezone.utc),
    )
    m.require_training_row(find("rolling12"), utc_item)
    outside = m.Session("QQQ", date(2023, 12, 29), 390)
    with pytest.raises(ValueError, match="window"):
        m.require_training_row(
            find("rolling12"),
            m.TrainingRowClock(
                outside,
                outside.clock(60),
                outside.clock(59),
                outside.clock(62),
                "FILLED",
            ),
        )
    future = m.Session("QQQ", date(2025, 1, 2), 390)
    with pytest.raises(ValueError, match="window"):
        m.require_training_row(
            find("expanding"),
            m.TrainingRowClock(
                future, future.clock(60), future.clock(59), future.clock(62), "FILLED"
            ),
        )


def test_calendar_keeps_short_and_missing_days_without_relabeling_absence():
    calendar = {date(2025, 7, 2): 390, date(2025, 7, 3): 210}
    sessions = [
        m.Session(ticker, day, close)
        for day, close in calendar.items()
        for ticker in m.TICKERS
    ]
    sessions[-1] = replace(sessions[-1], source_status="MISSING_SOURCE")
    counts = m.require_session_universe(
        sessions, calendar, date(2025, 7, 1), date(2025, 8, 1)
    )
    assert counts == dict(
        expected=6, available=5, missing_no_evaluable=1, early_close_ticker_days=3
    )
    for bad in (
        sessions[:-1],
        sessions + sessions[:1],
        sessions[:-1] + [replace(sessions[-1], close_i=390)],
    ):
        with pytest.raises(ValueError):
            m.require_session_universe(
                bad, calendar, date(2025, 7, 1), date(2025, 8, 1)
            )


def test_historical_cutoff_separate_from_replay_seal_and_outcome_read():
    fold = find("expanding")
    midnight = datetime(2025, 1, 1, tzinfo=m.NY)
    sealed = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)
    opened = sealed + timedelta(seconds=1)
    m.require_fit_evidence_order(
        fold, midnight - timedelta(microseconds=1), sealed, opened
    )
    m.require_fit_evidence_order(
        fold, (midnight - timedelta(seconds=1)).astimezone(timezone.utc), sealed, opened
    )
    for bad in (
        midnight,
        midnight + timedelta(seconds=1),
        midnight.replace(tzinfo=None),
    ):
        with pytest.raises(ValueError):
            m.require_fit_evidence_order(fold, bad, sealed, opened)
    for bad_open in (sealed, sealed - timedelta(seconds=1)):
        with pytest.raises(ValueError):
            m.require_fit_evidence_order(
                fold, midnight - timedelta(seconds=1), sealed, bad_open
            )


def test_empty_calendar_cannot_pass_coverage():
    with pytest.raises(ValueError):
        m.require_session_universe([], {}, date(2025, 1, 1), date(2025, 2, 1))
