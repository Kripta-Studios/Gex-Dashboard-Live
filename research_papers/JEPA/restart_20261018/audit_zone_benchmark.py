"""Independent audit of frozen zone benchmark artifacts; no producer imports.

Recomputes accounting, validation selection, scheduler, model fits/predictions,
source checksums and selected test fills. This audits a development simulation,
not original receipt times, market fills, dealer positions or future profitability.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

TICKERS = ('SPXW', 'SPY', 'QQQ')
ARMS = ('price', 'authentic', 'placebo')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for data in iter(lambda: handle.read(8 * 1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def close(a, b, message):
    require(bool(np.isclose(float(a), float(b), rtol=0, atol=1e-7, equal_nan=True)), message)


def net_dollars(ask, bid, adverse=False):
    slip = Decimal('.02' if adverse else '.01')
    proceeds = max(Decimal(str(bid)) - slip, Decimal(0))
    return float((proceeds - Decimal(str(ask)) - slip) * 100 - Decimal('2.60'))


def independent_schedule(rows, threshold):
    if threshold is None:
        return rows.iloc[:0].copy()
    keep = []
    released = {}
    records = rows.to_dict('records')
    by_event = {}
    for row in records:
        by_event.setdefault((row['decision'], row['ticker_name']), []).append(row)
    for event in sorted(by_event):
        candidates = by_event[event]
        require(all(np.isfinite(row['prediction']) for row in candidates), 'Nonfinite prediction')
        selected = min(candidates, key=lambda row: (-row['prediction'], row['right']))
        decision = pd.Timestamp(selected['decision'])
        ticker = selected['ticker_name']
        if selected['prediction'] <= threshold or decision < released.get(ticker, pd.Timestamp.min):
            continue
        # Missing future entry cannot change the already selected action.
        if not np.isfinite(selected['net']):
            continue
        entry = pd.Timestamp(selected['entry_time'])
        exit_time = pd.Timestamp(selected['exit_time'])
        require(entry == decision + pd.Timedelta(minutes=1), 'Entry scheduling mismatch')
        require(exit_time == entry + pd.Timedelta(minutes=30), 'Hold scheduling mismatch')
        keep.append(selected)
        released[ticker] = exit_time
    return pd.DataFrame(keep, columns=rows.columns)


def comparable_metrics(rows):
    result = {'trades': len(rows)}
    for col, name in (('net', 'base'), ('adverse_net', 'adverse')):
        values = rows[col].to_numpy(float)
        gains = values[values > 0].sum()
        losses = -values[values < 0].sum()
        result[name + '_net_usd'] = float(values.sum())
        result[name + '_win_rate'] = float(np.mean(values > 0)) if len(values) else None
        result[name + '_profit_factor'] = float(gains / losses) if losses > 0 else None
    return result


def compare_metrics(actual, reported, context):
    require(actual.keys() == reported.keys(), 'Metric keys differ ' + context)
    for key, value in actual.items():
        if value is None:
            require(reported[key] is None, context + ' ' + key)
        else:
            close(value, reported[key], context + ' ' + key)


def raw_quotes(path, ticker, date):
    cols = ['symbol', 'expiration', 'trade_date', 'strike', 'right', 'timestamp', 'bid', 'ask', 'delta']
    frame = pq.read_table(path, columns=cols).to_pandas()
    frame['right'] = frame.right.astype(str).str.upper().replace({'C': 'CALL', 'P': 'PUT'})
    frame['strike'] = pd.to_numeric(frame.strike, errors='coerce')
    for field in ('expiration', 'trade_date', 'timestamp'):
        frame[field] = pd.to_datetime(frame[field].astype(str), format='ISO8601', errors='coerce')
        require(frame[field].dt.tz is None, 'Unexpected timezone in raw source')
    day = pd.Timestamp(date)
    keep = ((frame.symbol == ticker) & (frame.expiration.dt.normalize() == day)
            & (frame.trade_date.dt.normalize() == day) & (frame.timestamp.dt.normalize() == day)
            & frame.right.isin(['CALL', 'PUT']) & np.isfinite(frame.strike) & (frame.strike > 0)
            & (frame.timestamp == frame.timestamp.dt.floor('min'))
            & (frame.timestamp >= day + pd.Timedelta(hours=9, minutes=30))
            & (frame.timestamp <= day + pd.Timedelta(hours=16)))
    frame = frame.loc[keep].copy()
    frame = frame.loc[~frame.duplicated(['strike', 'right', 'timestamp'], keep=False)]
    valid = (np.isfinite(frame.bid) & np.isfinite(frame.ask) & (frame.bid >= 0)
             & (frame.ask > 0) & (frame.bid <= frame.ask))
    return frame.loc[valid].copy()


def audit(root, output):
    freeze = json.loads((root / 'freeze.json').read_text(encoding='utf-8'))
    identity = json.loads((root / 'run_identity.json').read_text(encoding='utf-8'))
    summary = json.loads((root / 'summary.json').read_text(encoding='utf-8'))
    completion = json.loads((root / 'completion.json').read_text(encoding='utf-8'))
    sources = json.loads((root / 'sources.json').read_text(encoding='utf-8'))
    coverage = json.loads((root / 'coverage.json').read_text(encoding='utf-8'))
    expected_config = dict(n_estimators=150, num_leaves=15, max_depth=5,
                           min_child_samples=80, learning_rate=.04, reg_lambda=10,
                           n_jobs=2, random_state=20261018, verbosity=-1,
                           deterministic=True, force_col_wise=True)
    require(freeze['config'] == expected_config, 'Model configuration differs from fixed benchmark')
    require(summary['thresholds'] == freeze['representations'], 'Reported frozen selection differs')
    require(summary['coverage'] == coverage, 'Reported coverage differs')
    require(completion['summary_sha256'] == digest(root / 'summary.json'), 'Summary seal differs')
    require(completion['source_count'] == len(sources), 'Source count differs')
    require(freeze['test_payoffs_constructed'] is False, 'No pre-test freeze claim')
    for filename, key in [('frozen_predictions.parquet', 'prediction_sha256'), ('features.parquet', 'features_sha256'),
                          ('candidates.parquet', 'candidates_sha256'), ('sources.json', 'sources_sha256'),
                          ('train_validation_labels.parquet', 'train_validation_labels_sha256'),
                          ('zone_benchmark.py', 'script_sha256'), ('BENCHMARK_SPEC.md', 'spec_sha256')]:
        require(digest(root / filename) == freeze[key], 'Frozen hash differs: ' + filename)
    require(identity['script_sha256'] == freeze['script_sha256'], 'Code changed during run')
    require(identity['spec_sha256'] == freeze['spec_sha256'], 'Spec changed during run')
    for filename, expected in freeze['models'].items():
        require(digest(root / filename) == expected, 'Model seal differs: ' + filename)
    freeze_time = datetime.fromisoformat(freeze['frozen_at_utc']).timestamp()
    require(freeze_time <= (root / 'test_labels.parquet').stat().st_mtime, 'Test output predates freeze')

    source_results = {}
    source_counts = Counter()
    for n, (path, metadata) in enumerate(sources.items()):
        p = Path(path)
        require(p.stat().st_size == metadata['bytes'], 'Source size differs: ' + path)
        actual = digest(p)
        require(actual == metadata['sha256'], 'Source hash differs: ' + path)
        source_results[path] = actual
        source_counts[p.stem.split('_')[0]] += 1
        if n % 100 == 0:
            print(json.dumps({'audit_stage': 'source_rehash', 'done': n + 1, 'total': len(sources)}), flush=True)
    for ticker in TICKERS:
        require(source_counts[ticker] == 2 * coverage['days_read_' + ticker], 'Coverage/source file count differs ' + ticker)
        require(coverage['decision_candidates_' + ticker] == 10 * coverage['days_read_' + ticker], 'Decision count differs ' + ticker)

    features = pd.read_parquet(root / 'features.parquet')
    candidates = pd.read_parquet(root / 'candidates.parquet')
    predictions = pd.read_parquet(root / 'frozen_predictions.parquet')
    train_labels = pd.read_parquet(root / 'train_validation_labels.parquet')
    test_labels = pd.read_parquet(root / 'test_labels.parquet')
    labels = pd.concat([train_labels, test_labels], ignore_index=True)
    require(not features.event_id.duplicated().any(), 'Feature IDs duplicate')
    require(not candidates.duplicated(['event_id', 'right']).any(), 'Candidate IDs duplicate')
    require(not labels.duplicated(['event_id', 'right']).any(), 'Label IDs duplicate')
    require(not predictions.duplicated(['representation', 'event_id', 'right']).any(), 'Prediction IDs duplicate')
    require(len(labels) == len(candidates) and len(predictions) == 3 * len(candidates), 'Candidate/label/prediction count differs')
    require(not set(('net', 'adverse_net', 'entry_ask', 'exit_bid', 'missing_exit')).intersection(predictions), 'Outcome field in prediction artifact')
    labeled = candidates.merge(labels, on=['event_id', 'right'], validate='one_to_one')
    require((train_labels.event_id.str.split('_').str[1] < '20231001').all(), 'Test labels in train/validation file')
    require((test_labels.event_id.str.split('_').str[1] >= '20231001').all(), 'Earlier labels in test file')
    require(not candidates.date.isin(['20230703', '20231124']).any(), 'Early-close event present')
    require(candidates.date.between('20230101', '20231231').all(), 'Out-of-year candidate')
    for (ticker, date), subset in candidates.groupby(['ticker_name', 'date']):
        hashed = hashlib.sha256(f'20261018|{ticker}|{date}'.encode()).digest()
        magnitude = .2 + .6 * int.from_bytes(hashed[1:9], 'big') / (2**64 - 1)
        expected_shift = magnitude if hashed[0] % 2 == 0 else -magnitude
        require(np.array_equal(subset.placebo_shift_ib_units_diagnostic_only.to_numpy(float),
                               np.full(len(subset), expected_shift)), 'Placebo hash differs')
    for row in labeled.itertuples(index=False):
        if pd.isna(row.entry_ask):
            require(pd.isna(row.net) and pd.isna(row.adverse_net), 'Missing entry has payoff')
            continue
        close(net_dollars(row.entry_ask, row.exit_bid), row.net, 'Base accounting differs ' + row.event_id)
        close(net_dollars(row.entry_ask, row.exit_bid, True), row.adverse_net, 'Adverse accounting differs ' + row.event_id)
        require(not row.missing_exit or row.exit_bid == 0, 'Missing exit has proceeds')
    require(int(labels.entry_ask.isna().sum()) == coverage.get('missing_entry', 0), 'Missing-entry coverage differs')
    require(int(labels.missing_exit.sum()) == coverage.get('missing_exit_zero_liquidation', 0), 'Missing-exit coverage differs')

    matrix = labeled.merge(features, on=['event_id', 'date', 'ticker_name', 'decision'], validate='many_to_one')
    refits = []
    for arm in ARMS:
        cols = freeze['representations'][arm]['features']
        require(all(c.startswith('p_') or c.startswith({'authentic': 'a_', 'placebo': 'z_', 'price': 'p_'}[arm]) for c in cols), 'Unexpected feature family')
        for side in ('CALL', 'PUT'):
            train = matrix.loc[(matrix.date < '20230701') & (matrix.right == side) & matrix.net.notna()]
            all_side = matrix.loc[matrix.right == side]
            saved = lgb.Booster(model_file=str(root / f'model_{arm}_{side}.txt'))
            saved_prediction = saved.predict(all_side[cols].to_numpy(float))
            actual = predictions.loc[(predictions.representation == arm) & (predictions.right == side)]
            aligned = all_side[['event_id', 'right']].merge(actual[['event_id', 'right', 'prediction']], on=['event_id', 'right'], validate='one_to_one')
            require(np.array_equal(saved_prediction, aligned.prediction.to_numpy(float)), 'Saved-model prediction mismatch ' + arm + side)
            model = lgb.LGBMRegressor(**freeze['config'])
            model.fit(train[cols].to_numpy(float), train.net)
            independent = model.predict(all_side[cols].to_numpy(float))
            require(np.array_equal(independent, saved_prediction), 'Independent refit mismatch ' + arm + side)
            refits.append({'arm': arm, 'side': side, 'train_rows': len(train), 'prediction_rows': len(all_side), 'exact': True})
            print(json.dumps({'audit_stage': 'independent_refit', 'arm': arm, 'side': side, 'exact': True}), flush=True)

    joined = predictions.merge(labels, on=['event_id', 'right'], validate='many_to_one')
    all_ledger = []
    for arm in ARMS:
        arm_rows = joined.loc[joined.representation == arm]
        validation = arm_rows.loc[arm_rows.date.between('20230701', '20230930')]
        choices = []
        for threshold in (0, 5, 10):
            ledger = independent_schedule(validation, threshold)
            count = ledger.groupby('ticker_name').size().to_dict()
            choices.append({'threshold': threshold, 'net': float(ledger.net.sum()), 'counts': count,
                            'qualifies': all(count.get(t, 0) >= 10 for t in TICKERS)})
        expected_choices = freeze['representations'][arm]['validation_choices']
        for actual, expected in zip(choices, expected_choices, strict=True):
            require(actual['counts'] == expected['counts'] and actual['qualifies'] == expected['qualifies']
                    and actual['threshold'] == expected['threshold'], 'Validation choice differs ' + arm)
            close(actual['net'], expected['net'], 'Validation net differs ' + arm)
        qualifying = [v for v in choices if v['qualifies']]
        threshold = min(qualifying, key=lambda v: (-v['net'], v['threshold']))['threshold'] if qualifying else None
        require(threshold == freeze['representations'][arm]['threshold'], 'Chosen threshold differs ' + arm)
        for period, start, stop in [('validation', '20230701', '20230930'), ('test', '20231001', '20231231')]:
            rows = arm_rows.loc[arm_rows.date.between(start, stop)]
            ledger = independent_schedule(rows, threshold)
            ledger['period'] = period
            all_ledger.append(ledger)
            reported = summary['results'][arm][period]
            compare_metrics(comparable_metrics(ledger), reported['pooled'], arm + period)
            for ticker in TICKERS:
                ticker_ledger = ledger.loc[ledger.ticker_name == ticker]
                compare_metrics(comparable_metrics(ticker_ledger), reported['tickers'][ticker], arm + period + ticker)
                for month, reported_metrics in reported['months'][ticker].items():
                    compare_metrics(comparable_metrics(ticker_ledger.loc[ticker_ledger.date.str.startswith(month)]), reported_metrics, arm + ticker + month)
    rebuilt = pd.concat(all_ledger, ignore_index=True)
    reported_ledger = pd.read_parquet(root / 'ledger.parquet')
    keys = ['representation', 'period', 'event_id', 'right']
    require(not rebuilt.duplicated(keys).any() and not reported_ledger.duplicated(keys).any(), 'Ledger duplicates')
    left = rebuilt.sort_values(keys).reset_index(drop=True)
    right = reported_ledger.sort_values(keys).reset_index(drop=True)
    require(len(left) == len(right), 'Ledger size differs')
    for col in left.columns:
        if pd.api.types.is_numeric_dtype(left[col]):
            require(np.allclose(left[col].to_numpy(float), right[col].to_numpy(float), atol=1e-7, rtol=0, equal_nan=True), 'Ledger column differs: ' + col)
        else:
            require(left[col].fillna('<NA>').equals(right[col].fillna('<NA>')), 'Ledger column differs: ' + col)

    test = rebuilt.loc[rebuilt.period == 'test']
    unique = test.drop_duplicates(['event_id', 'right'])
    raw_checked = 0
    for (ticker, date), subset in unique.groupby(['ticker_name', 'date']):
        expected_suffix = f'{ticker}_{date}_{date}_greeks.parquet'
        paths = [p for p in sources if Path(p).name == expected_suffix]
        require(len(paths) == 1, 'Raw source mapping ambiguous')
        frame = raw_quotes(paths[0], ticker, date)
        indexed = frame.set_index(['strike', 'right', 'timestamp'])
        for row in subset.itertuples(index=False):
            feat = frame.loc[(frame.timestamp == pd.Timestamp(row.feature_time)) & (frame.right == row.right)
                             & np.isfinite(frame.delta) & (frame.delta.abs() <= 1)].copy()
            require(len(feat) > 0, 'Raw feature contract absent')
            feat['distance'] = (feat.delta.abs() - .5).abs()
            chosen = feat.sort_values(['distance', 'strike'], kind='stable').iloc[0]
            close(chosen.strike, row.strike, 'Raw feature-time contract selection differs')
            close(chosen.delta, row.selected_delta, 'Raw selected delta differs')
            entry = indexed.loc[(row.strike, row.right, pd.Timestamp(row.entry_time))]
            close(entry.ask, row.entry_ask, 'Raw entry ask differs')
            exit_key = (row.strike, row.right, pd.Timestamp(row.exit_time))
            if exit_key not in indexed.index:
                require(row.missing_exit and row.exit_bid == 0, 'Raw missing exit differs')
            else:
                require(not row.missing_exit, 'Raw exit exists but flagged missing')
                close(indexed.loc[exit_key].bid, row.exit_bid, 'Raw exit bid differs')
            raw_checked += 1

    days = [d.strftime('%Y%m%d') for d in pd.bdate_range('2023-10-02', '2023-12-29')
            if d.strftime('%Y%m%d') not in ('20231123', '20231124', '20231225')]
    daily = test.groupby(['date', 'representation']).net.sum().unstack(fill_value=0).reindex(index=days, columns=ARMS, fill_value=0).fillna(0)
    saved_daily = pd.read_csv(root / 'test_daily_net.csv', dtype={'date': str}).set_index('date')
    require(saved_daily.index.tolist() == days, 'Daily calendar differs')
    require(np.allclose(saved_daily[list(ARMS)], daily, rtol=0, atol=1e-7), 'Daily net differs')
    rng = np.random.default_rng(20261018)
    begins = rng.integers(0, len(days), size=(2000, (len(days) + 4) // 5))
    picks = ((begins[:, :, None] + np.arange(5)) % len(days)).reshape(2000, -1)[:, :len(days)]
    for control in ('price', 'placebo'):
        difference = (daily.authentic - daily[control]).to_numpy(float)
        samples = difference[picks].sum(axis=1)
        expected = summary['paired_test_comparisons']['authentic_minus_' + control]
        close(difference.sum(), expected['observed_net_difference'], 'Paired difference differs')
        interval = np.quantile(samples, [.025, .975])
        require(np.allclose(interval, expected['paired_circular_5session_block_bootstrap_95ci_total_usd'], rtol=0, atol=1e-7), 'Bootstrap differs')

    rebuilt.to_parquet(output / 'independent_ledger.parquet', index=False)
    (output / 'source_rehash.json').write_text(json.dumps(source_results, indent=2), encoding='utf-8')
    result = {'status': 'PASS_INDEPENDENT_EXPLORATORY_BENCHMARK_AUDIT', 'source_files_rehashed': len(source_results),
              'source_hash_mismatch': 0, 'accounting_rows': len(labeled), 'ledger_rows': len(rebuilt),
              'unique_selected_test_contracts_raw_checked': raw_checked, 'model_refits': refits,
              'calendar_days': len(days), 'bootstrap_comparisons_rebuilt': 2,
              'summary_sha256': digest(root / 'summary.json'), 'audit_script_sha256': digest(__file__),
              'untouched_outer': False, 'live_parity_verified': False, 'original_receipt_times_verified': False,
              'full_raw_feature_reconstruction': False, 'audit_finished_utc': datetime.now(timezone.utc).isoformat()}
    (output / 'audit.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(result), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    try:
        audit(args.root, args.output)
    except Exception as exc:
        (args.output / 'audit_failure.json').write_text(json.dumps({'status': 'AUDIT_FAILED', 'error': repr(exc)}, indent=2), encoding='utf-8')
        raise


if __name__ == '__main__':
    main()
