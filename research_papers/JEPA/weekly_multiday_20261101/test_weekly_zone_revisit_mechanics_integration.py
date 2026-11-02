"""Post-closure synthetic agreement tests for the public D producer/auditor APIs.

This file is intentionally not part of either closed component suite.  It may be
run only after the independently authored auditor has closed its own static and
formal suites; all fixtures are artificial and do not authorize a real adapter.
"""
from datetime import datetime, timedelta

import pytest

from audit_weekly_zone_revisit_mechanics import AuditError, audit_revisit_mechanics
from weekly_zone_revisit_mechanics import evaluate_revisit_mechanics


EPOCH = datetime(1970, 1, 1)
MINUTE = 60_000_000_000
CONFIG = {"evaluation_start_date": "2026-01-02", "evaluation_end_date": "2026-09-17"}
RISK_PIN = "9c387e9bea74ba65777808b5ac5e5fccfdc2437645e7b301c15eab2d33bbeb7b"


def ns(date, hour, minute):
    delta = datetime.fromisoformat(date) + timedelta(hours=hour, minutes=minute) - EPOCH
    return (delta.days * 86400 + delta.seconds) * 1_000_000_000


def plan(identifier="p1", ticker="SPY", ordinal=0, days=("2026-01-02", "2026-01-05", "2026-01-06")):
    result = {
        "calendar_ordinal": ordinal, "plan_id": identifier, "ticker": ticker,
        "trade_date": days[0], "expiry_date": days[2],
        "call_decision_id": identifier + ":CALL", "put_decision_id": identifier + ":PUT",
        "horizon_end_local_ns": ns(days[2], 10, 35), "d_1030_local_ns": ns(days[0], 10, 30),
        "b_plan_pin": "a" * 64, "b_value_pin": "b" * 64,
        "c_anchor_pin": "c" * 64, "c_geometry_pin": "d" * 64,
        "fixed_risk_contract_pin": RISK_PIN, "geometry_status": "AVAILABLE_GEOMETRY",
        "geometry_partition": "ELIGIBLE_ANCHOR_SET", "expected_rth_minutes": [],
    }
    for date, prefix in zip(days, ("d", "d1", "h2")):
        opening = ns(date, 9, 30)
        closing = ns(date, 16, 0)
        result.update({
            prefix + "_session_date": date, prefix + "_session_kind": "FULL",
            prefix + "_rth_open_local_ns": opening, prefix + "_rth_close_local_ns": closing,
        })
        last = result["horizon_end_local_ns"] if prefix == "h2" else closing
        result["expected_rth_minutes"].extend(range(opening, last + MINUTE, MINUTE))
    return result


def anchor(item, identifier="zone", ordinal=0, center=100.0, confluent=True):
    return {
        "plan_id": item["plan_id"], "anchor_id": identifier, "cluster_ordinal": ordinal,
        "center": center, "band": 1.0, "source_mask": 6 if confluent else 2,
        "anchor_available_at_local_ns": item["d_1030_local_ns"], "valid_geometry": True,
        "components": [{"kind": "FIB"}, {"kind": "WALL"}] if confluent else [{"kind": "FIB"}],
        "c_anchor_pin": item["c_anchor_pin"], "c_geometry_pin": item["c_geometry_pin"],
    }


