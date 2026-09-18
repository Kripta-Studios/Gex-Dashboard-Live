import hashlib
import json

import pytest

from neural.jepa.research_raw_archive import create, verify


def test_byte_exact_archive_and_original_append_is_independent(tmp_path):
    original = tmp_path/'input.bin'
    raw = b'quote,timestamp,value\r\n' * 1000 + bytes(range(256))
    original.write_bytes(raw)
    archived = tmp_path/'archive'
    report = create(original, hashlib.sha256(raw).hexdigest(), archived)
    original.write_bytes(raw+b'new activity')
    assert verify(archived, report['verification']['manifest_sha256'])['bytes_restored'] == len(raw)
    with pytest.raises(FileExistsError):
        create(original, hashlib.sha256(raw).hexdigest(), archived)


@pytest.mark.parametrize('target', ['body', 'manifest', 'forged_size'])
def test_archive_mutation_rejected(tmp_path, target):
    original = tmp_path/'input.bin'
    original.write_bytes(b'original-source\n'*1000)
    output = tmp_path/'archive'
    report = create(original, hashlib.sha256(original.read_bytes()).hexdigest(), output)
    checksum = report['verification']['manifest_sha256']
    if target == 'body':
        (output/'body.zst').write_bytes((output/'body.zst').read_bytes()+b'changed')
    else:
        manifest = json.loads((output/'manifest.json').read_bytes())
        manifest['original_bytes'] = 1
        (output/'manifest.json').write_text(json.dumps(manifest))
        if target == 'forged_size':
            checksum = hashlib.sha256((output/'manifest.json').read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='ARCHIVE'):
        verify(output, checksum)
