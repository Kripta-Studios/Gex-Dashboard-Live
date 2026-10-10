"""Bind validated market observations to the October KING NODE workbook."""

from __future__ import annotations

import math
from datetime import UTC, datetime

import numpy as np
import schedula as sh

from modules.king_node_formula_runtime import Workbook, is_error, scalar
from modules.king_node_kernel_bridge import Kernel, decode, encode
from modules.king_node_live_math import apply_lock, greeks

KNM = "King Node Model"
LE = "Level Engine"


def surface_from_input(normalized):
    """The source script's refresh() exposure equations, using CALL IV for both legs.

    Units are exactly its SCALE=.001, VEGA_PER=.01 and fixed RATE/DIV. Provider
    Greeks are not silently substituted for its Black-Scholes calculations.
    The source expiration convention is explicitly 20:00 UTC (including winter).
    """
    spot = float(normalized.underlying["spot"])
    now = datetime.fromisoformat(normalized.as_of)
    expiry = datetime.fromisoformat(str(normalized.expiration["expiry"])).replace(
        hour=20, tzinfo=UTC
    )
    years = (expiry - now).total_seconds() / (365 * 86400)
    if years <= 0:
        raise ValueError("KING NODE source expiration clock has elapsed")
    pairs = {}
    for option in normalized.option_rows:
        legs = pairs.setdefault(option.strike, {})
        if option.right in legs:
            raise ValueError("Duplicate strike/right in KING NODE input")
        legs[option.right] = option
    rows = []
    for strike, legs in sorted(pairs.items()):
        if set(legs) != {"CALL", "PUT"}:
            raise ValueError("KING NODE requires both option rights at every strike")
        call, put = legs["CALL"], legs["PUT"]
        cg = greeks(spot, strike, years, call.iv, "C")
        pg = greeks(spot, strike, years, call.iv, "P")
        if cg is None or pg is None:
            raise ValueError("Invalid input to source Greek equations")
        coi, poi = call.open_interest, put.open_interest
        total, net, scale = coi + poi, coi - poi, 0.1
        cash_gamma = scale * spot * spot * 0.01
        rows.append(
            {
                "strike": strike,
                "raw_call_gamma": cg["gamma"] * coi,
                "raw_put_gamma": cg["gamma"] * poi,
                "raw_gamma": cg["gamma"] * total,
                "gamma_gross": cg["gamma"] * total * cash_gamma,
                "gex": cg["gamma"] * net * cash_gamma,
                "zomma": cg["zomma"] * net * cash_gamma,
                "dex": (cg["delta"] * coi + pg["delta"] * poi) * scale * spot,
                "vex": cg["vanna"] * net * scale * spot,
                "vomma": cg["vomma"] * 0.01 * total * scale,
                "vega": cg["vega"] * 0.01 * total * scale,
                "speed": cg["speed"] * net * scale * spot * spot * 0.0025,
                "charm": cg["charm"] * coi + pg["charm"] * poi,
                "dgex": cg["speed"] * net * cash_gamma,
                "call_gex": cg["gamma"] * coi * cash_gamma,
                "put_gex": -cg["gamma"] * poi * cash_gamma,
                "call_iv": call.iv,
                "put_iv": put.iv,
                "call_oi": coi,
                "put_oi": poi,
            }
        )
    return rows, years * 365 * 24


def _clean(value):
    value = scalar(value)
    if value is sh.EMPTY or is_error(value):
        return None
    if isinstance(value, np.ndarray):
        raise TypeError("Unexpected array in workbook output")
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _number(value):
    value = _clean(value)
    return (
        value
        if isinstance(value, (int, float)) and not isinstance(value, bool)
        else None
    )


def _pending_decode(records):
    return {(tuple(k) if isinstance(k, list) else k): v for k, v in records}


def _pending_encode(pending):
    return [[list(k) if isinstance(k, tuple) else k, v] for k, v in pending.items()]


