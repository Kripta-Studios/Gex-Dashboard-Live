"""Same candle/map representation with an explicit physical session clock.

No outcomes or file I/O. Full-session paths delegate frozen functions unchanged.
Time and bar age retain /390 units; remaining time uses the actual NYSE close.
"""

from dataclasses import dataclass
import numpy as np

try:
    from . import features as frozen
    from . import session_level_engine as level_engine
    from .session_clock import FULL, SessionClock
except ImportError:
    import features as frozen
    import session_level_engine as level_engine
    from session_clock import FULL, SessionClock

VERSION = "SESSION_CLOCK_FEATURES_V1"
GRID = frozen.GRID
MAP_NAMES = frozen.MAP_NAMES
SIDE_CONTEXT = frozen.SIDE_CONTEXT
CONTEXT_NAMES = frozen.CONTEXT_NAMES
GEOMETRY_NAMES = frozen.GEOMETRY_NAMES
TOKEN_NAMES = frozen.TOKEN_NAMES
BASE_NAMES = frozen.BASE_NAMES
ACTION_NAMES = frozen.ACTION_NAMES
ACTION_INPUT_NAMES = frozen.ACTION_INPUT_NAMES
_mean = frozen._mean
_safe = frozen._safe
flatten_state_features = frozen.flatten_state_features


@dataclass
class DayFeatureCache(frozen.DayFeatureCache):
    clock: SessionClock = FULL


