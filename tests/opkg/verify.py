#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import sys
base, mode = Path(sys.argv[1]), sys.argv[2]
root = base / mode
expected = json.loads((base / 'expected.json').read_text())
for path, checksum in expected['hashes'].items():
    assert hashlib.sha256((root / path).read_bytes()).hexdigest() == checksum, (mode, path)
for path, owner in expected['owners'].items():
    assert '/' + path in (root / 'usr/lib/opkg/info' / (owner + '.list')).read_text().splitlines(), (mode, path, owner)
status = {}
for block in (root / 'usr/lib/opkg/status').read_text().split('\n\n'):
    f = dict(line.split(': ', 1) for line in block.splitlines() if ': ' in line)
    if f:
        status[f['Package']] = f
for name, version in expected['versions'].items():
    assert status[name]['Version'] == version, (mode, name)
    assert status[name]['Status'].endswith(' installed'), (mode, name)
print('Verified', len(expected['versions']), 'packages and', len(expected['hashes']), 'files:', mode)
