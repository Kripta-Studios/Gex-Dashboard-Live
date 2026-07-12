"""Causal primitives for ``WALL_SURFACE_FLOW_AT_TOUCH_V1``.

The module deliberately contains no outcome or option-payoff logic.  An option
OHLC row stamped ``m`` represents the completed interval ``[m, m + 1m)`` and is
eligible for a decision at ``t`` only when ``m + 1m <= t``.  Trade direction is
not observed: ``trade_sign_proxy`` compares the bar close with the exact
bar-start quote midpoint and is therefore only a quote-relative proxy.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


START_DATE = "20220801"
END_DATE = "20251231"
FIRST_MINUTE = 635
LAST_MINUTE = 870
CADENCE_MINUTES = 5
TOUCH_BPS = 15.0
LOCAL_RADIUS_BPS = 30.0
SPOT_ALIGNMENT_TOLERANCE_BPS = 0.001
WINDOWS_MINUTES = (1, 5, 15)
EARLY_CLOSE_DATES = frozenset(
    {
        "20221125",
        "20230703", "20231124",
        "20240703", "20241129", "20241224",
        "20250703", "20251128", "20251224",
    }
)

KEY_COLUMNS = ("ticker", "trade_date", "minute", "wall_identity")
WALL_SPECS: dict[str, tuple[str, str, str]] = {
    "call_gamma": ("wall_call_gamma_strike", "CALL", "resistance"),
    "put_gamma": ("wall_put_gamma_strike", "PUT", "support"),
    "call_delta": ("wall_call_delta_strike", "CALL", "resistance"),
    "put_delta": ("wall_put_delta_strike", "PUT", "support"),
}

CONTROL_FEATURES = (
    "minute_sin",
    "minute_cos",
    "role_resistance",
    "candidate_distance_bps",
    "candidate_abs_distance_bps",
    "spot_ret_1m_bps",
    "spot_abs_ret_1m_bps",
    "spot_ret_5m_bps",
    "spot_ret_15m_bps",
    "spot_ret_30m_bps",
    "realized_vol_5m_bps",
    "realized_vol_15m_bps",
    "candidate_distance_change_5m_bps",
    "candidate_distance_change_15m_bps",
    "candidate_distance_change_30m_bps",
    "candidate_approach_5m_bps",
    "candidate_approach_15m_bps",
    "candidate_approach_30m_bps",
)


def _flow_feature_names() -> tuple[str, ...]:
    names: list[str] = []
    for window in WINDOWS_MINUTES:
        suffix = f"w{window}m"
        for right in ("call", "put"):
            names.extend(
                [
                    f"surface_{right}_volume_{suffix}",
                    f"surface_{right}_count_{suffix}",
                    f"surface_{right}_close_notional_{suffix}",
                    f"surface_{right}_signed_volume_{suffix}",
                    f"surface_{right}_signed_count_{suffix}",
                    f"surface_{right}_signed_close_notional_{suffix}",
                    f"surface_{right}_quote_row_coverage_{suffix}",
                    f"surface_{right}_quote_volume_coverage_{suffix}",
                    f"surface_{right}_price_volume_coverage_{suffix}",
                    f"surface_{right}_signable_volume_coverage_{suffix}",
                    f"surface_{right}_count_volume_coverage_{suffix}",
                ]
            )
        names.extend(
            [
                f"surface_directional_pressure_{suffix}",
                f"surface_volume_imbalance_{suffix}",
                f"surface_count_imbalance_{suffix}",
                f"surface_close_notional_imbalance_{suffix}",
                f"surface_quote_row_coverage_{suffix}",
                f"surface_quote_volume_coverage_{suffix}",
                f"surface_price_volume_coverage_{suffix}",
                f"surface_signable_volume_coverage_{suffix}",
                f"surface_count_volume_coverage_{suffix}",
                f"local_volume_{suffix}",
                f"local_count_{suffix}",
                f"local_close_notional_{suffix}",
                f"local_signed_volume_{suffix}",
                f"local_signed_count_{suffix}",
                f"local_signed_close_notional_{suffix}",
                f"local_buy_sell_close_notional_log_ratio_{suffix}",
                f"local_signed_close_notional_ratio_{suffix}",
                f"local_quote_row_coverage_{suffix}",
                f"local_quote_volume_coverage_{suffix}",
                f"local_price_volume_coverage_{suffix}",
                f"local_signable_volume_coverage_{suffix}",
                f"local_count_volume_coverage_{suffix}",
                f"role_break_pressure_{suffix}",
            ]
        )
    names.extend(
        [
            "surface_pressure_same_sign_1m_5m",
            "surface_pressure_same_sign_5m_15m",
            "local_pressure_same_sign_1m_5m",
            "local_pressure_same_sign_5m_15m",
        ]
    )
    return tuple(names)


FLOW_FEATURES = _flow_feature_names()
SURFACE_FLOW_PROVENANCE_COLUMNS = (
    "ticker", "trade_date", "minute", "decision_dt", "wall_identity", "wall_role",
    "candidate_right", "candidate_wall_strike", "spot", "wall_alias_count",
    "episode_sequence", "episode_start_minute", "episode_id",
)
SURFACE_FLOW_AUDIT_COLUMNS = (
    "flow_earliest_bar_start", "flow_latest_bar_start", "flow_latest_bar_end",
)


def expected_surface_flow_columns() -> tuple[str, ...]:
    return (*SURFACE_FLOW_PROVENANCE_COLUMNS, *CONTROL_FEATURES, *FLOW_FEATURES, *SURFACE_FLOW_AUDIT_COLUMNS)


def normalize_right(series: pd.Series) -> pd.Series:
    values = series.astype(str).str.upper().str.strip()
    return values.replace({"C": "CALL", "P": "PUT"})


def option_market_close_minute(ticker: str, trade_date: str) -> int:
    """Return the last tradable minute boundary for the 0DTE option.

    QQQ/SPY options normally close at 16:15 ET and at 13:15 ET on the
    enumerated half days.  Expiring SPXW closes with the cash index at 16:00
    or 13:00.  The current candidate window ends at 14:30 on regular days, but
    keeping the two clocks explicit prevents later scheduler/label confusion.
    """

    date = str(trade_date).replace("-", "")[:8]
    is_spxw = str(ticker).upper() == "SPXW"
    if date in EARLY_CLOSE_DATES:
        return 13 * 60 if is_spxw else 13 * 60 + 15
    return 16 * 60 if is_spxw else 16 * 60 + 15


def underlying_market_close_minute(trade_date: str) -> int:
    """Return the physical underlying RTH close used by decisions/labels."""

    date = str(trade_date).replace("-", "")[:8]
    return 13 * 60 if date in EARLY_CLOSE_DATES else 16 * 60


def last_scheduled_decision_minute(ticker: str, trade_date: str) -> int:
    # A wall interaction requires a currently trading underlying.  QQQ/SPY
    # options remain open for 15 minutes after the cash half-day close, but
    # those post-close option minutes are not eligible physical decisions.
    close = underlying_market_close_minute(trade_date)
    return min(LAST_MINUTE, FIRST_MINUTE + ((close - 1 - FIRST_MINUTE) // CADENCE_MINUTES) * CADENCE_MINUTES)


def _require_columns(frame: pd.DataFrame, required: tuple[str, ...], source: str) -> None:
    missing = sorted(set(required).difference(frame.columns))
    if missing:
        raise KeyError(f"{source} missing required columns: {missing}")


def _safe_ratio(numerator: float, denominator: float) -> float:
    if not np.isfinite(denominator) or denominator <= 0.0:
        return 0.0
    value = float(numerator) / float(denominator)
    return value if np.isfinite(value) else 0.0


def validate_underlying_session(
    underlying: pd.DataFrame,
    *,
    expected_ticker: str,
    expected_trade_date: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Validate the complete structural contract of a derived 1m spot source."""

    required = ("symbol", "date", "timestamp", "open", "high", "low", "close", "tick_count")
    _require_columns(underlying, required, "derived underlying")
    ticker = str(expected_ticker).upper()
    day = str(expected_trade_date).replace("-", "")[:8]
    frame = underlying[list(required)].copy()
    frame["symbol"] = frame["symbol"].astype(str).str.upper()
    source_day = frame["date"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    if set(frame["symbol"].unique()) != {ticker} or not source_day.eq(day).all():
        raise AssertionError("derived underlying symbol/date metadata mismatch")
    frame["bar_start"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    if frame["bar_start"].isna().any() or not frame["bar_start"].dt.strftime("%Y%m%d").eq(day).all():
        raise AssertionError("derived underlying timestamps do not belong to expected trade date")
    boundary = frame["bar_start"].dt.second.eq(0) & frame["bar_start"].dt.microsecond.eq(0)
    if not bool(boundary.all()) or frame.duplicated(["bar_start"]).any():
        raise AssertionError("derived underlying contains non-boundary or duplicate minute keys")
    numeric_columns = ["open", "high", "low", "close", "tick_count"]
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    close_minute = underlying_market_close_minute(day)
    session_start = pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} 09:30:00")
    session_end = pd.Timestamp(day) + pd.Timedelta(minutes=close_minute - 1)
    required_grid = pd.date_range(session_start, session_end, freq="1min")
    observed = pd.Index(frame["bar_start"])
    missing = required_grid.difference(observed)
    if len(missing):
        raise AssertionError(f"derived underlying regular-session grid is incomplete: missing={len(missing)}")
    # The earliest frozen decision is 10:35 and RV15 needs N+1 completed
    # closes, hence 10:19 is the first value that can enter F0.  Earlier source
    # anomalies are counted but never repaired or allowed to reject/select a
    # session whose experiment inputs and labels remain unaffected.
    value_start = pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} 10:19:00")
    relevant = frame[frame["bar_start"].between(value_start, session_end, inclusive="both")].copy()
    finite = np.isfinite(frame[numeric_columns].to_numpy(dtype=float)).all(axis=1)
    positive_ohlc = frame[["open", "high", "low", "close"]].gt(0.0).all(axis=1)
    positive_ticks = frame["tick_count"].gt(0.0)
    envelope = frame["high"].ge(frame[["open", "close"]].max(axis=1)) & frame["low"].le(
        frame[["open", "close"]].min(axis=1)
    )
    structurally_valid = finite & positive_ohlc & positive_ticks & envelope
    relevant_valid = structurally_valid.loc[relevant.index]
    if not bool(relevant_valid.all()):
        raise AssertionError(
            f"derived underlying contains invalid research-window rows: {(~relevant_valid).sum()}"
        )
    frame = frame.sort_values("bar_start", kind="stable").reset_index(drop=True)
    return frame, {
        "underlying_rows": int(len(frame)),
        "underlying_required_window_minutes": int(observed.isin(required_grid).sum()),
        "expected_underlying_required_window_minutes": int(len(required_grid)),
        "underlying_timestamp_min": frame["bar_start"].min(),
        "underlying_timestamp_max": frame["bar_start"].max(),
        "underlying_min_research_tick_count": float(relevant["tick_count"].min()),
        "underlying_out_of_scope_invalid_rows": int((~structurally_valid & frame["bar_start"].lt(value_start)).sum()),
    }