def build_day_feature_cache(raw: dict, clock: SessionClock = FULL) -> DayFeatureCache:
    """Build only small daily intermediates; no economic outcomes are accepted."""
    if clock.is_full:
        return frozen.build_day_feature_cache(raw)
    level_engine.validate_cache(raw, clock)
    spot = np.asarray(raw["spot"], dtype=np.float64)
    spot_valid = (
        np.asarray(raw["spot_valid"], dtype=bool) & np.isfinite(spot) & (spot > 0)
    )
    initial = spot[:60][spot_valid[:60]]
    low = float(initial.min()) if len(initial) else np.nan
    high = float(initial.max()) if len(initial) else np.nan
    ib_valid = len(initial) >= 57 and high > low
    width = high - low if ib_valid else 1.0
    strike = np.asarray(raw["strike"], dtype=np.float64)
    side = np.asarray(raw["right"])
    coordinate = (strike - low) / width if ib_valid else np.zeros(len(strike))
    kernels = np.exp(-0.5 * ((GRID[None, :] - coordinate[:, None]) / 0.08) ** 2)
    outside = (coordinate < GRID[0]) | (coordinate > GRID[-1])
    oi = level_engine.available_oi_matrix(raw, clock)
    present = (np.asarray(raw["row_flags"], dtype=np.uint8) & 1) != 0
    # The rectangular cache contains a union of contracts across the entire day.
    # Denominators must use identities already observed, never the union size.
    visible = level_engine.known_contract_matrix(raw)
    context = np.full((clock.n_slots, len(CONTEXT_NAMES)), np.nan, dtype=np.float64)
    walls = np.zeros((clock.n_slots, 4, 3, 3), dtype=np.float64)
    maps = np.zeros((clock.n_slots, 5, 64), dtype=np.float64)
    map_known = np.zeros((clock.n_slots, 5), dtype=bool)
    fib = np.exp(
        -0.5 * ((GRID[None, :] - level_engine.RATIOS[:, None]) / 0.08) ** 2
    ).sum(axis=0)
    if ib_valid:
        maps[:, 0] = fib
        map_known[:, 0] = True
    for minute in range(clock.n_slots):
        gamma = level_engine.bs_gamma_density(raw, minute, oi[minute], clock)
        weights = [
            np.where(side == 0, oi[minute], np.nan),
            np.where(side == 1, oi[minute], np.nan),
            np.where(side == 0, gamma, np.nan),
            np.where(side == 1, gamma, np.nan),
        ]
        for channel, mass in enumerate(weights):
            known = np.isfinite(mass)
            positive = known & (mass > 0)
            if ib_valid and known.any():
                map_known[minute, channel + 1] = True
                # Active-only reduction also avoids future-only cache identities
                # changing floating-point reduction shapes for an earlier state.
                maps[minute, channel + 1] = (
                    mass[positive, None] * kernels[positive]
                ).sum(axis=0)
                total = mass[positive].sum()
                context[minute, 2 * len(SIDE_CONTEXT) + channel] = (
                    mass[positive & outside].sum() / total if total > 0 else 0.0
                )
                indices = np.flatnonzero(positive)
                ordered = indices[np.lexsort((strike[indices], -mass[indices]))][:3]
                for rank, contract in enumerate(ordered):
                    walls[minute, channel, rank] = (
                        coordinate[contract],
                        np.log1p(mass[contract]),
                        1.0,
                    )
        for direction in (0, 1):
            selected = (side == direction) & present[minute]
            iv = np.asarray(raw["iv"][minute])
            delta = np.asarray(raw["delta"][minute])
            vega = np.asarray(raw["vega"][minute])
            theta = np.asarray(raw["theta"][minute])
            iv_ok = selected & np.isfinite(iv) & (iv > 0) & (iv <= 5)
            delta_ok = selected & np.isfinite(delta) & (np.abs(delta) <= 1)
            vega_ok = selected & np.isfinite(vega) & (vega >= 0)
            theta_ok = selected & np.isfinite(theta)
            known_oi = (side == direction) & np.isfinite(oi[minute])
            known_gamma = (side == direction) & np.isfinite(gamma)
            n_present = int(selected.sum())
            n_visible = int(((side == direction) & visible[minute]).sum())
            n_oi = int(known_oi.sum())
            quote_ok = selected & (
                (np.asarray(raw["row_flags"][minute], dtype=np.uint8) & 2) != 0
            )
            values = [
                _mean(iv[iv_ok]),
                _mean(np.abs(delta[delta_ok])),
                _mean(vega[vega_ok]) / spot[minute] if spot_valid[minute] else np.nan,
                _mean(theta[theta_ok]) / spot[minute] if spot_valid[minute] else np.nan,
                np.log1p(oi[minute, known_oi].sum()) if n_oi else np.nan,
                np.log1p(gamma[known_gamma].sum()) if known_gamma.any() else np.nan,
                quote_ok.sum() / n_present if n_present else 0.0,
                iv_ok.sum() / n_present if n_present else 0.0,
                n_oi / n_visible if n_visible else 0.0,
                (oi[minute, known_oi] > 0).sum() / n_oi if n_oi else 0.0,
                n_present / n_visible if n_visible else 0.0,
                delta_ok.sum() / n_present if n_present else 0.0,
                vega_ok.sum() / n_present if n_present else 0.0,
                theta_ok.sum() / n_present if n_present else 0.0,
            ]
            context[
                minute,
                direction * len(SIDE_CONTEXT) : (direction + 1) * len(SIDE_CONTEXT),
            ] = values
    bars = {}
    for duration in (5, 15):
        rows = []
        for start in range(0, clock.n_slots - duration + 1, duration):
            stop = start + duration
            valid = spot_valid[start:stop]
            values = spot[start:stop][valid]
            ohlc = (
                (values[0], values.max(), values.min(), values[-1])
                if len(values)
                else (np.nan,) * 4
            )
            known = map_known[start:stop]
            count = known.sum(axis=0)
            mean_map = np.divide(
                maps[start:stop].sum(axis=0),
                count[:, None],
                out=np.zeros((5, 64)),
                where=count[:, None] > 0,
            )
            maximum = mean_map.max(axis=1, keepdims=True)
            normalized = np.divide(
                mean_map, maximum, out=np.zeros_like(mean_map), where=maximum > 0
            )
            rows.append(
                dict(
                    end=stop - 1,
                    ohlc=np.asarray(ohlc),
                    fraction=valid.mean(),
                    last_age=(duration - 1 - np.flatnonzero(valid)[-1]) / duration
                    if valid.any()
                    else 1.0,
                    context=_mean(context[start:stop], axis=0),
                    maps=normalized,
                    map_mask=count / duration,
                    token_mask=bool(valid.any()),
                )
            )
        bars[duration] = rows
    return DayFeatureCache(
        raw,
        spot,
        spot_valid,
        low,
        high,
        len(initial),
        ib_valid,
        context,
        walls,
        bars,
        clock,
    )


