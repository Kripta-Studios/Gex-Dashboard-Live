"""Independent, in-memory auditor for the synthetic D revisit interface.

This module deliberately contains its own validation, transition, identity and
accounting code.  It reads no files and imports no research implementation.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime, timedelta
from decimal import Context, Decimal, Inexact, ROUND_CEILING, localcontext


class AuditError(ValueError):
    """Raised for malformed artificial inputs or a non-identical projection."""


NS_MINUTE = 60_000_000_000
EPOCH = datetime(1970, 1, 1)
RISK_PIN = "9c387e9bea74ba65777808b5ac5e5fccfdc2437645e7b301c15eab2d33bbeb7b"
TICKERS = ("SPY", "QQQ", "SPXW")
BOOKS = (("A", "BASE", Decimal("0.01")), ("A", "ADVERSE", Decimal("0.02")),
         ("B", "BASE", Decimal("0.01")), ("B", "ADVERSE", Decimal("0.02")))
CONFIG = {"evaluation_start_date": "2026-01-02", "evaluation_end_date": "2026-09-17"}

EVENT_FIELDS = (
    "calendar_ordinal plan_id ticker trade_date expiry_date anchor_id cluster_ordinal center band "
    "source_mask anchor_available_at revisit_id event_status armed_side visit_time departure_time "
    "departure_side revisit_time confirmation_time confirmation_time_local_ns event_id event_session_date "
    "decision_id side stop_spot target_anchor_id target_spot entry_quote_time entry_quote_time_local_ns "
    "event_entry_ask intent_id terminal_reason overlap_rank_json transition_trace_json spot_coverage_status "
    "option_coverage_status label_available_at b_plan_pin c_anchor_pin"
).split()
LEDGER_FIELDS = (
    "ledger_id intent_id event_id plan_id ticker event_session_date arm cost admission_status fill_status "
    "decision_time entry_quote_time horizon_end decision_id right entry_ask slippage_dollars unit_risk_cents qty "
    "entry_debit_decimal exit_trigger_time exit_trigger_kind exit_bid_time exit_bid accounting_exit_time "
    "exit_credit_decimal net_decimal outcome missing_exit_flag ambiguous_flag label_available_at "
    "cash_before_entry_decimal reserve_before_entry_decimal exit_fee_obligation_before_decimal "
    "realized_equity_before_decimal cash_after_entry_decimal reserve_after_entry_decimal "
    "exit_fee_obligation_after_entry_decimal realized_equity_after_entry_decimal cash_after_exit_decimal "
    "reserve_after_exit_decimal exit_fee_obligation_after_exit_decimal realized_equity_after_exit_decimal "
    "wait_reason b_value_pin c_geometry_pin replay_contract_pin"
).split()
COVERAGE_FIELDS = (
    "calendar_ordinal plan_id ticker trade_date expiry_date geometry_partition c_anchor_count "
    "eligible_anchor_count revisit_row_count confirmed_event_count first_physical_event_id "
    "first_physical_event_time outside_evaluation_event_count in_evaluation_event_count economic_intent_count "
    "event_day_evidence_json terminal_status_counts_json b_plan_pin c_geometry_pin"
).split()
COUNT_FIELDS = (
    "plan_rows plan_coverage_rows plans_c_missing_geometry plans_c_invalid_geometry "
    "plans_no_confluent_anchor plans_with_eligible_anchor plans_no_confirmed_event "
    "plans_with_only_outside_evaluation_events plans_with_only_in_evaluation_events "
    "plans_with_mixed_evaluation_events eligible_revisit_rows ineligible_nonconfluence_rows revisit_rows "
    "confirmed_rows no_visit_rows no_departure_rows cross_through_rows no_revisit_rows no_confirmation_rows "
    "no_target_rows superseded_first_event_rows pre_fill_trigger_cancelled_rows no_entry_quote_rows "
    "too_late_rows not_evaluable_rows common_intent_rows admitted_intent_rows wait_rows event_risk_budget_rows "
    "capital_blocked_rows open_position_rows no_fill_rows filled_rows missing_exit_rows ambiguous_rows "
    "a_base_ledger_rows a_adverse_ledger_rows b_base_ledger_rows b_adverse_ledger_rows"
).split()
TERMINALS = ("NO_VISIT", "NO_DEPARTURE", "CROSS_THROUGH", "NO_REVISIT", "NO_CONFIRMATION",
             "NO_TARGET", "SUPERSEDED_FIRST_EVENT", "PRE_FILL_TRIGGER_CANCELLED", "NO_ENTRY_QUOTE",
             "TOO_LATE", "OUTSIDE_EVALUATION_WINDOW", "WAIT", "NO_FILL", "FILLED", "NOT_EVALUABLE")
EVENT_STATUSES = (
    "NOT_ARMED", "ARMED", "VISIT", "DEPARTURE", "REVISIT", "CONFIRMED",
    "CROSS_THROUGH", "GAP_CROSSING", "NO_TARGET", "SUPERSEDED_FIRST_EVENT",
    "PRE_FILL_TRIGGER_CANCELLED", "NO_ENTRY_QUOTE", "TOO_LATE",
)
TRACE_KINDS = (
    "ARMED_ABOVE", "ARMED_BELOW", "VISIT", "DEPARTURE", "REVISIT",
    "CONFIRMATION_MINUTE_1", "CONFIRMED", "CROSS_THROUGH", "GAP_CROSSING",
    "MISSING_MINUTE", "SESSION_BREAK", "CONFIRMATION_RESET", "NO_TARGET",
    "SUPERSEDED_FIRST_EVENT", "PRE_FILL_TRIGGER_CANCELLED", "NO_ENTRY_QUOTE",
    "TOO_LATE",
)
TRACE_REASONS = (
    "FIRST_ELIGIBLE_SAMPLE", "INNER_BAND", "OUTER_SAME_SIDE",
    "OUTER_OPPOSITE_SIDE", "NO_INTERIOR_SAMPLE", "MISSING_RTH_MINUTE",
    "SESSION_BOUNDARY", "NON_CONFIRMING_OBSERVATION", "TARGET_ABSENT",
    "DAY_PRIORITY", "TRIGGER_PRE_FILL", "ASK_ABSENT", "TERMINAL_CLOCK",
)
TRACE_STATES = (
    "INIT", "ARMED_ABOVE", "ARMED_BELOW", "VISITED_ABOVE", "VISITED_BELOW",
    "DEPARTED_ABOVE", "DEPARTED_BELOW", "REVISITED_ABOVE", "REVISITED_BELOW",
    "CONFIRM_ONE_ABOVE", "CONFIRM_ONE_BELOW", "CONFIRMED", "TERMINAL",
)
GEOMETRY_PARTITIONS = (
    "C_MISSING_SOURCE", "C_INVALID_IB", "C_INVALID_STATE60",
    "NO_CONFLUENT_ANCHOR", "ELIGIBLE_ANCHOR_SET",
)
I16_MAX = 2**15 - 1
I32_MAX = 2**31 - 1
I64_MIN = -(2**63)
I64_MAX = 2**63 - 1


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _digest(payload):
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _is_int(value):
    return type(value) is int


def _i16(value, where, nonnegative=False):
    _need(_is_int(value) and -2**15 <= value <= I16_MAX, where)
    _need(not nonnegative or value >= 0, where)


def _i32(value, where, nonnegative=False):
    _need(_is_int(value) and -2**31 <= value <= I32_MAX, where)
    _need(not nonnegative or value >= 0, where)


def _i64(value, where):
    _need(_is_int(value) and I64_MIN <= value <= I64_MAX, where)


def _need(condition, message):
    if not condition:
        raise AuditError(message)


def _keys(record, wanted, where):
    _need(type(record) is dict and set(record) == set(wanted), "%s keys" % where)


def _date(value, where):
    _need(
        type(value) is str
        and len(value) == 10
        and value.isascii()
        and value[4] == "-"
        and value[7] == "-"
        and value[:4].isdigit()
        and value[5:7].isdigit()
        and value[8:].isdigit(),
        "%s date type" % where,
    )
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise AuditError("%s date" % where) from exc
    _need(parsed.isoformat() == value, "%s canonical date" % where)
    return parsed


def _dt(ns):
    _i64(ns, "ns")
    return EPOCH + timedelta(microseconds=ns // 1000)


def _date_at(ns):
    return _dt(ns).date().isoformat()


def _finite_float(value, where, positive=False):
    _need(type(value) is float and math.isfinite(value) and (not positive or value > 0), where)


def _pin(value, where):
    _need(type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value), where)


def _literal(value, choices, where):
    _need(type(value) is str and value in choices, where)


def _decimal_text(value):
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def _d(value):
    return Decimal(str(value))


def _valid_quote(q):
    return q["ask"] is not None and q["bid"] is not None and q["ask"] > 0 and 0 <= q["bid"] <= q["ask"]


def _session(plan, ns):
    for prefix in ("d", "d1", "h2"):
        if plan[prefix + "_rth_open_local_ns"] <= ns <= plan[prefix + "_rth_close_local_ns"]:
            return prefix
    return None


def _expected_grid(plan):
    result = []
    for prefix in ("d", "d1", "h2"):
        stop = min(plan[prefix + "_rth_close_local_ns"], plan["horizon_end_local_ns"])
        current = plan[prefix + "_rth_open_local_ns"]
        while current <= stop:
            result.append(current)
            current += NS_MINUTE
    return result


def _validate(plans, anchors, spots, quotes, config):
    _need(type(plans) is list and plans, "plans")
    _need(type(anchors) is list and type(spots) is list and type(quotes) is list, "collections")
    _keys(config, CONFIG, "config")
    for key, value in CONFIG.items():
        _need(type(config[key]) is str, "config type")
        _date(config[key], "config date")
        _need(config[key] == value, "fixed config")
    plan_keys = (
        "calendar_ordinal plan_id ticker trade_date expiry_date call_decision_id put_decision_id "
        "horizon_end_local_ns d_1030_local_ns d_session_date d1_session_date h2_session_date "
        "d_session_kind d1_session_kind h2_session_kind d_rth_open_local_ns d_rth_close_local_ns "
        "d1_rth_open_local_ns d1_rth_close_local_ns h2_rth_open_local_ns h2_rth_close_local_ns "
        "expected_rth_minutes b_plan_pin b_value_pin c_anchor_pin c_geometry_pin "
        "fixed_risk_contract_pin geometry_status geometry_partition"
    ).split()
    anchor_keys = (
        "plan_id anchor_id cluster_ordinal center band source_mask anchor_available_at_local_ns "
        "valid_geometry components c_anchor_pin c_geometry_pin"
    ).split()
    spot_keys = "ticker time_local_ns trade_date spot valid_rth".split()
    quote_keys = "decision_id time_local_ns ask bid".split()
    previous = None
    by_id = {}
    decisions = {}
    pairs = set()
    physical = {}
    for p in plans:
        _keys(p, plan_keys, "plan")
        _i32(p["calendar_ordinal"], "calendar ordinal", nonnegative=True)
        _need(type(p["plan_id"]) is str and p["plan_id"], "plan id")
        key = (p["calendar_ordinal"], p["plan_id"])
        _need(previous is None or key > previous, "plan order")
        previous = key
        _need(type(p["plan_id"]) is str and p["plan_id"] and p["plan_id"] not in by_id, "plan id")
        _literal(p["ticker"], TICKERS, "ticker")
        _need(p["trade_date"] == p["d_session_date"] and (_date(p["trade_date"], "trade") is not None), "trade date")
        _date(p["expiry_date"], "expiry")
        _need((p["ticker"], p["trade_date"]) not in pairs, "plan physical duplicate")
        pairs.add((p["ticker"], p["trade_date"]))
        _need(
            type(p["call_decision_id"]) is str and p["call_decision_id"]
            and type(p["put_decision_id"]) is str and p["put_decision_id"]
            and p["call_decision_id"] != p["put_decision_id"],
            "decisions",
        )
        for d_id, right in ((p["call_decision_id"], "CALL"), (p["put_decision_id"], "PUT")):
            _need(d_id not in decisions, "decision duplicate")
            decisions[d_id] = (p, right)
        for k in ("b_plan_pin", "b_value_pin", "c_anchor_pin", "c_geometry_pin"):
            _pin(p[k], k)
        _need(type(p["fixed_risk_contract_pin"]) is str and p["fixed_risk_contract_pin"] == RISK_PIN, "risk pin")
        _literal(p["geometry_status"], ("MISSING_SOURCE", "INVALID_IB", "INVALID_STATE60", "AVAILABLE_GEOMETRY"), "geometry status")
        _need(type(p["expected_rth_minutes"]) is list, "grid type")
        for expected_ns in p["expected_rth_minutes"]:
            _i64(expected_ns, "grid timestamp")
        _need(p["expected_rth_minutes"] == _expected_grid(p), "complete grid")
        dates = [p[x] for x in ("d_session_date", "d1_session_date", "h2_session_date")]
        for session_date in dates:
            _date(session_date, "session date")
        _need(dates == sorted(dates) and len(set(dates)) == 3, "sessions")
        for prefix in ("d", "d1", "h2"):
            _literal(p[prefix + "_session_kind"], ("FULL", "SHORT"), "session kind")
            open_ns, close_ns = p[prefix + "_rth_open_local_ns"], p[prefix + "_rth_close_local_ns"]
            _i64(open_ns, "open ns")
            _i64(close_ns, "close ns")
            _need(open_ns % NS_MINUTE == 0 and close_ns % NS_MINUTE == 0, "civil endpoint ns")
            _need(_date_at(open_ns) == p[prefix + "_session_date"] == _date_at(close_ns), "session date/ns")
            expected_close_hour = 13 if p[prefix + "_session_kind"] == "SHORT" else 16
            _need(_dt(open_ns).hour == 9 and _dt(open_ns).minute == 30 and _dt(close_ns).hour == expected_close_hour and _dt(close_ns).minute == 0, "rth bounds")
        _i64(p["d_1030_local_ns"], "d 1030")
        _need(p["d_1030_local_ns"] % NS_MINUTE == 0 and p["d_1030_local_ns"] == p["d_rth_open_local_ns"] + 60 * NS_MINUTE, "d 1030")
        _i64(p["horizon_end_local_ns"], "horizon")
        _need(p["horizon_end_local_ns"] % NS_MINUTE == 0 and _dt(p["horizon_end_local_ns"]).hour == 10 and _dt(p["horizon_end_local_ns"]).minute == 35 and _date_at(p["horizon_end_local_ns"]) == p["h2_session_date"], "horizon")
        by_id[p["plan_id"]] = p
        for prefix in ("d", "d1", "h2"):
            ph = (p["ticker"], p[prefix + "_session_date"])
            signature = (p[prefix + "_rth_open_local_ns"], p[prefix + "_rth_close_local_ns"], p[prefix + "_session_kind"])
            _need(ph not in physical or physical[ph] == signature, "physical session conflict")
            physical[ph] = signature
    previous = None
    anchor_map = {}
    anchor_ids = set()
    anchor_ordinals = set()
    for a in anchors:
        _keys(a, anchor_keys, "anchor")
        _need(type(a["plan_id"]) is str and type(a["anchor_id"]) is str, "anchor scalar")
        _i16(a["cluster_ordinal"], "cluster ordinal", nonnegative=True)
        key = (a["plan_id"], a["cluster_ordinal"], a["anchor_id"])
        _need(previous is None or key > previous, "anchor order")
        previous = key
        _need(a["plan_id"] in by_id and type(a["anchor_id"]) is str and a["anchor_id"], "anchor identity")
        _i16(a["source_mask"], "source mask", nonnegative=True)
        _finite_float(a["center"], "center")
        _finite_float(a["band"], "band", True)
        p = by_id[a["plan_id"]]
        _i64(a["anchor_available_at_local_ns"], "anchor availability")
        _need(a["anchor_available_at_local_ns"] == p["d_1030_local_ns"] and a["valid_geometry"] is True, "anchor availability")
        _pin(a["c_anchor_pin"], "anchor pin")
        _pin(a["c_geometry_pin"], "geometry pin")
        _need(a["c_anchor_pin"] == p["c_anchor_pin"] and a["c_geometry_pin"] == p["c_geometry_pin"], "anchor pins")
        _need(type(a["components"]) is list and a["components"], "components")
        for c in a["components"]:
            _keys(c, ("kind",), "component")
            _literal(c["kind"], ("FIB", "WALL"), "component kind")
        _need((a["plan_id"], a["anchor_id"]) not in anchor_ids and (a["plan_id"], a["cluster_ordinal"]) not in anchor_ordinals, "anchor duplicate")
        anchor_ids.add((a["plan_id"], a["anchor_id"]))
        anchor_ordinals.add((a["plan_id"], a["cluster_ordinal"]))
        anchor_map[(a["plan_id"], a["anchor_id"])] = a
    previous = None
    spot_map = {}
    for s in spots:
        _keys(s, spot_keys, "spot")
        _need(type(s["ticker"]) is str, "spot scalar")
        _i64(s["time_local_ns"], "spot time")
        key = (s["ticker"], s["time_local_ns"])
        _need(previous is None or key > previous, "spot order")
        previous = key
        _literal(s["ticker"], TICKERS, "spot ticker")
        _need(_date_at(s["time_local_ns"]) == s["trade_date"], "spot identity")
        _date(s["trade_date"], "spot date")
        _need(type(s["valid_rth"]) is bool, "spot valid")
        if s["valid_rth"]:
            _finite_float(s["spot"], "spot", True)
        else:
            _need(s["spot"] is None, "invalid spot null")
        spot_map[key] = s
    previous = None
    quote_map = {}
    for q in quotes:
        _keys(q, quote_keys, "quote")
        _need(type(q["decision_id"]) is str, "quote scalar")
        _i64(q["time_local_ns"], "quote time")
        key = (q["decision_id"], q["time_local_ns"])
        _need(previous is None or key > previous, "quote order")
        previous = key
        _need(q["decision_id"] in decisions, "quote decision/time")
        p = decisions[q["decision_id"]][0]
        if q["time_local_ns"] <= p["horizon_end_local_ns"]:
            _need(_session(p, q["time_local_ns"]) is not None, "quote outside RTH")
        for name in ("ask", "bid"):
            _need(q[name] is None or (type(q[name]) is float and math.isfinite(q[name])), "quote scalar")
        quote_map[key] = q
    return by_id, decisions, anchor_map, spot_map, quote_map


def _trace(trace, kind, ns, spot, side, before, after, reason):
    trace.append({"seq": len(trace), "kind": kind, "time_local_ns": ns, "spot_f64": None if spot is None else float(spot).hex(), "side": side, "state_before": before, "state_after": after, "reason": reason})


def _event_for(plan, anchor, spots):
    z = anchor["center"]
    b = anchor["band"]
    h = plan["horizon_end_local_ns"]
    _need(math.isfinite(z + 2*b) and math.isfinite(z - 2*b), "finite zone arithmetic")
    start = max(plan["d_1030_local_ns"], anchor["anchor_available_at_local_ns"])
    grid = [t for t in plan["expected_rth_minutes"] if start <= t <= h]
    state = "INIT"
    side = None
    armed = None
    visit = None
    departure = None
    dep_side = None
    revisit = None
    confirmation = None
    trace = []
    last_good = None
    previous_grid = None
    for t in grid:
        if state.startswith("CONFIRM_ONE") and previous_grid is not None and _date_at(previous_grid) != _date_at(t):
            before_boundary = state
            state = "REVISITED_" + side
            _trace(trace, "SESSION_BREAK", t, None, side, before_boundary, state, "SESSION_BOUNDARY")
            last_good = None
        sample = spots.get((plan["ticker"], t))
        valid = sample is not None and sample["valid_rth"]
        if not valid:
            if state == "CONFIRM_ONE_ABOVE" or state == "CONFIRM_ONE_BELOW":
                _trace(trace, "MISSING_MINUTE", t, None, side, state, "REVISITED_" + side, "MISSING_RTH_MINUTE")
                state = "REVISITED_" + side
            last_good = None
            previous_grid = t
            continue
        spot = sample["spot"]
        before = state
        above, below, inner = spot > z + 2*b, spot < z - 2*b, abs(spot-z) <= b
        if state == "INIT":
            if above or below:
                side = "ABOVE" if above else "BELOW"
                armed = side
                visit = None
                departure = None
                dep_side = None
                revisit = None
                confirmation = None
                state = "ARMED_" + side
                _trace(trace, "ARMED_" + side, t, spot, side, before, state, "FIRST_ELIGIBLE_SAMPLE")
        elif state.startswith("ARMED"):
            if inner:
                state = "VISITED_" + side
                visit = t
                _trace(trace, "VISIT", t, spot, side, before, state, "INNER_BAND")
            elif (side == "ABOVE" and below) or (side == "BELOW" and above):
                _trace(trace, "GAP_CROSSING", t, spot, side, before, before, "NO_INTERIOR_SAMPLE")
        elif state.startswith("VISITED"):
            same = above if side == "ABOVE" else below
            opposite = below if side == "ABOVE" else above
            if same:
                state = "DEPARTED_" + side
                departure = t
                dep_side = side
                _trace(trace, "DEPARTURE", t, spot, side, before, state, "OUTER_SAME_SIDE")
            elif opposite:
                state = "INIT"
                _trace(trace, "CROSS_THROUGH", t, spot, side, before, state, "OUTER_OPPOSITE_SIDE")
        elif state.startswith("DEPARTED"):
            if inner:
                state = "REVISITED_" + side
                revisit = t
                _trace(trace, "REVISIT", t, spot, side, before, state, "INNER_BAND")
            elif (side == "ABOVE" and below) or (side == "BELOW" and above):
                _trace(trace, "GAP_CROSSING", t, spot, side, before, before, "NO_INTERIOR_SAMPLE")
        elif state.startswith("REVISITED") or state.startswith("CONFIRM_ONE"):
            same = above if side == "ABOVE" else below
            opposite = below if side == "ABOVE" else above
            if opposite:
                state = "INIT"
                _trace(trace, "CROSS_THROUGH", t, spot, side, before, state, "OUTER_OPPOSITE_SIDE")
            elif same:
                if state.startswith("REVISITED"):
                    state = "CONFIRM_ONE_" + side
                    _trace(trace, "CONFIRMATION_MINUTE_1", t, spot, side, before, state, "OUTER_SAME_SIDE")
                elif last_good is not None and t - last_good == NS_MINUTE and _date_at(last_good) == _date_at(t):
                    state = "CONFIRMED"
                    confirmation = t
                    _trace(trace, "CONFIRMED", t, spot, side, before, state, "OUTER_SAME_SIDE")
                    break
            elif state.startswith("CONFIRM_ONE"):
                state = "REVISITED_" + side
                _trace(trace, "CONFIRMATION_RESET", t, spot, side, before, state, "NON_CONFIRMING_OBSERVATION")
        last_good = t
        previous_grid = t
    if state == "CONFIRMED":
        status, terminal = "CONFIRMED", None
    elif state == "INIT" and any(x["kind"] == "CROSS_THROUGH" for x in trace):
        status, terminal = "CROSS_THROUGH", "CROSS_THROUGH"
    elif state == "INIT" or state.startswith("ARMED"):
        status, terminal = ("NOT_ARMED" if armed is None else "ARMED"), "NO_VISIT"
    elif state.startswith("VISITED"):
        status, terminal = "VISIT", "NO_DEPARTURE"
    elif state.startswith("DEPARTED"):
        status, terminal = "DEPARTURE", "NO_REVISIT"
    else:
        status, terminal = "REVISIT", "NO_CONFIRMATION"
    return {"status": status, "terminal": terminal, "armed": armed, "visit": visit, "departure": departure,
            "dep_side": dep_side, "revisit": revisit, "confirmation": confirmation, "trace": trace, "grid": grid}


def _coverage(plan, event, spot_map, label):
    prefix = [t for t in event["grid"] if t <= min(label, plan["horizon_end_local_ns"])]
    if not prefix:
        return "NOT_EVALUABLE"
    sessions = {_date_at(t) for t in prefix}
    good_by_session = {d: 0 for d in sessions}
    missing = False
    for t in prefix:
        s = spot_map.get((plan["ticker"], t))
        if s is not None and s["valid_rth"]:
            good_by_session[_date_at(t)] += 1
        else:
            missing = True
    if any(v == 0 for v in good_by_session.values()):
        return "MISSING_SESSION"
    return "MISSING_MINUTE" if missing else "COMPLETE"


def _base_event(plan, anchor, fsm):
    rid = _digest({"schema": "D_REVISIT_V1", "plan_id": plan["plan_id"], "anchor_id": anchor["anchor_id"]})
    row = {k: None for k in EVENT_FIELDS}
    row.update({"calendar_ordinal": plan["calendar_ordinal"], "plan_id": plan["plan_id"], "ticker": plan["ticker"],
                "trade_date": plan["trade_date"], "expiry_date": plan["expiry_date"], "anchor_id": anchor["anchor_id"],
                "cluster_ordinal": anchor["cluster_ordinal"], "center": anchor["center"], "band": anchor["band"],
                "source_mask": anchor["source_mask"], "anchor_available_at": anchor["anchor_available_at_local_ns"],
                "revisit_id": rid, "event_status": fsm["status"], "armed_side": fsm["armed"], "visit_time": fsm["visit"],
                "departure_time": fsm["departure"], "departure_side": fsm["dep_side"], "revisit_time": fsm["revisit"],
                "terminal_reason": fsm["terminal"], "transition_trace_json": _canonical(fsm["trace"]),
                "b_plan_pin": plan["b_plan_pin"], "c_anchor_pin": plan["c_anchor_pin"]})
    return row


def _terminal_trace(fsm, row, kind, label_time, reason, spot=None):
    """Append one reviewed terminal annotation after observed FSM evidence."""
    _trace(fsm["trace"], kind, label_time, spot, row["departure_side"], "CONFIRMED", "TERMINAL", reason)


def _apply_candidate(row, plan, anchor, all_anchors, fsm, spot_map):
    h, confirm, side = plan["horizon_end_local_ns"], fsm["confirmation"], fsm["dep_side"]
    row["confirmation_time"] = row["confirmation_time_local_ns"] = confirm
    row["event_session_date"] = _date_at(confirm)
    row["event_id"] = _digest({"schema": "D_EVENT_V1", "revisit_id": row["revisit_id"], "confirmation_time_local_ns": confirm, "departure_side": side})
    row["decision_id"] = plan["call_decision_id"] if side == "ABOVE" else plan["put_decision_id"]
    row["side"] = "CALL" if side == "ABOVE" else "PUT"
    row["stop_spot"] = anchor["center"] - 2*anchor["band"] if side == "ABOVE" else anchor["center"] + 2*anchor["band"]
    cspot = spot_map[(plan["ticker"], confirm)]["spot"]
    choices = []
    for candidate in all_anchors:
        if candidate["anchor_id"] == anchor["anchor_id"] or candidate["anchor_available_at_local_ns"] > confirm:
            continue
        if side == "ABOVE" and candidate["center"] > cspot:
            choices.append(candidate)
        if side == "BELOW" and candidate["center"] < cspot:
            choices.append(candidate)
    if choices:
        # A finite float subtraction can still overflow to infinity.  Compare
        # exact Decimal representations instead, retaining the published
        # float source value in the emitted event.
        with localcontext(_dec_ctx()):
            choices.sort(
                key=lambda item: (
                    abs(Decimal.from_float(item["center"]) - Decimal.from_float(cspot)),
                    item["cluster_ordinal"],
                    item["anchor_id"],
                )
            )
        row["target_anchor_id"] = choices[0]["anchor_id"]
        row["target_spot"] = choices[0]["center"]
    row["event_status"] = "CONFIRMED"
    return cspot


def _first_trigger(plan, row, spot_map, after):
    for t in plan["expected_rth_minutes"]:
        if not (after < t < plan["horizon_end_local_ns"]):
            continue
        s = spot_map.get((plan["ticker"], t))
        if not (s and s["valid_rth"]):
            continue
        target = (row["side"] == "CALL" and s["spot"] >= row["target_spot"]) or (row["side"] == "PUT" and s["spot"] <= row["target_spot"])
        stop = (row["side"] == "CALL" and s["spot"] <= row["stop_spot"]) or (row["side"] == "PUT" and s["spot"] >= row["stop_spot"])
        if target or stop:
            return t, "STOP" if stop else "TARGET", target and stop
    return None, None, False


def _valid_quotes(quote_map, decision, start, h):
    return [q for (d, t), q in quote_map.items() if d == decision and start < t <= h and _valid_quote(q)]


def _dec_ctx():
    ctx = Context(prec=1000)
    ctx.traps[Inexact] = True
    return ctx


def _ledger_row(intent, arm, cost, slip):
    row = {k: None for k in LEDGER_FIELDS}
    row.update({"ledger_id": _digest({"schema": "D_LEDGER_V1", "intent_id": intent["intent_id"], "arm": arm, "cost": cost}),
                "intent_id": intent["intent_id"], "event_id": intent["row"]["event_id"], "plan_id": intent["plan"]["plan_id"],
                "ticker": intent["plan"]["ticker"], "event_session_date": intent["row"]["event_session_date"], "arm": arm,
                "cost": cost, "decision_time": intent["row"]["confirmation_time"], "entry_quote_time": intent["quote"]["time_local_ns"],
                "horizon_end": intent["plan"]["horizon_end_local_ns"], "decision_id": intent["row"]["decision_id"], "right": intent["row"]["side"],
                "entry_ask": intent["quote"]["ask"], "slippage_dollars": _decimal_text(slip), "unit_risk_cents": intent["risk"],
                "qty": intent["qty"], "b_value_pin": intent["plan"]["b_value_pin"], "c_geometry_pin": intent["plan"]["c_geometry_pin"],
                "replay_contract_pin": intent["plan"]["fixed_risk_contract_pin"], "missing_exit_flag": False, "ambiguous_flag": False})
    return row


def _book_values(book):
    with localcontext(_dec_ctx()):
        equity = book["cash"] + book["reserve"]
    return (_decimal_text(book["cash"]), _decimal_text(book["reserve"]), _decimal_text(book["fee"]), _decimal_text(equity))


def _finish_position(book, position):
    row = position["row"]
    q = Decimal(row["qty"])
    slip = position["slip"]
    bid = position["bid"]
    with localcontext(_dec_ctx()):
        credit = q * ((max(_d(bid) - slip, Decimal(0)) if bid is not None else Decimal(0)) * Decimal(100) - Decimal("1.30"))
    with localcontext(_dec_ctx()):
        book["cash"] += credit
        book["reserve"] -= position["principal"]
        book["fee"] -= q * Decimal("1.30")
    with localcontext(_dec_ctx()):
        net = credit - position["debit"]
    row["exit_credit_decimal"] = _decimal_text(credit)
    row["net_decimal"] = _decimal_text(net)
    row["cash_after_exit_decimal"], row["reserve_after_exit_decimal"], row["exit_fee_obligation_after_exit_decimal"], row["realized_equity_after_exit_decimal"] = _book_values(book)


def _process_intents(intents, spot_map, quote_map):
    books = {(a, c): {"cash": Decimal("100000"), "reserve": Decimal(0), "fee": Decimal(0), "positions": []} for a, c, _ in BOOKS}
    rows = []
    for intent in sorted(intents, key=lambda x: (x["quote"]["time_local_ns"], TICKERS.index(x["plan"]["ticker"]), x["plan"]["plan_id"], x["row"]["event_id"], x["intent_id"])):
        when = intent["quote"]["time_local_ns"]
        for book in books.values():
            due = [p for p in book["positions"] if p["time"] <= when]
            for p in sorted(due, key=lambda x: (x["time"], TICKERS.index(x["ticker"]), x["row"]["ledger_id"])):
                _finish_position(book, p)
                book["positions"].remove(p)
        q = intent["qty"]
        produced = []
        for arm, cost, slip in BOOKS:
            produced.append((_ledger_row(intent, arm, cost, slip), books[(arm, cost)], slip))
        if q == 0:
            intent["row"]["terminal_reason"] = "NO_FILL"
            intent["row"]["label_available_at"] = when
            for row, book, _ in produced:
                before = _book_values(book)
                row.update({"admission_status": "EVENT_RISK_BUDGET", "fill_status": "NO_FILL", "exit_trigger_kind": "NOT_APPLICABLE", "label_available_at": when,
                            "cash_before_entry_decimal": before[0], "reserve_before_entry_decimal": before[1], "exit_fee_obligation_before_decimal": before[2], "realized_equity_before_decimal": before[3]})
            rows.extend(r for r, _, _ in produced)
            continue
        b_positions = books[("B", "ADVERSE")]["positions"]
        lock = any(p["ticker"] == intent["plan"]["ticker"] for p in b_positions) or len(b_positions) >= 3
        adequate = True
        debits = {}
        for row, book, slip in produced:
            with localcontext(_dec_ctx()):
                debit = Decimal(q) * ((_d(row["entry_ask"]) + slip) * Decimal(100) + Decimal("1.30"))
            debits[row["ledger_id"]] = debit
            with localcontext(_dec_ctx()):
                sufficient = book["cash"] - book["fee"] >= debit + Decimal(q) * Decimal("1.30")
            if not sufficient:
                adequate = False
        if lock or not adequate:
            why = "OPEN_POSITION" if lock else "CAPITAL_BLOCKED"
            intent["row"]["terminal_reason"] = "WAIT"
            intent["row"]["label_available_at"] = when
            for row, _, _ in produced:
                before = _book_values(books[(row["arm"], row["cost"])])
                row.update({"admission_status": "WAIT", "fill_status": "NOT_APPLICABLE", "exit_trigger_kind": "NOT_APPLICABLE", "wait_reason": why, "label_available_at": when,
                            "cash_before_entry_decimal": before[0], "reserve_before_entry_decimal": before[1], "exit_fee_obligation_before_decimal": before[2], "realized_equity_before_decimal": before[3]})
            rows.extend(r for r, _, _ in produced)
            continue
        intent["row"]["terminal_reason"] = "FILLED"
        labels = []
        for row, book, slip in produced:
            before = _book_values(book)
            debit = debits[row["ledger_id"]]
            # debit already includes the entry commission.  Reserve contains
            # only option principal; fee is the distinct future exit reserve.
            with localcontext(_dec_ctx()):
                entry_fee = Decimal(q) * Decimal("1.30")
                principal = debit - entry_fee
                book["cash"] -= debit
                book["reserve"] += principal
                book["fee"] += entry_fee
            after = _book_values(book)
            trigger, kind, ambiguous = (intent["a_trigger"], intent["a_kind"], intent["a_ambiguous"]) if row["arm"] == "A" else (intent["plan"]["horizon_end_local_ns"], "H2", False)
            quotes = _valid_quotes(quote_map, row["decision_id"], trigger if kind != "H2" else trigger-1, intent["plan"]["horizon_end_local_ns"])
            if kind == "H2":
                bidq = next((x for x in quotes if x["time_local_ns"] == trigger), None)
            else:
                bidq = next((x for x in quotes if x["time_local_ns"] > trigger), None)
            bid = None if bidq is None else bidq["bid"]
            bidtime = None if bidq is None else bidq["time_local_ns"]
            timeout = kind == "H2"
            outcome = "TIMEOUT_H2" if timeout else ("STOP_FIRST_OBSERVED" if kind == "STOP" else "TARGET_FIRST_OBSERVED")
            account = intent["plan"]["horizon_end_local_ns"] if bidtime is None else bidtime
            row.update({"admission_status": "ADMITTED", "fill_status": "FILLED", "entry_debit_decimal": _decimal_text(debit), "exit_trigger_time": trigger,
                        "exit_trigger_kind": kind, "exit_bid_time": bidtime, "exit_bid": bid, "accounting_exit_time": account,
                        "outcome": outcome, "missing_exit_flag": bidtime is None, "ambiguous_flag": bool(ambiguous), "label_available_at": account,
                        "cash_before_entry_decimal": before[0], "reserve_before_entry_decimal": before[1], "exit_fee_obligation_before_decimal": before[2], "realized_equity_before_decimal": before[3],
                        "cash_after_entry_decimal": after[0], "reserve_after_entry_decimal": after[1], "exit_fee_obligation_after_entry_decimal": after[2], "realized_equity_after_entry_decimal": after[3]})
            book["positions"].append({"time": account, "ticker": row["ticker"], "row": row, "debit": debit, "principal": principal, "bid": bid, "slip": slip})
            labels.append(account)
        intent["row"]["label_available_at"] = max(labels)
        rows.extend(r for r, _, _ in produced)
    for book in books.values():
        for pos in sorted(list(book["positions"]), key=lambda x: (x["time"], TICKERS.index(x["ticker"]), x["row"]["ledger_id"])):
            _finish_position(book, pos)
            book["positions"].remove(pos)
    return sorted(rows, key=lambda r: (r["event_session_date"], r["ticker"], r["arm"], r["cost"], r["ledger_id"]))


def reconstruct_revisit_mechanics(plans, anchors, spots, quotes, *, config):
    """Rebuild the published synthetic record projection without producer code."""
    by_id, _, _, spot_map, quote_map = _validate(plans, anchors, spots, quotes, config)
    anchors_by_plan = {p["plan_id"]: [] for p in plans}
    for a in anchors:
        anchors_by_plan[a["plan_id"]].append(a)
    rows = []
    fsm_by_id = {}
    for p in plans:
        supplied = anchors_by_plan[p["plan_id"]]
        confluent = [a for a in supplied if {x["kind"] for x in a["components"]} == {"FIB", "WALL"}]
        expected_partition = {"MISSING_SOURCE": "C_MISSING_SOURCE", "INVALID_IB": "C_INVALID_IB", "INVALID_STATE60": "C_INVALID_STATE60"}.get(p["geometry_status"], "ELIGIBLE_ANCHOR_SET" if confluent else "NO_CONFLUENT_ANCHOR")
        _literal(p["geometry_partition"], ("C_MISSING_SOURCE", "C_INVALID_IB", "C_INVALID_STATE60", "NO_CONFLUENT_ANCHOR", "ELIGIBLE_ANCHOR_SET"), "geometry partition type")
        _need(p["geometry_partition"] == expected_partition and (p["geometry_status"] == "AVAILABLE_GEOMETRY" or not supplied), "geometry partition")
        for a in confluent:
            fsm = _event_for(p, a, spot_map)
            row = _base_event(p, a, fsm)
            rows.append(row)
            fsm_by_id[row["revisit_id"]] = (fsm, p, a, supplied)
    candidates = {}
    for row in rows:
        fsm, p, a, supplied = fsm_by_id[row["revisit_id"]]
        if fsm["confirmation"] is not None:
            _apply_candidate(row, p, a, supplied, fsm, spot_map)
            candidates.setdefault((p["ticker"], row["event_session_date"]), []).append(row)
    intents = []
    for group in candidates.values():
        group.sort(key=lambda r: (r["confirmation_time_local_ns"], r["cluster_ordinal"], r["anchor_id"]))
        if len({(r["confirmation_time_local_ns"], r["cluster_ordinal"], r["anchor_id"]) for r in group}) != len(group):
            raise AuditError("candidate rank duplicate")
        winner = group[0]
        for rank, row in enumerate(group, 1):
            row["overlap_rank_json"] = _canonical({"eligible_event_session_date": row["event_session_date"], "confirmation_time_local_ns": row["confirmation_time_local_ns"], "cluster_ordinal": row["cluster_ordinal"], "anchor_id": row["anchor_id"], "rank": rank, "winner_revisit_id": winner["revisit_id"], "winner_event_id": winner["event_id"], "decision": "WINNER" if row is winner else "SUPERSEDED"})
            if row is not winner:
                row["event_status"] = "SUPERSEDED_FIRST_EVENT"
                row["terminal_reason"] = "SUPERSEDED_FIRST_EVENT"
                row["label_available_at"] = max(row["confirmation_time"], winner["confirmation_time"])
                _terminal_trace(fsm_by_id[row["revisit_id"]][0], row, "SUPERSEDED_FIRST_EVENT", row["label_available_at"], "DAY_PRIORITY")
                continue
            fsm, p, a, supplied = fsm_by_id[row["revisit_id"]]
            h = p["horizon_end_local_ns"]
            inside = CONFIG["evaluation_start_date"] <= row["event_session_date"] <= CONFIG["evaluation_end_date"]
            if not inside:
                row["terminal_reason"] = "OUTSIDE_EVALUATION_WINDOW"
                row["label_available_at"] = row["confirmation_time"]
                continue
            if row["confirmation_time"] >= h:
                row["event_status"] = "TOO_LATE"
                row["terminal_reason"] = "TOO_LATE"
                row["option_coverage_status"] = "TOO_LATE"
                row["label_available_at"] = row["confirmation_time"]
                _terminal_trace(fsm, row, "TOO_LATE", row["label_available_at"], "TERMINAL_CLOCK")
                continue
            if row["target_anchor_id"] is None:
                row["event_status"] = "NO_TARGET"
                row["terminal_reason"] = "NO_TARGET"
                row["label_available_at"] = row["confirmation_time"]
                _terminal_trace(fsm, row, "NO_TARGET", row["label_available_at"], "TARGET_ABSENT")
                continue
            trigger, kind, ambiguity = _first_trigger(p, row, spot_map, row["confirmation_time"])
            valid = _valid_quotes(quote_map, row["decision_id"], row["confirmation_time"], h)
            first = valid[0] if valid else None
            if trigger is not None and (first is None or trigger <= first["time_local_ns"]):
                row["event_status"] = "PRE_FILL_TRIGGER_CANCELLED"
                row["terminal_reason"] = "PRE_FILL_TRIGGER_CANCELLED"
                row["option_coverage_status"] = "PRE_FILL_TRIGGER_CANCELLED"
                row["label_available_at"] = trigger
                _terminal_trace(fsm, row, "PRE_FILL_TRIGGER_CANCELLED", trigger, "TRIGGER_PRE_FILL", spot_map[(p["ticker"], trigger)]["spot"])
                continue
            if first is None:
                row["event_status"] = "NO_ENTRY_QUOTE"
                row["terminal_reason"] = "NO_ENTRY_QUOTE"
                row["option_coverage_status"] = "ENTRY_QUOTE_MISSING"
                row["label_available_at"] = h
                _terminal_trace(fsm, row, "NO_ENTRY_QUOTE", h, "ASK_ABSENT")
                continue
            if first["time_local_ns"] == h:
                row["event_status"] = "TOO_LATE"
                row["terminal_reason"] = "TOO_LATE"
                row["option_coverage_status"] = "TOO_LATE"
                row["label_available_at"] = h
                _terminal_trace(fsm, row, "TOO_LATE", h, "TERMINAL_CLOCK")
                continue
            row["entry_quote_time"] = first["time_local_ns"]
            row["entry_quote_time_local_ns"] = first["time_local_ns"]
            row["event_entry_ask"] = first["ask"]
            row["intent_id"] = _digest({"schema": "D_INTENT_V1", "event_id": row["event_id"], "decision_id": row["decision_id"], "entry_quote_time_local_ns": first["time_local_ns"]})
            row["option_coverage_status"] = "ENTRY_QUOTE_VALID"
            with localcontext(_dec_ctx()):
                risk = int(((_d(first["ask"]) + Decimal("0.02")) * Decimal(10000) + Decimal(260)).to_integral_value(rounding=ROUND_CEILING))
            qty = 500000 // risk
            intents.append({"row": row, "plan": p, "quote": first, "risk": risk, "qty": qty, "intent_id": row["intent_id"], "a_trigger": trigger if trigger is not None else h, "a_kind": kind if kind is not None else "H2", "a_ambiguous": ambiguity})
    for row in rows:
        if row["overlap_rank_json"] is None:
            row["overlap_rank_json"] = _canonical({"eligible_event_session_date": None, "confirmation_time_local_ns": None, "cluster_ordinal": row["cluster_ordinal"], "anchor_id": row["anchor_id"], "rank": None, "winner_revisit_id": None, "winner_event_id": None, "decision": "NOT_COMPETING"})
        if row["label_available_at"] is None:
            row["label_available_at"] = by_id[row["plan_id"]]["horizon_end_local_ns"]
        if row["option_coverage_status"] is None:
            row["option_coverage_status"] = "NOT_REQUIRED"
    ledger = _process_intents(intents, spot_map, quote_map)
    # Admission can mature an intent at its ask, while a fill matures at its
    # accounting exit.  Coverage is deliberately computed only after that
    # causal terminal is fixed, never from later spot observations.
    for row in rows:
        row["transition_trace_json"] = _canonical(fsm_by_id[row["revisit_id"]][0]["trace"])
        row["spot_coverage_status"] = _coverage(by_id[row["plan_id"]], fsm_by_id[row["revisit_id"]][0], spot_map, row["label_available_at"])
    events = sorted(rows, key=lambda r: (r["calendar_ordinal"], r["plan_id"], r["anchor_id"]))
    coverage = _make_coverage(plans, anchors_by_plan, events)
    counts = _counts(plans, anchors, events, ledger, coverage)
    return {"status": "SYNTHETIC_MECHANICS_ONLY", "events": events, "ledger": ledger, "plan_coverage": coverage, "counts": counts}


def _make_coverage(plans, anchors_by_plan, events):
    result = []
    for p in plans:
        es = [r for r in events if r["plan_id"] == p["plan_id"]]
        confirmed = [r for r in es if r["event_id"] is not None]
        inside = [r for r in confirmed if CONFIG["evaluation_start_date"] <= r["event_session_date"] <= CONFIG["evaluation_end_date"]]
        outside = [r for r in confirmed if r not in inside]
        supplied = anchors_by_plan[p["plan_id"]]
        elig = [a for a in supplied if {x["kind"] for x in a["components"]} == {"FIB", "WALL"}]
        first = min(confirmed, key=lambda r: (r["confirmation_time"], r["cluster_ordinal"], r["anchor_id"])) if confirmed else None
        evidence = []
        for r in sorted(confirmed, key=lambda r: (r["event_session_date"], r["confirmation_time"], r["cluster_ordinal"], r["anchor_id"])):
            decision = json.loads(r["overlap_rank_json"])["decision"]
            status = "IN_EVALUATION_WINDOW" if r in inside else "OUTSIDE_EVALUATION_WINDOW"
            label = {"NO_TARGET": "NO_INTENT_NO_TARGET", "SUPERSEDED_FIRST_EVENT": "NO_INTENT_SUPERSEDED", "OUTSIDE_EVALUATION_WINDOW": "NO_INTENT_OUTSIDE_EVALUATION_WINDOW", "PRE_FILL_TRIGGER_CANCELLED": "NO_INTENT_PRE_FILL_TRIGGER_CANCELLED", "NO_ENTRY_QUOTE": "NO_INTENT_ENTRY_QUOTE_MISSING", "TOO_LATE": "NO_INTENT_TOO_LATE", "WAIT": "INTENT_WAIT", "NO_FILL": "INTENT_NO_FILL", "FILLED": "INTENT_FILLED"}[r["terminal_reason"]]
            evidence.append({"event_session_date": r["event_session_date"], "confirmation_time_local_ns": r["confirmation_time"], "revisit_id": r["revisit_id"], "event_id": r["event_id"], "overlap_decision": decision, "winner_event_id": json.loads(r["overlap_rank_json"])["winner_event_id"], "window_status": status, "terminal_reason": r["terminal_reason"], "intent_id": r["intent_id"], "economic_intent_status": label})
        terminals = {t: sum(r["terminal_reason"] == t for r in es) for t in TERMINALS}
        row = {"calendar_ordinal": p["calendar_ordinal"], "plan_id": p["plan_id"], "ticker": p["ticker"], "trade_date": p["trade_date"], "expiry_date": p["expiry_date"], "geometry_partition": p["geometry_partition"], "c_anchor_count": len(supplied), "eligible_anchor_count": len(elig), "revisit_row_count": len(es), "confirmed_event_count": len(confirmed), "first_physical_event_id": None if first is None else first["event_id"], "first_physical_event_time": None if first is None else first["confirmation_time"], "outside_evaluation_event_count": len(outside), "in_evaluation_event_count": len(inside), "economic_intent_count": sum(r["intent_id"] is not None for r in es), "event_day_evidence_json": _canonical(evidence), "terminal_status_counts_json": _canonical(terminals), "b_plan_pin": p["b_plan_pin"], "c_geometry_pin": p["c_geometry_pin"]}
        result.append(row)
    return result


def _counts(plans, anchors, events, ledger, coverage):
    c = {k: 0 for k in COUNT_FIELDS}
    c["plan_rows"] = len(plans)
    c["plan_coverage_rows"] = len(plans)
    for p in plans:
        part = p["geometry_partition"]
        c[{"C_MISSING_SOURCE": "plans_c_missing_geometry", "C_INVALID_IB": "plans_c_invalid_geometry", "C_INVALID_STATE60": "plans_c_invalid_geometry", "NO_CONFLUENT_ANCHOR": "plans_no_confluent_anchor", "ELIGIBLE_ANCHOR_SET": "plans_with_eligible_anchor"}[part]] += 1
    c["eligible_revisit_rows"] = len(events)
    c["revisit_rows"] = len(events)
    c["ineligible_nonconfluence_rows"] = len(anchors) - len(events)
    for p in coverage:
        inside, outside = p["in_evaluation_event_count"], p["outside_evaluation_event_count"]
        c["plans_no_confirmed_event" if inside + outside == 0 else "plans_with_mixed_evaluation_events" if inside and outside else "plans_with_only_in_evaluation_events" if inside else "plans_with_only_outside_evaluation_events"] += 1
    mapping = {"NO_VISIT": "no_visit_rows", "NO_DEPARTURE": "no_departure_rows", "CROSS_THROUGH": "cross_through_rows", "NO_REVISIT": "no_revisit_rows", "NO_CONFIRMATION": "no_confirmation_rows", "NO_TARGET": "no_target_rows", "SUPERSEDED_FIRST_EVENT": "superseded_first_event_rows", "PRE_FILL_TRIGGER_CANCELLED": "pre_fill_trigger_cancelled_rows", "NO_ENTRY_QUOTE": "no_entry_quote_rows", "TOO_LATE": "too_late_rows", "NOT_EVALUABLE": "not_evaluable_rows"}
    for e in events:
        if e["event_id"] is not None:
            c["confirmed_rows"] += 1
        if e["terminal_reason"] in mapping:
            c[mapping[e["terminal_reason"]]] += 1
    ids = {r["intent_id"] for r in ledger}
    c["common_intent_rows"] = len(ids)
    for ident in ids:
        rows = [r for r in ledger if r["intent_id"] == ident]
        status = rows[0]["admission_status"]
        if status == "ADMITTED":
            c["admitted_intent_rows"] += 1
        elif status == "WAIT":
            c["wait_rows"] += 1
            wait_count_key = "open_position_rows" if rows[0]["wait_reason"] == "OPEN_POSITION" else "capital_blocked_rows"
            c[wait_count_key] += 1
        else:
            c["event_risk_budget_rows"] += 1
    for r in ledger:
        if r["fill_status"] == "NO_FILL":
            c["no_fill_rows"] += 1
        if r["fill_status"] == "FILLED":
            c["filled_rows"] += 1
        if r["missing_exit_flag"]:
            c["missing_exit_rows"] += 1
        if r["ambiguous_flag"]:
            c["ambiguous_rows"] += 1
        c[{("A", "BASE"): "a_base_ledger_rows", ("A", "ADVERSE"): "a_adverse_ledger_rows", ("B", "BASE"): "b_base_ledger_rows", ("B", "ADVERSE"): "b_adverse_ledger_rows"}[(r["arm"], r["cost"])]] += 1
    return c


def _strict_equal(observed, expected, path="observed"):
    """Compare the public projection without Python's cross-type equality."""
    if type(observed) is not type(expected):
        raise AuditError("type mismatch: " + path)
    if type(expected) is float:
        if observed.hex() != expected.hex():
            raise AuditError("float mismatch: " + path)
        return
    if type(expected) is dict:
        if set(observed) != set(expected):
            raise AuditError("mapping keys: " + path)
        for key in expected:
            _strict_equal(observed[key], expected[key], path + "." + repr(key))
        return
    if type(expected) is list:
        if len(observed) != len(expected):
            raise AuditError("list length: " + path)
        for i, (left, right) in enumerate(zip(observed, expected)):
            _strict_equal(left, right, path + "[" + str(i) + "]")
        return
    if observed != expected:
        raise AuditError("value mismatch: " + path)


