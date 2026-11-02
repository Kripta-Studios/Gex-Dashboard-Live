"""Manual artificial-fixture tests for the independent D auditor.

No fixture reads data or producer code.  These tests are intentionally not run
by this hand-off; they document the static candidate's required mutations.
"""
from copy import deepcopy
from datetime import datetime, timedelta
from decimal import Inexact, getcontext
import unittest
import json

from audit_weekly_zone_revisit_mechanics import AuditError, RISK_PIN, audit_revisit_mechanics, reconstruct_revisit_mechanics


PIN = "a" * 64
CONFIG = {"evaluation_start_date": "2026-01-02", "evaluation_end_date": "2026-09-17"}


def _ns(day, hour, minute):
    point = datetime.fromisoformat(day) + timedelta(hours=hour, minutes=minute)
    delta = point - datetime(1970, 1, 1)
    return (delta.days * 86_400 + delta.seconds) * 1_000_000_000 + delta.microseconds * 1_000


def _grid(days):
    result = []
    for index, day in enumerate(days):
        end = (10, 35) if index == 2 else (16, 0)
        at = _ns(day, 9, 30)
        stop = _ns(day, *end)
        while at <= stop:
            result.append(at)
            at += 60_000_000_000
    return result


def _plan():
    days = ("2026-01-02", "2026-01-05", "2026-01-06")
    return {"calendar_ordinal": 0, "plan_id": "p0", "ticker": "SPY", "trade_date": days[0], "expiry_date": days[2], "call_decision_id": "call0", "put_decision_id": "put0", "horizon_end_local_ns": _ns(days[2], 10, 35), "d_1030_local_ns": _ns(days[0], 10, 30), "d_session_date": days[0], "d1_session_date": days[1], "h2_session_date": days[2], "d_session_kind": "FULL", "d1_session_kind": "FULL", "h2_session_kind": "FULL", "d_rth_open_local_ns": _ns(days[0], 9, 30), "d_rth_close_local_ns": _ns(days[0], 16, 0), "d1_rth_open_local_ns": _ns(days[1], 9, 30), "d1_rth_close_local_ns": _ns(days[1], 16, 0), "h2_rth_open_local_ns": _ns(days[2], 9, 30), "h2_rth_close_local_ns": _ns(days[2], 16, 0), "expected_rth_minutes": _grid(days), "b_plan_pin": PIN, "b_value_pin": PIN, "c_anchor_pin": PIN, "c_geometry_pin": PIN, "fixed_risk_contract_pin": RISK_PIN, "geometry_status": "AVAILABLE_GEOMETRY", "geometry_partition": "ELIGIBLE_ANCHOR_SET"}


def _anchor(identifier, cluster, center, kinds=("FIB", "WALL")):
    return {"plan_id": "p0", "anchor_id": identifier, "cluster_ordinal": cluster, "center": float(center), "band": 1.0, "source_mask": 3, "anchor_available_at_local_ns": _ns("2026-01-02", 10, 30), "valid_geometry": True, "components": [{"kind": x} for x in kinds], "c_anchor_pin": PIN, "c_geometry_pin": PIN}