def prepare_completed_bar_flow(
    greeks: pd.DataFrame,
    ohlc: pd.DataFrame,
    *,
    expected_ticker: str | None = None,
    expected_trade_date: str | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Exact-join active one-minute option bars to their bar-start quote.

    Sub-minute Greek rows are retained in the audit but cannot sign a minute
    bar.  OHLC is required to be a genuine one-minute, minute-boundary source;
    silently flooring a trade/tick timestamp is forbidden.
    """

    _require_columns(
        greeks,
        ("symbol", "expiration", "trade_date", "interval_used", "right", "strike", "bid", "ask"),
        "greeks",
    )
    if "timestamp" not in greeks and "underlying_timestamp" not in greeks:
        raise KeyError("greeks requires option timestamp or an audited underlying_timestamp fallback")
    _require_columns(
        ohlc,
        (
            "symbol", "expiration", "trade_date", "interval_used", "timestamp",
            "right", "strike", "close", "volume", "count",
        ),
        "ohlc",
    )
    provenance_columns = [column for column in ("symbol", "expiration", "trade_date", "interval_used") if column in greeks]
    quote_columns = [column for column in ("timestamp", "underlying_timestamp", "right", "strike", "bid", "ask") if column in greeks]
    quote = greeks[[*provenance_columns, *quote_columns]].copy()
    bar_provenance = [column for column in ("symbol", "expiration", "trade_date", "interval_used") if column in ohlc]
    bars = ohlc[[*bar_provenance, "timestamp", "right", "strike", "close", "volume", "count"]].copy()
    expected_date = str(expected_trade_date or "").replace("-", "")[:8]
    expected_symbol = str(expected_ticker or "").upper()
    timestamp_fallback_used = "timestamp" not in quote.columns
    if "timestamp" in quote:
        quote["quote_dt"] = pd.to_datetime(quote["timestamp"], errors="coerce")
        if "underlying_timestamp" in quote:
            underlying_dt = pd.to_datetime(quote["underlying_timestamp"], errors="coerce")
            if quote["quote_dt"].isna().any() or underlying_dt.isna().any():
                raise AssertionError("dual option/underlying timestamps must both be complete")
            mismatch = quote["quote_dt"].ne(underlying_dt)
            if bool(mismatch.any()):
                raise AssertionError("option timestamp and underlying_timestamp differ; quote clock is ambiguous")
    else:
        quote["quote_dt"] = pd.to_datetime(quote["underlying_timestamp"], errors="coerce")
    bars["bar_start"] = pd.to_datetime(bars.pop("timestamp"), errors="coerce")
    if quote["quote_dt"].isna().any() or bars["bar_start"].isna().any():
        raise AssertionError("option source contains missing/unparseable timestamps")
    if expected_date:
        quote_dates = quote["quote_dt"].dt.strftime("%Y%m%d")
        bar_dates = bars["bar_start"].dt.strftime("%Y%m%d")
        if not quote_dates.eq(expected_date).all():
            raise AssertionError("greeks timestamps do not belong to expected trade date")
        if not bar_dates.eq(expected_date).all():
            raise AssertionError("OHLC timestamps do not belong to expected trade date")
    quote_boundary = quote["quote_dt"].dt.second.eq(0) & quote["quote_dt"].dt.microsecond.eq(0)
    bar_boundary = bars["bar_start"].dt.second.eq(0) & bars["bar_start"].dt.microsecond.eq(0)
    if not bool(bar_boundary.all()):
        raise AssertionError("OHLC contains non-minute-boundary timestamps; interval semantics are not reproducible")
    quote["right"] = normalize_right(quote["right"])
    bars["right"] = normalize_right(bars["right"])
    for source_name, frame in (("greeks", quote), ("ohlc", bars)):
        observed_rights = set(frame["right"].dropna().astype(str).unique())
        if frame["right"].isna().any() or not observed_rights.issubset({"CALL", "PUT"}):
            raise AssertionError(f"{source_name} contains unknown option rights: {sorted(observed_rights)}")
    for source_name, frame in (("greeks", quote), ("ohlc", bars)):
        if "interval_used" in frame and set(frame["interval_used"].astype(str).str.lower().unique()) != {"1m"}:
            raise AssertionError(f"{source_name} is not uniformly interval_used=1m")
        if expected_symbol and "symbol" in frame:
            observed = set(frame["symbol"].astype(str).str.upper().unique())
            if observed != {expected_symbol}:
                raise AssertionError(f"{source_name} symbol contamination: {sorted(observed)}")
        for date_column in ("trade_date", "expiration"):
            if expected_date and date_column in frame:
                normalized = frame[date_column].astype(str).str.replace(r"\D", "", regex=True).str[:8]
                observed_dates = set(normalized.unique())
                if observed_dates != {expected_date}:
                    raise AssertionError(f"{source_name} {date_column} is not exact 0DTE {expected_date}: {sorted(observed_dates)}")
    for frame in (quote, bars):
        frame["strike"] = pd.to_numeric(frame["strike"], errors="coerce")
    for column in ("bid", "ask"):
        quote[column] = pd.to_numeric(quote[column], errors="coerce")
    for column in ("close", "volume", "count"):
        bars[column] = pd.to_numeric(bars[column], errors="coerce")
    quote_strike = quote["strike"].to_numpy(dtype=float)
    bar_strike = bars["strike"].to_numpy(dtype=float)
    if (
        quote[["strike", "right"]].isna().any().any()
        or not np.isfinite(quote_strike).all()
        or not (quote_strike > 0.0).all()
    ):
        raise AssertionError("greeks contains invalid normalized contract keys")
    if (
        bars[["strike", "right", "volume"]].isna().any().any()
        or not np.isfinite(bar_strike).all()
        or not (bar_strike > 0.0).all()
        or not np.isfinite(bars["volume"].to_numpy(dtype=float)).all()
        or not np.isfinite(bars["count"].dropna().to_numpy(dtype=float)).all()
    ):
        raise AssertionError("OHLC contains invalid normalized contract keys or activity")
    exact_quote = quote[quote_boundary].copy()
    quote_keys = ["quote_dt", "right", "strike"]
    bar_keys = ["bar_start", "right", "strike"]
    if exact_quote.duplicated(quote_keys).any():
        sample = exact_quote.loc[exact_quote.duplicated(quote_keys, keep=False), quote_keys].head().to_dict("records")
        raise AssertionError(f"duplicate exact quote keys: {sample}")
    if bars.duplicated(bar_keys).any():
        sample = bars.loc[bars.duplicated(bar_keys, keep=False), bar_keys].head().to_dict("records")
        raise AssertionError(f"duplicate OHLC keys: {sample}")
    negative_activity = bars["volume"].lt(0.0) | bars["count"].dropna().lt(0.0).reindex(bars.index, fill_value=False)
    if bool(negative_activity.any()):
        raise AssertionError("OHLC contains negative volume/count")
    bars["valid_count"] = bars["count"].notna().astype(np.int8)
    count_without_volume_rows = int((bars["volume"].le(0.0) & bars["count"].fillna(0.0).gt(0.0)).sum())
    bars["count"] = bars["count"].fillna(0.0)
    option_close_minute = option_market_close_minute(expected_symbol, expected_date) if expected_symbol and expected_date else 16 * 60
    underlying_close_minute = underlying_market_close_minute(expected_date) if expected_date else 16 * 60
    last_decision = min(
        LAST_MINUTE,
        FIRST_MINUTE + ((underlying_close_minute - 1 - FIRST_MINUTE) // CADENCE_MINUTES) * CADENCE_MINUTES,
    )
    last_required_bar = last_decision - 1
    bar_minute_values = bars["bar_start"].dt.hour * 60 + bars["bar_start"].dt.minute
    bars_relevant = bars[bar_minute_values.between(620, last_required_bar)].copy()
    active = bars_relevant[bars_relevant["volume"].gt(0.0)].copy()
    join_identity = [column for column in ("symbol", "expiration") if column in active and column in exact_quote]
    joined = active.merge(
        exact_quote.rename(columns={"quote_dt": "bar_start"}),
        on=[*join_identity, "bar_start", "right", "strike"],
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    valid_quote = (
        joined["bid"].gt(0.0)
        & joined["ask"].gt(0.0)
        & joined["ask"].ge(joined["bid"])
        & np.isfinite(joined["bid"])
        & np.isfinite(joined["ask"])
    )
    valid_price = joined["close"].gt(0.0) & np.isfinite(joined["close"])
    signable = valid_quote & valid_price
    joined["valid_quote"] = valid_quote.astype(np.int8)
    joined["valid_price"] = valid_price.astype(np.int8)
    joined["signable"] = signable.astype(np.int8)
    joined["quote_mid"] = ((joined["bid"] + joined["ask"]) / 2.0).where(valid_quote)
    sign = np.sign(joined["close"] - joined["quote_mid"]).where(signable)
    joined["trade_sign_proxy"] = sign.fillna(0.0).astype(np.int8)
    joined["close_notional"] = np.where(valid_price, joined["volume"] * joined["close"] * 100.0, 0.0)
    for metric in ("volume", "count", "close_notional"):
        joined[f"signed_{metric}"] = np.where(
            signable,
            joined["trade_sign_proxy"] * joined[metric],
            0.0,
        )
    joined["valid_quote_volume"] = np.where(valid_quote, joined["volume"], 0.0)
    joined["valid_price_volume"] = np.where(valid_price, joined["volume"], 0.0)
    joined["signable_volume"] = np.where(signable, joined["volume"], 0.0)
    joined["valid_count_volume"] = np.where(joined["valid_count"].gt(0), joined["volume"], 0.0)
    joined["buy_close_notional"] = np.where(joined["trade_sign_proxy"].gt(0), joined["close_notional"], 0.0)
    joined["sell_close_notional"] = np.where(joined["trade_sign_proxy"].lt(0), joined["close_notional"], 0.0)
    joined["bar_end"] = joined["bar_start"] + pd.Timedelta(minutes=1)

    quote_minute_values = exact_quote["quote_dt"].dt.hour * 60 + exact_quote["quote_dt"].dt.minute
    quote_relevant = exact_quote[quote_minute_values.between(620, last_required_bar)].copy()
    stale = quote_relevant.sort_values(["right", "strike", "quote_dt"], kind="stable").copy()
    grouped = stale.groupby(["right", "strike"], observed=True, sort=False)
    previous_dt = grouped["quote_dt"].shift(1)
    contiguous = previous_dt.eq(stale["quote_dt"] - pd.Timedelta(minutes=1))
    unchanged = grouped["bid"].shift(1).eq(stale["bid"]) & grouped["ask"].shift(1).eq(stale["ask"])
    stale_pairs = int((contiguous & unchanged).sum())
    contiguous_pairs = int(contiguous.sum())
    greeks_window_minutes = int(quote_relevant["quote_dt"].nunique())
    ohlc_window_minutes = int(bars_relevant["bar_start"].nunique())
    expected_window_minutes = int(last_required_bar - 620 + 1)
    total_active_volume = float(active["volume"].sum())
    valid_volume = float(joined.loc[valid_quote, "volume"].sum())
    priced_volume = float(joined.loc[valid_price, "volume"].sum())
    signable_volume = float(joined.loc[signable, "volume"].sum())
    audit = {
        "greeks_rows": int(len(greeks)),
        "greeks_parsed_rows": int(len(quote)),
        "greeks_exact_minute_rows": int(len(exact_quote)),
        "greeks_subminute_rows": int((~quote_boundary).sum()),
        "option_timestamp_fallback_used": bool(timestamp_fallback_used),
        "ohlc_rows": int(len(ohlc)),
        "greeks_required_window_minutes": greeks_window_minutes,
        "ohlc_required_window_minutes": ohlc_window_minutes,
        "expected_required_window_minutes": expected_window_minutes,
        "option_market_close_minute": option_close_minute,
        "underlying_market_close_minute": underlying_close_minute,
        "last_scheduled_decision_minute": last_decision,
        "active_rows": int(len(active)),
        "active_volume": total_active_volume,
        "active_count": float(active["count"].sum()),
        "valid_quote_rows": int(valid_quote.sum()),
        "valid_quote_volume": valid_volume,
        "priced_active_rows": int(valid_price.sum()),
        "priced_active_volume": priced_volume,
        "signable_rows": int(signable.sum()),
        "signable_volume": signable_volume,
        "nonpositive_close_active_rows": int((~valid_price).sum()),
        "nonpositive_close_active_volume": float(joined.loc[~valid_price, "volume"].sum()),
        "price_volume_coverage": _safe_ratio(priced_volume, total_active_volume),
        "signable_volume_coverage": _safe_ratio(signable_volume, total_active_volume),
        "quote_row_coverage": _safe_ratio(float(valid_quote.sum()), float(len(active))),
        "quote_volume_coverage": _safe_ratio(valid_volume, total_active_volume),
        "unmatched_active_rows": int(joined["_merge"].ne("both").sum()),
        "zero_count_active_rows": int((active["count"] <= 0.0).sum()),
        "missing_count_active_rows": int(active["valid_count"].le(0).sum()),
        "missing_count_active_volume": float(active.loc[active["valid_count"].le(0), "volume"].sum()),
        "count_without_volume_rows": count_without_volume_rows,
        "contiguous_quote_pairs": contiguous_pairs,
        "unchanged_contiguous_quote_pairs": stale_pairs,
        "unchanged_contiguous_quote_rate": _safe_ratio(stale_pairs, contiguous_pairs),
    }
    columns = [
        "bar_start", "bar_end", "right", "strike", "close", "volume", "count",
        "close_notional", "signed_volume", "signed_count", "signed_close_notional", "valid_quote",
        "valid_price", "signable", "valid_quote_volume", "valid_price_volume",
        "signable_volume", "valid_count_volume", "trade_sign_proxy", "buy_close_notional", "sell_close_notional",
    ]
    return joined[columns].sort_values(["bar_start", "right", "strike"], kind="stable").reset_index(drop=True), audit


def make_touch_candidates(
    walls: pd.DataFrame,
    events: pd.DataFrame,
    *,
    return_audit: bool = False,
) -> pd.DataFrame | tuple[pd.DataFrame, dict[str, Any]]:
    """Join the observable event control and expand four at-touch wall identities."""

    wall_required = ("ticker", "trade_date", "minute", "spot", *[spec[0] for spec in WALL_SPECS.values()])
    event_required = (
        "ticker", "trade_date", "minute", "spot",
        "ret_1m_bps", "ret_5m_bps", "ret_15m_bps", "ret_30m_bps",
    )
    _require_columns(walls, wall_required, "walls")
    _require_columns(events, event_required, "events")
    keys = ["ticker", "trade_date", "minute"]
    left = walls[list(wall_required)].copy()
    right = events[list(event_required)].copy()
    for frame in (left, right):
        frame["ticker"] = frame["ticker"].astype(str).str.upper()
        frame["trade_date"] = frame["trade_date"].astype(str).str.replace(r"\.0$", "", regex=True)
        frame["minute"] = pd.to_numeric(frame["minute"], errors="coerce")
    left = left[
        left["trade_date"].between(START_DATE, END_DATE)
        & left["minute"].between(FIRST_MINUTE, LAST_MINUTE)
        & ((left["minute"] - FIRST_MINUTE) % CADENCE_MINUTES == 0)
    ].copy()
    right = right[
        right["trade_date"].between(START_DATE, END_DATE)
        & right["minute"].between(FIRST_MINUTE, LAST_MINUTE)
        & ((right["minute"] - FIRST_MINUTE) % CADENCE_MINUTES == 0)
    ].copy()
    right["underlying_market_close_minute"] = [
        underlying_market_close_minute(trade_date)
        for trade_date in right["trade_date"]
    ]
    right = right[right["minute"].lt(right["underlying_market_close_minute"])].drop(
        columns=["underlying_market_close_minute"]
    )
    if left.duplicated(keys).any() or right.duplicated(keys).any():
        raise AssertionError("wall/event inputs must have unique exact decision keys")
    # The executable event view is the frozen decision universe.  Wall state
    # intentionally contains a denser grid, so require every event (not every
    # wall row) to have one exact wall snapshot.
    joined = right.merge(left, on=keys, how="left", suffixes=("_event", ""), validate="one_to_one")
    if len(joined) != len(right) or joined["spot"].isna().any():
        raise AssertionError(f"wall coverage failed: {joined['spot'].notna().sum()}/{len(right)} executable decisions")
    finite_columns = ["spot", "spot_event", "ret_1m_bps", "ret_5m_bps", "ret_15m_bps", "ret_30m_bps"]
    finite_matrix = joined[finite_columns].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(finite_matrix).all() or not pd.to_numeric(joined["spot"], errors="coerce").gt(0.0).all():
        raise AssertionError("wall/event control contains non-finite spot or causal returns")
    spot_diff = (joined["spot"] - joined["spot_event"]).abs() / joined["spot_event"] * 10_000.0
    if spot_diff.empty or float(spot_diff.max()) > SPOT_ALIGNMENT_TOLERANCE_BPS:
        raise AssertionError(f"wall/event exact-spot parity failed: max_bps={spot_diff.max()}")
    # The executable event view is the canonical decision spot.  The wall copy
    # is accepted only within a sub-millibasis-point serialization tolerance.
    joined["spot"] = joined["spot_event"]
    joined = joined.drop(columns=["spot_event"])
    candidates: list[pd.DataFrame] = []
    for identity, (strike_column, candidate_right, role) in WALL_SPECS.items():
        strike = pd.to_numeric(joined[strike_column], errors="coerce")
        distance = (joined["spot"] - strike) / joined["spot"] * 10_000.0
        selected = joined[distance.abs().le(TOUCH_BPS) & strike.gt(0.0)].copy()
        if selected.empty:
            continue
        selected["wall_identity"] = identity
        selected["wall_role"] = role
        selected["candidate_right"] = candidate_right
        selected["candidate_wall_strike"] = strike.loc[selected.index]
        selected["candidate_distance_bps"] = distance.loc[selected.index]
        selected["candidate_abs_distance_bps"] = distance.loc[selected.index].abs()
        selected["role_resistance"] = float(role == "resistance")
        selected["minute_sin"] = np.sin(2.0 * np.pi * selected["minute"].astype(float) / 1440.0)
        selected["minute_cos"] = np.cos(2.0 * np.pi * selected["minute"].astype(float) / 1440.0)
        selected["spot_ret_1m_bps"] = pd.to_numeric(selected["ret_1m_bps"], errors="coerce")
        selected["spot_abs_ret_1m_bps"] = selected["spot_ret_1m_bps"].abs()
        for lag in (5, 15, 30):
            ret = pd.to_numeric(selected[f"ret_{lag}m_bps"], errors="coerce")
            prior_spot = selected["spot"] / (1.0 + ret / 10_000.0)
            prior_distance = (prior_spot - selected["candidate_wall_strike"]) / selected["spot"] * 10_000.0
            selected[f"spot_ret_{lag}m_bps"] = ret
            selected[f"candidate_distance_change_{lag}m_bps"] = selected["candidate_distance_bps"] - prior_distance
            selected[f"candidate_approach_{lag}m_bps"] = prior_distance.abs() - selected["candidate_abs_distance_bps"]
        candidates.append(selected)
    if not candidates:
        return pd.DataFrame()
    out = pd.concat(candidates, ignore_index=True)
    raw_identity_rows = int(len(out))
    out["decision_dt"] = pd.to_datetime(out["trade_date"], format="%Y%m%d") + pd.to_timedelta(out["minute"], unit="m")
    # Gamma and delta walls can alias the same economic level.  Collapse those
    # aliases before modeling so one underlying event is never counted twice.
    level_keys = [
        "ticker", "trade_date", "minute", "wall_role", "candidate_right",
        "candidate_wall_strike",
    ]
    ordered = out.sort_values([*level_keys, "wall_identity"], kind="stable")
    identity_columns = [f"_identity_{identity}" for identity in WALL_SPECS]
    identity_flags = pd.get_dummies(ordered["wall_identity"], prefix="_identity", dtype=np.int8)
    for column in identity_columns:
        if column not in identity_flags:
            identity_flags[column] = 0
    flagged = pd.concat(
        [ordered[level_keys].reset_index(drop=True), identity_flags[identity_columns].reset_index(drop=True)], axis=1
    )
    grouped_flags = flagged.groupby(level_keys, observed=True, sort=True)[identity_columns].max().reset_index()
    base = ordered.drop_duplicates(level_keys, keep="first").drop(columns=["wall_identity"])
    out = base.merge(grouped_flags, on=level_keys, how="inner", validate="one_to_one")
    call_gamma = out["_identity_call_gamma"].gt(0)
    call_delta = out["_identity_call_delta"].gt(0)
    put_gamma = out["_identity_put_gamma"].gt(0)
    put_delta = out["_identity_put_delta"].gt(0)
    out["wall_identity"] = np.select(
        [call_gamma & call_delta, call_gamma, call_delta, put_gamma & put_delta, put_gamma, put_delta],
        ["call_delta+call_gamma", "call_gamma", "call_delta", "put_delta+put_gamma", "put_gamma", "put_delta"],
        default="",
    )
    if out["wall_identity"].eq("").any():
        raise AssertionError("failed to encode collapsed wall identity")
    out["wall_alias_count"] = out[identity_columns].sum(axis=1).astype(int)
    out = out.drop(columns=identity_columns).sort_values(
        ["ticker", "trade_date", "wall_role", "candidate_wall_strike", "minute"], kind="stable"
    ).reset_index(drop=True)
    same_role_level_rows = int(len(out))
    same_level_keys = ["ticker", "trade_date", "minute", "candidate_wall_strike"]
    role_counts = out.groupby(same_level_keys, observed=True, sort=False)["wall_role"].transform("nunique")
    ambiguous = role_counts.gt(1)
    ambiguous_levels = int(out.loc[ambiguous, same_level_keys].drop_duplicates().shape[0])
    ambiguous_rows = int(ambiguous.sum())
    out = out[~ambiguous].copy()
    if out.empty:
        for column in ("episode_sequence", "episode_start_minute"):
            out[column] = pd.Series(index=out.index, dtype="int64")
        out["episode_id"] = pd.Series(index=out.index, dtype="object")
        keep = [
            "ticker", "trade_date", "minute", "decision_dt", "wall_identity", "wall_role",
            "candidate_right", "candidate_wall_strike", "spot", "wall_alias_count",
            "episode_sequence", "episode_start_minute", "episode_id",
            *[column for column in CONTROL_FEATURES if column not in {"realized_vol_5m_bps", "realized_vol_15m_bps"}],
        ]
        final = out[keep]
        audit = {
            "raw_identity_touch_rows": raw_identity_rows,
            "same_role_level_rows": same_role_level_rows,
            "alias_rows_collapsed": int(raw_identity_rows - same_role_level_rows),
            "ambiguous_opposite_role_levels": ambiguous_levels,
            "ambiguous_opposite_role_rows_excluded": ambiguous_rows,
            "unambiguous_repeated_touch_rows": 0,
            "first_touch_episode_rows": 0,
            "first_touch_episode_rows_by_ticker": {},
        }
        return (final, audit) if return_audit else final
    episode_groups = out.groupby(
        ["ticker", "trade_date", "wall_role", "candidate_wall_strike"], observed=True, sort=False
    )
    previous_minute = episode_groups["minute"].shift(1)
    new_episode = previous_minute.isna() | previous_minute.ne(out["minute"] - CADENCE_MINUTES)
    out["episode_sequence"] = new_episode.groupby(
        [out["ticker"], out["trade_date"], out["wall_role"], out["candidate_wall_strike"]],
        sort=False,
    ).cumsum().astype(int)
    episode_keys = [
        "ticker", "trade_date", "wall_role", "candidate_wall_strike", "episode_sequence",
    ]
    out["episode_start_minute"] = out.groupby(episode_keys, observed=True, sort=False)["minute"].transform("min").astype(int)
    out["episode_id"] = (
        out["ticker"].astype(str) + ":" + out["trade_date"].astype(str) + ":"
        + out["wall_role"].astype(str) + ":" + out["candidate_wall_strike"].map(lambda value: f"{float(value):.6f}")
        + ":" + out["episode_start_minute"].astype(str)
    )
    # The physical experiment evaluates the first observable interaction only;
    # repeated five-minute rows within the same touch are not independent data.
    pre_episode_rows = int(len(out))
    out = out[out["minute"].eq(out["episode_start_minute"])].copy()
    out = out.sort_values(list(KEY_COLUMNS), kind="stable").reset_index(drop=True)
    if out.duplicated(list(KEY_COLUMNS)).any():
        raise AssertionError("duplicate at-touch candidate keys")
    if out["trade_date"].str.startswith("2026").any():
        raise AssertionError("2026 entered the at-touch candidate universe")
    # Past-only realized-vol controls are attached separately from exact
    # completed underlying bars.  Keep the sealed artifact intentionally
    # narrow so rejected wall-state features cannot be selected post hoc.
    keep = [
        "ticker", "trade_date", "minute", "decision_dt", "wall_identity", "wall_role",
        "candidate_right", "candidate_wall_strike", "spot", "wall_alias_count",
        "episode_sequence", "episode_start_minute", "episode_id",
        *[column for column in CONTROL_FEATURES if column not in {"realized_vol_5m_bps", "realized_vol_15m_bps"}],
    ]
    final = out[keep]
    audit = {
        "raw_identity_touch_rows": raw_identity_rows,
        "same_role_level_rows": same_role_level_rows,
        "alias_rows_collapsed": int(raw_identity_rows - same_role_level_rows),
        "ambiguous_opposite_role_levels": ambiguous_levels,
        "ambiguous_opposite_role_rows_excluded": ambiguous_rows,
        "unambiguous_repeated_touch_rows": pre_episode_rows,
        "first_touch_episode_rows": int(len(final)),
        "first_touch_episode_rows_by_ticker": final.groupby("ticker", observed=True).size().astype(int).to_dict(),
    }
    return (final, audit) if return_audit else final


def attach_completed_underlying_controls(
    candidates: pd.DataFrame,
    underlying: pd.DataFrame,
    *,
    expected_trade_date: str | None = None,
) -> pd.DataFrame:
    """Attach realized volatility using only bars completed strictly before ``t``."""

    _require_columns(underlying, ("timestamp", "close"), "underlying")
    bars = underlying[["timestamp", "close"]].copy()
    bars["bar_start"] = pd.to_datetime(bars.pop("timestamp"), errors="coerce")
    bars["close"] = pd.to_numeric(bars["close"], errors="coerce")
    if bars[["bar_start", "close"]].isna().any().any():
        raise AssertionError("underlying controls contain missing timestamp/close")
    expected_date = str(expected_trade_date or "").replace("-", "")[:8]
    if expected_date and not bars["bar_start"].dt.strftime("%Y%m%d").eq(expected_date).all():
        raise AssertionError("underlying control timestamps do not belong to expected trade date")
    boundary = bars["bar_start"].dt.second.eq(0) & bars["bar_start"].dt.microsecond.eq(0)
    if not bool(boundary.all()):
        raise AssertionError("underlying controls contain non-minute-boundary bars")
    if bars.duplicated(["bar_start"]).any():
        raise AssertionError("underlying controls contain duplicate minute keys")
    if candidates.empty:
        output = candidates.copy()
        output["realized_vol_5m_bps"] = pd.Series(index=output.index, dtype="float64")
        output["realized_vol_15m_bps"] = pd.Series(index=output.index, dtype="float64")
        return output
    bars = bars.sort_values("bar_start", kind="stable").set_index("bar_start")
    output = candidates.copy()
    controls: list[tuple[float, float]] = []
    for decision in pd.to_datetime(output["decision_dt"], errors="coerce"):
        values: list[float] = []
        for window in (5, 15):
            # N realized one-minute returns require N+1 completed closes.  The
            # latest eligible close is the bar starting at t-1m.
            expected = pd.date_range(
                decision - pd.Timedelta(minutes=window + 1),
                decision - pd.Timedelta(minutes=1),
                freq="1min",
            )
            closes = bars.reindex(expected)["close"]
            if closes.notna().all() and (closes > 0.0).all():
                returns = np.diff(np.log(closes.to_numpy(dtype=float))) * 10_000.0
                values.append(float(np.std(returns, ddof=0)))
            else:
                values.append(float("nan"))
        controls.append((values[0], values[1]))
    output[["realized_vol_5m_bps", "realized_vol_15m_bps"]] = pd.DataFrame(controls, index=output.index)
    return output


def _scope_totals(rows: pd.DataFrame) -> dict[str, float]:
    return {
        "rows": float(len(rows)),
        "volume": float(rows["volume"].sum()),
        "count": float(rows["count"].sum()),
        "close_notional": float(rows["close_notional"].sum()),
        "signed_volume": float(rows["signed_volume"].sum()),
        "signed_count": float(rows["signed_count"].sum()),
        "signed_close_notional": float(rows["signed_close_notional"].sum()),
        "valid_rows": float(rows["valid_quote"].sum()),
        "valid_volume": float(rows["valid_quote_volume"].sum()),
        "priced_volume": float(rows["valid_price_volume"].sum()),
        "signable_volume": float(rows["signable_volume"].sum()),
        "valid_count_volume": float(rows["valid_count_volume"].sum()),
        "buy_close_notional": float(rows["buy_close_notional"].sum()),
        "sell_close_notional": float(rows["sell_close_notional"].sum()),
    }


def _same_nonzero_sign(left: float, right: float) -> float:
    return float(np.sign(left) != 0.0 and np.sign(left) == np.sign(right))


def aggregate_candidate_flow(flow: pd.DataFrame, candidate: pd.Series) -> dict[str, float | pd.Timestamp]:
    """Aggregate only bars whose end timestamp is not later than the decision."""

    decision = pd.Timestamp(candidate["decision_dt"])
    history = flow[(flow["bar_end"] <= decision) & (flow["bar_start"] >= decision - pd.Timedelta(minutes=15))]
    values: dict[str, float | pd.Timestamp] = {}
    for window in WINDOWS_MINUTES:
        suffix = f"w{window}m"
        part = history[history["bar_start"] >= decision - pd.Timedelta(minutes=window)]
        by_right: dict[str, dict[str, float]] = {}
        for right in ("CALL", "PUT"):
            totals = _scope_totals(part[part["right"].eq(right)])
            by_right[right] = totals
            prefix = f"surface_{right.lower()}"
            for metric in ("volume", "count", "close_notional", "signed_volume", "signed_count", "signed_close_notional"):
                values[f"{prefix}_{metric}_{suffix}"] = totals[metric]
            values[f"{prefix}_quote_row_coverage_{suffix}"] = _safe_ratio(totals["valid_rows"], totals["rows"])
            values[f"{prefix}_quote_volume_coverage_{suffix}"] = _safe_ratio(totals["valid_volume"], totals["volume"])
            values[f"{prefix}_price_volume_coverage_{suffix}"] = _safe_ratio(totals["priced_volume"], totals["volume"])
            values[f"{prefix}_signable_volume_coverage_{suffix}"] = _safe_ratio(totals["signable_volume"], totals["volume"])
            values[f"{prefix}_count_volume_coverage_{suffix}"] = _safe_ratio(totals["valid_count_volume"], totals["volume"])
        call, put = by_right["CALL"], by_right["PUT"]
        total_volume = call["volume"] + put["volume"]
        total_count = call["count"] + put["count"]
        total_close_notional = call["close_notional"] + put["close_notional"]
        total_rows = call["rows"] + put["rows"]
        values[f"surface_directional_pressure_{suffix}"] = _safe_ratio(
            call["signed_close_notional"] - put["signed_close_notional"], total_close_notional
        )
        values[f"surface_volume_imbalance_{suffix}"] = _safe_ratio(call["volume"] - put["volume"], total_volume)
        values[f"surface_count_imbalance_{suffix}"] = _safe_ratio(call["count"] - put["count"], total_count)
        values[f"surface_close_notional_imbalance_{suffix}"] = _safe_ratio(
            call["close_notional"] - put["close_notional"], total_close_notional
        )
        values[f"surface_quote_row_coverage_{suffix}"] = _safe_ratio(
            call["valid_rows"] + put["valid_rows"], total_rows
        )
        values[f"surface_quote_volume_coverage_{suffix}"] = _safe_ratio(
            call["valid_volume"] + put["valid_volume"], total_volume
        )
        values[f"surface_price_volume_coverage_{suffix}"] = _safe_ratio(
            call["priced_volume"] + put["priced_volume"], total_volume
        )
        values[f"surface_signable_volume_coverage_{suffix}"] = _safe_ratio(
            call["signable_volume"] + put["signable_volume"], total_volume
        )
        values[f"surface_count_volume_coverage_{suffix}"] = _safe_ratio(
            call["valid_count_volume"] + put["valid_count_volume"], total_volume
        )

        radius = (part["strike"] - float(candidate["candidate_wall_strike"])).abs() / float(candidate["spot"]) * 10_000.0
        local = part[part["right"].eq(str(candidate["candidate_right"])) & radius.le(LOCAL_RADIUS_BPS)]
        totals = _scope_totals(local)
        for metric in ("volume", "count", "close_notional", "signed_volume", "signed_count", "signed_close_notional"):
            values[f"local_{metric}_{suffix}"] = totals[metric]
        values[f"local_buy_sell_close_notional_log_ratio_{suffix}"] = float(
            np.log1p(totals["buy_close_notional"]) - np.log1p(totals["sell_close_notional"])
        )
        values[f"local_signed_close_notional_ratio_{suffix}"] = _safe_ratio(
            totals["signed_close_notional"], totals["close_notional"]
        )
        values[f"local_quote_row_coverage_{suffix}"] = _safe_ratio(totals["valid_rows"], totals["rows"])
        values[f"local_quote_volume_coverage_{suffix}"] = _safe_ratio(totals["valid_volume"], totals["volume"])
        values[f"local_price_volume_coverage_{suffix}"] = _safe_ratio(totals["priced_volume"], totals["volume"])
        values[f"local_signable_volume_coverage_{suffix}"] = _safe_ratio(totals["signable_volume"], totals["volume"])
        values[f"local_count_volume_coverage_{suffix}"] = _safe_ratio(totals["valid_count_volume"], totals["volume"])
        # CALL pressure at resistance and PUT pressure at support both point in
        # the role's break direction, so no post-hoc sign flip is required.
        values[f"role_break_pressure_{suffix}"] = values[f"local_signed_close_notional_ratio_{suffix}"]

    values["surface_pressure_same_sign_1m_5m"] = _same_nonzero_sign(
        float(values["surface_directional_pressure_w1m"]), float(values["surface_directional_pressure_w5m"])
    )
    values["surface_pressure_same_sign_5m_15m"] = _same_nonzero_sign(
        float(values["surface_directional_pressure_w5m"]), float(values["surface_directional_pressure_w15m"])
    )
    values["local_pressure_same_sign_1m_5m"] = _same_nonzero_sign(
        float(values["role_break_pressure_w1m"]), float(values["role_break_pressure_w5m"])
    )
    values["local_pressure_same_sign_5m_15m"] = _same_nonzero_sign(
        float(values["role_break_pressure_w5m"]), float(values["role_break_pressure_w15m"])
    )
    values["flow_earliest_bar_start"] = history["bar_start"].min() if not history.empty else pd.NaT
    values["flow_latest_bar_start"] = history["bar_start"].max() if not history.empty else pd.NaT
    values["flow_latest_bar_end"] = history["bar_end"].max() if not history.empty else pd.NaT
    return values


def attach_flow_features(flow: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return candidates.copy()
    records: list[dict[str, Any]] = []
    for _, candidate in candidates.iterrows():
        record = candidate.to_dict()
        record.update(aggregate_candidate_flow(flow, candidate))
        records.append(record)
    out = pd.DataFrame(records).sort_values(list(KEY_COLUMNS), kind="stable").reset_index(drop=True)
    out = out[list(expected_surface_flow_columns())]
    assert_surface_flow_schema(out)
    return out


def assert_surface_flow_schema(frame: pd.DataFrame) -> None:
    expected = list(expected_surface_flow_columns())
    if list(frame.columns) != expected:
        missing = sorted(set(expected).difference(frame.columns))
        extra = sorted(set(frame.columns).difference(expected))
        raise AssertionError(f"surface-flow dataset schema/order mismatch: missing={missing} extra={extra}")
    if frame.duplicated(list(KEY_COLUMNS)).any():
        raise AssertionError("surface-flow dataset has duplicate candidate keys")
    if frame["trade_date"].astype(str).str.startswith("2026").any():
        raise AssertionError("surface-flow dataset contains forbidden 2026 rows")
    if not frame["minute"].between(FIRST_MINUTE, LAST_MINUTE).all():
        raise AssertionError("surface-flow dataset contains off-window decisions")
    if not (((frame["minute"] - FIRST_MINUTE) % CADENCE_MINUTES) == 0).all():
        raise AssertionError("surface-flow dataset contains off-grid decisions")
    if not pd.to_numeric(frame["candidate_abs_distance_bps"], errors="coerce").le(TOUCH_BPS + 1e-9).all():
        raise AssertionError("surface-flow dataset contains non-touch candidates")
    observed_end = pd.to_datetime(frame["flow_latest_bar_end"], errors="coerce")
    decision = pd.to_datetime(frame["decision_dt"], errors="coerce")
    if (observed_end.notna() & observed_end.gt(decision)).any():
        raise AssertionError("incomplete/future option bar entered a decision")
    matrix = frame[[*CONTROL_FEATURES, *FLOW_FEATURES]].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(matrix.to_numpy(dtype=float)).all():
        raise AssertionError("surface-flow control/feature allowlist contains non-finite values")
    forbidden_tokens = ("future", "outcome", "label", "pnl", "exit", "win")
    offenders = sorted(name for name in (*CONTROL_FEATURES, *FLOW_FEATURES) if any(token in name.lower() for token in forbidden_tokens))
    if offenders:
        raise AssertionError(f"forbidden feature names: {offenders}")
