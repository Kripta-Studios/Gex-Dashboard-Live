"""Independent full-width matrix, real model refit, selection and execution audit."""
import gc
import hashlib
import json
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd

from neural.jepa.multiscale_v1r1.contract import ACTIONS, CHANNELS, CONTROLS, SEED, SLOTS, TICKERS
from .engine import checksum, expected_action, read, reconstruct_ledger, require, statistics
from .tensor import audit_tensor_fixture


def fixture_events(month):
    rows = []
    for i, date in enumerate(pd.bdate_range(month + '01', periods=13)):
        day = str(date.date())
        for ticker in TICKERS:
            for clock in ('11:30', '11:35'):
                when = pd.Timestamp(day + ' ' + clock, tz='America/New_York') + pd.Timedelta(milliseconds=1)
                rows.append(dict(event_id=f'{ticker}:{day}:{clock}:SYNTHETIC', ticker=ticker, trade_date=day,
                                 month=month, decision_timestamp=when.isoformat(), signal=1 if i % 2 == 0 else -1))
    return rows


def parameters(config):
    return dict(objective='regression', device_type='cpu', deterministic=True, force_col_wise=True,
                num_threads=1, random_state=SEED, data_random_seed=SEED, feature_fraction_seed=SEED,
                bagging_seed=SEED, drop_seed=SEED, extra_seed=SEED, histogram_pool_size=1024,
                n_estimators=160 if config == 'A' else 240, learning_rate=.04 if config == 'A' else .025,
                num_leaves=15 if config == 'A' else 31, max_depth=4 if config == 'A' else 5,
                min_child_samples=100 if config == 'A' else 200, colsample_bytree=.8, subsample=1.,
                reg_lambda=1. if config == 'A' else 2., verbosity=-1)


def decisions(events, scores, threshold):
    result = []
    for event, scores_ in zip(events, scores, strict=True):
        action = int(np.argmax(scores_))
        if scores_[action] <= 0 or scores_[action] < threshold:
            action = None
        result.append({**{key: event[key] for key in ('event_id', 'ticker', 'month', 'trade_date', 'decision_timestamp')},
                       'action_id': action})
    return result


def canonical_vectors(directory):
    values = {name: np.load(directory / f'{name}.npy') for name in ('x5', 'm5', 'x15', 'm15', 'static')}
    primary = np.concatenate([values[k].reshape(-1) for k in ('x5', 'm5', 'x15', 'm15', 'static')]).astype('float32')
    indices = [CHANNELS.index(name) for name in CONTROLS]
    pieces = []
    for x, mask in ((values['x5'], values['m5']), (values['x15'], values['m15'])):
        control, valid = x[:, :, indices], mask[:, :, indices]
        require(np.array_equal(control, np.broadcast_to(control[:, :1, :], control.shape)), 'level information in controls')
        require(np.array_equal(valid, np.broadcast_to(valid[:, :1, :], valid.shape)), 'level mask in ablation')
        pieces.extend([control[:, 0, :].reshape(-1), valid[:, 0, :].reshape(-1)])
    no_levels = np.concatenate([*pieces, values['static']]).astype('float32')
    x, mask = values['x5'][-1], values['m5'][-1]
    candidates = []
    for i, name in enumerate(SLOTS):
        if name in ('zero_gamma', 'max_dgex', 'min_dgex') or not mask[i, 4]:
            continue
        support = name.startswith(('min_', 'put_')) or name.endswith('_ibl') or '_lower_' in name
        defend = bool(x[i, CHANNELS.index('reclaim')] or x[i, CHANNELS.index('rejection')])
        retest = bool(x[i, CHANNELS.index('retest')])
        if defend or retest:
            action = 5 if support and defend or not support and retest else 17
            candidates.append((-x[i, CHANNELS.index('confluence')], abs(x[i, 4]), i, action))
    return primary, no_levels, min(candidates)[3] if candidates else None


def validate_matrix(matrix, events, bank, projection):
    width = 92048 if projection == 0 else 488
    require(matrix.shape == (len(events), width) and matrix.dtype == np.float32, 'matrix dimensions/dtype')
    for i, e in enumerate(events):
        require(np.array_equal(matrix[i], bank[(e['ticker'], e['signal'])][projection]), 'matrix feature/slot/mask mismatch')