def _apply_prox(w, runtime, rows, locked, spot):
    """Source refresh() PROX admission: 10pt entry gap, three misses to clear."""
    held, misses = runtime.get("prox"), runtime.get("prox_misses", 0)
    negative = w.get(KNM, "A8") == "Neg" or _number(w.get(LE, "BG72")) == 1
    distance, gamma_floor, confl_floor = [w.get(LE, c) for c in ("BG7", "BG19", "BG20")]
    records = {
        r["strike"]: {
            c: _number(w.get(LE, f"{c}{i}"))
            for c in ("AM", "AC", "BK", "DH", "CU", "BT")
        }
        for i, r in enumerate(rows, 9)
    }

    def valid(k):
        q = records.get(k)
        return bool(
            q
            and negative
            and k in locked
            and 0 < k - spot <= distance
            and q["AM"] is not None
            and q["AC"] is not None
            and q["AM"] >= confl_floor
            and q["AC"] > gamma_floor
            and q["BK"] != 1
            and q["DH"] != 1
        )

    structural = [
        k for k, q in records.items() if q["BT"] is not None and k > spot and k != held
    ]
    candidates = sorted(k for k, q in records.items() if valid(k) and q["CU"] != 1)
    if held is not None:
        if (
            records.get(held, {}).get("CU") == 1
            or not negative
            or held <= spot
            or held not in locked
        ):
            held, misses = None, 0
        elif not valid(held):
            misses += 1
            if misses >= 3:
                held, misses = None, 0
        else:
            misses = 0
    if (
        candidates
        and structural
        and min(structural) - candidates[0] >= 10
        and (held is None or candidates[0] < held)
    ):
        held, misses = candidates[0], 0
    runtime["prox"], runtime["prox_misses"] = held, misses
    for i, r in enumerate(rows, 9):
        w.set(LE, f"EN{i}", int(r["strike"] == held))


