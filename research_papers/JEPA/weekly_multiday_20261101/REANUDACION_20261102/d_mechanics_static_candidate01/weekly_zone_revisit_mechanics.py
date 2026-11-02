"""Pure in-memory synthetic mechanics for the frozen D A/B replay recipe."""
from __future__ import annotations

from decimal import Decimal, Inexact, ROUND_CEILING, localcontext
import hashlib
import json
import math
from typing import Any, Mapping, Sequence


EVENT_TERMINALS = {"NO_VISIT", "NO_DEPARTURE", "CROSS_THROUGH", "NO_REVISIT", "NO_CONFIRMATION", "NO_TARGET", "SUPERSEDED_FIRST_EVENT", "PRE_FILL_TRIGGER_CANCELLED", "NO_ENTRY_QUOTE", "TOO_LATE", "OUTSIDE_EVALUATION_WINDOW", "WAIT", "NO_FILL", "FILLED", "NOT_EVALUABLE"}
TICKERS = ("SPY", "QQQ", "SPXW")
POLICY_START_DATE = "2026-01-02"
POLICY_END_DATE = "2026-09-17"
INITIAL_CASH = Decimal("100000")
FIXED_RISK_CONTRACT_PIN = "9c387e9bea74ba65777808b5ac5e5fccfdc2437645e7b301c15eab2d33bbeb7b"
PLAN_KEYS = {
    "calendar_ordinal", "plan_id", "ticker", "trade_date", "expiry_date",
    "call_decision_id", "put_decision_id", "horizon_end_local_ns", "d_1030_local_ns", "d_session_date",
    "d1_session_date", "h2_session_date", "d_rth_open_local_ns",
    "d_rth_close_local_ns", "d1_rth_open_local_ns", "d1_rth_close_local_ns",
    "h2_rth_open_local_ns", "h2_rth_close_local_ns", "expected_rth_minutes",
    "b_plan_pin", "b_value_pin", "c_anchor_pin", "c_geometry_pin",
    "fixed_risk_contract_pin", "geometry_status", "geometry_partition",
}
ANCHOR_KEYS = {
    "plan_id", "anchor_id", "cluster_ordinal", "center", "band", "source_mask",
    "anchor_available_at_local_ns", "valid_geometry", "components", "c_anchor_pin",
    "c_geometry_pin",
}
SPOT_KEYS = {"ticker", "time_local_ns", "trade_date", "spot", "valid_rth"}
QUOTE_KEYS = {"decision_id", "time_local_ns", "ask", "bid"}


class MechanicsError(ValueError):
    pass


