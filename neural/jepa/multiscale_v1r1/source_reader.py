"""DATA-002: restricted feature reader; has no payoff access capability."""
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .artifacts import append_access, digest
from .contract import ContractError

ALLOWED = {
    'underlying': frozenset(('timestamp', 'open', 'high', 'low', 'close', 'tick_count')),
    'greeks': frozenset(('timestamp', 'symbol', 'expiration', 'trade_date', 'right',
                         'strike', 'implied_vol', 'bid', 'ask', 'delta')),
    'oi': frozenset(('timestamp', 'symbol', 'expiration', 'trade_date', 'right', 'strike', 'open_interest')),
}


class FeatureReader:
    def __init__(self, manifest, root, access_log):
        self.root = Path(root).resolve()
        self.rows = {r['source_id']: r for r in manifest}
        self.access_log = Path(access_log)

    def read(self, source_id, columns, start, end, purpose):
        row = self.rows[source_id]
        path = Path(row['absolute_path']).resolve()
        kind = row['source_kind']
        allowed_root = (self.root / 'data_underlying_derived' / row['ticker'] if kind == 'underlying'
                        else self.root / 'data_options' / row['ticker'] / kind)
        if kind not in ALLOWED or not path.is_relative_to(allowed_root):
            raise ContractError('DATA-001: forbidden source')
        if not columns or not set(columns) <= ALLOWED[kind] or 'timestamp' not in columns:
            raise ContractError('DATA-002: forbidden columns')
        lower, upper = pd.Timestamp(start), pd.Timestamp(end)
        if lower.tzinfo is None or upper.tzinfo is None or lower >= upper:
            raise ContractError('DATA-002: explicit timezone-aware interval required')
        if purpose not in ('feature_bar_prefix', 'feature_wall_snapshot', 'prior_close_oi'):
            raise ContractError('DATA-002: purpose not allowed')
        if upper.tz_convert('America/New_York').date().isoformat() != row['trade_date']:
            raise ContractError('DATA-002: session mismatch')
        if row['trade_date'] > '2026-06-30' or row['trade_date'] < '2022-08-01':
            raise ContractError('DATA-002: outside experiment')
        if digest(path) != row['sha256']:
            raise ContractError('IO-001: source hash changed')
        arrow_type = pq.read_schema(path).field('timestamp').type
        local_start = lower.tz_convert('America/New_York').tz_localize(None)
        local_end = upper.tz_convert('America/New_York').tz_localize(None)
        if pa.types.is_timestamp(arrow_type):
            a, b = (lower, upper) if arrow_type.tz else (local_start, local_end)
            bounds = [pa.scalar(a, type=arrow_type), pa.scalar(b, type=arrow_type)]
        elif pa.types.is_string(arrow_type) or pa.types.is_large_string(arrow_type):
            # Only the documented ISO native format is admitted; parse/validate returned rows.
            bounds = [str(local_start), str(local_end)]
        else:
            raise ContractError('DATA-002: unsupported native timestamp storage')
        append_access(self.access_log, stage='data_gate', purpose=purpose, source_id=source_id,
                      columns=list(columns), time_range=[lower.isoformat(), upper.isoformat()],
                      upper_exclusive=True)
        table = pq.read_table(path, columns=list(columns),
                              filters=[('timestamp', '>=', bounds[0]), ('timestamp', '<', bounds[1])])
        frame = table.to_pandas()
        actual = pd.to_datetime(frame.timestamp, errors='raise')
        if actual.dt.tz is None:
            actual = actual.dt.tz_localize('America/New_York', ambiguous='raise', nonexistent='raise')
        if not ((actual >= lower) & (actual < upper)).all():
            raise ContractError('DATA-002: timestamp filter mismatch')
        frame['timestamp'] = actual
        return frame
