"""Independent level-oracle audit; imports no producer calculation code."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

TICKERS = ("SPXW", "SPY", "QQQ")
FIRST_STATE = 60
LAST_STATE = 375
CLOSE_INDEX = 385
DELTA_BUCKETS = (0.35, 0.50, 0.65)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def close(actual, expected, message, tolerance=1e-8):
    require(
        bool(np.isclose(float(actual), float(expected), rtol=0, atol=tolerance, equal_nan=True)),
        message,
    )


def load_cache(path):
    path = Path(path)
    metadata = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    require(digest(path) == metadata["sha256"], "Cache hash mismatch")
    with np.load(path, allow_pickle=False) as stored:
        arrays = {name: stored[name] for name in stored.files}
    require(set(arrays) == set(metadata["array_schema"]), "Cache array schema keys")
    for name, array in arrays.items():
        descriptor = metadata["array_schema"][name]
        require(list(array.shape) == descriptor["shape"], "Cache shape " + name)
        require(str(array.dtype) == descriptor["dtype"], "Cache dtype " + name)
    require(arrays["time_ns"].shape == (391,), "Cache minute count")
    require(np.all(np.diff(arrays["time_ns"]) == 60_000_000_000), "Cache minute grid")
    return arrays, metadata


def quote_valid(cache, minute, contract):
    bid = float(cache["bid"][minute, contract])
    ask = float(cache["ask"][minute, contract])
    flags = int(cache["row_flags"][minute, contract])
    return bool((flags & 3) == 3 and np.isfinite(bid) and np.isfinite(ask)
                and bid >= 0 and ask > 0 and bid <= ask)


def independent_known_and_oi(cache):
    present = (np.asarray(cache["row_flags"], dtype=np.uint8) & 1) != 0
    known = np.logical_or.accumulate(present, axis=0)
    oi = np.full(present.shape, np.nan, dtype=np.float64)
    times = np.asarray(cache["time_ns"], dtype=np.int64)
    records = sorted(
        zip(cache["oi_available_ns"], cache["oi_contract_idx"],
            cache["oi_value"], cache["oi_valid"], strict=True),
        key=lambda row: (int(row[0]), int(row[1])),
    )
    for available, contract, value, valid in records:
        if int(available) == np.iinfo(np.int64).min:
            continue
        first = int(np.searchsorted(times, int(available), side="left"))
        if first >= len(times):
            continue
        known[first:, int(contract)] = True
        good = bool(valid) and np.isfinite(value) and value >= 0 and value % 1 == 0
        oi[first:, int(contract)] = float(value) if good else np.nan
    return known, oi


def decimal_net(entry_ask, exit_bid, adverse=False):
    slip = Decimal(".02" if adverse else ".01")
    proceeds = max(Decimal(str(exit_bid)) - slip, Decimal(0))
    return float((proceeds - Decimal(str(entry_ask)) - slip) * 100 - Decimal("2.60"))


def canonical_float_net(entry_ask, exit_bid, adverse=False):
    """Rebuild the protocol's binary-float accounting order without producer imports."""
    slip = 0.02 if adverse else 0.01
    proceeds = np.maximum(np.asarray(exit_bid, dtype=float) - slip, 0.0)
    return float((proceeds - np.asarray(entry_ask, dtype=float) - slip) * 100 - 2.60)


def independent_exit(cache, action):
    start = int(action.state_i) + 1
    spot = np.asarray(cache["spot"], dtype=float)[start:CLOSE_INDEX]
    valid = (np.asarray(cache["spot_valid"], dtype=bool)[start:CLOSE_INDEX]
             & np.isfinite(spot) & (spot > 0))
    if int(action.right) == 0:
        target = spot >= float(action.target_center) - float(action.band)
        stop = spot <= float(action.stop_center) + float(action.band)
    else:
        target = spot <= float(action.target_center) + float(action.band)
        stop = spot >= float(action.stop_center) - float(action.band)
    hits = np.flatnonzero(valid & (target | stop))
    if len(hits):
        first = int(hits[0])
        minute = start + first
        return minute, minute + 1, "STOP" if stop[first] else "TARGET", int((~valid[:first + 1]).sum())
    return -1, CLOSE_INDEX, "EOD", int((~valid).sum())


