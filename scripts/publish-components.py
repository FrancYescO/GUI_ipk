#!/usr/bin/env python3
"""Idempotently publish complete immutable component Releases; never clobber assets."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time


def gh(*args):
    for attempt in range(8):
        result = subprocess.run(['gh', *args], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout
        message = result.stderr + result.stdout
        if not any(marker in message.lower() for marker in ('rate limit', 'secondary rate', 'http 429', 'http 502', 'http 503')):
            raise RuntimeError(message.strip())
        delay = min(60 * (attempt + 1), 300)
        print('GitHub requested backoff; retrying after {} seconds'.format(delay), flush=True)
        time.sleep(delay)
    raise RuntimeError('GitHub remained unavailable after bounded retries')


def release(repository, tag):
    # Query the listing so permission and network failures cannot be mistaken for a missing release.
    pages = json.loads(gh('api', '--paginate', '--slurp', 'repos/' + repository + '/releases?per_page=100'))
    return next((r for page in pages for r in page if r['tag_name'] == tag), None)


def assets(repository, identifier):
    pages = json.loads(gh('api', '--paginate', '--slurp', 'repos/{}/releases/{}/assets?per_page=100'.format(repository, identifier)))
    return {a['name']: a for page in pages for a in page}


def publish(directory, info, repository, revision):
    expected = {a['name']: a for a in info['assets']}
    if set(expected) != {p.name for p in directory.iterdir() if p.is_file()}:
        raise ValueError('Release directory differs from prepared asset manifest')
    for name, pin in expected.items():
        path = directory / name
        if path.stat().st_size != pin['size'] or hashlib.sha256(path.read_bytes()).hexdigest() != pin['sha256']:
            raise ValueError('Prepared asset changed: ' + name)
    state = release(repository, info['tag'])
    if state is None:
        gh('release', 'create', info['tag'], '--repo', repository, '--target', revision, '--draft', '--title', info['title'],
           '--notes', 'Verified OPKG component feed. Source: src/gz gui_component ' + info['url'] +
           '\nChecksums and provenance are included. Package bytes are not modified by publication.')
        state = release(repository, info['tag'])
    while True:
        current = assets(repository, state['id'])
        if set(current) - set(expected):
            raise ValueError('Existing release contains unexpected assets')
        for name, asset in current.items():
            if asset['size'] != expected[name]['size'] or asset.get('digest') != 'sha256:' + expected[name]['sha256']:
                raise ValueError('Refusing to overwrite differing asset: ' + name)
        missing = sorted(set(expected) - set(current))
        if not missing:
            break
        if not state['draft']:
            raise ValueError('Published immutable release is incomplete')
        batch = missing[:20]
        started = time.monotonic()
        result = subprocess.run(['gh', 'release', 'upload', info['tag'], '--repo', repository,
                                 *[str(directory / name) for name in batch]], capture_output=True, text=True)
        if result.returncode:
            message = result.stderr + result.stdout
            if any(m in message.lower() for m in ('rate limit', 'http 429', 'http 502', 'http 503', 'already exists')):
                print('Partial upload; preserving verified assets and retrying remaining files', flush=True)
                time.sleep(60)
                continue
            raise RuntimeError(message.strip())
        print('{}: {}/{} assets uploaded'.format(info['tag'], len(current) + len(batch), len(expected)), flush=True)
        # Keep content-generation requests below GitHub's documented per-minute threshold.
        if len(expected) > 40:
            time.sleep(max(0, len(batch) - (time.monotonic() - started)))
    if state['draft']:
        gh('release', 'edit', info['tag'], '--repo', repository, '--draft=false', '--latest=false')
    print('Verified public component:', info['url'], flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('publication', type=Path)
    parser.add_argument('--revision', required=True)
    args = parser.parse_args()
    catalog = json.loads((args.publication / 'catalog.json').read_text())
    for group, info in catalog['releases'].items():
        titles = {'kernel': 'Kernel modules by runtime ABI', 'asterisk20': 'Asterisk 20 OPKG feed',
                  'freeswitch-sounds': 'FreeSWITCH audio packages'}
        info['title'] = titles[group] + ' (' + info['tag'].rsplit('-', 1)[1] + ')'
        publish(args.publication / 'releases' / info['tag'], info, catalog['repository'], args.revision)


if __name__ == '__main__':
    main()
