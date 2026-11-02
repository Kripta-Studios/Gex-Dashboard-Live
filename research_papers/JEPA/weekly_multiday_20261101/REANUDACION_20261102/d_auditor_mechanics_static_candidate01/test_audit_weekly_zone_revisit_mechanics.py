"""Manual artificial-fixture tests for the independent D auditor.

No fixture reads data or producer code.  These tests are intentionally not run
by this hand-off; they document the static candidate's required mutations.
"""
from datetime import datetime, timedelta
import unittest

from audit_weekly_zone_revisit_mechanics import AuditError, RISK_PIN, audit_revisit_mechanics, reconstruct_revisit_mechanics


PIN = "a" * 64


def _ns(day, hour, minute):
    return int((datetime.fromisoformat(day) + timedelta(hours=hour, minutes=minute) - datetime(1970, 1, 1)).total_seconds() * 1_000_000_000)


def _grid(days):
    result = []
    for index, day in enumerate(days):
        end = (10, 35) if index == 2 else (16, 0)
        at = _ns(day, 9, 30); stop = _ns(day, *end)
        while at <= stop:
            result.append(at); at += 60_000_000_000
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


def _fixture():
    plan = _plan(); t = lambda h, m: _ns("2026-01-02", h, m)
    values = {t(10, 30): 103.0, t(10, 31): 100.0, t(10, 32): 103.0, t(10, 33): 100.0, t(10, 34): 103.0, t(10, 35): 104.0, t(10, 36): 104.0, t(10, 37): 106.0}
    quotes = _quotes([("call0", t(10, 38), 1.0, 0.9), ("call0", t(10, 39), 1.0, 0.8), ("call0", plan["horizon_end_local_ns"], 1.0, 0.7)])
    return plan, [_anchor("a0", 0, 100), _anchor("a1", 1, 110, ("FIB",))], _spots(plan, values), quotes


class TestIndependentSyntheticAuditor(unittest.TestCase):
    def test_manual_projection_and_independent_audit(self):
        plan, anchors, spots, quotes = _fixture()
        result = reconstruct_revisit_mechanics([plan], anchors, spots, quotes, config={"evaluation_start_date": "2026-01-02", "evaluation_end_date": "2026-09-17"})
        self.assertEqual(result["status"], "SYNTHETIC_MECHANICS_ONLY")
        self.assertEqual(len(result["events"]), 1)
        self.assertIsNotNone(result["events"][0]["event_id"])
        self.assertEqual(len(result["ledger"]), 4)
        self.assertEqual(result["counts"]["common_intent_rows"], 1)
        self.assertEqual(audit_revisit_mechanics([plan], anchors, spots, quotes, result, config={"evaluation_start_date": "2026-01-02", "evaluation_end_date": "2026-09-17"})["status"], "PASS_SYNTHETIC_D_MECHANICS_AUDIT")

    def test_manual_negative_mutations_are_rejected(self):
        for mutation in ("post_h", "causal", "quantity", "accounting", "coverage", "identifier"):
            with self.subTest(mutation=mutation):
                plan, anchors, spots, quotes = _fixture(); config = {"evaluation_start_date": "2026-01-02", "evaluation_end_date": "2026-09-17"}
                observed = reconstruct_revisit_mechanics([plan], anchors, spots, quotes, config=config)
                if mutation == "post_h":
                    # A post-H quote does not alter reconstruction; tampering the matured output does.
                    observed["events"][0]["label_available_at"] += 1
                elif mutation == "causal": observed["events"][0]["confirmation_time"] -= 60_000_000_000
                elif mutation == "quantity": observed["ledger"][0]["qty"] += 1
                elif mutation == "accounting": observed["ledger"][0]["net_decimal"] = "0"
                elif mutation == "coverage": observed["plan_coverage"][0]["eligible_anchor_count"] = 99
                else: observed["events"][0]["revisit_id"] = "0" * 64
                with self.assertRaises(AuditError):
                    audit_revisit_mechanics([plan], anchors, spots, quotes, observed, config=config)

    def test_post_h_quote_is_future_invariant_and_clock_is_fixed(self):
        plan, anchors, spots, quotes = _fixture(); config = {"evaluation_start_date": "2026-01-02", "evaluation_end_date": "2026-09-17"}
        baseline = reconstruct_revisit_mechanics([plan], anchors, spots, quotes, config=config)
        future = quotes + [{"decision_id": "call0", "time_local_ns": plan["horizon_end_local_ns"] + 60_000_000_000, "ask": 0.5, "bid": 0.4}]
        self.assertEqual(reconstruct_revisit_mechanics([plan], anchors, spots, future, config=config), baseline)
        with self.assertRaises(AuditError):
            reconstruct_revisit_mechanics([plan], anchors, spots, quotes, config={"evaluation_start_date": "2026-01-03", "evaluation_end_date": "2026-09-17"})

    def test_pre_fill_trigger_beats_later_quote_and_qty_zero_is_preserved(self):
        plan, anchors, spots, quotes = _fixture(); config = {"evaluation_start_date": "2026-01-02", "evaluation_end_date": "2026-09-17"}
        t = lambda h, m: _ns("2026-01-02", h, m)
        # The target is 110; this observed trigger precedes the first valid ask.
        for record in spots:
            if record["time_local_ns"] == t(10, 37): record["spot"] = 111.0
        cancelled = reconstruct_revisit_mechanics([plan], anchors, spots, quotes, config=config)
        self.assertEqual(cancelled["events"][0]["terminal_reason"], "PRE_FILL_TRIGGER_CANCELLED")
        self.assertEqual(cancelled["ledger"], [])
        plan, anchors, spots, quotes = _fixture()
        for quote in quotes:
            if quote["decision_id"] == "call0" and quote["time_local_ns"] < plan["horizon_end_local_ns"]: quote["ask"] = 1000.0; quote["bid"] = 999.0
        zero = reconstruct_revisit_mechanics([plan], anchors, spots, quotes, config=config)
        self.assertEqual(zero["events"][0]["terminal_reason"], "NO_FILL")
        self.assertEqual({row["admission_status"] for row in zero["ledger"]}, {"EVENT_RISK_BUDGET"})