def spot(ticker, moment, value):
    return {
        "ticker": ticker, "time_local_ns": moment,
        "trade_date": (EPOCH + timedelta(seconds=moment // 1_000_000_000)).date().isoformat(),
        "spot": value, "valid_rth": value is not None,
    }


def quote(decision_id, moment, ask=1.0, bid=0.9):
    return {"decision_id": decision_id, "time_local_ns": moment, "ask": ask, "bid": bid}


def spots_for(plans, replacements):
    grid = {(item["ticker"], moment) for item in plans for moment in item["expected_rth_minutes"]}
    return [spot(ticker, moment, replacements.get((ticker, moment), 105.0)) for ticker, moment in sorted(grid)]


def baseline_fixture():
    item = plan()
    start = item["d_1030_local_ns"]
    values = [103.0, 100.0, 103.0, 100.0, 103.0, 104.0, 104.0, 111.0]
    replacements = {("SPY", start + index * MINUTE): value for index, value in enumerate(values)}
    quotes = [
        quote(item["call_decision_id"], start + 6 * MINUTE),
        quote(item["call_decision_id"], start + 8 * MINUTE, 2.2, 2.0),
        quote(item["call_decision_id"], item["horizon_end_local_ns"], 1.0, 0.7),
    ]
    return [item], [anchor(item), anchor(item, "target", 1, 110.0, False)], spots_for([item], replacements), quotes


def produce(data):
    return evaluate_revisit_mechanics(*data, config=CONFIG)


def audit(data, observed):
    result = audit_revisit_mechanics(*data, observed, config=CONFIG)
    assert result["status"] == "PASS_SYNTHETIC_D_MECHANICS_AUDIT"
    return result


def test_baseline_call_has_manual_four_book_nets_and_complete_audit_agreement():
    data = baseline_fixture()
    observed = produce(data)
    event = observed["events"][0]
    expected = {
        ("A", "BASE"): ("4808.1", "9291.9", "4483.8"),
        ("A", "ADVERSE"): ("4855.1", "9244.9", "4389.8"),
        ("B", "BASE"): ("4808.1", "3181.9", "-1626.2"),
        ("B", "ADVERSE"): ("4855.1", "3134.9", "-1720.2"),
    }
    assert observed["status"] == "SYNTHETIC_MECHANICS_ONLY"
    assert (len(event), len(observed["ledger"][0]), len(observed["plan_coverage"][0]), len(observed["counts"])) == (39, 47, 19, 39)
    assert (event["side"], event["terminal_reason"], event["spot_coverage_status"]) == ("CALL", "FILLED", "COMPLETE")
    for row in observed["ledger"]:
        assert (row["entry_debit_decimal"], row["exit_credit_decimal"], row["net_decimal"]) == expected[row["arm"], row["cost"]]
    audited = audit(data, observed)
    assert audited["counts"] == observed["counts"]


def test_put_stop_missing_bid_preserves_negative_exit_fee_in_both_reconstructions():
    item = plan()
    start = item["d_1030_local_ns"]
    values = [97.0, 100.0, 97.0, 100.0, 97.0, 96.0, 96.0, 103.0]
    replacements = {("SPY", start + index * MINUTE): value for index, value in enumerate(values)}
    data = (
        [item], [anchor(item), anchor(item, "target", 1, 90.0, False)], spots_for([item], replacements),
        [quote(item["put_decision_id"], start + 6 * MINUTE), quote(item["put_decision_id"], item["horizon_end_local_ns"], 1.0, None)],
    )
    observed = produce(data)
    assert (observed["events"][0]["side"], observed["events"][0]["terminal_reason"]) == ("PUT", "FILLED")
    for row in observed["ledger"]:
        assert row["missing_exit_flag"] is True
        assert row["exit_bid"] is None
        assert row["exit_credit_decimal"] == "-61.1"
        assert row["net_decimal"] == ("-4869.2" if row["cost"] == "BASE" else "-4916.2")
    assert audit(data, observed)["counts"] == observed["counts"]


def test_p1_a_exit_does_not_release_b_books_before_p2_next_day_entry():
    p1 = plan("p1", ordinal=0)
    p2 = plan("p2", ordinal=1, days=("2026-01-05", "2026-01-06", "2026-01-07"))
    p1_start = p1["d_1030_local_ns"]
    p2_start = p2["d_1030_local_ns"]
    pattern = [103.0, 100.0, 103.0, 100.0, 103.0, 104.0, 104.0, 111.0]
    replacements = {
        ("SPY", start + index * MINUTE): value
        for start in (p1_start, p2_start)
        for index, value in enumerate(pattern)
    }
    quotes = [
        quote(p1["call_decision_id"], p1_start + 6 * MINUTE),
        quote(p1["call_decision_id"], p1_start + 8 * MINUTE, 2.2, 2.0),
        quote(p1["call_decision_id"], p1["horizon_end_local_ns"], 1.0, 0.7),
        quote(p2["call_decision_id"], p2_start + 6 * MINUTE),
    ]
    data = (
        [p1, p2],
        [anchor(p1), anchor(p1, "p1-target", 1, 110.0, False), anchor(p2), anchor(p2, "p2-target", 1, 110.0, False)],
        spots_for([p1, p2], replacements),
        quotes,
    )
    observed = produce(data)
    p1_event, p2_event = observed["events"]
    assert (p1_event["terminal_reason"], p2_event["terminal_reason"]) == ("FILLED", "WAIT")
    p1_a_base = next(row for row in observed["ledger"] if row["intent_id"] == p1_event["intent_id"] and row["arm"] == "A" and row["cost"] == "BASE")
    assert (p1_a_base["exit_bid_time"], p1_a_base["exit_bid"], p1_a_base["net_decimal"]) == (p1_start + 8 * MINUTE, 2.0, "4483.8")
    p2_rows = [row for row in observed["ledger"] if row["intent_id"] == p2_event["intent_id"]]
    assert len(p2_rows) == 4
    assert {(row["admission_status"], row["fill_status"], row["wait_reason"]) for row in p2_rows} == {("WAIT", "NOT_APPLICABLE", "OPEN_POSITION")}
    expected_cash = {
        ("A", "BASE"): "104483.8", ("A", "ADVERSE"): "104389.8",
        ("B", "BASE"): "95191.9", ("B", "ADVERSE"): "95144.9",
    }
    assert {(row["arm"], row["cost"]): row["cash_before_entry_decimal"] for row in p2_rows} == expected_cash
    assert observed["counts"]["open_position_rows"] == 1
    assert audit(data, observed)["counts"] == observed["counts"]


def test_geometry_absence_and_historical_coverage_remain_auditable_populations():
    missing = plan()
    missing.update(geometry_status="MISSING_SOURCE", geometry_partition="C_MISSING_SOURCE")
    no_geometry = ([missing], [], [], [])
    observed_missing = produce(no_geometry)
    assert observed_missing["events"] == []
    assert observed_missing["counts"]["plans_c_missing_geometry"] == 1
    assert audit(no_geometry, observed_missing)["counts"] == observed_missing["counts"]

    historical = plan(days=("2025-12-31", "2026-01-02", "2026-01-05"))
    changes = {}
    for start, values in (
        (historical["d_1030_local_ns"], [103.0, 100.0, 103.0, 100.0, 103.0, 104.0]),
        (ns("2026-01-02", 9, 30), [107.0, 110.0, 107.0, 110.0, 107.0, 106.0]),
    ):
        changes.update({("SPY", start + index * MINUTE): value for index, value in enumerate(values)})
    historical_data = (
        [historical], [anchor(historical), anchor(historical, "second", 1, 110.0), anchor(historical, "target", 2, 120.0, False)],
        spots_for([historical], changes),
        [quote(historical["put_decision_id"], ns("2026-01-02", 9, 36)), quote(historical["put_decision_id"], historical["horizon_end_local_ns"], 1.0, 0.7)],
    )
    observed_historical = produce(historical_data)
    coverage = observed_historical["plan_coverage"][0]
    assert (coverage["outside_evaluation_event_count"], coverage["in_evaluation_event_count"], coverage["economic_intent_count"]) == (1, 1, 1)
    assert audit(historical_data, observed_historical)["counts"] == observed_historical["counts"]


@pytest.mark.parametrize(
    "mutate",
    (
        lambda observed: observed["events"][0].__setitem__("event_id", "0" * 64),
        lambda observed: observed["events"][0].__setitem__("entry_quote_time", observed["events"][0]["entry_quote_time"] + MINUTE),
        lambda observed: observed["ledger"][0].__setitem__("net_decimal", "0"),
        lambda observed: observed["counts"].__setitem__("filled_rows", observed["counts"]["filled_rows"] + 1),
    ),
    ids=("event-id", "entry-clock", "net", "counter"),
)
def test_targeted_observed_mutations_are_rejected(mutate):
    data = baseline_fixture()
    observed = produce(data)
    mutate(observed)
    with pytest.raises(AuditError):
        audit_revisit_mechanics(*data, observed, config=CONFIG)
