"""Exact action/state factorization of market_cue_vectors, with bounded cache.

The reference extractor stays unchanged. Cache keys are state position, offered
side and band; every action-dependent output is overwritten from that action.
No filtering, fitting, approximation or change of arithmetic precision.
"""

from __future__ import annotations

import numpy as np

import market_cue_vectors as reference
from market_cues import A, B, extract_market_cues

OFFSETS = {name: index * 2 for index, name in enumerate(reference.VALUE_NAMES)}
GEOMETRY = (
    "target_distance_ib",
    "stop_distance_ib",
    "target_stop_ratio",
    "band_ib",
    "target_rel_spot_ib",
    "stop_rel_spot_ib",
    "strike_rel_spot_ib",
)
SOURCE_FLAGS = tuple(
    f"{which}_source_{name}"
    for which in ("target", "stop")
    for name in ("fib", "call_oi", "put_oi", "call_gamma", "put_gamma")
)
DIRECT_COLUMNS = (
    "is_put",
    *GEOMETRY,
    *SOURCE_FLAGS,
    "ask_over_spot",
    "bid_over_spot",
    "spread_over_premium",
    "delta",
    "iv",
    "vega_over_spot",
    "theta_over_spot",
)


def patch_action(row, base, action):
    """Mirror only the 25 direct action metrics of the frozen reference."""
    action = np.asarray(action, dtype=np.float64)
    geometry_ok = base[B["spot_valid"]] == 1 and base[B["ib_valid"]] == 1

    def emit(name, value, valid):
        offset = OFFSETS[name]
        row[offset : offset + 2] = 0
        if valid and np.isfinite(value):
            if abs(value) > float(np.finfo(np.float32).max):
                raise ValueError("Valid metric is not representable as finite float32")
            row[offset], row[offset + 1] = value, 1

    emit("is_put", action[A["is_put"]], action[A["is_put"]] in (0, 1))
    for name in GEOMETRY:
        emit(
            name,
            action[A[name]],
            geometry_ok
            and (
                action[A["stop_distance_ib"]] > 0
                if name == "target_stop_ratio"
                else True
            ),
        )
    for name in SOURCE_FLAGS:
        emit(name, action[A[name]], geometry_ok)
    quote_ok = (
        action[A["quote_valid"]] == 1 and action[A["ask_over_spot"]] > 0 and geometry_ok
    )
    emit("ask_over_spot", action[A["ask_over_spot"]], quote_ok)
    emit("bid_over_spot", action[A["bid_over_spot"]], quote_ok)
    emit(
        "spread_over_premium",
        action[A["spread_over_spot"]] / action[A["ask_over_spot"]] if quote_ok else 0.0,
        quote_ok,
    )
    for name, flag in (
        ("delta", "delta_valid"),
        ("iv", "iv_valid"),
        ("vega_over_spot", "vega_valid"),
        ("theta_over_spot", "theta_valid"),
    ):
        emit(
            name,
            action[A[name]],
            action[A[flag]] == 1
            and action[A["greek_present"]] == 1
            and (geometry_ok if name.endswith("over_spot") else True),
        )


def vectorize_rows(
    *,
    state_i,
    base,
    tokens,
    token_mask,
    bar_mask,
    bar_end_i,
    action_features,
    action_positions,
    state_positions,
):
    args = dict(
        state_i=state_i,
        base=base,
        tokens=tokens,
        token_mask=token_mask,
        bar_mask=bar_mask,
        bar_end_i=bar_end_i,
        action_features=action_features,
    )
    # Reuse reference structural validation without extracting any row.
    empty = np.empty(0, dtype=np.int64)
    reference.vectorize_rows(**args, action_positions=empty, state_positions=empty)
    ai, si = np.asarray(action_positions), np.asarray(state_positions)
    if (
        ai.ndim != 1
        or si.shape != ai.shape
        or ai.dtype.kind not in "iu"
        or si.dtype.kind not in "iu"
    ):
        raise ValueError("Integer one-dimensional action/state joins required")
    state_i, base, tokens, token_mask, bar_mask, bar_end_i, action_features = (
        np.asarray(value)
        for value in (
            state_i,
            base,
            tokens,
            token_mask,
            bar_mask,
            bar_end_i,
            action_features,
        )
    )
    if (
        np.any(ai < 0)
        or np.any(ai >= len(action_features))
        or np.any(si < 0)
        or np.any(si >= len(state_i))
    ):
        raise ValueError("Action/state join outside arrays")
    if token_mask.ndim == 3:
        token_mask = token_mask[:, :, 0]
    output = np.empty((len(ai), len(reference.COLUMN_NAMES)), dtype=np.float32)
    cache = {}
    for row, (action_index, state_index) in enumerate(zip(ai, si)):
        action = np.asarray(action_features[action_index], dtype=np.float64)
        key = (
            int(state_index),
            float(action[A["is_put"]]),
            float(action[A["band_ib"]]),
        )
        if key not in cache:
            cues = extract_market_cues(
                state_i=int(state_i[state_index]),
                base=base[state_index],
                tokens=tokens[state_index],
                token_mask=token_mask[state_index],
                bar_mask=bar_mask[state_index],
                bar_end_i=bar_end_i[state_index],
                action=action,
            )
            cache[key] = reference.vectorize_cues(cues)
        output[row] = cache[key]
        patch_action(output[row], base[state_index], action)
    return output
