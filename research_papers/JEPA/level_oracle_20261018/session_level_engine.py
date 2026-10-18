"""Session-aware engine; full sessions delegate to the immutable original.

Short-session bodies retain the original arithmetic and ordering, with an
explicit clock argument at every temporal boundary. No runtime source rewriting,
module-global mutation, market I/O, or fits occur here.
"""

from typing import Mapping
import numpy as np
import pandas as pd

try:
    from . import level_engine as frozen
    from .session_clock import FULL, SessionClock
except ImportError:
    import level_engine as frozen
    from session_clock import FULL, SessionClock

RATIOS = frozen.RATIOS
DELTA_BUCKETS = frozen.DELTA_BUCKETS
FIB, CALL_OI, PUT_OI, CALL_GAMMA, PUT_GAMMA = 1, 2, 4, 8, 16
ACTION_COLUMNS = frozen.ACTION_COLUMNS
LABEL_COLUMNS = frozen.LABEL_COLUMNS
DayData = frozen.DayData
OracleResult = frozen.OracleResult
PolicyResult = frozen.PolicyResult
ib_bounds = frozen.ib_bounds
deduplicate_levels = frozen.deduplicate_levels
known_contract_matrix = frozen.known_contract_matrix
quote_valid = frozen.quote_valid
selected_contracts = frozen.selected_contracts
net_usd = frozen.net_usd
ledger_summary = frozen.ledger_summary


def validate_cache(cache: Mapping, clock: SessionClock = FULL):
    """Structural validation only; source identity/hash checks belong to cache loader."""
    if clock.is_full:
        return frozen.validate_cache(cache)
    times = np.asarray(cache["time_ns"], dtype=np.int64)
    strike = np.asarray(cache["strike"], dtype=np.float64)
    side = np.asarray(cache["right"])
    if times.shape != (clock.n_slots,) or np.any(np.diff(times) != 60_000_000_000):
        raise ValueError(
            f"Expected {clock.n_slots} consecutive one-minute observations"
        )
    if (
        np.any(~np.isfinite(strike))
        or np.any(strike <= 0)
        or np.any(~np.isin(side, [0, 1]))
    ):
        raise ValueError("Invalid contract identity")
    if len(set(zip(strike.tolist(), side.tolist()))) != len(strike):
        raise ValueError("Duplicate normalized contract identity")
    for name in ("bid", "ask", "delta", "iv", "vega", "theta", "row_flags"):
        if np.asarray(cache[name]).shape != (clock.n_slots, len(strike)):
            raise ValueError("Invalid cache shape: " + name)
    for name in ("spot", "spot_valid"):
        if np.asarray(cache[name]).shape != (clock.n_slots,):
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


def available_oi_matrix(cache: Mapping, clock: SessionClock = FULL):
    """Latest reported OI, including invalidating newer reports; never back-fill."""
    if clock.is_full:
        return frozen.available_oi_matrix(cache)
    times = np.asarray(cache["time_ns"], dtype=np.int64)
    result = np.full((clock.n_slots, len(cache["strike"])), np.nan, dtype=np.float64)
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
        if first < clock.n_slots:
            result[first:, contract[row]] = values[row] if good[row] else np.nan
    return result


def bs_gamma_density(cache: Mapping, minute: int, oi_row, clock: SessionClock = FULL):
    """Unsigned BS dollar-gamma proxy, not observed dealer inventory."""
    if clock.is_full:
        return frozen.bs_gamma_density(cache, minute, oi_row)
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
    if not np.isfinite(spot) or spot <= 0 or minute >= clock.close_i:
        return result
    tau = (clock.close_i - minute) * 60 / (365 * 86400)
    sigma = iv[valid]
    d1 = (np.log(spot / strike[valid]) + 0.5 * sigma * sigma * tau) / (
        sigma * np.sqrt(tau)
    )
    gamma = np.exp(-0.5 * d1 * d1) / (np.sqrt(2 * np.pi) * spot * sigma * np.sqrt(tau))
    result[valid] = gamma * oi[valid] * 100 * spot * spot * 0.01
    return result


def causal_levels(cache, oi_row, minute, low, high, band, clock: SessionClock = FULL):
    if clock.is_full:
        return frozen.causal_levels(cache, oi_row, minute, low, high, band)
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
    gamma = bs_gamma_density(cache, minute, oi_row, clock)
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


