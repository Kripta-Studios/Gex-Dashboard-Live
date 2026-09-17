"""Executable synthetic-only monthly research circuit; never opens ThetaData."""
import time
import json
import threading
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pandas as pd
import psutil

from .account import replay_account
from .artifacts import append_access, digest, write_json
from .bootstrap import paired_bootstrap
from .contract import ACTIONS, TICKERS, ContractError
from .checkpoint import save_checkpoint, verify_resume
from .features import ablation, flatten, schema
from .freeze import seal, verify
from .interactions import build_event
from .models import folds
from .payoff import simulate_action
from .scheduler import replay
from .selection import decisions_from_scores, ledger_metrics, select_winner
from .synthetic_fixtures import FixtureRegressor, action_quotes, baseline_action, month_events, source_fixture


class SyntheticOutcomes:
    """Generation/access is denied for current/future test before its freeze."""
    def __init__(self, root, contract_hash):
        self.root, self.contract_hash = Path(root), contract_hash
        self.cache = {}
        self.test_month = None
        self.freeze = None
        self.freeze_hash = None

    def begin_fold(self, month):
        self.test_month, self.freeze, self.freeze_hash = month, None, None

    def permit(self, path):
        checksum = digest(path)
        verify(path, self.test_month, self.contract_hash, checksum)
        self.freeze, self.freeze_hash = Path(path), checksum
        append_access(self.root / 'access_log.jsonl', stage='freeze_verified', month=self.test_month,
                      freeze_sha256=checksum, profile='synthetic_fast')

    def month(self, month):
        if self.test_month is None or month > self.test_month:
            raise ContractError('FREEZE-001: future synthetic outcome access')
        if month == self.test_month:
            if self.freeze is None:
                raise ContractError('FREEZE-001: synthetic test access before freeze')
            verify(self.freeze, month, self.contract_hash, self.freeze_hash)
        if month not in self.cache:
            existing = self.root / 'payoffs' / f'{month}.json'
            if existing.exists():
                self.cache[month] = {event_id: {int(action): facts for action, facts in actions.items()}
                                     for event_id, actions in json.loads(existing.read_bytes()).items()}
                return self.cache[month]
            records = {}
            for event in month_events(month):
                quotes = action_quotes(event)
                records[event['event_id']] = {
                    action.action_id: simulate_action(quotes, event['ticker'], event['trade_date'],
                                                     event['decision_timestamp'], action.action_id)
                    for action in ACTIONS}
            self.cache[month] = records
            append_access(self.root / 'access_log.jsonl', stage='synthetic_outcome_created', month=month,
                          active_test=self.test_month, freeze_sha256=self.freeze_hash if month == self.test_month else None)
            write_json(self.root / 'payoffs' / f'{month}.json', records)
        return self.cache[month]


def feature_bank(root):
    bank, metrics = {}, {}
    for ticker in TICKERS:
        for signal in (-1, 1):
            clock = time.perf_counter()
            frame, quotes, oi, prior = source_fixture(ticker=ticker, direction=signal)
            event = build_event(frame, prior, quotes, oi, ticker, '2025-01-10',
                                pd.Timestamp('2025-01-10 11:35', tz='America/New_York'), 99.8)
            key = f'{ticker}_{signal}'
            bank[(ticker, signal)] = event
            folder = root / key
            folder.mkdir(parents=True)
            for name in ('x5', 'm5', 'x15', 'm15', 'static'):
                np.save(folder / f'{name}.npy', event[name])
            frame.to_parquet(folder / 'bars.parquet', index=False)
            quotes.to_parquet(folder / 'greeks.parquet', index=False)
            oi.to_parquet(folder / 'oi.parquet', index=False)
            for day, source in prior.items():
                source.to_parquet(folder / f'ib_{day}.parquet')
            write_json(folder / 'identity.json', dict(ticker=ticker, signal=signal, day='2025-01-10',
                       decision='2025-01-10T11:35:00-05:00', prior_close=99.8, synthetic=True))
            metrics[key] = time.perf_counter() - clock
    return bank, metrics


def inputs(events, bank, no_levels=False):
    # Fast orchestration consumes a deterministic projection from complete fixture
    # tensors. It is explicitly a test double input, never a production representation.
    values = {}
    for key, event in bank.items():
        args = [event[k] for k in ('x5', 'm5', 'x15', 'm15', 'static')]
        vector = ablation(*args) if no_levels else flatten(*args)
        values[key] = float(vector[3] if not no_levels else vector[0])
    return np.array([values[(e['ticker'], e['signal'])] for e in events])


def fit_bundle(events, bank, outcomes, config, no_levels=False):
    x = inputs(events, bank, no_levels)
    targets = np.array([[outcomes[e['month']][e['event_id']][action.action_id]['base']['net_dollar_pnl']
                         for action in ACTIONS] for e in events], dtype=float)
    return [FixtureRegressor(config, action.action_id).fit(x, targets[:, action.action_id]) for action in ACTIONS]