def reconstruct_labels(cache, actions):
    rows = []
    geometry = {}
    accounting = {}
    for action in actions.itertuples(index=False):
        contract = int(action.contract_i)
        entry = int(action.entry_i)
        if not quote_valid(cache, entry, contract):
            rows.append({"action_id": action.action_id, "status": "NO_FILL", "trigger_i": -1,
                         "exit_i": entry, "reason": "NO_FILL", "entry_ask": np.nan,
                         "exit_bid": np.nan, "missing_exit": False,
                         "missing_spot_count": 0, "net_base": 0.0,
                         "net_adverse": 0.0, "hold_minutes": 0})
            continue
        geometry_key = (int(action.state_i), int(action.right), float(action.target_center),
                        float(action.stop_center), float(action.band))
        if geometry_key not in geometry:
            geometry[geometry_key] = independent_exit(cache, action)
        trigger, exit_i, reason, missing_spot = geometry[geometry_key]
        ask = float(cache["ask"][entry, contract])
        missing_exit = not quote_valid(cache, exit_i, contract)
        bid = 0.0 if missing_exit else float(cache["bid"][exit_i, contract])
        price_key = (ask, bid)
        if price_key not in accounting:
            float_base = canonical_float_net(ask, bid)
            float_adverse = canonical_float_net(ask, bid, True)
            require(abs(float_base - decimal_net(ask, bid)) <= 1e-8,
                    "Float/Decimal base accounting")
            require(abs(float_adverse - decimal_net(ask, bid, True)) <= 1e-8,
                    "Float/Decimal adverse accounting")
            accounting[price_key] = (float_base, float_adverse)
        net_base, net_adverse = accounting[price_key]
        rows.append({"action_id": action.action_id, "status": "FILLED",
                     "trigger_i": trigger, "exit_i": exit_i, "reason": reason,
                     "entry_ask": ask, "exit_bid": bid, "missing_exit": missing_exit,
                     "missing_spot_count": missing_spot,
                     "net_base": net_base, "net_adverse": net_adverse,
                     "hold_minutes": exit_i - entry})
    return pd.DataFrame(rows)


def compare_frames(actual, expected, keys, context):
    actual = actual.sort_values(keys).reset_index(drop=True)
    expected = expected.sort_values(keys).reset_index(drop=True)
    require(actual.columns.tolist() == expected.columns.tolist(), context + " columns")
    require(len(actual) == len(expected), context + " row count")
    for column in actual:
        if pd.api.types.is_numeric_dtype(actual[column]):
            require(
                np.allclose(actual[column].to_numpy(float), expected[column].to_numpy(float),
                            rtol=0, atol=1e-8, equal_nan=True),
                f"{context} {column}",
            )
        else:
            require(
                actual[column].fillna("<NA>").equals(expected[column].fillna("<NA>")),
                f"{context} {column}",
            )


