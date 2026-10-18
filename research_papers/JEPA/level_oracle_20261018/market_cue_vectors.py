"""Fixed compact numeric projection for a future net-return control, no fitting.

Ordinary numbers plus explicit validity only. No narrative tags, memberships,
IDs, outcomes, hard entry gates or fitted transformations enter this schema.
"""

from __future__ import annotations

import hashlib
import json

import numpy as np

from market_cues import VERSION as EXTRACTOR_VERSION, extract_market_cues

VERSION = "CONTINUOUS_MARKET_CUE_VECTOR_V1"
VALUE_NAMES = (
    "is_put",
    "spot_ib",
    "ib_range_over_spot",
    "ib_valid_fraction",
    "minute_fraction",
    "remaining_fraction",
    *(f"directional_change_{lag}m_ib" for lag in (1, 5, 15)),
    "target_distance_ib",
    "stop_distance_ib",
    "target_stop_ratio",
    "band_ib",
    "target_rel_spot_ib",
    "stop_rel_spot_ib",
    "strike_rel_spot_ib",
    *(
        f"{which}_source_{source}"
        for which in ("target", "stop")
        for source in ("fib", "call_oi", "put_oi", "call_gamma", "put_gamma")
    ),
    "ask_over_spot",
    "bid_over_spot",
    "spread_over_premium",
    "delta",
    "iv",
    "vega_over_spot",
    "theta_over_spot",
    *(
        f"{side}_{name}"
        for side in ("call", "put")
        for name in (
            "oi_known_fraction",
            "oi_positive_fraction",
            "quote_valid_fraction",
            "iv_valid_fraction",
            "present_fraction",
            "observed_oi",
            "unsigned_gamma_proxy",
            "oi_top3_observed_concentration",
            "gamma_top3_observed_concentration",
        )
    ),
    "put_share_observed_oi",
    "put_share_observed_gamma",
    "nearest_visible_level_ib",
    "nearest_visible_level_distance_ib",
    "visible_source_types_inside_band",
    *(
        f"last_closed_5m_{field}_minus_current_anchor_ib"
        for field in ("low", "high", "close")
    ),
    "directional_previous_5m_close_change_ib",
    *(
        f"last_closed_{duration}m_{field}"
        for duration in (5, 15)
        for field in ("body_ib", "upper_wick_ib", "lower_wick_ib", "range_ib")
    ),
    *(
        f"{side}_{kind}_current_logmass_minus_closed_{duration}m_meanlog"
        for duration in (5, 15)
        for side in ("call", "put")
        for kind in ("oi", "gamma")
    ),
)
COLUMN_NAMES = tuple(
    name for value in VALUE_NAMES for name in (value, value + "__valid")
)


