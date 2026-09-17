"""FEAT-002: exact IB extensions and native-time Greek wall snapshots.

Pure calculations on already admitted source rows; no file access or outcomes.
The Black-Scholes primitives are implemented here, with no untracked dependency.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.special import ndtr

from .contract import SLOTS, ContractError

WALL_NAMES = SLOTS[:5] + SLOTS[53:]
KEY = ['ticker', 'trade_date', 'expiration', 'right', 'strike']
ROLES = {name: ('magnet' if name in ('zero_gamma', 'max_dgex', 'min_dgex') else
                'support' if name.startswith(('min_', 'put_')) or '_lower_' in name
                or name.endswith('_ibl') else 'resistance') for name in SLOTS}


@dataclass(frozen=True)
class Level:
    name: str
    price: float | None
    available_at: pd.Timestamp
    source_session: str
    strength: float | None = None
    concentration: float | None = None

    @property
    def role(self):
        return ROLES[self.name]


@dataclass
class Snapshot:
    endpoint: pd.Timestamp
    levels: dict[str, Level]
    members: pd.DataFrame


def initial_balance(prefix, day, lag=0):
    """Exactly sixty start-labelled minutes; return eight slots in fixed order."""
    start = pd.Timestamp(f'{day} 09:30', tz='America/New_York')
    end = start + pd.Timedelta(hours=1)
    window = prefix.loc[(prefix.index >= start) & (prefix.index < end)]
    if not window.index.equals(pd.date_range(start, end, freq='min', inclusive='left')):
        raise ContractError('FEAT-002: incomplete IB')
    high, low = float(window.high.max()), float(window.low.min())
    if not np.isfinite([high, low]).all() or not 0 < low < high or lag not in range(6):
        raise ContractError('FEAT-002: invalid IB range/lag')
    width = high - low
    values = [high, low]
    for ratio in (1.272, 1.618, 2.):
        values.extend([low + ratio * width, high - ratio * width])
    names = SLOTS[5 + 8 * lag:13 + 8 * lag]
    return {name: Level(name, price, end, day) for name, price in zip(names, values, strict=True)}


def ib_context(sessions, day):
    """Use IB-valid source sessions, independently of final event eligibility."""
    valid = {}
    for source_day in sorted(d for d in sessions if d <= day):
        try:
            initial_balance(sessions[source_day], source_day)
        except ContractError:
            continue
        valid[source_day] = sessions[source_day]
    if day not in valid or len(valid) < 6:
        raise ContractError('TIME-004: six IB source sessions required')
    result = {}
    for lag, source_day in enumerate(sorted(valid, reverse=True)[:6]):
        result.update(initial_balance(valid[source_day], source_day, lag))
    return result


def normalize_contracts(frame):
    """Normalize documented source identity; do not normalize quote timestamps."""
    frame = frame.copy()
    if 'ticker' not in frame and 'symbol' in frame:
        frame = frame.rename(columns={'symbol': 'ticker'})
    for column in ('trade_date', 'expiration'):
        frame[column] = pd.to_datetime(frame[column], errors='raise').dt.strftime('%Y-%m-%d')
    frame['right'] = frame['right'].replace({'C': 'CALL', 'P': 'PUT', 'call': 'CALL', 'put': 'PUT'})
    frame['strike'] = pd.to_numeric(frame['strike'], errors='raise').astype('float64')
    return frame


def wall_snapshot(greeks, oi, prefix, ticker, day, endpoint):
    endpoint = pd.Timestamp(endpoint)
    if endpoint.tzinfo is None:
        raise ContractError('TIME-005: timezone-aware wall endpoint required')
    endpoint = endpoint.tz_convert('America/New_York')
    if endpoint.date().isoformat() != day:
        raise ContractError('TIME-005: snapshot session mismatch')
    quotes = normalize_contracts(greeks)
    ts = pd.to_datetime(quotes.timestamp, errors='raise')
    if ts.dt.tz is None:
        ts = ts.dt.tz_localize('America/New_York', ambiguous='raise', nonexistent='raise')
    quotes['timestamp'] = ts
    quotes = quotes.loc[(quotes.ticker == ticker) & (quotes.trade_date == day)
                        & (quotes.expiration == day) & (ts <= endpoint)
                        & (ts > endpoint - pd.Timedelta(seconds=60))].copy()
    if quotes.duplicated(KEY + ['timestamp'], keep=False).any():
        raise ContractError('TIME-005: duplicate native Greek key')
    valid = (quotes.right.isin(('CALL', 'PUT')) & (quotes.strike > 0)
             & quotes.implied_vol.between(0, 2, inclusive='neither')
             & (quotes.ask > 0) & (quotes.bid >= 0) & (quotes.ask >= quotes.bid))
    valid &= np.isfinite(quotes[['strike', 'implied_vol', 'ask', 'bid']]).all(axis=1)
    quotes = quotes.loc[valid].sort_values('timestamp').groupby(KEY, sort=False, as_index=False).tail(1)
    positions = normalize_contracts(oi)
    positions = positions.loc[(positions.ticker == ticker) & (positions.trade_date == day)
                              & (positions.expiration == day)].copy()
    # All copies of an ambiguous OI key are masked, never arbitrarily deduplicated.
    positions = positions.loc[~positions.duplicated(KEY, keep=False)]
    opening = pd.Timestamp(f'{day} 09:30', tz='America/New_York')
    if not {'as_of', 'available_at', 'provenance_ref'} <= set(positions.columns):
        raise ContractError('DATA-001: prior-close OI provenance required')
    as_of, available = pd.to_datetime(positions.as_of), pd.to_datetime(positions.available_at)
    if as_of.dt.tz is None or available.dt.tz is None:
        raise ContractError('DATA-001: OI provenance timezone required')
    eligible_oi = ((as_of < opening.normalize()) & (available <= opening)
                   & (available >= as_of) & positions.provenance_ref.notna()
                   & (positions.provenance_ref.astype(str).str.len() > 0)
                   & np.isfinite(positions.open_interest) & (positions.open_interest > 0))
    quotes = quotes.merge(positions.loc[eligible_oi, KEY + ['open_interest', 'provenance_ref']],
                          on=KEY, how='inner', validate='one_to_one')
    # Each row uses its own tau and the last COMPLETED underlying minute at tau.
    ends = prefix.index + pd.Timedelta(minutes=1)
    loc = ends.searchsorted(pd.DatetimeIndex(quotes.timestamp), side='right') - 1
    quotes = quotes.loc[loc >= 0].copy()
    loc = loc[loc >= 0]
    quotes['spot'] = prefix.close.to_numpy(dtype='float64')[loc]
    quotes['spot_bar_end'] = ends[loc]
    if not {'CALL', 'PUT'} <= set(quotes.right) or quotes.strike.nunique() < 2:
        raise ContractError('FEAT-002: insufficient source wall snapshot')
    spot = quotes.spot.to_numpy(dtype='float64')
    strike = quotes.strike.to_numpy(dtype='float64')
    sigma = quotes.implied_vol.to_numpy(dtype='float64')
    closing = pd.Timestamp(f'{day} 16:00', tz='America/New_York')
    seconds = (closing - quotes.timestamp).dt.total_seconds().to_numpy()
    years = np.maximum(seconds, 60) / (365.25 * 24 * 3600)
    interest = quotes.open_interest.to_numpy(dtype='float64')
    d1 = (np.log(spot / strike) + (.0325 - .015 + .5 * sigma**2) * years) / (sigma * np.sqrt(years))
    pdf = np.exp(-.5 * d1**2) / np.sqrt(2 * np.pi)
    cdf = ndtr(d1)
    discount = np.exp(-.015 * years)
    gamma = discount * pdf / (spot * sigma * np.sqrt(years)) * interest * spot**2
    is_call = quotes.right.to_numpy() == 'CALL'
    unit_delta = discount * np.where(is_call, cdf, -(1 - cdf))
    quotes['Gc'] = np.where(is_call, gamma, 0.)
    quotes['Gp'] = np.where(is_call, 0., gamma)
    quotes['Dc'] = np.where(is_call, unit_delta * interest * spot, 0.)
    quotes['Dp'] = np.where(is_call, 0., -unit_delta * interest * spot)
    quotes['Xn'] = np.where(is_call, 1., -1.) * gamma * np.abs(unit_delta)
    quotes['quote_age_ms'] = (endpoint - quotes.timestamp).dt.total_seconds() * 1000
    grouped = quotes.groupby('strike', sort=True)[['Gc', 'Gp', 'Dc', 'Dp', 'Xn']].sum()
    grouped['Gn'] = grouped.Gc - grouped.Gp
    grouped['Dn'] = grouped.Dc - grouped.Dp
    endpoint_loc = ends.searchsorted(endpoint, side='right') - 1
    levels = aggregate_walls(grouped, float(prefix.close.iloc[endpoint_loc]), endpoint, day)
    return Snapshot(endpoint, levels, quotes)


def aggregate_walls(grouped, spot, endpoint, day):
    """Strike-level scores, exact ties and all zero-gamma roots."""
    grouped = grouped.sort_index()
    if grouped.index.has_duplicates or not np.isfinite(grouped.to_numpy()).all():
        raise ContractError('FEAT-002: invalid strike aggregation')
    specs = {'max_gamma': ('Gn', 1), 'min_gamma': ('Gn', -1),
             'max_dgex': ('Xn', 1), 'min_dgex': ('Xn', -1),
             'call_gamma': ('Gc', 1), 'put_gamma': ('Gp', 1),
             'call_delta': ('Dc', 1), 'put_delta': ('Dp', 1),
             'max_delta': ('Dn', 1), 'min_delta': ('Dn', -1)}
    result = {}
    for name, (column, sign) in specs.items():
        scores = (grouped[column] * sign).clip(lower=0)
        if scores.max() <= 0:
            result[name] = Level(name, None, endpoint, day)
            continue
        strike = float(scores.idxmax())
        v = float(grouped.loc[strike, column]) * (-1 if name.startswith('put_') else 1)
        result[name] = Level(name, strike, endpoint, day,
                             float(np.sign(v) * np.log1p(abs(v))), float(scores.loc[strike] / scores.sum()))
    strikes, net = grouped.index.to_numpy(dtype=float), grouped.Gn.to_numpy(dtype=float)
    roots = [(float(k), i, i) for i, (k, v) in enumerate(zip(strikes, net, strict=True)) if v == 0]
    for i in range(len(strikes) - 1):
        if net[i] * net[i + 1] < 0:
            root = strikes[i] - net[i] * (strikes[i + 1] - strikes[i]) / (net[i + 1] - net[i])
            roots.append((float(root), i, i + 1))
    if roots:
        root, left, right = min(roots, key=lambda item: (abs(item[0] - spot), item[0]))
        denominator = np.abs(net).sum()
        concentration = float((abs(net[left]) + abs(net[right])) / denominator) if denominator > 0 else None
        result['zero_gamma'] = Level('zero_gamma', root, endpoint, day,
                                     float(np.sign(net.sum()) * np.log1p(abs(net.sum()))), concentration)
    else:
        result['zero_gamma'] = Level('zero_gamma', None, endpoint, day)
    return {name: result[name] for name in WALL_NAMES}
