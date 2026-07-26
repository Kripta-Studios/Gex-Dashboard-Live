"""Portable KING NODE calculation engine.

This module ports the calculation contract used by
``MASTER_KING_NODE_RECORD_V5.xlsx`` and ``live_king_node.py`` to a JSON-only
runtime.  It intentionally has no Excel, IBKR, pandas, or network dependency.
The caller supplies:

* the latest Tastytrade exposure JSON;
* observed VIX, VVIX, and VIX1D snapshots;
* the previously persisted state;
* an optional export of the workbook's static Matrix/IV Regime Map values.

The engine returns a self-contained snapshot for the web dashboard and a JSON
serializable state for the next cycle.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import math
from statistics import median
from typing import Any


SCHEMA_VERSION = "king-node.v1"
STATE_VERSION = 1
WINDOW_EACH_SIDE = 23
WINDOW_SIZE = WINDOW_EACH_SIDE * 2 + 1
SMOOTH_READINGS = 3
LEVEL_LOCK_CYCLES = 3
LEVEL_COUNT = 6
HISTORY_LENGTH = 50
GEX_HISTORY_LENGTH = 91
VOMMA_HISTORY_LENGTH = 8
SKEW_OFFSET_POINTS = 25.0

INDEX_DEADBANDS = {
    "vix": 0.10,
    "vvix": 0.25,
    "vix1d": 0.10,
    "atm_iv": 0.001,
}

# Jan-Jun 2026, 116 clean SPX 0DTE sessions.  Values are put/call wing IV
# premiums in volatility points.  The runtime interpolates between anchors.
SKEW_BASELINE = {
    "09:30": (2.15, -1.58),
    "10:00": (2.21, -1.41),
    "10:30": (2.29, -1.29),
    "11:00": (2.48, -1.23),
    "11:30": (2.48, -1.11),
    "12:00": (2.66, -0.85),
    "12:30": (2.85, -0.62),
    "13:00": (3.01, -0.30),
    "13:30": (3.26, 0.32),
    "14:00": (3.77, 0.78),
    "14:30": (4.46, 1.45),
    "15:00": (4.55, 2.20),
    "15:30": (4.11, 3.12),
}

ROW_NUMERIC_FIELDS = (
    "raw_call_gamma",
    "raw_put_gamma",
    "raw_gamma",
    "gamma_gross",
    "gex",
    "zomma",
    "dex",
    "vex",
    "vomma",
    "vega",
    "speed",
    "charm",
    "dgex",
    "call_gex",
    "put_gex",
    "call_iv",
    "put_iv",
)

PROFILE_FIELDS = (
    "gamma_gross",
    "gex",
    "zomma",
    "dex",
    "vex",
    "vomma",
    "vega",
    "speed",
)

TASTY_REQUIRED_COLUMNS = (
    "strike_price",
    "call_gamma",
    "put_gamma",
    "call_open_int",
    "put_open_int",
)


class KingNodeDataError(ValueError):
    """Raised when the core Tastytrade surface cannot be validated."""


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _sum_present(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return sum(present) if present else None


def _mean_present(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return sum(present) / len(present) if present else None


def _iso_utc(value: datetime | str | None = None) -> str:
    if isinstance(value, str):
        return value
    dt = value or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _epoch_seconds(value: datetime | str | None = None) -> float:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc).timestamp()
    else:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _sign_label(value: float | None) -> str:
    return "Pos" if value is not None and value >= 0 else "Neg"


def _side(value: float | None) -> int:
    if value is None or value == 0:
        return 0
    return 1 if value > 0 else -1


def initial_state(session_date: str | None = None) -> dict[str, Any]:
    """Return an empty, JSON-serializable runtime state."""

    return {
        "version": STATE_VERSION,
        "session_date": session_date,
        "histories": {
            "vix": [],
            "vvix": [],
            "vix1d": [],
            "atm_iv": [],
            "put_skew_residual": [],
            "call_skew_residual": [],
            "gex": [],
            "near_vomma": [],
        },
        "surface_history": [],
        "surface_source_ids": [],
        "locked": {"resistance": [], "support": []},
        "pending": {"resistance": {}, "support": {}},
        "gex_sign": 0,
        "gex_flip_at": None,
        "vix1d_low": None,
        "vix1d_high": None,
        "vix1d_low_at": None,
        "vix1d_high_at": None,
        "vix1d_high_prominence_pct": 0.0,
    }


def _normalise_state(state: dict[str, Any] | None, session_date: str) -> dict[str, Any]:
    if not isinstance(state, dict):
        return initial_state(session_date)
    if state.get("version") != STATE_VERSION:
        return initial_state(session_date)
    if state.get("session_date") != session_date:
        return initial_state(session_date)

    clean = initial_state(session_date)
    clean.update(deepcopy(state))
    for key, default in initial_state(session_date)["histories"].items():
        clean.setdefault("histories", {}).setdefault(key, deepcopy(default))
    clean.setdefault("locked", {"resistance": [], "support": []})
    clean.setdefault("pending", {"resistance": {}, "support": {}})
    return clean


def _append_history(
    state: dict[str, Any],
    name: str,
    value: float | None,
    timestamp: str,
    max_length: int = HISTORY_LENGTH,
) -> None:
    if value is None:
        return
    history = state["histories"].setdefault(name, [])
    item = {"timestamp": timestamp, "value": float(value)}
    if history and history[-1].get("timestamp") == timestamp:
        history[-1] = item
    else:
        history.append(item)
    del history[:-max_length]


def _history_values(state: dict[str, Any], name: str) -> list[float]:
    values: list[float] = []
    for item in state.get("histories", {}).get(name, []):
        value = _number(item.get("value")) if isinstance(item, dict) else _number(item)
        if value is not None:
            values.append(value)
    return values


def two_half_direction(values: list[float], deadband: float) -> str:
    """Port of live_king_node._two_half_dir."""

    if len(values) < 4:
        return "Flat"
    half = len(values) // 2
    older = values[:half]
    recent = values[half:]
    if not older or not recent:
        return "Flat"
    difference = sum(recent) / len(recent) - sum(older) / len(older)
    if difference >= deadband:
        return "Up"
    if difference <= -deadband:
        return "Down"
    return "Flat"


def rows_from_tastytrade(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate and normalize a Tastytrade ``orient=split`` option surface."""

    option_data = payload.get("option_data")
    if not isinstance(option_data, dict):
        raise KingNodeDataError("option_data is missing or is not an object")
    columns = option_data.get("columns")
    data = option_data.get("data")
    if not isinstance(columns, list) or not isinstance(data, list):
        raise KingNodeDataError("option_data must contain split columns and data")

    names = [str(column) for column in columns]
    missing = [column for column in TASTY_REQUIRED_COLUMNS if column not in names]
    if missing:
        raise KingNodeDataError(
            "Tastytrade surface is missing required fields: " + ", ".join(missing)
        )

    rows: list[dict[str, Any]] = []
    for values in data:
        if not isinstance(values, list):
            continue
        row = {
            name: values[index] if index < len(values) else None
            for index, name in enumerate(names)
        }
        strike = _number(row.get("strike_price"))
        if strike is None or strike <= 0:
            continue
        rows.append(row)
    if not rows:
        raise KingNodeDataError("Tastytrade surface contains no valid strikes")
    return rows


