from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest

from bots.tradingbot_wrapper_jepa import ET, JepaFixedDeltaBot, JepaOptionPosition, _now_et


def _bare_bot(*, risk_capital: float = 5000.0) -> JepaFixedDeltaBot:
    bot = JepaFixedDeltaBot.__new__(JepaFixedDeltaBot)
    bot.event_option_policy = {"risk_capital_dollars": risk_capital}
    return bot


def _position(*, entry_time: datetime, expiration: str) -> JepaOptionPosition:
    return JepaOptionPosition(
        ticker="SPX",
        direction="LONG",
        right="CALL",
        strike=6000.0,
        delta=0.35,
        expiration=expiration,
        entry_time=entry_time.isoformat(),
        entry_spot=6000.0,
        entry_premium=5.0,
        raw_entry_premium=4.5,
        entry_spread_pct=5.0 / 4.5 - 1.0,
        contracts=1,
        confidence=0.5,
        jepa_prob_up=0.6,
        long_threshold=0.5,
        short_threshold=0.5,
        selector_policy="event_option:SPXW:base:source:zero_dte:d25:test",
    )


def test_contract_count_uses_policy_capital_as_indivisible_sizing_target() -> None:
    bot = _bare_bot(risk_capital=5000.0)

    assert bot._contracts(25.0) == 2
    assert bot._contracts(50.0) == 1
    assert bot._contracts(50.001) == 1
    assert bot._contracts(50.01) == 1
    assert bot._contracts(float("nan")) == 0

    bot.event_option_policy["risk_capital_dollars"] = 1000.0
    assert bot._contracts(10.0) == 1
    assert bot._contracts(10.001) == 1


def test_event_option_entry_uses_ask_and_exact_expiration() -> None:
    bot = _bare_bot()
    chain = pd.DataFrame(
        [
            {
                "underlying_timestamp": "2026-07-10 10:30:00",
                "expiration": "20260711",
                "right": "CALL",
                "strike": 6010.0,
                "delta": 0.35,
                "bid": 1.0,
                "ask": 1.2,
            },
            {
                "underlying_timestamp": "2026-07-10 10:30:00",
                "expiration": "20260710",
                "right": "CALL",
                "strike": 6005.0,
                "delta": 0.35,
                "bid": 5.0,
                "ask": 4.0,
            },
            {
                "underlying_timestamp": "2026-07-10 10:30:00",
                "expiration": "20260710",
                "right": "CALL",
                "strike": 6000.0,
                "delta": 0.34,
                "bid": 4.0,
                "ask": 6.0,
            },
        ]
    )
    bot._read_parquet = lambda _filename: chain.copy()

    selected = bot._select_delta_option(
        "SPX",
        right="CALL",
        delta_target=0.35,
        suffix="0dte",
        selector_policy="event_option:test",
        expiration="20260710",
    )

    assert selected is not None
    assert selected["expiration"] == "20260710"
    assert selected["strike"] == pytest.approx(6000.0)
    assert selected["raw_entry_premium"] == pytest.approx(5.0)
    assert selected["entry_premium"] == pytest.approx(6.0)


def test_exact_snapshot_selected_strike_is_not_replaced_by_delta_tie_break() -> None:
    bot = _bare_bot()
    today = _now_et().strftime("%Y%m%d")
    timestamp = _now_et().replace(second=0, microsecond=0, tzinfo=None)
    chain = pd.DataFrame(
        [
            {
                "underlying_timestamp": timestamp,
                "expiration": today,
                "right": "CALL",
                "strike": 6000.0 + idx * 5.0,
                "delta": 0.35,
                "bid": 1.0 + idx * 0.1,
                "ask": 1.1 + idx * 0.1,
            }
            for idx in range(9)
        ]
    )
    bot._read_parquet = lambda _filename: chain.copy()

    selected = bot._select_delta_option(
        "SPX",
        right="CALL",
        delta_target=0.35,
        suffix="0dte",
        selector_policy="event_option:test",
        expiration=today,
        strike_target=6040.0,
    )

    assert selected is not None
    assert selected["strike"] == pytest.approx(6040.0)


