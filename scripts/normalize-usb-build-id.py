#!/usr/bin/env python
"""Normalize only GNU build-id when every other byte matches a pinned USB module."""
import argparse
import hashlib
import json
import os
import struct


def build_id_range(blob):
    if blob[:6] != b'\x7fELF\x01\x01':
        raise ValueError('Expected a 32-bit little-endian ELF module')
    header = struct.unpack_from('<16sHHIIIIIHHHHHH', blob)
    if header[2] != 40:
        raise ValueError('Expected an ARM module')
    offset, size, count, strings = header[6], header[11], header[12], header[13]
    rows = [struct.unpack_from('<IIIIIIIIII', blob, offset + i * size) for i in range(count)]
    row = rows[strings]
    names = blob[row[4]:row[4] + row[5]]
    matches = [row for row in rows if names[row[0]:].split(b'\0')[0] == b'.note.gnu.build-id']
    if len(matches) != 1:
        raise ValueError('Expected one GNU build-id section')
    row = matches[0]
    if row[4] + row[5] > len(blob):
        raise ValueError('Invalid build-id range')
    return row[4], row[5]


def normalize(path, reference, expected):
    with open(str(reference), 'rb') as stream:
        baseline = stream.read()
    with open(str(path), 'rb') as stream:
        actual = stream.read()
    if hashlib.sha256(baseline).hexdigest() != expected:
        raise ValueError('Reference differs from the runtime payload registry')
    if actual == baseline:
        return False
    offset, size = build_id_range(baseline)
    if build_id_range(actual) != (offset, size) or len(actual) != len(baseline):
        raise ValueError('ELF layout differs from the runtime-tested module')
    if actual[:offset] != baseline[:offset] or actual[offset + size:] != baseline[offset + size:]:
        raise ValueError('Module differs outside GNU build-id; refusing normalization')
    normalized = actual[:offset] + baseline[offset:offset + size] + actual[offset + size:]
    if hashlib.sha256(normalized).hexdigest() != expected:
        raise ValueError('Normalized payload differs from the runtime registry')
    with open(str(path), 'wb') as stream:
        stream.write(normalized)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory')
    parser.add_argument('references')
    parser.add_argument('registry')
    args = parser.parse_args()
    with open(args.registry) as stream:
        records = {m['name']: m['sha256'] for m in json.load(stream)['modules']}
    for name in ('cdc_ether', 'rndis_host'):
        changed = normalize(os.path.join(args.directory, name + '.ko'), os.path.join(args.references, name + '.ko'), records[name])
        print(name + ': ' + ('normalized GNU build-id only; all other bytes identical' if changed else 'exact runtime payload reproduced'))


if __name__ == '__main__':
    main()
