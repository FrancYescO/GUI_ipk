"""Prepare the mixed Pages/Release layout without dropping package versions."""
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
SITE = 'https://francyesco.github.io/GUI_ipk'
REPOSITORY = 'FrancYescO/GUI_ipk'
SECTIONS = ('base', 'luci', 'packages', 'routing', 'telephony', 'target/packages', 'telephony/asterisk-20')
KERNEL_ALIASES = {
    '4.1.52': '4.1.52-vbntk',
    '4.1.38-vbnts': '4.1.38-vbntk',
    '4.1.52-vbnts': '4.1.52-vbntk',
    '4.1.38-vbnts-candidates': '4.1.38-vbntk-candidates',
}
TRANSPORT = {'Filename', 'Size', 'SHA256sum', 'MD5Sum'}


def load_script(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(data):
    return hashlib.sha256(data).hexdigest()


def parse(text):
    return dict(line.split(': ', 1) for line in text.splitlines() if ': ' in line and not line[:1].isspace())


def controls(stanza):
    result, include = [], True
    for line in stanza.strip().splitlines():
        if line and not line[:1].isspace() and ':' in line:
            include = line.split(':', 1)[0] not in TRANSPORT
        if include:
            result.append(line)
    return '\n'.join(result)


def index(records):
    return ('\n\n'.join(r['control'].rstrip() + '\nFilename: ' + r['filename'] +
                        '\nSize: ' + str(r['size']) + '\nSHA256sum: ' + r['sha256']
                        for r in sorted(records, key=lambda r: r['filename'])) + '\n\n').encode()


def write_index(root, records):
    root.mkdir(parents=True, exist_ok=True)
    data = index(records)
    (root / 'Packages').write_bytes(data)
    with (root / 'Packages.gz').open('wb') as output:
        with gzip.GzipFile(filename='', fileobj=output, mode='wb', mtime=0) as zipped:
            zipped.write(data)


def record(path, stanza, section, kind='userspace', profile=None, origin=None):
    fields = parse(stanza)
    if path.name != fields['Filename'] or path.is_symlink():
        raise ValueError('Unsafe or mismatched package filename')
    blob = path.read_bytes()
    digest = sha(blob)
    if digest != fields['SHA256sum'] or len(blob) != int(fields['Size']):
        raise ValueError('Package differs from verified index: ' + str(path))
    if kind == 'userspace' and (fields['Package'] in ('kernel', 'gcc') or fields['Package'].startswith('kmod-')):
        raise ValueError('Kernel/native GCC in userspace')
    return {'package': fields['Package'], 'version': fields['Version'], 'architecture': fields['Architecture'],
            'filename': path.name, 'sha256': digest, 'size': len(blob), 'control': controls(stanza),
            'section': section, 'kind': kind, 'profile': profile, '_path': str(path),
            'origin_url': origin or SITE + '/' + section + '/' + path.name}


def read_section(root, section, kind='userspace', profile=None):
    records = []
    for stanza in (root / section / 'Packages').read_text().strip().split('\n\n'):
        if not stanza.strip():
            continue
        fields = parse(stanza)
        if Path(fields['Filename']).name != fields['Filename']:
            raise ValueError('Expected local verified feed input')
        records.append(record(root / section / fields['Filename'], stanza, section, kind, profile))
    return records


def promoted_applications(records, source):
    manifest = json.loads((ROOT / 'build/application-archive/manifest.json').read_text())
    shards = load_script('merge-userspace-shards')
    for pin in manifest['packages']:
        matches = [r for r in records if r['section'] != 'telephony/asterisk-20' and r['package'] == pin['package']]
        # Keep a genuinely newer source build; the pinned versions are minimum promoted versions.
        if matches and matches[0]['version'] != pin['version']:
            import re
            tokens = lambda v: [(1, int(p)) if p.isdigit() else (0, p) for p in re.findall(r'\d+|\D+', v)]
            if tokens(matches[0]['version']) > tokens(pin['version']):
                continue
        path = source / pin['filename']
        if sha(path.read_bytes()) != pin['sha256']:
            raise ValueError('Promoted application checksum mismatch')
        text, fields = shards.control(path)
        if any(fields[k] != pin[v] for k, v in [('Package', 'package'), ('Version', 'version'), ('Architecture', 'architecture')]):
            raise ValueError('Promoted application metadata mismatch')
        section = matches[0]['section'] if matches else 'packages'
        records = [r for r in records if r not in matches]
        stanza = text + '\nFilename: ' + path.name + '\nSize: ' + str(path.stat().st_size) + '\nSHA256sum: ' + pin['sha256']
        records.append(record(path, stanza, section, origin=pin['url']))
    return records


def kernel_inputs(work, normalize=True):
    feed = work / 'kernel-inputs'
    assembler = load_script('assemble-kernel-feed')
    ipks = []
    for suffix in ('manual', 'network', 'spu', 'rndis-compat'):
        ipks.extend((ROOT / ('artifacts/damson-4.1.52-' + suffix)).glob('*.ipk'))
    from firmware_kernel_candidates import audit_vbntk_ipks
    audit_vbntk_ipks(ipks)
    assembler.write_feed('4.1.52', ipks, feed)
    stage = load_script('fetch-kernel-candidates')
    stage.download(work / 'candidates', REPOSITORY)
    network = load_script('network_kmods_4138')
    for profile in ('vbnto', 'vbnts'):
        directory = ROOT / ('artifacts/' + profile + '-4.1.38-manual')
        subprocess.run([sys.executable, str(ROOT / 'scripts/verify-vbnto-4.1.38-ipks.py'), str(directory), '--profile', profile], check=True)
        network_dir = ROOT / ('artifacts/' + profile + '-4.1.38-network')
        network.materialize(profile, work / 'candidates' / profile / 'ipks', network_dir, verify=True)
        assembler.write_feed('4.1.38-' + profile, list(directory.glob('*.ipk')) + list(network_dir.glob('*.ipk')), feed)
    candidate = load_script('assemble-kernel-candidates')
    for profile, source in json.loads(candidate.SOURCES.read_text()).items():
        build = work / ('candidate-' + profile)
        metadata = candidate.restore(profile, source, work / 'candidates', build)
        candidate.write_feed(profile, source, build, metadata, feed / source['feed'])
    rows = []
    for section, profile in [('kernel/4.1.52', '4.1.52-vbntk'), ('kernel/4.1.38-vbnto', '4.1.38-vbnto'),
                             ('kernel/4.1.38-vbnts', '4.1.38-vbnts'), ('kernel/4.1.38-vbnto-candidates', '4.1.38-vbnto'),
                             ('kernel/4.1.38-vbnts-candidates', '4.1.38-vbnts')]:
        rows.extend(read_section(feed, section, 'kernel',
                                 '4.1.38-vbntk' if profile == '4.1.38-vbnts' else profile))
    if len(rows) != 579 or len({r['package'] for r in rows}) != 579:
        raise ValueError('Unexpected kernel package set')
    from firmware_kernel_candidates import publication_records
    rows.extend(publication_records(work / 'firmware-candidates'))
    from cryptodev_packages import publication_records as cryptodev_records
    rows.extend(cryptodev_records())
    if len({r['package'] for r in rows}) != len(rows):
        raise ValueError('Duplicate firmware candidate package')
    if normalize:
        from kernel_opkg_providers import apply as normalize_kernel_metadata
        return normalize_kernel_metadata(rows, work / 'opkg-metadata')
    return rows


def safe_record(row):
    return {k: v for k, v in row.items() if not k.startswith('_')}


def write_archive(path, files):
    with path.open('wb') as stream:
        with gzip.GzipFile(filename='', fileobj=stream, mode='wb', mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode='w') as archive:
                for name, data in sorted(files.items()):
                    member = tarfile.TarInfo(name)
                    member.mode, member.size = 0o644, len(data)
                    archive.addfile(member, io.BytesIO(data))


def prepare(userspace, applications, output):
    if output.exists():
        raise ValueError('Publication output must be fresh')
    output.mkdir(parents=True)
    rows = []
    for section in SECTIONS:
        rows.extend(read_section(userspace, section))
    rows = promoted_applications(rows, applications)
    rows.extend(kernel_inputs(output / 'work'))
    releases, pages = {}, output / 'site'
    for row in rows:
        if row['kind'] == 'kernel':
            suffix = '-candidates' if parse(row['control']).get('X-Module-Staging-Only') == 'yes' else ''
            row['section'] = 'kernel/' + row['profile'] + suffix
        group = 'freeswitch-sounds' if row['package'].startswith('freeswitch-sounds-') else None
        row['storage'] = group or 'pages'
        if group:
            releases.setdefault(group, []).append(row)
    release_info = {}
    for group, records in releases.items():
        if len(records) + 8 > 1000 or len({r['filename'] for r in records}) != len(records):
            raise ValueError('Release asset limit or duplicate filename')
        digest = sha(index(records))
        tag = group + '-' + digest[:16]
        directory = output / 'releases' / tag
        write_index(directory, records)
        url = 'https://github.com/' + REPOSITORY + '/releases/download/' + tag
        release_info[group] = {'tag': tag, 'url': url, 'count': len(records), 'sha256': digest}
        for row in records:
            shutil.copyfile(row['_path'], directory / row['filename'])
            row['download_url'] = url + '/' + row['filename']
        (directory / 'source.json').write_text(json.dumps({'format_version': 1, 'group': group,
            'packages': [safe_record(r) for r in records]}, indent=2, sort_keys=True) + '\n')
        sums = [sha(p.read_bytes()) + '  ' + p.name for p in sorted(directory.iterdir())]
        (directory / 'SHA256SUMS').write_text('\n'.join(sums) + '\n')
        release_info[group]['assets'] = [{'name': p.name, 'sha256': sha(p.read_bytes()), 'size': p.stat().st_size}
                                          for p in sorted(directory.iterdir())]
    for section in dict.fromkeys(r['section'] for r in rows if r['storage'] == 'pages'):
        records = [r for r in rows if r['section'] == section and r['storage'] == 'pages']
        write_index(pages / section, records)
        for row in records:
            shutil.copyfile(row['_path'], pages / section / row['filename'])
            row['download_url'] = SITE + '/' + section + '/' + row['filename']
            if row.get('_archive_source'):
                old_name = row['_archive_filename']
                if Path(old_name).name != old_name:
                    raise ValueError('Unsafe archived kernel input name')
                shutil.copyfile(row['_archive_source'], pages / section / old_name)
    # Retain profile diagnostics beside their candidate feeds, without overwriting
    # the generated indexes or duplicating package bytes.
    for profile in ('vbnto', 'vbnts'):
        source = output / 'work/kernel-inputs/kernel' / ('4.1.38-' + profile + '-candidates')
        destination = pages / 'kernel' / source.name.replace('vbnts', 'vbntk')
        for path in source.iterdir():
            if path.is_file() and path.suffix != '.ipk' and not path.name.startswith('Packages'):
                shutil.copyfile(path, destination / path.name)
    legacy = pages / 'kernel/4.1.38'
    legacy.mkdir(parents=True, exist_ok=True)
    write_archive(legacy / 'legacy-buildroot.tar.gz',
                  {p.name: p.read_bytes() for p in (ROOT / 'artifacts/buildroot-4.1.38').iterdir() if p.is_file()})
    write_kernel_aliases(pages, rows)
    catalog = {'format_version': 1, 'repository': REPOSITORY, 'site': SITE, 'releases': release_info,
               'records': [safe_record(r) for r in rows]}
    (output / 'catalog.json').write_text(json.dumps(catalog, indent=2, sort_keys=True) + '\n')
    write_snapshot(output / 'catalog.json.gz', catalog)
    return catalog


def write_kernel_aliases(pages, rows):
    # Alias indexes resolve downloads to the canonical ABI-specific directory.
    for alias, profile in KERNEL_ALIASES.items():
        records = [dict(r, filename='../' + profile + '/' + r['filename']) for r in rows
                   if r['section'] == 'kernel/' + profile]
        write_index(pages / 'kernel' / alias, records)


def write_snapshot(path, catalog):
    with path.open('wb') as stream:
        with gzip.GzipFile(filename='', fileobj=stream, mode='wb', mtime=0) as zipped:
            zipped.write((json.dumps(catalog, sort_keys=True, separators=(',', ':')) + '\n').encode())
