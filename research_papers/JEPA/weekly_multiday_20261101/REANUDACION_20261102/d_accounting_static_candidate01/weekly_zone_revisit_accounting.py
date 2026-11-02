"""Pure, bounded four-book accounting for synthetic D revisit mechanics.

This module deliberately owns only portfolio admission and post-fill accounting.
It does not select events, discover entries, read files, or call the producer or
auditor.  The caller supplies already-normalized, winning intents and plans.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Context, Decimal, Inexact, ROUND_CEILING, localcontext
from hashlib import sha256
import heapq
import json
import math
from typing import Any, Iterable, Mapping


_INITIAL_CASH = Decimal("100000")
_TICKER_ORDER = {"SPY": 0, "QQQ": 1, "SPXW": 2}
_BOOKS = (
    ("A", "BASE", Decimal("0.01")),
    ("A", "ADVERSE", Decimal("0.02")),
    ("B", "BASE", Decimal("0.01")),
    ("B", "ADVERSE", Decimal("0.02")),
)
_MONEY_ZERO = Decimal("0")
_ENTRY_FEE = Decimal("1.30")
_HUNDRED = Decimal("100")


@dataclass
class _Book:
    cash: Decimal = _INITIAL_CASH
    reserve: Decimal = _MONEY_ZERO
    obligation: Decimal = _MONEY_ZERO


@dataclass
class _Exit:
    time: int
    ticker_order: int
    ledger_id: str
    book: _Book
    row: dict[str, Any]
    credit: Decimal
    principal: Decimal
    fee: Decimal


def _decimal_context() -> Context:
    context = Context(prec=1000)
    context.traps[Inexact] = True
    return context


def _required(record: Mapping[str, Any], name: str) -> Any:
    if name not in record:
        raise AssertionError("missing accounting fact: " + name)
    return record[name]


def _as_records(records: Iterable[Mapping[str, Any]] | Mapping[str, Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    if isinstance(records, Mapping):
        return list(records.values())
    return list(records)


def _canonical_decimal(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in {"", "-0"}:
        return "0"
    return text


def _ledger_id(intent_id: str, arm: str, cost: str) -> str:
    payload = {
        "schema": "D_LEDGER_V1",
        "intent_id": intent_id,
        "arm": arm,
        "cost": cost,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256(encoded).hexdigest()


def _equity(book: _Book) -> Decimal:
    return book.cash + book.reserve


def _before_snapshot(book: _Book) -> tuple[str, str, str, str]:
    return (
        _canonical_decimal(book.cash),
        _canonical_decimal(book.reserve),
        _canonical_decimal(book.obligation),
        _canonical_decimal(_equity(book)),
    )


def _after_entry_snapshot(book: _Book) -> tuple[str, str, str, str]:
    return _before_snapshot(book)


def _valid_quote(quote: Mapping[str, Any]) -> bool:
    bid = quote.get("bid")
    ask = quote.get("ask")
    if not isinstance(bid, (int, float)) or isinstance(bid, bool):
        return False
    if not isinstance(ask, (int, float)) or isinstance(ask, bool):
        return False
    return math.isfinite(bid) and math.isfinite(ask) and ask > 0 and 0 <= bid <= ask


def _spot_is_valid(spot: Mapping[str, Any]) -> bool:
    value = spot.get("spot")
    return (
        spot.get("valid_rth", True) is True
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


def _unit_risk_and_qty(entry_ask: Any) -> tuple[int, int]:
    ask = Decimal(str(entry_ask))
    unit_risk = ((ask + Decimal("0.02")) * Decimal("10000") + Decimal("260")).to_integral_value(
        rounding=ROUND_CEILING
    )
    unit_risk_int = int(unit_risk)
    if unit_risk_int <= 0:
        raise AssertionError("entry ask must imply positive unit risk")
    return unit_risk_int, 500000 // unit_risk_int


def _capital_available(books: Mapping[tuple[str, str], _Book], debits: Mapping[tuple[str, str], Decimal], qty: int) -> bool:
    required_exit_fee = Decimal(qty) * _ENTRY_FEE
    return all(
        book.cash - book.obligation >= debits[key] + required_exit_fee
        for key, book in books.items()
    )


def _plan_map(plans: Iterable[Mapping[str, Any]] | Mapping[str, Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    output: dict[str, Mapping[str, Any]] = {}
    for plan in _as_records(plans):
        plan_id = _required(plan, "plan_id")
        if plan_id in output:
            raise AssertionError("duplicate plan_id")
        output[plan_id] = plan
    return output


def _index_quotes(quotes: Iterable[Mapping[str, Any]] | Mapping[str, Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    indexed: dict[str, list[Mapping[str, Any]]] = {}
    for quote in _as_records(quotes):
        decision_id = _required(quote, "decision_id")
        indexed.setdefault(decision_id, []).append(quote)
    for values in indexed.values():
        values.sort(key=lambda item: _required(item, "time_local_ns"))
    return indexed


def _index_spots(spots: Iterable[Mapping[str, Any]] | Mapping[str, Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    indexed: dict[str, list[Mapping[str, Any]]] = {}
    for spot in _as_records(spots):
        ticker = _required(spot, "ticker")
        indexed.setdefault(ticker, []).append(spot)
    for values in indexed.values():
        values.sort(key=lambda item: _required(item, "time_local_ns"))
    return indexed


def _bid_at_horizon(quotes: list[Mapping[str, Any]], horizon: int) -> tuple[int | None, Any | None]:
    for quote in quotes:
        if _required(quote, "time_local_ns") == horizon and _valid_quote(quote):
            return horizon, quote["bid"]
    return None, None


def _first_bid_after(
    quotes: list[Mapping[str, Any]], trigger_time: int, horizon: int
) -> tuple[int | None, Any | None]:
    for quote in quotes:
        time = _required(quote, "time_local_ns")
        if trigger_time < time <= horizon and _valid_quote(quote):
            return time, quote["bid"]
    return None, None


def _a_exit(
    intent: Mapping[str, Any], plan: Mapping[str, Any], entry_time: int, horizon: int,
    ticker_spots: list[Mapping[str, Any]], decision_quotes: list[Mapping[str, Any]],
) -> tuple[int, str, str, bool, int | None, Any | None]:
    """Return A trigger, outcome, ambiguity, and permitted exit bid."""
    grid = set(_required(plan, "expected_rth_minutes"))
    right = _required(intent, "side")
    stop = _required(intent, "stop_spot")
    target = _required(intent, "target_spot")
    for observation in ticker_spots:
        time = _required(observation, "time_local_ns")
        if time <= entry_time or time >= horizon or time not in grid or not _spot_is_valid(observation):
            continue
        price = observation["spot"]
        if right == "CALL":
            hit_stop = price <= stop
            hit_target = price >= target
        elif right == "PUT":
            hit_stop = price >= stop
            hit_target = price <= target
        else:
            raise AssertionError("right must be CALL or PUT")
        if hit_stop or hit_target:
            kind = "STOP" if hit_stop else "TARGET"
            outcome = "STOP_FIRST_OBSERVED" if hit_stop else "TARGET_FIRST_OBSERVED"
            bid_time, bid = _first_bid_after(decision_quotes, time, horizon)
            return time, kind, outcome, hit_stop and hit_target, bid_time, bid
    bid_time, bid = _bid_at_horizon(decision_quotes, horizon)
    return horizon, "H2", "TIMEOUT_H2", False, bid_time, bid


def _new_row(
    intent: Mapping[str, Any], plan: Mapping[str, Any], arm: str, cost: str,
    unit_risk: int, qty: int, book: _Book,
) -> dict[str, Any]:
    intent_id = _required(intent, "intent_id")
    entry_time = _required(intent, "entry_quote_time")
    horizon = _required(plan, "horizon_end_local_ns")
    before = _before_snapshot(book)
    return {
        "ledger_id": _ledger_id(intent_id, arm, cost),
        "intent_id": intent_id,
        "event_id": _required(intent, "event_id"),
        "plan_id": _required(intent, "plan_id"),
        "ticker": _required(intent, "ticker"),
        "event_session_date": _required(intent, "event_session_date"),
        "arm": arm,
        "cost": cost,
        "admission_status": None,
        "fill_status": None,
        "decision_time": _required(intent, "confirmation_time"),
        "entry_quote_time": entry_time,
        "horizon_end": horizon,
        "decision_id": _required(intent, "decision_id"),
        "right": _required(intent, "side"),
        "entry_ask": _required(intent, "event_entry_ask"),
        "slippage_dollars": "0.01" if cost == "BASE" else "0.02",
        "unit_risk_cents": unit_risk,
        "qty": qty,
        "entry_debit_decimal": None,
        "exit_trigger_time": None,
        "exit_trigger_kind": None,
        "exit_bid_time": None,
        "exit_bid": None,
        "accounting_exit_time": None,
        "exit_credit_decimal": None,
        "net_decimal": None,
        "outcome": None,
        "missing_exit_flag": False,
        "ambiguous_flag": False,
        "label_available_at": None,
        "cash_before_entry_decimal": before[0],
        "reserve_before_entry_decimal": before[1],
        "exit_fee_obligation_before_decimal": before[2],
        "realized_equity_before_decimal": before[3],
        "cash_after_entry_decimal": None,
        "reserve_after_entry_decimal": None,
        "exit_fee_obligation_after_entry_decimal": None,
        "realized_equity_after_entry_decimal": None,
        "cash_after_exit_decimal": None,
        "reserve_after_exit_decimal": None,
        "exit_fee_obligation_after_exit_decimal": None,
        "realized_equity_after_exit_decimal": None,
        "wait_reason": None,
        "b_value_pin": _required(plan, "b_value_pin"),
        "c_geometry_pin": _required(plan, "c_geometry_pin"),
        "replay_contract_pin": _required(plan, "fixed_risk_contract_pin"),
    }


def _set_nonfill(row: dict[str, Any], admission: str, fill: str, reason: str | None) -> None:
    row["admission_status"] = admission
    row["fill_status"] = fill
    row["exit_trigger_kind"] = "NOT_APPLICABLE"
    row["wait_reason"] = reason
    row["label_available_at"] = row["entry_quote_time"]


def _apply_exit(exit_action: _Exit) -> None:
    book = exit_action.book
    book.cash += exit_action.credit
    book.reserve -= exit_action.principal
    book.obligation -= exit_action.fee
    row = exit_action.row
    row["cash_after_exit_decimal"] = _canonical_decimal(book.cash)
    row["reserve_after_exit_decimal"] = _canonical_decimal(book.reserve)
    row["exit_fee_obligation_after_exit_decimal"] = _canonical_decimal(book.obligation)
    row["realized_equity_after_exit_decimal"] = _canonical_decimal(_equity(book))


def replay_portfolio(
    intents: Iterable[Mapping[str, Any]],
    plans: Iterable[Mapping[str, Any]] | Mapping[str, Mapping[str, Any]],
    spots: Iterable[Mapping[str, Any]] | Mapping[str, Mapping[str, Any]],
    quotes: Iterable[Mapping[str, Any]] | Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Replay normalized common intents into the fixed A/B x BASE/ADVERSE ledger.

    The return is exactly ``{"ledger", "event_updates"}``.  All timestamps are
    caller-supplied NY-naive integer clocks; no calendar or quote discovery occurs.
    """
    with localcontext(_decimal_context()):
        plan_by_id = _plan_map(plans)
        quotes_by_decision = _index_quotes(quotes)
        spots_by_ticker = _index_spots(spots)
        books = {key: _Book() for arm, cost, _ in _BOOKS for key in [(arm, cost)]}
        lockout_until: dict[str, int] = {}
        exit_heap: list[tuple[int, int, str, _Exit]] = []
        ledger: list[dict[str, Any]] = []
        event_updates: dict[str, dict[str, Any]] = {}

        common_intents = list(intents)
        common_intents.sort(
            key=lambda item: (
                _required(item, "entry_quote_time"),
                _TICKER_ORDER[_required(item, "ticker")],
                _required(item, "plan_id"),
                _required(item, "event_id"),
                _required(item, "intent_id"),
            )
        )

        for intent in common_intents:
            plan = plan_by_id[_required(intent, "plan_id")]
            ticker = _required(intent, "ticker")
            if ticker not in _TICKER_ORDER:
                raise AssertionError("unknown ticker")
            entry_time = _required(intent, "entry_quote_time")
            horizon = _required(plan, "horizon_end_local_ns")
            if not entry_time < horizon:
                raise AssertionError("economic entry must precede its original H2")
            while exit_heap and exit_heap[0][0] <= entry_time:
                _time, _ticker, _ledger, action = heapq.heappop(exit_heap)
                _apply_exit(action)
            for locked_ticker, locked_horizon in list(lockout_until.items()):
                if locked_horizon <= entry_time:
                    del lockout_until[locked_ticker]

            entry_ask = _required(intent, "event_entry_ask")
            unit_risk, qty = _unit_risk_and_qty(entry_ask)
            rows: list[tuple[dict[str, Any], _Book, Decimal, Decimal, Decimal]] = []
            debits: dict[tuple[str, str], Decimal] = {}
            for arm, cost, slippage in _BOOKS:
                book = books[(arm, cost)]
                row = _new_row(intent, plan, arm, cost, unit_risk, qty, book)
                ask = Decimal(str(entry_ask))
                principal = Decimal(qty) * (ask + slippage) * _HUNDRED
                fee = Decimal(qty) * _ENTRY_FEE
                debit = principal + fee
                debits[(arm, cost)] = debit
                rows.append((row, book, debit, principal, fee))
                ledger.append(row)

            if qty == 0:
                for row, _book, _debit, _principal, _fee in rows:
                    _set_nonfill(row, "EVENT_RISK_BUDGET", "NO_FILL", None)
                event_updates[_required(intent, "intent_id")] = {
                    "terminal_reason": "NO_FILL",
                    "label_available_at": entry_time,
                }
                continue
            if ticker in lockout_until or len(lockout_until) >= 3:
                for row, _book, _debit, _principal, _fee in rows:
                    _set_nonfill(row, "WAIT", "NOT_APPLICABLE", "OPEN_POSITION")
                event_updates[_required(intent, "intent_id")] = {
                    "terminal_reason": "WAIT",
                    "label_available_at": entry_time,
                }
                continue
            if not _capital_available(books, debits, qty):
                for row, _book, _debit, _principal, _fee in rows:
                    _set_nonfill(row, "WAIT", "NOT_APPLICABLE", "CAPITAL_BLOCKED")
                event_updates[_required(intent, "intent_id")] = {
                    "terminal_reason": "WAIT",
                    "label_available_at": entry_time,
                }
                continue

            # A common fill opens all books together; B's conservative ticker lock
            # survives an earlier A stop/target exit.
            lockout_until[ticker] = horizon
            decision_quotes = quotes_by_decision.get(_required(intent, "decision_id"), [])
            a_exit = _a_exit(
                intent,
                plan,
                entry_time,
                horizon,
                spots_by_ticker.get(ticker, []),
                decision_quotes,
            )
            a_trigger, a_kind, a_outcome, a_ambiguous, a_bid_time, a_bid = a_exit
            b_bid_time, b_bid = _bid_at_horizon(decision_quotes, horizon)
            maturities: list[int] = []
            for row, book, debit, principal, fee in rows:
                arm = row["arm"]
                slippage = Decimal(row["slippage_dollars"])
                if arm == "A":
                    trigger_time, trigger_kind, outcome, ambiguous, bid_time, bid = (
                        a_trigger,
                        a_kind,
                        a_outcome,
                        a_ambiguous,
                        a_bid_time,
                        a_bid,
                    )
                else:
                    trigger_time, trigger_kind, outcome, ambiguous, bid_time, bid = (
                        horizon,
                        "H2",
                        "TIMEOUT_H2",
                        False,
                        b_bid_time,
                        b_bid,
                    )
                book.cash -= debit
                book.reserve += principal
                book.obligation += fee
                row["admission_status"] = "ADMITTED"
                row["fill_status"] = "FILLED"
                row["entry_debit_decimal"] = _canonical_decimal(debit)
                row["exit_trigger_time"] = trigger_time
                row["exit_trigger_kind"] = trigger_kind
                row["exit_bid_time"] = bid_time
                row["exit_bid"] = bid
                missing = bid_time is None
                accounting_time = horizon if missing else bid_time
                bid_decimal = _MONEY_ZERO if missing else Decimal(str(bid))
                credit = Decimal(qty) * (max(bid_decimal - slippage, _MONEY_ZERO) * _HUNDRED - _ENTRY_FEE)
                row["accounting_exit_time"] = accounting_time
                row["exit_credit_decimal"] = _canonical_decimal(credit)
                row["net_decimal"] = _canonical_decimal(credit - debit)
                row["outcome"] = outcome
                row["missing_exit_flag"] = missing
                row["ambiguous_flag"] = ambiguous
                row["label_available_at"] = accounting_time
                row["cash_after_entry_decimal"], row["reserve_after_entry_decimal"], row[
                    "exit_fee_obligation_after_entry_decimal"
                ], row["realized_equity_after_entry_decimal"] = _after_entry_snapshot(book)
                maturities.append(accounting_time)
                action = _Exit(accounting_time, _TICKER_ORDER[ticker], row["ledger_id"], book, row, credit, principal, fee)
                heapq.heappush(exit_heap, (action.time, action.ticker_order, action.ledger_id, action))
            event_updates[_required(intent, "intent_id")] = {
                "terminal_reason": "FILLED",
                "label_available_at": max(maturities),
            }

        while exit_heap:
            _time, _ticker, _ledger, action = heapq.heappop(exit_heap)
            _apply_exit(action)

        ledger.sort(
            key=lambda row: (
                row["event_session_date"],
                _TICKER_ORDER[row["ticker"]],
                row["arm"],
                row["cost"],
                row["ledger_id"],
            )
        )
        return {"ledger": ledger, "event_updates": event_updates}
