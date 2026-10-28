"""Deterministic, additive cryptodev packages; never replace a stock driver."""
import gzip
import json
from pathlib import Path
from firmware_kernel_candidates import archive, files
from kernel_firmware import elf_module, sha, unresolved

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build/cryptodev'
SOURCE = '08644db02d43478f802755903212f5ee506af73b'
SOURCE_SHA256 = 'e795acb85118f1f39f0155df8fd28a3d79de7d1240b91bdf8cc9e2a1747d2642'


def definitions():
    return json.loads((BUILD / 'profiles.json').read_text())


def audit(profile, payload):
    entry = definitions()[profile]
    module = elf_module(payload)
    if module['modinfo']['vermagic'][0].strip() != entry['vermagic']:
        raise ValueError('cryptodev vermagic mismatch: ' + profile)
    checks = []
    if entry.get('export_input'):
        raw = (BUILD / entry['export_input']).read_bytes()
        exports = json.loads(gzip.decompress(raw))
        checks.append({'input': entry['export_input'], 'sha256': sha(raw)})
        if unresolved([module], exports):
            raise ValueError('Unresolved cryptodev imports: ' + repr(unresolved([module], exports)))
    for name in entry.get('stock_inputs', []):
        directory = ROOT / 'build/kernel-firmware-profiles' / name
        provenance = json.loads((directory / 'source.json').read_text())
        raw = (directory / 'stock-symbols.json.gz').read_bytes()
        if sha(raw) != provenance['stock_symbols_sha256'] or entry['kernel_package'] != provenance['kernel_package']:
            raise ValueError('Original firmware input changed')
        stock = json.loads(gzip.decompress(raw))
        exports = stock['exports'] + [s for m in stock['stock_modules'] for s in m['exports']]
        missing = unresolved([module], exports)
        if missing:
            raise ValueError('Unresolved cryptodev imports: ' + repr(missing))
        checks.append({'input': name, 'sha256': sha(raw)})
    return {'module_sha256': sha(payload), 'vermagic': entry['vermagic'], 'symbol_checks': checks,
            'unresolved_symbols': [], 'runtime_validated': entry['runtime_validated']}


def package(profile, directory, output):
    entry = definitions()[profile]
    payload = (directory / 'cryptodev.ko').read_bytes()
    report = audit(profile, payload)
    candidate = entry.get('candidate', False)
    name = 'kmod-cryptodev-' + profile + ('-candidate' if candidate else '')
    filename = name + '_1.14-1_' + entry['architecture'] + '.ipk'
    staged = 'usr/lib/kernel-module-candidates/' + profile + '/cryptodev.ko'
    control = (f'Package: {name}\nVersion: 1.14-1\nArchitecture: {entry["architecture"]}\n'
               f'Depends: kernel (= {entry["kernel_package"]})\nSection: kernel\nMaintainer: GUI_ipk\n'
               'Description: Synchronous cryptodev 1.14 with bounded page ownership; manual load, privileged access only\n'
               'X-Manual-Install-Only: yes\nX-Offline-Symbol-Check: passed\n'
               f'X-Runtime-Validated: {"yes" if entry["runtime_validated"] else "no"}\n'
               f'X-Kernel-Profile: {profile}\nX-Kernel-Vermagic: {entry["vermagic"]}\n'
               f'X-Module-Path: /{staged}\n')
    if candidate:
        control += 'X-Module-Staging-Only: yes\n'
    blob = archive({'./debian-binary': b'2.0\n', './control.tar.gz': archive({'./control': control.encode()}),
                    './data.tar.gz': archive({'./' + staged: payload})})
    output.mkdir(parents=True, exist_ok=True)
    (output / filename).write_bytes(blob)
    report.update(profile=profile, asset=filename, ipk_sha256=sha(blob), control=control,
                  source_commit=SOURCE, source_sha256=SOURCE_SHA256,
                  patch_sha256=sha((ROOT / 'patches/cryptodev/001-page-ownership-and-bounds.patch').read_bytes()))
    (output / 'manifest.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    return report


def publication_records():
    from publication_layout import record
    rows = []
    for profile, entry in definitions().items():
        directory = ROOT / 'artifacts/cryptodev' / profile
        manifest = json.loads((directory / 'manifest.json').read_text())
        path = directory / manifest['asset']
        if sha(path.read_bytes()) != manifest['ipk_sha256']:
            raise ValueError('cryptodev package checksum mismatch')
        payloads = files(files(path.read_bytes())['./data.tar.gz'])
        payload, = payloads.values()
        report = audit(profile, payload)
        if report['module_sha256'] != manifest['module_sha256']:
            raise ValueError('cryptodev payload checksum mismatch')
        if manifest['patch_sha256'] != sha((ROOT / 'patches/cryptodev/001-page-ownership-and-bounds.patch').read_bytes()):
            raise ValueError('cryptodev patch changed without rebuilding')
        stanza = (manifest['control'] + 'Filename: ' + path.name + '\nSize: ' + str(path.stat().st_size) + '\nSHA256sum: ' + manifest['ipk_sha256'])
        rows.append(record(path, stanza, entry['feed'], 'kernel', profile))
    return rows


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile', choices=definitions())
    parser.add_argument('modules', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    report = package(args.profile, args.modules, args.output)
    if args.verify:
        expected = json.loads((ROOT / 'artifacts/cryptodev' / args.profile / 'manifest.json').read_text())
        if report['ipk_sha256'] != expected['ipk_sha256']:
            raise SystemExit('cryptodev IPK differs from committed build')
    print(json.dumps(report, indent=2))
