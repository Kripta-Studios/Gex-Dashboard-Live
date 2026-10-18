"""Verify completed feature exports by causal manifests and artifact hashes only."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

try:
    from . import features as f
except ImportError:
    import features as f


def digest(path):
    hasher = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('D:/GexResearchArtifacts/level_oracle_20261018'))
    args = parser.parse_args()
    source_root, engine_root, output = (args.root / name for name in ('cache_v1', 'engine_v1', 'features_v1'))
    if not (source_root / 'full_summary.json').exists() or not (engine_root / 'completion.json').exists():
        raise ValueError('Source and engine completion markers required')
    if read(output / 'progress.json')['status'] != 'COMPLETE_AVAILABLE':
        raise ValueError('State writer has not completed')
    if read(output / 'action_progress.json')['status'] != 'COMPLETE_AVAILABLE':
        raise ValueError('Action writer has not completed')
    dependencies, schema = f._dependencies(), f.feature_schema()
    action_contract = read(output / 'action_feature_contract.json')
    rows, expected = [], set()
    for ticker in ('QQQ', 'SPXW', 'SPY'):
        for source in sorted((source_root / ticker).glob('*.npz')):
            date = source.stem
            expected.add((ticker, date))
            source_meta = read(source.with_suffix('.json'))
            day = output / ticker / date
            state, action, provenance = (read(day / name) for name in ('features.json', 'actions.json', 'actions.provenance.json'))
            source_binding = dict(source_sha256=source_meta['sha256'], source_metadata_sha256=digest(source.with_suffix('.json')), dependencies=dependencies)
            if state['binding'] != source_binding or state['schema'] != schema:
                raise ValueError(f'State binding/schema differs: {ticker}/{date}')
            if any(action['binding'][key] != value for key, value in source_binding.items()):
                raise ValueError(f'Action binding differs: {ticker}/{date}')
            if action['action_names'] != schema['action_names']:
                raise ValueError(f'Action schema differs: {ticker}/{date}')
            freeze_path = engine_root / ticker / date / 'causal_freeze.json'
            freeze = read(freeze_path)
            if provenance['actions_sha256'] != freeze['actions.parquet'] or provenance['raw_cache_sha256'] != source_meta['sha256']:
                raise ValueError(f'Causal action provenance differs: {ticker}/{date}')
            if provenance['causal_freeze_sha256'] != digest(freeze_path) or provenance['producer_sha256'] != action_contract['producer_sha256']:
                raise ValueError(f'Causal freeze/producer provenance differs: {ticker}/{date}')
            for stem, metadata in (('features', state), ('actions', action)):
                if digest(day / f'{stem}.npz') != metadata['sha256']:
                    raise ValueError(f'Artifact hash differs: {ticker}/{date}/{stem}')
            rows.append(dict(ticker=ticker, date=date, states=state['states'], valid_states=state['valid_states'], actions=action['actions'],
                             state_bytes=(day / 'features.npz').stat().st_size, action_bytes=(day / 'actions.npz').stat().st_size,
                             source_sha256=source_meta['sha256'], state_sha256=state['sha256'], action_sha256=action['sha256'],
                             causal_actions_sha256=provenance['actions_sha256']))
    for stem in ('features', 'actions'):
        actual = {(ticker, path.parent.name) for ticker in ('QQQ', 'SPXW', 'SPY') for path in (output / ticker).glob(f'*/{stem}.npz')}
        if actual != expected:
            raise ValueError(f'{stem} coverage differs from complete raw caches')
    index_path = output / 'coverage_final.csv'
    with index_path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = dict(status='PASS_FEATURE_COVERAGE_AND_ARTIFACT_HASHES', days=len(rows),
                   by_ticker={ticker: sum(row['ticker'] == ticker for row in rows) for ticker in ('QQQ', 'SPXW', 'SPY')},
                   **{key: sum(row[key] for row in rows) for key in ('states', 'valid_states', 'actions', 'state_bytes', 'action_bytes')},
                   dependencies=dependencies, index_sha256=digest(index_path), verifier_sha256=digest(Path(__file__)),
                   outcomes_read=False, raw_cache_bytes_rehashed=False, independent_feature_recomputation=False,
                   completed_utc=datetime.now(timezone.utc).isoformat())
    f.build_cache.write_json(output / 'coverage_final.json', summary)
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