def score(models, events, bank, no_levels=False):
    x = inputs(events, bank, no_levels)
    return np.column_stack([model.predict(x) for model in models])


def daily_statistics(ledger):
    daily = defaultdict(lambda: np.zeros(5))
    for row in ledger:
        if row['reason'] != 'EXECUTED':
            continue
        pnl = float(row['payoff']['base']['net_dollar_pnl'])
        daily[(row['ticker'], row['trade_date'])] += [pnl, max(pnl, 0), max(-pnl, 0), int(pnl > 0), 1]
    return daily


@contextmanager
def new_run_directory(root, resume, contract_hash):
    # Keep absolute frozen paths stable. Partial runs lack a summary PASS; never
    # rename their parent after writing a freeze with absolute artifact paths.
    if resume:
        verify_resume(root, contract_hash)
    else:
        root.mkdir(parents=True, exist_ok=False)
        write_json(root / 'run_started.json', {'state': 'RUNNING', 'profile': 'synthetic_fast'})
    process = psutil.Process()
    peak = [process.memory_info().rss]
    stop = threading.Event()

    def monitor():
        while not stop.wait(.05):
            peak[0] = max(peak[0], process.memory_info().rss)

    worker = threading.Thread(target=monitor, daemon=True)
    worker.start()
    try:
        yield root
    finally:
        stop.set()
        worker.join()
        # Failed runs have no PASS summary. Do not add a file after a resumable
        # fold checkpoint unless the run actually reached its final summary.
        if (root / 'summary.json').exists():
            write_json(root / 'resource_measurements.json', dict(peak_rss_bytes=peak[0],
                        artifact_bytes=sum(p.stat().st_size for p in root.rglob('*') if p.is_file()),
                        sampling_interval_seconds=.05, profile='synthetic_fast',
                        full_historical_training_measured=False))


