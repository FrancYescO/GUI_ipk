"""Offline firmware configuration and ARM module checks (standard library only)."""
import gzip
import hashlib
import lzma
import re
import struct


def decrypt_rbi(data):
    """Decode the public Technicolor RBI envelope for the supported ARM boards.

    Keys and envelope format are from FrancYescO/tch_firmware_extracted main.py.
    Callers pin the complete original RBI's SHA256; envelope decoding alone is
    not firmware authenticity verification.
    """
    keys = {
        'VBNT-K': 'ffd56a4e3a21401bf1798b3cd8ad54d238ba80039623bba08b6d50b8ec73f7b4',
        'VBNT-S': '0ef34d972945869ef40f89873fed30269020e107685c097751bef9479d75d620',
        'VBNT-O': '916aeb569d8cbf8cfaf060aec533d43a9ef0acb3138f8351c4112674212975a5',
        'VCNT-3': 'afe6a928efd1d5824cca03cf6f9cd7796fcbe9a746aa7120792b666fc2c3ebb6',
    }
    if len(data) < 0x144:
        raise ValueError('Truncated RBI')
    board = data[0x13c:0x142].decode('ascii')
    if board not in keys:
        raise ValueError('Unsupported RBI board: ' + board)
    offset = struct.unpack_from('>H', data, 0x2a)[0]
    if offset < 0x144 or offset >= len(data):
        raise ValueError('Invalid RBI payload offset')
    data = data[offset:]

    def decrypt(key, iv, payload):
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        decoder = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        result = decoder.update(payload) + decoder.finalize()
        padding = result[-1]
        if not 1 <= padding <= 16 or result[-padding:] != bytes([padding]) * padding:
            raise ValueError('Invalid RBI padding')
        return result[:-padding]

    for _ in range(16):
        if len(data) < 6:
            raise ValueError('Truncated RBI layer')
        kind = data[0]
        if kind == 0xb0:
            return data[6:], board
        if kind == 0xb8:
            data = data[42:]
        elif kind == 0xb4:
            import zlib
            decoder = zlib.decompressobj()
            data = decoder.decompress(data[10:], 128 * 1024**2)
            if not decoder.eof:
                raise ValueError('Incomplete or oversized RBI layer')
        elif kind == 0xb7:
            data = data[10:]
            key = decrypt(bytes.fromhex(keys[board]), data[:16], data[16:64])
            data = decrypt(key, data[64:80], data[80:])
        else:
            raise ValueError('Unsupported RBI envelope type')
    raise ValueError('Too many RBI layers')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def config_options(data):
    options = {}
    for line in data.decode().splitlines():
        if line.startswith('CONFIG_') and '=' in line:
            key, value = line.split('=', 1)
        elif line.startswith('# CONFIG_') and line.endswith(' is not set'):
            key, value = line[2:-len(' is not set')], 'n'
        else:
            continue
        if key in options:
            raise ValueError('Duplicate configuration option: ' + key)
        options[key] = value
    if not options:
        raise ValueError('Empty configuration')
    return options


def extract_config(data, offsets):
    trace = []
    for offset in offsets:
        if not 0 <= offset < len(data):
            raise ValueError('Invalid LZMA offset')
        decoder = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
        data = decoder.decompress(data[offset:], max_length=128 * 1024**2)
        if not decoder.eof:
            raise ValueError('Incomplete or oversized kernel layer')
        trace.append({'offset': offset, 'size': len(data), 'sha256': sha(data)})
    start = data.find(b'IKCFG_ST')
    if start < 0 or data.find(b'IKCFG_ST', start + 8) >= 0:
        raise ValueError('Expected one IKCONFIG start marker')
    end = data.find(b'IKCFG_ED', start + 8)
    if end < 0:
        raise ValueError('Missing IKCONFIG end marker')
    config = gzip.decompress(data[start + 8:end])
    config_options(config)
    return data, config, trace