def test_option_snapshot_rejects_fresh_file_with_previous_day_internal_timestamp() -> None:
    bot = _bare_bot()
    today = _now_et().date()
    stale = pd.Timestamp(today) - pd.Timedelta(days=1) + pd.Timedelta(hours=10, minutes=30)
    expiration = (pd.Timestamp(today) + pd.Timedelta(days=7)).strftime("%Y%m%d")
    bot._read_parquet = lambda _filename: pd.DataFrame(
        {
            "underlying_timestamp": [stale],
            "expiration": [expiration],
            "right": ["CALL"],
            "strike": [6000.0],
            "delta": [0.35],
            "bid": [1.0],
            "ask": [1.1],
        }
    )

    assert bot._latest_option_snapshot("SPX", suffix="weekly", expiration=expiration).empty


def test_open_position_uses_bid_from_exact_expiration() -> None:
    bot = _bare_bot()
    chain = pd.DataFrame(
        [
            {
                "underlying_timestamp": "2026-07-10 11:00:00",
                "expiration": "20260711",
                "right": "CALL",
                "strike": 6000.0,
                "bid": 99.0,
                "ask": 100.0,
            },
            {
                "underlying_timestamp": "2026-07-10 11:00:00",
                "expiration": "20260710",
                "right": "CALL",
                "strike": 6000.0,
                "bid": 2.0,
                "ask": 8.0,
            },
        ]
    )
    bot._read_parquet = lambda _filename: chain.copy()
    pos = _position(
        entry_time=datetime(2026, 7, 10, 10, 30, tzinfo=ET),
        expiration="20260710",
    )

    assert bot._current_option_premium(pos) == pytest.approx(2.0)


@pytest.mark.parametrize(
    ("now", "entry_time", "reason_prefix"),
    [
        (
            datetime(2026, 7, 10, 15, 31, tzinfo=ET),
            datetime(2026, 7, 10, 12, 30, tzinfo=ET),
            "event_option_max_hold_180m",
        ),
        (
            datetime(2026, 7, 10, 16, 0, tzinfo=ET),
            datetime(2026, 7, 10, 15, 0, tzinfo=ET),
            "event_option_eod_cleanup",
        ),
    ],
)
def test_due_zero_dte_position_closes_at_zero_when_bid_is_missing(
    now: datetime,
    entry_time: datetime,
    reason_prefix: str,
) -> None:
    bot = _bare_bot()
    pos = _position(entry_time=entry_time, expiration="20260710")
    bot.positions = {"SPX": pos}
    bot._current_option_premium = lambda _pos: float("nan")
    closes: list[tuple[str, float, str, datetime]] = []
    bot._close_position = lambda ticker, premium, reason, at: closes.append((ticker, premium, reason, at))

    bot._check_exit("SPX", now)

    assert closes == [("SPX", 0.0, f"{reason_prefix}_no_bid_zero_mark", now)]


def test_unexpired_weekly_position_is_not_zero_marked_without_bid() -> None:
    bot = _bare_bot()
    now = datetime(2026, 7, 10, 16, 0, tzinfo=ET)
    pos = _position(entry_time=datetime(2026, 7, 10, 12, 0, tzinfo=ET), expiration="20260717")
    pos.selector_policy = "event_option:SPXW:base:source:front_weekly:d25:test"
    bot.positions = {"SPX": pos}
    bot._current_option_premium = lambda _pos: float("nan")
    closes: list[tuple] = []
    bot._close_position = lambda *args: closes.append(args)

    bot._check_exit("SPX", now)

    assert closes == []


def test_zero_bid_after_min_hold_triggers_real_stop_instead_of_missing_quote() -> None:
    bot = _bare_bot()
    now = datetime(2026, 7, 10, 11, 0, tzinfo=ET)
    pos = _position(entry_time=datetime(2026, 7, 10, 10, 30, tzinfo=ET), expiration="20260710")
    bot.positions = {"SPX": pos}
    bot._current_option_premium = lambda _pos: 0.0
    bot._save_positions = lambda: None
    closes: list[tuple] = []
    bot._close_position = lambda *args: closes.append(args)

    bot._check_exit("SPX", now)

    assert len(closes) == 1
    assert closes[0][0] == "SPX"
    assert closes[0][1] == 0.0
    assert "stop_loss" in closes[0][2]
