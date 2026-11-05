#!/usr/bin/env python3
"""Verify imports against the pinned original firmware and private lab exports."""
import gzip
import hashlib
import json
from pathlib import Path
import sys

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'scripts'))
from firmware_kernel_candidates import INPUTS, elf_module, unresolved

root = Path(sys.argv[1])
source = json.loads((INPUTS / 'vbntk-2.4.5/source.json').read_text())
raw = (INPUTS / 'vbntk-2.4.5/stock-symbols.json.gz').read_bytes()
if hashlib.sha256(raw).hexdigest() != source['stock_symbols_sha256']:
    raise ValueError('Original firmware symbol checksum mismatch')
stock = json.loads(gzip.decompress(raw))
modules = [dict(elf_module(path.read_bytes()), file=path.name)
           for path in sorted(root.glob('*.ko')) if path.name != 'baseline-bcmspu.ko']
if len(modules) != 8:
    raise ValueError('Expected eight private lab/canary modules')
provided = stock['exports'] + [symbol for module in stock['stock_modules'] for symbol in module['exports']]
missing = unresolved(modules, provided)
if missing:
    raise ValueError('Unresolved lab imports: ' + ', '.join(missing))
report = {'original_image_sha256': source['image_sha256'], 'unresolved': [],
          'runtime_validation_performed': False,
          'modules': [{'file': m['file'], 'sha256':m['sha256']} for m in modules]}
(root / 'symbol-audit.json').write_text(json.dumps(report, indent=2) + '\n')
print('Verified imports for', len(modules), 'isolated lab modules')
