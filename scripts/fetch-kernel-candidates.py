#!/usr/bin/env python3
"""Download the pinned public candidate releases for subsequent verification."""
import argparse
import json
from pathlib import Path
import subprocess


def download(root, repository):
    source = Path(__file__).resolve().parents[1] / 'build/kernel-candidates/sources.json'
    for profile, record in json.loads(source.read_text()).items():
        destination = root / profile
        destination.mkdir(parents=True, exist_ok=True)
        subprocess.run(['gh', 'release', 'download', record['tag'], '--repo', repository,
                        '--pattern', record['archive'], '--dir', str(destination)], check=True)
        subprocess.run(['gh', 'release', 'download', record['tag'], '--repo', repository,
                        '--pattern', '*.ipk', '--dir', str(destination / 'ipks')], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--repository', default='FrancYescO/GUI_ipk')
    args = parser.parse_args()
    download(args.destination, args.repository)


if __name__ == '__main__':
    main()
