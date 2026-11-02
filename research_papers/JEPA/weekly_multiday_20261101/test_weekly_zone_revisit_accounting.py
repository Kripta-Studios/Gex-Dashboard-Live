"""Static-ready synthetic checks for the bounded four-book accounting module."""

from decimal import Decimal, Inexact, getcontext, setcontext

from weekly_zone_revisit_accounting import _Book, _capital_available, replay_portfolio


PIN = "a" * 64
RISK_PIN = "9c387e9bea74ba65777808b5ac5e5fccfdc2437645e7b301c15eab2d33bbeb7b"

LEDGER_FIELDS = {
    "ledger_id", "intent_id", "event_id", "plan_id", "ticker", "event_session_date", "arm", "cost",
    "admission_status", "fill_status", "decision_time", "entry_quote_time", "horizon_end", "decision_id",
    "right", "entry_ask", "slippage_dollars", "unit_risk_cents", "qty", "entry_debit_decimal",
    "exit_trigger_time", "exit_trigger_kind", "exit_bid_time", "exit_bid", "accounting_exit_time",
    "exit_credit_decimal", "net_decimal", "outcome", "missing_exit_flag", "ambiguous_flag",
    "label_available_at", "cash_before_entry_decimal", "reserve_before_entry_decimal",
    "exit_fee_obligation_before_decimal", "realized_equity_before_decimal", "cash_after_entry_decimal",
    "reserve_after_entry_decimal", "exit_fee_obligation_after_entry_decimal", "realized_equity_after_entry_decimal",
    "cash_after_exit_decimal", "reserve_after_exit_decimal", "exit_fee_obligation_after_exit_decimal",
    "realized_equity_after_exit_decimal", "wait_reason", "b_value_pin", "c_geometry_pin", "replay_contract_pin",
}


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
    assert len(base) == 47
    assert set(base) == LEDGER_FIELDS
    assert base["b_value_pin"] == PIN
    assert base["c_geometry_pin"] == PIN
    assert base["replay_contract_pin"] == RISK_PIN
    assert base["qty"] == 47
    assert base["entry_debit_decimal"] == "4808.1"
    assert base["exit_credit_decimal"] == "9291.9"
    assert base["cash_before_entry_decimal"] == "100000"
    assert base["cash_after_entry_decimal"] == "95191.9"
    assert base["reserve_after_entry_decimal"] == "4747"
    assert base["exit_fee_obligation_after_entry_decimal"] == "61.1"
    assert base["realized_equity_after_entry_decimal"] == "99938.9"
    assert base["cash_after_exit_decimal"] == "104483.8"
    assert base["reserve_after_exit_decimal"] == "0"
    assert base["exit_fee_obligation_after_exit_decimal"] == "0"
    assert base["realized_equity_after_exit_decimal"] == "104483.8"
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
    base = next(row for row in _rows(result, "i2") if row["arm"] == "B" and row["cost"] == "BASE")
    adverse = next(row for row in _rows(result, "i2") if row["arm"] == "B" and row["cost"] == "ADVERSE")
    assert base["cash_before_entry_decimal"] == "104483.8"
    assert adverse["cash_before_entry_decimal"] == "104389.8"
    assert all(row["cash_after_exit_decimal"] is not None for row in _rows(result, "i1"))


def test_a_early_exit_does_not_release_b_ticker_lockout():
    first = _intent("i1", entry=10)
    second = _intent("i2", entry=30)
    result = replay_portfolio(
        [first, second],
        [_plan(horizon=100, grid=[20])],
        [{"ticker": "SPY", "time_local_ns": 20, "spot": 110.0, "valid_rth": True}],
        [
            _quote("i1", 20, bid=1.0),
            _quote("i1", 21, bid=2.0),
            _quote("i1", 100, bid=2.0),
            _quote("i2", 100, bid=2.0),
        ],
    )
    assert {row["outcome"] for row in _rows(result, "i1") if row["arm"] == "A"} == {"TARGET_FIRST_OBSERVED"}
    a_base = next(row for row in _rows(result, "i1") if row["arm"] == "A" and row["cost"] == "BASE")
    assert a_base["exit_bid_time"] == 21
    assert a_base["exit_bid"] == 2.0
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
    nullable_after = {
        "entry_debit_decimal", "exit_trigger_time", "exit_bid_time", "exit_bid", "accounting_exit_time",
        "exit_credit_decimal", "net_decimal", "outcome", "cash_after_entry_decimal", "reserve_after_entry_decimal",
        "exit_fee_obligation_after_entry_decimal", "realized_equity_after_entry_decimal", "cash_after_exit_decimal",
        "reserve_after_exit_decimal", "exit_fee_obligation_after_exit_decimal", "realized_equity_after_exit_decimal",
    }
    for row in _rows(result, "i2"):
        assert all(row[field] is None for field in nullable_after)
        assert row["exit_trigger_kind"] == "NOT_APPLICABLE"
        assert row["missing_exit_flag"] is False
        assert row["ambiguous_flag"] is False


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


