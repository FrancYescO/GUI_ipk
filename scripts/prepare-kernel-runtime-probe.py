#!/usr/bin/env python3
"""Prepare a private 4.1.38 modem validation bundle; never connect or install."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
from network_kmods_4138 import ROOT, CORE, load


def prepare(profile, output, boot_id):
    if output.exists():
        raise ValueError('Output must be fresh')
    output.mkdir(parents=True)
    report = json.loads((ROOT / 'build' / (profile + '-4.1.38/runtime-validation/results.json')).read_text())
    for name in ('probe.sh', 'functional.sh', 'run.sh'):
        shutil.copyfile(ROOT / 'scripts/kernel-validation' / name, output / name)
    (output / 'boot-id').write_text(boot_id + '\n')
    (output / 'kernel-package').write_text(report['kernel_package'] + '\n')
    (output / 'modules').mkdir()
    rows = [r for r in report['modules'] if r['name'] not in CORE]
    for row in rows:
        source = ROOT / 'artifacts' / (profile + '-4.1.38-network') / row['asset']
        with tarfile.open(source) as outer:
            with tarfile.open(fileobj=outer.extractfile('./data.tar.gz')) as data:
                blob = data.extractfile('./lib/modules/4.1.38/' + row['name'] + '.ko').read()
        if hashlib.sha256(blob).hexdigest() != row['sha256']:
            raise ValueError('Probe payload mismatch')
        (output / 'modules' / (row['sha256'] + '.ko')).write_bytes(blob)
    (output / 'plan.tsv').write_text(''.join(r['name'] + '\t' + r['sha256'] + '\tnamespace\n' for r in rows))
    (output / 'pilot.tsv').write_text(''.join(r['name'] + '\t' + r['sha256'] + '\tnamespace\n' for r in rows if r['name'] in ('act_connmark', 'act_skbedit', 'cls_flow', 'em_u32')))
    if profile == 'vbnts':
        (output / 'em-u32-smoke-only').write_text('Native and profile-specific cls_basic unavailable; namespace validation only.\n')
    fetch = load('fetch-publication-inputs')
    catalog = fetch.read_catalog(ROOT / 'build/publication/bootstrap.json.gz', live=False)
    for package in ('tc', 'libmnl'):
        pin = next(r for r in catalog['records'] if r['package'] == package)
        source = fetch.retrieve(pin, output / 'cache' if (output / 'cache').exists() else make_cache(output), [pin['download_url']])
        with tarfile.open(source) as outer:
            with tarfile.open(fileobj=outer.extractfile('./data.tar.gz')) as data:
                for member in data:
                    if not member.isfile():
                        continue
                    if member.name.endswith('/sbin/tc'):
                        blob = data.extractfile(member).read()
                        if b'/etc/iproute2' not in blob:
                            raise ValueError('Unexpected tc configuration path')
                        blob = blob.replace(b'/etc/iproute2', b'/tmp/kv38maps')
                        path = output / 'bin/tc'
                    elif '/lib/libmnl.so.' in member.name:
                        blob = data.extractfile(member).read()
                        path = output / 'lib' / Path(member.name).name
                    else:
                        continue
                    path.parent.mkdir(exist_ok=True)
                    path.write_bytes(blob)
                    path.chmod(0o755 if package == 'tc' else 0o644)
    library = next((output / 'lib').glob('libmnl.so.*'))
    (output / 'lib/libmnl.so.0').symlink_to(library.name)
    (output / 'ematch_map').write_text('3 u32\n')
    shutil.rmtree(output / 'cache')
    print('Prepared 44 network probes; the five previously validated core modules are not replaced by this batch')


def make_cache(output):
    path = output / 'cache'
    path.mkdir()
    return path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile', choices=['vbnto', 'vbnts'])
    parser.add_argument('output', type=Path)
    parser.add_argument('--boot-id', required=True, help='Current /proc/sys/kernel/random/boot_id read from the target modem')
    args = parser.parse_args()
    prepare(args.profile, args.output, args.boot_id)
