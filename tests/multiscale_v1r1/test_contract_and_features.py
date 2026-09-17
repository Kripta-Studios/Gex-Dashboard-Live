import numpy as np
import pandas as pd
import pytest

from neural.jepa.multiscale_v1r1.contract import (
    ACTIONS, CHANNELS, DECISIONS, SLOTS, ContractError,
)
from neural.jepa.multiscale_v1r1.features import ablation, bars, buckets, flatten, repair_available
from neural.jepa.multiscale_v1r1.inventory import parse_name
from neural.jepa.multiscale_v1r1.models import choose_action, folds, parameters


def tensors():
    return (np.zeros((12, 59, 39), dtype='float32'), np.ones((12, 59, 39), dtype='uint8'),
            np.zeros((8, 59, 39), dtype='float32'), np.ones((8, 59, 39), dtype='uint8'), np.zeros(8))


def source_frame():
    return pd.DataFrame({'timestamp': pd.date_range('2025-01-02 09:30', periods=391, freq='min'),
                         'open': 100., 'high': 101., 'low': 99., 'close': 100., 'tick_count': 10})


def test_FEAT_001_dimensions_and_stable_order():
    assert len(SLOTS) == len(set(SLOTS)) == 59
    assert len(CHANNELS) == len(set(CHANNELS)) == 39
    assert len(ACTIONS) == 24 and len(DECISIONS) == 18
    assert (ACTIONS[0].right, ACTIONS[0].delta, ACTIONS[0].hold_minutes) == ('CALL', 25, 60)
    assert (ACTIONS[-1].right, ACTIONS[-1].delta, ACTIONS[-1].hold_minutes) == ('PUT', 50, 180)
    assert flatten(*tensors()).shape == (92048,)
    assert ablation(*tensors()).shape == (488,)


def test_FEAT_001_absence_is_not_valid_zero():
    x5, m5, x15, m15, static = tensors()
    zero = flatten(x5, m5, x15, m15, static)
    m5[0, 0, 0] = 0
    assert not np.array_equal(zero, flatten(x5, m5, x15, m15, static))
    x5[0, 0, 0] = 1
    with pytest.raises(ContractError, match='masked numeric'):
        flatten(x5, m5, x15, m15, static)


def test_FEAT_002_ablation_has_no_wall_information():
    arrays = tensors()
    before = ablation(*arrays)
    arrays[0][:, :, CHANNELS.index('wall_strength')] = np.arange(59)
    arrays[1][:, :, CHANNELS.index('rel_O_bps')] = 0
    np.testing.assert_array_equal(before, ablation(*arrays))
    arrays[0][0, 1, CHANNELS.index('body_bps')] = 1
    with pytest.raises(ContractError, match='level information'):
        ablation(*arrays)


@pytest.mark.parametrize('defect', ['missing', 'duplicate', 'subminute'])
def test_TIME_001_defects_fail(defect):
    frame = source_frame()
    if defect == 'missing':
        frame = frame.drop(3)
    elif defect == 'duplicate':
        frame = pd.concat([frame, frame.iloc[[3]]])
    else:
        frame.loc[3, 'timestamp'] += pd.Timedelta(seconds=1)
    with pytest.raises(ContractError):
        bars(frame, '2025-01-02', pd.Timestamp('2025-01-02 11:30', tz='America/New_York'))


def test_TIME_001_1600_and_future_values_never_used():
    frame = source_frame()
    endpoint = pd.Timestamp('2025-01-02 11:35', tz='America/New_York')
    before = bars(frame, '2025-01-02', endpoint)
    frame.loc[frame.timestamp >= endpoint.tz_localize(None), ['open', 'high', 'low', 'close']] = -999
    pd.testing.assert_frame_equal(before, bars(frame, '2025-01-02', endpoint))
    assert len(before) == 125
    result = buckets(before, endpoint, 15, 8)
    assert result.shape == (8, 5)  # Grid starts09:35, not global09:30.
    all_bars = bars(source_frame(), '2025-01-02', pd.Timestamp('2025-01-02 16:00', tz='America/New_York'))
    assert len(all_bars) == 390


def test_TIME_003_repair_availability():
    record = {'repair_kind': 'SPXW_INITIAL_ZERO_BAR', 'bar_timestamp': '2025-01-02T09:30:00-05:00',
              'original_zero_or_invalid': True, 'repaired_fields': ['open'],
              'effective_available_at': '2025-01-02T09:31:00-05:00', 'provenance_evidence': ['fixture']}
    assert repair_available(record, 'SPXW', '2025-01-02', '2025-01-02T09:35:00-05:00')
    for ticker, endpoint in [('QQQ', '2025-01-02T09:35:00-05:00'), ('SPXW', '2025-01-02T09:30:30-05:00')]:
        with pytest.raises(ContractError):
            repair_available(record, ticker, '2025-01-02', endpoint)
    record['bar_timestamp'] = '2025-01-02T09:31:00-05:00'
    with pytest.raises(ContractError):
        repair_available(record, 'SPXW', '2025-01-02', '2025-01-02T09:35:00-05:00')


def test_DATA_001_expiration_and_trade_date_are_distinct():
    assert parse_name('QQQ_20250117_20250102_greeks.parquet', 'greeks') == ('QQQ', '2025-01-02', '2025-01-17')


def test_FOLD_001_all_eighteen():
    rows = folds()
    assert len(rows) == 18
    assert rows[0] == {'month': '202501', 'train_start': '202208', 'train_end': '202406',
                       'selection': ['202407', '202408', '202409', '202410', '202411', '202412']}
    assert rows[1]['train_end'] == '202407'
    assert rows[-1]['selection'] == ['202512', '202601', '202602', '202603', '202604', '202605']
    assert rows[-1]['train_end'] == '202511'
    for row in rows:
        period = pd.Period(row['month'], freq='M')
        assert row['selection'] == [(period - i).strftime('%Y%m') for i in range(6, 0, -1)]
        assert row['train_end'] == (period - 7).strftime('%Y%m')


def test_ECON_002_scores_strictly_positive_and_stable_ties():
    scores = np.zeros(24)
    assert choose_action(scores, 0.) is None
    scores[1:3] = 5
    assert choose_action(scores, 5.) == 1
    scores[1:3] = 4.99
    assert choose_action(scores, 5.) is None
    assert parameters('A')['objective'] == 'regression'
    assert parameters('B')['histogram_pool_size'] == 1024
