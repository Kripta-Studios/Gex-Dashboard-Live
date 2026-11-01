from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("equal_risk_replay", HERE / "replay_equal_risk_frozen.py")
assert SPEC and SPEC.loader
replay = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(replay)


def row(
    candidate_id: str, ticker: str, entry: str, exit_date: str, *,
    decision_ask: float = 1.0, entry_ask: float | None = 1.0, exit_bid: float | None = 1.5,
    right: str = "CALL", ev: float = 1.0, status: str = "OBSERVED_EXIT",
) -> dict:
    ask = 0.0 if entry_ask is None else entry_ask
    bid = 0.0 if exit_bid is None else exit_bid
    return {
        "candidate_id": candidate_id, "ticker": ticker, "right": right,
        "entry_date": entry, "exit_date": exit_date, "decision_ask": decision_ask,
        "entry_ask": entry_ask, "exit_bid": exit_bid, "status": status,
        "entry_debit_base": 0.0 if entry_ask is None else (ask + 0.01) * 100 + 1.30,
        "entry_debit_adverse": 0.0 if entry_ask is None else (ask + 0.02) * 100 + 1.30,
        "net_base": 0.0 if entry_ask is None else (max(bid - 0.01, 0) - ask - 0.01) * 100 - 2.60,
        "net_adverse": 0.0 if entry_ask is None else (max(bid - 0.02, 0) - ask - 0.02) * 100 - 2.60,
        "_ev_base": ev, "_ev_adverse": ev,
    }


def coverage(rows: list[dict], sessions: list[str]) -> dict:
    output = []
    for ticker in replay.TICKERS:
        for day in sessions:
            ids = [item["candidate_id"] for item in rows if item["ticker"] == ticker and item["entry_date"] == day]
            output.append({"ticker": ticker, "entry_date": day, "candidate_ids": ids, "status": "CANDIDATES_BUILT" if ids else "NO_SERIES", "reason": None if ids else "NO_SERIES"})
    return {"rows": output}


def test_quantity_uses_decimal_ceil_whole_contracts_and_both_commissions() -> None:
    quantity, risk = replay.fixed_quantity("1.00001")
    assert risk == 10461
    assert quantity == replay.BUDGET_CENTS // 10461
    assert isinstance(quantity, int) and quantity * risk <= replay.BUDGET_CENTS < (quantity + 1) * risk


def test_entry_adverse_guard_rejects_without_resizing_or_rescue() -> None:
    sessions = ["20260701", "20260702", "20260703"]
    selected = row("selected", "SPY", sessions[0], sessions[2], decision_ask=1.0, entry_ask=1.04, ev=2.0)
    alternative = row("alternative", "SPY", sessions[0], sessions[2], decision_ask=1.0, entry_ask=1.0, right="PUT", ev=1.0)
    books = replay.replay_pair([selected, alternative], coverage([selected, alternative], sessions), sessions, sessions[0], "EV_TOP1_H2")
    for ledger in books.values():
        event = next(item for item in ledger if item.get("candidate_id") == "selected")
        assert event["event"] == "NO_FILL" and event["reason"] == "ENTRY_RISK_BUDGET"
        assert not any(item.get("candidate_id") == "alternative" and item["event"] == "ENTRY" for item in ledger)


def test_common_capital_blocks_both_books_when_only_one_can_afford() -> None:
    sessions = ["20260701", "20260702", "20260703"]
    selected = row("x", "SPY", sessions[0], sessions[2], decision_ask=49.95, entry_ask=49.95)
    books = replay.replay_pair(
        [selected], coverage([selected], sessions), sessions, sessions[0],
        "EV_TOP1_H2", starting_cash=4998.0,
    )
    for ledger in books.values():
        event = next(item for item in ledger if item.get("candidate_id") == "x")
        assert event["event"] == "CAPITAL_BLOCKED" and event["reason"] == "CAPITAL"
        assert not any(item["event"] == "ENTRY" for item in ledger)


def test_existing_exit_fee_obligation_blocks_later_ticker_in_both_books() -> None:
    sessions = ["20260701", "20260702", "20260703"]
    first = row("first", "SPY", sessions[0], sessions[2])
    second = row(
        "second", "QQQ", sessions[0], sessions[2],
        decision_ask=49.0, entry_ask=49.0,
    )
    rows = [first, second]
    books = replay.replay_pair(
        rows, coverage(rows, sessions), sessions, sessions[0],
        "EV_TOP1_H2", starting_cash=9820.0,
    )
    for ledger in books.values():
        assert any(item["event"] == "ENTRY" and item.get("candidate_id") == "first" for item in ledger)
        blocked = next(item for item in ledger if item.get("candidate_id") == "second")
        assert blocked["event"] == "CAPITAL_BLOCKED" and blocked["reason"] == "CAPITAL"