def reconstruct_payoffs(root, name, events):
    quotes = read(root / f'{name}_quotes.json')
    actual = read(root / f'{name}_payoffs.json')
    require(set(quotes) == set(actual) == {e['event_id'] for e in events}, 'payoff/quote event universe')
    for event in events:
        for action in ACTIONS:
            require(expected_action(event, action.action_id, quotes[event['event_id']]) == actual[event['event_id']][str(action.action_id)],
                    'label/contract/clock/money mismatch')
    return actual


def verify_access(root):
    previous, rows = '0' * 64, []
    for i, line in enumerate((root / 'access_log.jsonl').read_text(encoding='utf-8').splitlines()):
        row = json.loads(line)
        digest = row.pop('record_sha256')
        require(row['sequence'] == i and row['previous_sha256'] == previous, 'access chain order')
        raw = json.dumps(row, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()
        require(hashlib.sha256(raw).hexdigest() == digest, 'access chain digest')
        rows.append(row)
        previous = digest
    require([r['stage'] for r in rows] == ['fixture_payoff_created', 'fixture_payoff_created', 'freeze_verified', 'fixture_payoff_created'],
            'test access before freeze/order')
    require([rows[i].get('split') for i in (0, 1, 3)] == ['train', 'selection', 'test'], 'payoff access split')
    require(rows[2]['freeze_sha256'] == rows[3]['freeze_sha256'] == checksum(root / 'frozen/freeze_manifest.json'), 'access freeze hash')


def audit_run(root):
    from lightgbm import LGBMRegressor
    root = Path(root)
    verify_access(root)
    freeze = read(root / 'frozen/freeze_manifest.json')
    require(freeze['month'] == '202501' and set(freeze['artifacts']) == {'models', 'scores', 'decisions', 'events', 'schema', 'inputs', 'runtime', 'code'}, 'freeze contract')
    schema = read(root / 'schema.json')
    require(schema['slots'] == list(SLOTS) and schema['channels'] == list(CHANNELS)
            and schema['controls'] == list(CONTROLS) and schema['primary_dim'] == 92048
            and schema['ablation_dim'] == 488, 'feature schema')
    for entries in freeze['artifacts'].values():
        require(bool(entries), 'empty freeze')
        for item in entries:
            require(checksum(item['path']) == item['sha256'], 'frozen artifact changed')
    for name, digest in read(root / 'inputs.json').items():
        require(checksum(root / name) == digest, 'input dependency changed')
    for name, digest in read(root / 'code.json').items():
        require(checksum(name) == digest, 'code changed')
    bank = {}
    for directory in (root / 'feature_fixtures').iterdir():
        audit_tensor_fixture(directory)
        identity = read(directory / 'identity.json')
        bank[(identity['ticker'], identity['signal'])] = canonical_vectors(directory)
    require(len(bank) == 6, 'template universe')
    selection_months = [f'2024{i:02d}' for i in range(7, 13)]
    all_train = [e for p in pd.period_range('2022-08', '2024-06', freq='M') for e in fixture_events(p.strftime('%Y%m'))]
    train = []
    for ticker in TICKERS:
        for sign in (-1, 1):
            group = [e for e in all_train if e['ticker'] == ticker and e['signal'] == sign]
            train.extend(group[i] for i in np.linspace(0, len(group) - 1, 100, dtype=int))
    train.sort(key=lambda e: (e['decision_timestamp'], e['ticker']))
    events = dict(train=train, selection=[e for m in selection_months for e in fixture_events(m)], test=fixture_events('202501'))
    require(events == read(root / 'events.json'), 'train/selection/test calendar or sampling')
    matrices = {}
    for projection, name in enumerate(('primary', 'ablation')):
        for split, rows in events.items():
            matrices[(name, split)] = np.load(root / f'{name}_{split}.npy', mmap_mode='r')
            validate_matrix(matrices[(name, split)], rows, bank, projection)
    payoffs = {name: reconstruct_payoffs(root, name, rows) for name, rows in events.items()}
    refits, scored = 0, {}
    selection = read(root / 'selection.json')
    for name, kind, config in [('A', 'primary', 'A'), ('B', 'primary', 'B'), ('ablation', 'ablation', selection['winner']['config'])]:
        folder = root / 'models' / name
        meta = read(folder / 'bundle.json')
        require(len(meta['entries']) == 24 and meta['config'] == config
                and meta['columns'] == (488 if kind == 'ablation' else 92048)
                and meta['no_levels'] == (kind == 'ablation'), 'model bundle')
        splits = ('test',) if kind == 'ablation' else ('selection', 'test')
        scored[name] = {s: np.empty((len(events[s]), 24)) for s in splits}
        for action_id, item in enumerate(meta['entries']):
            require(item['action_id'] == action_id, 'action model identity')
            positions, labels = [], []
            for i, e in enumerate(train):
                p = payoffs['train'][e['event_id']][str(action_id)]
                if p['action_available']:
                    positions.append(i)
                    labels.append(float(p['base']['net_dollar_pnl']))
            require(len(labels) >= 500 and len(set(labels)) >= 2, 'fit label support')
            require(all(sum(train[i]['ticker'] == t for i in positions) >= 100 for t in TICKERS), 'ticker fit support')
            model = LGBMRegressor(**parameters(config)).fit(matrices[(kind, 'train')][positions], np.asarray(labels, dtype='float64'))
            path = folder / item['model']
            require(checksum(path) == item['sha256'], 'model hash')
            require(model.booster_.model_to_string().replace('\r\n', '\n') == path.read_text(encoding='utf-8'), 'real refit model bytes')
            require(dict(model.booster_.params) == item['parameters'], 'effective model parameters')
            for split in splits:
                x = matrices[(kind, split)]
                for start in range(0, len(x), 256):
                    scored[name][split][start:start + 256, action_id] = model.booster_.predict(x[start:start + 256], num_threads=1)
            refits += 1
            print(f'independent real refit {name} action={action_id:02d}', flush=True)
            del model
            gc.collect()
        for split in splits:
            require(np.array_equal(scored[name][split], np.load(root / f'scores_{name}_{split}.npy')), 'real prediction vector')
    candidates = []
    for ci, config in enumerate(('A', 'B')):
        for ti, threshold in enumerate((0., 5.)):
            ledger = reconstruct_ledger(decisions(events['selection'], scored[config]['selection'], threshold), payoffs['selection'])
            metrics = statistics(ledger, selection_months)
            eligible = all(min(m['monthly_counts'].values()) >= 13 for m in metrics.values())
            require(dict(config=config, threshold=threshold, eligible=eligible, metrics=metrics) == selection['candidates'][ci * 2 + ti], 'selection candidate metrics')
            if eligible:
                rank = (min(float(m['pf']) if m['pf'] is not None else -np.inf for m in metrics.values()),
                        min(m['wr'] or 0 for m in metrics.values()), min(Decimal(m['net_dollar_pnl']) for m in metrics.values()), -ci, -ti)
                candidates.append((rank, dict(config=config, threshold=threshold)))
    require(bool(candidates), 'no eligible winner')
    winner = max(candidates, key=lambda item: item[0])[1]
    require(winner == selection['winner'], 'winner mismatch')
    actual = read(root / 'decisions.json')
    for name, collection in [('primary', winner['config']), ('ablation', 'ablation')]:
        require(decisions(events['test'], scored[collection]['test'], winner['threshold']) == actual[name], 'test decisions')
    baseline = [{**{k: e[k] for k in ('event_id', 'ticker', 'month', 'trade_date', 'decision_timestamp')},
                 'action_id': bank[(e['ticker'], e['signal'])][2]} for e in events['test']]
    require(baseline == actual['baseline'], 'baseline decision')
    ledgers, metrics = read(root / 'ledger.json'), read(root / 'metrics.json')
    for name, rows in actual.items():
        expected = reconstruct_ledger(rows, payoffs['test'])
        require(expected == ledgers[name], 'real-model scheduler/ledger')
        for scenario in ('base', 'adverse'):
            require(statistics(expected, ['202501'], scenario) == metrics[name][scenario], 'scenario metrics')
    require(all(m['trades'] == 13 and m['wr'] == 1. for m in metrics['primary']['base'].values()), 'designed synthetic signal not learned')
    return dict(status='PASS_INDEPENDENT_REAL_BACKEND_SYNTHETIC_AUDIT', refits=refits, matrices=6,
                payoffs_reconstructed=sum(len(e) for e in events.values()) * 24, winners=1, mismatches=0,
                historical_economics='NOT_EVALUATED', promotion_approved=False)
