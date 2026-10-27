"""Reproduce manual network IPKs from pinned candidates and exact-device results."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
CORE = {'tun', 'wireguard', 'bcmspu', 'cdc_ether', 'rndis_host'}


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expected(profile, candidates):
    config = load('package-vbnto-4.1.38').profile_config(profile)
    archive = load('package-vbnto-4.1.38').archive
    report = json.loads((ROOT / 'build' / (profile + '-4.1.38/runtime-validation/results.json')).read_text())
    reference = json.loads((ROOT / 'build/vbntj/validation/results.json').read_text())
    names = {r['name'] for r in reference['modules'] if r.get('asset')}
    if report['kernel_package'] != config['KERNEL'] or {r['name'] for r in report['modules']} != names or len(names) != 49:
        raise ValueError('Runtime target set or exact ABI differs from reference')
    if not all(report['audit'].values()) or report['taint_before'] != report['taint_after']:
        raise ValueError('Restoration audit failed')
    result = {}
    for row in report['modules']:
        name = row['name']
        if name in CORE:
            continue
        if name == 'xt_nat' or row['status'] not in ('passed', 'skip_busy') or row['restore_exit'] != 0:
            raise ValueError('Unverified or quarantined network module: ' + name)
        path = candidates / row['source_asset']
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['source_ipk_sha256']:
            raise ValueError('Candidate input checksum mismatch')
        with tarfile.open(path) as outer:
            with tarfile.open(fileobj=outer.extractfile('./data.tar.gz')) as data:
                members = [m for m in data if m.isfile()]
                if len(members) != 1 or Path(members[0].name).name != name + '.ko':
                    raise ValueError('Unexpected candidate module payload')
                payload = data.extractfile(members[0]).read()
        if hashlib.sha256(payload).hexdigest() != row['sha256']:
            raise ValueError('Candidate differs from runtime evidence')
        if payload[:6] != b'\x7fELF\x01\x01' or payload[18:20] != b'\x28\x00' or ('vermagic=' + config['VERMAGIC']).encode() not in payload:
            raise ValueError('Wrong module architecture or vermagic')
        package = 'kmod-' + name.lower().replace('_', '-') + '-' + profile + '-4.1.38-manual'
        fields = {'Package': package, 'Version': '4.1.38-1', 'Architecture': 'arm_cortex-a9',
                  'Depends': 'kernel (= ' + config['KERNEL'] + ')', 'Section': 'kernel',
                  'Priority': 'optional', 'Maintainer': 'GUI_ipk',
                  'Description': 'Manual-only ' + name + ' module for ' + config['TARGET'] + '; see per-module validation',
                  'X-Target': config['TARGET'], 'X-Firmware': config['FIRMWARE'],
                  'X-Kernel-Profile': '4.1.38-' + profile, 'X-Kernel-Vermagic': config['VERMAGIC'],
                  'X-Manual-Install-Only': 'yes', 'X-Module-SHA256': row['sha256'],
                  'X-Source-Candidate-SHA256': row['source_ipk_sha256'],
                  'X-Runtime-Test': row['level'], 'X-Runtime-Test-Status': row['status'],
                  'X-Runtime-Test-Report': 'https://francyesco.github.io/GUI_ipk/validation/4.1.38-' + profile + '/'}
        dependencies = [part[8:].decode() for part in payload.split(b'\0') if part.startswith(b'depends=')]
        if dependencies and dependencies[0]:
            fields['X-Required-Loaded-Modules'] = dependencies[0]
        control = ''.join(k + ': ' + v + '\n' for k, v in fields.items()).encode()
        result[package + '_4.1.38-1_arm_cortex-a9.ipk'] = archive([
            ('debian-binary', b'2.0\n', 0o644),
            ('control.tar.gz', archive([('control', control, 0o644)]), 0o644),
            ('data.tar.gz', archive([('lib/modules/4.1.38/' + name + '.ko', payload, 0o644)]), 0o644)])
    if len(result) != 44:
        raise ValueError('Expected 44 additional network packages')
    return result


def materialize(profile, candidates, destination, verify=False):
    packages = expected(profile, candidates)
    sums = ''.join(hashlib.sha256(blob).hexdigest() + '  ' + name + '\n' for name, blob in sorted(packages.items()))
    if verify:
        if {p.name for p in destination.glob('*.ipk')} != set(packages):
            raise ValueError('Network package set mismatch')
        for name, blob in packages.items():
            if (destination / name).read_bytes() != blob:
                raise ValueError('Non-reproducible network package: ' + name)
        if (destination / 'SHA256SUMS').read_text() != sums:
            raise ValueError('Network checksum manifest mismatch')
    else:
        destination.mkdir(parents=True, exist_ok=True)
        if any(destination.iterdir()):
            raise ValueError('Output must be empty')
        for name, blob in packages.items():
            (destination / name).write_bytes(blob)
        (destination / 'SHA256SUMS').write_text(sums)
    print(('Verified' if verify else 'Packaged'), len(packages), 'exact-ABI network modules for', profile)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('profile', choices=['vbnto', 'vbnts'])
    p.add_argument('candidates', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--verify', action='store_true')
    a = p.parse_args()
    materialize(a.profile, a.candidates, a.output, a.verify)
