"""Causal complete candle tensors and spatial exposure histories, without labels.

All 12 five-minute and 8 fifteen-minute bars are anchored at 09:30 and end
strictly before the decision snapshot. Maps use IB coordinates [-2, 3], with
Gaussian width .08 IB; each completed bar/channel divides by its own maximum.
No day-wide price/volume normalization or future-contract denominator is used.
"""
from __future__ import annotations

# Native numerical thread limits precede NumPy import in spawned workers.
# ruff: noqa: E402

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import uuid

for _variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_variable] = '1'

import numpy as np

try:
    from . import build_cache, level_engine
except ImportError:
    import build_cache
    import level_engine

VERSION = 'LEVEL_SPATIAL_CANDLE_FEATURES_V1'
GRID = np.linspace(-2., 3., 64, dtype=np.float64)
MAP_NAMES = ('fib', 'call_oi', 'put_oi', 'call_gamma', 'put_gamma')
SIDE_CONTEXT = ('iv_mean', 'abs_delta_mean', 'vega_over_spot_mean', 'theta_over_spot_mean',
                'oi_logsum', 'gamma_logsum', 'quote_valid_fraction', 'iv_valid_fraction',
                'oi_known_fraction', 'oi_positive_fraction', 'present_fraction',
                'delta_valid_fraction', 'vega_valid_fraction', 'theta_valid_fraction')
CONTEXT_NAMES = tuple(f'{side}_{name}' for side in ('call', 'put') for name in SIDE_CONTEXT) + (
    'call_oi_outside_fraction', 'put_oi_outside_fraction',
    'call_gamma_outside_fraction', 'put_gamma_outside_fraction')
GEOMETRY_NAMES = ('open_rel_spot_ib', 'high_rel_spot_ib', 'low_rel_spot_ib', 'close_rel_spot_ib',
                  'close_ib', 'body_ib', 'upper_wick_ib', 'lower_wick_ib', 'range_ib',
                  'spot_valid_fraction', 'last_spot_age_fraction', 'bar_duration_15m', 'bar_end_age_390m')
TOKEN_NAMES = GEOMETRY_NAMES + CONTEXT_NAMES
BASE_NAMES = ('minute_fraction', 'remaining_fraction', 'spot_valid', 'ib_valid', 'ib_valid_fraction',
              'spot_ib', 'ib_range_over_spot', 'change_1m_ib', 'change_5m_ib', 'change_15m_ib',
              'change_1m_valid', 'change_5m_valid', 'change_15m_valid') + tuple(
    'current_' + name for name in CONTEXT_NAMES) + tuple(
    f'{channel}_top{rank}_{field}' for channel in MAP_NAMES[1:] for rank in (1, 2, 3)
    for field in ('strike_ib', 'log_mass', 'valid'))
ACTION_NAMES = ('is_put', 'strike_rel_spot_ib', 'selected_delta', 'delta_bucket',
                'target_rel_spot_ib', 'stop_rel_spot_ib', 'target_distance_ib', 'stop_distance_ib',
                'band_ib', 'target_stop_ratio', 'bid_over_spot', 'ask_over_spot',
                'spread_over_spot', 'iv', 'delta', 'vega_over_spot', 'theta_over_spot',
                'quote_valid', 'iv_valid', 'greek_present', 'delta_valid', 'vega_valid', 'theta_valid') + tuple(
    f'{which}_source_{name}' for which in ('target', 'stop') for name in MAP_NAMES)
ACTION_INPUT_NAMES = ('state_i', 'contract_i', 'right', 'strike', 'selected_delta', 'delta_bucket',
                      'target_center', 'target_source_mask', 'stop_center', 'stop_source_mask', 'band')


def _mean(values, axis=0):
    values = np.asarray(values, dtype=np.float64)
    valid = np.isfinite(values)
    count = valid.sum(axis=axis)
    return np.divide(np.where(valid, values, 0.).sum(axis=axis), count,
                     out=np.full(np.shape(count), np.nan), where=count > 0)


def _safe(values):
    return np.nan_to_num(np.asarray(values), nan=0., posinf=0., neginf=0.).astype(np.float32)


@dataclass
class DayFeatureCache:
    raw: dict
    spot: np.ndarray
    spot_valid: np.ndarray
    ib_low: float
    ib_high: float
    ib_count: int
    ib_valid: bool
    context: np.ndarray
    walls: np.ndarray
    bars: dict