def independent_dp(actions, labels):
    joined = actions.merge(labels, on="action_id", validate="one_to_one").sort_values("action_id")
    value = np.zeros(CLOSE_INDEX + 2, dtype=np.float64)
    choice = np.full(CLOSE_INDEX + 2, -1, dtype=np.int64)
    state = joined.state_i.to_numpy(int)
    exit_i = joined.exit_i.to_numpy(int)
    reward = joined.net_base.to_numpy(float)
    filled = joined.status.to_numpy() == "FILLED"
    action_ids = joined.action_id.to_numpy(int)
    groups = {minute: np.flatnonzero(state == minute) for minute in np.unique(state)}
    for minute in range(LAST_STATE, FIRST_STATE - 1, -1):
        best = value[minute + 1]
        for index in groups.get(minute, ()):
            if not filled[index]:
                continue
            candidate = reward[index] + value[exit_i[index] + 1]
            if candidate > best:  # WAIT, then lower action_id, wins exact ties.
                best = candidate
                choice[minute] = action_ids[index]
        value[minute] = best
    id_to_index = {action_id: index for index, action_id in enumerate(action_ids)}
    trajectory = []
    minute = FIRST_STATE
    while minute <= LAST_STATE:
        action_id = int(choice[minute])
        if action_id < 0:
            minute += 1
            continue
        row = joined.iloc[id_to_index[action_id]]
        trajectory.append(row.to_dict())
        minute = int(row.exit_i) + 1
    ledger = pd.DataFrame(trajectory, columns=joined.columns)
    selected = set(ledger.action_id.tolist())
    wait_value = value[state + 1]
    q_value = wait_value.copy()
    q_value[filled] = reward[filled] + value[exit_i[filled] + 1]
    advantages = pd.DataFrame({"action_id": action_ids, "q_value": q_value,
                               "wait_value": wait_value,
                               "dp_advantage": q_value - wait_value,
                               "teacher_selected": np.isin(action_ids, list(selected)),
                               "state_optimal_action": choice[state] == action_ids})
    return value, ledger, advantages


def brute_force_value(actions, labels, minute=FIRST_STATE, last=LAST_STATE):
    """Literal path enumeration for deliberately tiny fixtures."""
    joined = actions.merge(labels, on="action_id", validate="one_to_one")
    require(len(joined) <= 24, "Brute-force fixture is intentionally bounded")
    best = 0.0
    for row in joined.loc[(joined.state_i >= minute) & (joined.state_i <= last)].itertuples(index=False):
        if row.status != "FILLED":
            continue
        candidate = float(row.net_base) + brute_force_value(
            actions.loc[actions.state_i > int(row.exit_i)], labels, int(row.exit_i) + 1, last
        )
        best = max(best, candidate)
    return best


def expected_opposite_stop(centers, spot, band, direction):
    """Use the protocol's exact binary-float operation order at the 2-band boundary."""
    centers = np.asarray(centers, dtype=float)
    possible = centers[direction * (centers - spot) < -2 * band]
    if len(possible) == 0:
        return None
    return min(possible, key=lambda center: (abs(center - spot), center))


