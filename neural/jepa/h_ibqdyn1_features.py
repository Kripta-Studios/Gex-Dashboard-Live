"""Frozen H-IBQDYN1 tick feature primitives."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

SIDES = ("call", "put")
SIDE_FIELDS = (
    "log_update_count",
    "update_acceleration_10s_vs_prior20s",
    "signed_mid_change_pressure",
    "signed_spread_narrowing_pressure",
    "log_bid_replenishment",
    "log_bid_withdrawal",
    "log_ask_replenishment",
    "log_ask_withdrawal",
)
CROSS_FIELDS = (
    "ibqdyn_call_minus_put_log_update_count",
    "ibqdyn_call_minus_put_signed_mid_change_pressure",
    "ibqdyn_call_minus_put_bid_replenishment_balance",
    "ibqdyn_call_minus_put_ask_withdrawal_balance",
)
ALPHA_FIELDS = tuple(
    f"ibqdyn_{side}_{field}" for side in SIDES for field in SIDE_FIELDS
) + CROSS_FIELDS
MIN_ALPHA_STATES = 20
MIN_ORDERED_PAIRS = 5
RAW_STATE_COLUMNS = (
    "timestamp",
    "bid",
    "ask",
    "bid_size",
    "ask_size",
    "bid_exchange",
    "ask_exchange",
    "bid_condition",
    "ask_condition",
)
ALPHA_STATE_COLUMNS = ("bid", "ask", "bid_size", "ask_size")


def _finite_valid_rows(frame: pd.DataFrame) -> pd.Series:
    quote = frame[["bid", "ask", "bid_size", "ask_size"]].apply(
        pd.to_numeric, errors="coerce"
    )
    exchanges = frame[["bid_exchange", "ask_exchange"]].apply(
        pd.to_numeric, errors="coerce"
    )
    return (
        np.isfinite(quote).all(axis=1)
        & np.isfinite(exchanges).all(axis=1)
        & quote["bid"].gt(0)
        & quote["ask"].ge(quote["bid"])
        & quote["bid_size"].ge(0)
        & quote["ask_size"].ge(0)
    )


def _signed(up: int, down: int) -> float:
    return float((up - down) / (up + down + 1.0))


def right_stats(
    rows: pd.DataFrame, decision_dt: pd.Timestamp, right: str
) -> dict[str, Any]:
    label = str(right).strip().upper()
    if label not in {"CALL", "PUT"}:
        raise ValueError(f"invalid H-IBQDYN1 right: {right}")
    prefix = f"ibqdyn_{label.lower()}"
    missing = sorted(set(RAW_STATE_COLUMNS).difference(rows.columns))
    if missing:
        raise KeyError(f"H-IBQDYN1 tick fields missing: {missing}")
    part = rows[rows["right"].astype(str).str.upper().eq(label)].copy()
    part["timestamp"] = pd.to_datetime(part["timestamp"], errors="coerce")
    part["contract_ordinal"] = pd.to_numeric(
        part["contract_ordinal"], errors="coerce"
    )
    start = pd.Timestamp(decision_dt) - pd.Timedelta(seconds=32)
    split = pd.Timestamp(decision_dt) - pd.Timedelta(seconds=12)
    end = pd.Timestamp(decision_dt) - pd.Timedelta(seconds=2)
    if (
        part["timestamp"].isna().any()
        or part["contract_ordinal"].isna().any()
        or (len(part) and part["timestamp"].lt(start).any())
        or (len(part) and part["timestamp"].ge(end).any())
        or part["contract_ordinal"].duplicated().any()
    ):
        raise AssertionError("H-IBQDYN1 ticks violate guarded clock/ordinal")
    part = part.sort_values("contract_ordinal", kind="stable").reset_index(drop=True)
    raw_rows = len(part)
    raw_dedup = part.drop_duplicates(list(RAW_STATE_COLUMNS), keep="first")
    state = part[list(ALPHA_STATE_COLUMNS)]
    state_changed = state.ne(state.shift()).any(axis=1)
    if len(state_changed):
        state_changed.iloc[0] = True
    alpha = part[state_changed].copy()
    timestamp_counts = part["timestamp"].value_counts(dropna=False)
    collision_rows = int(part["timestamp"].map(timestamp_counts).gt(1).sum())
    valid_rows = _finite_valid_rows(part)
    pairs: list[tuple[pd.Series, pd.Series]] = []
    for position in range(1, len(part)):
        previous = part.iloc[position - 1]
        current = part.iloc[position]
        if (
            timestamp_counts[previous["timestamp"]] == 1
            and timestamp_counts[current["timestamp"]] == 1
            and current["timestamp"] > previous["timestamp"]
            and bool(valid_rows.iloc[position - 1])
            and bool(valid_rows.iloc[position])
        ):
            pairs.append((previous, current))
    quality: dict[str, Any] = {
        f"{prefix}_raw_rows": int(raw_rows),
        f"{prefix}_raw_dedup_rows": int(len(raw_dedup)),
        f"{prefix}_alpha_state_rows": int(len(alpha)),
        f"{prefix}_raw_exact_duplicate_rows": int(raw_rows - len(raw_dedup)),
        f"{prefix}_condition_exchange_only_rows": int(len(raw_dedup) - len(alpha)),
        f"{prefix}_collision_rows": collision_rows,
        f"{prefix}_ordered_pair_count": int(len(pairs)),
    }
    valid = len(alpha) >= MIN_ALPHA_STATES and len(pairs) >= MIN_ORDERED_PAIRS
    quality[f"{prefix}_valid"] = bool(valid)
    empty = {f"{prefix}_{field}": np.nan for field in SIDE_FIELDS}
    internal = {
        f"_{prefix}_bid_increase": 0,
        f"_{prefix}_bid_decrease": 0,
        f"_{prefix}_ask_increase": 0,
        f"_{prefix}_ask_decrease": 0,
    }
    if not valid:
        return {**empty, **quality, **internal}
    mid_up = mid_down = spread_narrow = spread_widen = 0
    bid_increase = bid_decrease = ask_increase = ask_decrease = 0
    for previous, current in pairs:
        previous_mid = (float(previous["bid"]) + float(previous["ask"])) / 2.0
        current_mid = (float(current["bid"]) + float(current["ask"])) / 2.0
        mid_up += int(current_mid > previous_mid)
        mid_down += int(current_mid < previous_mid)
        previous_spread = float(previous["ask"]) - float(previous["bid"])
        current_spread = float(current["ask"]) - float(current["bid"])
        spread_narrow += int(current_spread < previous_spread)
        spread_widen += int(current_spread > previous_spread)
        if (
            previous["bid"] == current["bid"]
            and previous["bid_exchange"] == current["bid_exchange"]
        ):
            bid_increase += int(current["bid_size"] > previous["bid_size"])
            bid_decrease += int(current["bid_size"] < previous["bid_size"])
        if (
            previous["ask"] == current["ask"]
            and previous["ask_exchange"] == current["ask_exchange"]
        ):
            ask_increase += int(current["ask_size"] > previous["ask_size"])
            ask_decrease += int(current["ask_size"] < previous["ask_size"])
    last10 = int(alpha["timestamp"].ge(split).sum())
    prior20 = int(alpha["timestamp"].lt(split).sum())
    features = {
        f"{prefix}_log_update_count": float(np.log1p(len(alpha))),
        f"{prefix}_update_acceleration_10s_vs_prior20s": float(
            np.log((last10 + 1.0) / (prior20 / 2.0 + 1.0))
        ),
        f"{prefix}_signed_mid_change_pressure": _signed(mid_up, mid_down),
        f"{prefix}_signed_spread_narrowing_pressure": _signed(
            spread_narrow, spread_widen
        ),
        f"{prefix}_log_bid_replenishment": float(np.log1p(bid_increase)),
        f"{prefix}_log_bid_withdrawal": float(np.log1p(bid_decrease)),
        f"{prefix}_log_ask_replenishment": float(np.log1p(ask_increase)),
        f"{prefix}_log_ask_withdrawal": float(np.log1p(ask_decrease)),
    }
    internal = {
        f"_{prefix}_bid_increase": bid_increase,
        f"_{prefix}_bid_decrease": bid_decrease,
        f"_{prefix}_ask_increase": ask_increase,
        f"_{prefix}_ask_decrease": ask_decrease,
    }
    return {**features, **quality, **internal}


def event_features(
    call_rows: pd.DataFrame, put_rows: pd.DataFrame, decision_dt: pd.Timestamp
) -> dict[str, Any]:
    call = right_stats(call_rows, decision_dt, "CALL")
    put = right_stats(put_rows, decision_dt, "PUT")
    call_bid_balance = _signed(
        int(call["_ibqdyn_call_bid_increase"]),
        int(call["_ibqdyn_call_bid_decrease"]),
    )
    put_bid_balance = _signed(
        int(put["_ibqdyn_put_bid_increase"]),
        int(put["_ibqdyn_put_bid_decrease"]),
    )
    call_ask_withdrawal = _signed(
        int(call["_ibqdyn_call_ask_decrease"]),
        int(call["_ibqdyn_call_ask_increase"]),
    )
    put_ask_withdrawal = _signed(
        int(put["_ibqdyn_put_ask_decrease"]),
        int(put["_ibqdyn_put_ask_increase"]),
    )
    cross = {
        "ibqdyn_call_minus_put_log_update_count": call[
            "ibqdyn_call_log_update_count"
        ]
        - put["ibqdyn_put_log_update_count"],
        "ibqdyn_call_minus_put_signed_mid_change_pressure": call[
            "ibqdyn_call_signed_mid_change_pressure"
        ]
        - put["ibqdyn_put_signed_mid_change_pressure"],
        "ibqdyn_call_minus_put_bid_replenishment_balance": call_bid_balance
        - put_bid_balance,
        "ibqdyn_call_minus_put_ask_withdrawal_balance": call_ask_withdrawal
        - put_ask_withdrawal,
    }
    clean_call = {key: value for key, value in call.items() if not key.startswith("_")}
    clean_put = {key: value for key, value in put.items() if not key.startswith("_")}
    return {**clean_call, **clean_put, **cross}
