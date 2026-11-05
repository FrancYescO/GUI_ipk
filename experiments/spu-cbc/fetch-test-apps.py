#!/usr/bin/env python3
"""Extract pinned test executables/libraries into a private temporary bundle."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import urllib.request

destination = Path(sys.argv[1]).resolve()
destination.mkdir(parents=True, exist_ok=True)
manifest = json.loads(Path(__file__).with_name('app-inputs.json').read_text())
for row in manifest['packages']:
    payload = urllib.request.urlopen(row['download_url'], timeout=30).read()
    if hashlib.sha256(payload).hexdigest() != row['sha256']:
        raise ValueError('Unexpected IPK: ' + row['package'])
    with tarfile.open(fileobj=io.BytesIO(payload)) as ipk:
        member = next(m for m in ipk if Path(m.name).name.startswith('data.tar.'))
        data = ipk.extractfile(member).read()
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for member in archive:
            name = member.name.removeprefix('./')
            if not (name in ('usr/bin/openssl', 'usr/sbin/openvpn', 'usr/sbin/ip') or
                    name.startswith(('usr/lib/liblzo2.so', 'usr/lib/liblz4.so', 'usr/lib/libcap-ng.so'))):
                continue
            path = destination / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.resolve().relative_to(destination)
            if member.issym():
                (path.parent / member.linkname).resolve().relative_to(destination)
                if not path.exists() and not path.is_symlink():
                    path.symlink_to(member.linkname)
            elif member.isfile():
                path.write_bytes(archive.extractfile(member).read())
                path.chmod(member.mode & 0o777)
    print(row['package'], row['version'], row['sha256'])
