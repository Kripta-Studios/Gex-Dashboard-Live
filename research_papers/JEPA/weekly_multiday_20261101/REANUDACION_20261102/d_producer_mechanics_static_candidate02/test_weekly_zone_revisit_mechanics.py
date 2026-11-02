"""Artificial end-to-end expectations for the D producer; no market data."""
from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import json
import unittest

import weekly_zone_revisit_mechanics as mechanics


EPOCH = datetime(1970, 1, 1)
MINUTE = 60_000_000_000
CONFIG = {"evaluation_start_date": "2026-01-02", "evaluation_end_date": "2026-09-17"}
RISK_PIN = "9c387e9bea74ba65777808b5ac5e5fccfdc2437645e7b301c15eab2d33bbeb7b"


def ns(date, hour, minute):
    delta = datetime.fromisoformat(date) + timedelta(hours=hour, minutes=minute) - EPOCH
    return (delta.days * 86400 + delta.seconds) * 1_000_000_000


def plan(identifier="p1", ticker="SPY", ordinal=0, days=("2026-01-02", "2026-01-05", "2026-01-06"), kinds=("FULL", "FULL", "FULL")):
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
    for index, prefix in enumerate(("d", "d1", "h2")):
        opening = ns(days[index], 9, 30)
        closing = ns(days[index], 13 if kinds[index] == "SHORT" else 16, 0)
        result.update({prefix + "_session_date": days[index], prefix + "_session_kind": kinds[index], prefix + "_rth_open_local_ns": opening, prefix + "_rth_close_local_ns": closing})
        last = result["horizon_end_local_ns"] if prefix == "h2" else closing
        result["expected_rth_minutes"].extend(range(opening, last + MINUTE, MINUTE))
    return result


def anchor(p, identifier="zone", ordinal=0, center=100.0, confluent=True):
    return {
        "plan_id": p["plan_id"], "anchor_id": identifier, "cluster_ordinal": ordinal,
        "center": center, "band": 1.0, "source_mask": 6 if confluent else 2,
        "anchor_available_at_local_ns": p["d_1030_local_ns"], "valid_geometry": True,
        "components": [{"kind": "FIB"}, {"kind": "WALL"}] if confluent else [{"kind": "FIB"}],
        "c_anchor_pin": p["c_anchor_pin"], "c_geometry_pin": p["c_geometry_pin"],
    }