def _optional(value, validator, where):
    if value is not None:
        validator(value, where)


def _nonempty_text(value, where):
    _need(type(value) is str and value, where)


def _json(value, where):
    _need(type(value) is str, where)
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError) as exc:
        raise AuditError(where) from exc
    _need(_canonical(parsed) == value, where)
    return parsed


def _decimal_string(value, where):
    _need(type(value) is str and value, where)
    try:
        parsed = Decimal(value)
    except Exception as exc:
        raise AuditError(where) from exc
    _need(parsed.is_finite() and _decimal_text(parsed) == value, where)


def _trace_projection(value):
    trace = _json(value, "canonical trace")
    _need(type(trace) is list, "trace list")
    trace_fields = {"seq", "kind", "time_local_ns", "spot_f64", "side", "state_before", "state_after", "reason"}
    for expected_seq, item in enumerate(trace):
        _need(type(item) is dict and set(item) == trace_fields, "trace schema")
        _i32(item["seq"], "trace seq", nonnegative=True)
        _need(item["seq"] == expected_seq, "trace sequence")
        _i64(item["time_local_ns"], "trace time")
        _literal(item["kind"], TRACE_KINDS, "trace kind")
        _literal(item["state_before"], TRACE_STATES, "trace before")
        _literal(item["state_after"], TRACE_STATES, "trace after")
        _literal(item["reason"], TRACE_REASONS, "trace reason")
        _need(item["side"] is None or (type(item["side"]) is str and item["side"] in ("ABOVE", "BELOW")), "trace side")
        if item["spot_f64"] is not None:
            _need(type(item["spot_f64"]) is str, "trace spot")
            try:
                parsed_spot = float.fromhex(item["spot_f64"])
            except (OverflowError, ValueError) as exc:
                raise AuditError("trace spot") from exc
            _need(math.isfinite(parsed_spot) and item["spot_f64"] == parsed_spot.hex(), "trace spot")


