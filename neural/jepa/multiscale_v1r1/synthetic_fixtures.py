"""Explicitly artificial market fixtures. Never accepts a real-data root."""
import numpy as np
import pandas as pd

from .contract import ACTIONS, TICKERS


def source_fixture(day='2025-01-10', ticker='SPXW', direction=1):
    clock = pd.date_range(f'{day} 09:30', periods=240, freq='min', tz='America/New_York')
    close = 100 + np.sin(np.arange(240) / 13) * .25 + np.arange(240) * .001
    bars = pd.DataFrame(dict(timestamp=clock, open=close - .01, high=close + .04,
                             low=close - .04, close=close, tick_count=20))
    quotes, positions = [], []
    for strike in (99. - direction, 100. - direction, 101. - direction):
        for right in ('CALL', 'PUT'):
            key = dict(ticker=ticker, trade_date=day, expiration=day, right=right, strike=strike)
            positions.append(dict(**key, open_interest=100000 if strike == 100. - direction and right == 'CALL' else 100,
                                  as_of=pd.Timestamp(day, tz='America/New_York') - pd.Timedelta(hours=8),
                                  available_at=pd.Timestamp(f'{day} 06:30', tz='America/New_York'), provenance_ref='SYNTHETIC_PRIOR_CLOSE'))
            for timestamp in clock:
                quotes.append(dict(**key, timestamp=timestamp, implied_vol=.2, ask=1.1, bid=1., delta=.5))
    prior = {}
    for date in pd.bdate_range(end=pd.Timestamp(day) - pd.Timedelta(days=1), periods=5):
        shifted = bars.copy()
        shifted['timestamp'] -= pd.Timedelta(days=(pd.Timestamp(day) - date).days)
        prior[str(date.date())] = shifted.set_index('timestamp')
    return bars, pd.DataFrame(quotes), pd.DataFrame(positions), prior


def month_events(month):
    """Thirteen fixture weekdays, not an XNYS historical admission claim."""
    start = pd.Timestamp(month + '01')
    days = pd.bdate_range(start, periods=13)
    rows = []
    for i, date in enumerate(days):
        day = str(date.date())
        signal = 1 if i % 2 == 0 else -1
        for ticker in TICKERS:
            for clock in ('11:30', '11:35'):
                decision = pd.Timestamp(f'{day} {clock}', tz='America/New_York') + pd.Timedelta(milliseconds=1)
                rows.append(dict(event_id=f'{ticker}:{day}:{clock}:SYNTHETIC', ticker=ticker,
                                 trade_date=day, month=month, decision_timestamp=decision.isoformat(), signal=signal))
    return rows


def action_quotes(event, scenario='signal'):
    """Generate executable quotes independently of the estimator's predictions."""
    decision = pd.Timestamp(event['decision_timestamp'])
    entry = decision.ceil('min')
    rows = []
    rng = np.random.default_rng(int(event['trade_date'].replace('-', '')))
    random_sign = int(rng.choice([-1, 1]))
    for right in ('CALL', 'PUT'):
        for delta in (25, 35, 50):
            key = dict(ticker=event['ticker'], trade_date=event['trade_date'], expiration=event['trade_date'],
                       right=right, strike=float(100 + delta), delta=delta / 100 * (1 if right == 'CALL' else -1))
            rows.append(dict(**key, timestamp=entry.isoformat(), bid=.98, ask=1.))
            if scenario == 'missing_exit':
                continue
            for hold in (60, 90, 120, 180):
                sign = event['signal'] if scenario != 'random' else random_sign
                win = (right == 'CALL') == (sign == 1)
                bid = 1.55 if win else .55
                if scenario == 'flat':
                    bid = .98
                elif scenario == 'cost_flip':
                    bid = 1.06
                bid -= (delta - 25) * .001 if scenario in ('signal', 'random') else 0
                rows.append(dict(**key, timestamp=(entry + pd.Timedelta(minutes=hold)).isoformat(), bid=bid, ask=bid + .02))
    return rows


class FixtureRegressor:
    """Train-only group means; TEST DOUBLE, not an additional research candidate."""
    def __init__(self, config, action_id):
        self.config, self.action_id = config, action_id
        self.means = {}

    def fit(self, x, y):
        x, y = np.asarray(x), np.asarray(y)
        self.means = {str(float(value)): float(np.mean(y[x == value])) for value in np.unique(x)}
        self.fallback = float(np.mean(y))
        return self

    def predict(self, x):
        return np.asarray([self.means.get(str(float(value)), self.fallback) for value in x])

    def artifact(self):
        return dict(profile='TEST_DOUBLE_GROUP_MEANS', config=self.config, action_id=self.action_id,
                    means=self.means, fallback=self.fallback, research_candidate=False)

    @classmethod
    def restore(cls, value):
        obj = cls(value['config'], value['action_id'])
        obj.means, obj.fallback = value['means'], value['fallback']
        return obj


def baseline_action(event_features):
    """V1 confluence/distance/slot baseline; fixed CALL35/PUT35 hold90."""
    candidates = []
    from .contract import CHANNELS, SLOTS
    from .levels import ROLES
    x, mask = event_features['x5'][-1], event_features['m5'][-1]
    index = {name: CHANNELS.index(name) for name in ('close_distance_bps', 'confluence', 'reclaim', 'rejection', 'retest')}
    for i, name in enumerate(SLOTS):
        if ROLES[name] == 'magnet' or not mask[i, index['close_distance_bps']]:
            continue
        role = ROLES[name]
        reclaim_or_reject = x[i, index['reclaim']] or x[i, index['rejection']]
        retest = x[i, index['retest']]
        if reclaim_or_reject or retest:
            call = (role == 'support' and reclaim_or_reject) or (role == 'resistance' and retest)
            action = next(a.action_id for a in ACTIONS if a.right == ('CALL' if call else 'PUT') and a.delta == 35 and a.hold_minutes == 90)
            candidates.append((-x[i, index['confluence']], abs(x[i, index['close_distance_bps']]), i, action))
    return min(candidates)[3] if candidates else None
