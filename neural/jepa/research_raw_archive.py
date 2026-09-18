"""Lossless raw-byte archive. No columns, time filtering or market calculations."""
import hashlib
import json
from pathlib import Path
import time

import pyarrow as pa

from neural.jepa.multiscale_v1r1.provenance import coherent_read_handles

CHUNK = 1024 * 1024


def verify(directory, expected_manifest_sha256):
    root = Path(directory)
    with coherent_read_handles([root/'manifest.json', root/'body.zst']) as streams:
        manifest_bytes = streams[0].read()
        if hashlib.sha256(manifest_bytes).hexdigest() != expected_manifest_sha256:
            raise ValueError('ARCHIVE: manifest changed')
        manifest = json.loads(manifest_bytes)
        compressed = hashlib.file_digest(streams[1], 'sha256').hexdigest()
        if compressed != manifest['archive_sha256']:
            raise ValueError('ARCHIVE: compressed bytes changed')
        streams[1].seek(0)
        digest, count = hashlib.sha256(), 0
        with pa.CompressedInputStream(streams[1], 'zstd') as decoded:
            while block := decoded.read(CHUNK):
                digest.update(block)
                count += len(block)
                if count > manifest['original_bytes']:
                    raise ValueError('ARCHIVE: decompression exceeds declared size')
        if count != manifest['original_bytes'] or digest.hexdigest() != manifest['original_sha256']:
            raise ValueError('ARCHIVE: restored bytes mismatch')
    return dict(status='PASS_BYTE_EXACT_RAW_ARCHIVE', bytes_restored=count, original_sha256=digest.hexdigest())


def create(source, expected_source_sha256, destination):
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    original, count = hashlib.sha256(), 0
    with coherent_read_handles([source]) as streams, (root/'body.zst').open('xb') as output:
        with pa.CompressedOutputStream(output, 'zstd') as compressed:
            while block := streams[0].read(CHUNK):
                original.update(block)
                count += len(block)
                compressed.write(block)
    if original.hexdigest() != expected_source_sha256:
        raise ValueError('ARCHIVE: original source identity mismatch; partial archive preserved')
    elapsed = time.perf_counter() - start
    with (root/'body.zst').open('rb') as archive:
        compressed_sha = hashlib.file_digest(archive, 'sha256').hexdigest()
    manifest = dict(original_path=str(Path(source).resolve()), original_sha256=original.hexdigest(),
                    original_bytes=count, archive_sha256=compressed_sha, archive_bytes=(root/'body.zst').stat().st_size,
                    codec='zstd', pyarrow=pa.__version__, compression_seconds=elapsed,
                    representation='exact original byte stream; no data/model transformation')
    with (root/'manifest.json').open('x', encoding='utf-8') as output:
        json.dump(manifest, output, indent=2)
        output.write('\n')
    manifest_sha = hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest()
    start = time.perf_counter()
    checked = verify(root, manifest_sha)
    checked.update(verification_seconds=time.perf_counter()-start, manifest_sha256=manifest_sha)
    with (root/'verification.json').open('x', encoding='utf-8') as output:
        json.dump(checked, output, indent=2)
        output.write('\n')
    return dict(**manifest, verification=checked)