def _event_projection(row):
    _i32(row["calendar_ordinal"], "event calendar", nonnegative=True)
    _nonempty_text(row["plan_id"], "event plan")
    _literal(row["ticker"], TICKERS, "event ticker")
    _date(row["trade_date"], "event trade date")
    _date(row["expiry_date"], "event expiry date")
    _nonempty_text(row["anchor_id"], "event anchor")
    _i16(row["cluster_ordinal"], "event cluster", nonnegative=True)
    _finite_float(row["center"], "event center")
    _finite_float(row["band"], "event band", True)
    _i16(row["source_mask"], "event source mask", nonnegative=True)
    _i64(row["anchor_available_at"], "event availability")
    _pin(row["revisit_id"], "revisit id")
    _literal(row["event_status"], EVENT_STATUSES, "event status")
    _need(row["armed_side"] is None or row["armed_side"] in ("ABOVE", "BELOW") and type(row["armed_side"]) is str, "armed side")
    for key in ("visit_time", "departure_time", "revisit_time", "confirmation_time", "confirmation_time_local_ns", "entry_quote_time", "entry_quote_time_local_ns"):
        _optional(row[key], _i64, "event " + key)
    _need(row["confirmation_time"] == row["confirmation_time_local_ns"], "confirmation clocks")
    _need(row["entry_quote_time"] == row["entry_quote_time_local_ns"], "entry clocks")
    _need(row["departure_side"] is None or row["departure_side"] in ("ABOVE", "BELOW") and type(row["departure_side"]) is str, "departure side")
    _need(row["event_id"] is None or type(row["event_id"]) is str and len(row["event_id"]) == 64, "event id")
    _need(row["event_session_date"] is None or _date(row["event_session_date"], "event session date"), "event session date")
    _need(row["decision_id"] is None or type(row["decision_id"]) is str and row["decision_id"], "event decision")
    _need(row["side"] is None or row["side"] in ("CALL", "PUT") and type(row["side"]) is str, "event right")
    for key in ("stop_spot", "target_spot", "event_entry_ask"):
        _optional(row[key], _finite_float, "event " + key)
    _need(row["target_anchor_id"] is None or type(row["target_anchor_id"]) is str and row["target_anchor_id"], "target anchor")
    _need(row["intent_id"] is None or type(row["intent_id"]) is str and len(row["intent_id"]) == 64, "intent id")
    _literal(row["terminal_reason"], TERMINALS, "terminal reason")
    overlap = _json(row["overlap_rank_json"], "overlap ranking")
    overlap_fields = {
        "eligible_event_session_date", "confirmation_time_local_ns", "cluster_ordinal",
        "anchor_id", "rank", "winner_revisit_id", "winner_event_id", "decision",
    }
    _need(type(overlap) is dict and set(overlap) == overlap_fields, "overlap schema")
    _need(overlap["eligible_event_session_date"] is None or _date(overlap["eligible_event_session_date"], "overlap date"), "overlap date")
    _optional(overlap["confirmation_time_local_ns"], _i64, "overlap confirmation")
    _i16(overlap["cluster_ordinal"], "overlap cluster", nonnegative=True)
    _nonempty_text(overlap["anchor_id"], "overlap anchor")
    _need(overlap["rank"] is None or type(overlap["rank"]) is int and overlap["rank"] > 0, "overlap rank")
    for key in ("winner_revisit_id", "winner_event_id"):
        _need(overlap[key] is None or type(overlap[key]) is str and len(overlap[key]) == 64, "overlap " + key)
    _literal(overlap["decision"], ("WINNER", "SUPERSEDED", "NOT_COMPETING"), "overlap decision")
    _trace_projection(row["transition_trace_json"])
    _literal(row["spot_coverage_status"], ("COMPLETE", "MISSING_MINUTE", "MISSING_SESSION", "NOT_EVALUABLE"), "spot coverage")
    _literal(row["option_coverage_status"], ("NOT_REQUIRED", "ENTRY_QUOTE_VALID", "ENTRY_QUOTE_MISSING", "PRE_FILL_TRIGGER_CANCELLED", "TOO_LATE"), "option coverage")
    _i64(row["label_available_at"], "event label")
    _pin(row["b_plan_pin"], "event b pin")
    _pin(row["c_anchor_pin"], "event c pin")