def build_day_feature_cache(raw: dict) -> DayFeatureCache:
    """Build only small daily intermediates; no economic outcomes are accepted."""
    level_engine.validate_cache(raw)
    spot = np.asarray(raw['spot'], dtype=np.float64)
    spot_valid = np.asarray(raw['spot_valid'], dtype=bool) & np.isfinite(spot) & (spot > 0)
    initial = spot[:60][spot_valid[:60]]
    low = float(initial.min()) if len(initial) else np.nan
    high = float(initial.max()) if len(initial) else np.nan
    ib_valid = len(initial) >= 57 and high > low
    width = high - low if ib_valid else 1.
    strike = np.asarray(raw['strike'], dtype=np.float64)
    side = np.asarray(raw['right'])
    coordinate = (strike - low) / width if ib_valid else np.zeros(len(strike))
    kernels = np.exp(-.5 * ((GRID[None, :] - coordinate[:, None]) / .08) ** 2)
    outside = (coordinate < GRID[0]) | (coordinate > GRID[-1])
    oi = level_engine.available_oi_matrix(raw)
    present = (np.asarray(raw['row_flags'], dtype=np.uint8) & 1) != 0
    # The rectangular cache contains a union of contracts across the entire day.
    # Denominators must use identities already observed, never the union size.
    visible = level_engine.known_contract_matrix(raw)
    context = np.full((391, len(CONTEXT_NAMES)), np.nan, dtype=np.float64)
    walls = np.zeros((391, 4, 3, 3), dtype=np.float64)
    maps = np.zeros((391, 5, 64), dtype=np.float64)
    map_known = np.zeros((391, 5), dtype=bool)
    fib = np.exp(-.5 * ((GRID[None, :] - level_engine.RATIOS[:, None]) / .08) ** 2).sum(axis=0)
    if ib_valid:
        maps[:, 0] = fib
        map_known[:, 0] = True
    for minute in range(391):
        gamma = level_engine.bs_gamma_density(raw, minute, oi[minute])
        weights = [np.where(side == 0, oi[minute], np.nan), np.where(side == 1, oi[minute], np.nan),
                   np.where(side == 0, gamma, np.nan), np.where(side == 1, gamma, np.nan)]
        for channel, mass in enumerate(weights):
            known = np.isfinite(mass)
            positive = known & (mass > 0)
            if ib_valid and known.any():
                map_known[minute, channel + 1] = True
                # Active-only reduction also avoids future-only cache identities
                # changing floating-point reduction shapes for an earlier state.
                maps[minute, channel + 1] = (mass[positive, None] * kernels[positive]).sum(axis=0)
                total = mass[positive].sum()
                context[minute, 2 * len(SIDE_CONTEXT) + channel] = mass[positive & outside].sum() / total if total > 0 else 0.
                indices = np.flatnonzero(positive)
                ordered = indices[np.lexsort((strike[indices], -mass[indices]))][:3]
                for rank, contract in enumerate(ordered):
                    walls[minute, channel, rank] = (coordinate[contract], np.log1p(mass[contract]), 1.)
        for direction in (0, 1):
            selected = (side == direction) & present[minute]
            iv = np.asarray(raw['iv'][minute])
            delta = np.asarray(raw['delta'][minute])
            vega = np.asarray(raw['vega'][minute])
            theta = np.asarray(raw['theta'][minute])
            iv_ok = selected & np.isfinite(iv) & (iv > 0) & (iv <= 5)
            delta_ok = selected & np.isfinite(delta) & (np.abs(delta) <= 1)
            vega_ok = selected & np.isfinite(vega) & (vega >= 0)
            theta_ok = selected & np.isfinite(theta)
            known_oi = (side == direction) & np.isfinite(oi[minute])
            known_gamma = (side == direction) & np.isfinite(gamma)
            n_present = int(selected.sum())
            n_visible = int(((side == direction) & visible[minute]).sum())
            n_oi = int(known_oi.sum())
            quote_ok = selected & ((np.asarray(raw['row_flags'][minute], dtype=np.uint8) & 2) != 0)
            values = [
                _mean(iv[iv_ok]), _mean(np.abs(delta[delta_ok])),
                _mean(vega[vega_ok]) / spot[minute] if spot_valid[minute] else np.nan,
                _mean(theta[theta_ok]) / spot[minute] if spot_valid[minute] else np.nan,
                np.log1p(oi[minute, known_oi].sum()) if n_oi else np.nan,
                np.log1p(gamma[known_gamma].sum()) if known_gamma.any() else np.nan,
                quote_ok.sum() / n_present if n_present else 0.,
                iv_ok.sum() / n_present if n_present else 0.,
                n_oi / n_visible if n_visible else 0.,
                (oi[minute, known_oi] > 0).sum() / n_oi if n_oi else 0.,
                n_present / n_visible if n_visible else 0.,
                delta_ok.sum() / n_present if n_present else 0.,
                vega_ok.sum() / n_present if n_present else 0.,
                theta_ok.sum() / n_present if n_present else 0.,
            ]
            context[minute, direction * len(SIDE_CONTEXT):(direction + 1) * len(SIDE_CONTEXT)] = values
    bars = {}
    for duration in (5, 15):
        rows = []
        for start in range(0, 391 - duration + 1, duration):
            stop = start + duration
            valid = spot_valid[start:stop]
            values = spot[start:stop][valid]
            ohlc = (values[0], values.max(), values.min(), values[-1]) if len(values) else (np.nan,) * 4
            known = map_known[start:stop]
            count = known.sum(axis=0)
            mean_map = np.divide(maps[start:stop].sum(axis=0), count[:, None],
                                 out=np.zeros((5, 64)), where=count[:, None] > 0)
            maximum = mean_map.max(axis=1, keepdims=True)
            normalized = np.divide(mean_map, maximum, out=np.zeros_like(mean_map), where=maximum > 0)
            rows.append(dict(end=stop - 1, ohlc=np.asarray(ohlc), fraction=valid.mean(),
                             last_age=(duration - 1 - np.flatnonzero(valid)[-1]) / duration if valid.any() else 1.,
                             context=_mean(context[start:stop], axis=0), maps=normalized,
                             map_mask=count / duration, token_mask=bool(valid.any())))
        bars[duration] = rows
    return DayFeatureCache(raw, spot, spot_valid, low, high, len(initial), ib_valid, context, walls, bars)


