"""Causal fixed-contract IV-surface deformation features for H-IVSURF1.

This module contains no outcome, payoff, or model logic.  The caller must
restore and audit the native option clock before calling
``prepare_iv_surface_source``; an ``underlying_timestamp`` is accepted only as
an additional equality check and is never used as a clock fallback.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd


WINDOWS_MINUTES = (1, 5, 15)
RIGHTS = ("CALL", "PUT")
SURFACE_RADIUS_FRACTION = 0.015
MIN_SHARED_STRIKES = 5
MIN_STRIKES_EACH_SIDE = 2
MAX_ABS_IV_ERROR = 0.10
MAX_IMPLIED_VOL = 2.0

REQUIRED_GREEK_COLUMNS = (
    "symbol",
    "expiration",
    "trade_date",
    "timestamp",
    "right",
    "strike",
    "implied_vol",
    "iv_error",
    "bid",
    "ask",
)


def _feature_names() -> tuple[str, ...]:
    return tuple(
        f"surface_{right.lower()}_{measure}_change_{window}m"
        for window in WINDOWS_MINUTES
        for right in RIGHTS
        for measure in ("level", "skew", "curvature")
    )


IV_SURFACE_FEATURES = _feature_names()
IV_SURFACE_QUALITY_FIELDS = (
    "surface_call_valid",
    "surface_put_valid",
    "surface_both_valid",
    "surface_call_shared_strikes",
    "surface_put_shared_strikes",
)
IV_SURFACE_ALLOWLIST = (*IV_SURFACE_FEATURES, *IV_SURFACE_QUALITY_FIELDS)

# Short aliases used by dataset builders.
SURFACE_FEATURES = IV_SURFACE_FEATURES
QUALITY_FEATURES = IV_SURFACE_QUALITY_FIELDS


def _day(value: Any) -> str:
    digits = "".join(character for character in str(value) if character.isdigit())
    return digits[:8]


def _expiration_day(series: pd.Series) -> pd.Series:
    return series.map(_day)


def _normalize_right(series: pd.Series) -> pd.Series:
    return series.astype(str).str.upper().str.strip().replace({"C": "CALL", "P": "PUT"})


def _normalize_frozen_contract_keys(keys: Any) -> pd.MultiIndex:
    """Return normalized (expiration, right, strike) keys."""

    if isinstance(keys, pd.DataFrame):
        required = {"expiration", "right", "strike"}
        missing = required.difference(keys.columns)
        if missing:
            raise KeyError(f"frozen contract keys missing columns: {sorted(missing)}")
        frame = keys[["expiration", "right", "strike"]].copy()
    else:
        frame = pd.DataFrame(list(keys), columns=["expiration", "right", "strike"])
    frame["expiration"] = _expiration_day(frame["expiration"])
    frame["right"] = _normalize_right(frame["right"])
    frame["strike"] = pd.to_numeric(frame["strike"], errors="coerce")
    if (
        frame.empty
        or frame["expiration"].str.len().ne(8).any()
        or not frame["right"].isin(RIGHTS).all()
        or not np.isfinite(frame["strike"]).all()
        or frame["strike"].le(0.0).any()
        or frame.duplicated().any()
    ):
        raise AssertionError("invalid or duplicate frozen contract keys")
    return pd.MultiIndex.from_frame(frame)


def prepare_iv_surface_source(
    greeks: pd.DataFrame,
    *,
    expected_ticker: str,
    expected_trade_date: str,
    frozen_contract_keys: Any | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Normalize one 0DTE first-order surface without dropping invalid quotes.

    ``timestamp`` must already be the audited native option clock.  Rows outside
    the frozen Greek universe are counted and removed before feature creation.
    Quote/IV validity is stored per row so invalid candidate geometry can be
    retained later rather than silently changing the candidate universe.
    """

    missing = sorted(set(REQUIRED_GREEK_COLUMNS).difference(greeks.columns))
    if missing:
        raise KeyError(f"Greek surface missing required columns: {missing}")

    ticker = str(expected_ticker).upper().strip()
    day = _day(expected_trade_date)
    columns = list(REQUIRED_GREEK_COLUMNS)
    if "underlying_timestamp" in greeks.columns:
        columns.append("underlying_timestamp")
    if "interval_used" in greeks.columns:
        columns.append("interval_used")
    frame = greeks[columns].copy()
    frame["symbol"] = frame["symbol"].astype(str).str.upper().str.strip()
    frame["trade_date"] = frame["trade_date"].map(_day)
    frame["expiration"] = _expiration_day(frame["expiration"])
    frame["right"] = _normalize_right(frame["right"])

    if ticker not in {"SPXW", "QQQ", "SPY"} or len(day) != 8:
        raise AssertionError("invalid expected ticker/date")
    if day.startswith("2026"):
        raise AssertionError("2026 is outside the sealed H-IVSURF1 source period")
    if set(frame["symbol"].unique()) != {ticker} or not frame["trade_date"].eq(day).all():
        raise AssertionError("Greek surface symbol/trade-date mismatch")
    if not frame["expiration"].eq(day).all():
        raise AssertionError("Greek surface is not exclusively current-session 0DTE")
    if not frame["right"].isin(RIGHTS).all():
        raise AssertionError("Greek surface contains unknown option rights")
    if "interval_used" in frame and not frame["interval_used"].astype(str).eq("1m").all():
        raise AssertionError("Greek surface requires interval_used=1m")

    frame["snapshot_dt"] = pd.to_datetime(frame.pop("timestamp"), errors="coerce")
    if frame["snapshot_dt"].isna().any():
        raise AssertionError("Greek surface contains missing/unparseable native timestamps")
    if getattr(frame["snapshot_dt"].dt, "tz", None) is not None:
        raise AssertionError("Greek surface timestamps must be timezone-naive ET")
    boundary = frame["snapshot_dt"].dt.second.eq(0) & frame["snapshot_dt"].dt.microsecond.eq(0)
    if not boundary.all() or not frame["snapshot_dt"].dt.strftime("%Y%m%d").eq(day).all():
        raise AssertionError("Greek surface contains non-boundary or wrong-session timestamps")
    if "underlying_timestamp" in frame:
        underlying_dt = pd.to_datetime(frame.pop("underlying_timestamp"), errors="coerce")
        if underlying_dt.isna().any() or not underlying_dt.eq(frame["snapshot_dt"]).all():
            raise AssertionError("native option timestamp and underlying_timestamp differ")

    numeric = ("strike", "implied_vol", "iv_error", "bid", "ask")
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if not np.isfinite(frame["strike"]).all() or frame["strike"].le(0.0).any():
        raise AssertionError("Greek surface contains invalid normalized contract strikes")
    normalized_key = ["symbol", "expiration", "trade_date", "snapshot_dt", "right", "strike"]
    if frame.duplicated(normalized_key).any():
        raise AssertionError("Greek surface contains duplicate normalized contract/minute keys")

    source_rows = len(frame)
    extras = 0
    if frozen_contract_keys is not None:
        allowed = _normalize_frozen_contract_keys(frozen_contract_keys)
        observed = pd.MultiIndex.from_frame(frame[["expiration", "right", "strike"]])
        keep = observed.isin(allowed)
        extras = int((~keep).sum())
        frame = frame.loc[keep].copy()

    finite = np.isfinite(frame[["implied_vol", "iv_error", "bid", "ask"]]).all(axis=1)
    frame["surface_row_valid"] = (
        finite
        & frame["implied_vol"].gt(0.0)
        & frame["implied_vol"].lt(MAX_IMPLIED_VOL)
        & frame["bid"].gt(0.0)
        & frame["ask"].ge(frame["bid"])
        & frame["iv_error"].abs().le(MAX_ABS_IV_ERROR)
    )
    frame = frame.sort_values(["snapshot_dt", "right", "strike"], kind="stable").reset_index(drop=True)
    audit = {
        "source_rows": int(source_rows),
        "retained_rows": int(len(frame)),
        "frozen_universe_extra_rows": int(extras),
        "valid_rows": int(frame["surface_row_valid"].sum()),
        "invalid_rows": int((~frame["surface_row_valid"]).sum()),
        "timestamp_min": frame["snapshot_dt"].min() if not frame.empty else pd.NaT,
        "timestamp_max": frame["snapshot_dt"].max() if not frame.empty else pd.NaT,
    }
    return frame, audit


