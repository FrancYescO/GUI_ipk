"""Build complete standard kernel packages from verified modules and stock groups."""
import base64
import copy
import gzip
import io
import json
import posixpath
from pathlib import Path
import re
import shlex
import tarfile

import kernel_opkg_providers as k

def stock_data(entries):
    files = {}
    for name, entry in entries.items():
        if name.startswith('/') or '..' in Path(name).parts:
            raise ValueError('Unsafe stock path')
        content = base64.b64decode(entry['base64'], validate=True)
        if k.sha(content) != entry['sha256']:
            raise ValueError('Stock payload checksum mismatch: ' + name)
        files[name] = content
    # Reuse the deterministic directory creation used for all kernel IPKs.
    output = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(k.data_archive(files))) as original, tarfile.open(fileobj=output, mode='w:gz', format=tarfile.USTAR_FORMAT) as target:
        for member in original:
            name = member.name.removeprefix('./')
            if member.isdir():
                target.addfile(member)
                continue
            entry = entries[name]
            if entry['mode'] == '120000':
                member.type = tarfile.SYMTYPE
                member.linkname = files[name].decode()
                resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), member.linkname))
                if member.linkname.startswith('/') or resolved not in entries:
                    raise ValueError('Unsafe stock symlink')
                member.size = 0
                target.addfile(member)
            else:
                member.mode = 0o755 if entry['mode'] == '100755' else 0o644
                target.addfile(member, io.BytesIO(files[name]))
    # tarfile's gzip writer uses wall time; normalize it for reproducibility.
    normalized = io.BytesIO()
    with gzip.GzipFile(filename='', fileobj=normalized, mode='wb', mtime=0) as stream:
        stream.write(gzip.decompress(output.getvalue()))
    return normalized.getvalue()