def _ledger_projection(row):
    for key in ("ledger_id", "intent_id", "event_id"):
        _pin(row[key], "ledger " + key)
    for key in ("plan_id", "decision_id"):
        _nonempty_text(row[key], "ledger " + key)
    _literal(row["ticker"], TICKERS, "ledger ticker")
    _date(row["event_session_date"], "ledger event date")
    _literal(row["arm"], ("A", "B"), "ledger arm")
    _literal(row["cost"], ("BASE", "ADVERSE"), "ledger cost")
    _literal(row["admission_status"], ("ADMITTED", "WAIT", "EVENT_RISK_BUDGET"), "ledger admission")
    _literal(row["fill_status"], ("FILLED", "NO_FILL", "NOT_APPLICABLE"), "ledger fill")
    for key in ("decision_time", "entry_quote_time", "horizon_end", "label_available_at"):
        _i64(row[key], "ledger " + key)
    _literal(row["right"], ("CALL", "PUT"), "ledger right")
    _finite_float(row["entry_ask"], "ledger entry ask", True)
    _decimal_string(row["slippage_dollars"], "ledger slippage")
    _i64(row["unit_risk_cents"], "ledger risk")
    _need(row["unit_risk_cents"] > 0, "ledger risk")
    _i32(row["qty"], "ledger qty", nonnegative=True)
    for key in ("entry_debit_decimal", "exit_credit_decimal", "net_decimal", "cash_before_entry_decimal", "reserve_before_entry_decimal", "exit_fee_obligation_before_decimal", "realized_equity_before_decimal", "cash_after_entry_decimal", "reserve_after_entry_decimal", "exit_fee_obligation_after_entry_decimal", "realized_equity_after_entry_decimal", "cash_after_exit_decimal", "reserve_after_exit_decimal", "exit_fee_obligation_after_exit_decimal", "realized_equity_after_exit_decimal"):
        _optional(row[key], _decimal_string, "ledger " + key)
    for key in ("exit_trigger_time", "exit_bid_time", "accounting_exit_time"):
        _optional(row[key], _i64, "ledger " + key)
    _literal(row["exit_trigger_kind"], ("TARGET", "STOP", "H2", "NOT_APPLICABLE"), "ledger trigger")
    _optional(row["exit_bid"], _finite_float, "ledger bid")
    _need(row["outcome"] is None or row["outcome"] in ("TARGET_FIRST_OBSERVED", "STOP_FIRST_OBSERVED", "TIMEOUT_H2") and type(row["outcome"]) is str, "ledger outcome")
    _need(type(row["missing_exit_flag"]) is bool and type(row["ambiguous_flag"]) is bool, "ledger flags")
    _need(row["wait_reason"] is None or row["wait_reason"] in ("CAPITAL_BLOCKED", "OPEN_POSITION") and type(row["wait_reason"]) is str, "ledger wait")
    _pin(row["b_value_pin"], "ledger b pin")
    _pin(row["c_geometry_pin"], "ledger c pin")
    _need(row["replay_contract_pin"] == RISK_PIN, "ledger risk pin")
    before_fields = (
        "cash_before_entry_decimal", "reserve_before_entry_decimal",
        "exit_fee_obligation_before_decimal", "realized_equity_before_decimal",
    )
    after_fields = (
        "cash_after_entry_decimal", "reserve_after_entry_decimal",
        "exit_fee_obligation_after_entry_decimal", "realized_equity_after_entry_decimal",
        "cash_after_exit_decimal", "reserve_after_exit_decimal",
        "exit_fee_obligation_after_exit_decimal", "realized_equity_after_exit_decimal",
    )
    _need(all(row[key] is not None for key in before_fields), "ledger before balances")
    if row["fill_status"] == "FILLED":
        _need(row["admission_status"] == "ADMITTED" and row["qty"] > 0, "filled admission")
        _need(all(row[key] is not None for key in after_fields), "filled balances")
        _need(row["entry_debit_decimal"] is not None and row["exit_credit_decimal"] is not None and row["net_decimal"] is not None, "filled accounting")
        _need(row["exit_trigger_kind"] in ("TARGET", "STOP", "H2") and row["exit_trigger_time"] is not None, "filled trigger")
        if row["missing_exit_flag"]:
            _need(row["exit_bid"] is None and row["exit_bid_time"] is None and row["accounting_exit_time"] == row["horizon_end"], "missing exit")
        else:
            _need(row["exit_bid"] is not None and row["exit_bid_time"] is not None and row["accounting_exit_time"] == row["exit_bid_time"], "observed exit")
    else:
        _need(all(row[key] is None for key in after_fields), "unfilled balances")
        _need(row["entry_debit_decimal"] is None and row["exit_credit_decimal"] is None and row["net_decimal"] is None, "unfilled accounting")
        _need(row["exit_trigger_kind"] == "NOT_APPLICABLE" and row["exit_trigger_time"] is None, "unfilled trigger")
        _need(row["exit_bid"] is None and row["exit_bid_time"] is None and row["accounting_exit_time"] is None, "unfilled exit")
        _need(not row["missing_exit_flag"] and not row["ambiguous_flag"] and row["outcome"] is None, "unfilled flags")
        if row["fill_status"] == "NO_FILL":
            _need(row["admission_status"] == "EVENT_RISK_BUDGET" and row["qty"] == 0 and row["wait_reason"] is None, "risk budget")
        else:
            _need(row["admission_status"] == "WAIT" and row["wait_reason"] is not None, "wait row")