def _spots(plan, values):
    out = []
    for t in plan["expected_rth_minutes"]:
        value = values.get(t, 105.0)
        out.append({"ticker": "SPY", "time_local_ns": t, "trade_date": (datetime(1970, 1, 1) + timedelta(microseconds=t // 1000)).date().isoformat(), "spot": value if value is not None else None, "valid_rth": value is not None})
    return out


def _quotes(values):
    return [{"decision_id": d, "time_local_ns": t, "ask": ask, "bid": bid} for d, t, ask, bid in sorted(values)]


def _d_time(hour, minute):
    return _ns("2026-01-02", hour, minute)


def _h2_time(hour, minute):
    return _ns("2026-01-06", hour, minute)


def _d1_time(hour, minute):
    return _ns("2026-01-05", hour, minute)


def _fixture():
    plan = _plan()
    values = {_d_time(10, 30): 103.0, _d_time(10, 31): 100.0, _d_time(10, 32): 103.0, _d_time(10, 33): 100.0, _d_time(10, 34): 103.0, _d_time(10, 35): 104.0, _d_time(10, 36): 104.0, _d_time(10, 37): 106.0}
    quotes = _quotes([("call0", _d_time(10, 38), 1.0, 0.9), ("call0", _d_time(10, 39), 1.0, 0.8), ("call0", plan["horizon_end_local_ns"], 1.0, 0.7)])
    return plan, [_anchor("a0", 0, 100), _anchor("a1", 1, 110, ("FIB",))], _spots(plan, values), quotes


def _three_ticker_fixture():
    plan, anchors, spots, quotes = _fixture()
    plans = []
    all_anchors = []
    all_spots = []
    all_quotes = []
    for ordinal, ticker in enumerate(("SPY", "QQQ", "SPXW")):
        current = deepcopy(plan)
        current["calendar_ordinal"] = ordinal
        current["plan_id"] = "p" + str(ordinal)
        current["ticker"] = ticker
        current["call_decision_id"] = "call" + str(ordinal)
        current["put_decision_id"] = "put" + str(ordinal)
        plans.append(current)
        for source in anchors:
            item = deepcopy(source)
            item["plan_id"] = current["plan_id"]
            all_anchors.append(item)
        for source in spots:
            item = deepcopy(source)
            item["ticker"] = ticker
            all_spots.append(item)
        for source in quotes:
            item = deepcopy(source)
            item["decision_id"] = current["call_decision_id"]
            all_quotes.append(item)
    return (
        sorted(plans, key=lambda item: (item["calendar_ordinal"], item["plan_id"])),
        sorted(all_anchors, key=lambda item: (item["plan_id"], item["cluster_ordinal"], item["anchor_id"])),
        sorted(all_spots, key=lambda item: (item["ticker"], item["time_local_ns"])),
        sorted(all_quotes, key=lambda item: (item["decision_id"], item["time_local_ns"])),
    )


def _plan_for_days(ordinal, plan_id, ticker, days):
    plan = _plan()
    plan["calendar_ordinal"] = ordinal
    plan["plan_id"] = plan_id
    plan["ticker"] = ticker
    plan["call_decision_id"] = plan_id + "-call"
    plan["put_decision_id"] = plan_id + "-put"
    plan["trade_date"] = days[0]
    plan["expiry_date"] = days[2]
    plan["d_session_date"] = days[0]
    plan["d1_session_date"] = days[1]
    plan["h2_session_date"] = days[2]
    for prefix, day in zip(("d", "d1", "h2"), days):
        plan[prefix + "_rth_open_local_ns"] = _ns(day, 9, 30)
        plan[prefix + "_rth_close_local_ns"] = _ns(day, 16, 0)
    plan["d_1030_local_ns"] = _ns(days[0], 10, 30)
    plan["horizon_end_local_ns"] = _ns(days[2], 10, 35)
    plan["expected_rth_minutes"] = _grid(days)
    return plan


def _anchor_for(plan, identifier, cluster, center, kinds=("FIB", "WALL")):
    anchor = _anchor(identifier, cluster, center, kinds)
    anchor["plan_id"] = plan["plan_id"]
    anchor["anchor_available_at_local_ns"] = plan["d_1030_local_ns"]
    return anchor


def _date_for_ns(value):
    return (datetime(1970, 1, 1) + timedelta(microseconds=value // 1_000)).date().isoformat()


def _spot_rows(ticker, plans, values):
    times = sorted({time for plan in plans for time in plan["expected_rth_minutes"]})
    rows = []
    for time in times:
        spot = values.get(time, 105.0)
        rows.append({
            "ticker": ticker,
            "time_local_ns": time,
            "trade_date": _date_for_ns(time),
            "spot": spot,
            "valid_rth": spot is not None,
        })
    return rows


def _confirmation_values(plan):
    day = plan["d_session_date"]
    return {
        _ns(day, 10, 30): 103.0,
        _ns(day, 10, 31): 100.0,
        _ns(day, 10, 32): 103.0,
        _ns(day, 10, 33): 100.0,
        _ns(day, 10, 34): 103.0,
        _ns(day, 10, 35): 103.0,
    }


def _weekdays(start, count):
    current = datetime.fromisoformat(start)
    result = []
    while len(result) < count:
        if current.weekday() < 5:
            result.append(current.date().isoformat())
        current += timedelta(days=1)
    return result


class TestIndependentSyntheticAuditor(unittest.TestCase):
    def test_manual_projection_and_independent_audit(self):
        plan, anchors, spots, quotes = _fixture()
        result = reconstruct_revisit_mechanics([plan], anchors, spots, quotes, config={"evaluation_start_date": "2026-01-02", "evaluation_end_date": "2026-09-17"})
        self.assertEqual(result["status"], "SYNTHETIC_MECHANICS_ONLY")
        self.assertEqual(len(result["events"]), 1)
        self.assertIsNotNone(result["events"][0]["event_id"])
        self.assertEqual(len(result["ledger"]), 4)
        self.assertEqual(result["counts"]["common_intent_rows"], 1)
        base_a = next(row for row in result["ledger"] if row["arm"] == "A" and row["cost"] == "BASE")
        # q=500000//10460=47; principal, entry commission, reserved
        # exit commission and net are independently hand-calculated here.
        self.assertEqual((base_a["qty"], base_a["entry_debit_decimal"], base_a["cash_after_entry_decimal"], base_a["reserve_after_entry_decimal"], base_a["exit_fee_obligation_after_entry_decimal"], base_a["exit_credit_decimal"], base_a["net_decimal"]), (47, "4808.1", "95191.9", "4747", "61.1", "3181.9", "-1626.2"))
        self.assertEqual(audit_revisit_mechanics([plan], anchors, spots, quotes, result, config={"evaluation_start_date": "2026-01-02", "evaluation_end_date": "2026-09-17"})["status"], "PASS_SYNTHETIC_D_MECHANICS_AUDIT")

    def test_manual_negative_mutations_are_rejected(self):
        for mutation in ("post_h", "causal", "quantity", "accounting", "coverage", "identifier"):
            with self.subTest(mutation=mutation):
                plan, anchors, spots, quotes = _fixture()
                config = {"evaluation_start_date": "2026-01-02", "evaluation_end_date": "2026-09-17"}
                observed = reconstruct_revisit_mechanics([plan], anchors, spots, quotes, config=config)
                if mutation == "post_h":
                    # A post-H quote does not alter reconstruction; tampering the matured output does.
                    observed["events"][0]["label_available_at"] += 1
                elif mutation == "causal":
                    observed["events"][0]["confirmation_time"] -= 60_000_000_000
                elif mutation == "quantity":
                    observed["ledger"][0]["qty"] += 1
                elif mutation == "accounting":
                    observed["ledger"][0]["net_decimal"] = "0"
                elif mutation == "coverage":
                    observed["plan_coverage"][0]["eligible_anchor_count"] = 99
                else:
                    observed["events"][0]["revisit_id"] = "0" * 64
                with self.assertRaises(AuditError):
                    audit_revisit_mechanics([plan], anchors, spots, quotes, observed, config=config)

    def test_post_h_quote_is_future_invariant_and_clock_is_fixed(self):
        plan, anchors, spots, quotes = _fixture()
        config = {"evaluation_start_date": "2026-01-02", "evaluation_end_date": "2026-09-17"}
        baseline = reconstruct_revisit_mechanics([plan], anchors, spots, quotes, config=config)
        future = quotes + [{"decision_id": "call0", "time_local_ns": plan["horizon_end_local_ns"] + 60_000_000_000, "ask": 0.5, "bid": 0.4}]
        self.assertEqual(reconstruct_revisit_mechanics([plan], anchors, spots, future, config=config), baseline)
        with self.assertRaises(AuditError):
            reconstruct_revisit_mechanics([plan], anchors, spots, quotes, config={"evaluation_start_date": "2026-01-03", "evaluation_end_date": "2026-09-17"})

    def test_pre_fill_trigger_beats_later_quote_and_qty_zero_is_preserved(self):
        plan, anchors, spots, quotes = _fixture()
        config = {"evaluation_start_date": "2026-01-02", "evaluation_end_date": "2026-09-17"}
        # The target is 110; this observed trigger precedes the first valid ask.
        for record in spots:
            if record["time_local_ns"] == _d_time(10, 37):
                record["spot"] = 111.0
        cancelled = reconstruct_revisit_mechanics([plan], anchors, spots, quotes, config=config)
        self.assertEqual(cancelled["events"][0]["terminal_reason"], "PRE_FILL_TRIGGER_CANCELLED")
        self.assertEqual(cancelled["ledger"], [])
        annotation = json.loads(cancelled["events"][0]["transition_trace_json"])[-1]
        self.assertEqual((annotation["kind"], annotation["reason"], annotation["state_before"], annotation["state_after"], annotation["spot_f64"]), ("PRE_FILL_TRIGGER_CANCELLED", "TRIGGER_PRE_FILL", "CONFIRMED", "TERMINAL", float(111.0).hex()))
        plan, anchors, spots, quotes = _fixture()
        for quote in quotes:
            if quote["decision_id"] == "call0" and quote["time_local_ns"] < plan["horizon_end_local_ns"]:
                quote["ask"] = 1000.0
                quote["bid"] = 999.0
        zero = reconstruct_revisit_mechanics([plan], anchors, spots, quotes, config=config)
        self.assertEqual(zero["events"][0]["terminal_reason"], "NO_FILL")
        self.assertEqual({row["admission_status"] for row in zero["ledger"]}, {"EVENT_RISK_BUDGET"})

    def test_manual_reset_missing_cross_and_exact_h_traces(self):
        plan, anchors, spots, quotes = _fixture()
        config = {"evaluation_start_date": "2026-01-02", "evaluation_end_date": "2026-09-17"}
        # Explicit observed intermediate minute interrupts CONFIRM_ONE and
        # cannot simultaneously start another streak.
        for record in spots:
            if record["time_local_ns"] == _d_time(10, 35):
                record["spot"] = 101.5
        reset = reconstruct_revisit_mechanics([plan], anchors, spots, quotes, config=config)
        trace = json.loads(reset["events"][0]["transition_trace_json"])
        reset_rows = [x for x in trace if x["kind"] == "CONFIRMATION_RESET"]
        self.assertEqual(len(reset_rows), 1)
        self.assertEqual((reset_rows[0]["reason"], reset_rows[0]["state_after"], reset_rows[0]["spot_f64"]), ("NON_CONFIRMING_OBSERVATION", "REVISITED_ABOVE", float(101.5).hex()))

        plan, anchors, spots, quotes = _fixture()
        for record in spots:
            if record["time_local_ns"] == _d_time(10, 35):
                record["spot"] = None
                record["valid_rth"] = False
        missing = reconstruct_revisit_mechanics([plan], anchors, spots, quotes, config=config)
        trace = json.loads(missing["events"][0]["transition_trace_json"])
        self.assertEqual([(x["kind"], x["spot_f64"], x["reason"]) for x in trace if x["kind"] == "MISSING_MINUTE"], [("MISSING_MINUTE", None, "MISSING_RTH_MINUTE")])

    def test_manual_exact_h_and_strict_type_rejection(self):
        plan, anchors, spots, quotes = _fixture()
        config = {"evaluation_start_date": "2026-01-02", "evaluation_end_date": "2026-09-17"}
        # Leave D armed; complete visit/departure/revisit/two-minute sequence
        # precisely at H2.  The event remains coverage but is TOO_LATE.
        values = {_h2_time(10, 31): 100.0, _h2_time(10, 32): 103.0, _h2_time(10, 33): 100.0, _h2_time(10, 34): 103.0, _h2_time(10, 35): 103.0}
        for record in spots:
            record["spot"] = 105.0
            if record["time_local_ns"] in values:
                record["spot"] = values[record["time_local_ns"]]
        late = reconstruct_revisit_mechanics([plan], anchors, spots, quotes, config=config)
        self.assertEqual((late["events"][0]["terminal_reason"], late["events"][0]["option_coverage_status"]), ("TOO_LATE", "TOO_LATE"))
        observed = reconstruct_revisit_mechanics([_plan()], [_anchor("a0", 0, 100), _anchor("a1", 1, 110, ("FIB",))], _spots(_plan(), {}), [], config=config)
        observed["counts"]["plan_rows"] = True
        with self.assertRaises(AuditError):
            audit_revisit_mechanics([_plan()], [_anchor("a0", 0, 100), _anchor("a1", 1, 110, ("FIB",))], _spots(_plan(), {}), [], observed, config=config)

    def test_schema_type_range_and_foreign_key_matrix(self):
        """All 39/47/19 record shapes and the 39 count types reject drift."""
        plan, anchors, spots, quotes = _fixture()
        result = reconstruct_revisit_mechanics([plan], anchors, spots, quotes, config=CONFIG)
        cases = []
        malformed_event = deepcopy(result)
        malformed_event["events"][0]["calendar_ordinal"] = True
        cases.append(malformed_event)
        malformed_event = deepcopy(result)
        malformed_event["events"][0]["transition_trace_json"] = "{}"
        cases.append(malformed_event)
        malformed_ledger = deepcopy(result)
        malformed_ledger["ledger"][0]["cash_before_entry_decimal"] = 100000.0
        cases.append(malformed_ledger)
        malformed_ledger = deepcopy(result)
        malformed_ledger["ledger"][0]["event_id"] = "0" * 64
        cases.append(malformed_ledger)
        malformed_coverage = deepcopy(result)
        malformed_coverage["plan_coverage"][0]["terminal_status_counts_json"] = "{}"
        cases.append(malformed_coverage)
        for count_name in result["counts"]:
            malformed_counts = deepcopy(result)
            malformed_counts["counts"][count_name] = True
            cases.append(malformed_counts)
        for observed in cases:
            with self.subTest(observed=observed):
                with self.assertRaises(AuditError):
                    audit_revisit_mechanics([plan], anchors, spots, quotes, observed, config=CONFIG)
        for collection, index in (("events", 0), ("ledger", 0), ("plan_coverage", 0)):
            for field in result[collection][index]:
                observed = deepcopy(result)
                observed[collection][index][field] = object()
                with self.subTest(collection=collection, field=field):
                    with self.assertRaises(AuditError):
                        audit_revisit_mechanics([plan], anchors, spots, quotes, observed, config=CONFIG)

    def test_rearm_clears_scalar_attempt_fields_and_cross_has_no_rescue(self):
        plan, anchors, spots, quotes = _fixture()
        for record in spots:
            if record["time_local_ns"] == _d_time(10, 31):
                record["spot"] = 100.0
            elif record["time_local_ns"] == _d_time(10, 32):
                record["spot"] = 97.0
            elif record["time_local_ns"] == _d_time(10, 33):
                record["spot"] = 103.0
        result = reconstruct_revisit_mechanics([plan], anchors, spots, quotes, config=CONFIG)
        row = result["events"][0]
        self.assertEqual(row["event_status"], "ARMED")
        self.assertEqual(row["armed_side"], "ABOVE")
        self.assertIsNone(row["visit_time"])
        self.assertIsNone(row["departure_time"])
        trace = json.loads(row["transition_trace_json"])
        self.assertEqual([item["kind"] for item in trace].count("CROSS_THROUGH"), 1)
        self.assertEqual(trace[-1]["kind"], "ARMED_ABOVE")

    def test_session_boundary_and_nonconfirming_reset_are_distinct(self):
        plan = _plan()
        anchors = [_anchor("a0", 0, 100), _anchor("a1", 1, 110, ("FIB",))]
        spots = _spots(plan, {})
        quotes = []
        values = {
            _d_time(15, 57): 100.0,
            _d_time(15, 58): 103.0,
            _d_time(15, 59): 100.0,
            _d_time(16, 0): 103.0,
            _d1_time(9, 30): 103.0,
        }
        for record in spots:
            if record["time_local_ns"] in values:
                record["spot"] = values[record["time_local_ns"]]
        result = reconstruct_revisit_mechanics([plan], anchors, spots, quotes, config=CONFIG)
        trace = json.loads(result["events"][0]["transition_trace_json"])
        boundary = [item for item in trace if item["kind"] == "SESSION_BREAK"]
        self.assertEqual(len(boundary), 1)
        self.assertEqual((boundary[0]["time_local_ns"], boundary[0]["reason"]), (_d1_time(9, 30), "SESSION_BOUNDARY"))

    def test_missing_bid_zero_bid_and_exit_fee_are_not_collapsed(self):
        plan, anchors, spots, quotes = _fixture()
        zero_quotes = deepcopy(quotes)
        for quote in zero_quotes:
            if quote["time_local_ns"] == plan["horizon_end_local_ns"]:
                quote["bid"] = 0.0
        zero = reconstruct_revisit_mechanics([plan], anchors, spots, zero_quotes, config=CONFIG)
        zero_a = next(row for row in zero["ledger"] if row["arm"] == "A" and row["cost"] == "ADVERSE")
        self.assertFalse(zero_a["missing_exit_flag"])
        self.assertEqual(zero_a["exit_bid"], 0.0)
        self.assertEqual(zero_a["exit_credit_decimal"], "-61.1")
        missing_quotes = deepcopy(zero_quotes)
        for quote in missing_quotes:
            if quote["time_local_ns"] == plan["horizon_end_local_ns"]:
                quote["bid"] = None
        missing = reconstruct_revisit_mechanics([plan], anchors, spots, missing_quotes, config=CONFIG)
        missing_a = next(row for row in missing["ledger"] if row["arm"] == "A" and row["cost"] == "ADVERSE")
        self.assertTrue(missing_a["missing_exit_flag"])
        self.assertIsNone(missing_a["exit_bid"])
        self.assertEqual(missing_a["exit_credit_decimal"], "-61.1")

    def test_three_ticker_execution_order_and_lexical_ledger_projection(self):
        plans, anchors, spots, quotes = _three_ticker_fixture()
        result = reconstruct_revisit_mechanics(plans, anchors, spots, quotes, config=CONFIG)
        self.assertEqual(result["counts"]["common_intent_rows"], 3)
        output_tickers = [row["ticker"] for row in result["ledger"]]
        self.assertEqual(output_tickers, sorted(output_tickers))
        qqq_base = next(row for row in result["ledger"] if row["ticker"] == "QQQ" and row["arm"] == "A" and row["cost"] == "BASE")
        spy_base = next(row for row in result["ledger"] if row["ticker"] == "SPY" and row["arm"] == "A" and row["cost"] == "BASE")
        self.assertEqual(spy_base["cash_before_entry_decimal"], "100000")
        self.assertEqual(qqq_base["cash_before_entry_decimal"], spy_base["cash_after_entry_decimal"])

    def test_geometry_no_trade_historical_event_and_future_invariance(self):
        plan, anchors, spots, quotes = _fixture()
        missing_only = _plan()
        missing_only["geometry_status"] = "MISSING_SOURCE"
        missing_only["geometry_partition"] = "C_MISSING_SOURCE"
        no_trade = reconstruct_revisit_mechanics([missing_only], [], _spots(missing_only, {}), [], config=CONFIG)
        self.assertEqual((no_trade["events"], no_trade["ledger"], no_trade["plan_coverage"][0]["geometry_partition"]), ([], [], "C_MISSING_SOURCE"))
        no_geometry = deepcopy(plan)
        no_geometry["geometry_status"] = "MISSING_SOURCE"
        no_geometry["geometry_partition"] = "C_MISSING_SOURCE"
        no_geometry["plan_id"] = "missing"
        no_geometry["call_decision_id"] = "missing-call"
        no_geometry["put_decision_id"] = "missing-put"
        no_geometry["calendar_ordinal"] = 1
        no_geometry["ticker"] = "QQQ"
        no_geometry["trade_date"] = "2026-01-09"
        no_geometry["d_session_date"] = "2026-01-09"
        # The malformed calendar mutation is deliberately rejected rather than
        # inferred; a genuine missing-geometry fixture must carry its own grid.
        with self.assertRaises(AuditError):
            reconstruct_revisit_mechanics([plan, no_geometry], anchors, spots, quotes, config=CONFIG)
        baseline = reconstruct_revisit_mechanics([plan], anchors, spots, quotes, config=CONFIG)
        future = deepcopy(quotes)
        future.append({"decision_id": "call0", "time_local_ns": plan["horizon_end_local_ns"] + 60_000_000_000, "ask": 0.1, "bid": 0.0})
        self.assertEqual(reconstruct_revisit_mechanics([plan], anchors, spots, future, config=CONFIG), baseline)

    def test_invalid_shapes_integer_clock_and_float_inputs_reject(self):
        plan, anchors, spots, quotes = _fixture()
        bad_plan = deepcopy(plan)
        bad_plan["calendar_ordinal"] = True
        with self.assertRaises(AuditError):
            reconstruct_revisit_mechanics([bad_plan], anchors, spots, quotes, config=CONFIG)
        bad_anchor = deepcopy(anchors)
        bad_anchor[0]["valid_geometry"] = 1
        with self.assertRaises(AuditError):
            reconstruct_revisit_mechanics([plan], bad_anchor, spots, quotes, config=CONFIG)
        bad_spots = deepcopy(spots)
        bad_spots[0]["spot"] = float("nan")
        with self.assertRaises(AuditError):
            reconstruct_revisit_mechanics([plan], anchors, bad_spots, quotes, config=CONFIG)
        bad_quotes = deepcopy(quotes)
        bad_quotes[0]["time_local_ns"] = True
        with self.assertRaises(AuditError):
            reconstruct_revisit_mechanics([plan], anchors, spots, bad_quotes, config=CONFIG)

    def test_capital_exhaustion_is_common_across_all_four_books(self):
        """Twenty realised synthetic losses leave only 28/8 cash; the 21st waits."""
        weekdays = _weekdays("2026-01-02", 63)
        plans = []
        anchors = []
        values = {}
        quotes = []
        for index in range(21):
            days = tuple(weekdays[index * 3:index * 3 + 3])
            plan = _plan_for_days(index, "capital-" + str(index), "SPY", days)
            plans.append(plan)
            anchors.extend((
                _anchor_for(plan, "main", 0, 100.0),
                _anchor_for(plan, "target", 1, 110.0, ("FIB",)),
            ))
            values.update(_confirmation_values(plan))
            quotes.extend((
                {"decision_id": plan["call_decision_id"], "time_local_ns": _ns(days[0], 10, 36), "ask": 49.95, "bid": 49.0},
                {"decision_id": plan["call_decision_id"], "time_local_ns": plan["horizon_end_local_ns"], "ask": 1.0, "bid": 0.0},
            ))
        spots = _spot_rows("SPY", plans, values)
        result = reconstruct_revisit_mechanics(plans, sorted(anchors, key=lambda item: (item["plan_id"], item["cluster_ordinal"], item["anchor_id"])), spots, sorted(quotes, key=lambda item: (item["decision_id"], item["time_local_ns"])), config=CONFIG)
        self.assertEqual((result["counts"]["common_intent_rows"], result["counts"]["admitted_intent_rows"], result["counts"]["capital_blocked_rows"], result["counts"]["wait_rows"]), (21, 20, 1, 1))
        blocked = [row for row in result["ledger"] if row["plan_id"] == "capital-20"]
        self.assertEqual(len(blocked), 4)
        expected_cash = {
            ("A", "BASE"): "28",
            ("A", "ADVERSE"): "8",
            ("B", "BASE"): "28",
            ("B", "ADVERSE"): "8",
        }
        for row in blocked:
            with self.subTest(book=(row["arm"], row["cost"])):
                self.assertEqual((row["admission_status"], row["fill_status"], row["wait_reason"], row["qty"]), ("WAIT", "NOT_APPLICABLE", "CAPITAL_BLOCKED", 1))
                self.assertEqual((row["cash_before_entry_decimal"], row["reserve_before_entry_decimal"], row["exit_fee_obligation_before_decimal"], row["realized_equity_before_decimal"]), (expected_cash[(row["arm"], row["cost"])], "0", "0", expected_cash[(row["arm"], row["cost"])]))

    def test_b_lockout_survives_a_exit_for_same_ticker(self):
        first = _plan_for_days(0, "lock-first", "SPY", ("2026-01-02", "2026-01-05", "2026-01-06"))
        second = _plan_for_days(1, "lock-second", "SPY", ("2026-01-05", "2026-01-06", "2026-01-07"))
        anchors = [
            _anchor_for(first, "main", 0, 100.0),
            _anchor_for(first, "target", 1, 110.0, ("FIB",)),
            _anchor_for(second, "main", 0, 100.0),
            _anchor_for(second, "target", 1, 110.0, ("FIB",)),
        ]
        values = _confirmation_values(first)
        values[_ns("2026-01-02", 10, 37)] = 111.0
        values.update(_confirmation_values(second))
        quotes = [
            {"decision_id": first["call_decision_id"], "time_local_ns": _ns("2026-01-02", 10, 36), "ask": 1.0, "bid": 0.9},
            {"decision_id": first["call_decision_id"], "time_local_ns": _ns("2026-01-02", 10, 38), "ask": 1.0, "bid": 0.9},
            {"decision_id": first["call_decision_id"], "time_local_ns": first["horizon_end_local_ns"], "ask": 1.0, "bid": 0.7},
            {"decision_id": second["call_decision_id"], "time_local_ns": _ns("2026-01-05", 10, 36), "ask": 1.0, "bid": 0.9},
            {"decision_id": second["call_decision_id"], "time_local_ns": second["horizon_end_local_ns"], "ask": 1.0, "bid": 0.7},
        ]
        result = reconstruct_revisit_mechanics([first, second], anchors, _spot_rows("SPY", [first, second], values), sorted(quotes, key=lambda item: (item["decision_id"], item["time_local_ns"])), config=CONFIG)
        second_rows = [row for row in result["ledger"] if row["plan_id"] == "lock-second"]
        self.assertEqual(len(second_rows), 4)
        expected_before = {
            ("A", "BASE"): ("99313.8", "0", "0", "99313.8"),
            ("A", "ADVERSE"): ("99219.8", "0", "0", "99219.8"),
            ("B", "BASE"): ("95191.9", "4747", "61.1", "99938.9"),
            ("B", "ADVERSE"): ("95144.9", "4794", "61.1", "99938.9"),
        }
        for row in second_rows:
            with self.subTest(book=(row["arm"], row["cost"])):
                self.assertEqual((row["admission_status"], row["fill_status"], row["wait_reason"]), ("WAIT", "NOT_APPLICABLE", "OPEN_POSITION"))
                self.assertEqual(tuple(row[key] for key in ("cash_before_entry_decimal", "reserve_before_entry_decimal", "exit_fee_obligation_before_decimal", "realized_equity_before_decimal")), expected_before[(row["arm"], row["cost"])])

    def test_exit_precedes_equal_time_entry_with_four_book_balances(self):
        days = ("2026-01-02", "2026-01-05", "2026-01-06")
        spy = _plan_for_days(0, "tie-spy", "SPY", days)
        qqq = _plan_for_days(1, "tie-qqq", "QQQ", days)
        anchors = [
            _anchor_for(spy, "main", 0, 100.0),
            _anchor_for(spy, "target", 1, 110.0, ("FIB",)),
            _anchor_for(qqq, "main", 0, 100.0),
            _anchor_for(qqq, "target", 1, 110.0, ("FIB",)),
        ]
        spy_values = _confirmation_values(spy)
        spy_values[_ns(days[0], 10, 37)] = 111.0
        qqq_values = _confirmation_values(qqq)
        quotes = [
            {"decision_id": spy["call_decision_id"], "time_local_ns": _ns(days[0], 10, 36), "ask": 1.0, "bid": 0.9},
            {"decision_id": spy["call_decision_id"], "time_local_ns": _ns(days[0], 10, 38), "ask": 1.0, "bid": 0.9},
            {"decision_id": spy["call_decision_id"], "time_local_ns": spy["horizon_end_local_ns"], "ask": 1.0, "bid": 0.7},
            {"decision_id": qqq["call_decision_id"], "time_local_ns": _ns(days[0], 10, 38), "ask": 1.0, "bid": 0.9},
            {"decision_id": qqq["call_decision_id"], "time_local_ns": qqq["horizon_end_local_ns"], "ask": 1.0, "bid": 0.7},
        ]
        spots = _spot_rows("SPY", [spy], spy_values) + _spot_rows("QQQ", [qqq], qqq_values)
        result = reconstruct_revisit_mechanics([spy, qqq], sorted(anchors, key=lambda item: (item["plan_id"], item["cluster_ordinal"], item["anchor_id"])), sorted(spots, key=lambda item: (item["ticker"], item["time_local_ns"])), sorted(quotes, key=lambda item: (item["decision_id"], item["time_local_ns"])), config=CONFIG)
        qqq_rows = [row for row in result["ledger"] if row["plan_id"] == "tie-qqq"]
        expected_before = {
            ("A", "BASE"): ("99313.8", "0", "0", "99313.8"),
            ("A", "ADVERSE"): ("99219.8", "0", "0", "99219.8"),
            ("B", "BASE"): ("95191.9", "4747", "61.1", "99938.9"),
            ("B", "ADVERSE"): ("95144.9", "4794", "61.1", "99938.9"),
        }
        for row in qqq_rows:
            with self.subTest(book=(row["arm"], row["cost"])):
                self.assertEqual((row["admission_status"], row["fill_status"]), ("ADMITTED", "FILLED"))
                self.assertEqual(tuple(row[key] for key in ("cash_before_entry_decimal", "reserve_before_entry_decimal", "exit_fee_obligation_before_decimal", "realized_equity_before_decimal")), expected_before[(row["arm"], row["cost"])])

    def test_physical_winner_no_rescue_is_not_an_fsm_cross(self):
        old = _plan_for_days(0, "winner-old", "SPY", ("2026-01-02", "2026-01-05", "2026-01-06"))
        new = _plan_for_days(1, "winner-new", "SPY", ("2026-01-05", "2026-01-06", "2026-01-07"))
        values = {
            _ns("2026-01-02", 10, 31): 100.0,
            _ns("2026-01-02", 10, 32): 103.0,
            _ns("2026-01-05", 9, 30): 100.0,
            _ns("2026-01-05", 9, 31): 103.0,
            _ns("2026-01-05", 9, 32): 103.0,
        }
        values.update(_confirmation_values(new))
        anchors = [
            _anchor_for(old, "only", 0, 100.0),
            _anchor_for(new, "main", 0, 100.0),
            _anchor_for(new, "target", 1, 110.0, ("FIB",)),
        ]
        quotes = [
            {"decision_id": new["call_decision_id"], "time_local_ns": _ns("2026-01-05", 10, 36), "ask": 1.0, "bid": 0.9},
            {"decision_id": new["call_decision_id"], "time_local_ns": new["horizon_end_local_ns"], "ask": 1.0, "bid": 0.7},
        ]
        result = reconstruct_revisit_mechanics([old, new], sorted(anchors, key=lambda item: (item["plan_id"], item["cluster_ordinal"], item["anchor_id"])), _spot_rows("SPY", [old, new], values), quotes, config=CONFIG)
        by_plan = {row["plan_id"]: row for row in result["events"]}
        self.assertEqual((by_plan["winner-old"]["terminal_reason"], by_plan["winner-new"]["terminal_reason"], result["ledger"]), ("NO_TARGET", "SUPERSEDED_FIRST_EVENT", []))
        self.assertEqual((result["counts"]["no_target_rows"], result["counts"]["superseded_first_event_rows"], result["counts"]["common_intent_rows"]), (1, 1, 0))
        new_trace_kinds = [item["kind"] for item in json.loads(by_plan["winner-new"]["transition_trace_json"])]
        self.assertNotIn("CROSS_THROUGH", new_trace_kinds)

    def test_decimal_rounding_and_global_context_independence(self):
        plan, anchors, spots, quotes = _fixture()
        for quote in quotes:
            if quote["time_local_ns"] == _d_time(10, 38):
                quote["ask"] = 1.0001
                quote["bid"] = 1.0
        context = getcontext()
        original_precision = context.prec
        original_inexact = context.traps[Inexact]
        context.prec = 7
        context.traps[Inexact] = True
        try:
            result = reconstruct_revisit_mechanics([plan], anchors, spots, quotes, config=CONFIG)
        finally:
            context.prec = original_precision
            context.traps[Inexact] = original_inexact
        base = next(row for row in result["ledger"] if row["arm"] == "A" and row["cost"] == "BASE")
        adverse = next(row for row in result["ledger"] if row["arm"] == "A" and row["cost"] == "ADVERSE")
        self.assertEqual((base["unit_risk_cents"], base["qty"], base["entry_debit_decimal"], adverse["entry_debit_decimal"]), (10461, 47, "4808.57", "4855.57"))

    def test_canonical_dates_exact_config_anchor_pins_and_trace_hex_reject(self):
        plan, anchors, spots, quotes = _fixture()
        week_date = deepcopy(plan)
        week_date["expiry_date"] = "2026-W01-1"
        with self.assertRaises(AuditError):
            reconstruct_revisit_mechanics([week_date], anchors, spots, quotes, config=CONFIG)

        class EqualDate(str):
            def __eq__(self, other):
                return True

        bad_config = deepcopy(CONFIG)
        bad_config["evaluation_start_date"] = EqualDate("not-a-date")
        with self.assertRaises(AuditError):
            reconstruct_revisit_mechanics([plan], anchors, spots, quotes, config=bad_config)

        class EqualPin(str):
            def __eq__(self, other):
                return True

        bad_anchors = deepcopy(anchors)
        bad_anchors[0]["c_anchor_pin"] = EqualPin("x")
        with self.assertRaises(AuditError):
            reconstruct_revisit_mechanics([plan], bad_anchors, spots, quotes, config=CONFIG)

        observed = reconstruct_revisit_mechanics([plan], anchors, spots, quotes, config=CONFIG)
        trace = json.loads(observed["events"][0]["transition_trace_json"])
        trace[0]["spot_f64"] = "nan"
        observed["events"][0]["transition_trace_json"] = json.dumps(trace, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        with self.assertRaises(AuditError):
            audit_revisit_mechanics([plan], anchors, spots, quotes, observed, config=CONFIG)
        malformed = reconstruct_revisit_mechanics([plan], anchors, spots, quotes, config=CONFIG)
        trace = json.loads(malformed["events"][0]["transition_trace_json"])
        trace[0]["spot_f64"] = "not-hex"
        malformed["events"][0]["transition_trace_json"] = json.dumps(trace, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        with self.assertRaises(AuditError):
            audit_revisit_mechanics([plan], anchors, spots, quotes, malformed, config=CONFIG)