def spot(ticker, moment, value):
    return {"ticker": ticker, "time_local_ns": moment, "trade_date": (EPOCH + timedelta(seconds=moment // 1_000_000_000)).date().isoformat(), "spot": value, "valid_rth": value is not None}


def quote(decision, moment, ask=1.0, bid=0.9):
    return {"decision_id": decision, "time_local_ns": moment, "ask": ask, "bid": bid}


def spots_for(plans, replacements=None):
    replacements = replacements or {}
    keys = {(p["ticker"], moment) for p in plans for moment in p["expected_rth_minutes"]}
    return [spot(ticker, moment, replacements.get((ticker, moment), 105.0)) for ticker, moment in sorted(keys)]


def fixture():
    p = plan()
    start = p["d_1030_local_ns"]
    values = [103.0, 100.0, 103.0, 100.0, 103.0, 104.0, 104.0, 111.0]
    changes = {("SPY", start + index * MINUTE): value for index, value in enumerate(values)}
    quotes = [quote(p["call_decision_id"], start + 6 * MINUTE), quote(p["call_decision_id"], start + 8 * MINUTE, 2.2, 2.0), quote(p["call_decision_id"], p["horizon_end_local_ns"], 1.0, 0.7)]
    return [p], [anchor(p), anchor(p, "target", 1, 110.0, False)], spots_for([p], changes), quotes


def evaluate(data):
    return mechanics.evaluate_revisit_mechanics(*data, config=CONFIG)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


class RevisitProducerTests(unittest.TestCase):
    def test_manual_ids_four_books_and_net_after_costs(self):
        data = fixture()
        result = evaluate(data)
        p = data[0][0]
        event = result["events"][0]
        confirmation = p["d_1030_local_ns"] + 5 * MINUTE
        entry = confirmation + MINUTE
        rid = digest({"schema": "D_REVISIT_V1", "plan_id": "p1", "anchor_id": "zone"})
        eid = digest({"schema": "D_EVENT_V1", "revisit_id": rid, "confirmation_time_local_ns": confirmation, "departure_side": "ABOVE"})
        iid = digest({"schema": "D_INTENT_V1", "event_id": eid, "decision_id": "p1:CALL", "entry_quote_time_local_ns": entry})
        self.assertEqual((event["revisit_id"], event["event_id"], event["intent_id"]), (rid, eid, iid))
        self.assertEqual(event["terminal_reason"], "FILLED")
        self.assertEqual(event["spot_coverage_status"], "COMPLETE")
        self.assertEqual(event["label_available_at"], p["horizon_end_local_ns"])
        expected = {("A", "BASE"): ("4808.1", "9291.9", "4483.8"), ("A", "ADVERSE"): ("4855.1", "9244.9", "4389.8"), ("B", "BASE"): ("4808.1", "3181.9", "-1626.2"), ("B", "ADVERSE"): ("4855.1", "3134.9", "-1720.2")}
        self.assertEqual(len(result["ledger"]), 4)
        for row in result["ledger"]:
            self.assertEqual((row["unit_risk_cents"], row["qty"]), (10460, 47))
            self.assertEqual((row["entry_debit_decimal"], row["exit_credit_decimal"], row["net_decimal"]), expected[row["arm"], row["cost"]])
            self.assertEqual(row["realized_equity_after_entry_decimal"], "99938.9")
            self.assertEqual(row["exit_fee_obligation_after_entry_decimal"], "61.1")
            self.assertEqual(row["reserve_after_entry_decimal"], "4747" if row["cost"] == "BASE" else "4794")
            self.assertEqual(row["ledger_id"], digest({"schema": "D_LEDGER_V1", "intent_id": iid, "arm": row["arm"], "cost": row["cost"]}))
            self.assertEqual(row["outcome"], "TARGET_FIRST_OBSERVED" if row["arm"] == "A" else "TIMEOUT_H2")
        self.assertEqual((len(event), len(result["ledger"][0]), len(result["plan_coverage"][0]), len(result["counts"])), (39, 47, 19, 39))
        self.assertEqual(result["counts"]["ineligible_nonconfluence_rows"], 1)
        self.assertEqual(result["counts"]["filled_rows"], 4)

    def test_future_mutation_cannot_change_closed_plan(self):
        data = fixture()
        baseline = evaluate(data)
        p = data[0][0]
        data[2].append(spot("SPY", p["horizon_end_local_ns"] + MINUTE, 999.0))
        data[3].append(quote("p1:CALL", p["horizon_end_local_ns"] + MINUTE, 200.0, 199.0))
        self.assertEqual(evaluate(data), baseline)

    def test_cancel_is_mature_without_any_later_quote(self):
        data = fixture()
        data[3].pop(0)
        cancelled = evaluate(data)
        self.assertEqual(cancelled["events"][0]["terminal_reason"], "PRE_FILL_TRIGGER_CANCELLED")
        self.assertEqual(cancelled["events"][0]["label_available_at"], ns("2026-01-02", 10, 37))
        self.assertEqual(cancelled["ledger"], [])
        data[3].clear()
        self.assertEqual(evaluate(data), cancelled)
        annotation = json.loads(cancelled["events"][0]["transition_trace_json"])[-1]
        self.assertEqual(annotation["spot_f64"], float(111).hex())

    def test_trigger_tie_beats_ask_but_later_trigger_does_not(self):
        data = fixture()
        self.assertEqual(evaluate(data)["events"][0]["terminal_reason"], "FILLED")
        data[3][0]["time_local_ns"] = ns("2026-01-02", 10, 37)
        self.assertEqual(evaluate(data)["events"][0]["terminal_reason"], "PRE_FILL_TRIGGER_CANCELLED")

    def test_valid_nonconfirming_observation_resets_streak(self):
        for value in (100.0, 101.5):
            with self.subTest(value=value):
                data = fixture()
                for row in data[2]:
                    if row["time_local_ns"] == ns("2026-01-02", 10, 35):
                        row["spot"] = value
                    if row["time_local_ns"] == ns("2026-01-02", 10, 37):
                        row["spot"] = 105.0
                event = evaluate(data)["events"][0]
                self.assertEqual(event["confirmation_time"], ns("2026-01-02", 10, 37))
                resets = [item for item in json.loads(event["transition_trace_json"]) if item["kind"] == "CONFIRMATION_RESET"]
                self.assertEqual(len(resets), 1)
                self.assertEqual(resets[0]["reason"], "NON_CONFIRMING_OBSERVATION")
                self.assertEqual(resets[0]["spot_f64"], value.hex())

    def test_absence_terminals_preserve_state(self):
        for values, terminal in (([100.0], "NO_VISIT"), ([103.0], "NO_VISIT"), ([103.0, 100.0], "NO_DEPARTURE"), ([103.0, 100.0, 103.0], "NO_REVISIT"), ([103.0, 100.0, 103.0, 100.0], "NO_CONFIRMATION"), ([103.0, 100.0, 97.0], "CROSS_THROUGH")):
            with self.subTest(terminal=terminal, values=values):
                p = plan()
                samples = [spot("SPY", p["d_1030_local_ns"] + i * MINUTE, value) for i, value in enumerate(values)]
                row = evaluate(([p], [anchor(p)], samples, []))["events"][0]
                self.assertEqual(row["terminal_reason"], terminal)
                self.assertIsNone(row["event_id"])
                self.assertEqual(row["label_available_at"], p["horizon_end_local_ns"])

    def test_gap_is_not_visit_and_initial_sample_arms(self):
        p = plan()
        samples = [spot("SPY", p["d_1030_local_ns"] - MINUTE, 97.0), spot("SPY", p["d_1030_local_ns"], 103.0), spot("SPY", p["d_1030_local_ns"] + MINUTE, 97.0)]
        row = evaluate(([p], [anchor(p)], samples, []))["events"][0]
        self.assertEqual(row["armed_side"], "ABOVE")
        self.assertEqual(row["terminal_reason"], "NO_VISIT")
        self.assertIsNone(row["visit_time"])
        self.assertEqual([r["kind"] for r in json.loads(row["transition_trace_json"])], ["ARMED_ABOVE", "GAP_CROSSING"])

    def test_cross_rearm_clears_previous_attempt_scalars(self):
        p = plan()
        values = [103.0, 100.0, 103.0, 100.0, 103.0, 97.0, 97.0, 100.0, 97.0, 100.0, 97.0, 96.0]
        samples = [spot("SPY", p["d_1030_local_ns"] + i * MINUTE, value) for i, value in enumerate(values)]
        row = evaluate(([p], [anchor(p), anchor(p, "put-target", 1, 90.0, False)], samples, []))["events"][0]
        self.assertEqual(row["side"], "PUT")
        self.assertEqual(row["visit_time"], ns("2026-01-02", 10, 37))
        self.assertEqual(row["departure_time"], ns("2026-01-02", 10, 38))
        self.assertEqual(row["revisit_time"], ns("2026-01-02", 10, 39))
        self.assertEqual(row["confirmation_time"], ns("2026-01-02", 10, 41))
        self.assertIn("CROSS_THROUGH", [item["kind"] for item in json.loads(row["transition_trace_json"])])

    def test_exact_h_requires_two_consecutive_minutes(self):
        for values, confirmed in (([103.0, 100.0, 103.0, 100.0, 103.0, 104.0], True), ([103.0, 100.0, 103.0, 100.0, 103.0], False)):
            with self.subTest(confirmed=confirmed):
                p = plan()
                start = p["horizon_end_local_ns"] - (len(values) - 1) * MINUTE
                samples = [spot("SPY", start + i * MINUTE, value) for i, value in enumerate(values)]
                row = evaluate(([p], [anchor(p), anchor(p, "target", 1, 110.0, False)], samples, []))["events"][0]
                self.assertEqual(row["event_id"] is not None, confirmed)
                self.assertEqual(row["terminal_reason"], "TOO_LATE" if confirmed else "NO_CONFIRMATION")
                self.assertEqual(row["label_available_at"], p["horizon_end_local_ns"])

    def test_missing_and_overnight_break_confirmations(self):
        p = plan()
        base = p["d_1030_local_ns"]
        for extra in (base + 6 * MINUTE, ns("2026-01-05", 9, 30)):
            with self.subTest(extra=extra):
                samples = [spot("SPY", base + i * MINUTE, value) for i, value in enumerate([103.0, 100.0, 103.0, 100.0, 103.0])]
                samples.append(spot("SPY", extra, 104.0))
                row = evaluate(([p], [anchor(p)], samples, []))["events"][0]
                self.assertIsNone(row["event_id"])
                self.assertEqual(row["terminal_reason"], "NO_CONFIRMATION")

    def test_no_target_retains_identity_and_physical_priority(self):
        data = fixture()
        p = data[0][0]
        data[1][:] = [anchor(p), anchor(p, "second", 1, 100.5)]
        result = evaluate(data)
        self.assertEqual([row["terminal_reason"] for row in sorted(result["events"], key=lambda row: row["cluster_ordinal"])], ["NO_TARGET", "SUPERSEDED_FIRST_EVENT"])
        self.assertTrue(all(row["event_id"] is not None for row in result["events"]))
        self.assertEqual(result["ledger"], [])
        self.assertEqual(sorted(json.loads(row["overlap_rank_json"])["rank"] for row in result["events"]), [1, 2])

    def test_missing_exit_charges_fee_and_zero_bid_is_observed(self):
        for bid, missing in ((None, True), (0.0, False)):
            with self.subTest(bid=bid):
                data = fixture()
                data[3][-1]["bid"] = bid
                result = evaluate(data)
                for row in result["ledger"]:
                    if row["arm"] == "B":
                        self.assertEqual(row["exit_credit_decimal"], "-61.1")
                        self.assertEqual(row["missing_exit_flag"], missing)
                        self.assertEqual(row["exit_bid"], bid)
                        self.assertEqual(row["outcome"], "TIMEOUT_H2")

    def test_qty_zero_has_four_nonfill_rows_and_before_balances(self):
        data = fixture()
        data[3][0]["ask"] = 1000.0
        result = evaluate(data)
        self.assertEqual(result["events"][0]["terminal_reason"], "NO_FILL")
        self.assertEqual(result["counts"]["event_risk_budget_rows"], 1)
        self.assertEqual(result["counts"]["no_fill_rows"], 4)
        for row in result["ledger"]:
            self.assertEqual(row["qty"], 0)
            self.assertEqual(row["cash_before_entry_decimal"], "100000")
            self.assertEqual(row["fill_status"], "NO_FILL")
            self.assertIsNone(row["outcome"])
            self.assertIsNone(row["cash_after_entry_decimal"])

    def test_missing_geometry_and_nonconfluent_coverage_are_not_deleted(self):
        for status, partition in (("MISSING_SOURCE", "C_MISSING_SOURCE"), ("INVALID_IB", "C_INVALID_IB"), ("INVALID_STATE60", "C_INVALID_STATE60"), ("AVAILABLE_GEOMETRY", "NO_CONFLUENT_ANCHOR")):
            with self.subTest(status=status):
                p = plan()
                p.update(geometry_status=status, geometry_partition=partition)
                anchors = [anchor(p, confluent=False)] if status == "AVAILABLE_GEOMETRY" else []
                result = evaluate(([p], anchors, [], []))
                self.assertEqual(result["events"], [])
                self.assertEqual(len(result["plan_coverage"]), 1)
                self.assertEqual(result["plan_coverage"][0]["geometry_partition"], partition)
                self.assertEqual(result["counts"]["plans_no_confirmed_event"], 1)

    def test_historical_plan_keeps_outside_and_inside_confirmations(self):
        p = plan(days=("2025-12-31", "2026-01-02", "2026-01-05"))
        changes = {}
        for start, values in ((p["d_1030_local_ns"], [103.0, 100.0, 103.0, 100.0, 103.0, 104.0]), (ns("2026-01-02", 9, 30), [107.0, 110.0, 107.0, 110.0, 107.0, 106.0])):
            changes.update({("SPY", start + i * MINUTE): value for i, value in enumerate(values)})
        levels = [anchor(p), anchor(p, "second", 1, 110.0), anchor(p, "target", 2, 120.0, False)]
        quotes = [quote("p1:PUT", ns("2026-01-02", 9, 36)), quote("p1:PUT", p["horizon_end_local_ns"], 1.0, 0.7)]
        result = evaluate(([p], levels, spots_for([p], changes), quotes))
        cov = result["plan_coverage"][0]
        self.assertEqual((cov["outside_evaluation_event_count"], cov["in_evaluation_event_count"], cov["economic_intent_count"]), (1, 1, 1))
        self.assertEqual(result["counts"]["plans_with_mixed_evaluation_events"], 1)
        self.assertEqual(len(json.loads(cov["event_day_evidence_json"])), 2)

    def test_short_session_grid_and_pre_support_observations(self):
        p = plan(days=("2026-07-02", "2026-07-06", "2026-07-07"), kinds=("SHORT", "FULL", "FULL"))
        values = [103.0, 100.0, 103.0, 100.0, 103.0, 104.0]
        samples = [spot("SPY", p["d_1030_local_ns"] - (6 - i) * MINUTE, value) for i, value in enumerate(values)]
        row = evaluate(([p], [anchor(p)], samples, []))["events"][0]
        self.assertIsNone(row["event_id"])
        self.assertEqual(row["transition_trace_json"], "[]")
        self.assertEqual(row["spot_coverage_status"], "MISSING_SESSION")

    def test_session_boundary_resets_last_close_confirmation_minute(self):
        p = plan()
        start = ns("2026-01-02", 15, 56)
        values = [103.0, 100.0, 103.0, 100.0, 103.0]
        changes = {("SPY", start + i * MINUTE): value for i, value in enumerate(values)}
        data = ([p], [anchor(p), anchor(p, "target", 1, 110.0, False)], spots_for([p], changes), [])
        event = evaluate(data)["events"][0]
        self.assertEqual(event["confirmation_time"], ns("2026-01-05", 9, 31))
        boundaries = [row for row in json.loads(event["transition_trace_json"]) if row["kind"] == "SESSION_BREAK"]
        self.assertEqual(len(boundaries), 1)
        self.assertEqual(boundaries[0]["time_local_ns"], ns("2026-01-05", 9, 30))
        self.assertEqual((boundaries[0]["state_before"], boundaries[0]["state_after"], boundaries[0]["side"], boundaries[0]["spot_f64"]), ("CONFIRM_ONE_ABOVE", "REVISITED_ABOVE", "ABOVE", None))

    def test_overlapping_plan_waits_for_b_even_after_a_profit(self):
        original = fixture()
        p1 = original[0][0]
        p2 = plan("p2", ordinal=1, days=("2026-01-05", "2026-01-06", "2026-01-07"))
        overrides = {(row["ticker"], row["time_local_ns"]): row["spot"] for row in original[2]}
        values = [203.0, 200.0, 203.0, 200.0, 203.0, 204.0, 204.0]
        overrides.update({("SPY", p2["d_1030_local_ns"] + i * MINUTE): value for i, value in enumerate(values)})
        levels = original[1] + [anchor(p2, center=200.0), anchor(p2, "target", 1, 210.0, False)]
        quotes = original[3] + [quote("p2:CALL", p2["d_1030_local_ns"] + 6 * MINUTE), quote("p2:CALL", p2["horizon_end_local_ns"], 1.0, 0.7)]
        result = evaluate(([p1, p2], levels, spots_for([p1, p2], overrides), quotes))
        waiting = [row for row in result["ledger"] if row["plan_id"] == "p2"]
        self.assertEqual(len(waiting), 4)
        for row in waiting:
            self.assertEqual((row["admission_status"], row["fill_status"], row["wait_reason"]), ("WAIT", "NOT_APPLICABLE", "OPEN_POSITION"))
            self.assertIsNone(row["entry_debit_decimal"])
            self.assertIsNone(row["outcome"])
            if row["cost"] == "BASE":
                self.assertEqual(row["cash_before_entry_decimal"], "104483.8" if row["arm"] == "A" else "95191.9")
        self.assertEqual((result["counts"]["common_intent_rows"], result["counts"]["admitted_intent_rows"], result["counts"]["wait_rows"]), (2, 1, 1))

    def test_strict_scalar_clock_identity_and_order_rejection(self):
        mutations = (
            lambda data: data[0][0].update(calendar_ordinal=True),
            lambda data: data[0][0].update(horizon_end_local_ns=data[0][0]["horizon_end_local_ns"] + 1),
            lambda data: data[0][0]["expected_rth_minutes"].__setitem__(0, float(data[0][0]["expected_rth_minutes"][0])),
            lambda data: data[1][0].update(source_mask=32768),
            lambda data: data[1][0].update(anchor_available_at_local_ns=data[1][0]["anchor_available_at_local_ns"] + MINUTE),
            lambda data: data[2][0].update(valid_rth=1),
            lambda data: data[3][0].update(bid=True),
            lambda data: data[3].append(quote("p1:CALL", 1 << 64)),
            lambda data: data[2].reverse(),
            lambda data: data[1].append(deepcopy(data[1][0])),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                data = fixture()
                mutation(data)
                with self.assertRaises(mechanics.MechanicsError):
                    evaluate(data)


if __name__ == "__main__":
    unittest.main()