def _empty_features() -> dict[str, Any]:
    result: dict[str, Any] = {name: np.nan for name in IV_SURFACE_FEATURES}
    result.update(
        {
            "surface_call_valid": False,
            "surface_put_valid": False,
            "surface_both_valid": False,
            "surface_call_shared_strikes": 0,
            "surface_put_shared_strikes": 0,
        }
    )
    return result


def _fit_equal_weight_quadratic(strikes: np.ndarray, iv: np.ndarray, wall: float) -> np.ndarray:
    x = np.log(strikes / wall) / SURFACE_RADIUS_FRACTION
    design = np.column_stack((np.ones(len(x)), x, x * x))
    coefficients, _, rank, _ = np.linalg.lstsq(design, iv, rcond=None)
    if rank != 3 or not np.isfinite(coefficients).all():
        raise ArithmeticError("local IV quadratic is rank deficient")
    return coefficients


def candidate_iv_surface_features(
    surface: pd.DataFrame,
    candidate: pd.Series | Mapping[str, Any],
) -> dict[str, Any]:
    """Compute the frozen 18 deformation features for one candidate row."""

    result = _empty_features()
    decision = pd.Timestamp(candidate["decision_dt"])
    wall = float(candidate["candidate_wall_strike"])
    spot = float(candidate["spot"])
    if decision.tzinfo is not None:
        raise AssertionError("candidate decision timestamp must be timezone-naive ET")
    if decision.second or decision.microsecond:
        raise AssertionError("candidate decision timestamp must be an exact minute")
    if not np.isfinite(wall) or wall <= 0.0 or not np.isfinite(spot) or spot <= 0.0:
        raise AssertionError("candidate wall/spot must be finite and positive")
    if decision.strftime("%Y").startswith("2026"):
        raise AssertionError("2026 candidate entered sealed H-IVSURF1")

    clocks = {0: decision, **{window: decision - pd.Timedelta(minutes=window) for window in WINDOWS_MINUTES}}
    relevant = surface[surface["snapshot_dt"].isin(clocks.values())].copy()
    for right in RIGHTS:
        part = relevant[(relevant["right"] == right) & relevant["surface_row_valid"]]
        counts = part.groupby("strike", sort=False)["snapshot_dt"].nunique()
        shared = counts[counts.eq(len(clocks))].index.to_numpy(dtype=float)
        shared = shared[np.abs(shared - wall) / spot <= SURFACE_RADIUS_FRACTION]
        shared.sort()
        key = right.lower()
        result[f"surface_{key}_shared_strikes"] = int(len(shared))
        geometry_valid = (
            len(shared) >= MIN_SHARED_STRIKES
            and int((shared < wall).sum()) >= MIN_STRIKES_EACH_SIDE
            and int((shared > wall).sum()) >= MIN_STRIKES_EACH_SIDE
        )
        if not geometry_valid:
            continue

        coefficients: dict[int, np.ndarray] = {}
        try:
            for lag, clock in clocks.items():
                clock_rows = part[(part["snapshot_dt"] == clock) & part["strike"].isin(shared)]
                clock_rows = clock_rows.set_index("strike").loc[shared]
                coefficients[lag] = _fit_equal_weight_quadratic(
                    shared,
                    clock_rows["implied_vol"].to_numpy(dtype=float),
                    wall,
                )
        except (KeyError, ArithmeticError):
            continue

        result[f"surface_{key}_valid"] = True
        current = coefficients[0]
        for window in WINDOWS_MINUTES:
            lagged = coefficients[window]
            result[f"surface_{key}_level_change_{window}m"] = float(current[0] - lagged[0])
            result[f"surface_{key}_skew_change_{window}m"] = float(current[1] - lagged[1])
            result[f"surface_{key}_curvature_change_{window}m"] = float(2.0 * (current[2] - lagged[2]))

    result["surface_both_valid"] = bool(result["surface_call_valid"] and result["surface_put_valid"])
    return result


def attach_iv_surface_features(candidates: pd.DataFrame, surface: pd.DataFrame) -> pd.DataFrame:
    """Attach features while preserving every input candidate and its order."""

    required = {"decision_dt", "candidate_wall_strike", "spot"}
    missing = sorted(required.difference(candidates.columns))
    if missing:
        raise KeyError(f"candidate frame missing required columns: {missing}")
    features = pd.DataFrame(
        [candidate_iv_surface_features(surface, row) for _, row in candidates.iterrows()],
        index=candidates.index,
    )
    return pd.concat([candidates.copy(), features[list(IV_SURFACE_ALLOWLIST)]], axis=1)

