"""Add complete OPKG capabilities to installable modules and verified builtins.

Staging-only modules never satisfy ordinary application dependencies. Legacy
package contents are used as a naming/grouping reference, never as payloads.
"""
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import shlex
import tarfile

from cryptodev_packages import definitions
from firmware_kernel_candidates import archive
from kernel_firmware import config_options, elf_module

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build/kernel-opkg-providers'
POLICY = '1'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def unpack(blob):
    with tarfile.open(fileobj=io.BytesIO(blob), mode='r:*') as source:
        result = {}
        for member in source:
            if member.isfile():
                name = member.name.removeprefix('./') if hasattr(str, 'removeprefix') else member.name.lstrip('./')
                if name.startswith('/') or '..' in Path(name).parts or name in result:
                    raise ValueError('Unsafe IPK entry')
                result[name] = source.extractfile(member).read()
        return result


def fields(control):
    return dict(line.split(': ', 1) for line in control.splitlines() if ': ' in line and not line[0].isspace())


def add(field, values):
    return ', '.join(sorted(set(filter(None, [v.strip() for v in field.split(',')] + list(values)))))


def upgraded(version):
    match = re.fullmatch(r'(.+)-(\d+)', version)
    if not match:
        raise ValueError('Unrecognized module package revision: ' + version)
    return match[1] + '-' + str(int(match[2]) + 1)


def config(profile):
    if profile.startswith('4.1.38-'):
        internal = 'vbnts' if profile.endswith('vbntk') else 'vbnto'
        path = ROOT / ('build/' + internal + '-4.1.38/kernel.config.gz')
    elif profile == '4.1.52-vbntk':
        path = ROOT / 'build/vbntj/kernel-4.1.52-runtime.config.gz'
    else:
        firmware = json.loads((ROOT / 'build/kernel-firmware-profiles/profiles.json').read_text())[profile]
        path = ROOT / 'build/kernel-firmware-profiles' / firmware['config_input'] / 'kernel.config.gz'
    raw = gzip.decompress(path.read_bytes())
    return config_options(raw), sha(raw)


def guard(kernel, replacements, stock_dependencies=None):
    """No module loading/unloading, dependency bypass or generic file overwrite."""
    q = shlex.quote
    binding = q('kernel (= ' + kernel + ')')
    script = '''#!/bin/sh
set -eu
[ -z "${IPKG_INSTROOT:-}" ] || exit 0
installed=$(opkg status kernel 2>/dev/null | sed -n 's/^Version: //p')
[ "$installed" = EXPECTED_KERNEL ] || { echo 'Kernel ABI mismatch; refusing module installation' >&2; exit 1; }
'''.replace('EXPECTED_KERNEL', q(kernel))
    for package in sorted(stock_dependencies or []):
        script += f'''metadata=$(opkg status {q(package)} 2>/dev/null || true)
printf '%s\\n' "$metadata" | grep -q '^Status:.* installed' &&\nprintf '%s\\n' "$metadata" | grep -F -- {binding} >/dev/null || {{ echo 'Missing exact-ABI firmware dependency: {package}' >&2; exit 1; }}
'''
    for generic, modules in sorted(replacements.items()):
        script += f'''metadata=$(opkg status {q(generic)} 2>/dev/null || true)
if printf '%s\\n' "$metadata" | grep -q '^Status:.* installed' &&
   ! printf '%s\\n' "$metadata" | grep -F -- {binding} >/dev/null; then
'''
        for module in sorted(modules):
            script += f'''  if [ -d {q('/sys/module/' + module.replace('-', '_'))} ]; then
    echo 'Legacy {generic} has active module {module}; quiesce and validate it before migration' >&2
    exit 1
  fi
'''
        script += 'fi\n'
    return script.encode()


def data_archive(contents):
    # Firmware opkg does not create missing parent directories while extracting.
    # Include every directory explicitly, before any child file.
    output = io.BytesIO()
    directories = set()
    for name in contents:
        directories.update(str(p) for p in Path(name).parents if str(p) != '.')
    with gzip.GzipFile(fileobj=output, mode='wb', filename='', mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode='w') as tar:
            for name in sorted(directories, key=lambda p: (len(Path(p).parts), p)):
                info = tarfile.TarInfo('./' + name + '/')
                info.type, info.mode = tarfile.DIRTYPE, 0o755
                tar.addfile(info)
            for name, blob in sorted(contents.items()):
                info = tarfile.TarInfo('./' + name)
                info.size, info.mode = len(blob), 0o644
                tar.addfile(info, io.BytesIO(blob))
    return output.getvalue()


