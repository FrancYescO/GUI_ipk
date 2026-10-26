#!/usr/bin/env python3
"""Package unvalidated 4.1.38 modules outside the firmware's boot module path."""
import argparse
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path


def archive(files):
    output = io.BytesIO()
    with gzip.GzipFile(fileobj=output, mode='wb', mtime=0, filename='') as zipped:
        with tarfile.open(fileobj=zipped, mode='w') as tar:
            for name, data in files:
                member = tarfile.TarInfo('./' + name)
                member.mode = 0o644
                member.size = len(data)
                tar.addfile(member, io.BytesIO(data))
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    args = parser.parse_args()
    manifest = json.loads((args.root / 'modules.json').read_text())
    destination = args.root / 'ipks'
    destination.mkdir(exist_ok=True)
    seen, sums = {}, []
    for module in manifest['modules']:
        name = module['name']
        if name in seen:
            if seen[name] != module['sha256']:
                raise ValueError('Conflicting module basenames: ' + name)
            continue
        payload = (args.root / module['path']).read_bytes()
        if hashlib.sha256(payload).hexdigest() != module['sha256']:
            raise ValueError('Module changed after compilation: ' + name)
        seen[name] = module['sha256']
        package = 'kmod-' + name.replace('_', '-').lower() + '-4.1.38-candidate'
        staged = 'usr/lib/kernel-module-candidates/4.1.38/' + name + '.ko'
        control = (
            f'Package: {package}\nVersion: 4.1.38-1\nArchitecture: arm_cortex-a9\n'
            'Section: kernel\nMaintainer: GUI_ipk\n'
            'Depends: kernel (= 4.1.38-1-08839f3f6145d3a5d2d04be7567e3f9d)\n'
            f'Description: Staged {name} candidate; load manually after validation\n'
            'X-Manual-Install-Only: yes\nX-Runtime-Validated: no\n'
            'X-Module-Staging-Only: yes\n'
            f'X-Module-Path: /{staged}\n'
            'X-Kernel-Vermagic: 4.1.38 SMP preempt mod_unload ARMv7\n'
        ).encode()
        contents = archive([
            ('debian-binary', b'2.0\n'),
            ('control.tar.gz', archive([('control', control)])),
            ('data.tar.gz', archive([(staged, payload)])),
        ])
        filename = package + '_4.1.38-1_arm_cortex-a9.ipk'
        (destination / filename).write_bytes(contents)
        sums.append(hashlib.sha256(contents).hexdigest() + '  ' + filename)
    (destination / 'SHA256SUMS').write_text('\n'.join(sums) + '\n')
    print('Packaged {} staged module candidates'.format(len(seen)))


if __name__ == '__main__':
    main()