def elf_module(data):
    """Read an ELF32 little-endian ARM relocatable object without host binutils."""
    if len(data) < 52 or data[:7] != b'\x7fELF\x01\x01\x01':
        raise ValueError('Expected ELF32 little-endian module')
    kind, machine = struct.unpack_from('<HH', data, 16)
    if kind != 1 or machine != 40:
        raise ValueError('Expected relocatable ARM module')
    offset = struct.unpack_from('<I', data, 32)[0]
    step, count, names = struct.unpack_from('<HHH', data, 46)
    if step != 40 or not count or names >= count or offset + step * count > len(data):
        raise ValueError('Invalid ELF section table')
    sections = [struct.unpack_from('<10I', data, offset + i * step) for i in range(count)]

    def contents(section):
        pos, size = section[4:6]
        if pos + size > len(data):
            raise ValueError('Truncated ELF section')
        return data[pos:pos + size]

    def string(table, pos):
        if not 0 <= pos < len(table):
            raise ValueError('Invalid ELF string offset')
        end = table.find(b'\0', pos)
        if end < 0:
            raise ValueError('Unterminated ELF string')
        return table[pos:end].decode('ascii')

    labels = contents(sections[names])
    imports, weak, exports, sizes, info = set(), set(), set(), {}, {}
    for section in sections:
        label = string(labels, section[0])
        if label == '.modinfo':
            for entry in contents(section).split(b'\0'):
                if b'=' in entry:
                    key, value = entry.decode().split('=', 1)
                    info.setdefault(key, []).append(value)
        if section[1] != 2:
            continue
        if section[6] >= count or section[9] != 16 or section[5] % 16:
            raise ValueError('Invalid ELF symbol table')
        symbols, strings = contents(section), contents(sections[section[6]])
        for pos in range(0, len(symbols), 16):
            name, value, size, binding, other, index = struct.unpack_from('<IIIBBH', symbols, pos)
            name = string(strings, name)
            if not name:
                continue
            if index == 0 and binding >> 4 in (1, 2):
                (weak if binding >> 4 == 2 else imports).add(name)
            elif name.startswith('__ksymtab_'):
                exports.add(name[len('__ksymtab_'):])
            if index and size:
                sizes[name] = size
    if len(info.get('vermagic', [])) != 1:
        raise ValueError('Missing or ambiguous module vermagic')
    return {'sha256': sha(data), 'imports': sorted(imports), 'weak_imports': sorted(weak),
            'exports': sorted(exports), 'symbol_sizes': sizes, 'modinfo': info}


def kernel_exports(data):
    """Locate ARM32 absolute export tables; require independent anchor agreement.

    No kallsyms assumptions: Technicolor's uncompressed kallsyms variant is not
    supported by common vmlinux converters. Every symbol in a long consecutive
    {value, name} table must point inside this image. Callers additionally check
    that these exports and stock-module exports resolve the stock modules.
    """
    words = struct.unpack('<' + 'I' * (len(data) // 4), data[:len(data) // 4 * 4])
    candidates = None
    for anchor in (b'kfree', b'printk', b'__kmalloc', b'schedule'):
        positions, cursor = [], 0
        while True:
            cursor = data.find(b'\0' + anchor + b'\0', cursor)
            if cursor < 0:
                break
            positions.append(cursor + 1)
            cursor += len(anchor) + 2
        bases = {word - pos for pos in positions for word in words
                 if 0x80000000 <= word - pos <= 0xffff0000 and (word - pos) % 4096 == 0}
        candidates = bases if candidates is None else candidates & bases
    if len(candidates or []) != 1:
        raise ValueError('Ambiguous kernel image base')
    base = candidates.pop()

    def symbol(address):
        pos = address - base
        if not 0 <= pos < len(data):
            return None
        end = data.find(b'\0', pos, pos + 160)
        if end < 0:
            return None
        name = data[pos:end]
        return name.decode() if re.fullmatch(rb'[A-Za-z_][A-Za-z_0-9]{0,150}', name) else None

    runs = []
    for parity in (0, 1):
        run = []
        for i in range(parity, len(words) - 1, 2):
            value, address = words[i:i + 2]
            name = symbol(address) if base <= value < base + len(data) + 64 * 1024**2 else None
            if name:
                run.append(name)
            else:
                if len(run) >= 128:
                    runs.append(run)
                run = []
        if len(run) >= 128:
            runs.append(run)
    exports = set(name for run in runs for name in run)
    if not {'kfree', 'printk', '__kmalloc', 'schedule'} <= exports:
        raise ValueError('Kernel export anchors missing')
    return {'base_address': hex(base), 'exports': sorted(exports),
            'table_run_lengths': [len(run) for run in runs], 'kernel_sha256': sha(data)}


def unresolved(modules, kernel):
    provided = set(kernel) | {s for module in modules for s in module['exports']}
    return sorted({s for module in modules for s in module['imports'] if s not in provided})