def aggregate_by_strike(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate option rows by strike, multiplying gamma by OI per leg first."""

    grouped: dict[float, dict[str, Any]] = {}
    for source in rows:
        strike = _number(source.get("strike_price"))
        if strike is None:
            continue
        target = grouped.setdefault(
            strike,
            {
                "strike": strike,
                "_raw_call": [],
                "_raw_put": [],
                "_call_gex": [],
                "_put_gex": [],
                "_call_iv": [],
                "_put_iv": [],
                "_exposures": {
                    field: []
                    for field in (
                        "total_gamma",
                        "total_zomma",
                        "total_delta",
                        "total_vanna",
                        "total_vomma",
                        "total_vega",
                        "total_speed",
                        "total_charm",
                        "total_dgex",
                    )
                },
            },
        )

        call_gamma = _number(source.get("call_gamma"))
        put_gamma = _number(source.get("put_gamma"))
        call_oi = _number(source.get("call_open_int"))
        put_oi = _number(source.get("put_open_int"))
        target["_raw_call"].append(
            call_gamma * call_oi
            if call_gamma is not None and call_oi is not None
            else None
        )
        target["_raw_put"].append(
            put_gamma * put_oi
            if put_gamma is not None and put_oi is not None
            else None
        )
        target["_call_gex"].append(_number(source.get("call_gex")))
        target["_put_gex"].append(_number(source.get("put_gex")))
        target["_call_iv"].append(_number(source.get("call_iv")))
        target["_put_iv"].append(_number(source.get("put_iv")))
        for field in target["_exposures"]:
            value = _number(source.get(field))
            target["_exposures"][field].append(
                value * 1_000_000_000.0 if value is not None else None
            )

    output: list[dict[str, Any]] = []
    for strike in sorted(grouped):
        item = grouped[strike]
        raw_call = _sum_present(item["_raw_call"])
        raw_put = _sum_present(item["_raw_put"])
        call_gex = _sum_present(item["_call_gex"])
        put_gex = _sum_present(item["_put_gex"])
        exposures = {
            field: _sum_present(values)
            for field, values in item["_exposures"].items()
        }
        gex = exposures["total_gamma"]
        if gex is None and call_gex is not None and put_gex is not None:
            gex = call_gex + put_gex
        gamma_gross = (
            abs(call_gex) + abs(put_gex)
            if call_gex is not None and put_gex is not None
            else (abs(gex) if gex is not None else None)
        )
        output.append(
            {
                "strike": strike,
                "raw_call_gamma": raw_call,
                "raw_put_gamma": raw_put,
                "raw_gamma": (
                    raw_call + raw_put
                    if raw_call is not None and raw_put is not None
                    else None
                ),
                "gamma_gross": gamma_gross,
                "gex": gex,
                "zomma": exposures["total_zomma"],
                "dex": exposures["total_delta"],
                "vex": exposures["total_vanna"],
                "vomma": exposures["total_vomma"],
                "vega": exposures["total_vega"],
                "speed": exposures["total_speed"],
                "charm": exposures["total_charm"],
                "dgex": exposures["total_dgex"],
                "call_gex": call_gex,
                "put_gex": put_gex,
                "call_iv": _mean_present(item["_call_iv"]),
                "put_iv": _mean_present(item["_put_iv"]),
            }
        )
    return output


def select_strike_window(
    rows: list[dict[str, Any]],
    spot: float,
    each_side: int = WINDOW_EACH_SIDE,
) -> list[dict[str, Any]]:
    """Select the nearest 23 strikes below/at and above spot (47 maximum)."""

    ordered = sorted(rows, key=lambda row: row["strike"])
    below = [row for row in ordered if row["strike"] <= spot][-each_side:]
    above = [row for row in ordered if row["strike"] > spot][:each_side]
    selected = below + above

    target_size = each_side * 2 + 1
    if len(selected) < target_size:
        selected_strikes = {row["strike"] for row in selected}
        remainder = sorted(
            (row for row in ordered if row["strike"] not in selected_strikes),
            key=lambda row: (abs(row["strike"] - spot), row["strike"]),
        )
        selected.extend(remainder[: target_size - len(selected)])
    return sorted(selected, key=lambda row: row["strike"])


def _smooth_surface(
    state: dict[str, Any],
    rows: list[dict[str, Any]],
    source_id: str,
) -> tuple[list[dict[str, Any]], int]:
    source_ids = state.setdefault("surface_source_ids", [])
    surfaces = state.setdefault("surface_history", [])
    if not source_ids or source_ids[-1] != source_id:
        source_ids.append(source_id)
        surfaces.append(deepcopy(rows))
        del source_ids[:-SMOOTH_READINGS]
        del surfaces[:-SMOOTH_READINGS]

    by_surface = [
        {float(row["strike"]): row for row in surface}
        for surface in surfaces
        if isinstance(surface, list)
    ]
    output: list[dict[str, Any]] = []
    for row in rows:
        strike = float(row["strike"])
        smoothed = {"strike": strike}
        for field in ROW_NUMERIC_FIELDS:
            values = [
                _number(surface[strike].get(field))
                for surface in by_surface
                if strike in surface
            ]
            smoothed[field] = _mean_present(values)
        output.append(smoothed)
    return output, len(by_surface)


def _interpolate(rows: list[dict[str, Any]], field: str, target: float) -> float | None:
    points = sorted(
        (float(row["strike"]), _number(row.get(field)))
        for row in rows
        if _number(row.get(field)) is not None and _number(row.get(field)) > 0
    )
    if len(points) < 2 or target < points[0][0] or target > points[-1][0]:
        return None
    for index in range(1, len(points)):
        if points[index][0] >= target:
            strike0, value0 = points[index - 1]
            strike1, value1 = points[index]
            if strike1 == strike0:
                return value1
            weight = (target - strike0) / (strike1 - strike0)
            return value0 + (value1 - value0) * weight
    return None


def _dte_hours(rows: list[dict[str, Any]]) -> float | None:
    values = []
    for row in rows:
        value = _number(row.get("time_till_exp"))
        if value is not None and value >= 0:
            values.append(value * 365.0 * 24.0)
    return median(values) if values else None


def _baseline_for_minute(minute: int) -> tuple[float, float]:
    anchors = sorted(
        (
            int(label[:2]) * 60 + int(label[3:]),
            values,
        )
        for label, values in SKEW_BASELINE.items()
    )
    if minute <= anchors[0][0]:
        return anchors[0][1]
    if minute >= anchors[-1][0]:
        return anchors[-1][1]
    for index in range(1, len(anchors)):
        if anchors[index][0] >= minute:
            minute0, values0 = anchors[index - 1]
            minute1, values1 = anchors[index]
            weight = (minute - minute0) / (minute1 - minute0)
            return (
                values0[0] + (values1[0] - values0[0]) * weight,
                values0[1] + (values1[1] - values0[1]) * weight,
            )
    return anchors[-1][1]


def _skew(
    rows: list[dict[str, Any]],
    spot: float,
    state: dict[str, Any],
    timestamp: str,
    market_minute: int,
) -> dict[str, Any]:
    atm_call = _interpolate(rows, "call_iv", spot)
    atm_put = _interpolate(rows, "put_iv", spot)
    atm = (
        (atm_call + atm_put) / 2.0
        if atm_call is not None and atm_put is not None
        else (atm_call if atm_call is not None else atm_put)
    )
    put_wing = _interpolate(rows, "put_iv", spot - SKEW_OFFSET_POINTS)
    call_wing = _interpolate(rows, "call_iv", spot + SKEW_OFFSET_POINTS)
    put_skew = (
        (put_wing - atm) * 100.0
        if put_wing is not None and atm is not None
        else None
    )
    call_skew = (
        (call_wing - atm) * 100.0
        if call_wing is not None and atm is not None
        else None
    )
    risk_reversal = (
        call_skew - put_skew
        if call_skew is not None and put_skew is not None
        else None
    )

    base_put, base_call = _baseline_for_minute(market_minute)
    if put_skew is not None:
        _append_history(
            state,
            "put_skew_residual",
            put_skew - base_put,
            timestamp,
        )
    if call_skew is not None:
        _append_history(
            state,
            "call_skew_residual",
            call_skew - base_call,
            timestamp,
        )
    put_values = _history_values(state, "put_skew_residual")
    call_values = _history_values(state, "call_skew_residual")
    put_direction = two_half_direction(put_values, 0.10)
    call_direction = two_half_direction(call_values, 0.10)
    steep = False
    if len(put_values) >= 3 and max(put_values) - min(put_values) > 0.2:
        steep = (
            (put_values[-1] - min(put_values))
            / (max(put_values) - min(put_values))
            >= 0.66
        )
    return {
        "atm_iv": atm,
        "put_skew_vol_points": put_skew,
        "call_skew_vol_points": call_skew,
        "risk_reversal_vol_points": risk_reversal,
        "put_direction": put_direction,
        "call_direction": call_direction,
        "put_steep": steep,
        "offset_points": SKEW_OFFSET_POINTS,
        "baseline": {"put": base_put, "call": base_call},
    }


def _max_abs(rows: list[dict[str, Any]], field: str) -> float:
    values = [abs(value) for row in rows if (value := _number(row.get(field))) is not None]
    return max(values) if values else 0.0


def _rank_level_candidates(
    rows: list[dict[str, Any]],
    spot: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    maxima = {
        field: _max_abs(rows, field)
        for field in (
            "gamma_gross",
            "gex",
            "dex",
            "vex",
            "zomma",
            "vomma",
            "speed",
            "raw_gamma",
        )
    }
    weights = {
        "gamma_gross": 1.30,
        "gex": 2.00,
        "dex": 0.70,
        "vex": 0.90,
        "zomma": 0.80,
        "vomma": 0.60,
        "speed": 0.50,
        "raw_gamma": 0.90,
    }
    candidates: list[dict[str, Any]] = []
    for row in rows:
        ratios: dict[str, float] = {}
        for field, maximum in maxima.items():
            value = _number(row.get(field))
            ratios[field] = abs(value) / maximum if value is not None and maximum else 0.0
        confluence = sum(1 for ratio in ratios.values() if ratio >= 0.66)
        score = sum(weights[field] * ratios[field] for field in weights)
        # The workbook boosts the near-expiry profile.  This distance term is only
        # a tie-breaker; it cannot turn a weak row into a strong level.
        distance = abs(float(row["strike"]) - spot)
        score += max(0.0, 0.15 - distance / max(spot, 1.0))
        backers = [
            field
            for field, ratio in ratios.items()
            if ratio >= 0.66
        ]
        candidates.append(
            {
                "strike": float(row["strike"]),
                "score": score,
                "confluence": confluence,
                "backers": backers,
                "gex": _number(row.get("gex")),
                "raw_gamma": _number(row.get("raw_gamma")),
                "distance": float(row["strike"]) - spot,
            }
        )

    resistances = sorted(
        (item for item in candidates if item["strike"] > spot),
        key=lambda item: (-item["score"], item["distance"], item["strike"]),
    )
    supports = sorted(
        (item for item in candidates if item["strike"] < spot),
        key=lambda item: (-item["score"], abs(item["distance"]), -item["strike"]),
    )
    return resistances[:LEVEL_COUNT], supports[:LEVEL_COUNT]


def _apply_level_lock(
    locked: list[float],
    pending: dict[str, Any],
    raw: list[float],
    spot: float,
    side: str,
) -> tuple[list[float], dict[str, Any]]:
    """Port the three-cycle level lock from ``live_king_node.apply_lock``."""

    if locked:
        if side == "resistance" and spot >= locked[0]:
            return list(raw[:LEVEL_COUNT]), {}
        if side == "support" and spot <= locked[0]:
            return list(raw[:LEVEL_COUNT]), {}
    if not locked:
        return list(raw[:LEVEL_COUNT]), {}

    new_locked = list(locked)
    count = min(LEVEL_COUNT, max(len(raw), len(locked)))
    for index in range(count):
        raw_item = raw[index] if index < len(raw) else None
        current = new_locked[index] if index < len(new_locked) else None
        key = str(index)
        if raw_item is None:
            continue
        if raw_item == current:
            pending.pop(key, None)
            continue
        challenge = pending.get(key)
        if (
            isinstance(challenge, list)
            and len(challenge) == 2
            and challenge[0] == raw_item
        ):
            challenge[1] += 1
            if challenge[1] >= LEVEL_LOCK_CYCLES:
                if index < len(new_locked):
                    new_locked[index] = raw_item
                else:
                    new_locked.append(raw_item)
                pending.pop(key, None)
        else:
            pending[key] = [raw_item, 1]

    raw_top = [value for value in raw[:LEVEL_COUNT] if value is not None]
    for index, value in enumerate(new_locked):
        if value is not None and value not in raw_top:
            replacement = next(
                (candidate for candidate in raw_top if candidate not in new_locked),
                None,
            )
            if replacement is not None:
                new_locked[index] = replacement
                pending.pop(str(index), None)

    deduplicated: list[float] = []
    for value in new_locked + raw:
        if value is not None and value not in deduplicated:
            deduplicated.append(value)
        if len(deduplicated) >= LEVEL_COUNT:
            break
    return deduplicated, pending


def _node(rows: list[dict[str, Any]], field: str, mode: str = "max_abs") -> dict[str, Any] | None:
    candidates = [row for row in rows if _number(row.get(field)) is not None]
    if not candidates:
        return None
    if mode == "max":
        row = max(candidates, key=lambda item: float(item[field]))
    elif mode == "min":
        row = min(candidates, key=lambda item: float(item[field]))
    else:
        row = max(candidates, key=lambda item: abs(float(item[field])))
    return {
        "strike": float(row["strike"]),
        "value": float(row[field]),
        "field": field,
    }


def _walls(
    rows: list[dict[str, Any]],
    gex_positive: bool,
) -> list[dict[str, Any]]:
    candidates = [
        row
        for row in rows
        if _number(row.get("gamma_gross")) is not None
        and _number(row.get("gex")) is not None
        and ((_number(row.get("gex")) or 0) > 0) is gex_positive
    ]
    candidates.sort(
        key=lambda row: (-float(row["gamma_gross"]), float(row["strike"]))
    )
    return [
        {
            "strike": float(row["strike"]),
            "gamma_gross": float(row["gamma_gross"]),
            "gex": float(row["gex"]),
        }
        for row in candidates[:3]
    ]


def _cumulative_levels(rows: list[dict[str, Any]], spot: float) -> dict[str, Any]:
    cumulative = 0.0
    cumulative_rows: list[dict[str, float]] = []
    for row in rows:
        gex = _number(row.get("gex"))
        if gex is None:
            continue
        cumulative += gex
        cumulative_rows.append(
            {"strike": float(row["strike"]), "cumulative_gex": cumulative}
        )

    gamma_flip = None
    if len(cumulative_rows) >= 3:
        maximum_index = max(
            range(len(cumulative_rows)),
            key=lambda index: cumulative_rows[index]["cumulative_gex"],
        )
        if 0 < maximum_index < len(cumulative_rows) - 1:
            gamma_flip = cumulative_rows[maximum_index]["strike"]

    crossings: list[dict[str, float]] = []
    for previous, current in zip(cumulative_rows, cumulative_rows[1:]):
        value0 = previous["cumulative_gex"]
        value1 = current["cumulative_gex"]
        if value0 == 0 or (value0 > 0) != (value1 > 0):
            interpolated = previous["strike"]
            if value1 != value0:
                interpolated = previous["strike"] + (
                    (current["strike"] - previous["strike"])
                    * (-value0)
                    / (value1 - value0)
                )
            crossings.append(
                {
                    "strike": previous["strike"],
                    "interpolated_strike": interpolated,
                    "distance": abs(previous["strike"] - spot),
                }
            )
    zero_gamma = min(crossings, key=lambda item: item["distance"]) if crossings else None
    return {
        "gamma_flip": gamma_flip,
        "zero_gamma": zero_gamma,
        "cumulative": cumulative_rows,
    }


def _vomma_status(values: list[float]) -> dict[str, Any]:
    if len(values) < 3:
        return {
            "status": "warming up",
            "signal": "none",
            "reference": values[-1] if values else 0.0,
            "change_pct": 0.0,
        }
    peak = max(values)
    trough = min(values)
    latest = values[-1]
    peak_index = len(values) - 1 - values[::-1].index(peak)
    trough_index = len(values) - 1 - values[::-1].index(trough)
    if peak_index >= trough_index:
        if peak_index == len(values) - 1:
            return {
                "status": "RISING / AT PEAK",
                "signal": "none",
                "reference": peak,
                "change_pct": 0.0,
            }
        change = (peak - latest) / peak if peak > 0 else 0.0
        return {
            "status": (
                f"ROLLED OVER -{change * 100:.0f}% - LONG trigger"
                if change >= 0.05
                else "peaked - watching"
            ),
            "signal": "long" if change >= 0.05 else "none",
            "reference": peak,
            "change_pct": change * 100.0,
        }
    if trough_index == len(values) - 1:
        return {
            "status": "FALLING / AT TROUGH",
            "signal": "none",
            "reference": trough,
            "change_pct": 0.0,
        }
    change = (latest - trough) / trough if trough > 0 else 0.0
    return {
        "status": (
            f"TURNED UP +{change * 100:.0f}% - SHORT trigger"
            if change >= 0.05
            else "troughed - watching"
        ),
        "signal": "short" if change >= 0.05 else "none",
        "reference": trough,
        "change_pct": change * 100.0,
    }


def _gex_monitor(
    state: dict[str, Any],
    net_gex: float,
    timestamp: str,
    vix1d_up: bool,
    vvix_up: bool,
) -> dict[str, Any]:
    _append_history(
        state,
        "gex",
        net_gex,
        timestamp,
        max_length=GEX_HISTORY_LENGTH,
    )
    current_sign = _side(net_gex) or int(state.get("gex_sign", 0))
    previous_sign = int(state.get("gex_sign", 0))
    if current_sign and current_sign != previous_sign:
        if previous_sign:
            state["gex_flip_at"] = timestamp
        state["gex_sign"] = current_sign

    history = state["histories"]["gex"]
    per_15_minutes = None
    if len(history) >= 2:
        first = history[0]
        last = history[-1]
        elapsed_minutes = max(
            (_epoch_seconds(last["timestamp"]) - _epoch_seconds(first["timestamp"]))
            / 60.0,
            0.5,
        )
        per_15_minutes = (
            (float(last["value"]) - float(first["value"]))
            / elapsed_minutes
            * 15.0
        )

    flip_age_minutes = None
    if state.get("gex_flip_at"):
        flip_age_minutes = max(
            0.0,
            (_epoch_seconds(timestamp) - _epoch_seconds(state["gex_flip_at"])) / 60.0,
        )
    tension = (
        per_15_minutes is not None
        and per_15_minutes > 0
        and vix1d_up
        and not vvix_up
    )
    return {
        "sign": "POS" if state.get("gex_sign", 0) > 0 else "NEG",
        "per_15_minutes": per_15_minutes,
        "flip_at": state.get("gex_flip_at"),
        "flip_age_minutes": flip_age_minutes,
        "vol_bid_tension": tension,
        "samples": len(history),
    }


def _vol_tension(
    net_gex: float,
    gex_monitor: dict[str, Any],
    vix: float | None,
    vix1d: float | None,
    vix1d_direction: str,
    skew: dict[str, Any],
) -> dict[str, Any]:
    slope = _number(gex_monitor.get("per_15_minutes"))
    ratio = vix1d / vix if vix1d is not None and vix not in (None, 0) else None
    if not net_gex:
        return {"label": "NO NET GEX", "expectation": "No profile this cycle", "ratio": ratio}
    if slope is None:
        return {"label": "BUILDING", "expectation": "Slope window is warming up", "ratio": ratio}

    negative = net_gex < 0
    pace = abs(slope) / abs(net_gex) * 100.0
    band = "SLOW" if pace < 1.5 else ("FAST" if pace > 4.0 else "MOD")
    deepening = slope < 0 if negative else slope > 0
    bid = vix1d_direction == "Up" or (ratio is not None and ratio > 0.75)
    steep = bool(skew.get("put_steep"))
    put_up = skew.get("put_direction") == "Up"

    flip_age = _number(gex_monitor.get("flip_age_minutes"))
    if flip_age is not None and flip_age <= 30:
        label, expectation = "REGIME FLIP", "Levels not re-anchored — stand down"
    elif ratio is not None and ratio >= 0.90 and steep:
        label, expectation = "VOL SHOCK", "Levels unreliable — size down"
    elif negative and deepening and band == "FAST" and (bid or put_up):
        label = "ACCELERATING NEG GAMMA"
        expectation = "Trend/cascade risk — do not fade"
    elif negative and not deepening and band != "SLOW":
        label, expectation = "NEG GAMMA UNWINDING", "Supports firming — bounces carry"
    elif negative:
        label, expectation = "SLOW NEG GAMMA", "Amplified, no cascade fuel — fade extremes"
    elif deepening and band != "SLOW":
        label, expectation = "POS GAMMA BUILDING", "Resistance leaks — dips shallow"
    elif not deepening and band != "SLOW" and bid:
        label, expectation = "POS GAMMA ERODING", "Pin decaying — breakout risk"
    else:
        label, expectation = "SLOW POS GAMMA", "Levels hold — mean reversion"
    return {
        "label": label,
        "expectation": expectation,
        "ratio": ratio,
        "pace_pct_per_15m": pace,
        "pace_band": band,
        "deepening": deepening,
        "front_end_bid": bid,
    }


def _semantic_matrix(
    gamma_sign: str,
    dex_sign: str,
    vex_sign: str,
    iv_box: str,
) -> dict[str, str]:
    """Transparent fallback for static workbook lookup values.

    The formula catalog contains the lookup formulas but not the literal Matrix
    cells.  A generated reference JSON overrides this function when available.
    """

    positive_gamma = gamma_sign == "Pos"
    if positive_gamma:
        phenomenon = "Gamma pin / compression"
        dealer_is = "Long gamma"
        dealer_action = "Sell strength and buy weakness"
        tactical = "FADE EXTREMES / respect locked levels"
        regime = f"{iv_box} IV · positive-gamma mean reversion"
    else:
        phenomenon = "Gamma expansion / directional amplification"
        dealer_is = "Short gamma"
        dealer_action = "Buy strength and sell weakness"
        tactical = (
            "BUY BREAKS / trail supports"
            if dex_sign == "Pos"
            else "SELL BREAKS / trail resistances"
        )
        regime = f"{iv_box} IV · negative-gamma expansion"
    if vex_sign != dex_sign:
        tilt = f"DEX {dex_sign}, VEX {vex_sign} · mixed flow"
    else:
        tilt = f"DEX/VEX aligned {dex_sign}"
    return {
        "phenomenon": phenomenon,
        "dealer_is": dealer_is,
        "dealer_action": dealer_action,
        "tactical": tactical,
        "regime": regime,
        "tilt": tilt,
    }


def _regime(
    totals: dict[str, float],
    directions: dict[str, str],
    indices: dict[str, float | None],
    atm_iv: float | None,
    dte_hours: float | None,
    reference: dict[str, Any] | None,
) -> dict[str, Any]:
    vix = indices.get("vix")
    vvix = indices.get("vvix")
    vix1d = indices.get("vix1d")
    ratio = vix1d / vix if vix1d is not None and vix not in (None, 0) else None

    iv_raw = "UNAVAILABLE"
    if vix is not None and vvix is not None and ratio is not None:
        if ratio >= 1.1 or vvix >= 110 or vix >= 22:
            iv_raw = "HIGH"
        elif ratio <= 0.9 or (vvix <= 90 and vix <= 15):
            iv_raw = "LOW"
        else:
            iv_raw = "NEUTRAL"
    iv_intensity = (
        max(0.6, min(1.4, 0.6 * ratio + 0.4 * (vvix / 100.0) + 0.4))
        if ratio is not None and vvix is not None
        else None
    )
    dte_boost = (
        1.0 + 0.6 * max(0.0, 1.0 - dte_hours / 6.5)
        if dte_hours is not None
        else None
    )

    if iv_raw == "HIGH":
        iv_box = "High"
        iv_box_method = "catalog_iv_raw"
    elif iv_raw == "LOW":
        iv_box = "Low"
        iv_box_method = "catalog_iv_raw"
    elif vix is not None and atm_iv is not None:
        iv_box = "High" if vix >= atm_iv * 100.0 else "Low"
        iv_box_method = "catalog_neutral_fallback_vix_vs_atm_iv"
    else:
        iv_box = "Neutral"
        iv_box_method = "missing_inputs"

    signs = {
        "gamma": _sign_label(totals.get("gex")),
        "zomma": _sign_label(totals.get("zomma")),
        "dex": _sign_label(totals.get("dex")),
        "vex": _sign_label(totals.get("vex")),
        "vega": _sign_label(totals.get("vega")),
        "vomma": _sign_label(totals.get("vomma")),
        "speed": _sign_label(totals.get("speed")),
        "charm": _sign_label(totals.get("charm")),
    }
    matrix_key = "|".join(
        [
            iv_box,
            signs["gamma"],
            signs["zomma"],
            signs["dex"],
            signs["vex"],
            signs["vega"],
            signs["vomma"],
            signs["speed"],
        ]
    )
    box_key = "|".join(
        [
            "Positive" if signs["gamma"] == "Pos" else "Negative",
            directions["vix"],
            directions["vvix"],
            directions["vix1d"],
        ]
    )

    reference = reference if isinstance(reference, dict) else {}
    matrix = reference.get("matrix", {}) if isinstance(reference.get("matrix", {}), dict) else {}
    iv_map = (
        reference.get("iv_regime_map", {})
        if isinstance(reference.get("iv_regime_map", {}), dict)
        else {}
    )
    matrix_value = matrix.get(matrix_key)
    reference_mode = "workbook_static_export"
    if not isinstance(matrix_value, dict):
        matrix_value = _semantic_matrix(
            signs["gamma"],
            signs["dex"],
            signs["vex"],
            iv_box,
        )
        reference_mode = "semantic_fallback"
    box_value = iv_map.get(box_key)
    if isinstance(box_value, dict):
        box_regime = box_value.get("regime")
        box_iv = box_value.get("iv")
    else:
        box_regime = None
        box_iv = None

    return {
        "iv_raw": iv_raw,
        "iv_box": iv_box,
        "iv_box_method": iv_box_method,
        "iv_intensity": iv_intensity,
        "dte_boost": dte_boost,
        "vix1d_vix_ratio": ratio,
        "signs": signs,
        "matrix_key": matrix_key,
        "box_key": box_key,
        "box_regime": box_regime,
        "box_iv": box_iv,
        "reference_mode": reference_mode,
        **matrix_value,
    }


def _index_values(
    volatility: dict[str, Any],
) -> tuple[dict[str, float | None], dict[str, dict[str, Any]]]:
    values: dict[str, float | None] = {}
    metadata: dict[str, dict[str, Any]] = {}
    for name in ("vix", "vvix", "vix1d"):
        raw = volatility.get(name, {})
        if isinstance(raw, dict):
            value = _number(raw.get("value"))
            metadata[name] = {
                "value": value,
                "timestamp": raw.get("timestamp"),
                "age_seconds": _number(raw.get("age_seconds")),
                "status": str(raw.get("status", "missing")),
                "source": raw.get("source", "ThetaData index snapshot"),
            }
        else:
            value = _number(raw)
            metadata[name] = {
                "value": value,
                "timestamp": None,
                "age_seconds": None,
                "status": "observed" if value is not None else "missing",
                "source": "caller",
            }
        values[name] = value
    return values, metadata


def build_snapshot(
    tastytrade_payload: dict[str, Any],
    volatility: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    *,
    source_meta: dict[str, Any] | None = None,
    reference: dict[str, Any] | None = None,
    generated_at: datetime | str | None = None,
    session_date: str | None = None,
    market_minute: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build a complete KING NODE web snapshot and next runtime state."""

    timestamp = _iso_utc(generated_at)
    generated_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    session_date = session_date or generated_dt.date().isoformat()
    next_state = _normalise_state(state, session_date)
    source_meta = deepcopy(source_meta) if isinstance(source_meta, dict) else {}
    volatility = volatility if isinstance(volatility, dict) else {}

    raw_rows = rows_from_tastytrade(tastytrade_payload)
    spot = _number(tastytrade_payload.get("spot_price"))
    if spot is None or spot <= 0:
        raise KingNodeDataError("spot_price is missing or invalid")
    aggregated = aggregate_by_strike(raw_rows)
    window = select_strike_window(aggregated, spot)
    if len(window) < 5:
        raise KingNodeDataError("fewer than five strikes are available near spot")

    source_id = str(
        source_meta.get("source_id")
        or source_meta.get("path")
        or tastytrade_payload.get("today_ddt_string")
        or timestamp
    )
    rows, smooth_depth = _smooth_surface(next_state, window, source_id)

    index_values, index_metadata = _index_values(volatility)
    for name, value in index_values.items():
        observed_at = index_metadata[name].get("timestamp") or timestamp
        _append_history(next_state, name, value, str(observed_at))

    atm_iv = _interpolate(rows, "call_iv", spot)
    _append_history(next_state, "atm_iv", atm_iv, timestamp)
    directions = {
        name: two_half_direction(
            _history_values(next_state, name),
            INDEX_DEADBANDS[name],
        )
        for name in ("vix", "vvix", "vix1d", "atm_iv")
    }
    minute = market_minute
    if minute is None:
        minute = generated_dt.hour * 60 + generated_dt.minute
    skew = _skew(rows, spot, next_state, timestamp, minute)
    skew["atm_iv"] = atm_iv

    totals: dict[str, float] = {}
    for field in (
        "raw_call_gamma",
        "raw_put_gamma",
        "raw_gamma",
        "gamma_gross",
        "gex",
        "zomma",
        "dex",
        "vex",
        "vomma",
        "vega",
        "speed",
        "charm",
        "dgex",
    ):
        totals[field] = sum(
            value
            for row in rows
            if (value := _number(row.get(field))) is not None
        )

    dte = _dte_hours(raw_rows)
    regime = _regime(
        totals,
        directions,
        index_values,
        atm_iv,
        dte,
        reference,
    )

    raw_resistances, raw_supports = _rank_level_candidates(rows, spot)
    for side_name, candidates in (
        ("resistance", raw_resistances),
        ("support", raw_supports),
    ):
        raw_levels = [item["strike"] for item in candidates]
        locked, pending = _apply_level_lock(
            list(next_state["locked"].get(side_name, [])),
            dict(next_state["pending"].get(side_name, {})),
            raw_levels,
            spot,
            side_name,
        )
        next_state["locked"][side_name] = locked
        next_state["pending"][side_name] = pending

    candidate_lookup = {
        item["strike"]: item for item in raw_resistances + raw_supports
    }
    locked_resistances = [
        candidate_lookup.get(
            strike,
            {
                "strike": strike,
                "score": None,
                "confluence": None,
                "backers": [],
                "gex": next(
                    (
                        _number(row.get("gex"))
                        for row in rows
                        if row["strike"] == strike
                    ),
                    None,
                ),
                "raw_gamma": next(
                    (
                        _number(row.get("raw_gamma"))
                        for row in rows
                        if row["strike"] == strike
                    ),
                    None,
                ),
                "distance": strike - spot,
            },
        )
        for strike in next_state["locked"]["resistance"]
    ]
    locked_supports = [
        candidate_lookup.get(
            strike,
            {
                "strike": strike,
                "score": None,
                "confluence": None,
                "backers": [],
                "gex": next(
                    (
                        _number(row.get("gex"))
                        for row in rows
                        if row["strike"] == strike
                    ),
                    None,
                ),
                "raw_gamma": next(
                    (
                        _number(row.get("raw_gamma"))
                        for row in rows
                        if row["strike"] == strike
                    ),
                    None,
                ),
                "distance": strike - spot,
            },
        )
        for strike in next_state["locked"]["support"]
    ]

    cumulative = _cumulative_levels(rows, spot)
    near_vomma = sum(
        abs(value)
        for row in rows
        if abs(float(row["strike"]) - spot) <= 25.0
        and (value := _number(row.get("vomma"))) is not None
    )
    _append_history(
        next_state,
        "near_vomma",
        near_vomma,
        timestamp,
        max_length=VOMMA_HISTORY_LENGTH,
    )
    vomma = _vomma_status(_history_values(next_state, "near_vomma"))
    gex_monitor = _gex_monitor(
        next_state,
        totals["gex"],
        timestamp,
        directions["vix1d"] == "Up",
        directions["vvix"] == "Up",
    )
    vol_tension = _vol_tension(
        totals["gex"],
        gex_monitor,
        index_values["vix"],
        index_values["vix1d"],
        directions["vix1d"],
        skew,
    )

    vix1d = index_values["vix1d"]
    if vix1d is not None:
        if next_state.get("vix1d_low") is None or vix1d < next_state["vix1d_low"]:
            next_state["vix1d_low"] = vix1d
            next_state["vix1d_low_at"] = timestamp
        if next_state.get("vix1d_high") is None or vix1d > next_state["vix1d_high"]:
            next_state["vix1d_high"] = vix1d
            next_state["vix1d_high_at"] = timestamp
            low = _number(next_state.get("vix1d_low"))
            next_state["vix1d_high_prominence_pct"] = (
                (vix1d - low) / low * 100.0 if low else 0.0
            )
    low = _number(next_state.get("vix1d_low"))
    high = _number(next_state.get("vix1d_high"))
    up_from_low = (vix1d - low) / low * 100.0 if vix1d is not None and low else None
    down_from_high = (
        (high - vix1d) / high * 100.0 if vix1d is not None and high else None
    )
    vol_extremes = {
        "session_low": low,
        "session_high": high,
        "low_at": next_state.get("vix1d_low_at"),
        "high_at": next_state.get("vix1d_high_at"),
        "up_from_low_pct": up_from_low,
        "down_from_high_pct": down_from_high,
        "vol_bottom": bool(
            up_from_low is not None
            and up_from_low >= 10.0
            and directions["vix1d"] == "Up"
        ),
        "vol_top": bool(
            _number(next_state.get("vix1d_high_prominence_pct")) is not None
            and next_state["vix1d_high_prominence_pct"] >= 10.0
            and down_from_high is not None
            and down_from_high >= 10.0
            and directions["vix1d"] == "Down"
        ),
    }

    raw_coverage = sum(
        1 for row in rows if _number(row.get("raw_gamma")) is not None
    )
    profile_cells = len(rows) * len(PROFILE_FIELDS)
    present_profile_cells = sum(
        1
        for row in rows
        for field in PROFILE_FIELDS
        if _number(row.get(field)) is not None
    )
    warnings: list[str] = []
    errors: list[str] = []
    if len(rows) < WINDOW_SIZE:
        warnings.append(f"Strike window contains {len(rows)}/{WINDOW_SIZE} rows")
    if raw_coverage < len(rows):
        warnings.append(
            f"Raw gamma is complete on {raw_coverage}/{len(rows)} strikes"
        )
    missing_indices = [
        name.upper() for name, value in index_values.items() if value is None
    ]
    if missing_indices:
        warnings.append(
            "Observed volatility index values unavailable: " + ", ".join(missing_indices)
        )
    if regime["reference_mode"] != "workbook_static_export":
        warnings.append(
            "Matrix/IV Regime static workbook values are using the documented semantic fallback"
        )
    if source_meta.get("stale"):
        warnings.append("Tastytrade source is older than the configured freshness limit")
    if raw_coverage < 5:
        errors.append("Fewer than five strikes have complete raw gamma inputs")
    if present_profile_cells < min(profile_cells, 5 * len(PROFILE_FIELDS)):
        errors.append("Fewer than five strikes have a complete workbook profile")

    status = "error" if errors else ("degraded" if warnings else "ok")
    quality = (
        "ERROR"
        if errors
        else (
            "COMPLETE"
            if len(rows) == WINDOW_SIZE
            and raw_coverage == len(rows)
            and present_profile_cells == profile_cells
            and not missing_indices
            and regime["reference_mode"] == "workbook_static_export"
            and not source_meta.get("stale")
            else "DEGRADED"
        )
    )

    prev_close = _number(tastytrade_payload.get("prev_close_price"))
    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "generated_at": timestamp,
        "session_date": session_date,
        "source": {
            "tastytrade": {
                **source_meta,
                "source_id": source_id,
                "ticker": tastytrade_payload.get("ticker", "SPX"),
                "expiration": tastytrade_payload.get("expir", "0dte"),
            },
            "indices": index_metadata,
            "formula_authority": {
                "catalog": "MASTER_KING_NODE_RECORD_V5_CATALOGO_COMPLETO_DE_FORMULAS.md",
                "runtime": "live_king_node.py",
                "profile": "King Node Model A:I, 47-strike window",
            },
        },
        "quality": {
            "grade": quality,
            "errors": errors,
            "warnings": warnings,
            "strike_count": len(rows),
            "expected_strike_count": WINDOW_SIZE,
            "raw_gamma_coverage": raw_coverage / len(rows) if rows else 0.0,
            "profile_coverage": (
                present_profile_cells / profile_cells if profile_cells else 0.0
            ),
            "smooth_depth": smooth_depth,
            "reference_mode": regime["reference_mode"],
        },
        "inputs": {
            "spot": spot,
            "previous_close": prev_close,
            "spot_change_pct": (
                (spot - prev_close) / prev_close * 100.0
                if prev_close not in (None, 0)
                else None
            ),
            "dte_hours": dte,
            "vix": index_values["vix"],
            "vvix": index_values["vvix"],
            "vix1d": index_values["vix1d"],
            "atm_iv": atm_iv,
        },
        "directions": directions,
        "regime": regime,
        "totals": totals,
        "levels": {
            "raw_gamma": _node(rows, "raw_gamma", "max"),
            "king_gamma": _node(rows, "gamma_gross", "max"),
            "max_gex": _node(rows, "gex", "max"),
            "min_gex": _node(rows, "gex", "min"),
            "gamma_flip": cumulative["gamma_flip"],
            "zero_gamma": cumulative["zero_gamma"],
            "daemon_zero_gamma": _number(tastytrade_payload.get("zerogamma")),
            "call_walls": _walls(rows, True),
            "put_walls": _walls(rows, False),
            "resistances": locked_resistances,
            "supports": locked_supports,
            "raw_resistances": raw_resistances,
            "raw_supports": raw_supports,
        },
        "monitor": {
            "gex": gex_monitor,
            "vomma": vomma,
            "skew": skew,
            "vol_tension": vol_tension,
            "vix1d_extremes": vol_extremes,
        },
        "rows": rows,
    }
    return snapshot, next_state


__all__ = [
    "KingNodeDataError",
    "SCHEMA_VERSION",
    "WINDOW_SIZE",
    "aggregate_by_strike",
    "build_snapshot",
    "initial_state",
    "rows_from_tastytrade",
    "select_strike_window",
    "two_half_direction",
]
