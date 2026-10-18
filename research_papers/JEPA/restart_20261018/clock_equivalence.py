"""Empirical comparison of stored quote and underlying clocks, no model/outcomes."""
from pathlib import Path
import hashlib
import json

import pandas as pd
import pyarrow.parquet as pq

ROOT = Path('D:/ThetaData/data_options')
OUT = Path('D:/GexResearchArtifacts/restart_20261018/clock_equivalence')


def path_for(ticker, day):
    return ROOT / ticker / 'greeks' / day[:4] / day[4:6] / f'{ticker}_{day}_{day}_greeks.parquet'


def parse_clock(series):
    if pd.api.types.is_datetime64_any_dtype(series.dtype):
        return pd.to_datetime(series)
    return pd.to_datetime(series, format='ISO8601')


def probe(path, selection):
    pf = pq.ParquetFile(path)
    cols = ['symbol', 'expiration', 'trade_date', 'strike', 'right', 'interval_used', 'underlying_timestamp']
    paired = 'timestamp' in pf.schema_arrow.names
    if paired:
        cols.append('timestamp')
    df = pf.read(columns=cols).to_pandas()
    uts = parse_clock(df.underlying_timestamp)
    df['_uts'] = uts
    counts = df.groupby(['strike', 'right']).size()
    per_minute = df.groupby(uts.dt.floor('min')).size()
    row = {'path': str(path), 'selection': selection, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
           'rows': len(df), 'clock_type': str(pf.schema_arrow.field('underlying_timestamp').type),
           'has_native_quote_timestamp': paired, 'intervals': sorted(df.interval_used.unique().tolist()),
           'underlying_min': str(uts.min()), 'underlying_max': str(uts.max()),
           'null_underlying': int(uts.isna().sum()), 'unique_underlying_clocks': int(uts.nunique()),
           'unique_underlying_minute_bins': len(per_minute), 'contracts': len(counts),
           'contract_rows_min': int(counts.min()), 'contract_rows_max': int(counts.max()),
           'duplicate_contract_underlying_clock': int(df.duplicated(['strike', 'right', '_uts']).sum()),
           'underlying_nonminute_rows': int((uts != uts.dt.floor('min')).sum()),
           'rows_outside_trade_date': int((uts.dt.strftime('%Y-%m-%d') != df.trade_date.astype(str)).sum()),
           'multiple_underlying_clocks_per_minute_bins': int((df.groupby(uts.dt.floor('min'))._uts.nunique() > 1).sum()),
           'per_minute_rows_min': int(per_minute.min()), 'per_minute_rows_max': int(per_minute.max())}
    if paired:
        ts = parse_clock(df.timestamp)
        age_ms = (ts - uts).dt.total_seconds() * 1000
        row.update({'native_min': str(ts.min()), 'native_max': str(ts.max()),
                    'null_native': int(ts.isna().sum()), 'exact_match_rows': int((ts == uts).sum()),
                    'exact_match_fraction': float((ts == uts).mean()),
                    'age_ms_min': float(age_ms.min()), 'age_ms_median': float(age_ms.median()),
                    'age_ms_p95': float(age_ms.quantile(.95)), 'age_ms_p99': float(age_ms.quantile(.99)),
                    'age_ms_max': float(age_ms.max()), 'negative_age_rows': int((age_ms < 0).sum()),
                    'age_gt_1min_rows': int((age_ms > 60000).sum()),
                    'quote_at_or_before_underlying_plus_1min_rows': int((ts <= uts + pd.Timedelta(minutes=1)).sum()),
                    'duplicate_contract_native_clock': int(df.duplicated(['strike', 'right', 'timestamp']).sum()),
                    'native_clocks_with_multiple_underlying_clocks': int((df.groupby('timestamp')._uts.nunique() > 1).sum())})
        for minutes in [1, 5, 15]:
            for op in ['floor', 'ceil']:
                bins_ts = getattr(ts.dt, op)(f'{minutes}min')
                bins_uts = getattr(uts.dt, op)(f'{minutes}min')
                row[f'{op}_{minutes}min_match_fraction'] = float((bins_ts == bins_uts).mean())
    return row


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    selected = {}
    for ticker in ['SPXW', 'SPY', 'QQQ']:
        for day in ['20230103', '20230601', '20231201']:
            selected[path_for(ticker, day)] = 'paired_2023_fixed_calendar_days'
        for year in ['2024', '2025', '2026']:
            paths = sorted((ROOT / ticker / 'greeks' / year).glob('*/*.parquet'))
            paths = [p for p in paths if p.stem.split('_')[1] == p.stem.split('_')[2]]
            if paths:
                selected[paths[0]] = f'{year}_first_0dte_filename'
                selected[paths[-1]] = f'{year}_last_0dte_filename'
    for ticker, day in [('QQQ', '20250102'), ('SPXW', '20260701')]:
        selected[path_for(ticker, day)] = 'known_paired_later_year_comparator'
    results = []
    for path, selection in selected.items():
        result = probe(path, selection)
        results.append(result)
        print(json.dumps(result), flush=True)
    data = {'purpose': 'empirical clock comparison; clock convention candidate, not proof of live receipt',
            'network_requests': 0, 'outcomes_read': False, 'sources': results}
    (OUT / 'comparison.json').write_text(json.dumps(data, indent=2), encoding='utf-8')
    oi_schemas = []
    for path in selected:
        if path.parent.parent.name == '2023':
            continue
        oi_path = Path(str(path).replace('\\greeks\\', '\\oi\\').replace('_greeks.parquet', '_oi.parquet'))
        if oi_path.exists():
            pf = pq.ParquetFile(oi_path)
            oi_schemas.append({'path': str(oi_path), 'columns': pf.schema_arrow.names,
                               'schema': str(pf.schema_arrow), 'rows': pf.metadata.num_rows})
    (OUT / 'oi_schemas.json').write_text(json.dumps(oi_schemas, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