def _projection_invariants(result):
    _need(set(result) == {"status", "events", "ledger", "plan_coverage", "counts"}, "return keys")
    _need(result["status"] == "SYNTHETIC_MECHANICS_ONLY", "return status")
    _need(all(set(row) == set(EVENT_FIELDS) for row in result["events"]), "event schema")
    _need(all(set(row) == set(LEDGER_FIELDS) for row in result["ledger"]), "ledger schema")
    _need(all(set(row) == set(COVERAGE_FIELDS) for row in result["plan_coverage"]), "coverage schema")
    _need(result["events"] == sorted(result["events"], key=lambda row: (row["calendar_ordinal"], row["plan_id"], row["anchor_id"])), "event order")
    _need(result["ledger"] == sorted(result["ledger"], key=lambda row: (row["event_session_date"], row["ticker"], row["arm"], row["cost"], row["ledger_id"])), "ledger order")
    _need(result["plan_coverage"] == sorted(result["plan_coverage"], key=lambda row: (row["calendar_ordinal"], row["plan_id"])), "coverage order")
    event_ids = set()
    events_by_id = {}
    intent_ids = set()
    for row in result["events"]:
        _event_projection(row)
        if row["event_id"] is not None:
            _need(row["event_id"] not in event_ids, "event FK")
            event_ids.add(row["event_id"])
            events_by_id[row["event_id"]] = row
        if row["intent_id"] is not None:
            _need(row["intent_id"] not in intent_ids, "intent FK")
            intent_ids.add(row["intent_id"])
    ledger_ids = set()
    for row in result["ledger"]:
        _ledger_projection(row)
        _need(row["ledger_id"] not in ledger_ids and row["event_id"] in event_ids and row["intent_id"] in intent_ids, "ledger FK")
        ledger_ids.add(row["ledger_id"])
    for row in result["plan_coverage"]:
        _i32(row["calendar_ordinal"], "coverage calendar", nonnegative=True)
        _nonempty_text(row["plan_id"], "coverage plan")
        _literal(row["ticker"], TICKERS, "coverage ticker")
        _date(row["trade_date"], "coverage trade date")
        _date(row["expiry_date"], "coverage expiry date")
        _literal(row["geometry_partition"], GEOMETRY_PARTITIONS, "coverage partition")
        for key in ("c_anchor_count", "eligible_anchor_count", "revisit_row_count", "confirmed_event_count", "outside_evaluation_event_count", "in_evaluation_event_count", "economic_intent_count"):
            _i32(row[key], "coverage " + key, nonnegative=True)
        _need(row["first_physical_event_id"] is None or type(row["first_physical_event_id"]) is str and len(row["first_physical_event_id"]) == 64, "coverage first event")
        _optional(row["first_physical_event_time"], _i64, "coverage first time")
        evidence = _json(row["event_day_evidence_json"], "coverage event evidence")
        _need(type(evidence) is list, "coverage event evidence")
        evidence_fields = {
            "event_session_date", "confirmation_time_local_ns", "revisit_id", "event_id",
            "overlap_decision", "winner_event_id", "window_status", "terminal_reason",
            "intent_id", "economic_intent_status",
        }
        evidence_order = None
        for item in evidence:
            _need(type(item) is dict and set(item) == evidence_fields, "coverage evidence schema")
            _date(item["event_session_date"], "coverage evidence date")
            _i64(item["confirmation_time_local_ns"], "coverage evidence confirmation")
            _pin(item["revisit_id"], "coverage evidence revisit")
            _pin(item["event_id"], "coverage evidence event")
            _literal(item["overlap_decision"], ("WINNER", "SUPERSEDED"), "coverage overlap")
            _need(item["winner_event_id"] is None or type(item["winner_event_id"]) is str and len(item["winner_event_id"]) == 64, "coverage winner")
            _literal(item["window_status"], ("OUTSIDE_EVALUATION_WINDOW", "IN_EVALUATION_WINDOW"), "coverage window")
            _literal(item["terminal_reason"], TERMINALS, "coverage terminal")
            _need(item["intent_id"] is None or type(item["intent_id"]) is str and len(item["intent_id"]) == 64, "coverage intent")
            _literal(item["economic_intent_status"], ("NO_INTENT_NO_TARGET", "NO_INTENT_SUPERSEDED", "NO_INTENT_OUTSIDE_EVALUATION_WINDOW", "NO_INTENT_PRE_FILL_TRIGGER_CANCELLED", "NO_INTENT_ENTRY_QUOTE_MISSING", "NO_INTENT_TOO_LATE", "INTENT_WAIT", "INTENT_NO_FILL", "INTENT_FILLED"), "coverage intent status")
            matching_event = events_by_id.get(item["event_id"])
            _need(matching_event is not None, "coverage evidence event FK")
            current_order = (
                item["event_session_date"], item["confirmation_time_local_ns"],
                matching_event["cluster_ordinal"], matching_event["anchor_id"],
            )
            _need(evidence_order is None or current_order >= evidence_order, "coverage evidence order")
            evidence_order = current_order
        terminal_counts = _json(row["terminal_status_counts_json"], "coverage terminal counts")
        _need(type(terminal_counts) is dict and set(terminal_counts) == set(TERMINALS), "coverage terminal schema")
        for value in terminal_counts.values():
            _i32(value, "coverage terminal count", nonnegative=True)
        _pin(row["b_plan_pin"], "coverage b pin")
        _pin(row["c_geometry_pin"], "coverage c pin")
    counts = result["counts"]
    _need(set(counts) == set(COUNT_FIELDS) and all(_is_int(v) and v >= 0 for v in counts.values()), "count schema")
    _need(counts["plan_rows"] == counts["plan_coverage_rows"], "plan counts")
    _need(sum(counts[key] for key in ("plans_c_missing_geometry", "plans_c_invalid_geometry", "plans_no_confluent_anchor", "plans_with_eligible_anchor")) == counts["plan_rows"], "geometry partitions")
    _need(sum(counts[key] for key in ("plans_no_confirmed_event", "plans_with_only_outside_evaluation_events", "plans_with_only_in_evaluation_events", "plans_with_mixed_evaluation_events")) == counts["plan_rows"], "window partitions")
    _need(counts["eligible_revisit_rows"] == counts["revisit_rows"], "eligible revisit equality")
    _need(counts["common_intent_rows"] == counts["admitted_intent_rows"] + counts["wait_rows"] + counts["event_risk_budget_rows"], "intent partition")
    _need(counts["capital_blocked_rows"] + counts["open_position_rows"] == counts["wait_rows"], "wait partition")
    _need(counts["no_fill_rows"] == 4 * counts["event_risk_budget_rows"] and counts["filled_rows"] == 4 * counts["admitted_intent_rows"], "fill partition")
    _need(counts["missing_exit_rows"] <= counts["filled_rows"] and counts["ambiguous_rows"] <= counts["filled_rows"], "orthogonal coverage flags")
    _need(sum(counts[x] for x in ("a_base_ledger_rows", "a_adverse_ledger_rows", "b_base_ledger_rows", "b_adverse_ledger_rows")) == 4 * counts["common_intent_rows"], "book partition")
    _need(counts["a_base_ledger_rows"] == counts["a_adverse_ledger_rows"] == counts["b_base_ledger_rows"] == counts["b_adverse_ledger_rows"] == counts["common_intent_rows"], "four book cardinality")


def audit_revisit_mechanics(plans, anchors, spots, quotes, observed, *, config):
    """Independently rebuild and compare the complete public synthetic projection."""
    actual = reconstruct_revisit_mechanics(plans, anchors, spots, quotes, config=config)
    _need(type(observed) is dict and set(observed) == set(actual), "observed top-level keys")
    _projection_invariants(actual)
    _projection_invariants(observed)
    _strict_equal(observed, actual)
    return {"status": "PASS_SYNTHETIC_D_MECHANICS_AUDIT", "counts": actual["counts"]}


# The name proposed in the implementation hand-off is a compatibility alias.
evaluate_revisit_mechanics = reconstruct_revisit_mechanics
