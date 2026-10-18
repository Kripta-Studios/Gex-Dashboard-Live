"""Names/schema-only search for six absent SPY/QQQ April-2026 Greek sources."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time

import pyarrow.parquet as pq

ROOT = Path('D:/ThetaData')
INVENTORY = Path('D:/GexResearchArtifacts/restart_20261018/inventory/files.csv')
OUTPUT = Path('D:/GexResearchArtifacts/level_oracle_20261018/daily_trade_feasibility_v1/source_candidates.json')
DATES = ('20260401', '20260409', '20260415')
TICKERS = ('QQQ', 'SPY')


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for part in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(part)
    return digest.hexdigest()


def relevant(path):
    if not re.search(r'(?<![A-Za-z])(QQQ|SPY)(?![A-Za-z])', path, flags=re.IGNORECASE):
        return False
    return any(token in path for date in DATES for token in
               (date, f'{date[:4]}-{date[4:6]}-{date[6:]}', f'{date[:4]}/{date[4:6]}/{date[6:]}',
                f'{date[:4]}_{date[4:6]}_{date[6:]}'))


def valid_dates(path):
    result = []
    for token in re.findall(r'(?<![A-Za-z0-9])(20\d{6})(?![A-Za-z0-9])', path):
        try:
            datetime.strptime(token, '%Y%m%d')
        except ValueError:
            continue
        result.append(token)
    return result


def main():
    started = time.perf_counter()
    catalog_matches, other_families, undated = [], {}, []
    with INVENTORY.open(encoding='utf-8-sig', newline='') as handle:
        for row in csv.DictReader(handle):
            path = row['path']
            if relevant(path):
                catalog_matches.append(path)
            if row['suffix'] == '.parquet' and row['family'] not in ('data_options', 'data_underlying_derived'):
                group = other_families.setdefault(row['family'], dict(parquets=0, min_filename_date=None, max_filename_date=None, sample=path))
                group['parquets'] += 1
                dates = valid_dates(path)
                if dates:
                    group['min_filename_date'] = min(filter(None, [group['min_filename_date'], min(dates)]))
                    group['max_filename_date'] = max(filter(None, [group['max_filename_date'], max(dates)]))
            if re.search(r'(?<![A-Za-z])(QQQ|SPY)(?![A-Za-z])', path, re.IGNORECASE) and not valid_dates(path):
                if row['suffix'] in ('.parquet', '.csv', '.npz', '.bin', '.zip', '.7z'):
                    undated.append(dict(path=path, bytes=int(row['bytes']), suffix=row['suffix']))
    matching, errors, visited = [], [], 0
    for directory, _, names in os.walk(ROOT, followlinks=False, onerror=lambda error: errors.append(str(error))):
        for name in names:
            visited += 1
            path = Path(directory) / name
            relative = path.relative_to(ROOT).as_posix()
            if relevant(relative):
                matching.append(relative)
    schemas = []
    for relative in sorted(matching):
        path = ROOT / relative
        item = dict(path=relative, bytes=path.stat().st_size, mtime_ns=path.stat().st_mtime_ns)
        if path.suffix == '.parquet':
            footer = pq.ParquetFile(path)
            fields = [(field.name, str(field.type)) for field in footer.schema_arrow]
            item.update(rows=footer.metadata.num_rows, fields=fields,
                        schema_sha256=hashlib.sha256(json.dumps(fields).encode()).hexdigest())
        schemas.append(item)
    expected = []
    for ticker in TICKERS:
        for date in DATES:
            paths = {kind: ROOT / 'data_options' / ticker / kind / date[:4] / date[4:6] / f'{ticker}_{date}_{date}_{kind}.parquet'
                     for kind in ('greeks', 'iv', 'ohlc', 'oi')}
            spot = ROOT / 'data_underlying_derived' / ticker / date[:4] / date[4:6] / f'{ticker}_{date}.parquet'
            expected.append(dict(ticker=ticker, date=date, canonical_exists={kind: path.exists() for kind, path in paths.items()},
                                 canonical_paths={kind: str(path) for kind, path in paths.items()}, derived_spot_exists=spot.exists(),
                                 status='NO_EVALUABLE_MISSING_SOURCE'))
    summary = dict(status='NAMES_AND_SCHEMA_SEARCH_COMPLETE', root=str(ROOT), files_named_in_fresh_walk=visited,
                   traversal_errors=errors, target_dates=list(DATES), target_tickers=list(TICKERS),
                   census_matches=sorted(catalog_matches), current_matches=sorted(matching),
                   current_matches_equal_census=set(matching) == set(catalog_matches), matches_with_schemas=schemas,
                   canonical_presence=expected, other_parquet_families=other_families,
                   undated_symbol_data_like_names=undated, inventory_sha256=sha(INVENTORY), code_sha256=sha(Path(__file__)),
                   source_values_read=False, full_source_bytes_hashed=False, network_used=False,
                   admitted_new_source=False, cache_modified=False, wall_seconds=time.perf_counter() - started,
                   completed_utc=datetime.now(timezone.utc).isoformat())
    OUTPUT.write_text(json.dumps(summary, indent=2), encoding='utf-8')
    OUTPUT.with_name('check_missing_source_candidates.executed.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(files=visited, matches=len(matching), errors=errors,
                         current_matches_equal_census=summary['current_matches_equal_census'],
                         canonical_presence=expected, other_parquet_families=other_families,
                         wall_seconds=summary['wall_seconds'])), flush=True)


if __name__ == '__main__':
    main()
