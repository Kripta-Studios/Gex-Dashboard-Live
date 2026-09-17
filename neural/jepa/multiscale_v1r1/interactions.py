"""Chronological, decision-causal multiscale interaction tensor, FEAT-001/002."""
import numpy as np
import pandas as pd

from .contract import CHANNELS, CONTROLS, DECISIONS, SLOTS, TICKERS, ContractError
from .features import ablation, bars, flatten
from .levels import ROLES, WALL_NAMES, ib_context, wall_snapshot

C = {name: index for index, name in enumerate(CHANNELS)}
STATES = ('retest', 'reclaim', 'rejection', 'acceptance', 'magnet')


def state_path(ohlc, anchor, spot, role, minutes):
    """Process ALL complete same-grid session buckets, including invisible history."""
    values = np.asarray(ohlc, dtype='float64')
    distance = (values[:, 3] - anchor) * 10000 / spot
    run_above = run_below = touches = 0
    first = None
    armed = pierced = accepted = False
    output = []
    for i, (o, high, low, close, _) in enumerate(values):
        d = distance[i]
        geometric = low <= anchor <= high or min(abs(x - anchor) for x in (o, high, low, close)) * 10000 / spot <= 15
        lag = 15 // minutes
        approach = i >= lag and abs(distance[i - lag]) - abs(d) >= 3
        qualified = geometric and approach
        defended = d >= 5 if role == 'support' else d <= -5
        broken = d <= -5 if role == 'support' else d >= 5
        prior_broken = (i > 0 and (distance[i - 1] <= -5 if role == 'support' else distance[i - 1] >= 5))
        pierce = (low - anchor) * 10000 / spot <= -5 if role == 'support' else (high - anchor) * 10000 / spot >= 5
        toward_defended = close > o if role == 'support' else close < o
        flags = dict(retest=geometric and accepted and (armed or qualified) and broken,
                     reclaim=pierced and defended, rejection=qualified and defended and toward_defended,
                     acceptance=broken and prior_broken, magnet=15 <= abs(d) <= 80)
        if role == 'magnet':
            flags.update(retest=False, reclaim=False, rejection=False, acceptance=False)
        state = next((name for name in STATES if flags[name]), 'neutral')
        run_above = run_above + 1 if d > 0 else 0
        run_below = run_below + 1 if d < 0 else 0
        first_flag = geometric and first is None and approach
        if geometric and first is None:
            first = i
        row = {name: float(state == name) for name in STATES}
        row.update(first_touch=float(first_flag), pierce=float(role != 'magnet' and pierce and (armed or qualified)),
                   prior_touches=float(touches), first_touch_index=first,
                   time_since_first_touch=None if first is None else float((i - first) * minutes),
                   run_above=float(run_above), run_below=float(run_below),
                   velocity=None if i == 0 else (abs(distance[i - 1]) - abs(d)) / minutes,
                   acceleration=None if i < 2 else
                   (2 * abs(distance[i - 1]) - abs(d) - abs(distance[i - 2])) / minutes**2)
        output.append(row)
        touches += int(geometric)
        if role != 'magnet':
            armed |= qualified
            pierced |= armed and pierce
            accepted |= bool(flags['acceptance'])
    return output


