#!/usr/bin/env python3
"""Create isolated old-opkg fixtures; never load a module or touch host packages."""
import argparse
import gzip
import json
from pathlib import Path
import shlex
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import kernel_opkg_providers as k
from publication_layout import index, kernel_inputs


def package(name, version, depends, data):
    control = (f'Package: {name}\nVersion: {version}\nArchitecture: all\nDepends: {depends}\n'
               'Description: Inert isolated OPKG fixture\n').encode()
    return k.archive({'./debian-binary': b'2.0\n', './control.tar.gz': k.control_archive({'control': control}),
                      './data.tar.gz': k.data_archive(data)})


def prepare(base, rows, remote_base=None):
    source = json.loads((k.BUILD / 'firmware-packages.json').read_text())
    remote_base = Path(remote_base or base)
    for profile, definition in k.definitions().items():
        directory = base / profile
        repo = directory / 'repo'
        repo.mkdir(parents=True, exist_ok=True)
        selected = []
        for row in rows:
            if row['profile'] != profile or row['section'] != definition['feed']:
                continue
            shutil.copyfile(row['_path'], repo / row['filename'])
            selected.append(row)
        raw = {Path(name).stem: row for row in selected if k.fields(row['control']).get('X-Kernel-Capability') != 'yes'
               for name in k.unpack(k.unpack(Path(row['_path']).read_bytes())['data.tar.gz']) if name.startswith('lib/modules/')}
        capabilities = {k.fields(r['control']).get('X-Kernel-Capability-Name'): r for r in selected
                        if k.fields(r['control']).get('X-Kernel-Capability') == 'yes'}
        group = next((g for g in ['kmod-sched-core', 'kmod-nf-nat', 'kmod-nf-conntrack6']
                      if g in capabilities and len(k.unpack(k.unpack(Path(capabilities[g]['_path']).read_bytes())['data.tar.gz'])) == 0), '')
        # A test with a real multi-module backend (rather than builtin-only metadata).
        if group:
            deptext = k.fields(capabilities[group]['control'])['Depends']
            components = [r for r in selected if r['package'] in deptext and r['package'] in {v['package'] for v in raw.values()}]
            if len(components) < 2:
                group = ''
                components = []
        else:
            components = []
        for name, depends in [('fixture-vpn', 'kmod-tun'), ('fixture-group', group or 'kernel')]:
            blob = package(name, '1', depends, {'usr/share/' + name: b'consumer\n'})
            filename = name + '_1_all.ipk'
            (repo / filename).write_bytes(blob)
            selected.append({'package': name, 'control': f'Package: {name}\nVersion: 1\nArchitecture: all\nDepends: {depends}\n',
                             'filename': filename, 'size': len(blob), 'sha256': k.sha(blob)})
        (repo / 'Packages').write_bytes(index(selected))
        (repo / 'Packages.gz').write_bytes(gzip.compress(index(selected), mtime=0))
        release = profile.split('-')[0]
        (directory / 'legacy-tun.ipk').write_bytes(package('kmod-tun', release + '-1', 'kernel',
                                                          {f'lib/modules/{release}/tun.ko': b'INERT-LEGACY-TUN-FIXTURE\n'}))
        (directory / 'unrelated.ipk').write_bytes(package('fixture-unrelated', '1', 'kernel',
                                                         {'usr/share/fixture-unrelated': b'KEEP-ME\n'}))
        old_group = {name: b'INERT-LEGACY-GROUP-FIXTURE\n' for r in components
                     for name in k.unpack(k.unpack(Path(r['_path']).read_bytes())['data.tar.gz'])}
        (directory / 'legacy-group.ipk').write_bytes(package(group or 'fixture-unused', release + '-1', 'kernel', old_group))
        kernel = definition['kernel_package']
        status = f'Package: kernel\nVersion: {kernel}\nArchitecture: {definition["architecture"]}\nStatus: install ok installed\n\n'
        for name, value in source.get(profile, {}).get('packages', {}).items():
            if name in ('kmod-tun', group):
                continue
            status += (f'Package: {name}\nVersion: {value["version"]}\nArchitecture: {definition["architecture"]}\n'
                       f'Depends: {value["depends"]}\nStatus: install ok installed\n\n')
        for case in ['clean', 'legacy', 'group', 'wrong']:
            folder = directory / case
            (folder / 'usr/lib/opkg/info').mkdir(parents=True, exist_ok=True)
            (folder / 'var/lock').mkdir(parents=True, exist_ok=True)
            (folder / 'usr/lib/opkg/status').write_text(status if case != 'wrong' else status.replace('Version: ' + kernel, 'Version: WRONG-ABI', 1))
            (folder / 'usr/lib/opkg/info/kernel.list').write_text('')
            for name in source.get(profile, {}).get('packages', {}):
                (folder / 'usr/lib/opkg/info' / (name + '.list')).write_text('')
            (directory / (case + '.conf')).write_text('dest root /\nlists_dir ext /var/opkg-lists\narch all 1\narch ' + definition['architecture'] +
                                                    ' 100\nsrc fixture file://' + str(remote_base / profile / 'repo') + '\n')
        tun = raw.get('tun')
        meta = capabilities.get('kmod-tun')
        env = {'kernel': kernel, 'tun_package': tun['package'] if tun else meta['package'] if meta else '',
               'canonical_tun': 'yes' if meta and meta['package'] == 'kmod-tun' else 'no',
               'modular': 'yes' if tun else 'no', 'group': group,
               'group_package': capabilities[group]['package'] if group else '',
               'components': ' '.join(r['package'] for r in components),
               'component_checks': ' '.join(name + ':' + k.sha(payload) for r in components
                   for name, payload in k.unpack(k.unpack(Path(r['_path']).read_bytes())['data.tar.gz']).items()),
               'module_sha256': k.sha(k.unpack(k.unpack(Path(tun['_path']).read_bytes())['data.tar.gz'])[f'lib/modules/{release}/tun.ko']) if tun else ''}
        (directory / 'case.env').write_text(''.join(name.upper() + '=' + shlex.quote(value) + '\n' for name, value in env.items()))
    shutil.copyfile(Path(__file__).with_name('run.sh'), base / 'run.sh')
    shutil.copyfile(ROOT / 'scripts/migrate-kernel-package.sh', base / 'migrate.sh')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--remote-base')
    args = parser.parse_args()
    rows = kernel_inputs(args.output.parent / (args.output.name + '-inputs'))
    prepare(args.output, rows, args.remote_base)
    print('Prepared inert offline-root tests for all eight kernel ABIs')