def validate_action_geometry(cache, states, levels, actions):
    known, oi = independent_known_and_oi(cache)
    state_indices = states.state_i.to_numpy(dtype=int)
    state_known = known[state_indices]
    state_oi_finite = np.isfinite(oi[state_indices])
    require(np.array_equal(states.known_contract_count.to_numpy(dtype=int),
                           state_known.sum(axis=1)), "Known contract count")
    require(np.array_equal(states.oi_known_count.to_numpy(dtype=int),
                           (state_known & state_oi_finite).sum(axis=1)), "Known OI count")
    require(np.array_equal(states.oi_missing_count.to_numpy(dtype=int),
                           (state_known & ~state_oi_finite).sum(axis=1)),
            "Known OI missing count")
    if actions.empty:
        return 0
    state_fields = states[["state_i", "eligible", "spot", "ib_range", "band",
                           "entry_level_id"]].rename(
        columns={"band": "state_band", "entry_level_id": "state_entry_level_id"}
    )
    joined = actions.merge(state_fields, on="state_i", validate="many_to_one")
    target_levels = levels[["state_i", "level_id", "center", "source_mask"]].rename(
        columns={"level_id": "target_level_id", "center": "known_target_center",
                 "source_mask": "known_target_mask"}
    )
    stop_levels = levels[["state_i", "level_id", "center", "source_mask"]].rename(
        columns={"level_id": "stop_level_id", "center": "known_stop_center",
                 "source_mask": "known_stop_mask"}
    )
    joined = joined.merge(target_levels, on=["state_i", "target_level_id"],
                          validate="many_to_one").merge(
        stop_levels, on=["state_i", "stop_level_id"], validate="many_to_one"
    )
    require(joined.eligible.all(), "Action at ineligible state")
    entry_keys = set(zip(levels.state_i, levels.level_id, strict=True))
    require(all((row.state_i, row.entry_level_id) in entry_keys
                for row in joined[["state_i", "entry_level_id"]].drop_duplicates().itertuples(index=False)),
            "Entry level unavailable at decision")
    require((joined.entry_level_id == joined.state_entry_level_id).all(), "Frozen entry level")
    require(np.allclose(joined.target_center, joined.known_target_center, rtol=0, atol=1e-8),
            "Target center unavailable at decision")
    require(np.allclose(joined.stop_center, joined.known_stop_center, rtol=0, atol=1e-8),
            "Stop center unavailable at decision")
    require((joined.target_source_mask == joined.known_target_mask).all(), "Target source mask")
    require((joined.stop_source_mask == joined.known_stop_mask).all(), "Stop source mask")
    expected_stops = []
    levels_by_state = {
        int(key): frame.center.to_numpy(dtype=float)
        for key, frame in levels.groupby("state_i", sort=False)
    }
    for state_i, spot, band in zip(
        state_indices, states.spot.to_numpy(dtype=float), states.band.to_numpy(dtype=float),
        strict=True,
    ):
        centers = levels_by_state.get(int(state_i), np.empty(0, dtype=float))
        below = expected_opposite_stop(centers, spot, band, 1)
        above = expected_opposite_stop(centers, spot, band, -1)
        if below is not None:
            expected_stops.append({"state_i": state_i, "right": 0,
                                   "expected_stop": below})
        if above is not None:
            expected_stops.append({"state_i": state_i, "right": 1,
                                   "expected_stop": above})
    expected_stops = pd.DataFrame(expected_stops)
    joined = joined.merge(expected_stops, on=["state_i", "right"], validate="many_to_one")
    require(np.allclose(joined.stop_center, joined.expected_stop, rtol=0, atol=1e-8),
            "Stop is not nearest opposite level")
    direction = np.where(joined.right.to_numpy() == 0, 1.0, -1.0)
    distance = direction * (joined.target_center.to_numpy() - joined.spot.to_numpy())
    require(np.all((distance > 2 * joined.band.to_numpy())
                   & (distance <= 3 * joined.ib_range.to_numpy())), "Target geometry")
    require((joined.entry_i == joined.state_i + 1).all(), "Entry chronology")
    require(np.allclose(joined.band, joined.state_band, rtol=0, atol=1e-8), "Frozen band")
    contract = joined.contract_i.to_numpy(int)
    minute = joined.state_i.to_numpy(int)
    require(np.array_equal(np.asarray(cache["right"])[contract], joined.right.to_numpy()),
            "Contract side")
    require(np.allclose(np.asarray(cache["strike"])[contract], joined.strike, rtol=0, atol=1e-8),
            "Contract strike")
    require(np.allclose(np.asarray(cache["delta"])[minute, contract], joined.selected_delta,
                        rtol=0, atol=1e-8), "Selected delta")
    bid = np.asarray(cache["bid"])[minute, contract]
    ask = np.asarray(cache["ask"])[minute, contract]
    flags = np.asarray(cache["row_flags"], dtype=np.uint8)[minute, contract]
    require(np.all(((flags & 3) == 3) & np.isfinite(bid) & np.isfinite(ask)
                   & (bid >= 0) & (ask > 0) & (bid <= ask)), "Decision quote invalid")
    # Reconstruct selected contracts and bucket-to-contract mapping.
    actual_contracts = {}
    selected = actions[["state_i", "right", "contract_i", "delta_bucket"]].drop_duplicates()
    for state_i, side, contract_i, bucket in selected.to_numpy():
        actual_contracts.setdefault((int(state_i), int(side)), set()).add(
            (int(contract_i), float(bucket))
        )
    cache_bid = np.asarray(cache["bid"], dtype=float)
    cache_ask = np.asarray(cache["ask"], dtype=float)
    cache_flags = np.asarray(cache["row_flags"], dtype=np.uint8)
    valid_quotes = (((cache_flags & 3) == 3) & np.isfinite(cache_bid) & np.isfinite(cache_ask)
                    & (cache_bid >= 0) & (cache_ask > 0) & (cache_bid <= cache_ask))
    cache_right = np.asarray(cache["right"])
    cache_delta = np.asarray(cache["delta"], dtype=float)
    cache_strike = np.asarray(cache["strike"], dtype=float)
    for state_i in sorted(actions.state_i.unique()):
        for side in (0, 1):
            actual = actual_contracts.get((int(state_i), side), set())
            if not actual:
                continue
            indices = np.flatnonzero((cache_right == side) & valid_quotes[state_i]
                                     & np.isfinite(cache_delta[state_i])
                                     & (np.abs(cache_delta[state_i]) <= 1))
            expected = []
            seen = set()
            for bucket in DELTA_BUCKETS:
                if len(indices) == 0:
                    break
                chosen = min(indices, key=lambda i: (abs(abs(cache_delta[state_i, i]) - bucket),
                                                     cache_strike[i]))
                if chosen not in seen:
                    expected.append((chosen, bucket))
                    seen.add(chosen)
            require(actual == set(expected), "Selected contract universe")
    return len(actions)