def full_buckets(prefix, decision, minutes):
    count = int((decision - prefix.index[0]).total_seconds() // (minutes * 60))
    endpoints = pd.date_range(end=decision, periods=count, freq=f'{minutes}min')
    output = []
    for end in endpoints:
        start = end - pd.Timedelta(minutes=minutes)
        block = prefix.loc[(prefix.index >= start) & (prefix.index < end)]
        if len(block) != minutes:
            raise ContractError('TIME-005: incomplete aligned state bucket')
        output.append([block.open.iloc[0], block.high.max(), block.low.min(), block.close.iloc[-1], block.tick_count.sum()])
    return endpoints, np.asarray(output, dtype='float64')


def minute_controls(prefix, prior_close):
    values = prefix[['open', 'high', 'low', 'close', 'tick_count']].to_numpy(dtype='float64')
    prev = np.r_[prior_close, values[:-1, 3]]
    tr = np.maximum.reduce([values[:, 1] - values[:, 2], abs(values[:, 1] - prev), abs(values[:, 2] - prev)])
    returns = (values[:, 3] / prev - 1) * 10000
    return pd.DataFrame({'tr': tr, 'return': returns, 'activity': values[:, 4]}, index=prefix.index)


def scale_tensor(prefix, decision, minutes, length, levels, snapshots, prior_close):
    endpoints, values = full_buckets(prefix, decision, minutes)
    if len(values) < length:
        raise ContractError('FEAT-001: insufficient scale history')
    x = np.zeros((length, len(SLOTS), len(CHANNELS)), dtype='float32')
    mask = np.zeros_like(x, dtype='uint8')
    spot = float(prefix.close.iloc[-1])
    minute = minute_controls(prefix, prior_close)
    controls = []
    for i, (endpoint, (o, high, low, close, activity)) in enumerate(zip(endpoints, values, strict=True)):
        previous = values[i - 1, 3] if i else (prior_close if endpoint - pd.Timedelta(minutes=minutes) == prefix.index[0]
                                            else prefix.loc[endpoint - pd.Timedelta(minutes=minutes + 1), 'close'])
        tr = max(high - low, abs(high - previous), abs(low - previous))
        last15 = minute.loc[(minute.index >= endpoint - pd.Timedelta(minutes=15)) & (minute.index < endpoint)]
        angle = 2 * np.pi * (endpoint - prefix.index[0]).total_seconds() / (390 * 60)
        mean_tr = last15.tr.mean() if len(last15) == 15 else np.nan
        mean_activity = last15.activity.mean() if len(last15) == 15 else np.nan
        controls.append(dict(body_bps=10000 * (close - o) / spot, direction=float(np.sign(close - o)),
                             upper_wick_bps=10000 * (high - max(o, close)) / spot,
                             lower_wick_bps=10000 * (min(o, close) - low) / spot,
                             true_range_bps=10000 * tr / spot,
                             range_over_atr15=(high - low) / mean_tr if mean_tr > 0 else None,
                             CLV=(2 * close - high - low) / (high - low) if high > low else None,
                             realized_vol_15m=float(last15['return'].std(ddof=0)) if len(last15) == 15 else None,
                             activity_proxy=float(activity), activity_ratio=activity / mean_activity if mean_activity > 0 else None,
                             time_of_day_sin=float(np.sin(angle)), time_of_day_cos=float(np.cos(angle))))

    def assign(token, slot, name, value):
        if value is not None and np.isfinite(value):
            x[token, slot, C[name]] = value
            mask[token, slot, C[name]] = 1

    for slot, name in enumerate(SLOTS):
        level = levels[name]
        if level.price is not None and (not np.isfinite(level.price) or level.available_at > decision + pd.Timedelta(milliseconds=1)):
            raise ContractError('TIME-005: invalid/unavailable decision anchor')
        path = state_path(values, level.price, spot, ROLES[name], minutes) if level.price is not None else None
        for token, i in enumerate(range(len(values) - length, len(values))):
            for channel in CONTROLS:
                assign(token, slot, channel, controls[i][channel])
            if path is None:
                continue
            endpoint = endpoints[i]
            o, high, low, close, _ = values[i]
            for channel, price in zip(('rel_O_bps', 'rel_H_bps', 'rel_L_bps', 'rel_C_bps'), (o, high, low, close), strict=True):
                assign(token, slot, channel, 10000 * (price - level.price) / spot)
            assign(token, slot, 'close_distance_bps', 10000 * (close - level.price) / spot)
            for channel, value in path[i].items():
                if channel != 'first_touch_index':
                    assign(token, slot, channel, value)
            confluence = sum(other.price is not None and other.name != name and abs(other.price - level.price) * 10000 / spot <= 15
                             for other in levels.values())
            assign(token, slot, 'confluence', confluence)
            first = path[i]['first_touch_index']
            if first is not None:
                touch_endpoint = endpoints[first]
                recent = minute.loc[(minute.index >= touch_endpoint - pd.Timedelta(minutes=15)) & (minute.index < touch_endpoint), 'tr']
                older = minute.loc[(minute.index >= touch_endpoint - pd.Timedelta(minutes=60))
                                   & (minute.index < touch_endpoint - pd.Timedelta(minutes=15)), 'tr']
                if len(recent) == 15 and len(older) == 45 and older.mean() > 0:
                    assign(token, slot, 'compression_before_touch', recent.mean() / older.mean())
                elapsed = minute.loc[(minute.index >= touch_endpoint) & (minute.index < endpoint), 'tr']
                if endpoint > touch_endpoint and len(recent) == 15 and recent.mean() > 0 and len(elapsed) == int((endpoint - touch_endpoint).total_seconds() / 60):
                    assign(token, slot, 'expansion_after_touch', elapsed.mean() / recent.mean())
            if name in WALL_NAMES and endpoint in snapshots:
                current = snapshots[endpoint].levels[name]
                if current.price is None:
                    continue
                assign(token, slot, 'wall_strength', current.strength)
                assign(token, slot, 'wall_concentration', current.concentration)
                for lag in (5, 15, 30):
                    earlier = snapshots.get(endpoint - pd.Timedelta(minutes=lag))
                    if earlier is not None and earlier.levels[name].price is not None:
                        assign(token, slot, f'wall_persistence_{lag}m', float(current.price == earlier.levels[name].price))
                        if lag == 5:
                            local_spot = prefix.loc[endpoint - pd.Timedelta(minutes=1), 'close']
                            assign(token, slot, 'wall_migration_5m_bps', 10000 * (current.price - earlier.levels[name].price) / local_spot)
    return x, mask


def build_event(frame, ib_sessions, greeks, oi, ticker, day, decision, prior_close):
    """Outcome-free complete event builder; caller must admit source provenance first."""
    decision = pd.Timestamp(decision)
    if (ticker not in TICKERS or decision.tzinfo is None or
            decision.tz_convert('America/New_York').strftime('%H:%M:%S') not in DECISIONS
            or decision.microsecond != 0 or decision.nanosecond != 0
            or decision.tz_convert('America/New_York').date().isoformat() != day):
        raise ContractError('TIME-005: invalid event identity')
    decision = decision.tz_convert('America/New_York')
    if not np.isfinite(prior_close) or prior_close <= 0:
        raise ContractError('FEAT-001: prior-close required')
    prefix = bars(frame, day, decision)
    sessions = {key: value for key, value in ib_sessions.items() if key < day}
    sessions[day] = prefix
    levels = ib_context(sessions, day)
    snapshots = {}
    for endpoint in pd.date_range(prefix.index[0] + pd.Timedelta(minutes=5), decision, freq='5min'):
        try:
            snapshots[endpoint] = wall_snapshot(greeks, oi, prefix, ticker, day, endpoint)
        except ContractError as error:
            if 'insufficient source wall snapshot' not in str(error):
                raise
            # Missing past snapshot masks only snapshot channels; D requires minimum.
            if endpoint == decision:
                raise
    levels.update(snapshots[decision].levels)
    levels = {name: levels[name] for name in SLOTS}
    x5, m5 = scale_tensor(prefix, decision, 5, 12, levels, snapshots, prior_close)
    x15, m15 = scale_tensor(prefix, decision, 15, 8, levels, snapshots, prior_close)
    spot = float(prefix.close.iloc[-1])
    angle = 2 * np.pi * (decision - prefix.index[0]).total_seconds() / (390 * 60)
    static = np.array([*(float(ticker == t) for t in TICKERS), np.sin(angle), np.cos(angle),
                       10000 * (spot - prefix.open.iloc[0]) / spot,
                       10000 * (spot - prior_close) / spot,
                       10000 * (levels['d0_ibh'].price - levels['d0_ibl'].price) / spot], dtype='float32')
    flatten(x5, m5, x15, m15, static)
    ablation(x5, m5, x15, m15, static)
    return dict(event_id=f'{ticker}:{day}:{decision.strftime("%H:%M:%S")}',
                ticker=ticker, trade_date=day, decision_timestamp=decision + pd.Timedelta(milliseconds=1),
                x5=x5, m5=m5, x15=x15, m15=m15, static=static, levels=levels, snapshots=snapshots)
