#!/usr/bin/env python3
"""Check rebuilt modules against the exact payload registry (including untested candidates)."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('report', type=Path)
    args = parser.parse_args()
    records = {row['name']: row for row in json.loads(args.report.read_text())['modules']}
    checked = 0
    for path in args.directory.glob('*.ko'):
        record = records.get(path.stem)
        if record is None:  # compile-time ABI canary and optional test helpers
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
            raise SystemExit('Rebuilt payload differs from recorded payload: ' + path.name)
        checked += 1
    if checked == 0:
        raise SystemExit('No registered module payloads found')
    print(f'Verified {checked} exact payload hashes; runtime status remains as recorded')


if __name__ == '__main__':
    main()