def raw_quote_is_valid(row):
    bid = pd.to_numeric(row.bid, errors="coerce")
    ask = pd.to_numeric(row.ask, errors="coerce")
    return bool(np.isfinite(bid) and np.isfinite(ask)
                and bid >= 0 and ask > 0 and bid <= ask)


def validate_raw_ledger_fills(indexed, cache, ledger):
    checked = 0
    for row in ledger.itertuples(index=False):
        right = "CALL" if row.right == 0 else "PUT"
        entry_time = pd.Timestamp(int(cache["time_ns"][int(row.entry_i)]))
        entry_key = (row.strike, right, entry_time)
        require(entry_key in indexed.index, "Raw entry absent")
        entry = indexed.loc[entry_key]
        require(raw_quote_is_valid(entry), "Raw entry quote invalid")
        close(entry.ask, row.entry_ask, "Raw entry ask")
        exit_time = pd.Timestamp(int(cache["time_ns"][int(row.exit_i)]))
        exit_key = (row.strike, right, exit_time)
        if exit_key not in indexed.index or not raw_quote_is_valid(indexed.loc[exit_key]):
            require(row.missing_exit and row.exit_bid == 0, "Raw missing/invalid exit")
        else:
            require(not row.missing_exit, "Raw exit incorrectly missing")
            close(indexed.loc[exit_key].bid, row.exit_bid, "Raw exit bid")
        checked += 1
    return checked