def test_entry_ties_use_plan_order_while_final_ledger_uses_lexicographic_ticker_order():
    same_ticker = replay_portfolio(
        [_intent("later", plan_id="p2"), _intent("first", plan_id="p1")],
        [_plan("p1", horizon=100, grid=[]), _plan("p2", horizon=100, grid=[])],
        [],
        [_quote("first", 100), _quote("later", 100)],
    )
    assert {row["admission_status"] for row in _rows(same_ticker, "first")} == {"ADMITTED"}
    assert {row["wait_reason"] for row in _rows(same_ticker, "later")} == {"OPEN_POSITION"}

    intents = [
        _intent("spy", plan_id="p-spy", ticker="SPY"),
        _intent("qqq", plan_id="p-qqq", ticker="QQQ"),
        _intent("spxw", plan_id="p-spxw", ticker="SPXW"),
    ]
    plans = [
        _plan("p-spy", ticker="SPY", horizon=100, grid=[]),
        _plan("p-qqq", ticker="QQQ", horizon=100, grid=[]),
        _plan("p-spxw", ticker="SPXW", horizon=100, grid=[]),
    ]
    result = replay_portfolio(intents, plans, [], [_quote("spy", 100), _quote("qqq", 100), _quote("spxw", 100)])
    assert list(dict.fromkeys(row["ticker"] for row in result["ledger"])) == ["QQQ", "SPXW", "SPY"]
    assert all(row["admission_status"] == "ADMITTED" for row in result["ledger"])


def test_replay_level_capital_block_follows_twenty_full_losses_and_preserves_before_balances():
    intents = []
    plans = []
    quotes = []
    for index in range(21):
        entry = 10 if index == 0 else index * 100
        horizon = (index + 1) * 100
        intent_id = "loss-" + str(index)
        plan_id = "plan-" + str(index)
        intents.append(_intent(intent_id, plan_id=plan_id, entry=entry))
        plans.append(_plan(plan_id, horizon=horizon, grid=[]))
        quotes.append(_quote(intent_id, horizon, ask=1.0, bid=0.0))
    result = replay_portfolio(intents, plans, [], quotes)
    blocked = _rows(result, "loss-20")
    assert {row["admission_status"] for row in blocked} == {"WAIT"}
    assert {row["wait_reason"] for row in blocked} == {"CAPITAL_BLOCKED"}
    base = next(row for row in blocked if row["arm"] == "B" and row["cost"] == "BASE")
    adverse = next(row for row in blocked if row["arm"] == "B" and row["cost"] == "ADVERSE")
    assert base["cash_before_entry_decimal"] == "2616"
    assert adverse["cash_before_entry_decimal"] == "1676"
    assert all(row["cash_after_entry_decimal"] is None for row in blocked)


def test_local_decimal_context_ignores_global_low_precision_inexact_trap():
    original = getcontext().copy()
    try:
        getcontext().prec = 6
        getcontext().traps[Inexact] = True
        result = replay_portfolio(
            [_intent(ask=1.2345678901234567)],
            [_plan(horizon=100, grid=[])],
            [],
            [_quote("i1", 100, bid=0.0)],
        )
        assert len(result["ledger"]) == 4
        assert all(row["fill_status"] == "FILLED" for row in result["ledger"])
    finally:
        setcontext(original)
