"""FREEZE-001: immutable freeze verification; absence always denies test access."""
import json
from pathlib import Path

from .artifacts import digest, stage, write_json
from .contract import ContractError

REQUIRED = frozenset(('models', 'scores', 'decisions', 'events', 'schema', 'inputs', 'runtime', 'code'))


def seal(destination, month, contract_sha256, artifacts):
    if set(artifacts) != REQUIRED:
        raise ContractError('FREEZE-001: incomplete freeze')
    checked = {}
    for kind, paths in artifacts.items():
        if not paths:
            raise ContractError(f'FREEZE-001: missing {kind}')
        checked[kind] = [{'path': str(Path(p).resolve()), 'sha256': digest(p)} for p in paths]
    with stage(destination) as directory:
        write_json(directory / 'freeze_manifest.json', {'month': month,
                   'contract_sha256': contract_sha256, 'artifacts': checked})


def verify(manifest_path, month, contract_sha256, published_sha256):
    if digest(manifest_path) != published_sha256:
        raise ContractError('FREEZE-001: freeze does not match published hash')
    manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    if manifest['month'] != month or manifest['contract_sha256'] != contract_sha256 or set(manifest['artifacts']) != REQUIRED:
        raise ContractError('FREEZE-001: freeze mismatch')
    for items in manifest['artifacts'].values():
        if not items:
            raise ContractError('FREEZE-001: empty artifact group')
        for item in items:
            if digest(item['path']) != item['sha256']:
                raise ContractError('FREEZE-001: changed artifact')
    return manifest
