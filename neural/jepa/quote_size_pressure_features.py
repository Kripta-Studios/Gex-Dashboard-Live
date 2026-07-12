"""Causal top-of-book quote-size pressure features for H-QSIZE1."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd


WINDOWS_MINUTES = (1, 5, 15)
RIGHTS = ("CALL", "PUT")
LOCAL_RADIUS_FRACTION = 0.015
MIN_SHARED_LOCAL_CONTRACTS = 5
MIN_CONTRACTS_EACH_SIDE = 2
MIN_SIGNABLE_LOCAL_CONTRACTS = 3
MIN_SIGNABLE_SURFACE_CONTRACTS = 5
MEASURES = (
    "local_qimb",
    "local_log_bid_depth",
    "local_log_ask_depth",
    "relative_qimb",
    "local_signable_fraction",
)
REQUIRED_COLUMNS = (
    "symbol",
    "expiration",
    "trade_date",
    "timestamp",
    "right",
    "strike",
    "bid",
    "ask",
    "bid_size",
    "ask_size",
)


def _measurement_names() -> tuple[str, ...]:
    names: list[str] = []
    for right in RIGHTS:
        prefix = f"qsize_{right.lower()}"
        names.extend(f"{prefix}_{measure}" for measure in MEASURES)
        for window in WINDOWS_MINUTES:
            names.extend(f"{prefix}_{measure}_change_{window}m" for measure in MEASURES)
    return tuple(names)


QSIZE_FEATURES = _measurement_names()
QSIZE_QUALITY_FIELDS = (
    "qsize_call_valid",
    "qsize_put_valid",
    "qsize_both_valid",
    "qsize_call_shared_local_contracts",
    "qsize_put_shared_local_contracts",
)
QSIZE_ALLOWLIST = (*QSIZE_FEATURES, *QSIZE_QUALITY_FIELDS)


def _day(value: Any) -> str:
    return "".join(character for character in str(value) if character.isdigit())[:8]


def _right(series: pd.Series) -> pd.Series:
    return series.astype(str).str.upper().str.strip().replace({"C": "CALL", "P": "PUT"})


def _frozen_contract_index(keys: Any) -> pd.MultiIndex:
    if isinstance(keys, pd.DataFrame):
        required = {"timestamp", "expiration", "right", "strike"}
        missing = required.difference(keys.columns)
        if missing:
            raise KeyError(f"frozen contract keys missing columns: {sorted(missing)}")
        frame = keys[["timestamp", "expiration", "right", "strike"]].copy()
    else:
        frame = pd.DataFrame(
            list(keys), columns=["timestamp", "expiration", "right", "strike"]
        )
    frame["snapshot_dt"] = pd.to_datetime(frame.pop("timestamp"), errors="coerce")
    frame["expiration"] = frame["expiration"].map(_day)
    frame["right"] = _right(frame["right"])
    frame["strike"] = pd.to_numeric(frame["strike"], errors="coerce")
    if (
        frame.empty
        or frame["snapshot_dt"].isna().any()
        or not (
            frame["snapshot_dt"].dt.second.eq(0)
            & frame["snapshot_dt"].dt.microsecond.eq(0)
        ).all()
        or frame["expiration"].str.len().ne(8).any()
        or not frame["right"].isin(RIGHTS).all()
        or not np.isfinite(frame["strike"]).all()
        or frame["strike"].le(0).any()
        or frame.duplicated().any()
    ):
        raise AssertionError("invalid frozen quote-size contract universe")
    return pd.MultiIndex.from_frame(
        frame[["snapshot_dt", "expiration", "right", "strike"]]
    )


def prepare_quote_size_source(
    quotes: pd.DataFrame,
    *,
    expected_ticker: str,
    expected_trade_date: str,
    frozen_contract_keys: Any,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    missing = sorted(set(REQUIRED_COLUMNS).difference(quotes.columns))
    if missing:
        raise KeyError(f"quote-size source missing columns: {missing}")
    ticker = str(expected_ticker).upper().strip()
    day = _day(expected_trade_date)
    if ticker not in {"SPXW", "QQQ", "SPY"} or len(day) != 8 or day >= "20260101":
        raise AssertionError("invalid/forbidden H-QSIZE1 session")
    frame = quotes[list(REQUIRED_COLUMNS)].copy()
    frame["symbol"] = frame["symbol"].astype(str).str.upper().str.strip()
    frame["expiration"] = frame["expiration"].map(_day)
    frame["trade_date"] = frame["trade_date"].map(_day)
    frame["right"] = _right(frame["right"])
    frame["snapshot_dt"] = pd.to_datetime(frame.pop("timestamp"), errors="coerce")
    if (
        frame["snapshot_dt"].isna().any()
        or not frame["snapshot_dt"].dt.strftime("%Y%m%d").eq(day).all()
        or not (
            frame["snapshot_dt"].dt.second.eq(0)
            & frame["snapshot_dt"].dt.microsecond.eq(0)
        ).all()
    ):
        raise AssertionError("quote-size source violates exact native minute clock")
    if (
        set(frame["symbol"].unique()) != {ticker}
        or not frame["trade_date"].eq(day).all()
        or not frame["expiration"].eq(day).all()
        or not frame["right"].isin(RIGHTS).all()
    ):
        raise AssertionError("quote-size source violates ticker/date/0DTE contract")
    for column in ("strike", "bid", "ask", "bid_size", "ask_size"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if not np.isfinite(frame["strike"]).all() or frame["strike"].le(0).any():
        raise AssertionError("quote-size source has invalid strikes")
    keys = ["symbol", "expiration", "trade_date", "snapshot_dt", "right", "strike"]
    if frame.duplicated(keys).any():
        raise AssertionError("quote-size source has duplicate exact keys")
    allowed = _frozen_contract_index(frozen_contract_keys)
    observed = pd.MultiIndex.from_frame(
        frame[["snapshot_dt", "expiration", "right", "strike"]]
    )
    keep = observed.isin(allowed)
    extras = int((~keep).sum())
    frame = frame.loc[keep].copy()
    finite = np.isfinite(frame[["bid", "ask", "bid_size", "ask_size"]]).all(axis=1)
    frame["qsize_row_signable"] = (
        finite
        & frame["bid"].gt(0)
        & frame["ask"].ge(frame["bid"])
        & frame["bid_size"].ge(0)
        & frame["ask_size"].ge(0)
        & frame["bid_size"].add(frame["ask_size"]).gt(0)
    )
    denominator = frame["bid_size"] + frame["ask_size"]
    frame["qsize_imbalance"] = np.where(
        frame["qsize_row_signable"],
        (frame["bid_size"] - frame["ask_size"]) / denominator,
        np.nan,
    )
    frame = frame.sort_values(["snapshot_dt", "right", "strike"], kind="stable").reset_index(
        drop=True
    )
    return frame, {
        "source_rows": int(len(quotes)),
        "retained_rows": int(len(frame)),
        "frozen_universe_extra_rows": extras,
        "signable_rows": int(frame["qsize_row_signable"].sum()),
        "signable_rate": float(frame["qsize_row_signable"].mean()) if len(frame) else 0.0,
        "bid_size_zero_rate": float(frame["bid_size"].eq(0).mean()) if len(frame) else 0.0,
        "ask_size_zero_rate": float(frame["ask_size"].eq(0).mean()) if len(frame) else 0.0,
    }


def _empty() -> dict[str, Any]:
    result: dict[str, Any] = {name: np.nan for name in QSIZE_FEATURES}
    result.update(
        {
            "qsize_call_valid": False,
            "qsize_put_valid": False,
            "qsize_both_valid": False,
            "qsize_call_shared_local_contracts": 0,
            "qsize_put_shared_local_contracts": 0,
        }
    )
    return result


def _clock_measurements(
    right_rows: pd.DataFrame,
    local_strikes: np.ndarray,
    clock: pd.Timestamp,
) -> dict[str, float] | None:
    current = right_rows[right_rows["snapshot_dt"].eq(clock)]
    local_all = current[current["strike"].isin(local_strikes)]
    local_valid = local_all[local_all["qsize_row_signable"]]
    surface_valid = current[current["qsize_row_signable"]]
    if (
        len(local_all) != len(local_strikes)
        or len(local_valid) < MIN_SIGNABLE_LOCAL_CONTRACTS
        or len(surface_valid) < MIN_SIGNABLE_SURFACE_CONTRACTS
    ):
        return None
    local_qimb = float(local_valid["qsize_imbalance"].median())
    return {
        "local_qimb": local_qimb,
        "local_log_bid_depth": float(np.log1p(local_valid["bid_size"].sum())),
        "local_log_ask_depth": float(np.log1p(local_valid["ask_size"].sum())),
        "relative_qimb": float(local_qimb - surface_valid["qsize_imbalance"].median()),
        "local_signable_fraction": float(len(local_valid) / len(local_strikes)),
    }


def candidate_quote_size_features(
    source: pd.DataFrame, candidate: pd.Series | Mapping[str, Any]
) -> dict[str, Any]:
    result = _empty()
    decision = pd.Timestamp(candidate["decision_dt"])
    wall, spot = float(candidate["candidate_wall_strike"]), float(candidate["spot"])
    if (
        decision.tzinfo is not None
        or decision.second
        or decision.microsecond
        or decision.strftime("%Y") == "2026"
        or not np.isfinite([wall, spot]).all()
        or min(wall, spot) <= 0
    ):
        raise AssertionError("invalid H-QSIZE1 candidate geometry/clock")
    clocks = {0: decision, **{h: decision - pd.Timedelta(minutes=h) for h in WINDOWS_MINUTES}}
    relevant = source[source["snapshot_dt"].isin(clocks.values())]
    for right in RIGHTS:
        part = relevant[relevant["right"].eq(right)]
        counts = part.groupby("strike", sort=False)["snapshot_dt"].nunique()
        shared = counts[counts.eq(len(clocks))].index.to_numpy(dtype=float)
        shared = shared[np.abs(shared - wall) / spot <= LOCAL_RADIUS_FRACTION]
        shared.sort()
        prefix = f"qsize_{right.lower()}"
        result[f"{prefix}_shared_local_contracts"] = int(len(shared))
        if (
            len(shared) < MIN_SHARED_LOCAL_CONTRACTS
            or int((shared < wall).sum()) < MIN_CONTRACTS_EACH_SIDE
            or int((shared > wall).sum()) < MIN_CONTRACTS_EACH_SIDE
        ):
            continue
        values = {lag: _clock_measurements(part, shared, clock) for lag, clock in clocks.items()}
        if any(value is None for value in values.values()):
            continue
        resolved = {lag: value for lag, value in values.items() if value is not None}
        result[f"{prefix}_valid"] = True
        for measure in MEASURES:
            result[f"{prefix}_{measure}"] = resolved[0][measure]
            for window in WINDOWS_MINUTES:
                result[f"{prefix}_{measure}_change_{window}m"] = float(
                    resolved[0][measure] - resolved[window][measure]
                )
    result["qsize_both_valid"] = bool(result["qsize_call_valid"] and result["qsize_put_valid"])
    return result


def attach_quote_size_features(candidates: pd.DataFrame, source: pd.DataFrame) -> pd.DataFrame:
    required = {"decision_dt", "candidate_wall_strike", "spot"}
    missing = sorted(required.difference(candidates.columns))
    if missing:
        raise KeyError(f"candidate frame missing fields: {missing}")
    features = pd.DataFrame(
        [candidate_quote_size_features(source, row) for _, row in candidates.iterrows()],
        index=candidates.index,
    )
    return pd.concat([candidates.copy(), features[list(QSIZE_ALLOWLIST)]], axis=1)
