#!/usr/bin/env python3
"""Prepare an immutable optional OPKG feed from a verified targeted build."""
import argparse
import hashlib
import importlib.util
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('shards', ROOT / 'scripts/merge-userspace-shards.py')
shards = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shards)
NAME = re.compile(r'[a-z0-9][a-z0-9+.-]*\Z')


def prepare(source, output, names, repository):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('Invalid GitHub repository')
    if not names or len(names) != len(set(names)) or any(not NAME.fullmatch(n) for n in names):
        raise ValueError('Provide distinct exact package names')
    if any(n in ('gcc', 'kernel') or n.startswith('kmod-') for n in names):
        raise ValueError('Kernel packages and experimental native GCC need separate profiles')
    provenance = json.loads((source / 'source-run.json').read_text())
    if (not re.fullmatch(r'[0-9]+', str(provenance.get('run_id', '')))
            or not re.fullmatch(r'[0-9a-f]{40}', provenance.get('revision', ''))
            or provenance.get('workflow') != '.github/workflows/build-packages.yml'
            or provenance.get('url') != 'https://github.com/{}/actions/runs/{}'.format(repository, provenance['run_id'])):
        raise ValueError('Invalid verified build provenance')
    found = {}
    for ipk in sorted(source.rglob('*.ipk')):
        if ipk.is_symlink() or not ipk.resolve().is_relative_to(source.resolve()):
            raise ValueError('Package symlinks are not allowed')
        text, fields = shards.control(ipk)
        name = fields['Package']
        if name not in names:
            continue
        if name in found:
            raise ValueError('Multiple candidates for package ' + name)
        if not re.fullmatch(r'[A-Za-z0-9_.+~:-]+\.ipk', ipk.name):
            raise ValueError('Unsafe asset filename: ' + ipk.name)
        if fields['Architecture'] not in ('all', 'arm_cortex-a9_neon'):
            raise ValueError('Unexpected architecture: ' + fields['Architecture'])
        if set(fields) & {'Filename', 'Size', 'SHA256sum', 'MD5Sum'}:
            raise ValueError('Control metadata contains index transport fields')
        found[name] = (ipk, text, fields)
    missing = set(names) - set(found)
    if missing:
        raise ValueError('Missing requested packages: ' + ', '.join(sorted(missing)))
    if len(found) + 4 > 1000:
        raise ValueError('Feed exceeds the release asset count limit')
    records = []
    for name, (ipk, _, fields) in sorted(found.items()):
        if ipk.stat().st_size >= 2 * 1024 ** 3:
            raise ValueError('Package exceeds the release asset size limit')
        records.append(dict(package=name, version=fields['Version'], architecture=fields['Architecture'],
                            filename=ipk.name, sha256=hashlib.sha256(ipk.read_bytes()).hexdigest(),
                            size=ipk.stat().st_size))
    manifest = dict(repository=repository, source=provenance, packages=records)
    serialized = json.dumps(manifest, indent=2, sort_keys=True) + '\n'
    digest = hashlib.sha256(serialized.encode()).hexdigest()
    tag = 'extras-{}-{}'.format(provenance['run_id'], digest[:16])
    if output.exists():
        raise ValueError('Output directory must not already exist')
    output.mkdir(parents=True)
    entries = []
    for ipk, text, _ in found.values():
        target = output / ipk.name
        shutil.copyfile(ipk, target)
        entries.append((target, text))
    shards.write_index(output, entries)
    (output / 'source.json').write_text(serialized)
    files = sorted(output.iterdir())
    (output / 'SHA256SUMS').write_text(''.join('{}  {}\n'.format(
        hashlib.sha256(p.read_bytes()).hexdigest(), p.name) for p in files))
    return dict(tag=tag, url='https://github.com/{}/releases/download/{}'.format(repository, tag),
                packages=len(found), revision=provenance['revision'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--packages', nargs='+', required=True)
    parser.add_argument('--repository', required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.source, args.output, args.packages, args.repository), sort_keys=True))
    except (ValueError, OSError) as error:
        parser.exit(1, 'Release feed preparation failed: {}\n'.format(error))


if __name__ == '__main__':
    main()
