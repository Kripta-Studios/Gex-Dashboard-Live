"""Offline closure of the interrupted 2022-08-01 IB source pilot.

This module has no capture or network path. It never writes to ``source_root``.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time
from urllib.parse import urlencode

from neural.jepa import audit_theta_ib_source_v1
from neural.jepa.multiscale_v1r1.artifacts import stage, write_json
from neural.jepa.multiscale_v1r1.provenance import coherent_read_handles


PILOT_HEAD = '60550cd1e783167a79134fcfb698e6ffd0d23f34'
DAY = '20220801'
BASE = 'http://91.99.90.39:25503/v3/option/history/greeks/first_order'
LIMIT = 512 * 1024**2
CODE_NAMES = (
    'theta_ib_source_v1.py',
    'audit_theta_ib_source_v1.py',
    '23_INITIAL_BALANCE_SOURCE_PILOT.md',
    'provenance.py',
)
FROZEN_CODE_SHA256 = {
    'theta_ib_source_v1.py': '2697ffe53271685ddf8650af0b0ed5148bbfd1eed031a64443481623be920313',
    'audit_theta_ib_source_v1.py': '38a3cce8abf01c54549cddb93372d8cfa500f91df6b311f8a043fc851d447a08',
    '23_INITIAL_BALANCE_SOURCE_PILOT.md': 'c1239c93172abee7ca2a32d4b642a75ea2e6328a625cb779313a2abb61831ec5',
    'provenance.py': '32f5afff8e8175e194181ac73a1ba3107dfe84423014bf7b1718161ffe6936c1',
}
SEALED = ('SPXW', 'SPY')


def require(condition, reason):
    if not condition:
        raise ValueError('IB_REVIEW: ' + reason)


def sha256(payload):
    return hashlib.sha256(payload).hexdigest()


def parameters(ticker):
    return dict(symbol=ticker, expiration=DAY, date=DAY, strike='*', right='both',
                interval='1s', start_time='09:30:00', end_time='10:30:00',
                version='1', format='csv')


def source_paths(root, specification):
    paths = [root / 'run_manifest.json']
    paths.extend(root / name for name in CODE_NAMES)
    for ticker in SEALED:
        paths.extend(root / ticker / name for name in (
            'manifest.json', 'response.bin', 'initial_balance.json'))
    paths.append(root / 'QQQ' / 'response.bin')
    paths.append(specification)
    require(len(set(paths)) == len(paths), 'duplicate evidence path')
    return paths


def snapshot(paths, destination):
    """Copy one coherent set while every source handle denies write/delete sharing."""
    catalog = []
    with coherent_read_handles(paths) as streams:
        captured_at = datetime.now(timezone.utc).isoformat()
        for index, (source, stream) in enumerate(zip(paths, streams, strict=True)):
            relative = f'{index:02d}_{source.name}'
            target = destination / relative
            digest = hashlib.sha256()
            size = 0
            with target.open('xb') as output:
                for block in iter(lambda: stream.read(1024**2), b''):
                    output.write(block)
                    digest.update(block)
                    size += len(block)
                output.flush()
                os.fsync(output.fileno())
            catalog.append(dict(source_path=str(source), snapshot_path=relative,
                                bytes=size, sha256=digest.hexdigest(),
                                source_mtime_ns=os.fstat(stream.fileno()).st_mtime_ns,
                                captured_at=captured_at))
    return catalog


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def validate_run_manifest(root, snapshot_dir, paths, catalog):
    entries = {path: (snapshot_dir / record['snapshot_path'], record)
               for path, record in zip(paths, catalog, strict=True)}
    run = load_json(entries[root / 'run_manifest.json'][0])
    require(run.get('head') == PILOT_HEAD, 'run HEAD mismatch')
    require(run.get('economic_evidence_state') == 'NOT_EVALUATED'
            and run.get('promotion_approved') is False, 'run claims economic approval')
    require(isinstance(run.get('code'), dict)
            and set(run['code']) == set(CODE_NAMES), 'run code inventory mismatch')
    for name in CODE_NAMES:
        copied = entries[root / name][1]
        require(run['code'][name] == copied['sha256'] == FROZEN_CODE_SHA256[name],
                f'copied code mismatch: {name}')
    executed_auditor = sha256(Path(audit_theta_ib_source_v1.__file__).read_bytes())
    require(executed_auditor == run['code']['audit_theta_ib_source_v1.py'],
            'executed auditor differs from frozen copy')
    return entries, run


def validate_sealed(ticker, root, entries):
    manifest = load_json(entries[root / ticker / 'manifest.json'][0])
    raw_path, raw_record = entries[root / ticker / 'response.bin']
    require(manifest.get('ticker') == ticker, f'{ticker}: manifest ticker')
    expected = parameters(ticker)
    require(manifest.get('params') == expected, f'{ticker}: request parameters')
    require(manifest.get('url') == BASE + '?' + urlencode(expected), f'{ticker}: URL')
    require(manifest.get('complete') is True and manifest.get('http_status') == 200,
            f'{ticker}: incomplete response')
    require(0 < raw_record['bytes'] <= LIMIT, f'{ticker}: response size')
    require(manifest.get('bytes') == raw_record['bytes']
            and manifest.get('sha256') == raw_record['sha256'],
            f'{ticker}: response hash/size')
    payload = raw_path.read_bytes()
    require(sha256(payload) == raw_record['sha256'], f'{ticker}: snapshot changed')
    observed = load_json(entries[root / ticker / 'initial_balance.json'][0])
    expected_record = audit_theta_ib_source_v1.reconstruct(payload, ticker)
    require(expected_record == observed, f'{ticker}: semantic reconstruction mismatch')
    return dict(status='PASS_COMPONENT_OFFLINE_AUDIT', response_bytes=raw_record['bytes'],
                response_sha256=raw_record['sha256'], bars=len(expected_record['bars']),
                initial_balance_sha256=entries[root / ticker / 'initial_balance.json'][1]['sha256'])


def run(source_root, output_root, specification):
    started = time.perf_counter()
    source_root = Path(source_root).resolve()
    output_root = Path(output_root).resolve()
    specification = Path(specification).resolve()
    require(source_root.is_dir(), 'source root missing')
    require(specification.is_file(), 'specification missing')
    require(output_root != source_root and source_root not in output_root.parents,
            'output must be separate from source')
    expected = source_paths(source_root, specification)
    paths = [path for path in expected if path.is_file()]
    absent = [str(path) for path in expected if not path.is_file()]
    expected_within_source = {path.relative_to(source_root).as_posix()
                              for path in expected if path != specification}
    unexpected = [path.relative_to(source_root).as_posix()
                  for path in source_root.rglob('*')
                  if path.is_file() and path.relative_to(source_root).as_posix()
                  not in expected_within_source]
    with stage(output_root) as staging:
        snapshot_dir = staging / 'snapshot'
        snapshot_dir.mkdir()
        catalog = snapshot(paths, snapshot_dir)
        entries = {path: (snapshot_dir / record['snapshot_path'], record)
                   for path, record in zip(paths, catalog, strict=True)}
        review_code = Path(__file__).read_bytes()
        audit_code = Path(audit_theta_ib_source_v1.__file__).read_bytes()
        spec_record = entries[specification][1]
        audit = dict(status='FAILED_AUDIT', source_run_head=None, tickers={},
                     review_code_sha256=sha256(review_code),
                     independent_auditor_sha256=sha256(audit_code),
                     specification_sha256=spec_record['sha256'])
        try:
            require(not absent, 'required evidence missing: ' + ', '.join(absent))
            require(not unexpected, 'unexpected source files: ' + ', '.join(unexpected))
            _, run_manifest = validate_run_manifest(source_root, snapshot_dir, paths, catalog)
            audit['source_run_head'] = run_manifest['head']
            for ticker in SEALED:
                audit['tickers'][ticker] = validate_sealed(ticker, source_root, entries)
            audit['status'] = 'PASS_SEALED_COMPONENTS_ONLY'
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            audit['reason'] = f'{type(error).__name__}: {error}'
        qqq_entry = entries.get(source_root / 'QQQ' / 'response.bin')
        audit['tickers']['QQQ'] = dict(
            status='UNSEALED_BODY_COMPLETENESS_UNKNOWN',
            response_bytes=qqq_entry[1]['bytes'] if qqq_entry else None,
            response_sha256=qqq_entry[1]['sha256'] if qqq_entry else None,
            parsed=False)
        runtime = dict(python=sys.version.split()[0], platform=platform.platform(),
                       elapsed_seconds=time.perf_counter() - started)
        summary = dict(status='INCOMPLETE_IB_PILOT', audit_status=audit['status'],
                       historical_economic_admission=False,
                       economic_evidence_state='NOT_EVALUATED',
                       prospective_validation_state='NOT_STARTED',
                       technical_ready=False, promotion_approved=False,
                       original_vintage_verified=False, requests_performed=0,
                       source_root=str(source_root), source_run_head=audit['source_run_head'],
                       specification_sha256=spec_record['sha256'], runtime=runtime)
        write_json(staging / 'catalog.json', dict(status='COHERENT_OFFLINE_SNAPSHOT',
                                                documents=catalog, absent=absent,
                                                unexpected=unexpected))
        write_json(staging / 'audit.json', audit)
        write_json(staging / 'summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True)
    parser.add_argument('--output-root', required=True)
    parser.add_argument('--specification', required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.source_root, args.output_root, args.specification), indent=2))


if __name__ == '__main__':
    main()
