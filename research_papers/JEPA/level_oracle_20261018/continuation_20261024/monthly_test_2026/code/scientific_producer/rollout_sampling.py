"""Outcome-free deterministic identity sampling; no filesystem or model access."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import Literal, Sequence

import numpy as np

SEED = 20261018
BANDS = ((60, 138), (139, 217), (218, 296), (297, 375))
CAP_PER_BAND = 32
TICKERS = frozenset(("QQQ", "SPXW", "SPY"))


def _integer(value: int, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise ValueError(f"{name} must be an exact integer")
    value = int(value)
    if not 0 <= value <= np.iinfo(np.int64).max:
        raise ValueError(f"{name} outside nonnegative int64")
    return value


def _day(ticker: str, date: str) -> None:
    if not isinstance(ticker, str) or ticker not in TICKERS:
        raise ValueError("ticker must be exactly QQQ, SPXW or SPY")
    if (
        not isinstance(date, str)
        or len(date) != 8
        or not date.isascii()
        or not date.isdecimal()
    ):
        raise ValueError("date must be YYYYMMDD")
    if datetime.strptime(date, "%Y%m%d").strftime("%Y%m%d") != date:
        raise ValueError("date must be valid YYYYMMDD")


def canonical_identity(
    seed: int, ticker: str, date: str, state_i: int, action_id: int
) -> bytes:
    """Exact serialized identity used by SHA256; no opaque delimiter convention."""
    seed = _integer(seed, "seed")
    _day(ticker, date)
    state_i = _integer(state_i, "state_i")
    action_id = _integer(action_id, "action_id")
    if not 60 <= state_i <= 375:
        raise ValueError("state_i outside 60..375")
    return json.dumps(
        [seed, ticker, date, state_i, action_id],
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _vector(values: np.ndarray, name: str) -> np.ndarray:
    values = np.asarray(values)
    if values.ndim != 1 or values.dtype.kind not in "iu":
        raise ValueError(f"{name} must be a one-dimensional integer array")
    if values.size and (np.any(values < 0) or np.any(values > np.iinfo(np.int64).max)):
        raise ValueError(f"{name} outside nonnegative int64")
    return values.astype(np.int64, copy=True)


def _readonly(values: np.ndarray) -> np.ndarray:
    values.setflags(write=False)
    return values


@dataclass(frozen=True)
class DaySample:
    ticker: str
    date: str
    seed: int
    action_id: np.ndarray
    state_i: np.ndarray
    band_i: np.ndarray
    identity_sha256: np.ndarray
    weight: np.ndarray
    population_by_band: np.ndarray
    selected_by_band: np.ndarray


def sample_day(
    ticker: str,
    date: str,
    action_id: np.ndarray,
    state_i: np.ndarray,
    *,
    seed: int = SEED,
) -> DaySample:
    """Select at most 32 offered actions per fixed band using only identities."""
    _day(ticker, date)
    seed = _integer(seed, "seed")
    if seed != SEED:
        raise ValueError("method seed is fixed at 20261018")
    ids, states = _vector(action_id, "action_id"), _vector(state_i, "state_i")
    if ids.shape != states.shape or len(np.unique(ids)) != len(ids):
        raise ValueError(
            "identities must align and action_id must be unique within day"
        )
    if np.any((states < 60) | (states > 375)):
        raise ValueError("state_i outside 60..375")
    bands = (states - 60) // 79
    populations = np.bincount(bands, minlength=4).astype(np.int64)
    digests = [
        hashlib.sha256(
            canonical_identity(seed, ticker, date, int(s), int(a))
        ).hexdigest()
        for a, s in zip(ids, states)
    ]
    selected: list[int] = []
    for band in range(4):
        rows = np.flatnonzero(bands == band).tolist()
        rows.sort(
            key=lambda j: (digests[j], seed, ticker, date, int(states[j]), int(ids[j]))
        )
        selected.extend(rows[:CAP_PER_BAND])
    ix = np.array(selected, dtype=np.int64)
    selected_counts = np.minimum(populations, CAP_PER_BAND)
    weights = np.array(
        [
            populations[bands[j]] / (len(ids) * selected_counts[bands[j]])
            for j in selected
        ],
        dtype=np.float64,
    )
    return DaySample(
        ticker,
        date,
        seed,
        _readonly(ids[ix]),
        _readonly(states[ix]),
        _readonly(bands[ix]),
        _readonly(np.array([digests[j] for j in selected], dtype="U64")),
        _readonly(weights),
        _readonly(populations),
        _readonly(selected_counts),
    )


@dataclass(frozen=True)
class FitSample:
    role: str
    ticker: np.ndarray
    date: np.ndarray
    action_id: np.ndarray
    state_i: np.ndarray
    band_i: np.ndarray
    identity_sha256: np.ndarray
    has_filled_today: np.ndarray | None
    weight: np.ndarray
    fit_weight: np.ndarray
    n_days: int
    normalization_factor: float


def _validate_sample(sample: DaySample) -> None:
    _day(sample.ticker, sample.date)
    if sample.seed != SEED:
        raise ValueError("sample seed mismatch")
    ids, states = (
        _vector(sample.action_id, "action_id"),
        _vector(sample.state_i, "state_i"),
    )
    n = len(ids)
    if not n or ids.shape != states.shape or len(np.unique(ids)) != n:
        raise ValueError("fit requires nonempty days with unique aligned identities")
    if np.any((states < 60) | (states > 375)):
        raise ValueError("state outside method horizon")
    pop = _vector(sample.population_by_band, "population_by_band")
    selected = _vector(sample.selected_by_band, "selected_by_band")
    bands = _vector(sample.band_i, "band_i")
    if (
        pop.shape != (4,)
        or selected.shape != (4,)
        or not np.array_equal(selected, np.minimum(pop, CAP_PER_BAND))
    ):
        raise ValueError("invalid band population/selection counts")
    if not np.array_equal(bands, (states - 60) // 79) or not np.array_equal(
        np.bincount(bands, minlength=4), selected
    ):
        raise ValueError("sample band membership/count mismatch")
    expected = pop[bands] / (int(pop.sum()) * selected[bands])
    if np.asarray(sample.weight).dtype != np.dtype("float64") or not np.array_equal(
        sample.weight, expected
    ):
        raise ValueError("sample IPW weights mismatch")
    hashes = np.array(
        [
            hashlib.sha256(
                canonical_identity(SEED, sample.ticker, sample.date, int(s), int(a))
            ).hexdigest()
            for a, s in zip(ids, states)
        ],
        dtype="U64",
    )
    if not np.array_equal(hashes, sample.identity_sha256):
        raise ValueError("sample identity digest mismatch")
    order = sorted(
        range(n), key=lambda j: (int(bands[j]), hashes[j], int(states[j]), int(ids[j]))
    )
    if order != list(range(n)):
        raise ValueError("sample rows must retain canonical band/hash order")


def prepare_fit_rows(
    samples: Sequence[DaySample], *, role: Literal["teacher", "final"]
) -> FitSample:
    """Assemble identity/weight pack only; never assemble features or targets."""
    if role not in ("teacher", "final") or not samples:
        raise ValueError("nonempty sample sequence and teacher/final role required")
    ordered = sorted(samples, key=lambda s: (s.ticker, s.date))
    if len({(s.ticker, s.date) for s in ordered}) != len(ordered):
        raise ValueError("duplicate ticker-day")
    for sample in ordered:
        _validate_sample(sample)
        low, high = (
            ("20230101", "20230630") if role == "teacher" else ("20230701", "20241231")
        )
        if not low <= sample.date <= high:
            raise ValueError("sample date outside role training period")
    ticker = np.concatenate(
        [np.full(len(s.action_id), s.ticker, dtype="U4") for s in ordered]
    )
    date = np.concatenate(
        [np.full(len(s.action_id), s.date, dtype="U8") for s in ordered]
    )
    arrays = [ticker, date] + [
        np.concatenate([getattr(s, key) for s in ordered])
        for key in ("action_id", "state_i", "band_i", "identity_sha256")
    ]
    weight = np.concatenate([s.weight for s in ordered])
    h = None
    if role == "final":
        arrays = [np.repeat(a, 2) for a in arrays]
        h = _readonly(np.tile(np.array([0, 1], dtype=np.int8), len(weight)))
        weight = np.repeat(weight / 2, 2)
    factor = len(weight) / len(ordered)
    fit_weight = weight * factor
    return FitSample(
        role,
        *[_readonly(a) for a in arrays],
        h,
        _readonly(weight),
        _readonly(fit_weight),
        len(ordered),
        factor,
    )
