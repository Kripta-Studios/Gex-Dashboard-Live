"""Scalar reference reconstruction of complete synthetic tensors, independent of builder."""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from neural.jepa.multiscale_v1r1.contract import CHANNELS, CONTROLS, SLOTS, TICKERS


def audit_tensor_fixture(folder):
    folder = Path(folder)
    identity = json.loads((folder / 'identity.json').read_bytes())
    day, ticker = identity['day'], identity['ticker']
    end = pd.Timestamp(identity['decision']).tz_convert('America/New_York')
    bars = pd.read_parquet(folder / 'bars.parquet').set_index('timestamp')
    bars = bars.loc[bars.index < end]
    spot = float(bars.close.iloc[-1])
    previous_close = identity['prior_close']
    quote = pd.read_parquet(folder / 'greeks.parquet')
    oi = pd.read_parquet(folder / 'oi.parquet')
    histories = [(day, bars)] + [(path.stem[3:], pd.read_parquet(path)) for path in sorted(folder.glob('ib_*.parquet'), reverse=True)]
    anchors = {}
    for lag, (_, source) in enumerate(histories):
        first = source.iloc[:60]
        h, low = float(first.high.max()), float(first.low.min())
        levels = [h, low]
        for ratio in (1.272, 1.618, 2.0):
            levels += [low + ratio * (h - low), h - ratio * (h - low)]
        anchors.update(dict(zip(SLOTS[5 + 8 * lag:13 + 8 * lag], levels, strict=True)))

    def walls(endpoint):
        rows = quote[(quote.timestamp <= endpoint) & (quote.timestamp > endpoint - pd.Timedelta(seconds=60))]
        sums = {}
        for (strike, right), records in rows.groupby(['strike', 'right']):
            if records.timestamp.duplicated().any():
                raise ValueError('AUDIT: duplicate native fixture timestamp')
            row = records.sort_values('timestamp').iloc[-1]
            interest = oi[(oi.strike == strike) & (oi.right == right)]
            if len(interest) != 1:
                raise ValueError('AUDIT: ambiguous fixture OI')
            item = interest.iloc[0]
            if item.as_of >= pd.Timestamp(day, tz='America/New_York') or item.available_at > bars.index[0]:
                raise ValueError('AUDIT: invalid fixture OI availability')
            prior = bars.loc[bars.index + pd.Timedelta(minutes=1) <= row.timestamp]
            s = float(prior.close.iloc[-1])
            t = max((pd.Timestamp(day + ' 16:00', tz='America/New_York') - row.timestamp).total_seconds(), 60) / 31557600
            iv = float(row.implied_vol)
            z = (math.log(s / strike) + (.0325 - .015 + iv * iv / 2) * t) / (iv * math.sqrt(t))
            cdf = (1 + math.erf(z / math.sqrt(2))) / 2
            gamma = math.exp(-.015 * t) * math.exp(-z * z / 2) / math.sqrt(2 * math.pi) / (s * iv * math.sqrt(t)) * float(item.open_interest) * s * s
            delta = math.exp(-.015 * t) * (cdf if right == 'CALL' else cdf - 1)
            values = sums.setdefault(float(strike), dict(Gc=0., Gp=0., Dc=0., Dp=0., Xn=0.))
            values['Gc' if right == 'CALL' else 'Gp'] += gamma
            values['Dc' if right == 'CALL' else 'Dp'] += abs(delta * float(item.open_interest) * s)
            values['Xn'] += gamma * abs(delta) * (1 if right == 'CALL' else -1)
        strikes = sorted(sums)
        for v in sums.values():
            v['Gn'], v['Dn'] = v['Gc'] - v['Gp'], v['Dc'] - v['Dp']
        result = {}
        specs = [('max_gamma', 'Gn', 1), ('min_gamma', 'Gn', -1), ('max_dgex', 'Xn', 1), ('min_dgex', 'Xn', -1),
                 ('call_gamma', 'Gc', 1), ('put_gamma', 'Gp', 1), ('call_delta', 'Dc', 1), ('put_delta', 'Dp', 1),
                 ('max_delta', 'Dn', 1), ('min_delta', 'Dn', -1)]
        for name, column, sign in specs:
            scores = {k: max(sums[k][column] * sign, 0) for k in strikes}
            k = min(strikes, key=lambda k: (-scores[k], k))
            if scores[k] == 0:
                result[name] = (None, None, None)
            else:
                v = sums[k][column] * (-1 if name.startswith('put_') else 1)
                result[name] = (k, math.copysign(math.log1p(abs(v)), v), scores[k] / sum(scores.values()))
        roots = [(k, k, k) for k in strikes if sums[k]['Gn'] == 0]
        for left, right in zip(strikes[:-1], strikes[1:], strict=True):
            a, b = sums[left]['Gn'], sums[right]['Gn']
            if a * b < 0:
                roots.append((left - a * (right - left) / (b - a), left, right))
        if roots:
            local_spot = float(bars.loc[bars.index < endpoint].close.iloc[-1])
            root, left, right = min(roots, key=lambda r: (abs(r[0] - local_spot), r[0]))
            total = sum(v['Gn'] for v in sums.values())
            denominator = sum(abs(v['Gn']) for v in sums.values())
            strength = math.copysign(math.log1p(abs(total)), total) if total else 0.
            result['zero_gamma'] = (root, strength, (abs(sums[left]['Gn']) + abs(sums[right]['Gn'])) / denominator if denominator else None)
        else:
            result['zero_gamma'] = (None, None, None)
        return result

    snapshots = {e: walls(e) for e in pd.date_range(bars.index[0] + pd.Timedelta(minutes=5), end, freq='5min')}
    anchors.update({name: values[0] for name, values in snapshots[end].items()})
    true_ranges, returns = {}, {}
    prev = previous_close
    for timestamp, row in bars.iterrows():
        true_ranges[timestamp] = max(row.high - row.low, abs(row.high - prev), abs(row.low - prev))
        returns[timestamp] = (row.close / prev - 1) * 10000
        prev = row.close
    tr1 = pd.Series(true_ranges)
    ret1 = pd.Series(returns)

    compared = 0
    for minutes, length in ((5, 12), (15, 8)):
        count = int((end - bars.index[0]).total_seconds() // (minutes * 60))
        endpoints = list(pd.date_range(end=end, periods=count, freq=f'{minutes}min'))
        buckets = []
        for e in endpoints:
            b = bars.loc[(bars.index >= e - pd.Timedelta(minutes=minutes)) & (bars.index < e)]
            buckets.append((b.open.iloc[0], b.high.max(), b.low.min(), b.close.iloc[-1], b.tick_count.sum()))
        expected = np.zeros((length, 59, 39), dtype='float32')
        valid = np.zeros_like(expected, dtype='uint8')
        for slot, name in enumerate(SLOTS):
            anchor = anchors[name]
            support = name.startswith(('min_', 'put_')) or name.endswith('_ibl') or '_lower_' in name
            magnet = name in ('zero_gamma', 'max_dgex', 'min_dgex')
            first = None
            touches = above = below = 0
            initiated = had_pierce = had_acceptance = False
            distances, velocities = [], []
            for i, (e, (o, h, low, close, activity)) in enumerate(zip(endpoints, buckets, strict=True)):
                start = e - pd.Timedelta(minutes=minutes)
                prev = previous_close if start == bars.index[0] else bars.loc[start - pd.Timedelta(minutes=1), 'close']
                tr = max(h - low, abs(h - prev), abs(low - prev))
                window = (bars.index >= e - pd.Timedelta(minutes=15)) & (bars.index < e)
                atr = tr1.loc[window].mean() if window.sum() == 15 else 0
                mean_activity = bars.loc[window, 'tick_count'].mean() if window.sum() == 15 else 0
                angle = 2 * math.pi * (e - bars.index[0]).total_seconds() / 23400
                features = dict(body_bps=(close - o) * 10000 / spot, direction=float(np.sign(close - o)),
                                upper_wick_bps=(h - max(o, close)) * 10000 / spot, lower_wick_bps=(min(o, close) - low) * 10000 / spot,
                                true_range_bps=tr * 10000 / spot, range_over_atr15=(h - low) / atr if atr > 0 else None,
                                CLV=(2 * close - h - low) / (h - low) if h > low else None,
                                realized_vol_15m=float(ret1.loc[window].std(ddof=0)) if window.sum() == 15 else None,
                                activity_proxy=float(activity), activity_ratio=activity / mean_activity if mean_activity > 0 else None,
                                time_of_day_sin=math.sin(angle), time_of_day_cos=math.cos(angle))
                if anchor is not None:
                    d = (close - anchor) * 10000 / spot
                    touch = low <= anchor <= h or min(abs(v - anchor) for v in (o, h, low, close)) * 10000 / spot <= 15
                    approach = i >= 15 // minutes and abs(distances[i - 15 // minutes]) - abs(d) >= 3
                    defended = d >= 5 if support else d <= -5
                    broken = d <= -5 if support else d >= 5
                    prior_broken = i > 0 and (distances[-1] <= -5 if support else distances[-1] >= 5)
                    pierce = (low - anchor) * 10000 / spot <= -5 if support else (h - anchor) * 10000 / spot >= 5
                    flags = {'retest': touch and had_acceptance and (initiated or touch and approach) and broken,
                             'reclaim': had_pierce and defended,
                             'rejection': touch and approach and defended and (close > o if support else close < o),
                             'acceptance': broken and prior_broken, 'magnet': 15 <= abs(d) <= 80}
                    if magnet:
                        for k in ('retest', 'reclaim', 'rejection', 'acceptance'):
                            flags[k] = False
                    selected = next((k for k in ('retest', 'reclaim', 'rejection', 'acceptance', 'magnet') if flags[k]), None)
                    features.update({k: float(k == selected) for k in flags})
                    features['first_touch'] = float(first is None and touch and approach)
                    if first is None and touch:
                        first = e
                    above = above + 1 if d > 0 else 0
                    below = below + 1 if d < 0 else 0
                    velocity = (abs(distances[-1]) - abs(d)) / minutes if distances else None
                    features.update(close_distance_bps=d, prior_touches=float(touches), run_above=float(above), run_below=float(below),
                                    pierce=float(not magnet and pierce and (initiated or touch and approach)), velocity=velocity,
                                    acceleration=(velocity - velocities[-1]) / minutes if i >= 2 else None,
                                    time_since_first_touch=(e - first).total_seconds() / 60 if first is not None else None,
                                    confluence=sum(v is not None and k != name and abs(v - anchor) * 10000 / spot <= 15 for k, v in anchors.items()))
                    for k, value in zip(('rel_O_bps', 'rel_H_bps', 'rel_L_bps', 'rel_C_bps'), (o, h, low, close), strict=True):
                        features[k] = (value - anchor) * 10000 / spot
                    if first is not None:
                        recent = tr1.loc[(tr1.index >= first - pd.Timedelta(minutes=15)) & (tr1.index < first)]
                        old = tr1.loc[(tr1.index >= first - pd.Timedelta(minutes=60)) & (tr1.index < first - pd.Timedelta(minutes=15))]
                        if len(recent) == 15 and len(old) == 45 and old.mean() > 0:
                            features['compression_before_touch'] = recent.mean() / old.mean()
                        elapsed = tr1.loc[(tr1.index >= first) & (tr1.index < e)]
                        if len(recent) == 15 and len(elapsed) and recent.mean() > 0:
                            features['expansion_after_touch'] = elapsed.mean() / recent.mean()
                    touches += int(touch)
                    if not magnet:
                        initiated |= touch and approach
                        had_pierce |= initiated and pierce
                        had_acceptance |= bool(flags['acceptance'])
                    distances.append(d)
                    velocities.append(velocity)
                    if name in snapshots[e] and snapshots[e][name][0] is not None:
                        current, strength, concentration = snapshots[e][name]
                        features.update(wall_strength=strength, wall_concentration=concentration)
                        for lag in (5, 15, 30):
                            old = snapshots.get(e - pd.Timedelta(minutes=lag), {}).get(name)
                            if old is not None and old[0] is not None:
                                features[f'wall_persistence_{lag}m'] = float(current == old[0])
                                if lag == 5:
                                    features['wall_migration_5m_bps'] = (current - old[0]) * 10000 / bars.loc[e - pd.Timedelta(minutes=1), 'close']
                if i >= count - length:
                    token = i - count + length
                    for channel, value in features.items():
                        if value is not None and np.isfinite(value):
                            expected[token, slot, CHANNELS.index(channel)] = value
                            valid[token, slot, CHANNELS.index(channel)] = 1
        observed, masks = np.load(folder / f'x{minutes}.npy'), np.load(folder / f'm{minutes}.npy')
        if not np.array_equal(valid, masks):
            raise ValueError('AUDIT: tensor mask mismatch')
        if not np.array_equal(expected, observed):
            where = np.argwhere(expected != observed)[0]
            raise ValueError(f'AUDIT: float32 tensor mismatch {minutes}m {where.tolist()}: {expected[tuple(where)]} != {observed[tuple(where)]}')
        for control in CONTROLS:
            index = CHANNELS.index(control)
            if not np.all(observed[:, :, index] == observed[:, :1, index]):
                raise ValueError('AUDIT: level leak in ablation')
        compared += observed.size
    angle = 2 * math.pi * (end - bars.index[0]).total_seconds() / 23400
    static = np.asarray([*(float(t == ticker) for t in TICKERS), math.sin(angle), math.cos(angle),
                         (spot - bars.open.iloc[0]) * 10000 / spot, (spot - previous_close) * 10000 / spot,
                         (anchors['d0_ibh'] - anchors['d0_ibl']) * 10000 / spot], dtype='float32')
    if not np.array_equal(static, np.load(folder / 'static.npy')):
        raise ValueError('AUDIT: static context mismatch')
    return dict(status='PASS_INDEPENDENT_SYNTHETIC_TENSOR', numeric_components=compared,
                masks_compared=compared, static_components=8, ticker=ticker, synthetic_only=True)
