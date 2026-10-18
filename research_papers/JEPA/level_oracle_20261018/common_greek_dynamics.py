"""Feature-only common-contract sensitivities; no targets, models or evaluation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

import level_engine as engine

GREEKS = ("gamma_bs_proxy", "delta_stored", "vega_per_vol_point", "theta_stored")
SIDES = ("CALL", "PUT")
LAGS = (5, 15)
FIELDS = (
    "available",
    "common_count_log1p",
    "common_known_now_fraction",
    "common_known_past_fraction",
    "common_eligible_now_fraction",
    "common_eligible_past_fraction",
    "observed_abs_mass_now_fraction",
    "observed_abs_mass_past_fraction",
    "observed_abs_mass_now_positive",
    "observed_abs_mass_past_positive",
    "common_signed_logmass_now",
    "common_signed_logmass_past",
    "common_relative_change",
    "fixed_oi_greek_relative_change",
    "reported_oi_relative_change",
    "composition_relative_change",
    "common_oi_relative_change",
)
FEATURE_NAMES = tuple(
    f"{greek}_{side}_{lag}m_{field}"
    for greek in GREEKS
    for side in SIDES
    for lag in LAGS
    for field in FIELDS
)


@dataclass
class DayDynamics:
    raw: dict
    oi: np.ndarray
    known: np.ndarray
    unit: dict[str, np.ndarray]
    valid: dict[str, np.ndarray]
    close_i: int


def prepare_day(raw, *, close_i):
    if close_i not in (210, 390):
        raise ValueError("Explicit calendar session close must be210 or390")
    oi = engine.available_oi_matrix(raw)
    known = engine.known_contract_matrix(raw)
    spot = np.asarray(raw["spot"], dtype=np.float64)
    flags = np.asarray(raw["row_flags"], dtype=np.uint8)
    present = (flags & 1) != 0
    underlying_valid = (flags & 4) != 0
    valid_spot = (
        np.asarray(raw["spot_valid"], dtype=bool) & np.isfinite(spot) & (spot > 0)
    )
    base = (
        present & underlying_valid & valid_spot[:, None] & np.isfinite(oi) & (oi >= 0)
    )
    base[np.arange(len(base)) >= close_i] = False
    iv = np.asarray(raw["iv"], dtype=np.float64)
    delta = np.asarray(raw["delta"], dtype=np.float64)
    vega = np.asarray(raw["vega"], dtype=np.float64)
    theta = np.asarray(raw["theta"], dtype=np.float64)
    unit = {
        GREEKS[0]: np.full(oi.shape, np.nan),
        GREEKS[1]: delta,
        GREEKS[2]: vega / 100.0,
        GREEKS[3]: theta,
    }
    valid = {
        GREEKS[0]: base & np.isfinite(iv) & (iv > 0) & (iv <= 5),
        GREEKS[1]: base & np.isfinite(delta) & (np.abs(delta) <= 1),
        GREEKS[2]: base & np.isfinite(vega) & (vega >= 0),
        GREEKS[3]: base & np.isfinite(theta),
    }
    strike = np.asarray(raw["strike"], dtype=np.float64)
    for minute in range(close_i):
        good = valid[GREEKS[0]][minute]
        tau = (close_i - minute) * 60 / (365 * 86400)
        sigma = iv[minute, good]
        d1 = (np.log(spot[minute] / strike[good]) + 0.5 * sigma * sigma * tau) / (
            sigma * np.sqrt(tau)
        )
        unit[GREEKS[0]][minute, good] = (
            np.exp(-0.5 * d1 * d1)
            * spot[minute]
            / (np.sqrt(2 * np.pi) * sigma * np.sqrt(tau))
        )
    for name in GREEKS:
        with np.errstate(over="ignore", invalid="ignore"):
            valid[name] &= np.isfinite(unit[name] * oi)
    return DayDynamics(raw, oi, known, unit, valid, close_i)


def divide(num, den):
    return num / den if den > 0 else 0.0


def signed_log(value):
    return np.sign(value) * np.log1p(abs(value))


def encode_state(day, minute):
    if (
        not isinstance(minute, (int, np.integer))
        or not 60 <= minute <= day.close_i - 15
    ):
        raise ValueError("State outside declared causal decision session")
    rows = []
    for greek in GREEKS:
        for side in (0, 1):
            side_mask = np.asarray(day.raw["right"]) == side
            for lag in LAGS:
                past = minute - lag
                now_valid = day.valid[greek][minute] & side_mask
                past_valid = day.valid[greek][past] & side_mask
                common = now_valid & past_valid
                count = int(common.sum())
                values = np.zeros(len(FIELDS), dtype=np.float64)
                if count:
                    now_all = (
                        day.unit[greek][minute, now_valid] * day.oi[minute, now_valid]
                    )
                    past_all = (
                        day.unit[greek][past, past_valid] * day.oi[past, past_valid]
                    )
                    now = day.unit[greek][minute, common] * day.oi[minute, common]
                    before = day.unit[greek][past, common] * day.oi[past, common]
                    fixed_oi = (
                        day.unit[greek][minute, common] * day.oi[past, common]
                    ).sum()
                    now_sum, past_sum = now.sum(), before.sum()
                    now_abs, past_abs = np.abs(now_all).sum(), np.abs(past_all).sum()
                    common_abs = np.abs(now).sum() + np.abs(before).sum()
                    values[:] = (
                        1.0,
                        np.log1p(count),
                        divide(count, (day.known[minute] & side_mask).sum()),
                        divide(count, (day.known[past] & side_mask).sum()),
                        divide(count, now_valid.sum()),
                        divide(count, past_valid.sum()),
                        divide(np.abs(now).sum(), now_abs),
                        divide(np.abs(before).sum(), past_abs),
                        float(now_abs > 0),
                        float(past_abs > 0),
                        signed_log(now_sum),
                        signed_log(past_sum),
                        divide(now_sum - past_sum, common_abs),
                        divide(fixed_oi - past_sum, common_abs),
                        divide(now_sum - fixed_oi, common_abs),
                        divide(
                            (now_all.sum() - now_sum) - (past_all.sum() - past_sum),
                            now_abs + past_abs,
                        ),
                        divide(
                            np.abs(day.oi[minute, common] - day.oi[past, common]).sum(),
                            (day.oi[minute, common] + day.oi[past, common]).sum(),
                        ),
                    )
                rows.extend(values)
    result = np.asarray(rows, dtype=np.float32)
    if result.shape != (272,) or not np.isfinite(result).all():
        raise ValueError("Nonfinite or invalid dynamic feature vector")
    return result


def append_to_compact(compact152, dynamics272):
    compact, dynamic = np.asarray(compact152), np.asarray(dynamics272)
    if compact.dtype != np.float32 or compact.ndim != 2 or compact.shape[1] != 152:
        raise ValueError("Original compact prefix must be exact float32 Nx152")
    if dynamic.dtype != np.float32 or dynamic.shape != (len(compact), 272):
        raise ValueError("Dynamics must be aligned float32 Nx272")
    if not np.isfinite(compact).all() or not np.isfinite(dynamic).all():
        raise ValueError(
            "Feature arrays must be finite, with explicit validity channels"
        )
    result = np.concatenate((compact, dynamic), axis=1)
    if not np.array_equal(result[:, :152].view(np.uint32), compact.view(np.uint32)):
        raise AssertionError("Original compact prefix changed")
    return result


def encode_states(day, indices):
    """Preserve caller order and duplicates; state indices are join keys, not features."""
    indices = np.asarray(indices)
    if indices.ndim != 1 or not np.issubdtype(indices.dtype, np.integer):
        raise ValueError("State join indices must be a one-dimensional integer array")
    if not len(indices):
        return np.empty((0, 272), dtype=np.float32)
    vectors = {int(index): encode_state(day, int(index)) for index in np.unique(indices)}
    return np.stack([vectors[int(index)] for index in indices])
