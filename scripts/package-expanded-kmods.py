#!/usr/bin/env python3
"""Package unvalidated 4.1.38 modules outside the firmware's boot module path."""
import argparse
import gzip
import hashlib
import io
import json
import tarfile
from collections import defaultdict
from pathlib import Path

QUARANTINED = {
    '340112b7526852684bf03b922da156c524ac436a663b101c0eaff23892563120':
        'xt_nat: kernel crash during test start; root cause unresolved',
}
QUARANTINED_NAMES = {'xt_nat'}


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
    parser.add_argument('--module-archive', type=Path,
                        help='Read exact-case module paths directly from a tar archive')
    args = parser.parse_args()
    manifest = json.loads((args.root / 'modules.json').read_text())
    by_stem = defaultdict(set)
    for module in manifest['modules']:
        by_stem[module['name'].replace('_', '-').lower()].add(module['name'])
    archived = None
    if args.module_archive:
        with tarfile.open(args.module_archive, 'r:gz') as source:
            archived = {module['path']: source.extractfile(module['path']).read()
                        for module in manifest['modules']}
    destination = args.root / 'ipks'
    destination.mkdir(exist_ok=True)
    # This directory is generated: do not leave obsolete or quarantined IPKs.
    for previous in destination.glob('kmod-*-4.1.38-candidate_4.1.38-1_arm_cortex-a9.ipk'):
        previous.unlink()
    seen, sums, package_owners = {}, [], {}
    for module in manifest['modules']:
        name = module['name']
        if name in seen:
            if seen[name] != module['sha256']:
                raise ValueError('Conflicting module basenames: ' + name)
            continue
        payload = (archived[module['path']] if archived is not None
                   else (args.root / module['path']).read_bytes())
        if hashlib.sha256(payload).hexdigest() != module['sha256']:
            raise ValueError('Module changed after compilation: ' + name)
        seen[name] = module['sha256']
        if name in QUARANTINED_NAMES or module['sha256'] in QUARANTINED:
            continue
        stem = name.replace('_', '-').lower()
        if len(by_stem[stem]) > 1:
            leaf = name[3:] if name.startswith('xt_') else ''
            if leaf and leaf.isupper():
                stem += '-target'
            elif leaf and leaf.islower():
                stem += '-match'
            else:
                stem += '-' + hashlib.sha256(name.encode()).hexdigest()[:8]
        package = 'kmod-' + stem + '-4.1.38-candidate'
        if package in package_owners:
            raise ValueError('Package name collision: ' + package)
        package_owners[package] = name
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
    (destination / 'QUARANTINED.txt').write_text(
        'xt_nat: all candidate builds withheld until the crash cause is resolved\n' + ''.join(
        digest + '  ' + reason + '\n' for digest, reason in QUARANTINED.items()))
    print('Packaged {} staged module candidates'.format(len(package_owners)))


if __name__ == '__main__':
    main()
