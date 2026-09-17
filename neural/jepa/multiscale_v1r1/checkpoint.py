"""Whole-run synthetic checkpoints: identical code and every frozen dependency."""
import json
from pathlib import Path

from .artifacts import digest, write_json
from .contract import ContractError


def save_checkpoint(root, month, code_paths, contract_hash):
    root = Path(root)
    folder = root / 'checkpoints'
    folder.mkdir(exist_ok=True)
    manifest = dict(month=month, contract_sha256=contract_hash,
                    code={str(Path(p).resolve()): digest(p) for p in code_paths},
                    artifacts={str(p.relative_to(root)): digest(p) for p in root.rglob('*') if p.is_file()})
    target = folder / f'{month}.json'
    temporary = folder / f'{month}.staging'
    write_json(temporary, manifest)
    temporary.rename(target)
    return target


def verify_resume(root, contract_hash):
    root = Path(root)
    paths = sorted((root / 'checkpoints').glob('*.json'))
    if not paths:
        raise ContractError('RESUME: no completed immutable checkpoint')
    latest = paths[-1]
    manifest = json.loads(latest.read_bytes())
    if manifest['contract_sha256'] != contract_hash:
        raise ContractError('RESUME: contract changed')
    expected = set(manifest['artifacts']) | {str(latest.relative_to(root))}
    actual = {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
    if expected != actual:
        raise ContractError('RESUME: partial or additional work after checkpoint; preserve and use new run')
    for name, checksum in manifest['code'].items():
        if digest(name) != checksum:
            raise ContractError('RESUME: code changed')
    for name, checksum in manifest['artifacts'].items():
        if digest(root / name) != checksum:
            raise ContractError('RESUME: dependency changed')
    return manifest
