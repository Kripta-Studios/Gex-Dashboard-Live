"""Pure standard-library, in-memory mechanics for artificial D fixtures only."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
import hashlib
import json
import math
from typing import Any

from weekly_zone_revisit_accounting import replay_portfolio

N = 60_000_000_000
EPOCH = datetime(1970, 1, 1)
PIN = "9c387e9bea74ba65777808b5ac5e5fccfdc2437645e7b301c15eab2d33bbeb7b"
FIXED_RISK_CONTRACT_PIN = PIN
TICKERS = ("SPY", "QQQ", "SPXW")
TERMINALS = ("NO_VISIT","NO_DEPARTURE","CROSS_THROUGH","NO_REVISIT","NO_CONFIRMATION","NO_TARGET","SUPERSEDED_FIRST_EVENT","PRE_FILL_TRIGGER_CANCELLED","NO_ENTRY_QUOTE","TOO_LATE","OUTSIDE_EVALUATION_WINDOW","WAIT","NO_FILL","FILLED","NOT_EVALUABLE")
COUNT_KEYS = ("plan_rows","plan_coverage_rows","plans_c_missing_geometry","plans_c_invalid_geometry","plans_no_confluent_anchor","plans_with_eligible_anchor","plans_no_confirmed_event","plans_with_only_outside_evaluation_events","plans_with_only_in_evaluation_events","plans_with_mixed_evaluation_events","eligible_revisit_rows","ineligible_nonconfluence_rows","revisit_rows","confirmed_rows","no_visit_rows","no_departure_rows","cross_through_rows","no_revisit_rows","no_confirmation_rows","no_target_rows","superseded_first_event_rows","pre_fill_trigger_cancelled_rows","no_entry_quote_rows","too_late_rows","not_evaluable_rows","common_intent_rows","admitted_intent_rows","wait_rows","event_risk_budget_rows","capital_blocked_rows","open_position_rows","no_fill_rows","filled_rows","missing_exit_rows","ambiguous_rows","a_base_ledger_rows","a_adverse_ledger_rows","b_base_ledger_rows","b_adverse_ledger_rows")
PK = {"calendar_ordinal","plan_id","ticker","trade_date","expiry_date","call_decision_id","put_decision_id","horizon_end_local_ns","d_1030_local_ns","d_session_date","d1_session_date","h2_session_date","d_session_kind","d1_session_kind","h2_session_kind","d_rth_open_local_ns","d_rth_close_local_ns","d1_rth_open_local_ns","d1_rth_close_local_ns","h2_rth_open_local_ns","h2_rth_close_local_ns","expected_rth_minutes","b_plan_pin","b_value_pin","c_anchor_pin","c_geometry_pin","fixed_risk_contract_pin","geometry_status","geometry_partition"}
AK = {"plan_id","anchor_id","cluster_ordinal","center","band","source_mask","anchor_available_at_local_ns","valid_geometry","components","c_anchor_pin","c_geometry_pin"}
SK = {"ticker", "time_local_ns", "trade_date", "spot", "valid_rth"}
QK = {"decision_id", "time_local_ns", "ask", "bid"}

class MechanicsError(ValueError):
    pass


def C(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def I(schema: str, **payload: Any) -> str:
    return hashlib.sha256(C({"schema": schema, **payload}).encode("utf-8")).hexdigest()


def fl(value: Any, label: str) -> float:
    if type(value) is not float or not math.isfinite(value):
        raise MechanicsError(label)
    return value


def day(value: Any, label: str) -> str:
    if type(value) is not str or not value.isascii():
        raise MechanicsError(label)
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise MechanicsError(label) from error
    if parsed.isoformat() != value:
        raise MechanicsError(label)
    return value


def civil(day_text: str, hour: int, minute: int) -> int:
    delta = datetime.combine(date.fromisoformat(day_text), time(hour, minute)) - EPOCH
    return (delta.days * 86400 + delta.seconds) * 1_000_000_000 + delta.microseconds * 1000


def goodq(quote: dict[str, Any]) -> bool:
    ask, bid = quote["ask"], quote["bid"]
    return type(ask) is float and type(bid) is float and math.isfinite(ask) and math.isfinite(bid) and ask > 0 and 0 <= bid <= ask


def confl(anchor: dict[str, Any]) -> bool:
    return {component["kind"] for component in anchor["components"]} >= {"FIB", "WALL"}


def trace(event_row, kind, moment, spot_value, side, before, after, reason) -> None:
    event_row["_t"].append({"seq": len(event_row["_t"]), "kind": kind, "time_local_ns": moment, "spot_f64": None if spot_value is None else spot_value.hex(), "side": side, "state_before": before, "state_after": after, "reason": reason})


def grid(plan_row: dict[str, Any]) -> list[int]:
    result = []
    for prefix in ("d", "d1"):
        session_date = plan_row[prefix + "_session_date"]
        opening = civil(session_date, 9, 30)
        closing = civil(session_date, 13 if plan_row[prefix + "_session_kind"] == "SHORT" else 16, 0)
        result.extend(range(opening, closing + N, N))
    result.extend(range(civil(plan_row["h2_session_date"], 9, 30), plan_row["horizon_end_local_ns"] + N, N))
    return result


def part(plan_row: dict[str, Any], levels: list[dict[str, Any]]) -> str:
    invalid = {"MISSING_SOURCE": "C_MISSING_SOURCE", "INVALID_IB": "C_INVALID_IB", "INVALID_STATE60": "C_INVALID_STATE60"}
    status = plan_row["geometry_status"]
    if status in invalid:
        return invalid[status]
    if status != "AVAILABLE_GEOMETRY":
        raise MechanicsError("geometry status")
    return "ELIGIBLE_ANCHOR_SET" if any(confl(anchor) for anchor in levels) else "NO_CONFLUENT_ANCHOR"

def _integer(value: Any, bits: int, label: str, nonnegative: bool = False) -> int:
    lower = 0 if nonnegative else -(1 << (bits - 1))
    if type(value) is not int or not lower <= value < (1 << (bits - 1)):
        raise MechanicsError(label + ": integer projection")
    return value


def _text(value: Any, label: str) -> str:
    if type(value) is not str or not value:
        raise MechanicsError(label + ": string projection")
    return value


def _records(value: Any, fields: set[str], label: str) -> None:
    if type(value) is not list or any(type(row) is not dict or set(row) != fields for row in value):
        raise MechanicsError(label + ": record projection")


def _ordered_unique(keys: list[tuple], label: str) -> None:
    if keys != sorted(keys) or len(keys) != len(set(keys)):
        raise MechanicsError(label + ": order or duplicate")


def _validate(plans, anchors, spots, quotes, config) -> dict[str, list[dict[str, Any]]]:
    expected_config = {"evaluation_start_date": "2026-01-02", "evaluation_end_date": "2026-09-17"}
    if type(config) is not dict or set(config) != set(expected_config):
        raise MechanicsError("config projection")
    if any(type(config[key]) is not str or config[key] != value for key, value in expected_config.items()):
        raise MechanicsError("fixed entry window")
    _records(plans, PK, "plans")
    _records(anchors, AK, "anchors")
    _records(spots, SK, "spots")
    _records(quotes, QK, "quotes")
    if not plans:
        raise MechanicsError("empty plans")
    plan_map = {}
    physical_plans = set()
    decisions = {}
    sessions = {}
    for plan in plans:
        _integer(plan["calendar_ordinal"], 32, "calendar ordinal", True)
        plan_id = _text(plan["plan_id"], "plan ID")
        ticker = _text(plan["ticker"], "ticker")
        if ticker not in TICKERS:
            raise MechanicsError("ticker")
        for key in ("trade_date", "expiry_date", "d_session_date", "d1_session_date", "h2_session_date"):
            day(plan[key], key)
        if plan_id in plan_map or (ticker, plan["trade_date"]) in physical_plans:
            raise MechanicsError("plan identity")
        if plan["trade_date"] != plan["d_session_date"] or not plan["d_session_date"] < plan["d1_session_date"] < plan["h2_session_date"]:
            raise MechanicsError("three session identities")
        for prefix in ("d", "d1", "h2"):
            session_date = plan[prefix + "_session_date"]
            kind = _text(plan[prefix + "_session_kind"], "session kind")
            if kind not in ("FULL", "SHORT"):
                raise MechanicsError("session kind")
            opening = _integer(plan[prefix + "_rth_open_local_ns"], 64, "session open")
            closing = _integer(plan[prefix + "_rth_close_local_ns"], 64, "session close")
            if opening != civil(session_date, 9, 30) or closing != civil(session_date, 13 if kind == "SHORT" else 16, 0):
                raise MechanicsError("exact session clocks")
            physical_key = (ticker, session_date)
            identity = (kind, opening, closing)
            if physical_key in sessions and sessions[physical_key] != identity:
                raise MechanicsError("conflicting physical session")
            sessions[physical_key] = identity
        if _integer(plan["d_1030_local_ns"], 64, "D10:30") != civil(plan["trade_date"], 10, 30):
            raise MechanicsError("exact D10:30")
        if _integer(plan["horizon_end_local_ns"], 64, "H2") != civil(plan["h2_session_date"], 10, 35):
            raise MechanicsError("exact H2")
        minutes = plan["expected_rth_minutes"]
        if type(minutes) is not list:
            raise MechanicsError("minute grid projection")
        for minute in minutes:
            _integer(minute, 64, "grid minute")
        if minutes != grid(plan):
            raise MechanicsError("complete exact minute grid")
        for key in ("b_plan_pin", "b_value_pin", "c_anchor_pin", "c_geometry_pin"):
            value = _text(plan[key], key)
            if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
                raise MechanicsError("SHA pin")
        if type(plan["fixed_risk_contract_pin"]) is not str or plan["fixed_risk_contract_pin"] != PIN:
            raise MechanicsError("risk pin")
        _text(plan["geometry_status"], "geometry status")
        _text(plan["geometry_partition"], "geometry partition")
        for key in ("call_decision_id", "put_decision_id"):
            decision_id = _text(plan[key], key)
            if decision_id in decisions:
                raise MechanicsError("decision identity")
            decisions[decision_id] = plan
        plan_map[plan_id] = plan
        physical_plans.add((ticker, plan["trade_date"]))
    _ordered_unique([(p["calendar_ordinal"], p["plan_id"]) for p in plans], "plans")
    grouped = {plan_id: [] for plan_id in plan_map}
    anchor_keys = set()
    cluster_keys = set()
    for anchor in anchors:
        plan_id = _text(anchor["plan_id"], "anchor plan")
        anchor_id = _text(anchor["anchor_id"], "anchor ID")
        ordinal = _integer(anchor["cluster_ordinal"], 16, "cluster ordinal", True)
        _integer(anchor["source_mask"], 16, "source mask", True)
        if plan_id not in plan_map or (plan_id, anchor_id) in anchor_keys or (plan_id, ordinal) in cluster_keys:
            raise MechanicsError("anchor identity")
        plan = plan_map[plan_id]
        if anchor["valid_geometry"] is not True:
            raise MechanicsError("invalid supplied level")
        center = fl(anchor["center"], "center")
        band = fl(anchor["band"], "band")
        if band <= 0 or not math.isfinite(center - 2 * band) or not math.isfinite(center + 2 * band):
            raise MechanicsError("finite positive band geometry")
        if _integer(anchor["anchor_available_at_local_ns"], 64, "anchor availability") != plan["d_1030_local_ns"]:
            raise MechanicsError("ENTRY_FROZEN availability")
        for key in ("c_anchor_pin", "c_geometry_pin"):
            if type(anchor[key]) is not str or anchor[key] != plan[key]:
                raise MechanicsError("anchor provenance")
        components = anchor["components"]
        if type(components) is not list or not components:
            raise MechanicsError("component list")
        for component in components:
            if type(component) is not dict or set(component) != {"kind"} or type(component["kind"]) is not str or component["kind"] not in ("FIB", "WALL"):
                raise MechanicsError("component projection")
        anchor_keys.add((plan_id, anchor_id))
        cluster_keys.add((plan_id, ordinal))
        grouped[plan_id].append(anchor)
    _ordered_unique([(a["plan_id"], a["cluster_ordinal"], a["anchor_id"]) for a in anchors], "anchors")
    for plan in plans:
        levels = grouped[plan["plan_id"]]
        if plan["geometry_partition"] != part(plan, levels):
            raise MechanicsError("derived geometry partition")
        if plan["geometry_status"] != "AVAILABLE_GEOMETRY" and levels:
            raise MechanicsError("fabricated invalid-geometry level")
    for sample in spots:
        ticker = _text(sample["ticker"], "spot ticker")
        moment = _integer(sample["time_local_ns"], 64, "spot clock")
        if ticker not in TICKERS or type(sample["valid_rth"]) is not bool:
            raise MechanicsError("spot scalar")
        if day(sample["trade_date"], "spot date") != (EPOCH + timedelta(seconds=moment // 1_000_000_000)).date().isoformat():
            raise MechanicsError("spot date/clock")
        if sample["valid_rth"]:
            if fl(sample["spot"], "spot value") <= 0:
                raise MechanicsError("positive spot")
        elif sample["spot"] is not None:
            raise MechanicsError("invalid spot must be null")
    _ordered_unique([(s["ticker"], s["time_local_ns"]) for s in spots], "spots")
    for quote in quotes:
        decision_id = _text(quote["decision_id"], "quote decision")
        moment = _integer(quote["time_local_ns"], 64, "quote clock")
        if decision_id not in decisions:
            raise MechanicsError("quote decision FK")
        for key in ("ask", "bid"):
            if quote[key] is not None:
                fl(quote[key], "raw " + key)
        plan = decisions[decision_id]
        if moment <= plan["horizon_end_local_ns"] and not any(plan[prefix + "_rth_open_local_ns"] <= moment <= plan[prefix + "_rth_close_local_ns"] for prefix in ("d", "d1", "h2")):
            raise MechanicsError("quote outside admitted RTH")
    _ordered_unique([(q["decision_id"], q["time_local_ns"]) for q in quotes], "quotes")
    return grouped

def event(p:dict[str,Any],a:dict[str,Any])->dict[str,Any]:
    r=I("D_REVISIT_V1",plan_id=p["plan_id"],anchor_id=a["anchor_id"])
    return {"calendar_ordinal":p["calendar_ordinal"],"plan_id":p["plan_id"],"ticker":p["ticker"],"trade_date":p["trade_date"],"expiry_date":p["expiry_date"],"anchor_id":a["anchor_id"],"cluster_ordinal":a["cluster_ordinal"],"center":a["center"],"band":a["band"],"source_mask":a["source_mask"],"anchor_available_at":a["anchor_available_at_local_ns"],"revisit_id":r,"event_status":"NOT_ARMED","armed_side":None,"visit_time":None,"departure_time":None,"departure_side":None,"revisit_time":None,"confirmation_time":None,"confirmation_time_local_ns":None,"event_id":None,"event_session_date":None,"decision_id":None,"side":None,"stop_spot":None,"target_anchor_id":None,"target_spot":None,"entry_quote_time":None,"entry_quote_time_local_ns":None,"event_entry_ask":None,"intent_id":None,"terminal_reason":"NO_VISIT","overlap_rank_json":"","transition_trace_json":"[]","spot_coverage_status":"COMPLETE","option_coverage_status":"NOT_REQUIRED","label_available_at":p["horizon_end_local_ns"],"b_plan_pin":p["b_plan_pin"],"c_anchor_pin":p["c_anchor_pin"],"_t":[]}
def target(p:dict[str,Any],a:dict[str,Any],aa:list[dict[str,Any]],side:str,s:float):
    z=[x for x in aa if x["anchor_id"]!=a["anchor_id"] and ((side=="ABOVE" and x["center"]>s) or(side=="BELOW" and x["center"]<s))]
    return None if not z else min(z,key=lambda x:(x["center"] if side=="ABOVE" else -x["center"],x["cluster_ordinal"],x["anchor_id"]))
def scan(p: dict[str, Any], a: dict[str, Any], aa: list[dict[str, Any]], ss: list[dict[str, Any]]) -> dict[str, Any]:
    """Scan only the plan-local causal minute grid for one confluent anchor."""
    e = event(p, a)
    samples = {item["time_local_ns"]: item for item in ss}
    state = "INIT"
    side: str | None = None
    first_confirmation: int | None = None
    prior: float | None = None
    pending_cross = False
    previous_session: str | None = None

    def reset_attempt() -> None:
        for key in ("visit_time", "departure_time", "departure_side", "revisit_time", "confirmation_time", "confirmation_time_local_ns", "event_id", "event_session_date", "decision_id", "side", "stop_spot", "target_anchor_id", "target_spot", "entry_quote_time", "entry_quote_time_local_ns", "event_entry_ask", "intent_id"):
            e[key] = None

    for moment in p["expected_rth_minutes"]:
        if moment < p["d_1030_local_ns"] or moment > p["horizon_end_local_ns"]:
            continue
        session = (EPOCH + timedelta(seconds=moment // 1_000_000_000)).date().isoformat()
        if previous_session is not None and session != previous_session and state.startswith("CONFIRM_ONE"):
            after = "REVISITED_" + str(side)
            trace(e, "SESSION_BREAK", moment, None, side, state, after, "SESSION_BOUNDARY")
            state, first_confirmation = after, None
        previous_session = session
        sample = samples.get(moment)
        if sample is None or sample["ticker"] != p["ticker"] or not sample["valid_rth"]:
            if state.startswith("CONFIRM_ONE"):
                trace(e, "MISSING_MINUTE", moment, None, side, state, "REVISITED_" + str(side), "MISSING_RTH_MINUTE")
                state = "REVISITED_" + str(side)
                first_confirmation = None
            continue
        spot = sample["spot"]
        outer = "ABOVE" if spot > a["center"] + 2.0 * a["band"] else "BELOW" if spot < a["center"] - 2.0 * a["band"] else None
        inner = abs(spot - a["center"]) <= a["band"]
        if (state.startswith("ARMED") or state.startswith("DEPARTED")) and prior is not None and ((prior > a["center"] + 2.0 * a["band"] and outer == "BELOW") or (prior < a["center"] - 2.0 * a["band"] and outer == "ABOVE")):
            trace(e, "GAP_CROSSING", moment, spot, None, state, state, "NO_INTERIOR_SAMPLE")
            prior = spot
            continue
        if state == "INIT" and outer is not None:
            if pending_cross:
                reset_attempt()
                pending_cross = False
            side = outer
            state = "ARMED_" + side
            e.update(event_status="ARMED", armed_side=side)
            trace(e, "ARMED_" + side, moment, spot, side, "INIT", state, "FIRST_ELIGIBLE_SAMPLE")
        elif state.startswith("ARMED") and inner:
            state = "VISITED_" + str(side)
            e.update(event_status="VISIT", visit_time=moment)
            trace(e, "VISIT", moment, spot, side, "ARMED_" + str(side), state, "INNER_BAND")
        elif state.startswith("VISITED") and outer is not None:
            if outer == side:
                state = "DEPARTED_" + str(side)
                e.update(event_status="DEPARTURE", departure_time=moment, departure_side=side)
                trace(e, "DEPARTURE", moment, spot, side, "VISITED_" + str(side), state, "OUTER_SAME_SIDE")
            else:
                trace(e, "CROSS_THROUGH", moment, spot, side, state, "INIT", "OUTER_OPPOSITE_SIDE")
                state, first_confirmation, pending_cross = "INIT", None, True
                e["event_status"] = "CROSS_THROUGH"
        elif state.startswith("DEPARTED") and inner:
            state = "REVISITED_" + str(side)
            e.update(event_status="REVISIT", revisit_time=moment)
            trace(e, "REVISIT", moment, spot, side, "DEPARTED_" + str(side), state, "INNER_BAND")
        elif state.startswith("REVISITED") or state.startswith("CONFIRM_ONE"):
            if outer is None:
                if state.startswith("CONFIRM_ONE"):
                    trace(e, "CONFIRMATION_RESET", moment, spot, side, state, "REVISITED_" + str(side), "NON_CONFIRMING_OBSERVATION")
                    state, first_confirmation = "REVISITED_" + str(side), None
            elif outer != side:
                trace(e, "CROSS_THROUGH", moment, spot, side, state, "INIT", "OUTER_OPPOSITE_SIDE")
                state, first_confirmation, pending_cross = "INIT", None, True
                e["event_status"] = "CROSS_THROUGH"
            elif state.startswith("CONFIRM_ONE") and first_confirmation is not None and moment != first_confirmation + N:
                trace(e, "SESSION_BREAK", moment, spot, side, state, "REVISITED_" + str(side), "SESSION_BOUNDARY")
                state, first_confirmation = "REVISITED_" + str(side), None
            if state.startswith("REVISITED") and outer == side:
                state, first_confirmation = "CONFIRM_ONE_" + str(side), moment
                trace(e, "CONFIRMATION_MINUTE_1", moment, spot, side, "REVISITED_" + str(side), state, "OUTER_SAME_SIDE")
            elif state.startswith("CONFIRM_ONE") and outer == side:
                state = "CONFIRMED"
                trace(e, "CONFIRMED", moment, spot, side, "CONFIRM_ONE_" + str(side), state, "OUTER_SAME_SIDE")
                e.update(event_status="CONFIRMED", confirmation_time=moment, confirmation_time_local_ns=moment, event_session_date=sample["trade_date"], departure_side=side, side="CALL" if side == "ABOVE" else "PUT", decision_id=p["call_decision_id"] if side == "ABOVE" else p["put_decision_id"], stop_spot=a["center"] - 2.0 * a["band"] if side == "ABOVE" else a["center"] + 2.0 * a["band"])
                e["event_id"] = I("D_EVENT_V1", revisit_id=e["revisit_id"], confirmation_time_local_ns=moment, departure_side=side)
                chosen = target(p, a, aa, side, spot)
                if chosen is not None:
                    e.update(target_anchor_id=chosen["anchor_id"], target_spot=chosen["center"])
                break
        prior = spot
    if e["event_id"] is None:
        if pending_cross:
            e.update(event_status="CROSS_THROUGH", terminal_reason="CROSS_THROUGH")
        elif state == "INIT":
            e.update(event_status="NOT_ARMED", terminal_reason="NO_VISIT")
        elif state.startswith("ARMED"):
            e["terminal_reason"] = "NO_VISIT"
        elif state.startswith("VISITED"):
            e["terminal_reason"] = "NO_DEPARTURE"
        elif state.startswith("DEPARTED"):
            e["terminal_reason"] = "NO_REVISIT"
        else:
            e["terminal_reason"] = "NO_CONFIRMATION"
    e["transition_trace_json"] = C(e.pop("_t"))
    return e


def _terminal_trace(e: dict[str, Any], kind: str, moment: int, reason: str, spot: float | None = None) -> None:
    rows = json.loads(e["transition_trace_json"])
    rows.append({"seq": len(rows), "kind": kind, "time_local_ns": moment,
                 "spot_f64": None if spot is None else spot.hex(), "side": e["departure_side"],
                 "state_before": "CONFIRMED", "state_after": "TERMINAL", "reason": reason})
    e["transition_trace_json"] = C(rows)


def _first_trigger(e: dict[str, Any], samples: list[dict[str, Any]], plan: dict[str, Any]) -> tuple[int, str] | None:
    horizon = plan["horizon_end_local_ns"]
    allowed = set(plan["expected_rth_minutes"])
    for sample in samples:
        moment = sample["time_local_ns"]
        if sample["ticker"] != e["ticker"] or moment not in allowed:
            continue
        if not (e["confirmation_time"] < moment < horizon) or not sample["valid_rth"]:
            continue
        value = sample["spot"]
        stop = value <= e["stop_spot"] if e["side"] == "CALL" else value >= e["stop_spot"]
        target_hit = value >= e["target_spot"] if e["side"] == "CALL" else value <= e["target_spot"]
        if stop or target_hit:
            return moment, "STOP" if stop else "TARGET"
    return None


def _resolve_intents(events: list[dict[str, Any]], plans: dict[str, dict[str, Any]], spots: dict[str, list[dict[str, Any]]], quotes: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for e in events:
        if e["event_id"] is None:
            e["overlap_rank_json"] = C({"eligible_event_session_date": None, "confirmation_time_local_ns": None, "cluster_ordinal": e["cluster_ordinal"], "anchor_id": e["anchor_id"], "rank": None, "winner_revisit_id": None, "winner_event_id": None, "decision": "NOT_COMPETING"})
        else:
            groups.setdefault((e["ticker"], e["event_session_date"]), []).append(e)
    intents: list[dict[str, Any]] = []
    for candidates in groups.values():
        candidates.sort(key=lambda e: (e["confirmation_time_local_ns"], e["cluster_ordinal"], e["anchor_id"]))
        keys = [(e["confirmation_time_local_ns"], e["cluster_ordinal"], e["anchor_id"]) for e in candidates]
        if len(keys) != len(set(keys)):
            raise MechanicsError("candidate tie")
        winner = candidates[0]
        for rank, e in enumerate(candidates, 1):
            e["overlap_rank_json"] = C({"eligible_event_session_date": e["event_session_date"], "confirmation_time_local_ns": e["confirmation_time_local_ns"], "cluster_ordinal": e["cluster_ordinal"], "anchor_id": e["anchor_id"], "rank": rank, "winner_revisit_id": winner["revisit_id"], "winner_event_id": winner["event_id"], "decision": "WINNER" if e is winner else "SUPERSEDED"})
            if e is not winner:
                e.update(event_status="SUPERSEDED_FIRST_EVENT", terminal_reason="SUPERSEDED_FIRST_EVENT", label_available_at=max(e["confirmation_time"], winner["confirmation_time"]))
                _terminal_trace(e, "SUPERSEDED_FIRST_EVENT", e["confirmation_time"], "DAY_PRIORITY")
                continue
            horizon = plans[e["plan_id"]]["horizon_end_local_ns"]
            if not ("2026-01-02" <= e["event_session_date"] <= "2026-09-17"):
                e.update(terminal_reason="OUTSIDE_EVALUATION_WINDOW", label_available_at=e["confirmation_time"])
                continue
            if e["confirmation_time"] >= horizon:
                e.update(event_status="TOO_LATE", terminal_reason="TOO_LATE", option_coverage_status="TOO_LATE", label_available_at=e["confirmation_time"])
                _terminal_trace(e, "TOO_LATE", e["confirmation_time"], "TERMINAL_CLOCK")
                continue
            if e["target_anchor_id"] is None:
                e.update(event_status="NO_TARGET", terminal_reason="NO_TARGET", label_available_at=e["confirmation_time"])
                _terminal_trace(e, "NO_TARGET", e["confirmation_time"], "TARGET_ABSENT")
                continue
            trigger = _first_trigger(e, spots[e["ticker"]], plans[e["plan_id"]])
            valid = [q for q in quotes.get(e["decision_id"], []) if goodq(q)]
            first_ask = next((q for q in valid if e["confirmation_time"] < q["time_local_ns"] < horizon), None)
            if trigger is not None and (first_ask is None or trigger[0] <= first_ask["time_local_ns"]):
                e.update(event_status="PRE_FILL_TRIGGER_CANCELLED", terminal_reason="PRE_FILL_TRIGGER_CANCELLED", option_coverage_status="PRE_FILL_TRIGGER_CANCELLED", label_available_at=trigger[0])
                observed_spot = next(sample["spot"] for sample in spots[e["ticker"]] if sample["time_local_ns"] == trigger[0])
                _terminal_trace(e, "PRE_FILL_TRIGGER_CANCELLED", trigger[0], "TRIGGER_PRE_FILL", observed_spot)
                continue
            if first_ask is None:
                at_h = next((q for q in valid if q["time_local_ns"] == horizon), None)
                if at_h is not None:
                    e.update(event_status="TOO_LATE", terminal_reason="TOO_LATE", option_coverage_status="TOO_LATE", label_available_at=horizon)
                    _terminal_trace(e, "TOO_LATE", horizon, "TERMINAL_CLOCK")
                else:
                    e.update(event_status="NO_ENTRY_QUOTE", terminal_reason="NO_ENTRY_QUOTE", option_coverage_status="ENTRY_QUOTE_MISSING", label_available_at=horizon)
                    _terminal_trace(e, "NO_ENTRY_QUOTE", horizon, "ASK_ABSENT")
                continue
            e.update(entry_quote_time=first_ask["time_local_ns"], entry_quote_time_local_ns=first_ask["time_local_ns"], event_entry_ask=first_ask["ask"], option_coverage_status="ENTRY_QUOTE_VALID")
            e["intent_id"] = I("D_INTENT_V1", event_id=e["event_id"], decision_id=e["decision_id"], entry_quote_time_local_ns=first_ask["time_local_ns"])
            intents.append(e)
    return intents

def _spot_coverage(plan, row, samples) -> str:
    cutoff = min(row["label_available_at"], plan["horizon_end_local_ns"])
    start = max(plan["d_1030_local_ns"], row["anchor_available_at"])
    prefix = [moment for moment in plan["expected_rth_minutes"] if start <= moment <= cutoff]
    if not prefix:
        return "NOT_EVALUABLE"
    valid = {sample["time_local_ns"] for sample in samples if sample["ticker"] == plan["ticker"] and sample["valid_rth"]}
    by_session = {}
    for moment in prefix:
        session = (EPOCH + timedelta(seconds=moment // 1_000_000_000)).date().isoformat()
        by_session.setdefault(session, []).append(moment)
    if any(not any(moment in valid for moment in minutes) for minutes in by_session.values()):
        return "MISSING_SESSION"
    return "COMPLETE" if all(moment in valid for moment in prefix) else "MISSING_MINUTE"


def _make_plan_coverage(plans, anchors_by_plan, events):
    result = []
    economic_status = {
        "NO_TARGET": "NO_INTENT_NO_TARGET",
        "SUPERSEDED_FIRST_EVENT": "NO_INTENT_SUPERSEDED",
        "OUTSIDE_EVALUATION_WINDOW": "NO_INTENT_OUTSIDE_EVALUATION_WINDOW",
        "PRE_FILL_TRIGGER_CANCELLED": "NO_INTENT_PRE_FILL_TRIGGER_CANCELLED",
        "NO_ENTRY_QUOTE": "NO_INTENT_ENTRY_QUOTE_MISSING",
        "TOO_LATE": "NO_INTENT_TOO_LATE",
        "WAIT": "INTENT_WAIT",
        "NO_FILL": "INTENT_NO_FILL",
        "FILLED": "INTENT_FILLED",
    }
    for plan in plans:
        rows = [row for row in events if row["plan_id"] == plan["plan_id"]]
        confirmed = sorted((row for row in rows if row["event_id"] is not None), key=lambda row: (row["event_session_date"], row["confirmation_time_local_ns"], row["cluster_ordinal"], row["anchor_id"]))
        evidence = []
        inside = 0
        for row in confirmed:
            in_window = "2026-01-02" <= row["event_session_date"] <= "2026-09-17"
            inside += int(in_window)
            rank = json.loads(row["overlap_rank_json"])
            if row["terminal_reason"] not in economic_status:
                raise MechanicsError("unresolved confirmed terminal")
            evidence.append({
                "event_session_date": row["event_session_date"],
                "confirmation_time_local_ns": row["confirmation_time_local_ns"],
                "revisit_id": row["revisit_id"], "event_id": row["event_id"],
                "overlap_decision": rank["decision"],
                "winner_event_id": rank["winner_event_id"],
                "window_status": "IN_EVALUATION_WINDOW" if in_window else "OUTSIDE_EVALUATION_WINDOW",
                "terminal_reason": row["terminal_reason"], "intent_id": row["intent_id"],
                "economic_intent_status": economic_status[row["terminal_reason"]],
            })
        first = confirmed[0] if confirmed else None
        levels = anchors_by_plan[plan["plan_id"]]
        result.append({
            "calendar_ordinal": plan["calendar_ordinal"], "plan_id": plan["plan_id"],
            "ticker": plan["ticker"], "trade_date": plan["trade_date"], "expiry_date": plan["expiry_date"],
            "geometry_partition": plan["geometry_partition"], "c_anchor_count": len(levels),
            "eligible_anchor_count": sum(confl(anchor) for anchor in levels),
            "revisit_row_count": len(rows), "confirmed_event_count": len(confirmed),
            "first_physical_event_id": None if first is None else first["event_id"],
            "first_physical_event_time": None if first is None else first["confirmation_time"],
            "outside_evaluation_event_count": len(confirmed) - inside,
            "in_evaluation_event_count": inside,
            "economic_intent_count": sum(row["intent_id"] is not None for row in rows),
            "event_day_evidence_json": C(evidence),
            "terminal_status_counts_json": C({terminal: sum(row["terminal_reason"] == terminal for row in rows) for terminal in TERMINALS}),
            "b_plan_pin": plan["b_plan_pin"], "c_geometry_pin": plan["c_geometry_pin"],
        })
    return result


def _make_counts(plans, anchors, events, ledger, coverage):
    counts = {key: 0 for key in COUNT_KEYS}
    counts.update(plan_rows=len(plans), plan_coverage_rows=len(coverage), revisit_rows=len(events), eligible_revisit_rows=len(events), ineligible_nonconfluence_rows=len(anchors) - len(events), confirmed_rows=sum(row["event_id"] is not None for row in events))
    geometry = {
        "C_MISSING_SOURCE": "plans_c_missing_geometry",
        "C_INVALID_IB": "plans_c_invalid_geometry",
        "C_INVALID_STATE60": "plans_c_invalid_geometry",
        "NO_CONFLUENT_ANCHOR": "plans_no_confluent_anchor",
        "ELIGIBLE_ANCHOR_SET": "plans_with_eligible_anchor",
    }
    for row in coverage:
        counts[geometry[row["geometry_partition"]]] += 1
        inside, outside = row["in_evaluation_event_count"], row["outside_evaluation_event_count"]
        key = "plans_no_confirmed_event" if not inside and not outside else "plans_with_mixed_evaluation_events" if inside and outside else "plans_with_only_in_evaluation_events" if inside else "plans_with_only_outside_evaluation_events"
        counts[key] += 1
    for terminal, key in (
        ("NO_VISIT", "no_visit_rows"), ("NO_DEPARTURE", "no_departure_rows"),
        ("CROSS_THROUGH", "cross_through_rows"), ("NO_REVISIT", "no_revisit_rows"),
        ("NO_CONFIRMATION", "no_confirmation_rows"), ("NO_TARGET", "no_target_rows"),
        ("SUPERSEDED_FIRST_EVENT", "superseded_first_event_rows"),
        ("PRE_FILL_TRIGGER_CANCELLED", "pre_fill_trigger_cancelled_rows"),
        ("NO_ENTRY_QUOTE", "no_entry_quote_rows"), ("TOO_LATE", "too_late_rows"),
        ("NOT_EVALUABLE", "not_evaluable_rows"),
    ):
        counts[key] = sum(row["terminal_reason"] == terminal for row in events)
    by_intent = {}
    for row in ledger:
        by_intent.setdefault(row["intent_id"], []).append(row)
        _integer(row["unit_risk_cents"], 64, "output unit risk", True)
        _integer(row["qty"], 32, "output quantity", True)
        if len(row) != 47:
            raise MechanicsError("ledger projection")
        counts[row["arm"].lower() + "_" + row["cost"].lower() + "_ledger_rows"] += 1
        counts["no_fill_rows"] += int(row["fill_status"] == "NO_FILL")
        counts["filled_rows"] += int(row["fill_status"] == "FILLED")
        counts["missing_exit_rows"] += int(row["missing_exit_flag"])
        counts["ambiguous_rows"] += int(row["ambiguous_flag"])
    for rows in by_intent.values():
        if len(rows) != 4 or {(row["arm"], row["cost"]) for row in rows} != {("A", "BASE"), ("A", "ADVERSE"), ("B", "BASE"), ("B", "ADVERSE")}:
            raise MechanicsError("four coordinated rows")
        common = {(row["entry_quote_time"], row["entry_ask"].hex(), row["unit_risk_cents"], row["qty"], row["admission_status"], row["fill_status"], row["wait_reason"]) for row in rows}
        if len(common) != 1:
            raise MechanicsError("common intent admission")
        row = rows[0]
        counts["common_intent_rows"] += 1
        if row["admission_status"] == "ADMITTED":
            counts["admitted_intent_rows"] += 1
        elif row["admission_status"] == "EVENT_RISK_BUDGET":
            counts["event_risk_budget_rows"] += 1
        elif row["admission_status"] == "WAIT":
            counts["wait_rows"] += 1
            counts[{"CAPITAL_BLOCKED": "capital_blocked_rows", "OPEN_POSITION": "open_position_rows"}[row["wait_reason"]]] += 1
        else:
            raise MechanicsError("admission status")
    if counts["common_intent_rows"] != counts["admitted_intent_rows"] + counts["wait_rows"] + counts["event_risk_budget_rows"] or counts["filled_rows"] != 4 * counts["admitted_intent_rows"] or counts["no_fill_rows"] != 4 * counts["event_risk_budget_rows"]:
        raise MechanicsError("intent/ledger equations")
    if set(by_intent) != {row["intent_id"] for row in events if row["intent_id"] is not None}:
        raise MechanicsError("event/ledger intent identity")
    for row in coverage:
        if len(row) != 19 or sum(json.loads(row["terminal_status_counts_json"]).values()) != row["revisit_row_count"] or row["in_evaluation_event_count"] + row["outside_evaluation_event_count"] != row["confirmed_event_count"] or row["economic_intent_count"] > 3:
            raise MechanicsError("plan coverage equations")
    if any(len(row) != 39 or row["terminal_reason"] not in TERMINALS for row in events):
        raise MechanicsError("event projection")
    for key, value in counts.items():
        _integer(value, 64, "count " + key, True)
    return counts


def evaluate_revisit_mechanics(plans, anchors, spots, quotes, *, config):
    """Pure synthetic composition of observed events and causal shared accounting."""
    anchors_by_plan = _validate(plans, anchors, spots, quotes, config)
    plan_map = {plan["plan_id"]: plan for plan in plans}
    spots_by_ticker = {ticker: [] for ticker in TICKERS}
    quotes_by_decision = {}
    for sample in spots:
        spots_by_ticker[sample["ticker"]].append(sample)
    for quote in quotes:
        quotes_by_decision.setdefault(quote["decision_id"], []).append(quote)
    events = [scan(plan, anchor, anchors_by_plan[plan["plan_id"]], spots_by_ticker[plan["ticker"]]) for plan in plans for anchor in anchors_by_plan[plan["plan_id"]] if confl(anchor)]
    intents = _resolve_intents(events, plan_map, spots_by_ticker, quotes_by_decision)
    accounting = replay_portfolio(intents, plans, spots, quotes)
    for row in intents:
        row.update(accounting["event_updates"][row["intent_id"]])
    for row in events:
        row["spot_coverage_status"] = _spot_coverage(plan_map[row["plan_id"]], row, spots_by_ticker[row["ticker"]])
    events.sort(key=lambda row: (row["calendar_ordinal"], row["plan_id"], row["anchor_id"]))
    ledger = sorted(accounting["ledger"], key=lambda row: (row["event_session_date"], row["ticker"], row["arm"], row["cost"], row["ledger_id"]))
    coverage = _make_plan_coverage(plans, anchors_by_plan, events)
    counts = _make_counts(plans, anchors, events, ledger, coverage)
    return {"status": "SYNTHETIC_MECHANICS_ONLY", "events": events, "ledger": ledger, "plan_coverage": coverage, "counts": counts}