def schema():
    record = dict(
        version=VERSION,
        extractor_version=EXTRACTOR_VERSION,
        value_names=list(VALUE_NAMES),
        column_names=list(COLUMN_NAMES),
        width=len(COLUMN_NAMES),
        dtype="float32",
        imputation="zero_plus_explicit_validity",
        transforms_fitted=False,
        hard_entry_filters=False,
        target_or_stop_sources="observed_action_categories_not_directional_rules",
        excluded=[
            "rejection_description",
            "acceptance_retest_description",
            "evidence_tags",
            "nearest_visible_source",
            "selected_option_gamma",
            "theta_cash_decay_per_minute",
            "target_stop_net_dollar_ratio",
            "dealer_signed_gamma",
            "historical_top_wall_displacement_ib",
            "oracle_membership",
            "model_membership",
        ],
    )
    record["schema_sha256"] = hashlib.sha256(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return record


def vectorize_cues(cues):
    if (
        cues.get("version") != EXTRACTOR_VERSION
        or cues.get("outcomes_read") is not False
    ):
        raise ValueError("Expected outcome-free frozen extractor result")
    values = np.zeros(len(COLUMN_NAMES), dtype=np.float32)
    for index, name in enumerate(VALUE_NAMES):
        metric = cues["metrics"][name]
        valid = metric["valid"]
        if not isinstance(valid, (bool, np.bool_)):
            raise ValueError("Metric validity must be explicit boolean")
        if valid:
            value = metric["value"]
            if (
                value is None
                or not np.isfinite(value)
                or abs(value) > float(np.finfo(np.float32).max)
            ):
                raise ValueError("Valid metric is not representable as finite float32")
            values[index * 2], values[index * 2 + 1] = value, 1
        elif metric["value"] is not None:
            raise ValueError("Missing metric must remain null before vectorization")
    return values


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
    """Project joined source rows; positions only join, never become predictors.

    Accepts raw mask shape(N,20) or frozen FeatureStore shape(N,20,2), where
    channels are token and bar masks. It checks consistency rather than inferring
    past availability. Callers bind input bytes/action IDs before this pure API.
    """
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
    ai, si = np.asarray(action_positions), np.asarray(state_positions)
    if (
        ai.ndim != 1
        or si.shape != ai.shape
        or ai.dtype.kind not in "iu"
        or si.dtype.kind not in "iu"
    ):
        raise ValueError("Integer one-dimensional action/state joins required")
    if state_i.ndim != 1 or state_i.dtype.kind not in "iu":
        raise ValueError("Integer one-dimensional decision clock required")
    nstates = len(state_i)
    if (
        base.shape != (nstates, 81)
        or tokens.shape != (nstates, 20, 45)
        or bar_mask.shape != (nstates, 20)
        or bar_end_i.shape != (nstates, 20)
    ):
        raise ValueError("State tensor schema mismatch")
    if token_mask.shape == (nstates, 20, 2):
        if not np.array_equal(token_mask[:, :, 1], bar_mask):
            raise ValueError("Stacked bar-mask channel differs")
        token_mask = token_mask[:, :, 0]
    if (
        token_mask.shape != (nstates, 20)
        or action_features.ndim != 2
        or action_features.shape[1] != 33
    ):
        raise ValueError("Action or mask schema mismatch")
    if (
        np.any(ai < 0)
        or np.any(ai >= len(action_features))
        or np.any(si < 0)
        or np.any(si >= nstates)
    ):
        raise ValueError("Action/state join outside arrays")
    output = np.empty((len(ai), len(COLUMN_NAMES)), dtype=np.float32)
    for row, (action_index, state_index) in enumerate(zip(ai, si)):
        cues = extract_market_cues(
            state_i=int(state_i[state_index]),
            base=base[state_index],
            tokens=tokens[state_index],
            token_mask=token_mask[state_index],
            bar_mask=bar_mask[state_index],
            bar_end_i=bar_end_i[state_index],
            action=action_features[action_index],
        )
        output[row] = vectorize_cues(cues)
    return output


def join_action_rows(
    *,
    reference_action_ids,
    reference_state_i,
    pack_action_ids,
    offered_action_ids,
    offered_state_i,
    pack_state_i,
):
    """Verify the semantic action→decision join before extracting any feature.

    Reference rows come from the frozen training sample or the offered inference
    list. Their sample_i/day identity and source hashes remain caller obligations.
    This helper does not infer identity from arbitrary array positions.
    """
    ref, clocks, packed, offered, offer_clocks, states = (
        np.asarray(x)
        for x in (
            reference_action_ids,
            reference_state_i,
            pack_action_ids,
            offered_action_ids,
            offered_state_i,
            pack_state_i,
        )
    )
    if any(
        x.ndim != 1 or x.dtype.kind not in "iu"
        for x in (ref, clocks, packed, offered, offer_clocks, states)
    ):
        raise ValueError("Integer identity and clock arrays required")
    if len(ref) != len(clocks) or len(offered) != len(offer_clocks):
        raise ValueError("Reference/action clock lengths differ")
    if any(len(np.unique(x)) != len(x) for x in (packed, offered, states)):
        raise ValueError("Duplicate source action/state identity")
    if set(packed.tolist()) != set(offered.tolist()):
        raise ValueError("Packed and offered action universes differ")
    pmap = {int(value): index for index, value in enumerate(packed)}
    omap = {int(value): int(clock) for value, clock in zip(offered, offer_clocks)}
    smap = {int(value): index for index, value in enumerate(states)}
    ai, si = [], []
    for ident, minute in zip(ref, clocks):
        if (
            int(ident) not in omap
            or omap[int(ident)] != int(minute)
            or int(minute) not in smap
        ):
            raise ValueError(
                "Reference action/state does not match causal offered action"
            )
        ai.append(pmap[int(ident)])
        si.append(smap[int(minute)])
    return np.asarray(ai, dtype=np.int64), np.asarray(si, dtype=np.int64)
