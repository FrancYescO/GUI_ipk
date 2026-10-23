#!/usr/bin/env python3
"""Report declared dependency gaps without assuming vendor-installed packages."""
import argparse
import csv
import gzip
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

FEEDS = ('base', 'luci', 'packages', 'routing', 'telephony', 'target/packages')
TERM = re.compile(r'^([A-Za-z0-9+_.-]+)(?:\s*\((>=|<=|>>|<<|=|>|<)\s*([^()]+)\))?$')


def stanzas(text):
    for block in text.split('\n\n'):
        fields = {}
        previous = None
        for line in block.splitlines():
            if line[:1].isspace() and previous:
                fields[previous] += ' ' + line.strip()
            elif ': ' in line:
                previous, value = line.split(': ', 1)
                fields[previous] = value
        if fields.get('Package'):
            yield fields


def term(value, provided=False):
    if provided:
        inline = re.fullmatch(r'([A-Za-z0-9+_.-]+)=([^\s(),]+)', value.strip())
        if inline:
            return inline.group(1), '=', inline.group(2)
    match = TERM.fullmatch(value.strip())
    if not match:
        raise ValueError('Unrecognized dependency or provider: ' + value)
    return match.groups()



def exact_version_available(name, operator, required, candidates):
    if operator not in ('=', '>=', '<='):
        return False
    for package, version, _, declaration in candidates:
        actual = version if package == name else None
        if declaration and package != name:
            _, provided_operator, provided_version = term(declaration, provided=True)
            if provided_operator == '=':
                actual = provided_version
        if actual == required:
            return True
    return False


def audit(root, extra_feeds=()):
    sections = list(FEEDS)
    for extra in extra_feeds:
        path = Path(extra)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('Extra feed must be a relative path inside the feed root')
        if extra not in sections:
            sections.append(extra)
    entries = []
    indexes = []
    providers = defaultdict(set)
    for section in sections:
        directory = root / section
        index = directory / 'Packages'
        compressed = directory / 'Packages.gz'
        if index.is_file():
            text = index.read_text(encoding='utf-8')
        elif compressed.is_file():
            with gzip.open(str(compressed), 'rt', encoding='utf-8') as stream:
                text = stream.read()
        elif section in extra_feeds:
            raise ValueError('Requested extra feed has no index: ' + section)
        else:
            continue
        indexes.append(section)
        for fields in stanzas(text):
            if not fields.get('Version'):
                raise ValueError('Package version missing: ' + fields['Package'])
            fields = dict(fields, feed=section)
            entries.append(fields)
            provider = (fields['Package'], fields['Version'], section)
            providers[fields['Package']].add(provider + ('',))
            for declaration in fields.get('Provides', '').split(','):
                if declaration.strip():
                    providers[term(declaration, provided=True)[0]].add(provider + (declaration.strip(),))
    if not indexes:
        raise ValueError('No OPKG indexes found')
    counts = Counter()
    missing = defaultdict(set)
    issues = []
    for package in entries:
        for group in package.get('Depends', '').split(','):
            if not group.strip():
                continue
            choices = [term(choice) for choice in group.split('|')]
            matches = sorted({provider for name, _, _ in choices for provider in providers[name]})
            if any(providers[name] and not operator for name, operator, _ in choices):
                status = 'name-available'
            elif any(exact_version_available(name, operator, required, providers[name])
                     for name, operator, required in choices):
                status = 'exact-version-available'
            elif matches:
                status = 'version-check-required'
            elif all(name == 'kernel' or name.startswith('kmod-') for name, _, _ in choices):
                status = 'unresolved-kernel'
            else:
                status = 'unresolved-userspace'
            counts[status] += 1
            if status in ('name-available', 'exact-version-available'):
                continue
            if status.startswith('unresolved'):
                missing[group.strip()].add(package['Package'])
            issues.append(dict(package=package['Package'], version=package['Version'],
                               feed=package['feed'], dependency=group.strip(), status=status,
                               providers=';'.join('{}={} [{}]'.format(*p[:3]) + (' Provides: ' + p[3] if p[3] else '') for p in matches)))
    issues.sort(key=lambda row: (row['status'], row['dependency'], row['package'], row['feed']))
    summary = dict(indexes=indexes, package_records=len(entries),
                   dependency_groups=sum(counts.values()), statuses=dict(sorted(counts.items())),
                   missing=[dict(dependency=name, affected_packages=len(names), packages=sorted(names))
                            for name, names in sorted(missing.items(), key=lambda pair: (-len(pair[1]), pair[0]))])
    return issues, summary


def write(output, issues, summary):
    output.mkdir(parents=True, exist_ok=True)
    with (output / 'dependency-issues.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, ['package', 'version', 'feed', 'dependency', 'status', 'providers'])
        writer.writeheader()
        writer.writerows(issues)
    (output / 'dependency-summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    lines = ['# Declared feed dependency audit', '',
             'Indexes: ' + ', '.join('`' + name + '`' for name in summary['indexes']), '',
             '| Result | Dependency groups |', '|---|---:|']
    lines += ['| {} | {} |'.format(name, count) for name, count in summary['statuses'].items()]
    lines += ['', '`dependency-issues.csv` contains unresolved dependencies and version checks only.', '',
              'Availability checks exact names and explicit OPKG providers. Identical explicit versions satisfy =, >= and <= constraints. Other version comparisons remain for review; package and declared provider versions are shown. This is not a runtime or ELF-symbol check.', '',
              'Missing modules may be installed by vendor firmware, but this audit does not assume that. Kernel profiles are audited separately; indexes from the other kernel version are not consulted.', '',
              '| Missing dependency | Affected package names |', '|---|---:|']
    lines += ['| {} | {} |'.format(row['dependency'].replace('|', '\\|'), row['affected_packages'])
              for row in summary['missing']]
    (output / 'dependency-report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('feed', type=Path)
    parser.add_argument('--extra-feed', action='append', default=[])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        issues, summary = audit(args.feed, args.extra_feed)
        write(args.output, issues, summary)
        print(json.dumps(dict(package_records=summary['package_records'], statuses=summary['statuses']), sort_keys=True))
    except (ValueError, OSError, csv.Error) as error:
        parser.exit(1, 'Dependency audit failed: {}\n'.format(error))


if __name__ == '__main__':
    main()
