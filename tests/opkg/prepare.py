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
            group_modules = json.loads((k.BUILD / 'legacy-map.json').read_text())['groups'][group]['modules']
            components = [raw[m] for m in group_modules if m in raw]
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
        kernel = definition['kernel_package']
        stock = source.get(profile, {}).get('packages', {})
        group_version = stock[group]['version'] if group in stock else release + '-1'
        (directory / 'legacy-group.ipk').write_bytes(package(group or 'fixture-unused', group_version,
                                                            'kernel (= ' + kernel + ')', old_group))
        status = f'Package: kernel\nVersion: {kernel}\nArchitecture: {definition["architecture"]}\nStatus: install ok installed\n\n'
        for name, value in source.get(profile, {}).get('packages', {}).items():
            if name in ('kmod-tun', group):
                continue
            status += (f'Package: {name}\nVersion: {value["version"]}\nArchitecture: {definition["architecture"]}\n'
                       f'Depends: {value["depends"]}\nStatus: install ok installed\n\n')
        for case in ['clean', 'legacy', 'group', 'wrong', 'qos', 'usb']:
            folder = directory / case
            (folder / 'usr/lib/opkg/info').mkdir(parents=True, exist_ok=True)
            (folder / 'var/lock').mkdir(parents=True, exist_ok=True)
            case_status = status
            if case == 'qos' and group in stock:
                value = stock[group]
                case_status += (f'Package: {group}\nVersion: {value["version"]}\nArchitecture: {definition["architecture"]}\n'
                                f'Depends: {value["depends"]}\nStatus: install ok installed\n\n')
            (folder / 'usr/lib/opkg/status').write_text(case_status if case != 'wrong' else status.replace('Version: ' + kernel, 'Version: WRONG-ABI', 1))
            (folder / 'usr/lib/opkg/info/kernel.list').write_text('')
            for name, value in stock.items():
                paths = []
                if name != 'kmod-tun' and (name != group or case == 'qos'):
                    for module in value['modules']:
                        path = Path('lib/modules') / release / (module + '.ko')
                        (folder / path).parent.mkdir(parents=True, exist_ok=True)
                        (folder / path).write_bytes(('INERT-STOCK-' + module + '\n').encode())
                        paths.append('/' + str(path))
                (folder / 'usr/lib/opkg/info' / (name + '.list')).write_text(''.join(p + '\n' for p in paths))
            (directory / (case + '.conf')).write_text('dest root /\nlists_dir ext /var/opkg-lists\narch all 1\narch ' + definition['architecture'] +
                                                    ' 100\nsrc fixture file://' + str(remote_base / profile / 'repo') + '\n')
        tun = raw.get('tun')
        meta = capabilities.get('kmod-tun')
        env = {'kernel': kernel, 'tun_package': tun['package'] if tun else meta['package'] if meta else '',
               'cdc_package': raw['cdc_ether']['package'] if definition.get('installable') else '',
               'cdc_filename': raw['cdc_ether']['filename'] if definition.get('installable') else '',
               'rndis_package': raw['rndis_host']['package'] if definition.get('installable') else '',
               'rndis_filename': raw['rndis_host']['filename'] if definition.get('installable') else '',
               'qos_package': capabilities['kmod-act-connmark']['package'] if 'kmod-act-connmark' in capabilities and 'act_connmark' in raw else '',
               'canonical_tun': 'yes' if meta and meta['package'] == 'kmod-tun' else 'no',
               'modular': 'yes' if tun else 'no', 'group': group,
               'group_package': capabilities[group]['package'] if group else '',
               'components': ' '.join(r['package'] for r in components),
               'component_checks': ' '.join(name + ':' + k.sha(payload) for r in components
                   for name, payload in k.unpack(k.unpack(Path(r['_path']).read_bytes())['data.tar.gz']).items()),
               'module_sha256': k.sha(k.unpack(k.unpack(Path(tun['_path']).read_bytes())['data.tar.gz'])[f'lib/modules/{release}/tun.ko']) if tun else ''}
        (directory / 'case.env').write_text(''.join(name.upper() + '=' + shlex.quote(value) + '\n' for name, value in env.items()))
        usb_names = ('kmod-usb-net-cdc-ether', 'kmod-usb-net-rndis')
        by_name = {r['package']: r for r in selected}
        recovery = json.loads(gzip.decompress((k.BUILD / 'stock-usb.json.gz').read_bytes()))[profile]['packages']
        for case in ('usb-clean', 'usb-native', 'usb-manual', 'usb-wrong'):
            folder = directory / case
            shutil.copytree(directory / 'usb', folder)
            database = folder / 'usr/lib/opkg/status'
            missing = (*usb_names, *recovery) if case == 'usb-clean' else (*usb_names, 'kmod-usb-net')
            removed = ['Package: ' + name for name in missing]
            blocks = [b for b in database.read_text().split('\n\n') if b and b.splitlines()[0] not in removed]
            for name in missing:
                for path in (folder / 'usr/lib/opkg/info').glob(name + '.*'):
                    path.unlink()
            if case in ('usb-native', 'usb-manual'):
                for name in usb_names:
                    f = k.fields(by_name[name]['control'])
                    owner = name if case == 'usb-native' else f['X-Previous-Module-Package']
                    version = stock.get(name, {}).get('version', release + '-1')
                    blocks.append(f'Package: {owner}\nVersion: {version}\nArchitecture: {definition["architecture"]}\nDepends: kernel (= {kernel})\nStatus: install ok installed')
                    path = f['X-Module-Path']
                    target = folder / path.lstrip('/')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(b'INERT-OLD-USB-DRIVER\n')
                    (folder / 'usr/lib/opkg/info' / (owner + '.list')).write_text(path + '\n')
            text = '\n\n'.join(blocks) + '\n\n'
            if case == 'usb-wrong':
                text = text.replace('Version: ' + kernel, 'Version: WRONG-ABI', 1)
            database.write_text(text)
            (directory / (case + '.conf')).write_text((directory / 'usb.conf').read_text())
        (directory / 'usb-checks').write_text('\n'.join(
            k.fields(by_name[name]['control'])['X-Module-SHA256'] + '  ' +
            k.fields(by_name[name]['control'])['X-Module-Path'].lstrip('/') for name in usb_names) + '\n')
        (directory / 'usb-previous').write_text('\n'.join(k.fields(by_name[name]['control'])['X-Previous-Module-Package'] for name in usb_names) + '\n')
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
