"""Artificial in-memory composition cases for D revisit mechanics only.

These fixtures deliberately use tiny integer nanosecond domains.  They neither
read an adapter nor stand in for the future 1620/2790 real-population gate.
"""
from __future__ import annotations

import unittest

import weekly_zone_revisit_mechanics as mechanics


PIN = "a" * 64
CONFIG = {"evaluation_start_date": "2026-01-02", "evaluation_end_date": "2026-09-17"}
MINUTE_NS = 60 * 1_000_000_000
D_1030 = 60 * MINUTE_NS
H2 = 225 * MINUTE_NS


def clock(value: int | str) -> int:
    if value == "H2":
        return H2
    if value == "POST_H2":
        return H2 + 1
    return D_1030 + value


def plan(plan_id: str = "P1", ordinal: int = 1) -> dict[str, object]:
    return {
        "calendar_ordinal": ordinal, "plan_id": plan_id, "ticker": "SPY",
        "trade_date": "2026-01-02", "expiry_date": "2026-01-09",
        "call_decision_id": plan_id + "C", "put_decision_id": plan_id + "P",
        "horizon_end_local_ns": H2, "d_1030_local_ns": D_1030,
        "d_session_date": "2026-01-02",
        "d1_session_date": "2026-01-05", "h2_session_date": "2026-01-06",
        "d_rth_open_local_ns": 0, "d_rth_close_local_ns": 70 * MINUTE_NS,
        "d1_rth_open_local_ns": 80 * MINUTE_NS, "d1_rth_close_local_ns": 150 * MINUTE_NS,
        "h2_rth_open_local_ns": 160 * MINUTE_NS, "h2_rth_close_local_ns": H2,
        "expected_rth_minutes": [clock(t) for t in (10, 20, 30, 40, 50, 60, 70)] + [H2],
        "b_plan_pin": PIN, "b_value_pin": "b" * 64,
        "c_anchor_pin": "c" * 64, "c_geometry_pin": "d" * 64,
        "fixed_risk_contract_pin": mechanics.FIXED_RISK_CONTRACT_PIN, "geometry_status": "AVAILABLE",
        "geometry_partition": "ELIGIBLE_ANCHOR_SET",
    }


def anchor(plan_id: str = "P1", anchor_id: str = "A1", center: float = 100.0, cluster: int = 1) -> dict[str, object]:
    return {
        "plan_id": plan_id, "anchor_id": anchor_id, "cluster_ordinal": cluster,
        "center": center, "band": 1.0, "source_mask": 3,
        "anchor_available_at_local_ns": 1, "valid_geometry": True,
        "components": [{"kind": "FIB"}, {"kind": "WALL"}],
        "c_anchor_pin": "c" * 64, "c_geometry_pin": "d" * 64,
    }


def spot(t: int | str, value: float, valid: bool = True, **extra: object) -> dict[str, object]:
    return {"ticker": "SPY", "time_local_ns": clock(t), "trade_date": "2026-01-02", "spot": value, "valid_rth": valid, **extra}


def quote(decision: str, t: int | str, ask: float | None, bid: float | None) -> dict[str, object]:
    return {"decision_id": decision, "time_local_ns": clock(t), "ask": ask, "bid": bid}


def confirmed_path() -> list[dict[str, object]]:
    return [spot(10, 104.0), spot(20, 100.0), spot(30, 104.0), spot(40, 100.0), spot(50, 104.0), spot(60, 105.0)]


