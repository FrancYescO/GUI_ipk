#!/usr/bin/env python3
"""Restore pinned staged-module releases and publish optional OPKG indexes."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import tarfile

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / 'build/kernel-candidates/sources.json'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def checksums(path):
    result = {}
    for line in path.read_text().splitlines():
        sha, name = line.split()
        if Path(name).name != name or name in result or len(sha) != 64:
            raise ValueError('Invalid pinned checksum manifest')
        result[name] = sha
    return result


def tar_files(data):
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        files = {}
        for member in archive:
            if member.isdir():
                continue
            if not member.isfile() or member.name in files:
                raise ValueError('Unexpected archive member: ' + member.name)
            files[member.name] = archive.extractfile(member).read()
        return files


def verify_ipk(ipk, expected, source, profile, modules):
    raw = ipk.read_bytes()
    if digest(raw) != expected:
        raise ValueError('IPK differs from pinned release: ' + ipk.name)
    outer = tar_files(raw)
    if set(outer) != {'./debian-binary', './control.tar.gz', './data.tar.gz'}:
        raise ValueError('Unexpected IPK structure')
    if outer['./debian-binary'] != b'2.0\n':
        raise ValueError('Invalid package format')
    control = tar_files(outer['./control.tar.gz'])
    if set(control) != {'./control'}:
        raise ValueError('Candidate must not contain installation scripts')
    fields = dict(line.split(': ', 1) for line in control['./control'].decode().splitlines())
    required = {
        'Architecture': 'arm_cortex-a9', 'Version': '4.1.38-1',
        'Depends': 'kernel (= ' + source['kernel_package'] + ')',
        'X-Manual-Install-Only': 'yes', 'X-Runtime-Validated': 'no',
        'X-Module-Staging-Only': 'yes',
        'X-Kernel-Vermagic': '4.1.38 SMP preempt mod_unload ARMv7',
    }
    if any(fields.get(k) != v for k, v in required.items()):
        raise ValueError('Candidate profile/ABI guard mismatch: ' + ipk.name)
    if fields.get('Package', '') + '_4.1.38-1_arm_cortex-a9.ipk' != ipk.name:
        raise ValueError('Unexpected package filename')
    suffix = ('-vbnts' if profile == 'vbnts' else '') + '-4.1.38-candidate'
    if not fields['Package'].startswith('kmod-') or not fields['Package'].endswith(suffix):
        raise ValueError('Unexpected candidate package name')
    payloads = tar_files(outer['./data.tar.gz'])
    if len(payloads) != 1:
        raise ValueError('Expected one staged module')
    name, payload = next(iter(payloads.items()))
    prefix = './usr/lib/kernel-module-candidates/' + ('4.1.38-vbnts' if profile == 'vbnts' else '4.1.38') + '/'
    if not name.startswith(prefix) or '/' in name[len(prefix):] or not name.endswith('.ko'):
        raise ValueError('Candidate must stay outside the boot module path')
    stem = name[len(prefix):-3]
    if stem == 'xt_nat' or fields.get('X-Module-Path') != name[1:]:
        raise ValueError('Quarantined module or incorrect staging path')
    if modules.get(stem) != digest(payload):
        raise ValueError('Module differs from build manifest')
    return fields, stem, digest(payload)


def restore(profile, source, downloads, work):
    archive = downloads / profile / source['archive']
    if digest(archive.read_bytes()) != source['archive_sha256']:
        raise ValueError('Module archive differs from pinned release: ' + profile)
    work.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, 'r:gz') as tar:
        manifest = tar.extractfile('modules.json').read()
        report = tar.extractfile('BUILD-REPORT.md').read()
    (work / 'modules.json').write_bytes(manifest)
    (work / 'BUILD-REPORT.md').write_bytes(report)
    packages = downloads / profile / 'ipks'
    expected = checksums(ROOT / 'build/kernel-candidates' / (profile + '.sha256'))
    if set(expected) != {p.name for p in packages.glob('*.ipk')}:
        raise ValueError('Downloaded package set differs from pinned release')
    output = work / 'ipks'
    output.mkdir(exist_ok=True)
    for stale in output.glob('*.ipk'):
        stale.unlink()
    for name in expected:
        shutil.copyfile(packages / name, output / name)
    return json.loads(manifest)


def write_feed(profile, source, work, manifest, destination):
    expected = checksums(ROOT / 'build/kernel-candidates' / (profile + '.sha256'))
    if len(expected) != source['package_count'] or set(expected) != {p.name for p in (work / 'ipks').glob('*.ipk')}:
        raise ValueError('Restored package set differs from pinned release')
    modules = {m['name']: m['sha256'] for m in manifest['modules']}
    validated = {}
    if profile == 'vbnto':
        report = json.loads((ROOT / 'build/vbnto-4.1.38/validation/results.json').read_text())
        validated = {(m['name'], m['sha256']): m for m in report['modules']}
    entries, files = [], []
    for filename, sha in sorted(expected.items()):
        ipk = work / 'ipks' / filename
        fields, name, module_sha = verify_ipk(ipk, sha, source, profile, modules)
        record = validated.get((name, module_sha), {})
        if record.get('status', '').startswith('blocked'):
            raise ValueError('Quarantined validation result: ' + name)
        fields.update({'Filename': filename, 'Size': str(ipk.stat().st_size),
                       'SHA256sum': sha, 'X-Module-SHA256': module_sha,
                       'X-Feed-Profile': profile,
                       'X-Runtime-Test': record.get('level', 'build-only'),
                       'X-Runtime-Test-Status': record.get('status', 'not_tested')})
        entries.append('\n'.join(k + ': ' + v for k, v in fields.items()))
        files.append(ipk)
    # Validate the entire set before replacing an existing feed.
    destination.mkdir(parents=True, exist_ok=True)
    for stale in destination.glob('*.ipk'):
        stale.unlink()
    for ipk in files:
        shutil.copyfile(ipk, destination / ipk.name)
    data = ('\n\n'.join(entries) + '\n\n').encode()
    (destination / 'Packages').write_bytes(data)
    (destination / 'Packages.manifest').write_bytes(data)
    with (destination / 'Packages.gz').open('wb') as output:
        with gzip.GzipFile(filename='', mode='wb', fileobj=output, mtime=0) as zipped:
            zipped.write(data)
    shutil.copyfile(work / 'modules.json', destination / 'modules.json')
    shutil.copyfile(work / 'BUILD-REPORT.md', destination / 'BUILD-REPORT.md')
    shutil.copyfile(ROOT / 'build/kernel-candidates' / (profile + '.sha256'), destination / 'SHA256SUMS')
    print('Published {} staged candidates in {}'.format(len(files), destination))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('downloads', type=Path)
    parser.add_argument('work', type=Path)
    parser.add_argument('feed_root', type=Path)
    args = parser.parse_args()
    for profile, source in json.loads(SOURCES.read_text()).items():
        work = args.work / profile
        manifest = restore(profile, source, args.downloads, work)
        write_feed(profile, source, work, manifest, args.feed_root / source['feed'])


if __name__ == '__main__':
    main()