def raw_clock_and_fill_check(cache, metadata, ticker, date, ledger):
    source_hashes = metadata["source_hashes"]
    greek_paths = [Path(path) for path in source_hashes if path.endswith("_greeks.parquet")]
    oi_paths = [Path(path) for path in source_hashes if path.endswith("_oi.parquet")]
    require(len(greek_paths) == len(oi_paths) == 1, "Raw source mapping")
    for path in greek_paths + oi_paths:
        record = source_hashes[str(path)]
        require(path.stat().st_size == record["bytes"] and digest(path) == record["sha256"],
                "Raw source seal " + str(path))
    greek_path, oi_path = greek_paths[0], oi_paths[0]
    greek_schema = set(pq.read_schema(greek_path).names)
    oi_schema = set(pq.read_schema(oi_path).names)
    greek_clock = "NATIVE_STORED_TIMESTAMP" if "timestamp" in greek_schema else "ASSUMED_UNDERLYING_SNAPSHOT_CLOCK"
    oi_clock = "NATIVE_STORED_TIMESTAMP" if "timestamp" in oi_schema else "ASSUMED_PRIOR_CLOSE_UNVERIFIED_RECEIPT"
    require(metadata["clock_basis"] == greek_clock, "Greek clock metadata")
    require(metadata["oi_clock_basis"] == oi_clock, "OI clock metadata")
    columns = ["symbol", "expiration", "trade_date", "strike", "right", "bid", "ask"]
    columns += (["timestamp", "underlying_timestamp"] if "timestamp" in greek_schema
                else ["underlying_timestamp"])
    raw = pq.read_table(greek_path, columns=columns, use_threads=False).to_pandas()
    if "timestamp" in raw:
        native = pd.to_datetime(raw.timestamp, format="ISO8601", errors="coerce")
        underlying = pd.to_datetime(raw.underlying_timestamp, format="ISO8601", errors="coerce")
        mismatch = int((native != underlying).sum())
        require(mismatch == metadata["counters"]["paired_clock_mismatch_rows"],
                "Paired raw clock mismatch count")
    raw["timestamp"] = pd.to_datetime(raw["timestamp"] if "timestamp" in raw else raw["underlying_timestamp"],
                                      format="ISO8601", errors="coerce")
    raw["right"] = raw.right.astype(str).str.upper().replace({"C": "CALL", "P": "PUT"})
    raw["strike"] = pd.to_numeric(raw.strike, errors="coerce")
    day = pd.Timestamp(date)
    raw = raw.loc[(raw.symbol == ticker)
                  & (pd.to_datetime(raw.expiration.astype(str), format="ISO8601", errors="coerce").dt.normalize() == day)
                  & (pd.to_datetime(raw.trade_date.astype(str), format="ISO8601", errors="coerce").dt.normalize() == day)
                  & (raw.timestamp.dt.normalize() == day)
                  & (raw.timestamp == raw.timestamp.dt.floor("min"))]
    require(not raw.duplicated(["strike", "right", "timestamp"], keep=False).any(), "Raw duplicate fill keys")
    indexed = raw.set_index(["strike", "right", "timestamp"])
    checked = validate_raw_ledger_fills(indexed, cache, ledger)
    return checked, greek_clock, oi_clock


