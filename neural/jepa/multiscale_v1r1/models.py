"""MODEL-001: fixed LightGBM parameters and chronological fold calendar."""
import numpy as np
import pandas as pd

from .contract import ContractError, SEED, TICKERS


def folds():
    result = []
    for month in pd.period_range('2025-01', '2026-06', freq='M'):
        result.append({'month': month.strftime('%Y%m'), 'train_start': '202208',
                       'train_end': (month - 7).strftime('%Y%m'),
                       'selection': [(month - i).strftime('%Y%m') for i in range(6, 0, -1)]})
    return result


def parameters(config):
    if config not in ('A', 'B'):
        raise ContractError('MODEL-001: unknown configuration')
    return dict(objective='regression', device_type='cpu', deterministic=True,
                force_col_wise=True, num_threads=1, random_state=SEED,
                data_random_seed=SEED, feature_fraction_seed=SEED, bagging_seed=SEED,
                drop_seed=SEED, extra_seed=SEED, histogram_pool_size=1024,
                n_estimators=160 if config == 'A' else 240,
                learning_rate=.04 if config == 'A' else .025,
                num_leaves=15 if config == 'A' else 31,
                max_depth=4 if config == 'A' else 5,
                min_child_samples=100 if config == 'A' else 200,
                colsample_bytree=.8, subsample=1., reg_lambda=1. if config == 'A' else 2.,
                verbosity=-1)


def fit_action(x, labels, tickers, config):
    from lightgbm import LGBMRegressor
    y = np.asarray(labels, dtype='float64')
    if (len(y) < 500 or not np.isfinite(y).all() or len(np.unique(y)) < 2
            or any(np.count_nonzero(np.asarray(tickers) == ticker) < 100 for ticker in TICKERS)):
        raise ContractError('BLOCKED_DATA: insufficient executable action labels')
    if len(x) != len(y):
        raise ContractError('MODEL-001: row mismatch')
    return LGBMRegressor(**parameters(config)).fit(x, y)


def choose_action(scores, threshold):
    from .contract import THRESHOLDS_USD
    scores = np.asarray(scores)
    if threshold not in THRESHOLDS_USD or scores.shape != (24,) or not np.isfinite(scores).all():
        raise ContractError('ECON-002: invalid scores/threshold')
    index = int(scores.argmax())
    return index if scores[index] > 0 and scores[index] >= threshold else None
