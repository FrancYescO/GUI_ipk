#!/usr/bin/env python3
"""Pin firmware IKCONFIG and exports from an RBI and its extracted stock tree.

The stock tree must be extracted on a case-sensitive filesystem. No router is
contacted. Encrypted RBI decoding additionally requires Python cryptography.
"""
import argparse
import gzip
import json
from pathlib import Path
from kernel_firmware import decrypt_rbi, elf_module, extract_config, kernel_exports, sha, unresolved


def write_gzip(path, data):
    with path.open('wb') as stream:
        with gzip.GzipFile(filename='', fileobj=stream, mode='wb', mtime=0) as output:
            output.write(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('stock_root', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--lzma-offset', type=lambda v: int(v, 0), action='append', required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a fresh output directory')
    raw = args.image.read_bytes()
    data, board = decrypt_rbi(raw) if args.image.suffix.lower() == '.rbi' else (raw, None)
    kernel, config, layers = extract_config(data, args.lzma_offset)
    exports = kernel_exports(kernel)
    modules = []
    for path in sorted((args.stock_root / 'lib/modules').rglob('*.ko')):
        module = elf_module(path.read_bytes())
        module.pop('symbol_sizes')
        modules.append(dict(module, path=str(path.relative_to(args.stock_root)), name=path.stem))
    if len(modules) < 100:
        raise ValueError('Incomplete stock module input')
    vermagic = {module['modinfo']['vermagic'][0].strip() for module in modules}
    if len(vermagic) != 1:
        raise ValueError('Stock modules have different vermagic values')
    missing = unresolved(modules, exports['exports'])
    if missing:
        raise ValueError('Stock symbol closure failed: ' + ', '.join(missing))
    control = (args.stock_root / 'usr/lib/opkg/info/kernel.control').read_text()
    version = next(line[9:] for line in control.splitlines() if line.startswith('Version: '))
    firmware = (args.stock_root / 'etc/config/version').read_text()
    args.output.mkdir(parents=True)
    write_gzip(args.output / 'kernel.config.gz', config)
    symbols = dict(exports, stock_modules=modules, unresolved_stock=[])
    write_gzip(args.output / 'stock-symbols.json.gz', (json.dumps(symbols, sort_keys=True) + '\n').encode())
    metadata = {'image': args.image.name, 'image_sha256': sha(raw), 'board': board,
                'decrypted_sha256': sha(data), 'layers': layers, 'config_sha256': sha(config),
                'kernel_package': version, 'stock_module_count': len(modules),
                'kernel_export_count': len(exports['exports']), 'base_address': exports['base_address'],
                'vermagic': vermagic.pop(),
                'stock_symbols_sha256': sha((args.output / 'stock-symbols.json.gz').read_bytes()),
                'firmware_version_file': firmware, 'runtime_validated': False}
    (args.output / 'source.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(args.image.name, board, len(modules), 'stock modules; complete symbol closure; config', sha(config))


if __name__ == '__main__':
    main()