def run(root, specification, resume=False):
    """One command creates nonempty monthly freezes, models, ledgers and audits."""
    start = time.perf_counter()
    root = Path(root)
    contract_hash = digest(specification)
    with new_run_directory(root, resume, contract_hash) as out:
        if not resume:
            (out / 'payoffs').mkdir()
            write_json(out / 'profile.json', dict(profile='synthetic_fast', input_source='generated fixtures only',
                   models='TEST_DOUBLE_GROUP_MEANS', historical_economics='NOT_EVALUATED',
                   feature_projection='Explicit test-double scalar from canonical tensor; not V1R1 training representation',
                   folds=18, actions=24, real_training_smoke='separate command/artifact', promotion_approved=False))
            write_json(out / 'schema.json', schema())
            bank, feature_times = feature_bank(out / 'feature_fixtures')
            from neural.jepa.multiscale_v1r1_audit.tensor import audit_tensor_fixture
            write_json(out / 'feature_audit.json', {p.name: audit_tensor_fixture(p) for p in (out / 'feature_fixtures').iterdir()})
            write_json(out / 'feature_timings.json', feature_times)
        else:
            bank = {}
            for directory in (out / 'feature_fixtures').iterdir():
                identity = json.loads((directory / 'identity.json').read_bytes())
                bank[(identity['ticker'], identity['signal'])] = {k: np.load(directory / f'{k}.npy') for k in ('x5', 'm5', 'x15', 'm15', 'static')}
            feature_times = json.loads((out / 'feature_timings.json').read_bytes())
        outcomes = SyntheticOutcomes(out, contract_hash)
        ledgers = {name: [] for name in ('primary', 'ablation', 'baseline')}
        selection_results = []
        for fold in folds():
            month = fold['month']
            if resume and (out / 'checkpoints' / f'{month}.json').exists():
                from neural.jepa.multiscale_v1r1_audit.engine import audit_fold
                audit_fold(out / 'folds' / month, out)
                completed = json.loads((out / 'folds' / month / 'ledger.json').read_bytes())
                for name, rows in completed.items():
                    ledgers[name].extend(rows)
                selection_results.append(dict(month=month, winner=json.loads((out / 'folds' / month / 'selection.json').read_bytes())['winner'], resumed=True))
                continue
            fold_start = time.perf_counter()
            outcomes.begin_fold(month)
            train_months = [p.strftime('%Y%m') for p in pd.period_range('2022-08', pd.Period(fold['train_end'], freq='M'), freq='M')]
            train = [e for m in train_months for e in month_events(m)]
            selection = [e for m in fold['selection'] for e in month_events(m)]
            test = month_events(month)
            historical = {m: outcomes.month(m) for m in train_months + fold['selection']}
            def lookup(event_id, action_id):
                return historical[event_id.split(':')[1].replace('-', '')[:6]][event_id][action_id]
            models = {config: fit_bundle(train, bank, historical, config) for config in ('A', 'B')}
            selection_scores = {config: score(bundle, selection, bank) for config, bundle in models.items()}
            winner, candidates = select_winner(selection, selection_scores, lookup, fold['selection'])
            if winner is None:
                raise ContractError('FAILED_FREQUENCY: no synthetic winner; test remains closed')
            comparator = fit_bundle(train, bank, historical, winner['config'], no_levels=True)
            test_scores = dict(primary=score(models[winner['config']], test, bank),
                               ablation=score(comparator, test, bank, no_levels=True))
            decisions = {name: decisions_from_scores(test, scores, winner['threshold']) for name, scores in test_scores.items()}
            decisions['baseline'] = [dict(event_id=e['event_id'], ticker=e['ticker'], month=month, trade_date=e['trade_date'],
                                          decision_timestamp=e['decision_timestamp'], action_id=baseline_action(bank[(e['ticker'], e['signal'])])) for e in test]
            folder = out / 'folds' / month
            folder.mkdir(parents=True)
            write_json(folder / 'selection.json', dict(winner=winner, candidates=candidates, fold=fold, synthetic_only=True))
            write_json(folder / 'models.json', {config: [model.artifact() for model in bundle] for config, bundle in models.items()})
            write_json(folder / 'ablation_models.json', [model.artifact() for model in comparator])
            pd.DataFrame(test).to_parquet(folder / 'events.parquet', index=False)
            for name, scores in test_scores.items():
                np.save(folder / f'{name}_scores.npy', scores)
            write_json(folder / 'decisions.json', decisions)
            write_json(folder / 'inputs.json', dict(train=train_months, selection=fold['selection'],
                        payoff_hashes={m: digest(out / 'payoffs' / f'{m}.json') for m in historical},
                        fixture_hashes={str(p.relative_to(out)): digest(p) for p in (out / 'feature_fixtures').rglob('*') if p.is_file()}))
            write_json(folder / 'runtime.json', dict(profile='synthetic_fast', numpy=np.__version__, pandas=pd.__version__))
            code_paths = list(Path(__file__).parent.glob('*.py')) + list(Path(__file__).parent.with_name('multiscale_v1r1_audit').glob('*.py'))
            write_json(folder / 'code.json', {str(p.resolve()): digest(p) for p in code_paths})
            seal(folder / 'frozen', month, contract_hash, dict(
                models=[folder / 'models.json', folder / 'ablation_models.json'],
                scores=[folder / 'primary_scores.npy', folder / 'ablation_scores.npy'],
                decisions=[folder / 'decisions.json'], events=[folder / 'events.parquet'], schema=[out / 'schema.json'],
                inputs=[folder / 'inputs.json'], runtime=[folder / 'runtime.json'], code=[folder / 'code.json']))
            outcomes.permit(folder / 'frozen/freeze_manifest.json')
            payoffs = outcomes.month(month)
            month_ledgers = {name: replay(rows, lambda e, a: payoffs[e][a]) for name, rows in decisions.items()}
            write_json(folder / 'ledger.json', month_ledgers)
            from neural.jepa.multiscale_v1r1_audit.engine import audit_fold
            audit = audit_fold(folder, out, bank_expected=True)
            write_json(folder / 'audit.json', audit)
            for name, rows in month_ledgers.items():
                ledgers[name].extend(rows)
            selection_results.append(dict(month=month, winner=winner, seconds=time.perf_counter() - fold_start))
            save_checkpoint(out, month, code_paths, contract_hash)
            print(f'synthetic fold={month} audit={audit["status"]}', flush=True)
        months = [fold['month'] for fold in folds()]
        metrics = {name: {scenario: ledger_metrics(rows, months, scenario) for scenario in ('base', 'adverse')}
                   for name, rows in ledgers.items()}
        write_json(out / 'metrics.json', metrics)
        calendar = {m: sorted({e['trade_date'] for e in month_events(m)}) for m in months}
        bootstrap = paired_bootstrap(daily_statistics(ledgers['primary']), daily_statistics(ledgers['ablation']), calendar)
        write_json(out / 'bootstrap.json', bootstrap)
        account = replay_account(ledgers['primary'], out / 'paper_account.jsonl', '350.00')
        write_json(out / 'account_summary.json', account)
        from .scenarios import run_scenarios
        run_scenarios(out / 'scenarios')
        from neural.jepa.multiscale_v1r1_audit.summary import audit_summary
        write_json(out / 'summary_audit.json', audit_summary(out))
        result = dict(status='ENGINE_E2E_SYNTHETIC_PASS', profile='synthetic_fast', fold_count=18,
                      scenario='artificial deterministic learnable signal', selection=selection_results,
                      feature_build_seconds=feature_times, elapsed_seconds=time.perf_counter() - start,
                      historical_economics='NOT_EVALUATED', technical_ready=False,
                      prospective_validation_state='NOT_STARTED', promotion_approved=False,
                      limits='Test-double fits; separate full-width real LightGBM smoke required; SSL/RANGE training not certified')
        write_json(out / 'summary.json', result)
    return result
