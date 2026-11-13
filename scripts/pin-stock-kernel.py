#!/usr/bin/env python3
"""Pin original kernel package groups and their dependency payloads from the extracted-firmware Git mirror."""
import argparse
import base64
import gzip
import json
from pathlib import Path
import subprocess

from kernel_opkg_providers import BUILD, definitions, fields, sha


def pin(repository, sources, catalog):
    inventory = json.loads((BUILD / 'firmware-packages.json').read_text())
    result = {}
    for profile, source in sources.items():
        commit = source['commit']
        def read(path):
            return subprocess.check_output(['git', '-C', str(repository), 'show', commit + ':' + path])
        kernel = fields(read('usr/lib/opkg/info/kernel.control').decode())['Version']
        if kernel != definitions()[profile]['kernel_package']:
            raise ValueError('Firmware ABI mismatch: ' + profile)
        packages = {}
        records = [r for r in catalog['records'] if r.get('profile') == profile]
        modules = {Path(fields(r['control']).get('X-Module-Path', '')).stem for r in records}
        for row in records:
            modules.update(json.loads(fields(row['control']).get('X-Rebuilt-Modules', '{}')))
        pending = list(source.get('roots', [name for name, entry in inventory[profile]['packages'].items() if modules.intersection(entry['modules'])]))
        controls = subprocess.check_output(['git', '-C', str(repository), 'ls-tree', '-r', '--name-only', commit, '--', 'usr/lib/opkg/info']).decode().splitlines()
        native = {Path(path).name[:-8] for path in controls if path.endswith('.control') and Path(path).name.startswith('kmod-')}
        if 'roots' not in source:
            for row in records:
                for part in fields(row['control']).get('Depends', '').split(','):
                    if part.strip() and part.strip().split()[0] in native:
                        pending.append(part.strip().split()[0])
        while pending:
            name = pending.pop()
            if name in packages or name == 'kernel':
                continue
            control = read('usr/lib/opkg/info/' + name + '.control')
            listing = read('usr/lib/opkg/info/' + name + '.list')
            f = fields(control.decode())
            if f['Package'] != name:
                raise ValueError('Stock package identity mismatch: ' + profile + '/' + name)
            expected = inventory[profile]['packages'].get(name)
            if expected and (f['Version'] != expected['version'] or f['Depends'] != expected['depends']):
                raise ValueError('Stock metadata mismatch: ' + profile + '/' + name)
            if 'kernel (=' + kernel + ')' not in f['Depends']:
                raise ValueError('Missing stock ABI binding: ' + name)
            data = {}
            missing_original = []
            for path in listing.decode().splitlines():
                path = path.lstrip('/')
                tree = subprocess.check_output(['git', '-C', str(repository), 'ls-tree', commit, '--', path]).decode()
                if not tree:
                    if path.endswith('.ko') and Path(path).stem in modules:
                        missing_original.append(path)
                        continue
                    raise ValueError('Original firmware file is unavailable: ' + profile + '/' + path)
                content = read(path)
                mode = tree.split()[0]
                data[path] = {'mode': mode, 'base64': base64.b64encode(content).decode(), 'sha256': sha(content)}
            packages[name] = {'control': control.decode(), 'list': listing.decode(), 'data': data, 'requires_rebuilt_files': missing_original,
                              'control_sha256': sha(control), 'list_sha256': sha(listing)}
            pending.extend(part.strip().split()[0] for part in f['Depends'].split(','))
        result[profile] = dict(source, kernel_package=kernel, packages=packages)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repository', type=Path)
    parser.add_argument('sources', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--catalog', type=Path, default=BUILD.parent / 'publication/bootstrap.json.gz')
    args = parser.parse_args()
    data = json.dumps(pin(args.repository, json.loads(args.sources.read_text()), json.loads(gzip.decompress(args.catalog.read_bytes()))), sort_keys=True, indent=2).encode() + b'\n'
    with args.output.open('wb') as stream:
        with gzip.GzipFile(filename='', fileobj=stream, mode='wb', mtime=0) as output:
            output.write(data)