def encode_state(cache: DayFeatureCache, minute: int) -> dict[str, np.ndarray]:
    """Every numerical output is finite float32; masks retain missing information."""
    if not isinstance(minute, (int, np.integer)) or minute < 60 or minute > 375:
        raise ValueError('Decision indices must be integers in 60..375')
    width = cache.ib_high - cache.ib_low if cache.ib_valid else 1.
    spot = cache.spot[minute] if cache.spot_valid[minute] else np.nan
    changes, change_masks = [], []
    for lag in (1, 5, 15):
        good = bool(cache.spot_valid[minute] and cache.spot_valid[minute - lag] and cache.ib_valid)
        changes.append((spot - cache.spot[minute - lag]) / width if good else 0.)
        change_masks.append(float(good))
    base = [minute / 390, (390 - minute) / 390, float(cache.spot_valid[minute]),
            float(cache.ib_valid), cache.ib_count / 60,
            (spot - cache.ib_low) / width if cache.ib_valid else np.nan,
            width / spot if cache.ib_valid else np.nan, *changes, *change_masks,
            *cache.context[minute], *cache.walls[minute].ravel()]
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
            assert bar['end'] < minute
            open_, high, low, close = bar['ohlc']
            geometry = [*(bar['ohlc'] - spot) / width,
                        (close - cache.ib_low) / width, (close - open_) / width,
                        (high - max(open_, close)) / width, (min(open_, close) - low) / width,
                        (high - low) / width, bar['fraction'], bar['last_age'],
                        duration / 15, (minute - bar['end']) / 390]
            tokens[slot] = _safe([*geometry, *bar['context']])
            maps[slot] = bar['maps'].astype(np.float32)
            token_mask[slot] = bar['token_mask']
            bar_mask[slot] = True
            map_mask[slot] = bar['map_mask'].astype(np.float32)
            bar_end[slot] = bar['end']
        offset += lookback
    return dict(state_i=np.asarray(minute, dtype=np.int16), base=_safe(base), tokens=tokens, maps=maps,
                token_mask=token_mask, bar_mask=bar_mask, map_mask=map_mask, bar_end_i=bar_end,
                state_valid=np.asarray(cache.ib_valid and cache.spot_valid[minute], dtype=bool))


def encode_states(cache: DayFeatureCache, indices=None) -> dict[str, np.ndarray]:
    indices = list(range(60, 376)) if indices is None else list(indices)
    if not indices:
        raise ValueError('At least one state index is required')
    encoded = [encode_state(cache, index) for index in indices]
    return {name: np.stack([item[name] for item in encoded]) for name in encoded[0]}


