#!/usr/bin/env python3
"""Apply the recorded VBNT-K runtime profile without changing module payloads."""
import hashlib
import io
import json
from pathlib import Path
import runpy
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def files(blob):
    with tarfile.open(fileobj=io.BytesIO(blob), mode='r:gz') as tar:
        return {m.name: tar.extractfile(m).read() for m in tar if m.isfile()}


def main():
    profile = json.loads((ROOT / 'build/kernel-profiles/vbntk-4.1.52.json').read_text())
    records = json.loads((ROOT / 'build/vbntj/validation/results.json').read_text())['modules']
    expected = {r['asset']: r for r in records if r.get('asset')}
    archive = runpy.run_path(str(ROOT / 'scripts/package-vbnto-4.1.38.py'))['archive']
    for suffix in ('manual', 'network', 'spu', 'rndis-compat'):
        directory = ROOT / ('artifacts/damson-4.1.52-' + suffix)
        for ipk in directory.glob('*.ipk'):
            outer = files(ipk.read_bytes())
            payload = files(outer['./data.tar.gz'])
            if len(payload) != 1 or hashlib.sha256(next(iter(payload.values()))).hexdigest() != expected[ipk.name]['sha256']:
                raise ValueError('Module differs from tested registry: ' + ipk.name)
            control = files(outer['./control.tar.gz'])
            if set(control) != {'./control'}:
                raise ValueError('Unexpected package scripts')
            fields = dict(l.split(': ', 1) for l in control['./control'].decode().splitlines())
            fields = {k: v for k, v in fields.items() if not k.startswith('X-Damson-')}
            fields['Description'] = fields['Description'].replace('Damson', 'VBNT-K')
            fields.update({'Depends': 'kernel (= ' + profile['kernel_package'] + ')',
                           'X-Kernel-Profile': profile['profile'], 'X-Kernel-Target': 'VBNT-K',
                           'X-Firmware': profile['firmware']})
            new_control = ('\n'.join(k + ': ' + v for k, v in fields.items()) + '\n').encode()
            ipk.write_bytes(archive([('debian-binary', b'2.0\n', 0o644),
                                    ('control.tar.gz', archive([('control', new_control, 0o644)]), 0o644),
                                    ('data.tar.gz', outer['./data.tar.gz'], 0o644)]))
        manifest = directory / 'SHA256SUMS'
        entries = []
        for line in manifest.read_text().splitlines():
            if not line.strip():
                continue
            _, name = line.split(None, 1)
            name = name.strip().lstrip('*')
            entries.append(hashlib.sha256((directory / name).read_bytes()).hexdigest() + '  ' + name)
        manifest.write_text('\n'.join(entries) + '\n')


if __name__ == '__main__':
    main()
