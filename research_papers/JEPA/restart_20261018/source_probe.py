"""Read-only representative local source feasibility probe; no network or fits."""
from pathlib import Path
import hashlib
import json

import pandas as pd
import pyarrow.parquet as pq

ROOT = Path('D:/ThetaData')
OUT = Path('D:/GexResearchArtifacts/restart_20261018/source_probe/iso8601_parser')


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    schemas = []
    values = []
    for ticker in ['SPXW', 'SPY', 'QQQ']:
        dates = {'20230103', '20240102', '20250102', '20260701'}
        for month in range(1, 13):
            paths = sorted((ROOT / 'data_options' / ticker / 'greeks' / '2023' / f'{month:02d}').glob('*.parquet'))
            paths = [p for p in paths if p.stem.split('_')[1] == p.stem.split('_')[2]]
            if paths:
                dates.add(paths[0].stem.split('_')[1])
                dates.add(paths[-1].stem.split('_')[1])
        for date in sorted(dates):
            for kind in ['greeks', 'oi']:
                p = ROOT / 'data_options' / ticker / kind / date[:4] / date[4:6] / f'{ticker}_{date}_{date}_{kind}.parquet'
                if not p.exists():
                    schemas.append({'path': str(p), 'exists': False})
                    continue
                pf = pq.ParquetFile(p)
                md = pf.metadata.metadata or {}
                schemas.append({'path': str(p), 'exists': True, 'rows': pf.metadata.num_rows,
                                'schema': str(pf.schema_arrow), 'columns': pf.schema_arrow.names,
                                'pandas_index_columns': json.loads(md.get(b'pandas', b'{}')).get('index_columns')})
                if date not in ['20230103', '20230601', '20231201']:
                    continue
                cols = (['timestamp', 'underlying_timestamp', 'strike', 'right', 'underlying_price',
                         'bid', 'ask', 'delta', 'implied_vol', 'interval_used'] if kind == 'greeks'
                        else ['timestamp', 'strike', 'right', 'open_interest', 'interval_used'])
                df = pf.read(columns=cols).to_pandas()
                ts = pd.to_datetime(df.timestamp, format='ISO8601')
                item = {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                        'rows': len(df), 'intervals': sorted(df.interval_used.unique().tolist()),
                        'timestamp_min': str(ts.min()), 'timestamp_max': str(ts.max()),
                        'timestamps': int(ts.nunique()), 'null_timestamp': int(ts.isna().sum()),
                        'duplicate_contract_timestamp': int(df.duplicated(['timestamp', 'strike', 'right']).sum())}
                if kind == 'greeks':
                    uts = pd.to_datetime(df.underlying_timestamp, format='ISO8601')
                    regular = (ts.dt.time >= pd.Timestamp('09:30').time()) & (ts.dt.time < pd.Timestamp('16:00').time())
                    g = df.loc[regular].groupby('timestamp')
                    item.update({'underlying_ahead_of_quote_rows': int((uts > ts).sum()),
                                 'nonpositive_spot_rows': int((df.underlying_price <= 0).sum()),
                                 'spot_disagreement_minutes': int((g.underlying_price.nunique() > 1).sum()),
                                 'spot_regular_minutes': int(g.ngroups),
                                 'valid_bidask_rows': int(((df.bid > 0) & (df.ask >= df.bid)).sum()),
                                 'null_delta_rows': int(df.delta.isna().sum()),
                                 'null_iv_rows': int(df.implied_vol.isna().sum()),
                                 'sample_rows': df.head(2).to_dict('records')})
                else:
                    after = ts.dt.time > pd.Timestamp('09:30').time()
                    item.update({'positive_oi': int((df.open_interest > 0).sum()),
                                 'zero_oi': int((df.open_interest == 0).sum()),
                                 'positive_oi_after_open': int(((df.open_interest > 0) & after).sum()),
                                 'rows_after_open': int(after.sum()), 'prior_close_semantics_verified': False})
                values.append(item)
    payload = {'purpose': 'representative feasibility, not exhaustive source admission',
               'network_requests': 0, 'fits': 0, 'schemas': schemas, 'value_probes': values}
    (OUT / 'probe.json').write_text(json.dumps(payload, indent=2, default=str), encoding='utf-8')
    print(json.dumps({'output': str(OUT / 'probe.json'), 'schema_records': len(schemas), 'value_probes': values}, default=str))


if __name__ == '__main__':
    main()