def control_archive(contents):
    # Maintainer scripts must be executable. All timestamps/owners are fixed.
    output = io.BytesIO()
    with gzip.GzipFile(fileobj=output, mode='wb', filename='', mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode='w') as tar:
            for name, blob in sorted(contents.items()):
                info = tarfile.TarInfo('./' + name)
                info.size = len(blob)
                info.mode = 0o755 if name in ('preinst', 'postinst', 'prerm', 'postrm') else 0o644
                tar.addfile(info, io.BytesIO(blob))
    return output.getvalue()


def emit(row, control, ipk, output):
    from publication_layout import record
    text = ''.join(k + ': ' + v + '\n' for k, v in control.items() if v)
    filename = control['Package'] + '_' + control['Version'] + '_' + control['Architecture'] + '.ipk'
    path = output / row['profile'] / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(ipk)
    stanza = text + 'Filename: ' + filename + '\nSHA256sum: ' + sha(ipk) + '\nSize: ' + str(len(ipk)) + '\n'
    return record(path, stanza, row['section'], 'kernel', row['profile'])


def apply(rows, output):
    rows = [dict(r, section='kernel/' + r['profile'] + ('-candidates' if fields(r['control']).get('X-Module-Staging-Only') == 'yes' else '')) for r in rows]
    mapping = json.loads((BUILD / 'legacy-map.json').read_text())
    profiles = definitions()
    firmware = json.loads((BUILD / 'firmware-packages.json').read_text())
    groups = dict(mapping['groups'])
    configs = {p: config(p) for p in profiles}
    inventory = {p: {} for p in profiles}
    sources = {}
    for row in rows:
        profile = row['profile']
        if profile not in profiles or row['section'] != profiles[profile]['feed']:
            continue
        f = fields(row['control'])
        if f.get('X-Module-Staging-Only') == 'yes':
            continue
        path = Path(row['_path'])
        original = path.read_bytes()
        if sha(original) != row['sha256']:
            raise ValueError('Unverified module source IPK')
        outer = unpack(original)
        data = unpack(outer['data.tar.gz'])
        if len(data) != 1:
            continue
        member, payload = next(iter(data.items()))
        if not member.startswith('lib/modules/') or not member.endswith('.ko'):
            continue  # Includes deliberately staged cryptodev on runtime feeds.
        module = Path(member).stem
        if module in inventory[profile]:
            raise ValueError('Ambiguous installable module: ' + profile + '/' + module)
        parsed = elf_module(payload)
        inventory[profile][module] = {'row': row, 'outer': outer, 'member': member,
                                     'payload': payload, 'elf': parsed, 'fields': f}
        sources[row['package']] = inventory[profile][module]
        canonical = 'kmod-' + module.lower().replace('_', '-')
        groups.setdefault(canonical, {'modules': [module], 'depends': 'kernel', 'extra_files': [],
                                     'source': 'Single module in a verified ABI-specific package'})

    reports = {}
    plans = {}
    # Determine complete capabilities first, including dependencies between groups.
    for profile, entry in profiles.items():
        cfg, cfg_sha = configs[profile]
        available = inventory[profile]
        stock = firmware.get(profile, {}).get('packages', {})
        local_groups = dict(groups)
        for name, data in stock.items():
            if name not in sources and data['modules']:
                local_groups[name] = dict(data)
        selected, skipped = {}, {}
        for generic, group in local_groups.items():
            mods = group['modules']
            missing = [m for m in mods if m not in available and cfg.get(mapping['builtin_configs'].get(m, '')) != 'y']
            if not mods or group.get('extra_files') or missing:
                skipped[generic] = {'missing_or_staged_modules': missing, 'extra_files': group.get('extra_files', []),
                                    'empty_module_group': not bool(mods)}
                continue
            dependencies = []
            invalid = []
            for part in group.get('depends', '').split(','):
                part = part.strip()
                if not part or part == 'kernel' or part.startswith('kernel ('):
                    continue
                if not re.fullmatch(r'kmod-[a-zA-Z0-9+-]+', part):
                    invalid.append(part)
                else:
                    dependencies.append(part)
            if invalid:
                skipped[generic] = {'unsupported_dependencies': invalid}
                continue
            selected[generic] = {'modules': mods, 'dependencies': dependencies,
                                 'builtins': [m for m in mods if m not in available]}
        changed = True
        while changed:
            changed = False
            for generic, group in list(selected.items()):
                missing = [d for d in group['dependencies'] if d not in selected and d not in stock]
                if missing:
                    skipped[generic] = {'unavailable_groups': missing}
                    del selected[generic]
                    changed = True
        # Only advertise a direct provider when the complete capability is exactly one module.
        direct = {g: available[v['modules'][0]]['row']['package'] for g, v in selected.items()
                  if len(v['modules']) == 1 and v['modules'][0] in available}
        names = {g: direct.get(g, g + '-' + profile + '-compat' if g in stock else g) for g in selected}
        plans[profile] = {'groups': selected, 'direct': direct, 'names': names, 'stock': stock}
        reports[profile] = {'config_sha256': cfg_sha, 'kernel_package': entry['kernel_package'],
                            'provided': selected, 'not_provided': skipped,
                            'policy': 'Only installed module payloads and exact-ABI builtin capabilities; staging is not a provider.'}

    # All physical module package versions/relationships are calculated together.
    versions = {}
    modified = {}
    for profile, items in inventory.items():
        plan = plans[profile]
        for module, source in items.items():
            f = dict(source['fields'])
            generic_names = [g for g, pkg in plan['direct'].items() if pkg == f['Package']]
            replacement_groups = dict(groups)
            replacement_groups.update(plan['stock'])
            replacing = {g: [module] for g, gdata in replacement_groups.items()
                         if module in gdata['modules'] and g != f['Package'] and g not in sources}
            f['Version'] = upgraded(f['Version'])
            f['Provides'] = add(f.get('Provides', ''), generic_names)
            # The exact 2017 firmware opkg has an out-of-bounds Replaces parser.
            # Never place this field in a public index or its underlying IPK.
            f.pop('Replaces', None)
            f.pop('Conflicts', None)
            f['X-Module-Path'] = '/' + source['member']
            f['X-Module-SHA256'] = sha(source['payload'])
            f['X-Canonical-Provider-Packages'] = ', '.join(g for g in generic_names if g not in plan['stock'])
            f['X-Original-IPK-SHA256'] = source['row']['sha256']
            f['X-Kernel-OPKG-Metadata'] = POLICY
            versions[f['Package']] = f['Version']
            modified[f['Package']] = {'fields': f, 'source': source, 'replacing': replacing}

    emitted = {}
    for package, item in modified.items():
        source, f = item['source'], item['fields']
        profile = source['row']['profile']
        available = inventory[profile]
        dependencies = []
        stock_deps = set()
        for mod in source['elf']['modinfo'].get('depends', [''])[0].split(','):
            if not mod:
                continue
            cfg, _ = configs[profile]
            if cfg.get(mapping['builtin_configs'].get(mod, '')) == 'y':
                continue
            if mod not in available:
                owners = [p for p,v in plans[profile]['stock'].items() if mod in v['modules']]
                if not owners:
                    raise ValueError('Missing runtime module dependency: ' + profile + '/' + mod)
                dep = sorted(owners)[0]
                stock_deps.add(dep)
                version = plans[profile]['stock'][dep]['version']
            else:
                dep = available[mod]['row']['package']
                version = versions[dep]
            dependencies.append(dep + ' (= ' + version + ')')
        for generic, target in plans[profile]['direct'].items():
            if target != package:
                continue
            for dep in plans[profile]['groups'][generic]['dependencies']:
                if dep in plans[profile]['names']:
                    name = plans[profile]['names'][dep]
                    version = versions.get(name, profile.split('-')[0] + '-' + (POLICY if dep in plans[profile]['stock'] else str(int(POLICY) + 1)))
                else:
                    name = dep
                    version = plans[profile]['stock'][dep]['version']
                    stock_deps.add(dep)
                if name != package:
                    dependencies.append(name + ' (= ' + version + ')')
        f['Depends'] = add(f['Depends'], dependencies)
        controls = unpack(source['outer']['control.tar.gz'])
        if any(name != 'control' for name in controls):
            raise ValueError('Unexpected existing maintainer scripts: ' + package)
        controls['control'] = ''.join(k + ': ' + v + '\n' for k, v in f.items() if v).encode()
        controls['preinst'] = guard(profiles[profile]['kernel_package'], item['replacing'], stock_deps)
        outer = archive({'./debian-binary': b'2.0\n', './control.tar.gz': control_archive(controls),
                         './data.tar.gz': data_archive(unpack(source['outer']['data.tar.gz']))})
        emitted[package] = emit(source['row'], f, outer, output)

    metas = []
    for profile, plan in plans.items():
        entry = profiles[profile]
        for generic, capability in plan['groups'].items():
            if generic in plan['direct'] and generic in plan['stock']:
                continue
            physical = sorted({inventory[profile][m]['row']['package'] for m in capability['modules'] if m in inventory[profile]})
            dependencies = ['kernel (= ' + entry['kernel_package'] + ')']
            dependencies += [name + ' (= ' + versions[name] + ')' for name in physical]
            for dep in capability['dependencies']:
                name = plan['names'].get(dep, dep)
                version = versions.get(name, profile.split('-')[0] + '-' + (POLICY if dep in plans[profile]['stock'] else str(int(POLICY) + 1))) if dep in plan['names'] else plan['stock'][dep]['version']
                dependencies.append(name + ' (= ' + version + ')')
            migration_alias = generic not in plan['stock']
            package_name = generic if migration_alias else plan['names'][generic]
            provider_version = profile.split('-')[0] + '-' + str(int(POLICY) + 1) if migration_alias else profile.split('-')[0] + '-' + POLICY
            f = {'Package': package_name, 'Version': provider_version,
                 'Architecture': entry['architecture'], 'Depends': ', '.join(sorted(set(dependencies))),
                 'Provides': '' if migration_alias else generic,
                 'Section': 'kernel', 'Maintainer': 'GUI_ipk',
                 'Description': 'Exact-ABI ' + generic + ' capability for ' + profile + '; complete group or firmware builtins',
                 'X-Kernel-Profile': profile, 'X-Kernel-Vermagic': entry['vermagic'],
                 'X-Kernel-Capability': 'yes', 'X-Kernel-Capability-Name': generic, 'X-Kernel-OPKG-Metadata': POLICY,
                 'X-Builtin-Modules': ', '.join(capability['builtins']),
                 'X-Kernel-Config-SHA256': reports[profile]['config_sha256'],
                 'X-Manual-Install-Only': 'yes'}
            if entry.get('candidate'):
                f['X-Module-Staging-Only'] = 'yes'
                f['X-Runtime-Validated'] = 'no'
            control = ''.join(k + ': ' + v + '\n' for k, v in f.items() if v).encode()
            blob = archive({'./debian-binary': b'2.0\n', './control.tar.gz': control_archive({'control': control, 'preinst': guard(entry['kernel_package'], {}, [d for d in capability['dependencies'] if d not in plan['names']])}),
                            './data.tar.gz': archive({})})
            row = {'section': entry['feed'], 'profile': profile}
            metas.append(emit(row, f, blob, output))
    # Normalize the remaining staged IPKs as well: directory entries and the
    # absence of Replaces are required even when no capability is advertised.
    for row in rows:
        if row['package'] in emitted:
            continue
        if '_path' not in row:
            raise ValueError('Full publication requires every pinned input IPK')
        outer = unpack(Path(row['_path']).read_bytes())
        if sha(Path(row['_path']).read_bytes()) != row['sha256']:
            raise ValueError('Unverified staged source package')
        controls = unpack(outer['control.tar.gz'])
        f = fields(controls['control'].decode())
        data = unpack(outer['data.tar.gz'])
        if any(not name.endswith('.ko') for name in data):
            raise ValueError('Unexpected non-module payload in kernel source package')
        f.pop('Replaces', None)
        f['Version'] = upgraded(f['Version'])
        f['X-Original-IPK-SHA256'] = row['sha256']
        f['X-Kernel-OPKG-Metadata'] = POLICY
        controls['control'] = ''.join(k + ': ' + v + '\n' for k,v in f.items() if v).encode()
        blob = archive({'./debian-binary': b'2.0\n', './control.tar.gz': control_archive(controls),
                        './data.tar.gz': data_archive(data)})
        emitted[row['package']] = emit(row, f, blob, output)
    result = [emitted.get(row['package'], row) for row in rows] + metas
    # Preserve old raw input URLs for validation reports and source provenance,
    # but do not advertise those old control records in OPKG indexes.
    for row in result:
        if row['package'] in sources:
            original = sources[row['package']]['row']
        else:
            original = next((r for r in rows if r['package'] == row['package'] and r['profile'] == row['profile']), None)
        if original and row['filename'] != original['filename']:
            row['_archive_source'] = original.get('_path')
            row['_archive_filename'] = original['filename']
    if len({(r['section'], r['package'], r['version'], r['architecture']) for r in result}) != len(result):
        raise ValueError('Duplicate package identity within a feed')
    (output / 'coverage.json').write_text(json.dumps(reports, indent=2, sort_keys=True) + '\n')
    return result


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    from publication_layout import kernel_inputs
    raw = kernel_inputs(a.output.parent / (a.output.name + '-source-inputs'), normalize=False)
    rows = apply(raw, a.output)
    public = [{k: v for k, v in r.items() if not k.startswith('_')} for r in rows]
    (a.output / 'records.json').write_text(json.dumps(public, sort_keys=True, indent=2) + '\n')
    print('Generated', len(rows), 'kernel records;', sum(fields(r['control']).get('X-Kernel-Capability') == 'yes' for r in rows), 'complete capability packages')
