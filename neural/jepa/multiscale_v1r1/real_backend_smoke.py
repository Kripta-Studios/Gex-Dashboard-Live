"""One predeclared synthetic fold with all 72 real regressors; no real data API."""
import argparse
import json
import shutil
import threading
import time
from pathlib import Path

import lightgbm
import numpy as np
import pandas as pd
import psutil

from .artifacts import append_access, digest, publication, write_json
from .contract import ACTIONS, DISK_RESERVE, PROCESS_LIMIT, TICKERS, ContractError
from .features import schema
from .freeze import seal, verify
from .models import folds
from .payoff import simulate_action
from .real_backend import fit_bundle, matrix
from .scheduler import replay
from .selection import decisions_from_scores, ledger_metrics, select_winner
from .synthetic_engine import feature_bank
from .synthetic_fixtures import action_quotes, baseline_action, month_events


def training_events():
    candidates = [e for p in pd.period_range('2022-08', '2024-06', freq='M')
                  for e in month_events(p.strftime('%Y%m'))]
    rows = []
    for ticker in TICKERS:
        for signal in (-1, 1):
            group = [e for e in candidates if e['ticker'] == ticker and e['signal'] == signal]
            rows.extend(group[i] for i in np.linspace(0, len(group) - 1, 100, dtype=int))
    return sorted(rows, key=lambda e: (e['decision_timestamp'], e['ticker']))


class FixturePayoffs:
    def __init__(self, root, specification_hash):
        self.root, self.specification_hash = Path(root), specification_hash
        self.permit_hash = None

    def permit_test(self, manifest):
        self.permit_hash = digest(manifest)
        verify(manifest, '202501', self.specification_hash, self.permit_hash)
        append_access(self.root / 'access_log.jsonl', stage='freeze_verified', month='202501',
                      freeze_sha256=self.permit_hash)

    def generate(self, name, events):
        if name not in ('train', 'selection', 'test'):
            raise ContractError('REAL_BACKEND: unknown split')
        if name == 'test':
            if self.permit_hash is None:
                raise ContractError('FREEZE-001: test fixture payoff before freeze')
            verify(self.root / 'frozen/freeze_manifest.json', '202501', self.specification_hash, self.permit_hash)
        elif any(e['month'] >= '202501' for e in events):
            raise ContractError('FREEZE-001: future fixture payoff in history')
        result, quotes = {}, {}
        for event in events:
            rows = action_quotes(event)
            quotes[event['event_id']] = rows
            result[event['event_id']] = {str(a.action_id): simulate_action(rows, event['ticker'], event['trade_date'],
                                       event['decision_timestamp'], a.action_id) for a in ACTIONS}
        write_json(self.root / f'{name}_quotes.json', quotes)
        write_json(self.root / f'{name}_payoffs.json', result)
        append_access(self.root / 'access_log.jsonl', stage='fixture_payoff_created', split=name,
                      freeze_sha256=self.permit_hash if name == 'test' else None)
        return result