def encode_state(cache: DayFeatureCache, minute: int) -> dict[str, np.ndarray]:
    """Every numerical output is finite float32; masks retain missing information."""
    clock = getattr(cache, "clock", FULL)
    if clock.is_full:
        return frozen.encode_state(cache, minute)
    if (
        not isinstance(minute, (int, np.integer))
        or minute < 60
        or minute > clock.last_state
    ):
        raise ValueError(f"Decision indices must be integers in 60..{clock.last_state}")
    width = cache.ib_high - cache.ib_low if cache.ib_valid else 1.0
    spot = cache.spot[minute] if cache.spot_valid[minute] else np.nan
    changes, change_masks = [], []
    for lag in (1, 5, 15):
        good = bool(
            cache.spot_valid[minute]
            and cache.spot_valid[minute - lag]
            and cache.ib_valid
        )
        changes.append((spot - cache.spot[minute - lag]) / width if good else 0.0)
        change_masks.append(float(good))
    base = [
        minute / 390,
        (clock.close_i - minute) / 390,
        float(cache.spot_valid[minute]),
        float(cache.ib_valid),
        cache.ib_count / 60,
        (spot - cache.ib_low) / width if cache.ib_valid else np.nan,
        width / spot if cache.ib_valid else np.nan,
        *changes,
        *change_masks,
        *cache.context[minute],
        *cache.walls[minute].ravel(),
    ]
    tokens = np.zeros((20, len(TOKEN_NAMES)), dtype=np.float32)
    maps = np.zeros((20, 5, 64), dtype=np.float32)
    token_mask = np.zeros(20, dtype=bool)
    bar_mask = np.zeros(20, dtype=bool)
    map_mask = np.zeros((20, 5), dtype=np.float32)
    bar_end = np.full(20, -1, dtype=np.int16)
    offset = 0
    for duration, lookback in ((5, 12), (15, 8)):
        completed = minute // duration
        for token, index in enumerate(range(completed - lookback, completed)):
            slot = offset + token
            if index < 0:
                continue
            bar = cache.bars[duration][index]
            assert bar["end"] < minute
            open_, high, low, close = bar["ohlc"]
            geometry = [
                *(bar["ohlc"] - spot) / width,
                (close - cache.ib_low) / width,
                (close - open_) / width,
                (high - max(open_, close)) / width,
                (min(open_, close) - low) / width,
                (high - low) / width,
                bar["fraction"],
                bar["last_age"],
                duration / 15,
                (minute - bar["end"]) / 390,
            ]
            tokens[slot] = _safe([*geometry, *bar["context"]])
            maps[slot] = bar["maps"].astype(np.float32)
            token_mask[slot] = bar["token_mask"]
            bar_mask[slot] = True
            map_mask[slot] = bar["map_mask"].astype(np.float32)
            bar_end[slot] = bar["end"]
        offset += lookback
    return dict(
        state_i=np.asarray(minute, dtype=np.int16),
        base=_safe(base),
        tokens=tokens,
        maps=maps,
        token_mask=token_mask,
        bar_mask=bar_mask,
        map_mask=map_mask,
        bar_end_i=bar_end,
        state_valid=np.asarray(cache.ib_valid and cache.spot_valid[minute], dtype=bool),
    )


