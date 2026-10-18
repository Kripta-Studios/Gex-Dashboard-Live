"""Single-worker IB audit using selected spot, state and feature arrays only."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

STATE_COLUMNS = ('state_i', 'ib_low', 'ib_high', 'ib_range', 'ib_observed')
BASE_COLUMNS = ('spot_ib', 'ib_range_over_spot', 'ib_valid', 'ib_valid_fraction')


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def read_json(path):
    raw = path.read_bytes()
    return json.loads(raw), sha_bytes(raw)


def array_digest(arrays):
    digest = hashlib.sha256()
    for name, value in arrays.items():
        value = np.asarray(value)
        descriptor = json.dumps([name, str(value.dtype), list(value.shape)], separators=(',', ':')).encode()
        digest.update(len(descriptor).to_bytes(8, 'little'))
        digest.update(descriptor)
        digest.update(value.tobytes(order='C'))
    return digest.hexdigest()


def check_day(root, ticker, date):
    source = root / 'cache_v1' / ticker / f'{date}.npz'
    engine = root / 'engine_v1' / ticker / date
    feature = root / 'features_v1' / ticker / date
    source_meta, source_meta_hash = read_json(source.with_suffix('.json'))
    feature_meta, feature_meta_hash = read_json(feature / 'features.json')
    freeze, freeze_hash = read_json(engine / 'causal_freeze.json')
    with np.load(source, allow_pickle=False) as stored:
        raw = {name: stored[name] for name in ('time_ns', 'spot', 'spot_valid')}
    with np.load(feature / 'features.npz', allow_pickle=False) as stored:
        arrays = {name: stored[name] for name in ('state_i', 'bar_end_i', 'base')}
    table = pq.read_table(engine / 'states.parquet', columns=list(STATE_COLUMNS))
    states = {name: table[name].to_numpy() for name in STATE_COLUMNS}
    begin = np.datetime64(f'{date[:4]}-{date[4:6]}-{date[6:]}T09:30', 'ns').astype(np.int64)
    assert np.array_equal(raw['time_ns'], begin + np.arange(391) * 60_000_000_000), 'session_clock'
    observed = raw['spot_valid'] & np.isfinite(raw['spot']) & (raw['spot'] > 0)
    first_hour = raw['spot'][:60][observed[:60]]
    count = len(first_hour)
    low, high = (float(first_hour.min()), float(first_hour.max())) if count else (np.nan, np.nan)
    ib_valid = count >= 57 and high > low
    width = high - low
    minutes = np.arange(60, 376)
    assert np.array_equal(states['state_i'], minutes), 'engine_decision_indices'
    assert np.array_equal(arrays['state_i'], minutes), 'feature_decision_indices'
    for name, value in (('ib_low', low), ('ib_high', high), ('ib_range', width)):
        expected = value if ib_valid else np.nan
        assert np.array_equal(states[name], np.full(len(minutes), expected), equal_nan=True), name
    assert np.all(states['ib_observed'] == (count if ib_valid else 0)), 'ib_observed'
    expected_ends = []
    for minute in minutes:
        ends = []
        for duration, lookback in ((5, 12), (15, 8)):
            ends.extend((index + 1) * duration - 1 if index >= 0 else -1
                        for index in range(minute // duration - lookback, minute // duration))
        expected_ends.append(ends)
    assert np.array_equal(arrays['bar_end_i'], expected_ends), 'bar_end_anchor'
    assert np.all(arrays['bar_end_i'] < minutes[:, None]), 'bar_closed_before_decision'
    names = feature_meta['schema']['base_names']
    assert arrays['base'].shape == (len(minutes), len(names)), 'base_shape'
    current = np.where(observed[minutes], raw['spot'][minutes], np.nan)
    expected_base = dict(spot_ib=(current - low) / width if ib_valid else np.zeros(len(minutes)),
                         ib_range_over_spot=width / current if ib_valid else np.zeros(len(minutes)),
                         ib_valid=np.full(len(minutes), float(ib_valid)),
                         ib_valid_fraction=np.full(len(minutes), count / 60))
    inspected_base = {}
    for name in BASE_COLUMNS:
        expected = np.nan_to_num(expected_base[name], nan=0., posinf=0., neginf=0.).astype(np.float32)
        actual = arrays['base'][:, names.index(name)]
        assert np.array_equal(actual, expected), 'base:' + name
        inspected_base[name] = actual
    assert feature_meta['binding']['source_sha256'] == source_meta['sha256'], 'source_binding'
    assert feature_meta['binding']['source_metadata_sha256'] == source_meta_hash, 'source_metadata_binding'
    return dict(ticker=ticker, date=date, status='PASS', states=len(minutes), ib_observed=count,
                ib_valid=bool(ib_valid), raw_cache_sha256_reported=source_meta['sha256'],
                states_parquet_sha256_reported=freeze['states.parquet'],
                features_npz_sha256_reported=feature_meta['sha256'],
                source_metadata_sha256_actual=source_meta_hash, feature_metadata_sha256_actual=feature_meta_hash,
                causal_freeze_sha256_actual=freeze_hash, selected_raw_arrays_sha256_actual=array_digest(raw),
                selected_state_columns_sha256_actual=array_digest(states),
                selected_feature_arrays_sha256_actual=array_digest(dict(state_i=arrays['state_i'], bar_end_i=arrays['bar_end_i'], **inspected_base)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('D:/GexResearchArtifacts/level_oracle_20261018'))
    parser.add_argument('--out', type=Path)
    parser.add_argument('--expected-days', type=int, default=2595)
    args = parser.parse_args()
    out = args.out or args.root / 'ib_feature_audit_v1'
    out.mkdir(parents=True, exist_ok=False)
    records, errors = [], []
    source = Path(__file__).read_bytes()
    (out / 'audit_ib_feature_exports.executed.py').write_bytes(source)
    for ticker in ('QQQ', 'SPXW', 'SPY'):
        for path in sorted((args.root / 'cache_v1' / ticker).glob('*.npz')):
            try:
                records.append(check_day(args.root, ticker, path.stem))
            except Exception as error:
                item = dict(ticker=ticker, date=path.stem, status='FAIL', error=f'{type(error).__name__}: {error}')
                errors.append(item)
                print(json.dumps(item), flush=True)
            if (len(records) + len(errors)) % 100 == 0:
                print(json.dumps(dict(checked=len(records) + len(errors), passed=len(records), failed=len(errors))), flush=True)
    if len(records) + len(errors) != args.expected_days:
        errors.append(dict(status='FAIL', error='Complete-cache day count differs from expected contract'))
    index_path = out / 'days.csv'
    with index_path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    summary = dict(status='PASS_IB_FEATURE_EXPORT_INVARIANTS' if not errors else 'FAIL_IB_FEATURE_EXPORT_INVARIANTS',
                   checked_days=len(records) + len([item for item in errors if 'ticker' in item]),
                   passed_days=len(records), failed=errors, states=sum(row['states'] for row in records),
                   by_ticker={ticker: sum(row['ticker'] == ticker for row in records) for ticker in ('QQQ', 'SPXW', 'SPY')},
                   ib_observed_min=min(row['ib_observed'] for row in records), ib_observed_max=max(row['ib_observed'] for row in records),
                   invalid_ib_days=sum(not row['ib_valid'] for row in records), base_columns_checked=list(BASE_COLUMNS),
                   workers=1, quotes_read=False, outcomes_read=False, full_npz_or_parquet_rehashed=False,
                   full_feature_recomputation=False, code_sha256=sha_bytes(source), days_csv_sha256=sha_bytes(index_path.read_bytes()),
                   completed_utc=datetime.now(timezone.utc).isoformat())
    (out / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary), flush=True)
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