def build_day(cache: Mapping, metadata=None, clock: SessionClock = FULL):
    """Build only causal objects; never inspect entry/exit quotes or future spot."""
    if clock.is_full:
        return frozen.build_day(cache, metadata)
    validate_cache(cache, clock)
    metadata = dict(metadata or {})
    oi = available_oi_matrix(cache, clock)
    known = known_contract_matrix(cache)
    ib = ib_bounds(cache)
    states, level_rows, actions = [], [], []
    coverage = {
        "scheduled_states": clock.last_state - clock.first_state + 1,
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
    for minute in range(clock.first_state, clock.last_state + 1):
        spot = float(spot_array[minute])
        valid = bool(ib is not None and valid_spot[minute])
        low, high, observed = ib if ib is not None else (np.nan, np.nan, 0)
        width = high - low
        band = max(0.05 * width, 0.0001 * spot) if valid else np.nan
        levels = (
            causal_levels(cache, oi[minute], minute, low, high, band, clock)
            if valid
            else []
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


def exit_trigger(
    spot, spot_valid, state_i, right, target, stop, band, clock: SessionClock = FULL
):
    """Known target remains fixed; intermediate levels never enter this function."""
    if clock.is_full:
        return frozen.exit_trigger(spot, spot_valid, state_i, right, target, stop, band)
    start = int(state_i) + 1
    values = np.asarray(spot, dtype=float)[start : clock.eod_i]
    valid = (
        np.asarray(spot_valid, dtype=bool)[start : clock.eod_i]
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
    return -1, clock.eod_i, "EOD", int((~valid).sum())


def evaluate_actions(cache: Mapping, actions: pd.DataFrame, clock: SessionClock = FULL):
    """Future sidecar. Missing entry is cash/no fill; missing exit is zero liquidation."""
    if clock.is_full:
        return frozen.evaluate_actions(cache, actions)
    validate_cache(cache, clock)
    if (
        len(actions)
        and not actions.state_i.between(clock.first_state, clock.last_state).all()
    ):
        raise ValueError("Action outside session decision range")
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
            geometry_cache[key] = exit_trigger(
                cache["spot"], cache["spot_valid"], *key, clock=clock
            )
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


def joined_actions(actions, labels, clock: SessionClock = FULL):
    if clock.is_full:
        return frozen.joined_actions(actions, labels)
    if (
        len(actions)
        and not actions.state_i.between(clock.first_state, clock.last_state).all()
    ):
        raise ValueError("Action outside session decision range")
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
            & (result.loc[filled, "exit_i"] <= clock.eod_i)
        ).all():
            raise ValueError("Impossible fill chronology")
        if not np.isfinite(result[["net_base", "net_adverse"]].to_numpy(float)).all():
            raise ValueError("Nonfinite reward")
    return result


def solve_oracle(actions, labels, clock: SessionClock = FULL):
    """Base-cost clairvoyant dynamic program; adverse uses the identical trajectory."""
    if clock.is_full:
        return frozen.solve_oracle(actions, labels)
    joined = joined_actions(actions, labels, clock)
    value = np.zeros(clock.eod_i + 2, dtype=np.float64)
    choice = np.full(clock.eod_i + 2, -1, dtype=np.int64)
    groups = {int(i): group for i, group in joined.groupby("state_i", sort=True)}
    for minute in range(clock.last_state, clock.first_state - 1, -1):
        best = value[minute + 1]  # WAIT wins an exact tie.
        for action in groups.get(minute, joined.iloc[:0]).itertuples(index=False):
            if action.status != "FILLED":
                continue
            candidate = float(action.net_base) + value[int(action.exit_i) + 1]
            if candidate > best:
                best, choice[minute] = candidate, int(action.action_id)
        value[minute] = best
    trajectory = []
    minute = clock.first_state
    indexed = joined.set_index("action_id", drop=False)
    while minute <= clock.last_state:
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
            "oracle_base_value": float(value[clock.first_state]),
            "oracle_uses_future": True,
            "adverse_reoptimized": False,
            "offered_actions": len(joined),
            "no_fill_actions": int((joined.status == "NO_FILL").sum()),
        }
    )
    if not np.isclose(summary["net_base"], value[clock.first_state], rtol=0, atol=1e-8):
        raise AssertionError("DP path does not reconstruct value")
    return OracleResult(value, ledger, advantage_frame, summary)


def evaluate_policy(actions, labels, scores, threshold=0.0, clock: SessionClock = FULL):
    """Causal score scheduler on a fixed action universe, preserving no-fill attempts."""
    if clock.is_full:
        return frozen.evaluate_policy(actions, labels, scores, threshold)
    joined = joined_actions(actions, labels, clock)
    scores = np.asarray(scores, dtype=float)
    if scores.shape != (len(actions),):
        raise ValueError("Scores must align with actions row order")
    score_by_id = dict(zip(actions.action_id, scores))
    joined["score"] = joined.action_id.map(score_by_id)
    attempts = []
    next_state = clock.first_state
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