def encode_states(cache: DayFeatureCache, indices=None) -> dict[str, np.ndarray]:
    clock = getattr(cache, "clock", FULL)
    if clock.is_full:
        return frozen.encode_states(cache, indices)
    indices = (
        list(range(60, clock.last_state + 1)) if indices is None else list(indices)
    )
    if not indices:
        raise ValueError("At least one state index is required")
    encoded = [encode_state(cache, index) for index in indices]
    return {name: np.stack([item[name] for item in encoded]) for name in encoded[0]}


def action_features(
    raw: dict,
    actions,
    feature_cache: DayFeatureCache | None = None,
    clock: SessionClock = FULL,
) -> np.ndarray:
    """Explicit causal whitelist; action labels/realized fills are never read.

    Accept a DataFrame or sequence of mappings. Quotes are from decision state_i,
    NOT entry_i. Returned rows preserve the supplied action order.
    """
    if clock.is_full:
        return frozen.action_features(raw, actions, feature_cache)
    level_engine.validate_cache(raw, clock)
    records = (
        actions.loc[:, list(ACTION_INPUT_NAMES)].to_dict("records")
        if hasattr(actions, "to_dict")
        else [{name: row[name] for name in ACTION_INPUT_NAMES} for row in actions]
    )
    if feature_cache is None:
        bounds = level_engine.ib_bounds(raw)
        width = bounds[1] - bounds[0] if bounds is not None else 1.0
    else:
        width = (
            feature_cache.ib_high - feature_cache.ib_low
            if feature_cache.ib_valid
            else 1.0
        )
    output = []
    for action in records:
        minute, contract = int(action["state_i"]), int(action["contract_i"])
        if not 60 <= minute <= clock.last_state:
            raise ValueError("Action state outside causal decision range")
        spot = raw["spot"][minute]
        bid, ask, iv, delta, vega, theta = (
            raw[key][minute, contract]
            for key in ("bid", "ask", "iv", "delta", "vega", "theta")
        )
        target, stop = float(action["target_center"]), float(action["stop_center"])
        target_distance, stop_distance = abs(target - spot), abs(stop - spot)
        quote_valid = (
            np.isfinite(bid)
            and np.isfinite(ask)
            and bid >= 0
            and ask > 0
            and bid <= ask
        )
        iv_valid = np.isfinite(iv) and 0 < iv <= 5
        delta_valid = np.isfinite(delta) and abs(delta) <= 1
        vega_valid = np.isfinite(vega) and vega >= 0
        theta_valid = np.isfinite(theta)
        bits = [
            float(int(action[f"{which}_source_mask"]) & bit != 0)
            for which in ("target", "stop")
            for bit in (1, 2, 4, 8, 16)
        ]
        values = [
            float(action["right"] == 1),
            (action["strike"] - spot) / width,
            action["selected_delta"],
            action["delta_bucket"],
            (target - spot) / width,
            (stop - spot) / width,
            target_distance / width,
            stop_distance / width,
            action["band"] / width,
            target_distance / stop_distance if stop_distance > 0 else 0.0,
            bid / spot,
            ask / spot,
            (ask - bid) / spot,
            iv if iv_valid else np.nan,
            delta if delta_valid else np.nan,
            vega / spot if vega_valid else np.nan,
            theta / spot if theta_valid else np.nan,
            float(quote_valid),
            float(iv_valid),
            float((int(raw["row_flags"][minute, contract]) & 1) != 0),
            float(delta_valid),
            float(vega_valid),
            float(theta_valid),
            *bits,
        ]
        output.append(_safe(values))
    return np.asarray(output, dtype=np.float32).reshape(-1, len(ACTION_NAMES))


def encode_actions(
    raw: dict, states, actions, clock: SessionClock = FULL
) -> np.ndarray:
    """Trainer-compatible alias; states is intentionally unused, raw is authoritative."""
    del states
    return action_features(raw, actions, clock=clock)


def feature_schema():
    schema = frozen.feature_schema()
    schema.update(
        version=VERSION,
        gamma_definition="session_level_engine.bs_gamma_density; expiry at declared close_i",
        session_time_units="minute/390, bar_age/390, (close_i-minute)/390",
    )
    return schema