def test_decision_budget_zero_quantity_is_no_fill_without_rescue() -> None:
    sessions = ["20260701", "20260702", "20260703"]
    selected = row("too_large", "SPY", sessions[0], sessions[2], decision_ask=100.0, ev=2.0)
    alternative = row("alternative", "SPY", sessions[0], sessions[2], right="PUT", ev=1.0)
    rows = [selected, alternative]
    books = replay.replay_pair(rows, coverage(rows, sessions), sessions, sessions[0], "EV_TOP1_H2")
    for ledger in books.values():
        event = next(item for item in ledger if item.get("candidate_id") == "too_large")
        assert event["event"] == "NO_FILL" and event["reason"] == "DECISION_RISK_BUDGET"
        assert not any(item["event"] == "ENTRY" for item in ledger)


def test_open_position_waits_and_exit_precedes_same_day_entry() -> None:
    sessions = ["20260701", "20260702", "20260703", "20260706", "20260707"]
    first = row("a", "SPY", sessions[0], sessions[2])
    blocked_by_open = row("b", "SPY", sessions[1], sessions[3])
    after_exit = row("c", "SPY", sessions[2], sessions[4])
    rows = [first, blocked_by_open, after_exit]
    ledger = replay.replay_pair(rows, coverage(rows, sessions), sessions, sessions[2], "EV_TOP1_H2")["adverse"]
    assert any(item["event"] == "WAIT" and item["date"] == sessions[1] and item["reason"] == "OPEN_POSITION" for item in ledger)
    same_day = [item["event"] for item in ledger if item["date"] == sessions[2] and item["ticker"] == "SPY"]
    assert same_day[:2] == ["EXIT", "ENTRY"]


def test_missing_exit_is_quantity_scaled_lower_bound_and_cash_reconciles() -> None:
    sessions = ["20260701", "20260702", "20260703"]
    selected = row("missing", "SPY", sessions[0], sessions[2], exit_bid=None, status="MISSING_EXIT_SOURCE")
    books = replay.replay_pair([selected], coverage([selected], sessions), sessions, sessions[0], "EV_TOP1_H2")
    for cost, ledger in books.items():
        entry = next(item for item in ledger if item["event"] == "ENTRY")
        exit_event = next(item for item in ledger if item["event"] == "EXIT")
        assert exit_event["status"] == "MISSING_EXIT_SOURCE"
        assert exit_event["net_usd"] == pytest.approx(entry["quantity"] * selected[f"net_{cost}"])
        assert exit_event["cash"] == pytest.approx(replay.STARTING_CASH + exit_event["net_usd"])
        assert exit_event["premium_reserved"] == pytest.approx(0)
        assert exit_event["exit_fee_obligation"] == pytest.approx(0)


def test_no_fill_entry_quote_and_abstain_do_not_create_positions() -> None:
    sessions = ["20260701", "20260702", "20260703"]
    no_fill = row("nf", "SPY", sessions[0], sessions[2], entry_ask=None, exit_bid=None, status="NO_FILL")
    filled_policy = replay.replay_pair([no_fill], coverage([no_fill], sessions), sessions, sessions[0], "EV_TOP1_H2")
    abstain = replay.replay_pair([no_fill], coverage([no_fill], sessions), sessions, sessions[0], "ALWAYS_ABSTAIN")
    assert all(any(item["event"] == "NO_FILL" and item["reason"] == "ENTRY_QUOTE" for item in ledger) for ledger in filled_policy.values())
    assert all(not any(item["event"] == "ENTRY" for item in ledger) for ledger in abstain.values())


def test_book_metrics_reports_whole_quantity_and_operational_counts() -> None:
    sessions = ["20260701", "20260702", "20260703"]
    selected = row("x", "SPY", sessions[0], sessions[2])
    ledger = replay.replay_pair([selected], coverage([selected], sessions), sessions, sessions[0], "EV_TOP1_H2")["adverse"]
    metrics = replay.book_metrics(ledger)
    assert metrics["trades"] == 1 and isinstance(metrics["quantity_median"], int)
    assert metrics["quantity_total"] == metrics["quantity_max"] == metrics["quantity_median"]
    assert metrics["max_entry_budget_used_cents"] <= replay.BUDGET_CENTS


def test_implementation_has_no_fit_call_or_sklearn_import() -> None:
    source = (HERE / "replay_equal_risk_frozen.py").read_text(encoding="utf-8")
    assert ".fit(" not in source
    assert "sklearn" not in source
