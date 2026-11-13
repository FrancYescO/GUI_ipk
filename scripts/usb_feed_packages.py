"""Publish standard USB driver names and pinned, nonempty stock dependencies."""
import base64
import gzip
import io
import json
import posixpath
from pathlib import Path
import re
import shlex
import tarfile

import kernel_opkg_providers as k

STANDARD = {'cdc_ether': 'kmod-usb-net-cdc-ether', 'rndis_host': 'kmod-usb-net-rndis'}


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
    pinned = json.loads(gzip.decompress((k.BUILD / 'stock-usb.json.gz').read_bytes()))
    renames = {}
    drivers = {}
    for row in rows:
        f = k.fields(row['control'])
        module = Path(f.get('X-Module-Path', '')).stem
        if module in STANDARD and not f.get('X-Module-Staging-Only'):
            version = '1:' + row['version']
            renames[row['profile'], row['package']] = (STANDARD[module], version)
            drivers[row['profile'], row['package']] = module
    result = []
    for row in rows:
        profile = row['profile']
        f = k.fields(row['control'])
        old = row['package']
        module = drivers.get((profile, old))
        # Stock recovery replaces empty compatibility records for these names.
        if f.get('X-Kernel-Capability') == 'yes' and (old in pinned[profile]['packages'] or f.get('X-Kernel-Capability-Name') in STANDARD.values()):
            continue
        changed = False
        if module:
            f['Package'], f['Version'] = renames[profile, old]
            f.pop('X-Manual-Install-Only', None)
            f['Provides'] = ', '.join(p.strip() for p in f.get('Provides', '').split(',') if p.strip() and p.strip() != f['Package'])
            f['X-Previous-Module-Package'] = old
            changed = True
        depends = f.get('Depends', '')
        for (p, previous), (name, version) in renames.items():
            if p == profile:
                depends = re.sub(r'(?<![\w+.-])' + re.escape(previous) + r'\s*\(= [^)]+\)', name + ' (= ' + version + ')', depends)
                # Compatibility aliases may still reference the native owner
                # rather than the old manual name. They must follow its upgrade.
                depends = re.sub(r'(?<![\w+.-])' + re.escape(name) + r'\s*\(=\s*[^)]+\)', name + ' (= ' + version + ')', depends)
        # Always bind RNDIS to the repaired CDC package, including old .52 feeds.
        if module == 'rndis_host':
            cdc_version = next(v for (p, _), (n, v) in renames.items() if p == profile and n == STANDARD['cdc_ether'])
            depends = re.sub(r'kmod-usb-net-cdc-ether\s*\(=\s*[^)]+\)', '', depends)
            depends = k.add(','.join(part for part in depends.split(',') if part.strip()), [STANDARD['cdc_ether'] + ' (= ' + cdc_version + ')'])
        if depends != f.get('Depends'):
            f['Depends'] = depends
            changed = True
        if not changed:
            result.append(row)
            continue
        outer = k.unpack(Path(row['_path']).read_bytes())
        controls = k.unpack(outer['control.tar.gz'])
        if module:
            # OPKG cannot transfer another package's file ownership implicitly.
            # Fail before extraction and give a concrete migration instruction.
            controls['preinst'] += (f'legacy=$(package_status {shlex.quote(old)})\n'
                'if printf "%s\\n" "$legacy" | grep -q "^Status:.* installed"; then\n'
                f'  echo "Remove legacy package {old} after quiescing USB tethering, then retry" >&2\n'
                '  exit 1\nfi\n').encode()
        controls['control'] = ''.join(key + ': ' + value + '\n' for key, value in f.items() if value).encode()
        blob = k.archive({'./debian-binary': b'2.0\n', './control.tar.gz': k.control_archive(controls), './data.tar.gz': outer['data.tar.gz']})
        updated = k.emit(row, f, blob, output)
        for key, value in row.items():
            if key.startswith('_') and key != '_path':
                updated[key] = value
        result.append(updated)
    for profile, source in pinned.items():
        if source['kernel_package'] != k.definitions()[profile]['kernel_package']:
            raise ValueError('Stock USB ABI mismatch')
        for name, package in source['packages'].items():
            if k.sha(package['control'].encode()) != package['control_sha256'] or k.sha(package['list'].encode()) != package['list_sha256']:
                raise ValueError('Stock control/list checksum mismatch')
            f = k.fields(package['control'])
            f['X-Stock-Firmware-Commit'] = source['commit']
            f['X-Stock-Control-SHA256'] = package['control_sha256']
            f['X-Kernel-Profile'] = profile
            f['X-Stock-Recovery'] = 'yes'
            f['X-Stock-Modules'] = ', '.join(Path(p).stem for p in package['data'] if p.endswith('.ko'))
            if name == 'kmod-usb-net' and not any(p.endswith('/usbnet.ko') for p in package['data']):
                raise ValueError('Stock USBnet payload is missing')
            control = ''.join(key + ': ' + value + '\n' for key, value in f.items()).encode()
            blob = k.archive({'./debian-binary': b'2.0\n', './control.tar.gz': k.control_archive({'control': control, 'preinst': k.guard(source['kernel_package'], {})}), './data.tar.gz': stock_data(package['data'])})
            result.append(k.emit({'section': k.definitions()[profile]['feed'], 'profile': profile}, f, blob, output))
    if len({(r['section'], r['package']) for r in result}) != len(result):
        raise ValueError('Duplicate USB feed package')
    return result
