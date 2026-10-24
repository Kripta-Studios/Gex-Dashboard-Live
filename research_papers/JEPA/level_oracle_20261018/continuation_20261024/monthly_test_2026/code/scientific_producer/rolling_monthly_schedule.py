"""Pure monthly walk-forward calendar and causal admission checks; no data I/O."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal, Mapping, Sequence
from zoneinfo import ZoneInfo


Mode = Literal["static", "expanding", "rolling12"]
MODES = ("static", "expanding", "rolling12")
TICKERS = ("SPXW", "SPY", "QQQ")
NY = ZoneInfo("America/New_York")
EVALUATION_START = date(2025, 1, 1)
EVALUATION_STOP = date(2026, 7, 1)
EARLIEST_TRAIN = date(2023, 1, 1)


def month_shift(month: date, offset: int) -> date:
    if type(month) is not date or month.day != 1:
        raise ValueError("A calendar month must be a date on its first day")
    if type(offset) is not int:
        raise ValueError("Month offset must be an integer")
    ordinal = month.year * 12 + month.month - 1 + offset
    year, zero_month = divmod(ordinal, 12)
    return date(year, zero_month + 1, 1)


@dataclass(frozen=True)
class Fold:
    mode: Mode
    evaluation_month: date
    train_start: date
    train_stop: date  # Exclusive; labels must also have closed before this clock.

    def __post_init__(self):
        if self.mode not in MODES:
            raise ValueError("Unknown mode")
        for value in (self.evaluation_month, self.train_start, self.train_stop):
            month_shift(value, 0)
        if not EVALUATION_START <= self.evaluation_month < EVALUATION_STOP:
            raise ValueError("Evaluation month outside declared 18-month period")
        if self.mode == "static":
            expected = (EARLIEST_TRAIN, EVALUATION_START)
        elif self.mode == "expanding":
            expected = (EARLIEST_TRAIN, self.evaluation_month)
        else:
            expected = (month_shift(self.evaluation_month, -12), self.evaluation_month)
        if (self.train_start, self.train_stop) != expected:
            raise ValueError("Training window differs from the declared mode")

    @property
    def evaluation_stop(self) -> date:
        return month_shift(self.evaluation_month, 1)

    @property
    def period(self) -> str:
        return (
            "validation" if self.evaluation_month.year == 2025 else "development_test"
        )

    @property
    def fit_key(self) -> str:
        """Shared only when algorithm, sample rule, sources and feature schema agree."""
        return f"train_{self.train_start:%Y%m%d}_{self.train_stop:%Y%m%d}_exclusive"


def build_schedule() -> tuple[Fold, ...]:
    rows = []
    for offset in range(18):
        month = month_shift(EVALUATION_START, offset)
        for mode in MODES:
            start = month_shift(month, -12) if mode == "rolling12" else EARLIEST_TRAIN
            stop = EVALUATION_START if mode == "static" else month
            rows.append(Fold(mode, month, start, stop))
    return tuple(rows)


def unique_fit_windows(folds: Sequence[Fold]) -> dict[str, tuple[date, date]]:
    return {fold.fit_key: (fold.train_start, fold.train_stop) for fold in folds}


@dataclass(frozen=True)
class Session:
    ticker: str
    day: date
    close_i: int
    source_status: Literal["COMPLETE", "MISSING_SOURCE"] = "COMPLETE"

    def __post_init__(self):
        if self.ticker not in TICKERS or type(self.day) is not date:
            raise ValueError("Invalid ticker/session date")
        if type(self.close_i) is not int or self.close_i not in (210, 390):
            raise ValueError("Session close must come from full/early NYSE calendar")
        if self.source_status not in ("COMPLETE", "MISSING_SOURCE"):
            raise ValueError("Unknown source status")

    @property
    def last_state(self) -> int:
        return self.close_i - 15

    @property
    def liquidation_i(self) -> int:
        return self.close_i - 5

    def clock(self, minute: int) -> datetime:
        return datetime.combine(self.day, time(9, 30), NY) + timedelta(minutes=minute)


def require_session_universe(
    sessions: Sequence[Session], calendar: Mapping[date, int], start: date, stop: date
) -> dict[str, int]:
    """Calendar is supplied from the separately audited NYSE session contract.

    Missing sources must be explicit rows, never omitted from daily eligibility.
    This function does not fetch or fabricate an exchange calendar.
    """
    if type(start) is not date or type(stop) is not date or start >= stop:
        raise ValueError("Invalid exclusive calendar bounds")
    if any(
        type(day) is not date or type(close) is not int or close not in (210, 390)
        for day, close in calendar.items()
    ):
        raise ValueError("Invalid calendar entry")
    expected = {
        (ticker, day) for day in calendar if start <= day < stop for ticker in TICKERS
    }
    actual = {(row.ticker, row.day) for row in sessions}
    if not expected or len(actual) != len(sessions) or actual != expected:
        raise ValueError("Missing, duplicated or extra calendar ticker-day")
    if any(row.close_i != calendar[row.day] for row in sessions):
        raise ValueError("Session horizon differs from audited calendar")
    missing = sum(row.source_status == "MISSING_SOURCE" for row in sessions)
    return dict(
        expected=len(expected),
        available=len(expected) - missing,
        missing_no_evaluable=missing,
        early_close_ticker_days=sum(row.close_i == 210 for row in sessions),
    )


def _aware(value: datetime, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name + " must have an explicit timezone")
    return value.astimezone(NY)


@dataclass(frozen=True)
class TrainingRowClock:
    session: Session
    decision_at: datetime
    latest_feature_available_at: datetime
    outcome_closed_at: datetime
    status: Literal["FILLED", "NO_FILL"]


def require_training_row(fold: Fold, row: TrainingRowClock) -> None:
    """Validate caller-supplied clocks; does not certify raw timestamp semantics."""
    session = row.session
    if session.source_status != "COMPLETE":
        raise ValueError("A missing source cannot contribute a training row")
    if not fold.train_start <= session.day < fold.train_stop:
        raise ValueError("Training session outside fit window")
    decision = _aware(row.decision_at, "decision")
    feature = _aware(row.latest_feature_available_at, "feature availability")
    closed = _aware(row.outcome_closed_at, "outcome close")
    if decision.date() != session.day or closed.date() != session.day:
        raise ValueError(
            "Decision/outcome must belong to the same session; no overnight"
        )
    if decision.second or decision.microsecond or closed.second or closed.microsecond:
        raise ValueError("Decisions and outcomes must align to sampled minutes")
    if not session.clock(60) <= decision <= session.clock(session.last_state):
        raise ValueError("Decision outside session horizon")
    if feature > decision:
        raise ValueError("Feature available after the decision")
    if row.status == "NO_FILL":
        if closed != decision + timedelta(minutes=1):
            raise ValueError("NO_FILL must close one minute after decision")
    elif row.status == "FILLED":
        if (
            not decision + timedelta(minutes=2)
            <= closed
            <= session.clock(session.liquidation_i)
        ):
            raise ValueError("Filled outcome outside physical exit bounds")
    else:
        raise ValueError("Unknown outcome status")
    cutoff = datetime.combine(fold.train_stop, time.min, NY)
    if closed >= cutoff:
        raise ValueError("Training outcome was not closed strictly before fit cutoff")


def require_fit_evidence_order(
    fold: Fold,
    latest_training_outcome_at: datetime,
    model_sealed_at: datetime,
    evaluation_outcomes_read_at: datetime,
) -> None:
    """Separate historical information cutoff from actual replay artifact clocks.

    A historical replay writes models now; never invent a past publication time.
    This verifies supplied clocks, not an execution trace or source provenance.
    """
    latest = _aware(latest_training_outcome_at, "last training outcome")
    sealed = _aware(model_sealed_at, "model seal")
    opened = _aware(evaluation_outcomes_read_at, "evaluation outcomes read")
    if latest >= datetime.combine(fold.train_stop, time.min, NY):
        raise ValueError("Training information reaches beyond fit cutoff")
    if not latest < sealed < opened:
        raise ValueError("Training, model seal and evaluation read order is invalid")
