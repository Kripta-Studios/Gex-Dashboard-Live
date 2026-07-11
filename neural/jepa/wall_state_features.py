"""Causal per-strike GEX/DEX wall-state feature construction.

The functions here are shared research primitives: every output at timestamp t is
computed only from the option snapshot observable at t and earlier state rows.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from training_data.stats import (
    calc_delta_adjusted_gex,
    calc_delta_ex,
    calc_dp_cdf_pdf,
    calc_gamma_ex,
)


R_RATE = 0.0325
Q_DIV = 0.0150
WALL_PERSIST_PREFIXES = (
    "call_gamma", "put_gamma", "call_delta", "put_delta", "max_dgex", "min_dgex",
)


def signed_log(value: float) -> float:
    value = float(value)
    return float(np.sign(value) * np.log1p(abs(value))) if np.isfinite(value) else float("nan")


def exact_time_to_expiry(timestamp: pd.Series) -> np.ndarray:
    ts = pd.to_datetime(timestamp, errors="coerce")
    close = ts.dt.normalize() + pd.Timedelta(hours=16)
    seconds = (close - ts).dt.total_seconds().clip(lower=60.0)
    return seconds.to_numpy(dtype=np.float64) / (3600.0 * 24.0 * 365.25)


def prepare_exposure_rows(chain: pd.DataFrame) -> pd.DataFrame:
    """Calculate row-level current-time exposures with the live formulas."""
    required = {
        "dt", "strike", "right", "underlying_price", "implied_vol", "open_interest",
    }
    missing = required.difference(chain.columns)
    if missing:
        raise KeyError(f"Missing wall-state source columns: {sorted(missing)}")
    work = chain.copy()
    work["dt"] = pd.to_datetime(work["dt"], errors="coerce").dt.floor("min")
    work["right"] = work["right"].astype(str).str.upper().str[0].map({"C": "CALL", "P": "PUT"})
    for column in ("strike", "underlying_price", "implied_vol", "open_interest"):
        work[column] = pd.to_numeric(work[column], errors="coerce")
    work = work.dropna(subset=["dt", "right", "strike", "underlying_price", "implied_vol", "open_interest"])
    work = work[
        (work["strike"] > 0.0)
        & (work["underlying_price"] > 0.0)
        & (work["implied_vol"] > 0.0)
        & (work["implied_vol"] < 2.0)
        & (work["open_interest"] > 0.0)
    ].copy()
    if work.empty:
        return work
    # A duplicated quote must not multiply daily OI exposure.
    work = work.sort_values("dt", kind="stable").drop_duplicates(
        ["dt", "strike", "right"], keep="last"
    )
    S = work["underlying_price"].to_numpy(dtype=np.float64)
    K = work["strike"].to_numpy(dtype=np.float64)
    vol = work["implied_vol"].to_numpy(dtype=np.float64)
    oi = work["open_interest"].to_numpy(dtype=np.float64)
    T = exact_time_to_expiry(work["dt"])
    valid_t = np.isfinite(T) & (T > 0.0)
    work = work.loc[valid_t].copy()
    if work.empty:
        return work
    S, K, vol, oi, T = S[valid_t], K[valid_t], vol[valid_t], oi[valid_t], T[valid_t]
    dp, cdf_dp, pdf_dp = calc_dp_cdf_pdf(S, K, vol, T, R_RATE, Q_DIV)
    gamma = calc_gamma_ex(S, vol, T, Q_DIV, oi, pdf_dp)
    call_delta = calc_delta_ex(S, T, Q_DIV, "call", oi, cdf_dp)
    put_delta = calc_delta_ex(S, T, Q_DIV, "put", oi, cdf_dp)
    call_dgex = calc_delta_adjusted_gex(gamma, cdf_dp, T, Q_DIV, "call")
    put_dgex = calc_delta_adjusted_gex(gamma, cdf_dp, T, Q_DIV, "put")
    is_call = work["right"].eq("CALL").to_numpy()
    work["call_gamma"] = np.where(is_call, gamma, 0.0)
    work["put_gamma_abs"] = np.where(~is_call, gamma, 0.0)
    work["net_gamma"] = np.where(is_call, gamma, -gamma)
    work["call_delta"] = np.where(is_call, call_delta, 0.0)
    work["put_delta_abs"] = np.where(~is_call, -put_delta, 0.0)
    work["net_delta"] = np.where(is_call, call_delta, put_delta)
    work["net_dgex"] = np.where(is_call, call_dgex, -put_dgex)
    finite_cols = [
        "call_gamma", "put_gamma_abs", "net_gamma", "call_delta",
        "put_delta_abs", "net_delta", "net_dgex",
    ]
    finite = np.isfinite(work[finite_cols].to_numpy(dtype=float)).all(axis=1)
    return (
        work.loc[finite]
        .sort_values(["dt", "strike", "right"], kind="stable")
        .reset_index(drop=True)
    )


def aggregate_by_strike(exposure_rows: pd.DataFrame) -> pd.DataFrame:
    if exposure_rows.empty:
        return pd.DataFrame()
    columns = [
        "call_gamma", "put_gamma_abs", "net_gamma", "call_delta",
        "put_delta_abs", "net_delta", "net_dgex",
    ]
    grouped = exposure_rows.groupby(["dt", "strike"], observed=True, sort=True)[columns].sum().reset_index()
    spot = exposure_rows.groupby("dt", observed=True)["underlying_price"].median().rename("spot")
    return grouped.merge(spot, left_on="dt", right_index=True, how="left", validate="many_to_one")


def _distribution_stats(scores: np.ndarray) -> tuple[float, float, float, int]:
    scores = np.asarray(scores, dtype=float)
    scores = np.where(np.isfinite(scores) & (scores > 0.0), scores, 0.0)
    total = float(scores.sum())
    active = int((scores > 0.0).sum())
    if total <= 0.0:
        return 0.0, 0.0, 0.0, active
    shares = scores / total
    hhi = float(np.square(shares).sum())
    positive = shares[shares > 0.0]
    entropy = float(-(positive * np.log(positive)).sum())
    effective = float(math.exp(entropy))
    ordered = np.sort(scores)[::-1]
    top1 = float(ordered[0])
    top2 = float(ordered[1]) if len(ordered) > 1 else 0.0
    dominance = float((top1 - top2) / top1) if top1 > 0.0 else 0.0
    return hhi, effective, dominance, active


def _wall_features(
    snapshot: pd.DataFrame,
    *,
    name: str,
    value_column: str,
    score_sign: float = 1.0,
    magnitude_sign: float = 1.0,
) -> dict[str, float]:
    values = pd.to_numeric(snapshot[value_column], errors="coerce").to_numpy(dtype=float)
    scores = score_sign * values
    valid = np.isfinite(scores) & (scores > 0.0)
    prefix = f"wall_{name}"
    if not valid.any():
        return {
            f"{prefix}_strike": float("nan"), f"{prefix}_dist_bps": float("nan"),
            f"{prefix}_magnitude_log": float("nan"), f"{prefix}_concentration": 0.0,
            f"{prefix}_dominance_gap": 0.0, f"{prefix}_active_strikes": 0,
        }
    valid_positions = np.flatnonzero(valid)
    position = int(valid_positions[np.argmax(scores[valid])])
    spot = float(snapshot["spot"].iloc[0])
    strike = float(snapshot["strike"].iloc[position])
    raw_magnitude = float(values[position]) * float(magnitude_sign)
    positive_scores = np.where(valid, scores, 0.0)
    total = float(positive_scores.sum())
    _hhi, _effective, dominance, active = _distribution_stats(positive_scores)
    return {
        f"{prefix}_strike": strike,
        f"{prefix}_dist_bps": float((spot - strike) / spot * 10_000.0),
        f"{prefix}_magnitude_log": signed_log(raw_magnitude),
        f"{prefix}_concentration": float(scores[position] / total) if total > 0.0 else 0.0,
        f"{prefix}_dominance_gap": dominance,
        f"{prefix}_active_strikes": active,
    }


def summarize_snapshot(snapshot: pd.DataFrame) -> dict[str, float | str]:
    if snapshot.empty:
        return {}
    snapshot = snapshot.sort_values("strike", kind="stable").reset_index(drop=True)
    spot = float(snapshot["spot"].iloc[0])
    result: dict[str, float | str] = {"dt": pd.Timestamp(snapshot["dt"].iloc[0]), "spot": spot}
    specs = (
        ("call_gamma", "call_gamma", 1.0, 1.0),
        ("put_gamma", "put_gamma_abs", 1.0, -1.0),
        ("call_delta", "call_delta", 1.0, 1.0),
        ("put_delta", "put_delta_abs", 1.0, -1.0),
        ("max_gamma", "net_gamma", 1.0, 1.0),
        ("min_gamma", "net_gamma", -1.0, 1.0),
        ("max_delta", "net_delta", 1.0, 1.0),
        ("min_delta", "net_delta", -1.0, 1.0),
        ("max_dgex", "net_dgex", 1.0, 1.0),
        ("min_dgex", "net_dgex", -1.0, 1.0),
    )
    for name, column, score_sign, magnitude_sign in specs:
        result.update(_wall_features(
            snapshot, name=name, value_column=column,
            score_sign=score_sign, magnitude_sign=magnitude_sign,
        ))

    families = (
        ("call_gamma", "call_gamma"), ("put_gamma", "put_gamma_abs"),
        ("call_delta", "call_delta"), ("put_delta", "put_delta_abs"),
    )
    totals = {}
    for name, column in families:
        values = pd.to_numeric(snapshot[column], errors="coerce").fillna(0.0).clip(lower=0.0).to_numpy(dtype=float)
        hhi, effective, _dominance, active = _distribution_stats(values)
        total = float(values.sum())
        totals[name] = total
        sign = -1.0 if name.startswith("put") else 1.0
        result[f"wall_{name}_total_log"] = signed_log(sign * total)
        result[f"wall_{name}_hhi"] = hhi
        result[f"wall_{name}_effective_strikes"] = effective
        result[f"wall_{name}_family_active_strikes"] = active
    for family in ("gamma", "delta"):
        call = totals[f"call_{family}"]
        put = totals[f"put_{family}"]
        result[f"wall_{family}_call_put_balance"] = float((call - put) / (call + put + 1e-12))
    result["wall_net_gamma_total_log"] = signed_log(float(snapshot["net_gamma"].sum()))
    result["wall_net_delta_total_log"] = signed_log(float(snapshot["net_delta"].sum()))
    result["wall_net_dgex_total_log"] = signed_log(float(snapshot["net_dgex"].sum()))
    result["wall_gamma_separation_bps"] = float(
        (result["wall_call_gamma_strike"] - result["wall_put_gamma_strike"]) / spot * 10_000.0
    )
    result["wall_delta_separation_bps"] = float(
        (result["wall_call_delta_strike"] - result["wall_put_delta_strike"]) / spot * 10_000.0
    )
    return result


def compute_wall_states(chain: pd.DataFrame, *, first_minute: int = 635, last_minute: int = 870, cadence: int = 5) -> pd.DataFrame:
    exposure_rows = prepare_exposure_rows(chain)
    by_strike = aggregate_by_strike(exposure_rows)
    if by_strike.empty:
        return pd.DataFrame()
    by_strike["minute"] = by_strike["dt"].dt.hour * 60 + by_strike["dt"].dt.minute
    by_strike = by_strike[
        by_strike["minute"].between(int(first_minute), int(last_minute))
        & ((by_strike["minute"] - int(first_minute)) % int(cadence) == 0)
    ].copy()
    rows = [summarize_snapshot(snapshot) for _, snapshot in by_strike.groupby("dt", observed=True, sort=True)]
    out = pd.DataFrame([row for row in rows if row])
    if out.empty:
        return out
    out["minute"] = out["dt"].dt.hour * 60 + out["dt"].dt.minute
    return out.sort_values("dt", kind="stable").reset_index(drop=True)


def add_wall_persistence(frame: pd.DataFrame) -> pd.DataFrame:
    """Add backward-looking wall stability without crossing sessions or gaps."""
    if frame.empty:
        return frame.copy()
    required = {"ticker", "trade_date", "minute", "spot"}
    missing = required.difference(frame.columns)
    if missing:
        raise KeyError(f"Missing persistence keys: {sorted(missing)}")
    out = frame.sort_values(["ticker", "trade_date", "minute"], kind="stable").copy()
    grouped = out.groupby(["ticker", "trade_date"], observed=True, sort=False)
    for prefix in WALL_PERSIST_PREFIXES:
        strike_col = f"wall_{prefix}_strike"
        magnitude_col = f"wall_{prefix}_magnitude_log"
        if strike_col not in out.columns or magnitude_col not in out.columns:
            continue
        for lag in (5, 15, 30):
            steps = lag // 5
            prior_minute = grouped["minute"].shift(steps)
            prior_strike = grouped[strike_col].shift(steps)
            prior_magnitude = grouped[magnitude_col].shift(steps)
            contiguous = prior_minute.eq(out["minute"] - lag)
            same = contiguous & np.isclose(out[strike_col], prior_strike, rtol=0.0, atol=1e-9, equal_nan=False)
            out[f"wall_{prefix}_same_{lag}m"] = same.astype(np.int8)
            out[f"wall_{prefix}_move_{lag}m_bps"] = (
                (out[strike_col] - prior_strike) / out["spot"] * 10_000.0
            ).where(contiguous)
            out[f"wall_{prefix}_magnitude_chg_{lag}m"] = (
                out[magnitude_col] - prior_magnitude
            ).where(contiguous)
        ages = np.zeros(len(out), dtype=np.int32)
        for positions in grouped.indices.values():
            previous_position: int | None = None
            for raw_position in positions:
                position = int(raw_position)
                if previous_position is not None:
                    contiguous = int(out.iloc[position]["minute"]) == int(out.iloc[previous_position]["minute"]) + 5
                    same = np.isclose(
                        float(out.iloc[position][strike_col]), float(out.iloc[previous_position][strike_col]),
                        rtol=0.0, atol=1e-9, equal_nan=False,
                    )
                    if contiguous and same:
                        ages[position] = ages[previous_position] + 5
                previous_position = position
        out[f"wall_{prefix}_age_minutes"] = ages
    return out.reset_index(drop=True)


def assert_wall_state_schema(frame: pd.DataFrame) -> None:
    forbidden = ("future", "outcome", "exit", "pnl", "return_label", "win_label")
    offenders = [column for column in frame.columns if any(token in column.lower() for token in forbidden)]
    if offenders:
        raise AssertionError(f"Outcome/future columns entered wall state: {offenders}")
    if "trade_date" in frame and frame["trade_date"].astype(str).str.startswith("2026").any():
        raise AssertionError("2026 entered wall-state features")
    concentration = [column for column in frame if column.endswith("_concentration") or column.endswith("_hhi")]
    for column in concentration:
        values = pd.to_numeric(frame[column], errors="coerce").dropna()
        if not values.between(0.0, 1.0).all():
            raise AssertionError(f"{column} outside [0,1]")