class SyntheticMechanicsTests(unittest.TestCase):
    def test_composed_confirmation_has_common_four_books_and_zero_bid(self) -> None:
        result = mechanics.evaluate_revisit_mechanics([plan()], [anchor(), anchor(anchor_id="A2", center=110.0, cluster=2)], confirmed_path(), [quote("P1C", 70, 2.0, 1.0), quote("P1C", "H2", 2.0, 0.0)], config=CONFIG)
        self.assertEqual(result["status"], "SYNTHETIC_MECHANICS_ONLY")
        self.assertEqual(len(result["ledger"]), 4)
        self.assertEqual({row["arm"] for row in result["ledger"]}, {"A", "B"})
        self.assertTrue(all(row["exit_bid"] == 0.0 for row in result["ledger"]))

    def test_gap_crossing_preserves_no_touch_and_trace(self) -> None:
        result = mechanics.evaluate_revisit_mechanics([plan()], [anchor()], [spot(10, 103.0), spot(20, 97.0)], [], config=CONFIG)
        event = result["events"][0]
        self.assertIn("GAP_CROSSING", event["transition_trace_json"])
        self.assertIsNone(event["visit_time"])

    def test_missing_minute_and_session_break_prevent_confirmation(self) -> None:
        samples = confirmed_path()[:-1] + [spot(60, 104.0, False), spot(70, 104.0, True, session_break=True)]
        result = mechanics.evaluate_revisit_mechanics([plan()], [anchor()], samples, [], config=CONFIG)
        self.assertNotEqual(result["events"][0]["event_status"], "CONFIRMED")

    def test_first_physical_event_supersedes_without_rescue(self) -> None:
        anchors = [anchor("P1", "A1", 100.0, 1), anchor("P1", "A2", 101.0, 2), anchor("P1", "A3", 120.0, 3)]
        result = mechanics.evaluate_revisit_mechanics([plan()], anchors, confirmed_path(), [quote("P1C", 70, 2.0, 1.0)], config=CONFIG)
        statuses = {row["anchor_id"]: row["terminal_reason"] for row in result["events"]}
        self.assertIn("SUPERSEDED_FIRST_EVENT", statuses.values())

    def test_h2_boundary_and_future_mutation_do_not_rescue(self) -> None:
        anchors = [anchor(), anchor(anchor_id="A2", center=110.0, cluster=2)]
        no_future = mechanics.evaluate_revisit_mechanics([plan()], anchors, confirmed_path(), [quote("P1C", "H2", 2.0, 1.0)], config=CONFIG)
        with_future = mechanics.evaluate_revisit_mechanics([plan()], anchors, confirmed_path() + [spot("POST_H2", 120.0)], [quote("P1C", "H2", 2.0, 1.0)], config=CONFIG)
        self.assertEqual(no_future["events"], with_future["events"])
        self.assertEqual(no_future["events"][0]["terminal_reason"], "TOO_LATE")

    def test_pre_fill_trigger_is_mature_without_a_future_ask(self) -> None:
        anchors = [anchor(), anchor(anchor_id="A2", center=110.0, cluster=2)]
        cancelled = mechanics.evaluate_revisit_mechanics([plan()], anchors, confirmed_path() + [spot(70, 110.0)], [], config=CONFIG)
        with_later_ask = mechanics.evaluate_revisit_mechanics([plan()], anchors, confirmed_path() + [spot(70, 110.0)], [quote("P1C", 80, 2.0, 1.0)], config=CONFIG)
        self.assertEqual(cancelled["events"][0]["terminal_reason"], "PRE_FILL_TRIGGER_CANCELLED")
        self.assertEqual(cancelled["events"], with_later_ask["events"])
        self.assertEqual(cancelled["ledger"], [])

    def test_qty_zero_precedes_open_position_and_coverage_has_no_trade(self) -> None:
        result = mechanics.evaluate_revisit_mechanics([plan()], [anchor(), anchor(anchor_id="A2", center=110.0, cluster=2)], confirmed_path(), [quote("P1C", 70, 1_000_000.0, 1.0)], config=CONFIG)
        self.assertEqual({row["admission_status"] for row in result["ledger"]}, {"EVENT_RISK_BUDGET"})
        no_anchor_plan = {**plan(), "geometry_partition": "NO_CONFLUENT_ANCHOR"}
        no_trade = mechanics.evaluate_revisit_mechanics([no_anchor_plan], [], [], [], config=CONFIG)
        self.assertEqual(no_trade["plan_coverage"][0]["economic_intent_count"], 0)

    def test_rejects_partition_and_provenance_drift_without_coercion(self) -> None:
        bad_partition = {**plan(), "geometry_partition": "ELIGIBLE_ANCHOR_SET"}
        with self.assertRaises(mechanics.MechanicsError):
            mechanics.evaluate_revisit_mechanics([bad_partition], [], [], [], config=CONFIG)
        bad_quote = quote("P1C", 70, 2.0, 0.0)
        bad_quote["bid"] = True
        with self.assertRaises(mechanics.MechanicsError):
            mechanics.evaluate_revisit_mechanics([plan()], [], [], [bad_quote], config=CONFIG)

    def test_crossed_quote_is_retained_but_cannot_create_intent(self) -> None:
        anchors = [anchor(), anchor(anchor_id="A2", center=110.0, cluster=2)]
        result = mechanics.evaluate_revisit_mechanics([plan()], anchors, confirmed_path(), [quote("P1C", 70, 1.0, 2.0)], config=CONFIG)
        self.assertEqual(result["events"][0]["terminal_reason"], "NO_ENTRY_QUOTE")
        self.assertEqual(result["ledger"], [])


if __name__ == "__main__":
    unittest.main()