def flatten_state_features(encoded: dict, spatial_bins: int = 8) -> np.ndarray:
    """GBT view retains every candle and every history map, pooling space only."""
    if spatial_bins not in (8, 64):
        raise ValueError('Spatial bins must be 8 (GBT) or 64 (full)')
    single = np.asarray(encoded['base']).ndim == 1
    def batch(name):
        value = np.asarray(encoded[name])
        return value[None] if single else value
    n = batch('base').shape[0]
    maps = batch('maps').reshape(n, 20, 5, spatial_bins, 64 // spatial_bins).mean(axis=-1)
    result = np.concatenate([batch('base'), batch('tokens').reshape(n, -1), maps.reshape(n, -1),
                             batch('token_mask').reshape(n, -1), batch('bar_mask').reshape(n, -1),
                             batch('map_mask').reshape(n, -1)], axis=1).astype(np.float32)
    return result[0] if single else result


def action_features(raw: dict, actions, feature_cache: DayFeatureCache | None = None) -> np.ndarray:
    """Explicit causal whitelist; action labels/realized fills are never read.

    Accept a DataFrame or sequence of mappings. Quotes are from decision state_i,
    NOT entry_i. Returned rows preserve the supplied action order.
    """
    records = (actions.loc[:, list(ACTION_INPUT_NAMES)].to_dict('records') if hasattr(actions, 'to_dict')
               else [{name: row[name] for name in ACTION_INPUT_NAMES} for row in actions])
    if feature_cache is None:
        bounds = level_engine.ib_bounds(raw)
        width = bounds[1] - bounds[0] if bounds is not None else 1.
    else:
        width = feature_cache.ib_high - feature_cache.ib_low if feature_cache.ib_valid else 1.
    output = []
    for action in records:
        minute, contract = int(action['state_i']), int(action['contract_i'])
        if not 60 <= minute <= 375:
            raise ValueError('Action state outside causal decision range')
        spot = raw['spot'][minute]
        bid, ask, iv, delta, vega, theta = (raw[key][minute, contract] for key in ('bid', 'ask', 'iv', 'delta', 'vega', 'theta'))
        target, stop = float(action['target_center']), float(action['stop_center'])
        target_distance, stop_distance = abs(target - spot), abs(stop - spot)
        quote_valid = np.isfinite(bid) and np.isfinite(ask) and bid >= 0 and ask > 0 and bid <= ask
        iv_valid = np.isfinite(iv) and 0 < iv <= 5
        delta_valid = np.isfinite(delta) and abs(delta) <= 1
        vega_valid = np.isfinite(vega) and vega >= 0
        theta_valid = np.isfinite(theta)
        bits = [float(int(action[f'{which}_source_mask']) & bit != 0)
                for which in ('target', 'stop') for bit in (1, 2, 4, 8, 16)]
        values = [float(action['right'] == 1), (action['strike'] - spot) / width,
                  action['selected_delta'], action['delta_bucket'], (target - spot) / width,
                  (stop - spot) / width, target_distance / width, stop_distance / width,
                  action['band'] / width, target_distance / stop_distance if stop_distance > 0 else 0.,
                  bid / spot, ask / spot, (ask - bid) / spot, iv if iv_valid else np.nan,
                  delta if delta_valid else np.nan, vega / spot if vega_valid else np.nan,
                  theta / spot if theta_valid else np.nan, float(quote_valid), float(iv_valid),
                  float((int(raw['row_flags'][minute, contract]) & 1) != 0),
                  float(delta_valid), float(vega_valid), float(theta_valid), *bits]
        output.append(_safe(values))
    return np.asarray(output, dtype=np.float32).reshape(-1, len(ACTION_NAMES))


def encode_actions(raw: dict, states, actions) -> np.ndarray:
    """Trainer-compatible alias; states is intentionally unused, raw is authoritative."""
    del states
    return action_features(raw, actions)


def feature_schema() -> dict:
    return dict(version=VERSION, base_names=list(BASE_NAMES), token_names=list(TOKEN_NAMES),
                map_names=list(MAP_NAMES), action_names=list(ACTION_NAMES), grid=GRID.tolist(),
                base_dim=len(BASE_NAMES), token_dim=len(TOKEN_NAMES), action_dim=len(ACTION_NAMES),
                gbt_state_dim=len(BASE_NAMES) + 20 * len(TOKEN_NAMES) + 20 * 5 * 8 + 20 + 20 + 20 * 5,
                bars={'5m': 12, '15m': 8}, map_sigma_ib=.08,
                map_normalization='Each completed bar/channel divided by its own past-only maximum; mass and overflow retained in context',
                gamma_definition='level_engine.bs_gamma_density; same known-time proxy as action levels',
                indices='12 oldest-to-newest completed5m, then8 oldest-to-newest completed15m; anchor09:30; end<state',
                missing='finite0 numeric placeholders plus token_mask,bar_mask,map_mask and context fractions')


def _sha(path):
    return build_cache.sha256(Path(path))


def _dependencies():
    paths = [Path(__file__), Path(level_engine.__file__), Path(build_cache.__file__)]
    return {path.name: _sha(path) for path in paths}


def load_day_features(path: Path, verify_hash: bool = True) -> dict[str, np.ndarray]:
    path = Path(path)
    metadata = json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
    if metadata['version'] != VERSION or (verify_hash and _sha(path) != metadata['sha256']):
        raise ValueError(f'Feature cache version/hash mismatch: {path}')
    with np.load(path, allow_pickle=False) as stored:
        arrays = {name: stored[name] for name in stored.files}
    if set(arrays) != set(metadata['array_schema']):
        raise ValueError(f'Feature array-name mismatch: {path}')
    for name, descriptor in metadata['array_schema'].items():
        if list(arrays[name].shape) != descriptor['shape'] or str(arrays[name].dtype) != descriptor['dtype']:
            raise ValueError(f'Feature shape/dtype mismatch: {path}:{name}')
    return arrays


def write_day_features(source: Path, target: Path, dependencies: dict | None = None) -> dict:
    source, target = Path(source), Path(target)
    dependencies = _dependencies() if dependencies is None else dependencies
    source_meta = build_cache.read_day_metadata(source)
    if _sha(source) != source_meta['sha256']:
        raise ValueError(f'Source cache hash mismatch: {source}')
    binding = dict(source_sha256=source_meta['sha256'], source_metadata_sha256=_sha(source.with_suffix('.json')),
                   dependencies=dependencies)
    if target.exists() or target.with_suffix('.json').exists():
        if not target.exists() or not target.with_suffix('.json').exists():
            raise ValueError(f'Partial feature publication: {target}')
        metadata = json.loads(target.with_suffix('.json').read_text(encoding='utf-8'))
        if metadata['binding'] != binding:
            raise ValueError(f'Feature resume binding mismatch: {target}')
        load_day_features(target)
        return dict(ticker=source_meta['ticker'], date=source_meta['date'], status='VERIFIED_EXISTING',
                    path=str(target), bytes=target.stat().st_size)
    arrays = encode_states(build_day_feature_cache(build_cache.load_day_cache(source)))
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + '.partial-' + uuid.uuid4().hex)
    with temporary.open('wb') as handle:
        np.savez_compressed(handle, **arrays)
    os.replace(temporary, target)
    metadata = dict(version=VERSION, ticker=source_meta['ticker'], date=source_meta['date'], binding=binding,
                    sha256=_sha(target), schema=feature_schema(), source_path=str(source.resolve()),
                    array_schema={name: dict(shape=list(value.shape), dtype=str(value.dtype)) for name, value in arrays.items()},
                    clock_basis=source_meta['clock_basis'], oi_clock_basis=source_meta['oi_clock_basis'],
                    valid_states=int(arrays['state_valid'].sum()), states=len(arrays['state_i']),
                    uncompressed_bytes=sum(value.nbytes for value in arrays.values()), outcomes_read=False,
                    completed_utc=datetime.now(timezone.utc).isoformat())
    build_cache.write_json(target.with_suffix('.json'), metadata)
    load_day_features(target)
    return dict(ticker=source_meta['ticker'], date=source_meta['date'], status='BUILT', path=str(target),
                bytes=target.stat().st_size, valid_states=metadata['valid_states'])