def calculate_workbook(
    reference,
    rows,
    raw_rows,
    spot,
    indices,
    directions,
    state,
    timestamp,
    gex_slope=None,
):
    """Evaluate current formulas with current inputs and explicit persistent state."""
    cells = reference.raw.get("workbook_cells")
    if not cells:
        raise ValueError("The October workbook formula export is required")
    w = Workbook(cells)
    runtime = state.setdefault("workbook", {})
    previous = runtime.get("timestamp")
    advance = previous != timestamp
    # Persist only engine-written values, never formula results or Excel caches.
    for sheet, cell, value in runtime.get("inputs", []):
        w.inputs[sheet, cell] = value
    w.set(KNM, "B4", spot)
    for name, value_cell, dir_cell in [
        ("vix", "B5", "P4"),
        ("vvix", "D5", "P5"),
        ("vix1d", "F5", "P6"),
    ]:
        w.set(KNM, value_cell, indices[name])
        w.set(KNM, dir_cell, directions[name])
    ordered = sorted(rows, key=lambda r: -r["strike"])
    raw = {r["strike"]: r for r in raw_rows}
    fields = ["gamma_gross", "gex", "zomma", "dex", "vex", "vomma", "vega", "speed"]
    for i in range(47):
        r = ordered[i] if i < len(ordered) else None
        for j, field in enumerate(["strike"] + fields):
            w.set(KNM, f"{chr(65 + j)}{29 + i}", None if r is None else r[field])
        for col, field in [("K", "call_oi"), ("L", "put_oi")]:
            w.set(KNM, f"{col}{29 + i}", raw[r["strike"]][field] if r else None)
    for col, field in zip(
        "ABCDEFGH", ["gex", "zomma", "dex", "vex", "vega", "vomma", "speed", "charm"]
    ):
        # Source flags use unsmoothed net exposures (not the rounded ladder).
        total = sum(r[field] for r in raw_rows)
        w.set(KNM, f"{col}8", "Pos" if total >= 0 else "Neg")
    w.set("Master Dashboard", "L5", None)  # no saved manual override
    w.set(LE, "B3", directions["atm_iv"])
    w.set(LE, "HC9", gex_slope)
    w.set(
        LE,
        "C3",
        round(state["current_atm_iv"], 4) if state.get("current_atm_iv") else None,
    )

    now = datetime.fromisoformat(timestamp)
    kernel = Kernel(w, runtime.get("kernel"), now)
    kernel.ns["_locked_R"] = runtime.get("locked", {}).get("resistance", [])
    kernel.ns["_locked_S"] = runtime.get("locked", {}).get("support", [])
    atm = state.get("current_atm_iv")
    v1, lo, hi = indices["vix1d"], state.get("vix1d_low"), state.get("vix1d_high")
    rising = (v1 - lo) / lo * 100 if lo else 0
    falling = (hi - v1) / hi * 100 if hi else 0
    top = (
        state.get("vix1d_high_prominence_pct", 0) >= 10
        and falling >= 10
        and directions["vix1d"] == "Down"
    )
    if top and not runtime.get("vol_top_since"):
        runtime["vol_top_since"] = kernel.ns["et_now"]().strftime("%H:%M")
    w.set(
        KNM,
        "AB13",
        f"VOL BOTTOM — vol RISING, +{rising:.0f}% up off LoD {lo:.2f}"
        if rising >= 10 and directions["vix1d"] == "Up"
        else "",
    )
    w.set(
        KNM,
        "AB14",
        f"▽ VOL TOP — vol FALLING, -{falling:.0f}% down off HoD {hi:.2f}, front-end fading"
        if top
        else f"vol topped out earlier today, from {runtime['vol_top_since']} — not true now"
        if runtime.get("vol_top_since")
        else "",
    )
    if advance:
        runtime["iv_fast_held"] = kernel.call("iv_fast_step", now.timestamp(), atm)
        runtime["iv_top"], runtime["iv_top_high"] = kernel.call(
            "iv_top_step", now.timestamp(), atm
        )
        history = runtime.setdefault("spot_history", [])
        history.append([timestamp, spot])
        del history[:-8]
        velocity, acceleration, ready = kernel.call(
            "move_velocity",
            [v for _, v in history],
            [datetime.fromisoformat(t) for t, _ in history],
            3,
        )
        runtime["spot_direction"] = (
            "Up"
            if ready and velocity > 0.05
            else "Down"
            if ready and velocity < -0.05
            else "Flat"
        )
        runtime["velocity"], runtime["acceleration"] = velocity, acceleration
    w.set(KNM, "P13", runtime.get("spot_direction", "Flat"))
    w.set("GEX Depth", "C68", runtime.get("velocity"))
    w.set("GEX Depth", "C69", runtime.get("acceleration"))
    w.set(LE, "BG80", runtime.get("iv_fast_held"))
    w.set(LE, "BG78", runtime.get("iv_top"))
    w.set(
        LE,
        "BG79",
        round(runtime["iv_top_high"], 4)
        if runtime.get("iv_top_high") is not None
        else None,
    )
    net_gex = sum(r["gex"] for r in rows)
    et = kernel.ns["et_now"]()
    if (
        runtime.get("gex_open5") is None
        and (et.hour, et.minute) >= (9, 35)
        and et.hour < 16
    ):
        runtime["gex_open5"] = net_gex
    w.set(KNM, "AB15", runtime.get("gex_open5"))
    table = [[r["strike"]] + [r[f] for f in fields] for r in ordered]
    if advance:
        sk = kernel.call(
            "skew_monitor",
            {
                r["strike"]: (r["call_iv"], r["put_iv"], r["call_oi"], r["put_oi"])
                for r in raw_rows
            },
            spot,
        )
        runtime["skew_result"] = list(sk[:6])
        runtime["gex_text"] = kernel.call(
            "gex_monitor",
            net_gex,
            now.timestamp(),
            directions["vix1d"] == "Up",
            directions["vvix"] == "Up",
            atm,
        )
        runtime["tension_text"] = kernel.call(
            "vol_tension",
            net_gex,
            indices["vix1d"] / indices["vix"] if indices["vix"] else None,
            directions["vix1d"] == "Up",
        )
        runtime["tape_text"] = kernel.call("tape_line")[0]
        runtime["spot_vol"] = list(
            kernel.call("spot_vol_flags", spot, indices["vix1d"], indices["vix"])
        )
        runtime["squeeze"] = list(
            kernel.call(
                "squeeze_conditions", spot, table, indices["vix"], indices["vix1d"]
            )
        )
        response = kernel.call("open_vol_response", atm, kernel.ns["et_now"]())
        if response is not None:
            runtime["open_vol_response"] = response
    gex_slope = kernel.ns.get("_gex_per15")
    w.set(LE, "HC9", gex_slope)
    w.set(LE, "E3", runtime.get("open_vol_response"))
    w.set(KNM, "AB12", runtime.get("gex_text"))
    w.set(KNM, "AB17", runtime.get("tension_text"))
    # Workbook BG99 reads the spot/term-VIX headline. Populate that dependency
    # from the same source state machine, never from a saved display string.
    w.set("Master Dashboard", "E28", (runtime.get("spot_vol") or [""])[0])
    sk = runtime.get("skew_result", [None] * 6)
    w.set(KNM, "AB16", sk[3])
    w.set(KNM, "P11", sk[4])
    w.set(KNM, "P12", sk[5])
    # Empty engine-held columns deliberately select the workbook's documented raw
    # fallback. They must never inherit a previous file's saved latch values.
    locked = runtime.setdefault("locked", {"resistance": [], "support": []})
    pending = runtime.setdefault("pending", {"resistance": [], "support": []})
    for side, first in [("resistance", 9), ("support", 18)]:
        for i in range(6):
            w.set(
                LE, f"W{first + i}", locked[side][i] if i < len(locked[side]) else None
            )
    table = [[r["strike"]] + [r[f] for f in fields] for r in ordered]
    if advance:
        for name in (
            "_write_oedge",
            "_write_nvanna",
            "_write_cluster_admit",
            "_write_gwall_hold",
            "_write_stack_hold",
        ):
            kernel.call(name)
        kernel.call("_write_spd_hold", table)
        negative = w.get(KNM, "A8") == "Neg" or _number(w.get(LE, "BG72")) == 1
        kernel.call(
            "sand_lock_step",
            kernel.sheets[LE],
            spot,
            negative,
            kernel.ns["et_now"]().date(),
            [w.get(KNM, f"AL{i}") for i in (49, 50, 51)],
        )
        kernel.call("_write_fragile_hold", net_gex)
        for name in ("_write_shape_hold", "_write_peak_hold", "_write_cliff_hold"):
            kernel.call(name)
        kernel.call("_apply_dedge_hold", spot)
    raw_levels = {}
    for side, first in [("resistance", 9), ("support", 18)]:
        raw_levels[side] = [
            v
            for i in range(6)
            if (v := _number(w.get(LE, f"V{first + i}"))) is not None
        ]
    reversal = {
        round(r["strike"])
        for i, r in enumerate(ordered)
        if _number(w.get(LE, f"AN{9 + i}")) == 1
    }
    if advance:
        touches = runtime.setdefault("first_touch", {})
        for i, row in enumerate(ordered, 9):
            item = touches.setdefault(str(row["strike"]), {"in": False, "done": False})
            if not item["done"]:
                if spot >= row["strike"]:
                    item["in"] = True
                elif item["in"] and spot <= row["strike"] - 10:
                    item.update(done=True, **{"in": False})
            w.set(LE, f"EI{i}", int(not item["done"]))
        boxes = {}
        for i, row in enumerate(ordered, 9):
            lo, hi = _number(w.get(LE, f"FB{i}")), _number(w.get(LE, f"FC{i}"))
            boxes[row["strike"]] = int(
                lo is not None
                and hi is not None
                and hi > lo
                and _number(w.get(LE, f"GF{i}")) != 1
            )
        pos = w.get(KNM, "A8") == "Pos" and _number(w.get(LE, "BG72")) != 1
        raw_levels["resistance"], raw_levels["support"] = kernel.call(
            "apply_rs_hysteresis",
            raw_levels["resistance"],
            raw_levels["support"],
            spot,
            float(w.get(LE, "BG9")),
            boxes,
            now=now.timestamp(),
            pos=pos,
            qr=kernel.call("qr_settings", kernel.sheets[LE]),
        )
        for side in ("resistance", "support"):
            locked[side], p = apply_lock(
                locked[side],
                _pending_decode(pending[side]),
                raw_levels[side],
                spot,
                "R" if side == "resistance" else "S",
                thr=float(w.get(LE, "BG9")),
                rev=reversal,
            )
            pending[side] = _pending_encode(p)
        lr, ls, pr, ps = kernel.call(
            "qr_apply",
            locked["resistance"],
            locked["support"],
            _pending_decode(pending["resistance"]),
            _pending_decode(pending["support"]),
        )
        lr, ls = (
            kernel.call("dedup_levels", lr, raw_levels["resistance"]),
            kernel.call("dedup_levels", ls, raw_levels["support"]),
        )
        lr, ls = kernel.call("force_minvex_R", lr, ls, spot)
        lr, ls = kernel.call("force_minvex_S", lr, ls, spot)
        locked.update(resistance=lr, support=ls)
        pending.update(resistance=_pending_encode(pr), support=_pending_encode(ps))
        kernel.ns.update(_locked_R=lr, _locked_S=ls)
    for side, first in [("resistance", 9), ("support", 18)]:
        for i in range(6):
            w.set(
                LE, f"W{first + i}", locked[side][i] if i < len(locked[side]) else None
            )
    if advance:
        node = _number(w.get(KNM, "V23"))
        if runtime.get("min_gex") is None:
            runtime["min_gex"] = node
        else:
            held, pending_node = kernel.call(
                "apply_sw_lock",
                runtime["min_gex"],
                decode(runtime.get("min_gex_pending")),
                node,
            )
            runtime["min_gex"], runtime["min_gex_pending"] = held, encode(pending_node)
    w.set(KNM, "T23", runtime.get("min_gex"))

    if advance:
        kernel.call("_write_oedge")
        kernel.call("_apply_chop_yield", spot)
        for side, raw_col, dest in [
            ("resistance", "CM", "CT"),
            ("support", "CN", "CW"),
        ]:
            enabled = _number(w.get(LE, f"{raw_col}2")) == 1
            edge, far = (
                _number(w.get(LE, f"{raw_col}3")),
                _number(w.get(LE, f"{raw_col}4")),
            )
            offered = (
                (round(edge), round(far), _clean(w.get(LE, f"{raw_col}9")) or "")
                if enabled and edge is not None and far is not None
                else None
            )
            old = decode(runtime.get("shelf_" + side))
            old_pending = decode(runtime.get("shelf_pending_" + side))
            held, p = kernel.call("apply_sw_lock", old, old_pending, offered)
            runtime["shelf_" + side], runtime["shelf_pending_" + side] = (
                encode(held),
                encode(p),
            )
            for index, row in enumerate((3, 4, 9)):
                w.set(LE, f"{dest}{row}", held[index] if held else None)
        hold = int(w.get(LE, "CT12"))
        w.set(
            LE,
            "CT14",
            kernel.call(
                "apply_warn_hysteresis",
                directions["vix1d"] == "Up",
                directions["vvix"] == "Up",
                hold,
            ),
        )
        w.set(
            LE,
            "CT26",
            kernel.call(
                "apply_roll_reclaim",
                spot,
                locked["support"],
                indices["vix1d"],
                indices["vix"],
            ),
        )
        w.set(
            LE,
            "EL7",
            kernel.call(
                "apply_flip_gate_hysteresis", _number(w.get(LE, "EL8")) == 1, hold
            ),
        )
        w.set(
            LE,
            "EQ1",
            kernel.call(
                "apply_box_latch", _number(w.get(LE, "EO2")), spot, w.get(LE, "BG9")
            ),
        )
        fast = runtime.get("iv_fast_held") or directions["atm_iv"].upper()
        pos = w.get(KNM, "A8") == "Pos" and _number(w.get(LE, "BG72")) != 1
        le = kernel.sheets[LE]
        kernel.call("_write_shelf_latch", le)
        kernel.call("_write_grank", le)
        for i in range(9, 56):
            w.set(LE, f"FN{i}", 0)  # qualHold explicitly disabled in supplied replay
        _apply_prox(w, runtime, ordered, locked["resistance"], spot)
        kernel.call("drain_live_step", le, spot, table, w.get(KNM, "A8"))
        latch = decode(runtime.get("vanna_latch")) or set()
        latch_state = decode(runtime.get("vanna_latch_state")) or {}
        vex_by = {round(r["strike"]): r["vex"] for r in ordered}
        dex_by = {round(r["strike"]): r["dex"] for r in ordered}
        rev_by = {
            round(r["strike"]): int(_number(w.get(LE, f"AN{i}")) == 1)
            for i, r in enumerate(ordered, 9)
        }
        walls = {
            round(r["strike"])
            for i, r in enumerate(ordered, 9)
            if _number(w.get(LE, f"JZ{i}")) == 1
        }
        kernel.call(
            "vlatch_step",
            latch,
            latch_state,
            spot,
            locked["resistance"],
            locked["support"],
            vex_by,
            rev_by,
            dex_by,
            fast,
            not pos,
            w.get(LE, "BG94"),
            w.get(LE, "BG94"),
            w.get(LE, "BG9"),
            w.get(LE, "BG100"),
            int(w.get(LE, "BG101")),
            ivtop=runtime.get("iv_top"),
            near_pts=w.get(LE, "BG98"),
            svuv=_clean(w.get(LE, "BG99")),
            callwalls=walls,
        )
        kernel.call("vlatch_write", le, latch)
        runtime["vanna_latch"], runtime["vanna_latch_state"] = (
            encode(latch),
            encode(latch_state),
        )
        kernel.call(
            "gdv_live_step",
            le,
            spot,
            table,
            pos,
            fast,
            runtime.get("iv_top"),
            w.get(LE, "BG98"),
            _clean(w.get(LE, "BG99")),
            locked["resistance"],
            locked["support"],
        )
        kernel.call(
            "vb_live_step",
            le,
            spot,
            table,
            pos,
            fast,
            locked["resistance"],
            locked["support"],
        )
        runtime["kernel"] = kernel.persisted()
    # Only explicitly written cells survive a restart; the workbook's stored
    # numeric values have never entered this execution.
    persist = set(kernel.writes)
    persist.update((LE, f"W{r}") for r in list(range(9, 15)) + list(range(18, 24)))
    persist.update(
        (LE, c)
        for c in [
            "CT3",
            "CT4",
            "CT9",
            "CW3",
            "CW4",
            "CW9",
            "CT14",
            "CT26",
            "EL7",
            "EQ1",
        ]
    )
    persist.update((LE, f"EI{r}") for r in range(9, 56))
    persist.update((LE, f"{col}{r}") for col in ("EN", "FN") for r in range(9, 56))
    previous_inputs = {(s, c): v for s, c, v in runtime.get("inputs", [])}
    previous_inputs.update({key: w.inputs.get(key) for key in persist})
    runtime["inputs"] = [[s, c, v] for (s, c), v in sorted(previous_inputs.items())]

    def value(sheet, cell):
        result = w.get(sheet, cell)
        if is_error(result):
            raise ValueError(f"Workbook output {sheet}!{cell} failed: {result}")
        return _clean(result)

    matrix_key = value(KNM, "J8")
    entry = reference.matrix.get(matrix_key)
    if not entry:
        raise ValueError(f"Workbook Matrix has no exact key: {matrix_key}")
    box_key = value(KNM, "P8")
    regime = {
        **entry,
        "iv_raw": value(KNM, "J5"),
        "iv_box": value(KNM, "L5"),
        "iv_box_method": "workbook_L5_map_first",
        "iv_intensity": value(KNM, "N5"),
        "dte_boost": None,
        "matrix_key": matrix_key,
        "box_key": box_key,
        "box_regime": value(KNM, "P9"),
        "box_iv": value(KNM, "P10"),
        "reference_mode": "verified_static_reference",
        "vix1d_vix_ratio": indices["vix1d"] / indices["vix"]
        if indices["vix"]
        else None,
        "signs": {
            name: value(KNM, f"{col}8")
            for col, name in zip(
                "ABCDEFGH",
                ["gamma", "zomma", "dex", "vex", "vega", "vomma", "speed", "charm"],
            )
        },
        "fragile_positive_gamma": bool(value(LE, "BG72")),
    }
    lookup = {r["strike"]: r for r in rows}

    def level(strike):
        row_index = next(i + 9 for i, r in enumerate(ordered) if r["strike"] == strike)
        source = lookup[strike]
        return {
            "strike": strike,
            "score": value(LE, f"AR{row_index}"),
            "confluence": value(LE, f"AM{row_index}"),
            "backers": [],
            "gex": source["gex"],
            "raw_gamma": source["raw_gamma"],
            "distance": strike - spot,
            "reversal": value(LE, f"AN{row_index}") == 1,
            "unsafe": value(LE, f"HP{row_index}") == 1,
            "unsafe_reasons": value(LE, f"HQ{row_index}"),
            "safe_reasons": value(LE, f"KH{row_index}"),
            "vanna_arrival": value(LE, f"JV{row_index}"),
            "zomma_now": value(LE, f"KE{row_index}"),
            "geometry": value(LE, f"FA{row_index}"),
            "box_low": value(LE, f"FB{row_index}"),
            "box_high": value(LE, f"FC{row_index}"),
            "take_profit": value(LE, f"LM{row_index}"),
            "breakout_risk": value(LE, f"LP{row_index}") == 1,
        }

    levels = {}
    for side, first in [("resistance", 9), ("support", 18)]:
        levels[side + "s"] = [level(k) for k in locked[side] if k in lookup]
        levels["raw_" + side + "s"] = [
            level(k) for k in raw_levels[side] if k in lookup
        ]
        for i, item in enumerate(levels[side + "s"]):
            item["backers"] = str(value(LE, f"C{first + i}") or "").split()

    def node(cell, field):
        strike = _number(w.get(KNM, cell))
        return (
            {"strike": strike, "value": lookup[strike][field]}
            if strike in lookup
            else None
        )

    levels.update(
        king_gamma=node("B23", "gamma_gross"),
        max_gex=node("C23", "gex"),
        min_gex=node("C24", "gex"),
        gamma_flip=value(KNM, "D26"),
        zero_gamma=value(KNM, "D27"),
    )
    for k in ("gamma_flip", "zero_gamma"):
        if not isinstance(levels[k], (int, float)):
            levels[k] = None
    runtime["timestamp"] = timestamp
    if kernel.errors:
        raise ValueError("KING NODE state machine failed: " + "; ".join(kernel.errors))
    return (
        regime,
        levels,
        {
            "release": "2026-10-10",
            "evaluated_cells": len(w.cache),
            "calculation_errors": dict(w.errors),
            "state_machine_errors": kernel.errors,
            "expiration_convention": "source_script_20_UTC",
            "unavailable_inputs": ["ES futures / TPO / VWAP", "option volume flow"],
            "monitors": {
                "gex": {
                    "net_gex": net_gex,
                    "per_15_minutes": gex_slope,
                    "text": runtime.get("gex_text"),
                    "tape": runtime.get("tape_text"),
                    "sign": kernel.ns.get("_gex_sign"),
                    "flip_at_epoch": kernel.ns.get("_gex_flip_t"),
                },
                "skew": {
                    "atm_iv": atm,
                    "put_skew_vol_points": sk[0],
                    "call_skew_vol_points": sk[1],
                    "risk_reversal_vol_points": sk[2],
                    "text": sk[3],
                    "put_text": sk[4],
                    "call_text": sk[5],
                    "baseline_method": "source_script_intraday_baseline",
                    "offset_points": 25.0,
                    **kernel.ns.get("_skew_state", {}),
                    "put_direction": kernel.ns.get("_skew_state", {}).get(
                        "ps_dir", "Flat"
                    ),
                    "call_direction": kernel.ns.get("_skew_state", {}).get(
                        "cs_dir", "Flat"
                    ),
                    "put_steep": kernel.ns.get("_skew_state", {}).get("steep", False),
                },
                "vol_tension": {
                    "text": runtime.get("tension_text"),
                    "label": runtime.get("tension_text"),
                },
                "spot_vol": {"text": (runtime.get("spot_vol") or [""])[0]},
                "squeeze": {
                    "text": (runtime.get("squeeze") or [""])[0],
                    "observation_only": True,
                },
            },
        },
    )
