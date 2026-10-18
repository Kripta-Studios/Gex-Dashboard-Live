"""Descriptive pre-entry evidence from the existing causal feature vectors only.

No labels, raw reconstruction, oracle membership, trade outcomes or fitting.
Definitions and limitations: MARKET_CUE_ORACLE_DESIGN.md.
"""

from __future__ import annotations

import numpy as np

from features import BASE_NAMES, TOKEN_NAMES, ACTION_NAMES

VERSION = "MARKET_CUES_V1"
RATIOS = np.array(
    [-1.0, -0.618, -0.272, 0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.272, 1.618, 2.0]
)
B = {name: index for index, name in enumerate(BASE_NAMES)}
T = {name: index for index, name in enumerate(TOKEN_NAMES)}
A = {name: index for index, name in enumerate(ACTION_NAMES)}


def extract_market_cues(
    *, state_i, base, tokens, token_mask, bar_mask, bar_end_i, action
):
    """Return JSON-safe metrics with explicit validity, and descriptive evidence tags.

    Inputs describe ONE decision and ONE offered action, not a realized trade.
    Option Greeks keep their stored units. All direction tags are relative to
    the offered CALL/PUT, and are not recommended actions or causal explanations.
    """
    base, tokens, action = (np.asarray(x, dtype=float) for x in (base, tokens, action))
    token_mask, bar_mask, ends = (
        np.asarray(x) for x in (token_mask, bar_mask, bar_end_i)
    )
    if base.shape != (81,) or tokens.shape != (20, 45) or action.shape != (33,):
        raise ValueError("Expected frozen B81/T20x45/A33 feature schema")
    if any(x.shape != (20,) for x in (token_mask, bar_mask, ends)):
        raise ValueError("Expected twenty token masks/end indices")
    if not isinstance(state_i, (int, np.integer)) or not 60 <= state_i <= 375:
        raise ValueError("Invalid decision minute")
    metrics, tags = {}, []

    def emit(name, value=None, valid=True, reason="MISSING_OR_INVALID_INPUT"):
        good = bool(valid and value is not None and np.isfinite(value))
        metrics[name] = dict(
            value=float(value) if good else None,
            valid=good,
            missing_reason=None if good else reason,
        )
        return float(value) if good else None

    def b(name):
        return base[B[name]]

    def a(name):
        return action[A[name]]

    def good_metric(name):
        return metrics[name]["value"]

    geometry_ok = b("spot_valid") == 1 and b("ib_valid") == 1
    side_ok = a("is_put") in (0, 1)
    direction = 1 - 2 * a("is_put") if side_ok else np.nan
    emit("is_put", a("is_put"), side_ok)
    for name in (
        "spot_ib",
        "ib_range_over_spot",
        "ib_valid_fraction",
        "minute_fraction",
        "remaining_fraction",
    ):
        emit(name, b(name), geometry_ok)
    for lag in (1, 5, 15):
        emit(
            f"directional_change_{lag}m_ib",
            direction * b(f"change_{lag}m_ib"),
            geometry_ok and side_ok and b(f"change_{lag}m_valid") == 1,
        )
    for name in (
        "target_distance_ib",
        "stop_distance_ib",
        "target_stop_ratio",
        "band_ib",
        "target_rel_spot_ib",
        "stop_rel_spot_ib",
        "strike_rel_spot_ib",
    ):
        emit(
            name,
            a(name),
            geometry_ok
            and (a("stop_distance_ib") > 0 if name == "target_stop_ratio" else True),
        )
    for which in ("target", "stop"):
        for source in ("fib", "call_oi", "put_oi", "call_gamma", "put_gamma"):
            emit(f"{which}_source_{source}", a(f"{which}_source_{source}"), geometry_ok)
    quote_ok = a("quote_valid") == 1 and a("ask_over_spot") > 0 and geometry_ok
    emit("ask_over_spot", a("ask_over_spot"), quote_ok)
    emit("bid_over_spot", a("bid_over_spot"), quote_ok)
    emit(
        "spread_over_premium",
        a("spread_over_spot") / a("ask_over_spot") if quote_ok else None,
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
            a(name),
            a(flag) == 1
            and a("greek_present") == 1
            and (geometry_ok if name.endswith("over_spot") else True),
        )
    emit("selected_option_gamma", reason="NOT_STORED_IN_ACTION_FEATURES")
    emit("theta_cash_decay_per_minute", reason="THETA_TIME_UNIT_NOT_VERIFIED")
    emit("target_stop_net_dollar_ratio", reason="SPOT_DISTANCE_RATIO_IS_NOT_OPTION_PNL")
    emit("dealer_signed_gamma", reason="POSITION_SIDE_AND_DEALER_INVENTORY_UNOBSERVED")

    # Log zero is a genuine OI zero ONLY if at least one OI identity is known.
    for side in ("call", "put"):
        for field in (
            "oi_known_fraction",
            "oi_positive_fraction",
            "quote_valid_fraction",
            "iv_valid_fraction",
            "present_fraction",
        ):
            emit(f"{side}_{field}", b(f"current_{side}_{field}"))
        known = b(f"current_{side}_oi_known_fraction")
        oi_log = b(f"current_{side}_oi_logsum")
        gamma_log = b(f"current_{side}_gamma_logsum")
        emit(
            f"{side}_observed_oi",
            np.expm1(oi_log) if 0 <= oi_log < 700 else None,
            known > 0,
            "NO_KNOWN_OI_IDENTITIES",
        )
        # Marginal IV/OI masks cannot prove their intersection. Positive mass is
        # identifiable; zero was also used as the missing-value placeholder.
        emit(
            f"{side}_unsigned_gamma_proxy",
            np.expm1(gamma_log) if 0 < gamma_log < 700 else None,
            gamma_log > 0 and known > 0 and geometry_ok,
            "ZERO_OR_MISSING_GAMMA_NOT_IDENTIFIABLE",
        )
        if 0 < known < 1:
            tags.append(side.upper() + "_OI_PARTIAL_KNOWN_UNIVERSE")
        for kind, total_name in (
            ("oi", f"{side}_observed_oi"),
            ("gamma", f"{side}_unsigned_gamma_proxy"),
        ):
            masses = []
            for rank in (1, 2, 3):
                stem = f"{side}_{kind}_top{rank}_"
                if b(stem + "valid") == 1 and 0 < b(stem + "log_mass") < 700:
                    masses.append(np.expm1(b(stem + "log_mass")))
            total = good_metric(total_name)
            emit(
                f"{side}_{kind}_top3_observed_concentration",
                sum(masses) / total
                if total is not None and total > 0 and masses
                else None,
                reason="NO_POSITIVE_IDENTIFIABLE_MASS",
            )
    for kind, suffix in (("oi", "observed_oi"), ("gamma", "unsigned_gamma_proxy")):
        call, put = (good_metric(side + "_" + suffix) for side in ("call", "put"))
        emit(
            f"put_share_observed_{kind}",
            put / (call + put)
            if call is not None and put is not None and call + put > 0
            else None,
            reason="BOTH_OBSERVED_SIDES_WITH_POSITIVE_TOTAL_REQUIRED",
        )

    # Visible-level diagnostics are not reconstruction of the engine's clusters.
    # All thirteen fixed Fib values are known; wall channels expose only top three.
    spot, band = b("spot_ib"), a("band_ib")
    levels = [(float(value), "fib") for value in RATIOS]
    for channel in ("call_oi", "put_oi", "call_gamma", "put_gamma"):
        for rank in (1, 2, 3):
            stem = f"{channel}_top{rank}_"
            if b(stem + "valid") == 1 and np.isfinite(b(stem + "strike_ib")):
                levels.append((float(b(stem + "strike_ib")), channel))
    valid_zone = geometry_ok and np.isfinite(spot) and np.isfinite(band) and band > 0
    nearest = (
        min(levels, key=lambda row: (abs(row[0] - spot), row[0], row[1]))
        if valid_zone
        else None
    )
    close_types = sorted(
        {source for level, source in levels if valid_zone and abs(level - spot) <= band}
    )
    emit("nearest_visible_level_ib", nearest[0] if nearest else None)
    emit(
        "nearest_visible_level_distance_ib", abs(nearest[0] - spot) if nearest else None
    )
    emit("visible_source_types_inside_band", len(close_types), valid_zone)
    if "fib" in close_types and len(close_types) > 1:
        tags.append("FIB_AND_VISIBLE_WALL_BANDS_OVERLAP")
    if nearest and abs(nearest[0] - spot) <= band:
        tags.append("NEAR_VISIBLE_LEVEL_COMPONENT")
    anchor = nearest[0] - spot if nearest else np.nan

    # Ignore nonexistent, masked, partial, current or future bars. Require the
    # exact latest completed scheduled bar; do not silently substitute an old one.
    def bar(duration, lag=0):
        slots = range(12) if duration == 5 else range(12, 20)
        wanted = (state_i // duration - lag) * duration - 1
        for index in slots:
            if (
                ends[index] == wanted
                and ends[index] < state_i
                and token_mask[index] == 1
                and bar_mask[index] == 1
                and tokens[index, T["spot_valid_fraction"]] == 1
                and np.isfinite(tokens[index, :13]).all()
            ):
                return tokens[index]
        return None

    last, previous, prior = bar(5), bar(5, 1), bar(5, 2)
    for field in ("low_rel_spot_ib", "high_rel_spot_ib", "close_rel_spot_ib"):
        emit(
            "last_closed_5m_" + field.replace("rel_spot", "minus_current_anchor"),
            last[T[field]] - anchor if last is not None and nearest else None,
            geometry_ok,
            "COMPLETE_5M_BAR_AND_CURRENT_ANCHOR_REQUIRED",
        )
    emit(
        "directional_previous_5m_close_change_ib",
        direction * (previous[T["close_rel_spot_ib"]] - prior[T["close_rel_spot_ib"]])
        if previous is not None and prior is not None
        else None,
        geometry_ok and side_ok,
        "TWO_PRIOR_COMPLETE_5M_BARS_REQUIRED",
    )
    for duration in (5, 15):
        current = bar(duration)
        for field in ("body_ib", "upper_wick_ib", "lower_wick_ib", "range_ib"):
            emit(
                f"last_closed_{duration}m_{field}",
                current[T[field]] if current is not None else None,
                geometry_ok,
                "LATEST_CLOSED_BAR_NOT_FULLY_OBSERVED",
            )
        for side in ("call", "put"):
            for kind in ("oi", "gamma"):
                field = side + "_" + kind + "_logsum"
                full_known = (
                    current is not None
                    and b(f"current_{side}_oi_known_fraction") == 1
                    and current[T[f"{side}_oi_known_fraction"]] == 1
                )
                if kind == "gamma":
                    full_known = (
                        full_known
                        and b(f"current_{side}_iv_valid_fraction") == 1
                        and b(f"current_{side}_present_fraction") == 1
                        and current[T[f"{side}_iv_valid_fraction"]] == 1
                        and current[T[f"{side}_present_fraction"]] == 1
                        and b("current_" + field) > 0
                        and current[T[field]] > 0
                    )
                emit(
                    f"{side}_{kind}_current_logmass_minus_closed_{duration}m_meanlog",
                    b("current_" + field) - current[T[field]] if full_known else None,
                    full_known,
                    "FULL_COMPARABLE_COVERAGE_REQUIRED_LOG_AVERAGE_NOT_ARITHMETIC_MASS",
                )
    emit(
        "historical_top_wall_displacement_ib",
        reason="HISTORICAL_TOP_WALL_COORDINATES_NOT_IN_INPUT_SCHEMA",
    )
    rejection = acceptance = None
    if (
        last is not None
        and previous is not None
        and geometry_ok
        and side_ok
        and nearest
    ):
        lo, hi = last[T["low_rel_spot_ib"]], last[T["high_rel_spot_ib"]]
        touched = lo <= anchor + band and hi >= anchor - band
        outgoing = direction * (last[T["close_rel_spot_ib"]] - anchor) >= 0
        body = direction * last[T["body_ib"]] > 0
        current_follow = direction * (-last[T["close_rel_spot_ib"]]) >= 0
        wick = last[T["lower_wick_ib"] if direction > 0 else T["upper_wick_ib"]]
        if prior is not None:
            approach = (
                direction
                * (previous[T["close_rel_spot_ib"]] - prior[T["close_rel_spot_ib"]])
                < 0
            )
            rejection = float(
                touched
                and outgoing
                and body
                and current_follow
                and approach
                and wick > 0
            )
        trend15 = bar(15)
        if trend15 is not None:
            two_closes = (
                outgoing
                and direction * (previous[T["close_rel_spot_ib"]] - anchor) >= 0
            )
            acceptance = float(
                touched
                and two_closes
                and body
                and direction * trend15[T["body_ib"]] > 0
            )
    emit(
        "rejection_description",
        rejection,
        reason="THREE_COMPLETE_5M_BARS_AND_VISIBLE_ANCHOR_REQUIRED",
    )
    emit(
        "acceptance_retest_description",
        acceptance,
        reason="TWO_COMPLETE_5M_AND_ONE_15M_BARS_AND_ANCHOR_REQUIRED",
    )
    if rejection == 1:
        tags.append("REJECTION_GEOMETRY_RELATIVE_TO_CURRENT_ANCHOR")
    if acceptance == 1:
        tags.append("ACCEPTANCE_RETEST_GEOMETRY_RELATIVE_TO_CURRENT_ANCHOR")
    return dict(
        version=VERSION,
        state_i=int(state_i),
        metrics=metrics,
        evidence_tags=sorted(tags),
        nearest_visible_source=nearest[1] if nearest else None,
        visible_sources_inside_band=close_types,
        interpretation="DESCRIPTIVE_PREENTRY_EVIDENCE_NOT_PREDICTED_PROFIT",
        wall_scope="CURRENT_TOP3_PER_SIDE_AND_MASS_CHANNEL_NOT_FULL_STRIKE_UNIVERSE",
        signed_dealer_exposure_observed=False,
        anchor_asof_decision=True,
        historical_anchor_availability_verified=False,
        outcomes_read=False,
    )