def audit_case(ticker, date, cache_path, engine_dir):
    cache, metadata = load_cache(cache_path)
    engine_dir = Path(engine_dir)
    identity = json.loads((engine_dir / "identity.json").read_text(encoding="utf-8"))
    freeze = json.loads((engine_dir / "causal_freeze.json").read_text(encoding="utf-8"))
    summary = json.loads((engine_dir / "summary.json").read_text(encoding="utf-8"))
    require(digest(engine_dir / "level_engine.py") == identity["engine_sha256"], "Engine snapshot")
    require(digest(engine_dir / "PROTOCOL.md") == identity["protocol_sha256"], "Protocol snapshot")
    require(identity["oracle_uses_future"] is True, "Oracle hindsight disclosure")
    for filename, expected in freeze.items():
        require(digest(engine_dir / filename) == expected, "Causal freeze " + filename)
        require((engine_dir / filename).stat().st_mtime <= (engine_dir / "labels.parquet").stat().st_mtime,
                "Causal artifact postdates labels")
    states = pd.read_parquet(engine_dir / "states.parquet")
    levels = pd.read_parquet(engine_dir / "levels.parquet")
    actions = pd.read_parquet(engine_dir / "actions.parquet")
    labels = pd.read_parquet(engine_dir / "labels.parquet")
    advantages = pd.read_parquet(engine_dir / "advantages.parquet")
    ledger = pd.read_parquet(engine_dir / "oracle_ledger.parquet")
    saved_value = np.load(engine_dir / "oracle_value.npy", allow_pickle=False)
    require(not set(("net_base", "net_adverse", "exit_i", "reason")).intersection(actions),
            "Future field in causal actions")
    require(states.state_i.tolist() == list(range(FIRST_STATE, LAST_STATE + 1)), "State grid")
    contracts_checked = validate_action_geometry(cache, states, levels, actions)
    rebuilt_labels = reconstruct_labels(cache, actions)
    rebuilt_labels = rebuilt_labels[labels.columns]
    compare_frames(rebuilt_labels, labels, ["action_id"], "Labels")
    value, rebuilt_ledger, rebuilt_advantages = independent_dp(actions, rebuilt_labels)
    max_dp_abs_diff = float(np.max(np.abs(value - saved_value)))
    require(np.allclose(value, saved_value, rtol=0, atol=1e-8), "Oracle values")
    compare_frames(rebuilt_ledger, ledger, ["action_id"], "Oracle ledger")
    rebuilt_advantages = rebuilt_advantages[advantages.columns]
    compare_frames(rebuilt_advantages, advantages, ["action_id"], "Oracle advantages")
    close(ledger.net_base.sum() if len(ledger) else 0, summary["oracle"]["net_base"], "Summary base")
    close(ledger.net_adverse.sum() if len(ledger) else 0, summary["oracle"]["net_adverse"], "Summary adverse")
    close(value[FIRST_STATE], summary["oracle"]["oracle_base_value"], "Summary DP value")
    require(summary["oracle"]["adverse_reoptimized"] is False, "Adverse path reoptimized")
    require(summary["no_predictive_profitability_claim"] is True, "Predictive disclaimer")
    raw_checked, greek_clock, oi_clock = raw_clock_and_fill_check(
        cache, metadata, ticker, date, rebuilt_ledger
    )
    return {"ticker": ticker, "date": date, "actions": len(actions),
            "filled_actions": int((labels.status == "FILLED").sum()),
            "no_fill_actions": int((labels.status == "NO_FILL").sum()),
            "oracle_trades": len(ledger), "oracle_net_base": float(ledger.net_base.sum()),
            "oracle_net_adverse_same_path": float(ledger.net_adverse.sum()),
            "contracts_and_targets_checked": contracts_checked,
            "raw_oracle_fills_checked": raw_checked,
            "max_dp_value_abs_difference": max_dp_abs_diff,
            "greek_clock_basis": greek_clock, "oi_clock_basis": oi_clock,
            "missing_exit_oracle_trades": int(ledger.missing_exit.sum()) if len(ledger) else 0,
            "missing_spot_oracle_trades": int((ledger.missing_spot_count > 0).sum()) if len(ledger) else 0}


def resolve_engine_case(root, ticker, date):
    candidates = [root / f"{ticker}_{date}", root / ticker / date, root / ticker]
    found = [path for path in candidates if (path / "summary.json").exists()]
    require(len(found) == 1, f"Cannot resolve engine output for {ticker} {date}")
    return found[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--engine-root", type=Path, required=True)
    parser.add_argument("--date", default="20230103")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    try:
        cases = []
        for ticker in TICKERS:
            cache = args.cache_root / ticker / f"{args.date}.npz"
            cases.append(audit_case(ticker, args.date, cache,
                                    resolve_engine_case(args.engine_root, ticker, args.date)))
        result = {"status": "PASS_INDEPENDENT_LEVEL_ORACLE_PILOT_AUDIT",
                  "cases": cases, "source_hash_mismatch": 0,
                  "independent_dp_and_accounting": True,
                  "synthetic_bruteforce_required": True,
                  "oracle_is_hindsight_upper_bound": True,
                  "causal_learner_profitability_evaluated": False,
                  "live_parity_verified": False, "original_receipt_verified": False,
                  "technical_ready": False, "promotion_approved": False,
                  "audit_script_sha256": digest(Path(__file__)),
                  "finished_at_utc": datetime.now(timezone.utc).isoformat()}
        (args.output / "audit.json").write_text(
            json.dumps(result, indent=2, allow_nan=False), encoding="utf-8"
        )
        print(json.dumps(result), flush=True)
    except Exception as exc:
        (args.output / "audit_failure.json").write_text(
            json.dumps({"status": "AUDIT_FAILED", "error": repr(exc)}, indent=2),
            encoding="utf-8",
        )
        raise


if __name__ == "__main__":
    main()
