#!/usr/bin/env python3
"""Apply verified targeted-build IPKs to an already assembled userspace feed."""
import argparse
import gzip
import hashlib
import importlib.util
import io
import json
import shutil
import tarfile
from pathlib import Path

FEEDS = ('base', 'luci', 'packages', 'routing', 'telephony', 'target/packages')


def fields(text):
    result = {}
    for line in text.splitlines():
        if line and not line[0].isspace() and ': ' in line:
            key, value = line.split(': ', 1)
            if key in result:
                raise ValueError('Duplicate package field: ' + key)
            result[key] = value
    return result


def filename(entry):
    for key in ('Package', 'Version', 'Architecture'):
        if not entry.get(key) or any(c in entry[key] for c in '/\\\r\n\0'):
            raise ValueError('Invalid package ' + key)
    return '{Package}_{Version}_{Architecture}.ipk'.format(**entry)


def control(package):
    with tarfile.open(str(package), 'r:*') as archive:
        controls = [m for m in archive if m.name.lstrip('./') == 'control.tar.gz' and m.isfile()]
        if len(controls) != 1:
            raise ValueError('Expected one control archive: ' + str(package))
        with tarfile.open(fileobj=io.BytesIO(archive.extractfile(controls[0]).read()), mode='r:gz') as nested:
            members = [m for m in nested if m.name.lstrip('./') == 'control' and m.isfile()]
            if len(members) != 1:
                raise ValueError('Expected one control file: ' + str(package))
            text = nested.extractfile(members[0]).read().decode('utf-8').rstrip('\n')
    entry = fields(text)
    if package.name != filename(entry):
        raise ValueError('Filename differs from control: ' + str(package))
    if entry['Architecture'] not in ('all', 'arm_cortex-a9_neon'):
        raise ValueError('Unexpected repair architecture: ' + entry['Architecture'])
    if entry['Package'] == 'kernel' or entry['Package'].startswith('kmod-'):
        raise ValueError('Kernel IPKs cannot be userspace repairs')
    if any(key in entry for key in ('Filename', 'Size', 'SHA256sum')):
        raise ValueError('Control contains reserved index fields')
    return text, entry


def sha256(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def merge(feed, repairs):
    indexes = {}
    for section in FEEDS:
        path = feed / section / 'Packages'
        entries = []
        if path.is_file():
            for stanza in path.read_text(encoding='utf-8').strip().split('\n\n'):
                if not stanza:
                    continue
                entry = fields(stanza)
                if entry.get('Filename') != filename(entry) or not (path.parent / entry['Filename']).is_file():
                    raise ValueError('Invalid baseline index: ' + str(path))
                entries.append((stanza, entry))
        indexes[section] = entries
    if not any(indexes.values()):
        raise ValueError('No baseline userspace indexes')
    spec = importlib.util.spec_from_file_location('payload_check', Path(__file__).with_name('check-userspace-payloads.py'))
    payload_check = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(payload_check)
    payload_check.check_payloads(repairs)
    candidates = {}
    provenance = []
    for directory in sorted(p for p in repairs.iterdir() if p.is_dir()):
        if (directory / 'shard-manifest.json').exists():
            raise ValueError('Expected targeted output, not a full shard: ' + str(directory))
        failure = directory / 'failed-packages.txt'
        if failure.is_file() and failure.read_text().strip():
            raise ValueError('Repair output reports failed packages: ' + str(directory))
        source = directory / 'source-run.json'
        if source.is_file():
            provenance.append(json.loads(source.read_text()))
        for package in sorted(directory.rglob('*.ipk')):
            if package.is_symlink():
                raise ValueError('Symlink in repair output: ' + str(package))
            section = package.relative_to(directory).parent.as_posix()
            if section not in FEEDS:
                raise ValueError('Unexpected repair section: ' + str(package))
            text, entry = control(package)
            name = entry['Package']
            if name in candidates:
                previous = candidates[name][3]
                if (previous['Version'], previous['Architecture']) != (entry['Version'], entry['Architecture']):
                    raise ValueError('Conflicting repair versions or architectures: ' + name)
            candidates[name] = (section, package, text, entry)
    if not candidates:
        raise ValueError('No targeted IPKs to merge')
    for entries in indexes.values():
        for stanza, old_entry in entries:
            if old_entry['Package'] in candidates:
                replacement = candidates[old_entry['Package']][3]
                if (old_entry['Version'], old_entry['Architecture']) != (replacement['Version'], replacement['Architecture']):
                    raise ValueError('Repair changes an existing version or architecture: ' + old_entry['Package'])
    # Validate every repair before replacing any baseline files.
    changes = []
    for name, (section, source, text, entry) in sorted(candidates.items()):
        destination = feed / section / source.name
        old_versions = set()
        for old_section in FEEDS:
            retained = []
            for stanza, old_entry in indexes[old_section]:
                if old_entry['Package'] == name:
                    old_versions.add(old_entry['Version'])
                    old_path = feed / old_section / old_entry['Filename']
                    if old_path != destination:
                        old_path.unlink()
                else:
                    retained.append((stanza, old_entry))
            indexes[old_section] = retained
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        stanza = text + '\nFilename: {}\nSize: {}\nSHA256sum: {}'.format(source.name, destination.stat().st_size, sha256(destination))
        indexes[section].append((stanza, fields(stanza)))
        changes.append(dict(package=name, section=section, version=entry['Version'],
                            previous_versions=sorted(old_versions)))
    for section, entries in indexes.items():
        if not entries and not (feed / section / 'Packages').is_file():
            continue
        directory = feed / section
        directory.mkdir(parents=True, exist_ok=True)
        text = '\n\n'.join(stanza for stanza, entry in sorted(entries, key=lambda pair: pair[1]['Package'])) + '\n\n'
        (directory / 'Packages').write_text(text, encoding='utf-8')
        with (directory / 'Packages.gz').open('wb') as stream:
            with gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0) as compressed:
                compressed.write(text.encode())
        # These supplemental indexes describe the old files and must not persist.
        for stale in ('Packages.manifest', 'Packages.sig'):
            if (directory / stale).exists():
                (directory / stale).unlink()
    result = dict(repaired_packages=changes, source_runs=provenance)
    (feed / 'repairs-report.json').write_text(json.dumps(result, indent=2) + '\n')
    lines = ['# Targeted build repairs', '', 'Updated {} userspace package names.'.format(len(changes)), '',
             '| Package | Version | Previous version |', '|---|---|---|']
    lines.extend('| {} | {} | {} |'.format(row['package'], row['version'], ', '.join(row['previous_versions']) or 'new') for row in changes)
    (feed / 'repairs-report.md').write_text('\n'.join(lines) + '\n')
    print('Applied {} targeted userspace packages'.format(len(changes)))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('feed', type=Path)
    parser.add_argument('repairs', type=Path)
    args = parser.parse_args()
    try:
        merge(args.feed, args.repairs)
    except (OSError, ValueError, tarfile.TarError, StopIteration) as error:
        parser.exit(1, 'Userspace repair merge failed: {}\n'.format(error))


if __name__ == '__main__':
    main()
