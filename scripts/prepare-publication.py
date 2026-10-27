#!/usr/bin/env python3
import argparse
from pathlib import Path
from publication_layout import prepare

parser = argparse.ArgumentParser(description='Preserve all userspace updates; move coherent optional components to Releases.')
parser.add_argument('userspace', type=Path)
parser.add_argument('applications', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
catalog = prepare(args.userspace, args.applications, args.output)
print('Prepared', len(catalog['records']), 'packages;', sum(r['storage'] == 'pages' for r in catalog['records']), 'on Pages')
