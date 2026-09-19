"""One authorized QQQ IB source request; no economic or historical admission."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

from neural.jepa import audit_theta_ib_source_v1 as auditor
from neural.jepa import theta_ib_source_v1 as source
from neural.jepa.multiscale_v1r1.provenance import coherent_read_handles


REPOSITORY = Path(__file__).resolve().parents[2]
ROOT = Path('D:/GexResearchArtifacts/multiscale_v1r1/qqq_ib_recovery_20260919_01')
BRANCH = 'research/multiscale-v1r1-net-usd'
SNAPSHOTS = (
    'neural/jepa/theta_qqq_ib_recovery_v1.py',
    'neural/jepa/theta_ib_source_v1.py',
    'neural/jepa/audit_theta_ib_source_v1.py',
    'neural/jepa/multiscale_v1r1/provenance.py',
    'research_papers/JEPA/multiscale_v1r1/26_QQQ_CAPTURE_RECOVERY_PROPOSAL.md',
    'research_papers/JEPA/multiscale_v1r1/23_INITIAL_BALANCE_SOURCE_PILOT.md',
)


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def write_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def published_sources():
    """Verify that the exact code and contracts used are on the published HEAD."""
    branch = subprocess.check_output(
        ['git', 'branch', '--show-current'], cwd=REPOSITORY, text=True,
    ).strip()
    require(branch == BRANCH, 'QQQREC-001: unexpected branch')
    head = subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=REPOSITORY, text=True,
    ).strip()
    remote_line = subprocess.check_output(
        ['git', 'ls-remote', 'origin', f'refs/heads/{BRANCH}'],
        cwd=REPOSITORY, text=True,
    ).strip()
    require(remote_line and remote_line.split()[0] == head,
            'QQQREC-001: unpublished HEAD')
    contents = {}
    for name in SNAPSHOTS:
        path = REPOSITORY / name
        current = path.read_bytes()
        committed = subprocess.check_output(
            ['git', 'show', f'HEAD:{name}'], cwd=REPOSITORY,
        )
        require(current.replace(b'\r\n', b'\n') == committed.replace(b'\r\n', b'\n'),
                f'QQQREC-001: unpublished or changed source {name}')
        contents[name] = current
    return head, contents


def run(destination, authorization_reference):
    """Capture once, then verify the 60 bars independently if the body is complete."""
    root = Path(destination).resolve()
    require(root == ROOT.resolve(), 'QQQREC-001: unexpected output root')
    require(not root.exists(), 'QQQREC-001: output root already exists')
    require(authorization_reference and authorization_reference.strip()
            and authorization_reference.strip().upper() not in {'PENDING', 'NONE'},
            'QQQREC-001: explicit authorization reference required')
    head, contents = published_sources()
    require(root.parent.is_dir(), 'QQQREC-001: output parent missing')
    require(shutil.disk_usage(root.parent).free >= 20 * 1024**3 + source.LIMIT,
            'BLOCKED_RESOURCE: insufficient disk reserve')

    root.mkdir()
    snapshot_dir = root / 'code_snapshot'
    snapshot_dir.mkdir()
    hashes = {}
    for name, body in contents.items():
        snapshot = snapshot_dir / Path(name).name
        snapshot.write_bytes(body)
        hashes[name] = hashlib.sha256(body).hexdigest()
    write_json(root / 'run_manifest.json', {
        'head': head,
        'branch': BRANCH,
        'authorization_reference': authorization_reference.strip(),
        'code_and_contract_sha256': hashes,
        'captured_at': datetime.now(timezone.utc).isoformat(),
        'request': source.request_definition('QQQ'),
        'request_limit_bytes': source.LIMIT,
        'request_deadline_seconds': source.DEADLINE,
        'inactivity_timeout_seconds': 120,
        'original_vintage_verified': False,
        'historical_economic_admission': False,
        'economic_evidence_state': 'NOT_EVALUATED',
        'promotion_approved': False,
    })

    started = time.perf_counter()
    status = 'BLOCKED_QQQ_IB_CAPTURE'
    reason = None
    capture = None
    build_seconds = audit_seconds = None
    try:
        # This is the sole transport call. capture_one owns streaming, deadline,
        # no-redirect behavior, response bytes, and its terminal manifest.
        capture = source.capture_one(root / 'QQQ', 'QQQ')
        require(capture.get('complete') is True and capture.get('http_status') == 200,
                'QQQREC-002: incomplete or non-200 capture')
        require(capture.get('ticker') == 'QQQ'
                and capture.get('params') == source.request_definition('QQQ'),
                'QQQREC-002: request identity mismatch')
        with coherent_read_handles([root / 'QQQ' / 'response.bin']) as streams:
            body = streams[0].read()
        require(0 < len(body) <= source.LIMIT and len(body) == capture.get('bytes'),
                'QQQREC-002: captured byte count mismatch')
        require(hashlib.sha256(body).hexdigest() == capture.get('sha256'),
                'QQQREC-002: captured source changed')
        started_build = time.perf_counter()
        result = source.build_hour(body, 'QQQ')
        build_seconds = time.perf_counter() - started_build
        started_audit = time.perf_counter()
        independent = auditor.reconstruct(body, 'QQQ')
        audit_seconds = time.perf_counter() - started_audit
        require(result == independent,
                'QQQREC-003: independent reconstruction mismatch')
        write_json(root / 'QQQ' / 'initial_balance.json', result)
        status = 'PASS_RECONSTRUCTED_QQQ_IB_COMPONENT'
    except Exception as error:
        reason = f'{type(error).__name__}: {error}'
        if capture and capture.get('complete') is True and capture.get('http_status') == 200:
            status = 'BLOCKED_QQQ_IB_RECONSTRUCTION'

    summary = {
        'status': status,
        'reason': reason,
        'capture_manifest': capture,
        'source_bytes': capture.get('bytes') if capture else None,
        'source_sha256': capture.get('sha256') if capture else None,
        'build_seconds': build_seconds,
        'audit_seconds': audit_seconds,
        'elapsed_seconds': time.perf_counter() - started,
        'original_vintage_verified': False,
        'historical_economic_admission': False,
        'economic_evidence_state': 'NOT_EVALUATED',
        'prospective_validation_state': 'NOT_STARTED',
        'promotion_approved': False,
    }
    write_json(root / 'summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--authorization-reference', required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.root, arguments.authorization_reference), indent=2))


if __name__ == '__main__':
    main()