def _canon(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _id(schema: str, **payload: Any) -> str:
    return hashlib.sha256(_canon({"schema": schema, **payload}).encode("utf-8")).hexdigest()


def _finite(value: Any, label: str) -> float:
    if type(value) is not float or not math.isfinite(value):
        raise MechanicsError(label + " must be finite float")
    return value


def _valid_quote(quote: Mapping[str, Any]) -> bool:
    """Retain raw invalid observations, but never price an entry/exit from one."""
    ask, bid = quote["ask"], quote["bid"]
    return (
        type(ask) is float and type(bid) is float and math.isfinite(ask)
        and math.isfinite(bid) and ask > 0 and 0 <= bid <= ask
    )


def _ns(value: Any, label: str) -> int:
    if type(value) is not int:
        raise MechanicsError(label + " must be signed int")
    return value


def _date(value: Any, label: str) -> str:
    if type(value) is not str or len(value) != 10 or value[4] != "-" or value[7] != "-":
        raise MechanicsError(label + " must be ISO date")
    return value


def _decimal(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


def _trace(rows: list[dict[str, Any]]) -> str:
    return _canon(rows)


def _event_template(plan: Mapping[str, Any], anchor: Mapping[str, Any], revisit_id: str) -> dict[str, Any]:
    return {"calendar_ordinal": plan["calendar_ordinal"], "plan_id": plan["plan_id"], "ticker": plan["ticker"], "trade_date": plan["trade_date"], "expiry_date": plan["expiry_date"], "anchor_id": anchor["anchor_id"], "cluster_ordinal": anchor["cluster_ordinal"], "center": anchor["center"], "band": anchor["band"], "source_mask": anchor["source_mask"], "anchor_available_at": anchor["anchor_available_at_local_ns"], "revisit_id": revisit_id, "event_status": "NOT_ARMED", "armed_side": None, "visit_time": None, "departure_time": None, "departure_side": None, "revisit_time": None, "confirmation_time": None, "confirmation_time_local_ns": None, "event_id": None, "event_session_date": None, "decision_id": None, "side": None, "stop_spot": None, "target_anchor_id": None, "target_spot": None, "entry_quote_time": None, "entry_quote_time_local_ns": None, "event_entry_ask": None, "intent_id": None, "terminal_reason": "NO_VISIT", "overlap_rank_json": "", "transition_trace_json": "[]", "spot_coverage_status": "COMPLETE", "option_coverage_status": "NOT_REQUIRED", "label_available_at": plan["horizon_end_local_ns"], "b_plan_pin": plan["b_plan_pin"], "b_value_pin": plan["b_value_pin"], "c_anchor_pin": plan["c_anchor_pin"], "c_geometry_pin": plan["c_geometry_pin"], "fixed_risk_contract_pin": plan["fixed_risk_contract_pin"]}


def _partition(plan: Mapping[str, Any], anchors: Sequence[Mapping[str, Any]]) -> str:
    """Derive the public C partition; caller text is checked, never trusted."""
    status = plan["geometry_status"]
    if status == "MISSING_SOURCE":
        return "C_MISSING_SOURCE"
    if status == "INVALID_IB":
        return "C_INVALID_IB"
    if status == "INVALID_STATE60":
        return "C_INVALID_STATE60"
    if status != "AVAILABLE":
        raise MechanicsError("geometry status")
    eligible = [a for a in anchors if isinstance(a, Mapping) and a.get("plan_id") == plan["plan_id"] and a.get("valid_geometry") is True and isinstance(a.get("components"), Sequence) and not isinstance(a.get("components"), (str, bytes)) and all(isinstance(c, Mapping) for c in a["components"]) and {c.get("kind") for c in a["components"]} >= {"FIB", "WALL"}]
    return "ELIGIBLE_ANCHOR_SET" if eligible else "NO_CONFLUENT_ANCHOR"


def _validate(plans: Sequence[Mapping[str, Any]], anchors: Sequence[Mapping[str, Any]], spots: Sequence[Mapping[str, Any]], quotes: Sequence[Mapping[str, Any]], config: Mapping[str, Any]) -> None:
    if set(config) != {"evaluation_start_date", "evaluation_end_date"}:
        raise MechanicsError("config schema")
    if config["evaluation_start_date"] != POLICY_START_DATE or config["evaluation_end_date"] != POLICY_END_DATE:
        raise MechanicsError("fixed evaluation calendar")
    if not plans or any(not isinstance(plan, Mapping) or set(plan) != PLAN_KEYS for plan in plans):
        raise MechanicsError("plan schema")
    if [(p["calendar_ordinal"], p["plan_id"]) for p in plans] != sorted((p["calendar_ordinal"], p["plan_id"]) for p in plans):
        raise MechanicsError("plan order")
    if len({p["plan_id"] for p in plans}) != len(plans):
        raise MechanicsError("plan identity")
    for plan in plans:
        if type(plan["calendar_ordinal"]) is not int or plan["ticker"] not in TICKERS:
            raise MechanicsError("plan scalar")
        for key in ("trade_date", "expiry_date", "d_session_date", "d1_session_date", "h2_session_date"):
            _date(plan[key], key)
        if not (POLICY_START_DATE <= plan["trade_date"] <= POLICY_END_DATE):
            raise MechanicsError("plan outside fixed calendar")
        if not (plan["d_session_date"] < plan["d1_session_date"] < plan["h2_session_date"]):
            raise MechanicsError("three distinct session dates")
        for key in ("horizon_end_local_ns", "d_1030_local_ns", "d_rth_open_local_ns", "d_rth_close_local_ns", "d1_rth_open_local_ns", "d1_rth_close_local_ns", "h2_rth_open_local_ns", "h2_rth_close_local_ns"):
            _ns(plan[key], key)
        if not (plan["d_rth_open_local_ns"] < plan["d_rth_close_local_ns"] < plan["d1_rth_open_local_ns"] < plan["d1_rth_close_local_ns"] < plan["h2_rth_open_local_ns"] < plan["h2_rth_close_local_ns"]):
            raise MechanicsError("session bounds chronology")
        if not (plan["d_1030_local_ns"] == plan["d_rth_open_local_ns"] + 60 * 60 * 1_000_000_000 and plan["d_rth_open_local_ns"] <= plan["d_1030_local_ns"] < plan["horizon_end_local_ns"] == plan["h2_rth_close_local_ns"]):
            raise MechanicsError("plan time envelope")
        minutes = plan["expected_rth_minutes"]
        if not isinstance(minutes, Sequence) or isinstance(minutes, (str, bytes)) or not minutes or any(type(x) is not int for x in minutes) or list(minutes) != sorted(minutes) or len(set(minutes)) != len(minutes):
            raise MechanicsError("expected minute grid")
        bounds = ((plan["d_rth_open_local_ns"], plan["d_rth_close_local_ns"]), (plan["d1_rth_open_local_ns"], plan["d1_rth_close_local_ns"]), (plan["h2_rth_open_local_ns"], plan["h2_rth_close_local_ns"]))
        if any(not any(start <= minute <= end for start, end in bounds) or minute > plan["horizon_end_local_ns"] for minute in minutes):
            raise MechanicsError("expected minute grid bounds")
        if any(type(plan[key]) is not str or not plan[key] for key in ("plan_id", "call_decision_id", "put_decision_id", "b_plan_pin", "b_value_pin", "c_anchor_pin", "c_geometry_pin", "fixed_risk_contract_pin", "geometry_status")):
            raise MechanicsError("plan provenance")
        if any(len(plan[key]) != 64 or any(char not in "0123456789abcdef" for char in plan[key]) for key in ("b_plan_pin", "b_value_pin", "c_anchor_pin", "c_geometry_pin")) or plan["fixed_risk_contract_pin"] != FIXED_RISK_CONTRACT_PIN:
            raise MechanicsError("provenance pin")
        expected_partition = _partition(plan, anchors)
        if plan["geometry_partition"] != expected_partition:
            raise MechanicsError("geometry partition")
    if any(not isinstance(a, Mapping) or set(a) != ANCHOR_KEYS for a in anchors):
        raise MechanicsError("anchor schema")
    if [(a["plan_id"], a["cluster_ordinal"], a["anchor_id"]) for a in anchors] != sorted((a["plan_id"], a["cluster_ordinal"], a["anchor_id"]) for a in anchors):
        raise MechanicsError("anchor order")
    plan_by_id = {p["plan_id"]: p for p in plans}
    for anchor in anchors:
        plan = plan_by_id.get(anchor["plan_id"])
        if plan is None or anchor["c_anchor_pin"] != plan["c_anchor_pin"] or anchor["c_geometry_pin"] != plan["c_geometry_pin"]:
            raise MechanicsError("anchor provenance")
        if type(anchor["cluster_ordinal"]) is not int or type(anchor["valid_geometry"]) is not bool:
            raise MechanicsError("anchor scalar")
        _finite(anchor["center"], "center"); _finite(anchor["band"], "band"); _ns(anchor["anchor_available_at_local_ns"], "anchor availability")
    if any(not isinstance(s, Mapping) or set(s) - (SPOT_KEYS | {"session_break"}) or not SPOT_KEYS.issubset(s) for s in spots):
        raise MechanicsError("spot schema")
    if [(s["ticker"], s["time_local_ns"]) for s in spots] != sorted((s["ticker"], s["time_local_ns"]) for s in spots) or len({(s["ticker"], s["time_local_ns"]) for s in spots}) != len(spots):
        raise MechanicsError("spot order")
    for sample in spots:
        if sample["ticker"] not in TICKERS or type(sample["valid_rth"]) is not bool or ("session_break" in sample and type(sample["session_break"]) is not bool):
            raise MechanicsError("spot scalar")
        _ns(sample["time_local_ns"], "spot time"); _date(sample["trade_date"], "spot date"); _finite(sample["spot"], "spot")
    if any(not isinstance(q, Mapping) or set(q) != QUOTE_KEYS for q in quotes):
        raise MechanicsError("quote schema")
    if [(q["decision_id"], q["time_local_ns"]) for q in quotes] != sorted((q["decision_id"], q["time_local_ns"]) for q in quotes) or len({(q["decision_id"], q["time_local_ns"]) for q in quotes}) != len(quotes):
        raise MechanicsError("quote order")
    for quote in quotes:
        _ns(quote["time_local_ns"], "quote time")
        if quote["ask"] is not None:
            _finite(quote["ask"], "raw ask")
        if quote["bid"] is not None:
            _finite(quote["bid"], "raw bid")


def _target(anchor: Mapping[str, Any], all_anchors: Sequence[Mapping[str, Any]], side: str, confirmation_spot: float) -> tuple[str, float] | None:
    candidates = [a for a in all_anchors if a["plan_id"] == anchor["plan_id"] and a["anchor_id"] != anchor["anchor_id"] and a.get("valid_geometry") is True and ((side == "ABOVE" and a["center"] > confirmation_spot) or (side == "BELOW" and a["center"] < confirmation_spot))]
    if not candidates: return None
    chosen = min(candidates, key=lambda a: (abs(a["center"] - confirmation_spot), a["cluster_ordinal"], a["anchor_id"]))
    return chosen["anchor_id"], chosen["center"]


def _scan(plan: Mapping[str, Any], anchor: Mapping[str, Any], all_anchors: Sequence[Mapping[str, Any]], samples: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    rid = _id("D_REVISIT_V1", plan_id=plan["plan_id"], anchor_id=anchor["anchor_id"]); event = _event_template(plan, anchor, rid)
    if anchor.get("valid_geometry") is not True or not {"FIB", "WALL"}.issubset({c.get("kind") for c in anchor.get("components", ())}):
        event["terminal_reason"] = "NOT_EVALUABLE"; return event
    z, b = _finite(anchor["center"], "center"), _finite(anchor["band"], "band")
    if b <= 0: raise MechanicsError("positive band")
    state, side, streak, trace, seq, prior, confirmation_minute = "INIT", None, 0, [], 0, None, None
    expected_minutes = list(plan["expected_rth_minutes"])
    expected_index = {minute: index for index, minute in enumerate(expected_minutes)}
    def add(kind: str, sample: Mapping[str, Any], before: str, after: str, reason: str, current_side: str | None) -> None:
        nonlocal seq
        trace.append({"seq": seq, "kind": kind, "time_local_ns": sample["time_local_ns"], "spot_f64": float(sample["spot"]).hex(), "side": current_side, "state_before": before, "state_after": after, "reason": reason}); seq += 1
    for sample in samples:
        t, spot = _ns(sample["time_local_ns"], "spot time"), _finite(sample["spot"], "spot")
        if sample.get("ticker") != plan["ticker"] or t < anchor["anchor_available_at_local_ns"] or t > plan["horizon_end_local_ns"]:
            continue
        if t == plan["horizon_end_local_ns"]:
            outer = "ABOVE" if spot > z + 2*b else "BELOW" if spot < z - 2*b else None
            if sample.get("valid_rth") is True and sample.get("session_break") is not True and (state.startswith("REVISITED") or state.startswith("CONFIRM_ONE")) and outer == side:
                event.update(event_status="TOO_LATE", confirmation_time=t, confirmation_time_local_ns=t, event_session_date=sample["trade_date"], departure_side=side, side="CALL" if side == "ABOVE" else "PUT", decision_id=plan["call_decision_id"] if side == "ABOVE" else plan["put_decision_id"], stop_spot=z-2*b if side == "ABOVE" else z+2*b, terminal_reason="TOO_LATE", label_available_at=t)
                event["event_id"] = _id("D_EVENT_V1", revisit_id=rid, confirmation_time_local_ns=t, departure_side=side)
                target = _target(anchor, all_anchors, side, spot)
                if target is not None:
                    event.update(target_anchor_id=target[0], target_spot=target[1])
                add("TOO_LATE", sample, state, "TERMINAL", "H2_EXACT_CONFIRMATION_FORBIDDEN", side)
            break
        if sample.get("valid_rth") is not True or sample.get("session_break") is True:
            if state.startswith("CONFIRM_ONE"): add("MISSING_MINUTE" if sample.get("valid_rth") is not True else "SESSION_BREAK", sample, state, state, "MISSING_RTH_MINUTE" if sample.get("valid_rth") is not True else "SESSION_BOUNDARY", side); streak = 0
            if state.startswith("CONFIRM_ONE"):
                state, confirmation_minute = "REVISITED_" + str(side), None
            continue
        outer = "ABOVE" if spot > z + 2*b else "BELOW" if spot < z - 2*b else None; inside = abs(spot-z) <= b
        if prior is not None and ((prior > z + 2*b and spot < z - 2*b) or (prior < z - 2*b and spot > z + 2*b)):
            add("GAP_CROSSING", sample, state, state, "NO_INTERIOR_SAMPLE", None); prior = spot; continue
        if state == "INIT" and outer:
            side, state = outer, "ARMED_" + outer; event.update(event_status="ARMED", armed_side=outer); add("ARMED_"+outer, sample, "INIT", state, "FIRST_ELIGIBLE_SAMPLE", outer)
        elif state.startswith("ARMED") and inside:
            state = "VISITED_" + side; event["visit_time"] = t; event["event_status"] = "VISIT"; add("VISIT", sample, "ARMED_"+side, state, "INNER_BAND", side)
        elif state.startswith("VISITED") and outer:
            if outer != side:
                add("CROSS_THROUGH", sample, state, "INIT", "OUTER_OPPOSITE_SIDE", side); state, side, streak = "INIT", None, 0; event.update(event_status="CROSS_THROUGH", terminal_reason="CROSS_THROUGH")
            else:
                state = "DEPARTED_"+side; event.update(event_status="DEPARTURE", departure_time=t, departure_side=side); add("DEPARTURE", sample, "VISITED_"+side, state, "OUTER_SAME_SIDE", side)
        elif state.startswith("DEPARTED") and inside:
            state = "REVISITED_"+side; event.update(event_status="REVISIT", revisit_time=t); add("REVISIT", sample, "DEPARTED_"+side, state, "INNER_BAND", side)
        elif (state.startswith("REVISITED") or state.startswith("CONFIRM_ONE")) and outer:
            if outer != side:
                add("CROSS_THROUGH", sample, state, "INIT", "OUTER_OPPOSITE_SIDE", side); state, side, streak = "INIT", None, 0; event.update(event_status="CROSS_THROUGH", terminal_reason="CROSS_THROUGH")
            else:
                if state.startswith("CONFIRM_ONE") and (confirmation_minute not in expected_index or t not in expected_index or expected_index[t] != expected_index[confirmation_minute] + 1):
                    add("MISSING_MINUTE", sample, state, "REVISITED_" + side, "EXPECTED_RTH_MINUTE_ABSENT", side)
                    state, streak, confirmation_minute = "REVISITED_" + side, 0, None
                streak += 1; before = state; state = "CONFIRM_ONE_"+side if streak == 1 else "CONFIRMED"; confirmation_minute = t
                add("CONFIRMATION_MINUTE_1" if streak == 1 else "CONFIRMED", sample, before, state, "OUTER_SAME_SIDE", side)
                if streak == 2:
                    event.update(event_status="CONFIRMED", confirmation_time=t, confirmation_time_local_ns=t, event_session_date=sample["trade_date"], departure_side=side, side="CALL" if side == "ABOVE" else "PUT", decision_id=plan["call_decision_id"] if side == "ABOVE" else plan["put_decision_id"], stop_spot=z-2*b if side == "ABOVE" else z+2*b)
                    event["event_id"] = _id("D_EVENT_V1", revisit_id=rid, confirmation_time_local_ns=t, departure_side=side)
                    target = _target(anchor, all_anchors, side, spot)
                    if target is None: event.update(event_status="NO_TARGET", terminal_reason="NO_TARGET", label_available_at=t); add("NO_TARGET", sample, "CONFIRMED", "TERMINAL", "TARGET_ABSENT", side)
                    else:
                        in_entry_window = plan["entry_start_local_ns"] <= t <= plan["entry_end_local_ns"]
                        event.update(target_anchor_id=target[0], target_spot=target[1], terminal_reason="NO_ENTRY_QUOTE" if in_entry_window else "OUTSIDE_EVALUATION_WINDOW", label_available_at=t)
                    break
        prior = spot
    if event["event_status"] not in {"CONFIRMED", "NO_TARGET", "TOO_LATE"}:
        event["terminal_reason"] = {"INIT":"NO_VISIT", "ARMED_ABOVE":"NO_DEPARTURE", "ARMED_BELOW":"NO_DEPARTURE", "VISITED_ABOVE":"NO_DEPARTURE", "VISITED_BELOW":"NO_DEPARTURE", "DEPARTED_ABOVE":"NO_REVISIT", "DEPARTED_BELOW":"NO_REVISIT", "REVISITED_ABOVE":"NO_CONFIRMATION", "REVISITED_BELOW":"NO_CONFIRMATION", "CONFIRM_ONE_ABOVE":"NO_CONFIRMATION", "CONFIRM_ONE_BELOW":"NO_CONFIRMATION"}.get(state, event["terminal_reason"])
    event["transition_trace_json"] = _trace(trace)
    return event


def _pre_fill_trigger(event: Mapping[str, Any], samples: Sequence[Mapping[str, Any]], horizon: int) -> tuple[int, str] | None:
    """Return the causal stop/target that wins an equal-time ask before fill."""
    for sample in samples:
        t = sample["time_local_ns"]
        if not (event["confirmation_time"] < t < horizon) or sample["valid_rth"] is not True or sample.get("session_break") is True:
            continue
        value = sample["spot"]
        if event["side"] == "CALL":
            if value <= event["stop_spot"]:
                return t, "STOP"
            if value >= event["target_spot"]:
                return t, "TARGET"
        else:
            if value >= event["stop_spot"]:
                return t, "STOP"
            if value <= event["target_spot"]:
                return t, "TARGET"
    return None


def _post_fill_trigger(event: Mapping[str, Any], samples: Sequence[Mapping[str, Any]], horizon: int) -> tuple[int, str] | None:
    """A exits at its first physical stop/target; B deliberately does not."""
    for sample in samples:
        t = sample["time_local_ns"]
        if not (event["entry_quote_time"] < t < horizon) or sample["valid_rth"] is not True or sample.get("session_break") is True:
            continue
        value = sample["spot"]
        if event["side"] == "CALL":
            if value <= event["stop_spot"]:
                return t, "STOP"
            if value >= event["target_spot"]:
                return t, "TARGET"
        else:
            if value >= event["stop_spot"]:
                return t, "STOP"
            if value <= event["target_spot"]:
                return t, "TARGET"
    return None


def evaluate_revisit_mechanics(plans: Sequence[Mapping[str, Any]], anchors: Sequence[Mapping[str, Any]], spots: Sequence[Mapping[str, Any]], quotes: Sequence[Mapping[str, Any]], *, config: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate artificial records; no files, adapters, benchmark, or real closure."""
    _validate(plans, anchors, spots, quotes, config)
    spot_map = {ticker: sorted([s for s in spots if s.get("ticker") == ticker], key=lambda s: s["time_local_ns"]) for ticker in TICKERS}
    events = [_scan(plan, anchor, anchors, spot_map[plan["ticker"]]) for plan in plans for anchor in anchors if anchor.get("plan_id") == plan["plan_id"]]
    candidates = [e for e in events if e["event_id"]]
    candidate_keys = [(e["ticker"], e["event_session_date"], e["confirmation_time_local_ns"], e["cluster_ordinal"], e["anchor_id"]) for e in candidates]
    if len(candidate_keys) != len(set(candidate_keys)):
        raise MechanicsError("ambiguous candidate ordering tie")
    winners: dict[tuple[str, str], dict[str, Any]] = {}
    for event in sorted(candidates, key=lambda e: (e["confirmation_time"], e["cluster_ordinal"], e["anchor_id"])): winners.setdefault((event["ticker"], event["event_session_date"]), event)
    quote_map = {key: sorted([q for q in quotes if q.get("decision_id") == key], key=lambda q: q["time_local_ns"]) for key in {e["decision_id"] for e in candidates}}
    intents: list[dict[str, Any]] = []
    for event in events:
        winner = winners.get((event["ticker"], event["event_session_date"])) if event["event_id"] else None
        rank = {"eligible_event_session_date": event["event_session_date"], "confirmation_time_local_ns": event["confirmation_time_local_ns"], "cluster_ordinal": event["cluster_ordinal"], "anchor_id": event["anchor_id"], "rank": 0 if winner is event else None, "winner_revisit_id": winner["revisit_id"] if winner else None, "winner_event_id": winner["event_id"] if winner else None, "decision": "WINNER" if winner is event else "SUPERSEDED" if event["event_id"] else "NOT_COMPETING"}
        event["overlap_rank_json"] = _canon(rank)
        if event["event_id"] and winner is not event:
            event.update(event_status="SUPERSEDED_FIRST_EVENT", terminal_reason="SUPERSEDED_FIRST_EVENT", label_available_at=max(event["confirmation_time"], winner["confirmation_time"]))
            continue
        if winner is event:
            plan = next(p for p in plans if p["plan_id"] == event["plan_id"])
            if event["confirmation_time"] < max(plan["d_1030_local_ns"], next(a["anchor_available_at_local_ns"] for a in anchors if a["plan_id"] == event["plan_id"] and a["anchor_id"] == event["anchor_id"])):
                event.update(event_status="OUTSIDE_EVALUATION_WINDOW", terminal_reason="OUTSIDE_EVALUATION_WINDOW", label_available_at=event["confirmation_time"])
                continue
            if event["confirmation_time"] == plan["horizon_end_local_ns"]:
                event.update(event_status="TOO_LATE", terminal_reason="TOO_LATE", label_available_at=plan["horizon_end_local_ns"])
                continue
            if event["target_anchor_id"] is None:
                event.update(event_status="NO_TARGET", terminal_reason="NO_TARGET", label_available_at=event["confirmation_time"])
                continue
            trigger = _pre_fill_trigger(event, spot_map[event["ticker"]], plan["horizon_end_local_ns"])
            if trigger is not None:
                event.update(event_status="PRE_FILL_TRIGGER_CANCELLED", terminal_reason="PRE_FILL_TRIGGER_CANCELLED", label_available_at=trigger[0], option_coverage_status="ENTRY_CANCELLED_" + trigger[1])
                continue
            eligible = [q for q in quote_map[event["decision_id"]] if q["time_local_ns"] > event["confirmation_time"] and q["time_local_ns"] < plan["horizon_end_local_ns"] and _valid_quote(q)]
            if not eligible:
                exact_h2 = any(q["time_local_ns"] == plan["horizon_end_local_ns"] and _valid_quote(q) for q in quote_map[event["decision_id"]])
                event.update(event_status="TOO_LATE" if exact_h2 else "NO_ENTRY_QUOTE", terminal_reason="TOO_LATE" if exact_h2 else "NO_ENTRY_QUOTE", option_coverage_status="ENTRY_ASK_H2" if exact_h2 else "ENTRY_QUOTE_MISSING", label_available_at=plan["horizon_end_local_ns"])
                continue
            q = eligible[0]; ask = _finite(q["ask"], "ask"); event.update(entry_quote_time=q["time_local_ns"], entry_quote_time_local_ns=q["time_local_ns"], event_entry_ask=ask, option_coverage_status="ENTRY_QUOTE_VALID")
            event["intent_id"] = _id("D_INTENT_V1", event_id=event["event_id"], decision_id=event["decision_id"], entry_quote_time_local_ns=q["time_local_ns"]); event.update(terminal_reason="FILLED", label_available_at=q["time_local_ns"]); intents.append(event)
    ledger = _ledger(intents, quotes, plans, spot_map)
    coverage = _coverage(plans, events, ledger)
    return {"status": "SYNTHETIC_MECHANICS_ONLY", "events": sorted(events, key=lambda e: (e["calendar_ordinal"], e["plan_id"], e["anchor_id"])), "ledger": ledger, "plan_coverage": coverage, "counts": _counts(events, ledger, coverage)}


def _ledger(intents: Sequence[Mapping[str, Any]], quotes: Sequence[Mapping[str, Any]], plans: Sequence[Mapping[str, Any]], spot_map: Mapping[str, Sequence[Mapping[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with localcontext() as ctx:
        ctx.prec = 1000; ctx.traps[Inexact] = True
        for event in intents:
            ask = Decimal(str(event["event_entry_ask"])); risk = int(((ask + Decimal("0.02"))*Decimal(10000)+Decimal(260)).to_integral_value(rounding=ROUND_CEILING)); qty = 500000 // risk
            horizon = next(p["horizon_end_local_ns"] for p in plans if p["plan_id"] == event["plan_id"])
            for arm in ("A", "B"):
                for cost, slip in (("BASE", Decimal("0.01")), ("ADVERSE", Decimal("0.02"))):
                    lid = _id("D_LEDGER_V1", intent_id=event["intent_id"], arm=arm, cost=cost)
                    status, fill = ("EVENT_RISK_BUDGET", "NO_FILL") if qty == 0 else ("ADMITTED", "FILLED")
                    debit = Decimal(qty)*((ask+slip)*Decimal(100)+Decimal("1.30")) if qty else None
                    bid = None; exit_time = horizon
                    trigger = _post_fill_trigger(event, spot_map[event["ticker"]], horizon) if arm == "A" else None
                    exit_kind = trigger[1] if trigger is not None else "H2"
                    earliest_bid = trigger[0] if trigger is not None else horizon
                    candidates = [q for q in quotes if q.get("decision_id") == event["decision_id"] and ((q["time_local_ns"] > earliest_bid and q["time_local_ns"] <= horizon) if trigger is not None else q["time_local_ns"] == horizon) and _valid_quote(q)]
                    if candidates: bid, exit_time = _finite(candidates[0]["bid"], "bid"), candidates[0]["time_local_ns"]
                    credit = Decimal(qty)*((max(Decimal(str(bid or 0))-slip, Decimal(0)))*Decimal(100)-Decimal("1.30")) if qty else None
                    rows.append({"ledger_id":lid,"intent_id":event["intent_id"],"event_id":event["event_id"],"plan_id":event["plan_id"],"ticker":event["ticker"],"event_session_date":event["event_session_date"],"arm":arm,"cost":cost,"admission_status":status,"fill_status":fill,"decision_time":event["confirmation_time"],"entry_quote_time":event["entry_quote_time"],"horizon_end":horizon,"decision_id":event["decision_id"],"right":event["side"],"entry_ask":event["event_entry_ask"],"slippage_dollars":_decimal(slip),"unit_risk_cents":risk,"qty":qty,"entry_debit_decimal":_decimal(debit) if debit is not None else None,"exit_trigger_time":trigger[0] if trigger is not None and qty else horizon if qty else None,"exit_trigger_kind":exit_kind if qty else "NOT_APPLICABLE","exit_bid_time":exit_time if bid is not None else None,"exit_bid":bid,"accounting_exit_time":exit_time if qty else None,"exit_credit_decimal":_decimal(credit) if credit is not None else None,"net_decimal":_decimal(credit-debit) if credit is not None else None,"outcome":exit_kind if qty else None,"missing_exit_flag":bool(qty and bid is None),"ambiguous_flag":False,"label_available_at":exit_time if qty else event["entry_quote_time"],"cash_before_entry_decimal":_decimal(INITIAL_CASH),"reserve_before_entry_decimal":"0","exit_fee_obligation_before_decimal":"0","realized_equity_before_decimal":_decimal(INITIAL_CASH),"cash_after_entry_decimal":"0" if qty else None,"reserve_after_entry_decimal":_decimal(debit) if debit else None,"exit_fee_obligation_after_entry_decimal":_decimal(Decimal(qty)*Decimal("1.30")) if qty else None,"realized_equity_after_entry_decimal":_decimal(INITIAL_CASH) if qty else None,"cash_after_exit_decimal":_decimal(credit) if credit else None,"reserve_after_exit_decimal":"0" if qty else None,"exit_fee_obligation_after_exit_decimal":"0" if qty else None,"realized_equity_after_exit_decimal":_decimal(INITIAL_CASH+credit-debit) if credit else None,"wait_reason":None,"b_plan_pin":event["b_plan_pin"],"b_value_pin":event["b_value_pin"],"c_anchor_pin":event["c_anchor_pin"],"c_geometry_pin":event["c_geometry_pin"],"fixed_risk_contract_pin":event["fixed_risk_contract_pin"]})
    return sorted(rows, key=lambda r: (r["event_session_date"], r["ticker"], r["arm"], r["cost"], r["ledger_id"]))


def _coverage(plans: Sequence[Mapping[str, Any]], events: Sequence[Mapping[str, Any]], ledger: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result=[]
    for p in plans:
        rows=[e for e in events if e["plan_id"]==p["plan_id"]]; confirmed=[e for e in rows if e["event_id"]]; result.append({"calendar_ordinal":p["calendar_ordinal"],"plan_id":p["plan_id"],"ticker":p["ticker"],"trade_date":p["trade_date"],"expiry_date":p["expiry_date"],"geometry_partition":p["geometry_partition"],"c_anchor_count":len(rows),"eligible_anchor_count":len(rows),"revisit_row_count":len(rows),"confirmed_event_count":len(confirmed),"first_physical_event_id":confirmed[0]["event_id"] if confirmed else None,"first_physical_event_time":confirmed[0]["confirmation_time"] if confirmed else None,"outside_evaluation_event_count":sum(e["terminal_reason"]=="OUTSIDE_EVALUATION_WINDOW" for e in rows),"in_evaluation_event_count":sum(e["event_id"] is not None and e["terminal_reason"]!="OUTSIDE_EVALUATION_WINDOW" for e in rows),"economic_intent_count":sum(e["intent_id"] is not None for e in rows),"event_day_evidence_json":"[]","terminal_status_counts_json":_canon({k:sum(e["terminal_reason"]==k for e in rows) for k in sorted(EVENT_TERMINALS)}),"b_plan_pin":p["b_plan_pin"],"b_value_pin":p["b_value_pin"],"c_anchor_pin":p["c_anchor_pin"],"c_geometry_pin":p["c_geometry_pin"],"fixed_risk_contract_pin":p["fixed_risk_contract_pin"]})
    return result


def _counts(events: Sequence[Mapping[str, Any]], ledger: Sequence[Mapping[str, Any]], coverage: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    intents=len({r["intent_id"] for r in ledger}); admitted=sum(r["admission_status"]=="ADMITTED" for r in ledger)//4
    return {"plan_rows":len(coverage),"plan_coverage_rows":len(coverage),"revisit_rows":len(events),"confirmed_rows":sum(e["event_id"] is not None for e in events),"common_intent_rows":intents,"admitted_intent_rows":admitted,"wait_rows":0,"event_risk_budget_rows":sum(r["admission_status"]=="EVENT_RISK_BUDGET" for r in ledger)//4,"no_fill_rows":sum(r["fill_status"]=="NO_FILL" for r in ledger),"filled_rows":sum(r["fill_status"]=="FILLED" for r in ledger),"a_base_ledger_rows":sum(r["arm"]=="A" and r["cost"]=="BASE" for r in ledger),"a_adverse_ledger_rows":sum(r["arm"]=="A" and r["cost"]=="ADVERSE" for r in ledger),"b_base_ledger_rows":sum(r["arm"]=="B" and r["cost"]=="BASE" for r in ledger),"b_adverse_ledger_rows":sum(r["arm"]=="B" and r["cost"]=="ADVERSE" for r in ledger)}
