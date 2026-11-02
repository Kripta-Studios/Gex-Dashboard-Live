"""Causal level actions, separately labelled outcomes, and a hindsight DP ceiling.

PROTOCOL.md is authoritative. No fixed holding period, training, or network access.
All array indices are native one-minute NY snapshots: 0=09:30, 385=15:55.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
from typing import Mapping

for _key in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[_key] = "1"

import numpy as np  # noqa: E402 -- native thread limits must precede imports
import pandas as pd  # noqa: E402 -- native thread limits must precede imports

FIRST_STATE = 60
LAST_STATE = 375
CLOSE_INDEX = 385
RATIOS = np.array(
    [-1.0, -0.618, -0.272, 0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.272, 1.618, 2.0]
)
DELTA_BUCKETS = (0.35, 0.50, 0.65)
FIB, CALL_OI, PUT_OI, CALL_GAMMA, PUT_GAMMA = 1, 2, 4, 8, 16
ACTION_COLUMNS = [
    "action_id",
    "state_i",
    "entry_i",
    "contract_i",
    "right",
    "strike",
    "selected_delta",
    "delta_bucket",
    "target_level_id",
    "target_center",
    "target_source_mask",
    "stop_level_id",
    "stop_center",
    "stop_source_mask",
    "band",
    "entry_level_id",
]
LABEL_COLUMNS = [
    "action_id",
    "status",
    "trigger_i",
    "exit_i",
    "reason",
    "entry_ask",
    "exit_bid",
    "missing_exit",
    "missing_spot_count",
    "net_base",
    "net_adverse",
    "hold_minutes",
]


@dataclass
class DayData:
    states: pd.DataFrame
    levels: pd.DataFrame
    actions: pd.DataFrame
    coverage: dict
    metadata: dict


@dataclass
class OracleResult:
    value: np.ndarray
    trajectory: pd.DataFrame
    advantages: pd.DataFrame
    summary: dict


@dataclass
class PolicyResult:
    attempts: pd.DataFrame
    ledger: pd.DataFrame
    summary: dict


def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for part in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def write_json(path, data):
    Path(path).write_text(
        json.dumps(data, indent=2, allow_nan=False, default=str), encoding="utf-8"
    )


def validate_cache(cache: Mapping):
    """Structural validation only; source identity/hash checks belong to cache loader."""
    times = np.asarray(cache["time_ns"], dtype=np.int64)
    strike = np.asarray(cache["strike"], dtype=np.float64)
    side = np.asarray(cache["right"])
    if times.shape != (391,) or np.any(np.diff(times) != 60_000_000_000):
        raise ValueError("Expected 391 consecutive one-minute observations")
    if (
        np.any(~np.isfinite(strike))
        or np.any(strike <= 0)
        or np.any(~np.isin(side, [0, 1]))
    ):
        raise ValueError("Invalid contract identity")
    if len(set(zip(strike.tolist(), side.tolist()))) != len(strike):
        raise ValueError("Duplicate normalized contract identity")
    for name in ("bid", "ask", "delta", "iv", "vega", "theta", "row_flags"):
        if np.asarray(cache[name]).shape != (391, len(strike)):
            raise ValueError("Invalid cache shape: " + name)
    for name in ("spot", "spot_valid"):
        if np.asarray(cache[name]).shape != (391,):
            raise ValueError("Invalid cache shape: " + name)
    lengths = [
        len(cache[name])
        for name in ("oi_contract_idx", "oi_value", "oi_available_ns", "oi_valid")
    ]
    if len(set(lengths)) != 1:
        raise ValueError("Ragged OI arrays differ in length")
    oi_contracts = np.asarray(cache["oi_contract_idx"], dtype=int)
    if np.any((oi_contracts < 0) | (oi_contracts >= len(strike))):
        raise ValueError("OI contract index outside cache")


def available_oi_matrix(cache: Mapping):
    """Latest reported OI, including invalidating newer reports; never back-fill."""
    times = np.asarray(cache["time_ns"], dtype=np.int64)
    result = np.full((391, len(cache["strike"])), np.nan, dtype=np.float64)
    contract = np.asarray(cache["oi_contract_idx"], dtype=int)
    available = np.asarray(cache["oi_available_ns"], dtype=np.int64)
    values = np.asarray(cache["oi_value"], dtype=np.float64)
    good = (
        np.asarray(cache["oi_valid"], dtype=bool)
        & np.isfinite(values)
        & (values >= 0)
        & (values % 1 == 0)
    )
    order = np.lexsort((contract, available))
    for row in order:
        first = int(np.searchsorted(times, available[row], side="left"))
        if first < 391:
            result[first:, contract[row]] = values[row] if good[row] else np.nan
    return result


def known_contract_matrix(cache: Mapping):
    """Causal identity universe; the full-day cache column axis is not observable."""
    present = (np.asarray(cache["row_flags"], dtype=np.uint8) & 1) != 0
    known = np.logical_or.accumulate(present, axis=0)
    times = np.asarray(cache["time_ns"], dtype=np.int64)
    for contract, available in zip(cache["oi_contract_idx"], cache["oi_available_ns"]):
        if int(available) == np.iinfo(np.int64).min:
            continue
        first = int(np.searchsorted(times, available, side="left"))
        if first < len(times):
            known[first:, int(contract)] = True
    return known


def bs_gamma_density(cache: Mapping, minute: int, oi_row):
    """Unsigned BS dollar-gamma proxy, not observed dealer inventory."""
    spot = float(cache["spot"][minute])
    iv = np.asarray(cache["iv"][minute], dtype=np.float64)
    strike = np.asarray(cache["strike"], dtype=np.float64)
    oi = np.asarray(oi_row, dtype=np.float64)
    valid = (
        np.isfinite(iv)
        & (iv > 0)
        & (iv <= 5)
        & np.isfinite(oi)
        & (oi >= 0)
        & ((np.asarray(cache["row_flags"][minute], dtype=np.uint8) & 1) != 0)
    )
    result = np.full(len(strike), np.nan)
    if not np.isfinite(spot) or spot <= 0 or minute >= 390:
        return result
    tau = (390 - minute) * 60 / (365 * 86400)
    sigma = iv[valid]
    d1 = (np.log(spot / strike[valid]) + 0.5 * sigma * sigma * tau) / (
        sigma * np.sqrt(tau)
    )
    gamma = np.exp(-0.5 * d1 * d1) / (np.sqrt(2 * np.pi) * spot * sigma * np.sqrt(tau))
    result[valid] = gamma * oi[valid] * 100 * spot * spot * 0.01
    return result


def ib_bounds(cache):
    spot = np.asarray(cache["spot"], dtype=float)
    valid = np.asarray(cache["spot_valid"], dtype=bool) & np.isfinite(spot) & (spot > 0)
    values = spot[:60][valid[:60]]
    if len(values) < 57:
        return None
    low, high = float(values.min()), float(values.max())
    return (low, high, len(values)) if high > low else None


def deduplicate_levels(raw_levels, band):
    """Bound total cluster diameter by 2b; no transitive neighbor chaining."""
    ordered = sorted(
        raw_levels, key=lambda row: (row["center"], row["source_mask"], row["name"])
    )
    groups = []
    for level in ordered:
        if not groups or level["center"] - groups[-1][0]["center"] > 2 * band:
            groups.append([level])
        else:
            groups[-1].append(level)
    result = []
    for level_id, group in enumerate(groups):
        mask = 0
        for item in group:
            mask |= int(item["source_mask"])
        result.append(
            {
                "level_id": level_id,
                "center": float(np.mean([row["center"] for row in group])),
                "source_mask": mask,
                "n_components": len(group),
                "components_json": json.dumps(
                    group, sort_keys=True, separators=(",", ":")
                ),
            }
        )
    return result


def causal_levels(cache, oi_row, minute, low, high, band):
    width = high - low
    raw = [
        {
            "center": float(low + ratio * width),
            "source_mask": FIB,
            "name": "FIB",
            "ratio": float(ratio),
        }
        for ratio in RATIOS
    ]
    strike = np.asarray(cache["strike"], dtype=float)
    sides = np.asarray(cache["right"])
    gamma = bs_gamma_density(cache, minute, oi_row)
    for side, oi_type, gamma_type in ((0, CALL_OI, CALL_GAMMA), (1, PUT_OI, PUT_GAMMA)):
        for weights, mask, name in (
            (oi_row, oi_type, "OI"),
            (gamma, gamma_type, "BS_GAMMA_PROXY"),
        ):
            weights = np.asarray(weights, dtype=float)
            indices = np.flatnonzero(
                (sides == side) & np.isfinite(weights) & (weights > 0)
            )
            ranking = indices[np.lexsort((strike[indices], -weights[indices]))][:3]
            for ci in ranking:
                raw.append(
                    {
                        "center": float(strike[ci]),
                        "source_mask": mask,
                        "name": ("CALL_" if side == 0 else "PUT_") + name,
                        "contract_i": int(ci),
                        "weight": float(weights[ci]),
                    }
                )
    return deduplicate_levels(raw, band)


def quote_valid(cache, minute, contract):
    bid = np.asarray(cache["bid"])[minute, contract]
    ask = np.asarray(cache["ask"])[minute, contract]
    flags = np.asarray(cache["row_flags"], dtype=np.uint8)[minute, contract]
    return (
        ((flags & 3) == 3)
        & np.isfinite(bid)
        & np.isfinite(ask)
        & (bid >= 0)
        & (ask > 0)
        & (bid <= ask)
    )


def selected_contracts(cache, minute, side):
    delta = np.asarray(cache["delta"][minute], dtype=float)
    strike = np.asarray(cache["strike"], dtype=float)
    indices = np.flatnonzero(
        (np.asarray(cache["right"]) == side)
        & quote_valid(cache, minute, np.arange(len(strike)))
        & np.isfinite(delta)
        & (np.abs(delta) <= 1)
    )
    selected = []
    seen = set()
    for bucket in DELTA_BUCKETS:
        if not len(indices):
            break
        order = np.lexsort((strike[indices], np.abs(np.abs(delta[indices]) - bucket)))
        ci = int(indices[order[0]])
        if ci not in seen:
            selected.append((ci, bucket))
            seen.add(ci)
    return sorted(selected, key=lambda value: (strike[value[0]], value[0]))


def build_day(cache: Mapping, metadata=None):
    """Build only causal objects; never inspect entry/exit quotes or future spot."""
    validate_cache(cache)
    metadata = dict(metadata or {})
    oi = available_oi_matrix(cache)
    known = known_contract_matrix(cache)
    ib = ib_bounds(cache)
    states, level_rows, actions = [], [], []
    coverage = {
        "scheduled_states": LAST_STATE - FIRST_STATE + 1,
        "invalid_ib": ib is None,
        "invalid_spot_states": 0,
        "eligible_states": 0,
        "no_stop_sides": 0,
        "no_contract_sides": 0,
        "causal_actions": 0,
    }
    spot_array = np.asarray(cache["spot"], dtype=float)
    valid_spot = (
        np.asarray(cache["spot_valid"], dtype=bool)
        & np.isfinite(spot_array)
        & (spot_array > 0)
    )
    for minute in range(FIRST_STATE, LAST_STATE + 1):
        spot = float(spot_array[minute])
        valid = bool(ib is not None and valid_spot[minute])
        low, high, observed = ib if ib is not None else (np.nan, np.nan, 0)
        width = high - low
        band = max(0.05 * width, 0.0001 * spot) if valid else np.nan
        levels = (
            causal_levels(cache, oi[minute], minute, low, high, band) if valid else []
        )
        near = [level for level in levels if abs(level["center"] - spot) <= band]
        near.sort(key=lambda level: (abs(level["center"] - spot), level["center"]))
        entry_id = near[0]["level_id"] if near else -1
        states.append(
            {
                "state_i": minute,
                "state_valid": valid,
                "spot": spot,
                "ib_low": low,
                "ib_high": high,
                "ib_range": width,
                "ib_observed": observed,
                "band": band,
                "eligible": bool(near),
                "entry_level_id": entry_id,
                "n_levels": len(levels),
                "known_contract_count": int(known[minute].sum()),
                "oi_known_count": int((known[minute] & np.isfinite(oi[minute])).sum()),
                "oi_missing_count": int(
                    (known[minute] & ~np.isfinite(oi[minute])).sum()
                ),
            }
        )
        for level in levels:
            level_rows.append({"state_i": minute, **level})
        if not valid_spot[minute]:
            coverage["invalid_spot_states"] += 1
        if not near:
            continue
        coverage["eligible_states"] += 1
        for side in (0, 1):
            direction = 1 if side == 0 else -1
            targets = [
                level
                for level in levels
                if 2 * band < direction * (level["center"] - spot) <= 3 * width
            ]
            stops = [
                level
                for level in levels
                if direction * (level["center"] - spot) < -2 * band
            ]
            if not stops:
                coverage["no_stop_sides"] += 1
                continue
            stop = min(
                stops, key=lambda level: (abs(level["center"] - spot), level["center"])
            )
            contracts = selected_contracts(cache, minute, side)
            if not contracts:
                coverage["no_contract_sides"] += 1
            for ci, bucket in contracts:
                for target in targets:
                    actions.append(
                        {
                            "action_id": len(actions),
                            "state_i": minute,
                            "entry_i": minute + 1,
                            "contract_i": ci,
                            "right": side,
                            "strike": float(cache["strike"][ci]),
                            "selected_delta": float(cache["delta"][minute, ci]),
                            "delta_bucket": bucket,
                            "target_level_id": target["level_id"],
                            "target_center": target["center"],
                            "target_source_mask": target["source_mask"],
                            "stop_level_id": stop["level_id"],
                            "stop_center": stop["center"],
                            "stop_source_mask": stop["source_mask"],
                            "band": band,
                            "entry_level_id": entry_id,
                        }
                    )
    coverage["causal_actions"] = len(actions)
    coverage["eligible_fraction"] = (
        coverage["eligible_states"] / coverage["scheduled_states"]
    )
    actions = pd.DataFrame(actions, columns=ACTION_COLUMNS)
    if len(actions):
        for column in ("action_id", "contract_i"):
            actions[column] = actions[column].astype(np.int32)
        for column in (
            "state_i",
            "entry_i",
            "target_level_id",
            "stop_level_id",
            "entry_level_id",
        ):
            actions[column] = actions[column].astype(np.int16)
        for column in ("right", "target_source_mask", "stop_source_mask"):
            actions[column] = actions[column].astype(np.int8)
    levels = pd.DataFrame(
        level_rows,
        columns=[
            "state_i",
            "level_id",
            "center",
            "source_mask",
            "n_components",
            "components_json",
        ],
    )
    return DayData(pd.DataFrame(states), levels, actions, coverage, metadata)


def exit_trigger(spot, spot_valid, state_i, right, target, stop, band):
    """Known target remains fixed; intermediate levels never enter this function."""
    start = int(state_i) + 1
    values = np.asarray(spot, dtype=float)[start:CLOSE_INDEX]
    valid = (
        np.asarray(spot_valid, dtype=bool)[start:CLOSE_INDEX]
        & np.isfinite(values)
        & (values > 0)
    )
    if right == 0:
        target_hit, stop_hit = values >= target - band, values <= stop + band
    else:
        target_hit, stop_hit = values <= target + band, values >= stop - band
    hits = np.flatnonzero(valid & (target_hit | stop_hit))
    if len(hits):
        first = int(hits[0])
        trigger = start + first
        return (
            trigger,
            trigger + 1,
            ("STOP" if stop_hit[first] else "TARGET"),
            int((~valid[: first + 1]).sum()),
        )
    return -1, CLOSE_INDEX, "EOD", int((~valid).sum())


def net_usd(entry_ask, exit_bid, slip=0.01):
    return (
        np.maximum(np.asarray(exit_bid, dtype=float) - slip, 0.0)
        - np.asarray(entry_ask, dtype=float)
        - slip
    ) * 100 - 2.60


def evaluate_actions(cache: Mapping, actions: pd.DataFrame):
    """Future sidecar. Missing entry is cash/no fill; missing exit is zero liquidation."""
    rows, geometry_cache = [], {}
    for action in actions.itertuples(index=False):
        ci, entry = int(action.contract_i), int(action.entry_i)
        if not bool(quote_valid(cache, entry, ci)):
            rows.append(
                {
                    "action_id": action.action_id,
                    "status": "NO_FILL",
                    "trigger_i": -1,
                    "exit_i": entry,
                    "reason": "NO_FILL",
                    "entry_ask": np.nan,
                    "exit_bid": np.nan,
                    "missing_exit": False,
                    "missing_spot_count": 0,
                    "net_base": 0.0,
                    "net_adverse": 0.0,
                    "hold_minutes": 0,
                }
            )
            continue
        key = (
            int(action.state_i),
            int(action.right),
            float(action.target_center),
            float(action.stop_center),
            float(action.band),
        )
        if key not in geometry_cache:
            geometry_cache[key] = exit_trigger(cache["spot"], cache["spot_valid"], *key)
        trigger, exit_i, reason, missing_spot = geometry_cache[key]
        ask = float(cache["ask"][entry, ci])
        missing_exit = not bool(quote_valid(cache, exit_i, ci))
        bid = 0.0 if missing_exit else float(cache["bid"][exit_i, ci])
        rows.append(
            {
                "action_id": action.action_id,
                "status": "FILLED",
                "trigger_i": trigger,
                "exit_i": exit_i,
                "reason": reason,
                "entry_ask": ask,
                "exit_bid": bid,
                "missing_exit": missing_exit,
                "missing_spot_count": missing_spot,
                "net_base": float(net_usd(ask, bid)),
                "net_adverse": float(net_usd(ask, bid, 0.02)),
                "hold_minutes": exit_i - entry,
            }
        )
    return pd.DataFrame(rows, columns=LABEL_COLUMNS)


def joined_actions(actions, labels):
    if actions.action_id.duplicated().any() or labels.action_id.duplicated().any():
        raise ValueError("Duplicate action IDs")
    if set(actions.action_id) != set(labels.action_id):
        raise ValueError("Action/label universe mismatch")
    result = actions.merge(
        labels, on="action_id", how="left", validate="one_to_one"
    ).sort_values("action_id")
    if len(result):
        if not result.status.isin(["FILLED", "NO_FILL"]).all():
            raise ValueError("Unknown label status")
        filled = result.status == "FILLED"
        if not (
            (result.loc[filled, "exit_i"] >= result.loc[filled, "state_i"] + 2)
            & (result.loc[filled, "exit_i"] <= CLOSE_INDEX)
        ).all():
            raise ValueError("Impossible fill chronology")
        if not np.isfinite(result[["net_base", "net_adverse"]].to_numpy(float)).all():
            raise ValueError("Nonfinite reward")
    return result


def ledger_summary(ledger):
    out = {"trades": len(ledger)}
    for column in ("net_base", "net_adverse"):
        values = ledger[column].to_numpy(float) if len(ledger) else np.array([], float)
        losses = float(-values[values < 0].sum())
        out[column] = float(values.sum())
        out[column + "_pf"] = (
            float(values[values > 0].sum()) / losses if losses > 0 else None
        )
        out[column + "_win_rate"] = float(np.mean(values > 0)) if len(values) else None
    if len(ledger):
        out["missing_exit_trades"] = (
            int(ledger.missing_exit.sum()) if "missing_exit" in ledger else 0
        )
        out["missing_spot_trades"] = (
            int((ledger.missing_spot_count > 0).sum())
            if "missing_spot_count" in ledger
            else 0
        )
    return out


def solve_oracle(actions, labels):
    """Base-cost clairvoyant dynamic program; adverse uses the identical trajectory."""
    joined = joined_actions(actions, labels)
    value = np.zeros(CLOSE_INDEX + 2, dtype=np.float64)
    choice = np.full(CLOSE_INDEX + 2, -1, dtype=np.int64)
    groups = {int(i): group for i, group in joined.groupby("state_i", sort=True)}
    for minute in range(LAST_STATE, FIRST_STATE - 1, -1):
        best = value[minute + 1]  # WAIT wins an exact tie.
        for action in groups.get(minute, joined.iloc[:0]).itertuples(index=False):
            if action.status != "FILLED":
                continue
            candidate = float(action.net_base) + value[int(action.exit_i) + 1]
            if candidate > best:
                best, choice[minute] = candidate, int(action.action_id)
        value[minute] = best
    trajectory = []
    minute = FIRST_STATE
    indexed = joined.set_index("action_id", drop=False)
    while minute <= LAST_STATE:
        action_id = int(choice[minute])
        if action_id < 0:
            minute += 1
            continue
        row = indexed.loc[action_id]
        trajectory.append(row.to_dict())
        minute = int(row.exit_i) + 1
    ledger = pd.DataFrame(trajectory, columns=joined.columns)
    selected = set(ledger.action_id.tolist())
    advantages = []
    for action in joined.itertuples(index=False):
        wait = float(value[int(action.state_i) + 1])
        q = (
            wait
            if action.status != "FILLED"
            else float(action.net_base) + float(value[int(action.exit_i) + 1])
        )
        advantages.append(
            {
                "action_id": action.action_id,
                "q_value": q,
                "wait_value": wait,
                "dp_advantage": q - wait,
                "teacher_selected": action.action_id in selected,
                "state_optimal_action": int(choice[int(action.state_i)])
                == action.action_id,
            }
        )
    advantage_frame = pd.DataFrame(
        advantages,
        columns=[
            "action_id",
            "q_value",
            "wait_value",
            "dp_advantage",
            "teacher_selected",
            "state_optimal_action",
        ],
    )
    summary = ledger_summary(ledger)
    summary.update(
        {
            "oracle_base_value": float(value[FIRST_STATE]),
            "oracle_uses_future": True,
            "adverse_reoptimized": False,
            "offered_actions": len(joined),
            "no_fill_actions": int((joined.status == "NO_FILL").sum()),
        }
    )
    if not np.isclose(summary["net_base"], value[FIRST_STATE], rtol=0, atol=1e-8):
        raise AssertionError("DP path does not reconstruct value")
    return OracleResult(value, ledger, advantage_frame, summary)


def evaluate_policy(actions, labels, scores, threshold=0.0):
    """Causal score scheduler on a fixed action universe, preserving no-fill attempts."""
    joined = joined_actions(actions, labels)
    scores = np.asarray(scores, dtype=float)
    if scores.shape != (len(actions),):
        raise ValueError("Scores must align with actions row order")
    score_by_id = dict(zip(actions.action_id, scores))
    joined["score"] = joined.action_id.map(score_by_id)
    attempts = []
    next_state = FIRST_STATE
    for minute, group in joined.groupby("state_i", sort=True):
        if minute < next_state:
            continue
        ranked = group.loc[
            np.isfinite(group.score) & (group.score > threshold)
        ].sort_values(["score", "action_id"], ascending=[False, True], kind="stable")
        if ranked.empty:
            continue
        row = ranked.iloc[0]
        attempts.append(row.to_dict())
        next_state = int(row.exit_i) + 1 if row.status == "FILLED" else int(minute) + 1
    attempt_frame = pd.DataFrame(attempts, columns=joined.columns)
    ledger = attempt_frame.loc[attempt_frame.status == "FILLED"].copy()
    summary = ledger_summary(ledger)
    summary["attempts"] = len(attempt_frame)
    summary["no_fill_attempts"] = int((attempt_frame.status == "NO_FILL").sum())
    return PolicyResult(attempt_frame, ledger, summary)


def run_day(cache, metadata, output_dir):
    """Persist causal objects before constructing their future sidecar; never overwrite."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=False)
    protocol = Path(__file__).with_name("PROTOCOL.md")
    shutil.copy2(__file__, out / "level_engine.py")
    shutil.copy2(protocol, out / "PROTOCOL.md")
    identity = {
        "engine_sha256": file_sha(__file__),
        "protocol_sha256": file_sha(protocol),
        "metadata": metadata,
        "status": "CAUSAL_BUILD_STARTED",
        "oracle_uses_future": True,
    }
    write_json(out / "identity.json", identity)
    data = build_day(cache, metadata)
    for name, frame in (
        ("states", data.states),
        ("levels", data.levels),
        ("actions", data.actions),
    ):
        frame.to_parquet(out / f"{name}.parquet", index=False)
    write_json(
        out / "causal_freeze.json",
        {
            name: file_sha(out / name)
            for name in ("states.parquet", "levels.parquet", "actions.parquet")
        },
    )
    labels = evaluate_actions(cache, data.actions)
    labels.to_parquet(out / "labels.parquet", index=False)
    oracle = solve_oracle(data.actions, labels)
    oracle.advantages.to_parquet(out / "advantages.parquet", index=False)
    oracle.trajectory.to_parquet(out / "oracle_ledger.parquet", index=False)
    np.save(out / "oracle_value.npy", oracle.value, allow_pickle=False)
    summary = {
        "status": "COMPLETED_HINDSIGHT_ORACLE_DAY",
        "coverage": data.coverage,
        "oracle": oracle.summary,
        "artifact_hashes": {p.name: file_sha(p) for p in out.glob("*.parquet")},
        "no_predictive_profitability_claim": True,
    }
    write_json(out / "summary.json", summary)
    return summary


def load_cache_module():
    path = Path(__file__).with_name("build_cache.py")
    spec = importlib.util.spec_from_file_location("level_source_cache", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = load_cache_module()
    cache = source.load_day_cache(args.cache)
    metadata = source.read_day_metadata(args.cache)
    print(json.dumps(run_day(cache, metadata, args.output), indent=2))


if __name__ == "__main__":
    main()
