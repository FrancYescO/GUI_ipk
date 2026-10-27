#!/usr/bin/env python3
"""Inspect ARM ELF module metadata without a host cross toolchain."""
import struct
from pathlib import Path


def inspect(path):
    blob = Path(path).read_bytes()
    if blob[:6] != b'\x7fELF\x01\x01':
        raise ValueError('Expected little-endian ELF32')
    header = struct.unpack_from('<16sHHIIIIIHHHHHH', blob)
    if header[2] != 40:
        raise ValueError('Expected ARM ELF')
    sections = [struct.unpack_from('<10I', blob, header[6] + i * header[11])
                for i in range(header[12])]
    def contents(section):
        return blob[section[4]:section[4] + section[5]]
    def string(table, offset):
        return table[offset:].split(b'\0', 1)[0].decode('utf-8', errors='replace')
    section_names = contents(sections[header[13]])
    imports, metadata = [], {}
    for section in sections:
        if string(section_names, section[0]) == '.modinfo':
            for item in contents(section).split(b'\0'):
                if b'=' in item:
                    key, value = item.decode('utf-8', errors='replace').split('=', 1)
                    metadata[key] = value
        if section[1] == 2:
            strings = contents(sections[section[6]])
            for offset in range(section[4], section[4] + section[5], section[9]):
                name, _, _, info, _, index = struct.unpack_from('<IIIBBH', blob, offset)
                if index == 0 and info >> 4 == 1 and name:
                    imports.append(string(strings, name))
    return dict(metadata=metadata, undefined=sorted(set(imports)))
