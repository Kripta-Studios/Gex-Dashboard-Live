"""REC-001: preserve exact documentary evidence before parsing mutable logs."""
import hashlib
import json
import os
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .artifacts import stage, write_json
from .contract import ContractError


@contextmanager
def coherent_read_handles(paths):
    """Deny write/delete sharing on ALL selected files until the last read ends.

    This is a point-in-time set of bytes, not an application transaction boundary.
    Fail on platforms without this mechanism; do not claim stat() is a lock.
    """
    if os.name != 'nt':
        raise ContractError('REC-001: no supported coherent snapshot mechanism on this platform')
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    with ExitStack() as stack:
        streams = []
        for path in paths:
            handle = create(str(Path(path).resolve()), 0x80000000, 1, None, 3, 0x80, None)
            if handle == ctypes.c_void_p(-1).value:
                raise ContractError(f'REC-001: cannot exclude writers: {path}: WinError {ctypes.get_last_error()}')
            try:
                fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
            except BaseException:
                close(handle)
                raise
            streams.append(stack.enter_context(os.fdopen(fd, 'rb')))
        yield streams


def capture_documents(paths, destination, *, roles=None, dependencies=None):
    """Caller supplies explicit non-secret source paths; never read raw market rows."""
    paths = sorted(Path(path).resolve() for path in paths)
    if len(set(paths)) != len(paths):
        raise ContractError('REC-001: repeated documentary source')
    with stage(destination) as temporary:
        records = []
        with coherent_read_handles(paths) as streams:
            captured_at = datetime.now(timezone.utc).isoformat()
            for index, (source, stream) in enumerate(zip(paths, streams, strict=True)):
                payload = stream.read()
                checksum = hashlib.sha256(payload).hexdigest()
                name = f'{index:04d}_{source.name}'
                with (temporary / name).open('xb') as target:
                    target.write(payload)
                    target.flush()
                    os.fsync(target.fileno())
                records.append(dict(source_path=str(source), snapshot_path=name,
                                    sha256=checksum, bytes=len(payload), captured_at=captured_at,
                                    role=(roles or {}).get(str(source), 'documentary_evidence'),
                                    dependencies=(dependencies or {}).get(str(source), []),
                                    source_mtime_ns=os.fstat(stream.fileno()).st_mtime_ns))
        write_json(temporary / 'manifest.json', dict(
            rule='REC-001', recorded_at=datetime.now(timezone.utc).isoformat(),
            coherence='Win32 shared-read handles held for entire selected set; write/delete denied',
            scope='Document copies attest their own contents, not historical market availability.',
            documents=records,
        ))
    return Path(destination) / 'manifest.json'


def read_document(snapshot_root, name, expected_manifest_sha256):
    root = Path(snapshot_root).resolve()
    manifest = root / 'manifest.json'
    manifest_bytes = manifest.read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != expected_manifest_sha256:
        raise ContractError('REC-001: documentary manifest changed')
    records = json.loads(manifest_bytes)['documents']
    matches = [record for record in records if record['snapshot_path'] == name]
    if len(matches) != 1:
        raise ContractError('REC-001: missing or ambiguous documentary copy')
    record = matches[0]
    path = (root / name).resolve()
    if path.parent != root:
        raise ContractError('REC-001: documentary path escaped root')
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != record['sha256'] or len(payload) != record['bytes']:
        raise ContractError('REC-001: documentary copy changed or escaped root')
    return payload.decode('utf-8', errors='replace')
