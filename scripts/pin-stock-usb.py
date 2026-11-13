#!/usr/bin/env python3
"""Pin original USB dependency payloads from the extracted-firmware Git mirror."""
import argparse
import base64
import gzip
import json
from pathlib import Path
import subprocess

from kernel_opkg_providers import BUILD, definitions, fields, sha


def pin(repository, sources):
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
        pending = ['kmod-usb-net']
        while pending:
            name = pending.pop()
            if name in packages or name == 'kernel':
                continue
            control = read('usr/lib/opkg/info/' + name + '.control')
            listing = read('usr/lib/opkg/info/' + name + '.list')
            f = fields(control.decode())
            expected = inventory[profile]['packages'].get(name)
            if expected and (f['Version'] != expected['version'] or f['Depends'] != expected['depends']):
                raise ValueError('Stock metadata mismatch: ' + profile + '/' + name)
            if 'kernel (=' + kernel + ')' not in f['Depends']:
                raise ValueError('Missing stock ABI binding: ' + name)
            data = {}
            for path in listing.decode().splitlines():
                path = path.lstrip('/')
                content = read(path)
                tree = subprocess.check_output(['git', '-C', str(repository), 'ls-tree', commit, '--', path]).decode()
                mode = tree.split()[0]
                data[path] = {'mode': mode, 'base64': base64.b64encode(content).decode(), 'sha256': sha(content)}
            packages[name] = {'control': control.decode(), 'list': listing.decode(), 'data': data,
                              'control_sha256': sha(control), 'list_sha256': sha(listing)}
            pending.extend(part.strip().split()[0] for part in f['Depends'].split(','))
        result[profile] = dict(source, kernel_package=kernel, packages=packages)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repository', type=Path)
    parser.add_argument('sources', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    data = json.dumps(pin(args.repository, json.loads(args.sources.read_text())), sort_keys=True, indent=2).encode() + b'\n'
    with args.output.open('wb') as stream:
        with gzip.GzipFile(filename='', fileobj=stream, mode='wb', mtime=0) as output:
            output.write(data)
