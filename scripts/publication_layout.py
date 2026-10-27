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
        records.append(record(path, stanza, section, origin=manifest['url'] + '/' + path.name))
    return records


def kernel_inputs(work):
    feed = work / 'kernel-inputs'
    assembler = load_script('assemble-kernel-feed')
    ipks = []
    for suffix in ('manual', 'network', 'spu', 'rndis-compat'):
        ipks.extend((ROOT / ('artifacts/damson-4.1.52-' + suffix)).glob('*.ipk'))
    assembler.write_feed('4.1.52', ipks, feed)
    for profile in ('vbnto', 'vbnts'):
        directory = ROOT / ('artifacts/' + profile + '-4.1.38-manual')
        subprocess.run([sys.executable, str(ROOT / 'scripts/verify-vbnto-4.1.38-ipks.py'), str(directory), '--profile', profile], check=True)
        assembler.write_feed('4.1.38-' + profile, list(directory.glob('*.ipk')), feed)
    stage = load_script('fetch-kernel-candidates')
    stage.download(work / 'candidates', REPOSITORY)
    candidate = load_script('assemble-kernel-candidates')
    for profile, source in json.loads(candidate.SOURCES.read_text()).items():
        build = work / ('candidate-' + profile)
        metadata = candidate.restore(profile, source, work / 'candidates', build)
        candidate.write_feed(profile, source, build, metadata, feed / source['feed'])
    rows = []
    for section, profile in [('kernel/4.1.52', '4.1.52-vbntk'), ('kernel/4.1.38-vbnto', '4.1.38-vbnto'),
                             ('kernel/4.1.38-vbnts', '4.1.38-vbnts'), ('kernel/4.1.38-vbnto-candidates', '4.1.38-vbnto'),
                             ('kernel/4.1.38-vbnts-candidates', '4.1.38-vbnts')]:
        rows.extend(read_section(feed, section, 'kernel', profile))
    if len(rows) != 491 or len({r['package'] for r in rows}) != 491:
        raise ValueError('Unexpected kernel package set')
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
        group = ('kernel' if row['kind'] == 'kernel' else 'asterisk20' if row['section'] == 'telephony/asterisk-20'
                 else 'freeswitch-sounds' if row['package'].startswith('freeswitch-sounds-') else None)
        row['storage'] = group or 'pages'
        if group:
            releases.setdefault(group, []).append(row)
    release_info = {}
    for group, records in releases.items():
        if len(records) + 8 > 1000 or len({r['filename'] for r in records}) != len(records):
            raise ValueError('Release asset limit or duplicate filename')
        digest = sha(b'publication-layout-v2\n' + index(records)) if group == 'kernel' else sha(index(records))
        tag = ('kernel-modules' if group == 'kernel' else group) + '-' + digest[:16]
        directory = output / 'releases' / tag
        write_index(directory, [r for r in records if parse(r['control']).get('X-Module-Staging-Only') != 'yes'])
        candidates = [r for r in records if parse(r['control']).get('X-Module-Staging-Only') == 'yes']
        if candidates:
            (directory / 'Candidates').write_bytes(index(candidates))
        url = 'https://github.com/' + REPOSITORY + '/releases/download/' + tag
        release_info[group] = {'tag': tag, 'url': url, 'count': len(records), 'sha256': digest}
        for row in records:
            shutil.copyfile(row['_path'], directory / row['filename'])
            row['download_url'] = url + '/' + row['filename']
        (directory / 'source.json').write_text(json.dumps({'format_version': 1, 'group': group,
            'packages': [safe_record(r) for r in records]}, indent=2, sort_keys=True) + '\n')
        if group == 'kernel':
            profiles = {'4.1.38-vbnto': '4.1.38-1-08839f3f6145d3a5d2d04be7567e3f9d',
                        '4.1.38-vbnts': '4.1.38-1-8dd693635a152c8c7b822a64e6c5c470',
                        '4.1.52-vbntk': json.loads((ROOT / 'build/kernel-profiles/vbntk-4.1.52.json').read_text())['kernel_package']}
            (directory / 'profiles.json').write_text(json.dumps(profiles, indent=2) + '\n')
            for src, name in [('build/vbntj/validation/results.json', 'validation-4.1.52.json'),
                              ('build/vbnto-4.1.38/validation/results.json', 'validation-4.1.38.json'),
                              ('build/usb-rndis/validation.json', 'validation-usb-4.1.38.json')]:
                report = json.loads((ROOT / src).read_text())
                report['asset_base'] = url + '/'
                if 'release' in report:
                    report['release'] = url + '/build-diagnostics.tar.gz'
                (directory / name).write_text(json.dumps(report, indent=2) + '\n')
            write_archive(directory / 'legacy-buildroot.tar.gz',
                          {p.name: p.read_bytes() for p in (ROOT / 'artifacts/buildroot-4.1.38').iterdir() if p.is_file()})
            diagnostics = {}
            for profile in ('vbnto', 'vbnts'):
                source = output / 'work' / ('candidate-' + profile)
                for path in source.iterdir():
                    if path.is_file():
                        diagnostics[profile + '/' + path.name] = path.read_bytes()
            write_archive(directory / 'build-diagnostics.tar.gz', diagnostics)
        sums = [sha(p.read_bytes()) + '  ' + p.name for p in sorted(directory.iterdir())]
        (directory / 'SHA256SUMS').write_text('\n'.join(sums) + '\n')
        release_info[group]['assets'] = [{'name': p.name, 'sha256': sha(p.read_bytes()), 'size': p.stat().st_size}
                                          for p in sorted(directory.iterdir())]
    for section in SECTIONS[:-1]:
        records = [r for r in rows if r['section'] == section and r['storage'] == 'pages']
        write_index(pages / section, records)
        for row in records:
            shutil.copyfile(row['_path'], pages / section / row['filename'])
            row['download_url'] = SITE + '/' + section + '/' + row['filename']
    catalog = {'format_version': 1, 'repository': REPOSITORY, 'site': SITE, 'releases': release_info,
               'records': [safe_record(r) for r in rows]}
    (output / 'catalog.json').write_text(json.dumps(catalog, indent=2, sort_keys=True) + '\n')
    write_snapshot(output / 'catalog.json.gz', catalog)
    return catalog


def write_snapshot(path, catalog):
    with path.open('wb') as stream:
        with gzip.GzipFile(filename='', fileobj=stream, mode='wb', mtime=0) as zipped:
            zipped.write((json.dumps(catalog, sort_keys=True, separators=(',', ':')) + '\n').encode())
