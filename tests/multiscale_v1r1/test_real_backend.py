import json

import numpy as np
import pytest

from neural.jepa.multiscale_v1r1.artifacts import write_json
from neural.jepa.multiscale_v1r1.contract import ACTIONS, ContractError
from neural.jepa.multiscale_v1r1.payoff import simulate_action
from neural.jepa.multiscale_v1r1.real_backend import action_labels, matrix, predict_blocks
from neural.jepa.multiscale_v1r1.real_backend_smoke import FixturePayoffs, training_events
from neural.jepa.multiscale_v1r1.synthetic_fixtures import action_quotes, month_events
from neural.jepa.multiscale_v1r1_audit.real_backend import canonical_vectors, reconstruct_payoffs, validate_matrix


def test_real_training_calendar_is_balanced_and_past_only():
    rows = training_events()
    assert len(rows) == len({e['event_id'] for e in rows}) == 600
    assert min(e['month'] for e in rows) == '202208'
    assert max(e['month'] for e in rows) == '202406'
    for ticker in ('SPXW', 'SPY', 'QQQ'):
        for sign in (-1, 1):
            assert sum(e['ticker'] == ticker and e['signal'] == sign for e in rows) == 100


def test_real_matrix_and_independent_level_removal(tmp_path):
    feature = dict(x5=np.zeros((12, 59, 39), dtype='float32'), m5=np.ones((12, 59, 39), dtype='uint8'),
                   x15=np.zeros((8, 59, 39), dtype='float32'), m15=np.ones((8, 59, 39), dtype='uint8'),
                   static=np.zeros(8, dtype='float32'))
    feature['static'][0] = 1
    feature['x5'][:, :, 0] = 3
    for key, value in feature.items():
        np.save(tmp_path / f'{key}.npy', value)
    vectors = canonical_vectors(tmp_path)
    event = [dict(ticker='SPXW', signal=1)]
    bank = {('SPXW', 1): feature}
    x = matrix(tmp_path / 'full.npy', event, bank)
    abl = matrix(tmp_path / 'abl.npy', event, bank, True)
    validate_matrix(x, event, {('SPXW', 1): vectors}, 0)
    validate_matrix(abl, event, {('SPXW', 1): vectors}, 1)
    feature['x5'][:, :, 0] = 900
    np.testing.assert_array_equal(abl, matrix(tmp_path / 'changed_abl.npy', event, bank, True))
    wrong = np.array(x)
    wrong[0, 0] += 1
    with pytest.raises(ValueError, match='feature/slot/mask'):
        validate_matrix(wrong, event, {('SPXW', 1): vectors}, 0)


def test_action_specific_executability_and_prediction_blocks():
    events = [dict(event_id=str(i), ticker='SPXW') for i in range(3)]
    outcomes = {str(i): {'0': dict(action_available=i != 1, base=dict(net_dollar_pnl=str(i + .4)))} for i in range(3)}
    rows, y, tickers = action_labels(events, outcomes, 0)
    assert rows.tolist() == [0, 2] and y.tolist() == [.4, 2.4] and tickers == ['SPXW', 'SPXW']
    class Booster:
        def __init__(self):
            self.blocks = []

        def predict(self, x, num_threads):
            assert num_threads == 1
            self.blocks.append(len(x))
            return x[:, 0]
    model = Booster()
    x = np.arange(601, dtype='float32').reshape(-1, 1)
    np.testing.assert_array_equal(predict_blocks(model, x), x[:, 0])
    assert model.blocks == [256, 256, 89]


def test_new_real_circuit_cannot_generate_test_before_freeze(tmp_path):
    store = FixturePayoffs(tmp_path, '1' * 64)
    with pytest.raises(ContractError, match='before freeze'):
        store.generate('test', month_events('202501'))
    with pytest.raises(ContractError, match='future'):
        store.generate('selection', month_events('202501'))
    assert not list(tmp_path.iterdir())


def test_independent_rebuild_rejects_changed_training_label(tmp_path):
    event = month_events('202408')[0]
    quotes = action_quotes(event)
    payoffs = {event['event_id']: {str(a.action_id): simulate_action(quotes, event['ticker'], event['trade_date'],
                               event['decision_timestamp'], a.action_id) for a in ACTIONS}}
    write_json(tmp_path / 'train_quotes.json', {event['event_id']: quotes})
    write_json(tmp_path / 'train_payoffs.json', payoffs)
    assert reconstruct_payoffs(tmp_path, 'train', [event]) == payoffs
    payoffs[event['event_id']]['0']['base']['net_dollar_pnl'] = '999'
    (tmp_path / 'train_payoffs.json').write_text(json.dumps(payoffs))
    with pytest.raises(ValueError, match='label/contract/clock/money'):
        reconstruct_payoffs(tmp_path, 'train', [event])
