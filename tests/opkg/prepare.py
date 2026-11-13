#!/usr/bin/env python3
"""Inert roots for exhaustive standard kernel installation and migration tests."""
import argparse
import base64
import gzip
import json
from pathlib import Path
import shutil
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import kernel_opkg_providers as k
from kernel_feed_packages import stock_data
from publication_layout import index, kernel_inputs

def stanza(name, version, architecture, depends=''):
    dependency = f'Depends: {depends}\n' if depends else ''
    return f'Package: {name}\nVersion: {version}\nArchitecture: {architecture}\n' + dependency + 'Status: install ok installed\n\n'

def prepare(base, rows, remote_base=None):
    pinned = json.loads(gzip.decompress((k.BUILD / 'stock-kernel.json.gz').read_bytes()))
    remote_base = Path(remote_base or base)
    for profile, definition in k.definitions().items():
        directory = base / profile
        repo = directory / 'repo'
        repo.mkdir(parents=True, exist_ok=True)
        selected = [r for r in rows if r['profile'] == profile and k.fields(r['control']).get('X-Module-Staging-Only') != 'yes']
        for row in selected:
            shutil.copyfile(row['_path'], repo / row['filename'])
        control = ('Package: fixture-all\nVersion: 1\nArchitecture: all\nDepends: ' + ', '.join(r['package'] + ' (= ' + r['version'] + ')' for r in selected) + '\nDescription: Inert consumer of all standard kernel packages\n').encode()
        blob = k.archive({'./debian-binary': b'2.0\n', './control.tar.gz': k.control_archive({'control': control}), './data.tar.gz': k.archive({})})
        filename = 'fixture-all_1_all.ipk'
        (repo / filename).write_bytes(blob)
        fixture = {'package': 'fixture-all', 'control': control.decode(), 'filename': filename, 'sha256': k.sha(blob), 'size': len(blob)}
        raw = index(selected + [fixture])
        (repo / 'Packages').write_bytes(raw)
        (repo / 'Packages.gz').write_bytes(gzip.compress(raw, mtime=0))
        expected, owners, migration, graph, versions, previous = {}, {}, {}, {}, {}, {}
        for row in selected:
            f = k.fields(row['control'])
            versions[row['package']] = row['version']
            outer = k.unpack(Path(row['_path']).read_bytes())
            for path, content in k.unpack(outer['data.tar.gz']).items():
                if path in expected:
                    raise ValueError('Two standard packages own one file: ' + profile + '/' + path)
                expected[path] = k.sha(content)
                owners[path] = row['package']
            if f.get('X-Previous-Module-Packages'):
                migration[row['package']] = row['filename']
            graph[row['package']] = [p.strip().split()[0] for p in f['Depends'].split(',') if p.strip().split()[0] != 'kernel']
            previous.update(json.loads(f.get('X-Previous-Module-Owners', '{}')))
        order, visited = [], set()
        def visit(name):
            if name in visited:
                return
            visited.add(name)
            for dep in graph[name]:
                visit(dep)
            if name in migration:
                order.append(migration[name])
        for name in graph:
            visit(name)
        (directory / 'migration-order').write_text('\n'.join(order) + '\n')
        first = k.unpack((repo / order[0]).read_bytes())
        tampered = k.unpack(first['data.tar.gz'])
        module = next(p for p in tampered if p.endswith('.ko'))
        tampered[module] = b'CORRUPTED-MODULE\n'
        (directory / 'tampered.ipk').write_bytes(k.archive({'./debian-binary': first['debian-binary'], './control.tar.gz': first['control.tar.gz'], './data.tar.gz': k.data_archive(tampered)}))
        (directory / 'expected.json').write_text(json.dumps({'hashes': expected, 'owners': owners, 'versions': versions}, sort_keys=True))
        (directory / 'previous').write_text('\n'.join(sorted(previous)) + '\n')
        for case in ('clean', 'native', 'legacy', 'wrong'):
            root = directory / case
            info = root / 'usr/lib/opkg/info'
            info.mkdir(parents=True)
            (root / 'var/lock').mkdir(parents=True)
            (info / 'kernel.list').write_text('')
            status = stanza('kernel', definition['kernel_package'] if case != 'wrong' else 'WRONG-ABI', definition['architecture'])
            payload = {}
            if case == 'native':
                for name, original in pinned[profile]['packages'].items():
                    f = k.fields(original['control'])
                    status += stanza(name, f['Version'], f['Architecture'], f['Depends'])
                    (info / (name + '.list')).write_text(original['list'])
                    payload.update(original['data'])
                    for path in original.get('requires_rebuilt_files', []):
                        content = b'INERT-UNAVAILABLE-ORIGINAL-MODULE\n'
                        payload[path] = {'base64': base64.b64encode(content).decode(), 'sha256': k.sha(content), 'mode': '100644'}
            if case == 'legacy':
                for name, paths in previous.items():
                    status += stanza(name, profile.split('-')[0] + '-6', definition['architecture'], 'kernel (= ' + definition['kernel_package'] + ')')
                    (info / (name + '.list')).write_text('\n'.join(paths) + '\n')
                    for path in paths:
                        content = b'INERT-PREVIOUS-MODULE\n'
                        payload[path.lstrip('/')] = {'base64': base64.b64encode(content).decode(), 'sha256': k.sha(content), 'mode': '100644'}
                status += stanza('fixture-existing-consumer', '1', 'all', 'kmod-tun')
                (info / 'fixture-existing-consumer.list').write_text('')
            if payload:
                (directory / (case + '-payload.tar.gz')).write_bytes(stock_data(payload))
            (root / 'usr/lib/opkg/status').write_text(status)
            (directory / (case + '.conf')).write_text('dest root /\nlists_dir ext /var/opkg-lists\narch all 1\narch ' + definition['architecture'] + ' 100\nsrc/gz fixture file://' + str(remote_base / profile / 'repo') + '\n')
    shutil.copyfile(ROOT / 'scripts/migrate-standard-kernel-package.sh', base / 'migrate.sh')
    shutil.copyfile(Path(__file__).with_name('verify.py'), base / 'verify.py')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--remote-base')
    args = parser.parse_args()
    prepare(args.output, kernel_inputs(args.output.parent / (args.output.name + '-inputs')), args.remote_base)
    print('Prepared exhaustive standard package tests for all eight kernel ABIs')
