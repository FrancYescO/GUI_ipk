#!/usr/bin/env python3
"""Stage pinned repository bundles; candidate feeds do not depend on Releases."""
import argparse
import json
from pathlib import Path
import hashlib
import io
import tarfile


def download(root, repository):
    repo = Path(__file__).resolve().parents[1]
    source = repo / 'build/kernel-candidates/sources.json'
    for profile, record in json.loads(source.read_text()).items():
        destination = root / profile
        destination.mkdir(parents=True, exist_ok=True)
        data = (repo / record['bundle']).read_bytes()
        if hashlib.sha256(data).hexdigest() != record['bundle_sha256']:
            raise ValueError('Pinned candidate bundle checksum mismatch')
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
            for member in archive:
                path = Path(member.name)
                if not member.isfile() or path.is_absolute() or '..' in path.parts:
                    raise ValueError('Unexpected bundle member: ' + member.name)
                output = destination / path
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(archive.extractfile(member).read())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--repository', default='FrancYescO/GUI_ipk')
    args = parser.parse_args()
    download(args.destination, args.repository)


if __name__ == '__main__':
    main()