def _worker(task):
    return write_day_features(Path(task[0]), Path(task[1]), task[2])


def write_action_feature_cache(source: Path, actions, target: Path) -> dict:
    """Persist causal action vectors once per day; accepts no outcomes dependency."""
    source, target = Path(source), Path(target)
    if hasattr(actions, 'loc'):
        records = actions.loc[:, ['action_id', *ACTION_INPUT_NAMES]].to_dict('records')
    else:
        records = [{name: row[name] for name in ('action_id', *ACTION_INPUT_NAMES)} for row in actions]
    ids = np.asarray([row['action_id'] for row in records], dtype=np.int32)
    identity = np.asarray([[row[name] for name in ('action_id', *ACTION_INPUT_NAMES)] for row in records], dtype=np.float64)
    source_meta = build_cache.read_day_metadata(source)
    binding = dict(source_sha256=source_meta['sha256'], source_metadata_sha256=_sha(source.with_suffix('.json')),
                   dependencies=_dependencies(),
                   action_inputs_sha256=hashlib.sha256(identity.tobytes()).hexdigest())
    if target.exists() or target.with_suffix('.json').exists():
        if not target.exists() or not target.with_suffix('.json').exists():
            raise ValueError('Partial action-feature publication')
        metadata = json.loads(target.with_suffix('.json').read_text(encoding='utf-8'))
        if metadata['binding'] != binding or _sha(target) != metadata['sha256']:
            raise ValueError('Action-feature resume identity mismatch')
        with np.load(target, allow_pickle=False) as stored:
            if not np.array_equal(stored['action_id'], ids):
                raise ValueError('Action IDs differ from cached feature order')
        return dict(status='VERIFIED_EXISTING', actions=len(ids), path=str(target))
    values = action_features(build_cache.load_day_cache(source), records)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + '.partial-' + uuid.uuid4().hex)
    with temporary.open('wb') as handle:
        np.savez_compressed(handle, action_id=ids, action_features=values)
    os.replace(temporary, target)
    build_cache.write_json(target.with_suffix('.json'), dict(version=VERSION, binding=binding, sha256=_sha(target),
                           action_names=list(ACTION_NAMES), actions=len(ids), outcomes_read=False))
    return dict(status='BUILT', actions=len(ids), path=str(target))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache-root', type=Path, default=Path('D:/GexResearchArtifacts/level_oracle_20261018/cache_v1'))
    parser.add_argument('--out', type=Path, default=Path('D:/GexResearchArtifacts/level_oracle_20261018/features_v1'))
    parser.add_argument('--workers', type=int, choices=(1, 2, 3, 4), default=2)
    parser.add_argument('--date', help='Optional exact YYYYMMDD pilot date')
    parser.add_argument('--watch', action='store_true', help='Consume new completed caches until cache full_summary exists')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    dependencies = _dependencies()
    contract = dict(version=VERSION, dependencies=dependencies, schema=feature_schema(),
                    cache_root=str(args.cache_root.resolve()), outcomes_read=False)
    contract_path = args.out / 'feature_contract.json'
    if contract_path.exists():
        if json.loads(contract_path.read_text(encoding='utf-8')) != contract:
            raise ValueError('Feature code/contract changed; preserve this root and choose a new output root')
    else:
        build_cache.write_json(contract_path, contract)
        shutil.copy2(Path(__file__), args.out / 'features.executed.py')
    seen, records = set(), []
    while True:
        available = sorted(path for path in args.cache_root.glob('*/*.npz')
                           if path.with_suffix('.json').exists() and (not args.date or path.stem == args.date))
        tasks = [(str(path), str(args.out / path.parent.name / path.stem / 'features.npz'), dependencies)
                 for path in available if str(path) not in seen]
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            for record in executor.map(_worker, tasks, chunksize=1):
                records.append(record)
                if len(records) % 25 == 0:
                    progress = dict(status='RUNNING', processed=len(records), compressed_bytes=sum(x['bytes'] for x in records), last=record)
                    build_cache.write_json(args.out / 'progress.json', progress)
                    print(json.dumps(progress), flush=True)
        seen.update(task[0] for task in tasks)
        full = args.cache_root / 'full_summary.json'
        if not args.watch or args.date or full.exists():
            # A source completion can arrive while this batch is processing.
            again = [p for p in args.cache_root.glob('*/*.npz') if p.with_suffix('.json').exists() and str(p) not in seen]
            if args.watch and not args.date and again:
                continue
            break
        time.sleep(15)
    summary = dict(status='COMPLETE_AVAILABLE', processed=len(records), compressed_bytes=sum(x['bytes'] for x in records),
                   built=sum(x['status'] == 'BUILT' for x in records), verified_existing=sum(x['status'] == 'VERIFIED_EXISTING' for x in records),
                   source_full_summary_exists=(args.cache_root / 'full_summary.json').exists(), outcomes_read=False,
                   completed_utc=datetime.now(timezone.utc).isoformat())
    build_cache.write_json(args.out / 'progress.json', summary)
    run = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    build_cache.write_json(args.out / f'{run}_summary.json', summary)
    build_cache.write_json(args.out / f'{run}_coverage.json', records)
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
