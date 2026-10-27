#!/usr/bin/env python3
"""Record every compiled candidate and incomplete vendor build diagnostics."""
import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    for stage in ('priority', 'wireguard', 'full', 'links', 'subtrees'):
        parser.add_argument('--' + stage + '-exit', type=int, required=True)
    args = parser.parse_args()
    cross = os.environ['CROSS_COMPILE']
    modules = []
    for path in sorted((args.root / 'modules').rglob('*.ko')):
        info = subprocess.check_output([cross + 'readelf', '-p', '.modinfo', str(path)],
                                       universal_newlines=True, encoding='utf-8', errors='replace')
        if not re.search(r'vermagic=4\.1\.38 SMP preempt mod_unload ARMv7\s', info):
            raise ValueError('Wrong candidate vermagic: ' + str(path))
        undefined = subprocess.check_output([cross + 'nm', '--undefined-only', str(path)],
                                            universal_newlines=True, encoding='utf-8', errors='replace')
        defined = subprocess.check_output([cross + 'nm', '--defined-only', str(path)],
                                          universal_newlines=True, encoding='utf-8', errors='replace')
        modules.append(dict(
            name=path.stem, path=str(path.relative_to(args.root)),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            undefined=sorted(line.split()[-1] for line in undefined.splitlines() if line.split()),
            exports=sorted(line.split()[-1][10:] for line in defined.splitlines()
                           if line.split() and line.split()[-1].startswith('__ksymtab_')),
        ))
    missing = [target for target in (args.root / 'priority-targets.txt').read_text().splitlines()
               if not (args.root / 'modules' / target).is_file()]
    summary = dict(module_count=len(modules), runtime_validated=False,
                   priority_exit=args.priority_exit, wireguard_exit=args.wireguard_exit,
                   full_exit=args.full_exit, missing_priority=missing, modules=modules)
    summary['runtime_profile'] = os.environ.get('RUNTIME_PROFILE', 'vbnto')
    summary['links_exit'] = args.links_exit
    summary['subtrees_exit'] = args.subtrees_exit
    (args.root / 'modules.json').write_text(json.dumps(summary, indent=2) + '\n')
    lines = ['# Linux 4.1.38 candidate module build', '',
             'Runtime profile: ' + summary['runtime_profile'], '',
             'Compiled modules: {}'.format(len(modules)),
             'Priority build exit: {}'.format(args.priority_exit),
             'WireGuard build exit: {}'.format(args.wireguard_exit),
             'Full build exit: {}'.format(args.full_exit),
             'Individual module links exit: {}'.format(args.links_exit), '',
             'Independent subtree builds exit: {}'.format(args.subtrees_exit), '',
             'These candidates have not been runtime validated. IPKs stage modules outside the boot module path.', '',
             '## Compiled modules', '']
    lines.extend('- `{}`'.format(module['path']) for module in modules)
    if missing:
        lines.extend(['', '## Missing priority modules', ''] + ['- ' + name for name in missing])
    (args.root / 'BUILD-REPORT.md').write_text('\n'.join(lines) + '\n')
    with (args.root / 'SHA256SUMS').open('w') as output:
        for module in modules:
            output.write(module['sha256'] + '  ' + module['path'] + '\n')
    print('Compiled {} candidate modules; {} priority modules missing'.format(len(modules), len(missing)))


if __name__ == '__main__':
    main()
