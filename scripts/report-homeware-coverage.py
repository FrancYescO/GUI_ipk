#!/usr/bin/env python3
"""Compare built OPKG indexes with the recorded Homeware 18/19 inventory."""
import argparse
import csv
import gzip
import json
from collections import Counter
from pathlib import Path
from urllib.parse import quote

FEEDS = ('base', 'luci', 'packages', 'routing', 'telephony', 'target/packages')
SOURCES = {
    '18': 'https://repository.macoers.com/homeware/18/brcm63xx-tch/VANTW/',
    '19': 'https://repository.macoers.com/homeware/19/brcm6xxx-tch/VANTW/',
}


def stanzas(text):
    for paragraph in text.split('\n\n'):
        fields = {}
        for line in paragraph.splitlines():
            if line and not line[0].isspace() and ': ' in line:
                key, value = line.split(': ', 1)
                fields[key] = value
        if fields:
            yield fields


def inventory(catalog):
    with catalog.open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    if not rows:
        raise ValueError('Homeware catalog is empty')
    seen = set()
    for row in rows:
        version, section = row['homeware'], row['section']
        if version not in SOURCES or section not in FEEDS + ('freifunk',):
            raise ValueError('Invalid catalog source: {!r}'.format(row))
        for field in ('name', 'version', 'architecture'):
            if not row[field] or '/' in row[field] or '\n' in row[field]:
                raise ValueError('Invalid catalog field: {!r}'.format(row))
        key = tuple(row[k] for k in ('homeware', 'section', 'name', 'version', 'architecture'))
        if key in seen:
            raise ValueError('Duplicate Homeware catalog row: {!r}'.format(key))
        seen.add(key)
    return rows


def compare(catalog, feed, metadata=None, config=None):
    expected = inventory(catalog)
    built = {}
    indexes = 0
    for section in FEEDS:
        index = feed / section / 'Packages'
        compressed = feed / section / 'Packages.gz'
        if index.is_file():
            text = index.read_text(encoding='utf-8')
        elif compressed.is_file():
            with gzip.open(str(compressed), 'rt', encoding='utf-8') as stream:
                text = stream.read()
        else:
            continue
        indexes += 1
        for entry in stanzas(text):
            if entry.get('Package') and entry.get('Version'):
                built.setdefault(entry['Package'], set()).add(entry['Version'])
    if not indexes:
        raise ValueError('No OPKG indexes found under {}'.format(feed))
    recipes = {}
    if metadata:
        source = ''
        for line in metadata.read_text(encoding='utf-8').splitlines():
            if line.startswith('Source-Makefile: '):
                source = line.split(': ', 1)[1]
            elif line.startswith('Package: '):
                recipes[line.split(': ', 1)[1]] = source
    selected = None
    if config:
        selected = set()
        for line in config.read_text(encoding='utf-8').splitlines():
            if line.startswith('CONFIG_PACKAGE_') and line.endswith(('=y', '=m')):
                selected.add(line[len('CONFIG_PACKAGE_'):-2])
    results = []
    for row in expected:
        row = dict(row)
        name = row['name']
        versions = built.get(name, set())
        if versions:
            status = 'present'
        elif metadata and name not in recipes:
            status = 'no-recipe'
        elif selected is not None and name not in selected:
            status = 'not-selected'
        elif metadata:
            status = 'not-built'
        else:
            status = 'missing'
        row.update(status=status, built_versions=';'.join(sorted(versions)),
                   recipe=recipes.get(name, ''))
        filename = '{}_{}_{}.ipk'.format(name, row['version'], row['architecture'])
        row['source_url'] = SOURCES[row['homeware']] + row['section'] + '/' + quote(filename)
        results.append(row)
    summaries = []
    for version in SOURCES:
        rows = [row for row in results if row['homeware'] == version]
        by_name = {row['name']: row['status'] for row in rows}
        counts = Counter(by_name.values())
        summaries.append(dict(homeware=version, names=len(by_name),
                              present=counts['present'], missing=len(by_name)-counts['present'],
                              statuses=dict(sorted(counts.items()))))
    return results, dict(indexes_read=indexes, built_names=len(built), versions=summaries)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('catalog', type=Path)
    parser.add_argument('feed', type=Path)
    parser.add_argument('--metadata', type=Path)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.config and not args.metadata:
        parser.error('--config requires --metadata')
    try:
        rows, summary = compare(args.catalog, args.feed, args.metadata, args.config)
        output = args.output or args.feed
        output.mkdir(parents=True, exist_ok=True)
        fields = ['homeware', 'section', 'name', 'version', 'architecture', 'status',
                  'built_versions', 'recipe', 'source_url']
        with (output / 'homeware-coverage.csv').open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fields)
            writer.writeheader()
            writer.writerows(rows)
        (output / 'homeware-coverage.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
        lines = ['# Homeware package coverage', '',
                 'Baseline: public directory listings recorded on 2026-10-22. Presence is compared by exact package name across the six userspace feeds.', '',
                 '| Homeware | Distinct names | Present | Missing |', '|---|---:|---:|---:|']
        for item in summary['versions']:
            lines.append('| {homeware} | {names} | {present} | {missing} |'.format(**item))
        lines += ['', 'See `homeware-coverage.csv` for every package, source link and built version.', '',
                  'Presence does not establish ABI, dependency or runtime compatibility. Different ABI package names remain distinct; versions are recorded without ranking them.',
                  'Catalog entries come from IPK filenames, not their internal control metadata. Homeware 18/19 are source labels, not verified kernel ABI declarations.', '',
                  'When metadata is supplied, `no-recipe`, `not-selected` and `not-built` distinguish remaining work. No missing package is silently considered integrated.', '']
        (output / 'homeware-coverage.md').write_text('\n'.join(lines), encoding='utf-8')
        print(json.dumps(summary, sort_keys=True))
    except (OSError, ValueError, KeyError, csv.Error) as error:
        parser.exit(1, 'Homeware coverage failed: {}\n'.format(error))


if __name__ == '__main__':
    main()
