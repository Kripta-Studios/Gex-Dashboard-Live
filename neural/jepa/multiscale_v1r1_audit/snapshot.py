"""Independent verification of new documentary snapshots; no evaluator imports."""
import hashlib
import json
from pathlib import Path


def verify_snapshot(directory, expected_manifest_hash):
    directory = Path(directory).resolve()
    data = (directory / 'manifest.json').read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_manifest_hash:
        raise ValueError('AUDIT: snapshot manifest mismatch')
    manifest = json.loads(data)
    contents = {}
    identities = set()
    for entry in manifest['documents']:
        name = entry['snapshot_path']
        path = (directory / name).resolve()
        if path.parent != directory or name in contents or entry['source_path'] in identities:
            raise ValueError('AUDIT: invalid documentary identity')
        data = path.read_bytes()
        if len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError('AUDIT: snapshot byte mismatch')
        contents[name] = data.decode('utf-8', errors='replace')
        identities.add(entry['source_path'])
    return contents
