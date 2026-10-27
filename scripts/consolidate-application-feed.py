#!/usr/bin/env python3
"""Combine pinned application IPKs without changing packages or losing provenance."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('shards', ROOT / 'scripts/merge-userspace-shards.py')
shards = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shards)


def consolidate(source, output, manifest):
    if output.exists():
        raise ValueError('Output must not already exist')
    previous = source / 'source.json'
    previous = json.loads(previous.read_text()) if previous.is_file() else {}
    originals = {}
    for group, info in manifest['groups'].items():
        name = info['former_tag']
        if Path(name).name != name:
            raise ValueError('Unsafe snapshot path')
        path = source / name / 'source.json'
        text = path.read_text() if path.is_file() else previous.get('original_source_manifests', {}).get(group)
        if not text or hashlib.sha256(text.encode()).hexdigest() != info['source_manifest_sha256']:
            raise ValueError('Source provenance mismatch: ' + group)
        originals[group] = text
    verified, names = [], set()
    for record in manifest['packages']:
        filename = record['filename']
        if Path(filename).name != filename:
            raise ValueError('Unsafe package path')
        group = record['group']
        nested = source / manifest['groups'][group]['former_tag'] / filename
        ipk = nested if nested.is_file() else source / filename
        if ipk.is_symlink() or ipk.stat().st_size != record['size'] or hashlib.sha256(ipk.read_bytes()).hexdigest() != record['sha256']:
            raise ValueError('Package differs from pinned snapshot: ' + filename)
        text, fields = shards.control(ipk)
        for field, key in [('Package', 'package'), ('Version', 'version'), ('Architecture', 'architecture')]:
            if fields[field] != record[key]:
                raise ValueError('Package metadata mismatch: ' + filename)
        if fields['Package'] in names or fields['Package'].startswith('kmod-') or fields['Package'] in ('kernel', 'gcc'):
            raise ValueError('Duplicate or non-application package')
        names.add(fields['Package'])
        declared = json.loads(originals[group])['packages']
        if not any(r['filename'] == filename and r['sha256'] == record['sha256'] for r in declared):
            raise ValueError('Package missing from original provenance')
        verified.append((ipk, text))
    output.mkdir(parents=True)
    entries = []
    for ipk, text in verified:
        destination = output / ipk.name
        shutil.copyfile(ipk, destination)
        entries.append((destination, text))
    shards.write_index(output, entries)
    provenance = {'format_version': 3, 'manifest': manifest, 'original_source_manifests': originals}
    (output / 'source.json').write_text(json.dumps(provenance, indent=2, sort_keys=True) + '\n')
    sums = [hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name for p in sorted(output.iterdir())]
    (output / 'SHA256SUMS').write_text('\n'.join(sums) + '\n')
    return len(entries)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'build/application-archive/manifest.json')
    args = parser.parse_args()
    print('Consolidated {} unchanged IPKs'.format(consolidate(args.source, args.output, json.loads(args.manifest.read_text()))))


if __name__ == '__main__':
    main()
