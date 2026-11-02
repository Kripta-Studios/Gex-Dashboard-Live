"""Static-ready synthetic checks for the bounded four-book accounting module."""

from decimal import Decimal

from weekly_zone_revisit_accounting import _Book, _capital_available, replay_portfolio


PIN = "a" * 64
RISK_PIN = "9c387e9bea74ba65777808b5ac5e5fccfdc2437645e7b301c15eab2d33bbeb7b"


def _plan(plan_id="p1", ticker="SPY", horizon=100, grid=None):
    return {
        "plan_id": plan_id,
        "ticker": ticker,
        "horizon_end_local_ns": horizon,
        "expected_rth_minutes": [] if grid is None else grid,
        "b_value_pin": PIN,
        "c_geometry_pin": PIN,
        "fixed_risk_contract_pin": RISK_PIN,
    }


def _intent(intent_id="i1", plan_id="p1", ticker="SPY", entry=10, ask=1.0, right="CALL"):
    return {
        "intent_id": intent_id,
        "event_id": "event-" + intent_id,
        "plan_id": plan_id,
        "ticker": ticker,
        "event_session_date": "2026-01-02",
        "confirmation_time": entry - 1,
        "entry_quote_time": entry,
        "event_entry_ask": ask,
        "decision_id": "decision-" + intent_id,
        "side": right,
        "stop_spot": 90.0 if right == "CALL" else 110.0,
        "target_spot": 110.0 if right == "CALL" else 90.0,
    }


def _quote(intent_id, time, ask=2.0, bid=1.0):
    return {"decision_id": "decision-" + intent_id, "time_local_ns": time, "ask": ask, "bid": bid}


def _rows(result, intent_id):
    return [row for row in result["ledger"] if row["intent_id"] == intent_id]


def test_four_rows_and_exact_fee_aware_cash_accounting():
    result = replay_portfolio([_intent()], [_plan(grid=[20])], [], [_quote("i1", 100, bid=2.0)])
    rows = _rows(result, "i1")
    assert len(rows) == 4
    base = next(row for row in rows if row["arm"] == "B" and row["cost"] == "BASE")
    assert base["qty"] == 47
    assert base["entry_debit_decimal"] == "4808.1"
    assert base["exit_credit_decimal"] == "9291.9"
    assert base["cash_before_entry_decimal"] == "100000"
    assert base["cash_after_entry_decimal"] == "95191.9"
    assert base["cash_after_exit_decimal"] == "104483.8"
    assert result["event_updates"]["i1"] == {"terminal_reason": "FILLED", "label_available_at": 100}


def test_exit_before_equal_time_entry_releases_cash_and_expires_lockout_at_horizon():
    first = _intent("i1", entry=10)
    second = _intent("i2", plan_id="p2", entry=100)
    result = replay_portfolio(
        [second, first],
        [_plan("p1", horizon=100, grid=[]), _plan("p2", horizon=200, grid=[])],
        [],
        [_quote("i1", 100, bid=2.0), _quote("i2", 200, bid=2.0)],
    )
    assert {row["admission_status"] for row in _rows(result, "i2")} == {"ADMITTED"}
    assert all(row["cash_before_entry_decimal"] == "104483.8" for row in _rows(result, "i2"))
    assert all(row["cash_after_exit_decimal"] is not None for row in _rows(result, "i1"))


def test_a_early_exit_does_not_release_b_ticker_lockout():
    first = _intent("i1", entry=10)
    second = _intent("i2", entry=30)
    result = replay_portfolio(
        [first, second],
        [_plan(horizon=100, grid=[20])],
        [{"ticker": "SPY", "time_local_ns": 20, "spot": 110.0, "valid_rth": True}],
        [_quote("i1", 21, bid=2.0), _quote("i1", 100, bid=2.0), _quote("i2", 100, bid=2.0)],
    )
    assert {row["outcome"] for row in _rows(result, "i1") if row["arm"] == "A"} == {"TARGET_FIRST_OBSERVED"}
    assert {row["wait_reason"] for row in _rows(result, "i2")} == {"OPEN_POSITION"}


def test_qty_zero_precedes_open_position_and_capital():
    first = _intent("i1", entry=10)
    zero = _intent("i2", entry=20, ask=1000.0)
    result = replay_portfolio(
        [first, zero], [_plan(horizon=100, grid=[])], [], [_quote("i1", 100), _quote("i2", 100)]
    )
    assert {row["admission_status"] for row in _rows(result, "i2")} == {"EVENT_RISK_BUDGET"}
    assert {row["fill_status"] for row in _rows(result, "i2")} == {"NO_FILL"}
    assert all(row["wait_reason"] is None for row in _rows(result, "i2"))


def test_common_capital_gate_requires_all_four_books():
    books = {
        ("A", "BASE"): _Book(Decimal("100000"), Decimal("0"), Decimal("0")),
        ("A", "ADVERSE"): _Book(Decimal("100000"), Decimal("0"), Decimal("0")),
        ("B", "BASE"): _Book(Decimal("100000"), Decimal("0"), Decimal("0")),
        ("B", "ADVERSE"): _Book(Decimal("10"), Decimal("0"), Decimal("0")),
    }
    debits = {key: Decimal("20") for key in books}
    assert not _capital_available(books, debits, 1)


def test_missing_exit_preserves_negative_fee_bid_zero_is_observed_and_invalid_pairs_do_not_price():
    missing = replay_portfolio([_intent()], [_plan(grid=[])], [], [_quote("i1", 100, bid=None, ask=1.0)])
    missing_b = next(row for row in _rows(missing, "i1") if row["arm"] == "B" and row["cost"] == "BASE")
    assert missing_b["missing_exit_flag"] is True
    assert missing_b["exit_bid"] is None
    assert missing_b["exit_credit_decimal"] == "-61.1"
    zero = replay_portfolio([_intent()], [_plan(grid=[])], [], [_quote("i1", 100, bid=0.0)])
    zero_b = next(row for row in _rows(zero, "i1") if row["arm"] == "B" and row["cost"] == "BASE")
    assert zero_b["missing_exit_flag"] is False
    assert zero_b["exit_bid"] == 0.0
    assert zero_b["exit_credit_decimal"] == "-61.1"
    invalid = replay_portfolio([_intent()], [_plan(grid=[])], [], [_quote("i1", 100, ask=1.0, bid=2.0)])
    assert all(row["missing_exit_flag"] is True for row in _rows(invalid, "i1"))


def test_source_clocks_ignore_post_horizon_and_preserve_zero_monetary_values():
    result = replay_portfolio(
        [_intent()], [_plan(horizon=100, grid=[20])],
        [{"ticker": "SPY", "time_local_ns": 101, "spot": 110.0, "valid_rth": True}],
        [_quote("i1", 100, bid=0.0), _quote("i1", 101, bid=5.0)],
    )
    a_base = next(row for row in _rows(result, "i1") if row["arm"] == "A" and row["cost"] == "BASE")
    assert a_base["exit_trigger_kind"] == "H2"
    assert a_base["exit_bid"] == 0.0
    assert a_base["exit_credit_decimal"] == "-61.1"
    assert a_base["reserve_after_exit_decimal"] == "0"
