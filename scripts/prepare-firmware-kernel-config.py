#!/usr/bin/env python3
"""Apply firmware-specific configuration differences to the proven SDK base."""
import argparse
import gzip
import json
from pathlib import Path
from kernel_firmware import config_options

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ROOT / 'build/kernel-firmware-profiles'


def prepare(profile):
    definitions = json.loads((PROFILES / 'profiles.json').read_text())
    entry = definitions[profile]
    reference = config_options(gzip.decompress((ROOT / 'build/vbntj/kernel-4.1.52-runtime.config.gz').read_bytes()))
    target = config_options(gzip.decompress((PROFILES / entry['config_input'] / 'kernel.config.gz').read_bytes()))
    base = config_options((ROOT / 'build/vbntj/kernel-4.1.52-damson.config').read_bytes())
    changes = {key: target.get(key) for key in reference.keys() | target.keys()
               if reference.get(key) != target.get(key)}
    for key, value in changes.items():
        if value is None:
            base.pop(key, None)
        else:
            base[key] = value
    for key, value in entry['required_options'].items():
        if base.get(key) != value:
            raise ValueError('Model configuration mismatch: ' + key)
    return ''.join('# ' + key + ' is not set\n' if value == 'n' else key + '=' + value + '\n'
                   for key, value in sorted(base.items())), changes


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile')
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    config, changes = prepare(args.profile)
    args.output.write_text(config)
    print('Applied', len(changes), 'firmware-specific option differences to the SDK-adapted base')
