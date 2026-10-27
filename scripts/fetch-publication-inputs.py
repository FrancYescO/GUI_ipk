#!/usr/bin/env python3
"""Reconstruct verified userspace inputs from durable published data, not expiring artifacts."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import urllib.error
import urllib.request
from publication_layout import ROOT, SITE, SECTIONS, write_index


def allowed(url):
    return url.startswith(SITE + '/') or url.startswith('https://github.com/FrancYescO/GUI_ipk/releases/download/')


def retrieve(pin, cache, urls):
    digest = pin['sha256']
    if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        raise ValueError('Invalid package digest')
    target = cache / digest
    if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == digest:
        return target
    errors = []
    for url in dict.fromkeys(urls):
        if not allowed(url):
            raise ValueError('Untrusted publication URL: ' + url)
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url, timeout=120) as response:
                    data = response.read()
                if len(data) != pin['size'] or hashlib.sha256(data).hexdigest() != digest:
                    raise ValueError('Published package checksum mismatch')
                target.write_bytes(data)
                return target
            except (OSError, ValueError) as error:
                errors.append(str(error))
                if isinstance(error, urllib.error.HTTPError) and error.code in (403, 404):
                    break
    raise RuntimeError('Unable to retrieve verified package ' + pin['filename'] + ': ' + '; '.join(errors[-3:]))


def read_catalog(bootstrap, live=True):
    if live:
        try:
            with urllib.request.urlopen(SITE + '/publication.json.gz', timeout=60) as response:
                raw = response.read(16 * 1024 * 1024)
            catalog = json.loads(gzip.decompress(raw))
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
            catalog = json.loads(gzip.decompress(bootstrap.read_bytes()))
    else:
        catalog = json.loads(gzip.decompress(bootstrap.read_bytes()))
    if catalog.get('format_version') != 1 or catalog.get('repository') != 'FrancYescO/GUI_ipk':
        raise ValueError('Unsupported publication catalog')
    return catalog


def stage(catalog, output, cache, applications):
    cache.mkdir(parents=True, exist_ok=True)
    records = [r for r in catalog['records'] if r['kind'] == 'userspace']
    for record in records:
        if record['section'] not in SECTIONS or Path(record['filename']).name != record['filename']:
            raise ValueError('Unsafe publication path')
    def fetch(record):
        path = retrieve(record, cache, [record['download_url'], record['origin_url']])
        destination = output / record['section'] / record['filename']
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        return record
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(fetch, r) for r in records]
        for count, future in enumerate(as_completed(futures), 1):
            future.result()
            if count % 250 == 0:
                print('Verified userspace inputs:', count, '/', len(records), flush=True)
    for section in SECTIONS:
        write_index(output / section, [r for r in records if r['section'] == section])
    pins = json.loads((ROOT / 'build/application-archive/manifest.json').read_text())
    applications.mkdir(parents=True, exist_ok=True)
    for pin in pins['packages']:
        path = retrieve(pin, cache, [pin['url']])
        shutil.copyfile(path, applications / pin['filename'])
    print('Reconstructed', len(records), 'verified userspace IPKs and all promoted updates')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('applications', type=Path)
    parser.add_argument('cache', type=Path)
    parser.add_argument('--bootstrap', type=Path, default=ROOT / 'build/publication/bootstrap.json.gz')
    parser.add_argument('--bootstrap-only', action='store_true')
    args = parser.parse_args()
    stage(read_catalog(args.bootstrap, not args.bootstrap_only), args.output, args.cache, args.applications)


if __name__ == '__main__':
    main()
