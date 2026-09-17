"""Sequential full-width LightGBM bundles. No source or payoff access capability."""
import gc
import time
from pathlib import Path

import numpy as np
import psutil

from .artifacts import digest, write_json
from .contract import ACTIONS, ABLATION_DIM, BLOCK_SIZE, PRIMARY_DIM, PROCESS_LIMIT, ContractError
from .features import ablation, flatten
from .models import fit_action


def matrix(path, events, bank, no_levels=False):
    width = ABLATION_DIM if no_levels else PRIMARY_DIM
    path = Path(path)
    if path.exists():
        raise ContractError('REAL_BACKEND: matrix already exists')
    vectors = {}
    for key, value in bank.items():
        args = [value[name] for name in ('x5', 'm5', 'x15', 'm15', 'static')]
        vectors[key] = (ablation if no_levels else flatten)(*args)
    x = np.lib.format.open_memmap(path, mode='w+', dtype='float32', shape=(len(events), width))
    for start in range(0, len(events), BLOCK_SIZE):
        for i in range(start, min(start + BLOCK_SIZE, len(events))):
            event = events[i]
            x[i] = vectors[(event['ticker'], event['signal'])]
    x.flush()
    return np.load(path, mmap_mode='r')


def action_labels(events, outcomes, action_id):
    selected, values, tickers = [], [], []
    for i, event in enumerate(events):
        facts = outcomes[event['event_id']][str(action_id)]
        if facts['action_available']:
            selected.append(i)
            values.append(float(facts['base']['net_dollar_pnl']))
            tickers.append(event['ticker'])
    return np.asarray(selected, dtype=np.int64), np.asarray(values, dtype=np.float64), tickers


def predict_blocks(booster, x):
    result = np.empty(len(x), dtype='float64')
    for start in range(0, len(x), BLOCK_SIZE):
        end = min(start + BLOCK_SIZE, len(x))
        result[start:end] = booster.predict(x[start:end], num_threads=1)
    if not np.isfinite(result).all():
        raise ContractError('REAL_BACKEND: nonfinite predictions')
    return result


def fit_bundle(destination, x, events, outcomes, config, score_sets, no_levels=False):
    from lightgbm import Booster
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=False)
    expected_width = ABLATION_DIM if no_levels else PRIMARY_DIM
    if x.shape != (len(events), expected_width) or x.dtype != np.float32:
        raise ContractError('REAL_BACKEND: noncanonical matrix')
    scores = {name: np.empty((len(data), 24), dtype='float64') for name, data in score_sets.items()}
    entries = []
    for action in ACTIONS:
        rows, y, tickers = action_labels(events, outcomes, action.action_id)
        estimate = len(rows) * expected_width * 12 + 1024**3
        if psutil.Process().memory_info().rss + estimate > PROCESS_LIMIT:
            raise ContractError('BLOCKED_RESOURCE: real fit process budget')
        start = time.perf_counter()
        model = fit_action(x[rows], y, tickers, config)
        fit_seconds = time.perf_counter() - start
        filename = root / f'action_{action.action_id:02d}.txt'
        start = time.perf_counter()
        model.booster_.save_model(str(filename))
        save_seconds = time.perf_counter() - start
        start = time.perf_counter()
        restored = Booster(model_file=str(filename))
        load_seconds = time.perf_counter() - start
        start = time.perf_counter()
        for name, data in score_sets.items():
            actual = predict_blocks(model.booster_, data)
            if not np.array_equal(actual, predict_blocks(restored, data)):
                raise ContractError('REAL_BACKEND: saved model prediction mismatch')
            scores[name][:, action.action_id] = actual
        prediction_seconds = time.perf_counter() - start
        entries.append(dict(action_id=action.action_id, model=filename.name, sha256=digest(filename),
                            rows=len(rows), target_values=len(np.unique(y)), parameters=dict(model.booster_.params),
                            fit_seconds=fit_seconds, save_seconds=save_seconds, load_seconds=load_seconds,
                            prediction_and_reload_verification_seconds=prediction_seconds))
        print(f'real fit {root.name} action={action.action_id:02d} rows={len(rows)} seconds={fit_seconds:.2f}', flush=True)
        del restored, model
        gc.collect()
    write_json(root / 'bundle.json', dict(config=config, no_levels=no_levels, columns=expected_width,
                                         prediction_unit='USD_per_contract', entries=entries))
    return scores
