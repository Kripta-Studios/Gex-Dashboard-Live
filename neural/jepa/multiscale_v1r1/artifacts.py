"""IO-001: immutable evidence and verifiable access records."""
import hashlib
import json
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path

from .contract import ContractError


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b''):
            h.update(block)
    return h.hexdigest()


def content_digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def write_json(path, value):
    path = Path(path)
    with path.open('xb') as stream:
        stream.write(canonical(value) + b'\n')
        stream.flush()
        os.fsync(stream.fileno())


@contextmanager
def stage(final):
    final = Path(final)
    final.parent.mkdir(parents=True, exist_ok=True)
    staging = final.with_name(final.name + '.staging')
    if final.exists() or staging.exists():
        raise ContractError(f'IO-001: evidence already exists: {final}')
    staging.mkdir()
    yield staging
    # Windows rename refuses replacement. Keep failed staging intact for evidence.
    if final.exists():
        raise ContractError('IO-001: destination appeared during construction')
    staging.rename(final)


def append_access(path, **event):
    """Hash chain records actual reader calls; it is not a tamper-proof external clock."""
    path = Path(path)
    previous = '0' * 64
    sequence = 0
    if path.exists():
        with path.open(encoding='utf-8') as stream:
            for line in stream:
                record = json.loads(line)
                checksum = record.pop('record_sha256')
                if record['previous_sha256'] != previous or content_digest(record) != checksum:
                    raise ContractError('IO-001: broken access log')
                previous = checksum
                sequence += 1
    record = dict(event, sequence=sequence, previous_sha256=previous)
    record['record_sha256'] = content_digest(record)
    with path.open('ab') as stream:
        stream.write(canonical(record) + b'\n')
        stream.flush()
        os.fsync(stream.fileno())


def publication(repo, paths):
    """Verify relevant working bytes and HEAD are committed and present upstream."""
    repo = Path(repo).resolve()

    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()

    head = git('rev-parse', 'HEAD')
    upstream = git('rev-parse', '--abbrev-ref', '@{upstream}')
    remote, branch = upstream.split('/', 1)
    advertised = git('ls-remote', '--heads', remote, f'refs/heads/{branch}').split()
    if not advertised or advertised[0] != head:
        raise ContractError('BLOCKED_PUBLICATION: HEAD does not equal remote branch')
    for path in paths:
        relative = Path(path).resolve().relative_to(repo).as_posix()
        git('ls-files', '--error-unmatch', '--', relative)
        if git('status', '--porcelain', '--', relative):
            raise ContractError(f'BLOCKED_PUBLICATION: uncommitted {relative}')
    return {'head': head, 'upstream': upstream, 'remote_head': advertised[0]}