def run(destination, specification):
    root = Path(destination).resolve()
    root.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(root.parent).free < DISK_RESERVE + 2 * 1024**3:
        raise ContractError('BLOCKED_RESOURCE: insufficient fixture disk reserve')
    code = sorted(Path(__file__).parent.glob('*.py')) + sorted(Path(__file__).parent.with_name('multiscale_v1r1_audit').glob('*.py'))
    published = publication(Path.cwd(), [specification, *code])
    root.mkdir(exist_ok=False)
    start = time.perf_counter()
    process, stop, peak = psutil.Process(), threading.Event(), [0]

    def watch():
        while not stop.wait(.05):
            peak[0] = max(peak[0], process.memory_info().rss)

    monitor = threading.Thread(target=watch, daemon=True)
    monitor.start()
    try:
        write_json(root / 'profile.json', dict(profile='REAL_BACKEND_SYNTHETIC_JAN2025', publication=published,
                   historical_economics='NOT_EVALUATED', real_models=72, template_count=6, train_rows=600,
                   full_historical_run=False, promotion_approved=False))
        write_json(root / 'schema.json', schema())
        bank, feature_seconds = feature_bank(root / 'feature_fixtures')
        from neural.jepa.multiscale_v1r1_audit.tensor import audit_tensor_fixture
        write_json(root / 'feature_audit.json', {p.name: audit_tensor_fixture(p) for p in (root / 'feature_fixtures').iterdir()})
        fold = folds()[0]
        events = dict(train=training_events(), selection=[e for m in fold['selection'] for e in month_events(m)],
                      test=month_events('202501'))
        write_json(root / 'events.json', events)
        matrices, build_seconds = {}, {}
        for no_levels, label in ((False, 'primary'), (True, 'ablation')):
            for name, rows in events.items():
                t = time.perf_counter()
                matrices[(label, name)] = matrix(root / f'{label}_{name}.npy', rows, bank, no_levels)
                build_seconds[f'{label}_{name}'] = time.perf_counter() - t
        outcomes = FixturePayoffs(root, digest(specification))
        train = outcomes.generate('train', events['train'])
        selection = outcomes.generate('selection', events['selection'])
        scores = {}
        for config in ('A', 'B'):
            scores[config] = fit_bundle(root / 'models' / config, matrices[('primary', 'train')], events['train'], train,
                                       config, {name: matrices[('primary', name)] for name in ('selection', 'test')})
        winner, candidates = select_winner(events['selection'], {k: v['selection'] for k, v in scores.items()},
                                          lambda e, a: selection[e][str(a)], fold['selection'])
        write_json(root / 'selection.json', dict(winner=winner, candidates=candidates, fold=fold))
        if winner is None:
            raise ContractError('FAILED_FREQUENCY: real fixture selection failed; test closed')
        comparator = fit_bundle(root / 'models' / 'ablation', matrices[('ablation', 'train')], events['train'], train,
                                winner['config'], {'test': matrices[('ablation', 'test')]}, no_levels=True)
        for config, values in scores.items():
            for name, values_ in values.items():
                np.save(root / f'scores_{config}_{name}.npy', values_)
        np.save(root / 'scores_ablation_test.npy', comparator['test'])
        decisions = dict(primary=decisions_from_scores(events['test'], scores[winner['config']]['test'], winner['threshold']),
                         ablation=decisions_from_scores(events['test'], comparator['test'], winner['threshold']))
        decisions['baseline'] = [dict(event_id=e['event_id'], ticker=e['ticker'], month=e['month'], trade_date=e['trade_date'],
                                     decision_timestamp=e['decision_timestamp'], action_id=baseline_action(bank[(e['ticker'], e['signal'])]))
                                 for e in events['test']]
        write_json(root / 'decisions.json', decisions)
        write_json(root / 'runtime.json', dict(numpy=np.__version__, pandas=pd.__version__, lightgbm=lightgbm.__version__))
        write_json(root / 'code.json', {str(p.resolve()): digest(p) for p in code})
        inputs = [p for p in root.glob('*.npy') if not p.name.startswith('scores_')]
        inputs += list((root / 'feature_fixtures').rglob('*'))
        inputs = [p for p in inputs if p.is_file()] + [root / f'{s}_{kind}.json' for s in ('train', 'selection') for kind in ('quotes', 'payoffs')]
        write_json(root / 'inputs.json', {str(p.relative_to(root)): digest(p) for p in inputs})
        seal(root / 'frozen', '202501', digest(specification), dict(
            models=[p for p in (root / 'models').rglob('*') if p.is_file()], scores=list(root.glob('scores_*.npy')),
            decisions=[root / 'decisions.json', root / 'selection.json'], events=[root / 'events.json'],
            schema=[root / 'schema.json'], inputs=[root / 'inputs.json'], runtime=[root / 'runtime.json'], code=[root / 'code.json']))
        outcomes.permit_test(root / 'frozen/freeze_manifest.json')
        test = outcomes.generate('test', events['test'])
        ledgers = {name: replay(rows, lambda e, a: test[e][str(a)]) for name, rows in decisions.items()}
        write_json(root / 'ledger.json', ledgers)
        metrics = {name: {scenario: ledger_metrics(rows, ['202501'], scenario) for scenario in ('base', 'adverse')}
                   for name, rows in ledgers.items()}
        write_json(root / 'metrics.json', metrics)
        from neural.jepa.multiscale_v1r1_audit.real_backend import audit_run
        t = time.perf_counter()
        independent = audit_run(root)
        audit_seconds = time.perf_counter() - t
        write_json(root / 'audit.json', independent)
        result = dict(status='PASS_REAL_BACKEND_SYNTHETIC_FOLD', real_regressors=72, independent_refits=independent['refits'],
                      winner=winner, feature_seconds=feature_seconds, matrix_seconds=build_seconds, audit_seconds=audit_seconds,
                      elapsed_seconds=time.perf_counter() - start, peak_rss_bytes=peak[0], process_limit_bytes=PROCESS_LIMIT,
                      historical_economics='NOT_EVALUATED', technical_ready=False, prospective_validation_state='NOT_STARTED',
                      promotion_approved=False, limits='One technical synthetic fold, six low-entropy templates, 600 train rows; no historical inference')
        write_json(root / 'summary.json', result)
        return result
    finally:
        stop.set()
        monitor.join()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--specification', required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.root, args.specification), indent=2), flush=True)
