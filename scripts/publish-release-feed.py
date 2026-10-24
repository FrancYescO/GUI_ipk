#!/usr/bin/env python3
"""Publish a prepared snapshot atomically; never replace existing release assets."""
import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path


def gh(*args):
    return subprocess.check_output(['gh', *args])


def publish(directory, metadata):
    info = json.loads(metadata.read_text())
    provenance = json.loads((directory / 'source.json').read_text())
    repository = provenance['repository']
    digest = hashlib.sha256((directory / 'source.json').read_bytes()).hexdigest()
    tag = 'extras-{}-{}'.format(provenance['source']['run_id'], digest[:16])
    if (not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository)
            or info['tag'] != tag or info['revision'] != provenance['source']['revision']
            or not re.fullmatch(r'[0-9a-f]{40}', info['revision'])
            or info['url'] != 'https://github.com/{}/releases/download/{}'.format(repository, tag)):
        raise ValueError('Snapshot metadata differs from build provenance')
    files = {p.name: p for p in directory.iterdir()}
    if any(p.is_symlink() or not p.is_file() for p in files.values()):
        raise ValueError('Snapshot must contain only regular files')
    expected = {}
    for line in (directory / 'SHA256SUMS').read_text().splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  ([A-Za-z0-9_.+~:-]+)', line)
        if not match or match[2] in expected:
            raise ValueError('Invalid snapshot checksum list')
        expected[match[2]] = match[1]
    if set(expected) != set(files) - {'SHA256SUMS'}:
        raise ValueError('Snapshot file list differs from checksums')
    for name, digest in expected.items():
        if hashlib.sha256(files[name].read_bytes()).hexdigest() != digest:
            raise ValueError('Snapshot checksum differs: ' + name)
    # Resolve existence through a successful listing: network/auth failures must not
    # be mistaken for a missing release.
    releases = json.loads(gh('api', '--paginate', '--slurp', 'repos/{}/releases?per_page=100'.format(repository)))
    matches = [r for page in releases for r in page if r['tag_name'] == tag]
    if matches:
        release = matches[0]
        if release['target_commitish'] != info['revision']:
            raise ValueError('Existing release points at another revision')
    else:
        gh('release', 'create', tag, '--repo', repository, '--target', info['revision'], '--draft',
           '--prerelease', '--title', 'Optional OPKG feed ' + tag,
           '--notes', 'Immutable optional feed snapshot. Build provenance and package hashes are attached.\n\n'
           'OPKG source: src/gz gui_extras ' + info['url'])
        release_id = json.loads(gh('release', 'view', tag, '--repo', repository, '--json', 'databaseId'))['databaseId']
        release = json.loads(gh('api', 'repos/{}/releases/{}'.format(repository, release_id)))
    assets = json.loads(gh('api', '--paginate', '--slurp', 'repos/{}/releases/{}/assets?per_page=100'.format(repository, release['id'])))
    assets = {a['name']: a for page in assets for a in page}
    if set(assets) - set(files):
        raise ValueError('Existing release contains unexpected assets')
    # Check every existing asset before uploading anything. Compare downloaded bytes
    # even on servers which do not expose an asset digest.
    with tempfile.TemporaryDirectory() as temporary:
        for name in sorted(assets):
            gh('release', 'download', tag, '--repo', repository, '--pattern', name, '--dir', temporary)
            if hashlib.sha256((Path(temporary) / name).read_bytes()).digest() != hashlib.sha256(files[name].read_bytes()).digest():
                raise ValueError('Refusing to overwrite differing release asset: ' + name)
    missing = set(files) - set(assets)
    if not release['draft'] and missing:
        raise ValueError('Published snapshots cannot be modified')
    # Draft assets stay invisible until the entire snapshot is present. Indexes last.
    for name in sorted(missing, key=lambda n: (not n.endswith('.ipk'), n)):
        gh('release', 'upload', tag, str(files[name]), '--repo', repository)
    if release['draft']:
        gh('release', 'edit', tag, '--repo', repository, '--draft=false', '--latest=false')
    return info['url']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('metadata', type=Path)
    args = parser.parse_args()
    print(publish(args.directory, args.metadata))


if __name__ == '__main__':
    main()
