"""FEAT-001/002: canonical tensor boundary and no-level projection.

These pure primitives do not certify raw sources or build a historical dataset.
"""
import numpy as np
import pandas as pd

from .contract import CHANNELS, CONTROLS, STATICS, SLOTS, ContractError


def schema():
    return {'slots': list(SLOTS), 'channels': list(CHANNELS), 'statics': list(STATICS),
            'controls': list(CONTROLS), 'shapes': [[12, 59, 39], [8, 59, 39]],
            'numeric_dtype': 'float32', 'mask_dtype': 'uint8',
            'imputation': 'zero_with_explicit_mask', 'primary_dim': 92048,
            'ablation_dim': 488, 'ssl_input_dim': 4602}


def validate_tensor(x, mask, length):
    if x.shape != (length, 59, 39) or mask.shape != x.shape:
        raise ContractError('FEAT-001: shape')
    if not np.isin(mask, (0, 1)).all() or not np.isfinite(x).all():
        raise ContractError('FEAT-001: nonfinite or nonbinary')
    if np.any(x[mask == 0] != 0):
        raise ContractError('FEAT-001: masked numeric must be zero')


def flatten(x5, m5, x15, m15, static):
    validate_tensor(x5, m5, 12)
    validate_tensor(x15, m15, 8)
    if np.shape(static) != (8,) or not np.isfinite(static).all():
        raise ContractError('FEAT-001: finite statics required')
    return np.concatenate([x5.ravel(), m5.ravel(), x15.ravel(), m15.ravel(), static]).astype('float32')


def ablation(x5, m5, x15, m15, static):
    flatten(x5, m5, x15, m15, static)  # Validate invariants before projecting.
    indices = [CHANNELS.index(c) for c in CONTROLS]
    parts = []
    for x, mask in ((x5, m5), (x15, m15)):
        controls = x[:, :, indices]
        validity = mask[:, :, indices]
        # Controls must be level-independent, including when the level is absent.
        if not (controls == controls[:, :1, :]).all() or not (validity == validity[:, :1, :]).all():
            raise ContractError('FEAT-002: level information in ablation controls')
        parts.extend([controls[:, 0, :].ravel(), validity[:, 0, :].ravel()])
    return np.concatenate([*parts, static]).astype('float32')


def bars(frame, day, endpoint):
    """TIME-001/005: validate a causal prefix without examining future bar values."""
    t = pd.to_datetime(frame['timestamp'], errors='raise')
    if t.dt.tz is None:
        t = t.dt.tz_localize('America/New_York', ambiguous='raise', nonexistent='raise')
    else:
        t = t.dt.tz_convert('America/New_York')
    opening = pd.Timestamp(f'{day} 09:30', tz='America/New_York')
    closing = pd.Timestamp(f'{day} 16:00', tz='America/New_York')
    endpoint = pd.Timestamp(endpoint)
    if endpoint.tzinfo is None or not opening < endpoint <= closing:
        raise ContractError('TIME-005: invalid endpoint')
    prefix = frame.loc[(t >= opening) & (t < endpoint)].copy()
    prefix['timestamp'] = t[(t >= opening) & (t < endpoint)]
    expected = pd.date_range(opening, endpoint, freq='min', inclusive='left')
    actual = pd.DatetimeIndex(prefix['timestamp'])
    if actual.has_duplicates or not actual.sort_values().equals(expected):
        raise ContractError('TIME-001: missing, duplicate or subminute bar')
    prefix = prefix.sort_values('timestamp').set_index('timestamp')
    values = prefix[['open', 'high', 'low', 'close', 'tick_count']].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values[:, :4] <= 0).any() or (values[:, 4] < 0).any():
        raise ContractError('TIME-001: invalid bar')
    if (values[:, 1] < values[:, [0, 2, 3]].max(axis=1)).any() or (
        values[:, 2] > values[:, [0, 1, 3]].min(axis=1)
    ).any():
        raise ContractError('TIME-001: inconsistent OHLC')
    return prefix


def buckets(prefix, decision, minutes, length):
    decision = pd.Timestamp(decision)
    output = []
    for i in range(length):
        begin = decision - pd.Timedelta(minutes=minutes * (length - i))
        end = begin + pd.Timedelta(minutes=minutes)
        window = prefix.loc[(prefix.index >= begin) & (prefix.index < end)]
        if not window.index.equals(pd.date_range(begin, end, freq='min', inclusive='left')):
            raise ContractError('TIME-005: incomplete bucket')
        output.append((window.open.iloc[0], window.high.max(), window.low.min(),
                       window.close.iloc[-1], window.tick_count.sum()))
    return np.asarray(output, dtype='float64')


def repair_available(repair, ticker, day, endpoint):
    """TIME-003: validate provenance, never perform a repair."""
    expected = pd.Timestamp(f'{day} 09:30', tz='America/New_York')
    if (ticker != 'SPXW' or repair.get('repair_kind') != 'SPXW_INITIAL_ZERO_BAR'
            or pd.Timestamp(repair.get('bar_timestamp')) != expected
            or repair.get('original_zero_or_invalid') is not True
            or not repair.get('provenance_evidence')
            or not repair.get('repaired_fields')
            or not set(repair['repaired_fields']) <= {'open', 'high', 'low', 'close'}):
        raise ContractError('TIME-003: unauthorized or undocumented repair')
    available = pd.Timestamp(repair['effective_available_at'])
    if available.tzinfo is None or not expected <= available <= pd.Timestamp(endpoint):
        raise ContractError('TIME-003: repair unavailable at endpoint')
    replacement = repair.get('replacement_source_timestamp')
    if replacement is not None and pd.Timestamp(replacement) > available:
        raise ContractError('TIME-003: invalid availability bound')
    return True
