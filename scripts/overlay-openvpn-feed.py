#!/usr/bin/env python3
"""Apply the verified OpenVPN snapshot without replacing other feed packages."""
import argparse
import hashlib
import importlib.util
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('shards', ROOT / 'scripts/merge-userspace-shards.py')
shards = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shards)
PACKAGES = {
    'openvpn-openssl': ('base', '2.6.23-1'),
    'openvpn-mbedtls': ('base', '2.6.23-1'),
    'libcap-ng': ('base', '0.8.5-1'),
    'liblz4': ('packages', 'v1.7.5-1'),
}
TRANSPORT = {'Filename', 'Size', 'SHA256sum', 'MD5Sum'}


def overlay(source, output):
    expected = {}
    for line in (source / 'SHA256SUMS').read_text().splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  ([A-Za-z0-9_.+-]+\.ipk)', line)
        if not match or match[2] in expected:
            raise ValueError('Invalid OpenVPN checksum manifest')
        expected[match[2]] = match[1]
    verified = {}
    for filename, digest in expected.items():
        ipk = source / filename
        if ipk.is_symlink() or hashlib.sha256(ipk.read_bytes()).hexdigest() != digest:
            raise ValueError('Invalid snapshot package: ' + filename)
        text, fields = shards.control(ipk)
        name = fields['Package']
        if (name not in PACKAGES or name in verified
                or fields['Version'] != PACKAGES[name][1]
                or fields['Architecture'] != 'arm_cortex-a9_neon'):
            raise ValueError('Unexpected snapshot package: ' + filename)
        verified[name] = (ipk, text)
    if set(verified) != set(PACKAGES):
        raise ValueError('Incomplete OpenVPN snapshot')

    plans = []
    for section in ('base', 'packages'):
        directory = output / section
        index = directory / 'Packages'
        if not index.is_file():
            raise ValueError('Missing feed index: ' + str(index))
        entries, remove = [], []
        for stanza in index.read_text().split('\n\n'):
            if not stanza.strip():
                continue
            lines = stanza.strip().splitlines()
            fields = dict(line.split(': ', 1) for line in lines if ': ' in line and not line[0].isspace())
            filename = fields['Filename']
            if Path(filename).name != filename or not filename.endswith('.ipk'):
                raise ValueError('Unsafe feed filename: ' + filename)
            ipk = directory / filename
            if ipk.is_symlink() or not ipk.is_file():
                raise ValueError('Missing or unsafe feed package: ' + str(ipk))
            name = fields['Package']
            if name in PACKAGES or name == 'openvpn-nossl':
                if name in PACKAGES:
                    version = fields['Version']
                    allowed = {PACKAGES[name][1]}
                    if name.startswith('openvpn-'):
                        allowed.add('2.4.5-4.2')
                    if section != PACKAGES[name][0] or version not in allowed:
                        raise ValueError('Refusing to replace unexpected version of ' + name)
                remove.append(ipk)
            else:
                text = '\n'.join(line for line in lines if line.split(':', 1)[0] not in TRANSPORT)
                entries.append((ipk, text))
        plans.append((section, directory, entries, remove))

    # Validate both sections and the complete snapshot before changing files.
    for section, directory, entries, remove in plans:
        for ipk in remove:
            ipk.unlink()
        for name, (ipk, text) in verified.items():
            if PACKAGES[name][0] == section:
                target = directory / ipk.name
                shutil.copyfile(ipk, target)
                entries.append((target, text))
        shards.write_index(directory, entries)
        (directory / 'Packages.manifest').write_bytes((directory / 'Packages').read_bytes())
        (directory / 'Packages.sig').unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--source', type=Path, default=ROOT / 'artifacts/openvpn-2.6.23')
    args = parser.parse_args()
    overlay(args.source, args.output)
    print('Applied four verified OpenVPN packages; preserved other feed entries')


if __name__ == '__main__':
    main()