def apply(rows, output):
    pinned = json.loads(gzip.decompress((k.BUILD / 'stock-kernel.json.gz').read_bytes()))
    result, coverage = [], {}
    for profile, definition in k.definitions().items():
        source = pinned[profile]
        if source['kernel_package'] != definition['kernel_package']:
            raise ValueError('Stock kernel ABI mismatch: ' + profile)
        native = source['packages']
        modules, metas, staged = {}, [], []
        archives, legacy_archives = {}, []
        for row in (r for r in rows if r['profile'] == profile):
            f = k.fields(row['control'])
            if row.get('_archive_source'):
                archives[row['_archive_filename']] = row['_archive_source']
            legacy_archives.extend(row.get('_legacy_archives', []))
            if f.get('X-Module-Staging-Only') == 'yes':
                staged.append(row)
            elif f.get('X-Module-Path'):
                module = Path(f['X-Module-Path']).stem
                if module in modules:
                    raise ValueError('Duplicate installable module: ' + module)
                outer = k.unpack(Path(row['_path']).read_bytes())
                modules[module] = {'row': row, 'fields': f, 'data': k.unpack(outer['data.tar.gz'])}
            else:
                metas.append(row)
        owners = {}
        for name, package in native.items():
            if k.sha(package['control'].encode()) != package['control_sha256'] or k.sha(package['list'].encode()) != package['list_sha256']:
                raise ValueError('Stock metadata checksum mismatch')
            for path in package['list'].splitlines():
                if path.endswith('.ko'):
                    owners.setdefault(Path(path).stem, set()).add(name)
        targets, members = {}, {}
        for module, item in modules.items():
            candidates = owners.get(module, set())
            if len(candidates) > 1:
                raise ValueError('Ambiguous native owner: ' + module)
            target = next(iter(candidates)) if candidates else 'kmod-' + module.lower().replace('_', '-')
            targets[item['row']['package']] = target
            members.setdefault(target, []).append(module)
        version = '1:' + profile.split('-')[0] + '-' + str(int(k.POLICY) + 1)
        versions = {name: k.fields(p['control'])['Version'] for name, p in native.items()}
        versions.update({name: version for name in members})
        aliases = {}
        for row in metas:
            f = k.fields(row['control'])
            generic = f.get('X-Kernel-Capability-Name', row['package'])
            target = generic
            targets[row['package']] = target
            if target not in versions:
                versions[target] = version
                aliases[target] = row

        def dependencies(text, package):
            dependencies = set()
            for part in text.split(','):
                part = part.strip()
                if not part:
                    continue
                name = part.split()[0]
                target = targets.get(name, name)
                if target == package:
                    continue
                if name == 'kernel':
                    dependencies.add('kernel (= ' + definition['kernel_package'] + ')')
                elif target in versions:
                    dependencies.add(target + ' (= ' + versions[target] + ')')
                else:
                    raise ValueError('Unavailable kernel dependency: ' + profile + '/' + package + '/' + part)
            return ', '.join(sorted(dependencies))

        def emit(name, f, data, previous=()):
            f = dict(f)
            f.update(Package=name, Version=versions[name], Architecture=definition['architecture'])
            for field in ('Provides', 'Replaces', 'Conflicts', 'X-Manual-Install-Only', 'X-Canonical-Provider-Packages', 'X-Previous-Module-Package'):
                f.pop(field, None)
            f.update({'X-Kernel-Profile': profile, 'X-Kernel-Vermagic': definition['vermagic'],
                      'X-Kernel-OPKG-Metadata': k.POLICY, 'X-Standard-Kernel-Package': 'yes'})
            f['Depends'] = dependencies(f.get('Depends', 'kernel'), name)
            previous = sorted(set(p for p in previous if p != name))
            if previous:
                f['X-Previous-Module-Packages'] = ', '.join(previous)
                if len(previous) == 1:
                    f['X-Previous-Module-Package'] = previous[0]
            hook = k.guard(definition['kernel_package'], {})
            for old in previous:
                hook += (f'legacy=$(package_status {shlex.quote(old)})\n'
                         f'if [ "${{MODGUI_KERNEL_MIGRATION:-}}" != {shlex.quote(name)} ] && printf "%s\\n" "$legacy" | grep -q "^Status:.* installed"; then\n'
                         f'  echo "Quiesce module consumers and remove legacy package {old}, then retry" >&2\n'
                         '  exit 1\nfi\n').encode()
            with tarfile.open(fileobj=io.BytesIO(data)) as payload:
                f['X-Payload-Checksums'] = ', '.join(k.sha(payload.extractfile(m).read()) + ':' + m.name.removeprefix('./') for m in payload if m.isfile())
            with tarfile.open(fileobj=io.BytesIO(data)) as payload:
                f['X-Payload-Symlinks'] = ', '.join(m.name.removeprefix('./') + ':' + m.linkname for m in payload if m.issym())
            control = ''.join(key + ': ' + value + '\n' for key, value in f.items() if value).encode()
            blob = k.archive({'./debian-binary': b'2.0\n', './control.tar.gz': k.control_archive({'control': control, 'preinst': hook}), './data.tar.gz': data})
            return k.emit({'profile': profile, 'section': definition['feed']}, f, blob, output)

        profile_rows = []
        for name in sorted(set(native) | set(members)):
            rebuilt = members.get(name, [])
            previous = [modules[m]['row']['package'] for m in rebuilt]
            if name in native:
                original = native[name]
                f = k.fields(original['control'])
                entries = copy.deepcopy(original['data'])
                for module in rebuilt:
                    paths = [path.lstrip('/') for path in original['list'].splitlines() if Path(path).name == module + '.ko']
                    if len(paths) != 1:
                        raise ValueError('Incomplete native file list: ' + name + '/' + module)
                    payload = next(iter(modules[module]['data'].values()))
                    entries[paths[0]] = {'base64': base64.b64encode(payload).decode(), 'sha256': k.sha(payload), 'mode': '100644'}
                expected = {p.lstrip('/') for p in original['list'].splitlines()}
                if set(entries) != expected:
                    raise ValueError('Incomplete native payload: ' + profile + '/' + name)
                f.update({'X-Stock-Firmware-Commit': source['commit'], 'X-Stock-Control-SHA256': original['control_sha256'],
                          'X-Stock-Modules': ', '.join(Path(p).stem for p in entries if p.endswith('.ko')),
                          'X-Stock-Recovery': 'mixed' if rebuilt else 'yes'})
                data = stock_data(entries)
            else:
                if len(rebuilt) != 1:
                    raise ValueError('Unmapped module name collision: ' + name)
                f = dict(modules[rebuilt[0]]['fields'])
                entries = {path: {} for path in modules[rebuilt[0]]['data']}
                data = k.data_archive(modules[rebuilt[0]]['data'])
            if rebuilt:
                f['X-Previous-Module-Owners'] = json.dumps({modules[m]['row']['package']: sorted('/' + p for p in modules[m]['data']) for m in rebuilt if modules[m]['row']['package'] != name}, sort_keys=True, separators=(',', ':'))
                hashes = {m: modules[m]['fields']['X-Module-SHA256'] for m in rebuilt}
                f['X-Rebuilt-Modules'] = json.dumps(hashes, sort_keys=True, separators=(',', ':'))
                f['X-Original-IPK-SHA256'] = ', '.join(sorted({modules[m]['fields']['X-Original-IPK-SHA256'] for m in rebuilt}))
                f['X-Validation-Level'] = 'runtime-tested' if all(modules[m]['fields'].get('X-Runtime-Validated') == 'yes' for m in rebuilt) else 'offline-checked'
                f['X-Module-Validation'] = json.dumps({m: modules[m]['fields'].get('X-Runtime-Validated') == 'yes' for m in rebuilt}, sort_keys=True, separators=(',', ':'))
                f['X-Module-Tests'] = json.dumps({m: {'test': modules[m]['fields'].get('X-Runtime-Test', ''), 'status': modules[m]['fields'].get('X-Runtime-Test-Status', '')} for m in rebuilt}, sort_keys=True, separators=(',', ':'))
                f['Depends'] = ', '.join([f['Depends']] + [modules[m]['fields']['Depends'] for m in rebuilt])
                paths = [p for p in entries if p.endswith('.ko')]
                if len(paths) == 1:
                    f['X-Module-Path'] = '/' + paths[0]
                    f['X-Module-SHA256'] = hashes[rebuilt[0]]
                else:
                    f.pop('X-Module-Path', None)
                    f.pop('X-Module-SHA256', None)
            profile_rows.append(emit(name, f, data, previous))
        for name, row in sorted(aliases.items()):
            f = k.fields(row['control'])
            f['X-Kernel-Capability-Name'] = name
            profile_rows.append(emit(name, f, k.archive({})))
        profile_rows[0]['_package_archives'] = [{'filename': n, 'path': p} for n, p in sorted(archives.items())]
        profile_rows[0]['_legacy_archives'] = legacy_archives
        result.extend(profile_rows + staged)
        coverage[profile] = {'rebuilt_module_count': len(modules), 'rebuilt_packages': len(members), 'stock_recovery_packages': len(set(native) - set(members)), 'aliases': len(aliases), 'staged': len(staged)}
    if len({(r['section'], r['package']) for r in result}) != len(result):
        raise ValueError('Duplicate standard kernel package')
    (output / 'standard-coverage.json').write_text(json.dumps(coverage, indent=2, sort_keys=True) + '\n')
    return result

