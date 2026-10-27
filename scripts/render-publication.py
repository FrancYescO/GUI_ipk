#!/usr/bin/env python3
"""Render one catalog while hosting only the selected userspace IPKs on Pages."""
import argparse
from collections import defaultdict
import gzip
import html
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
from publication_layout import ROOT, SITE, parse, write_snapshot
from kernel_compatibility_page import write_compatibility
from kernel_validation_page import write_report

spec = importlib.util.spec_from_file_location('pages', ROOT / 'scripts/generate-feed-pages.py')
pages = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pages)


def page(title, selected, groups, feeds, prefix):
    nav = [f'<a href="{prefix}index.html">All packages</a>', f'<a href="{prefix}feeds.json">Feed manifest</a>',
           f'<a href="{prefix}opkg-userspace.conf">Userspace OPKG sources</a>',
           f'<a href="{prefix}compatibility/index.html">Firmware compatibility</a>',
           f'<a href="{prefix}validation/4.1.38/index.html">4.1.38 tests</a>',
           f'<a href="{prefix}validation/4.1.52/index.html">4.1.52 tests</a>']
    nav += [f'<a href="{prefix}{key}/index.html">{html.escape(key)} ({len(rows)})</a>' for key, rows in groups.items()]
    rows = []
    for group in (groups if selected is None else [selected]):
        for record in groups[group]:
            fields = parse(record['control'])
            description = html.escape(fields.get('Description', ''))
            if fields.get('X-Module-Staging-Only') == 'yes':
                description += '<br>Staging only: manual validation required; excluded from automatic OPKG index.'
            if fields.get('X-Runtime-Test'):
                description += '<br>Test: ' + html.escape(fields['X-Runtime-Test']) + '; ' + html.escape(fields.get('X-Runtime-Test-Status', 'see validation'))
            rows.append('<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td><a href="{}">Download IPK</a></td></tr>'.format(
                html.escape(record['package']), html.escape(record['version']), html.escape(record['architecture']),
                description, html.escape(record['download_url'], quote=True)))
    source = ''
    if selected is not None:
        url = feeds[selected]
        source = '<p>OPKG source:</p><pre>src/gz gui_' + selected.replace('/', '_').replace('-', '_') + ' ' + html.escape(url) + '</pre>'
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + html.escape(title) + '</title><style>' + pages.STYLE + '</style></head><body><h1>' + html.escape(title) + '</h1><p>Userspace IPKs are hosted here. Kernel modules, Asterisk 20 and FreeSWITCH audio have dedicated Releases. Kernel packages require the exact runtime ABI; test levels remain distinct.</p>' + source + '<nav>' + ''.join(nav) + '</nav><label for="search">Search name, version, architecture or description</label><input id="search" type="search" placeholder="Search packages…"><p id="count"></p><div class="table-wrap"><table><thead><tr><th>Package</th><th>Version</th><th>Architecture</th><th>Description</th><th>Download</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div><script>' + pages.SCRIPT + '</script></body></html>'


def render(publication):
    catalog = json.loads((publication / 'catalog.json').read_text())
    site = publication / 'site'
    groups, feeds = defaultdict(list), {}
    for record in catalog['records']:
        key = ('kernel' if record['kind'] == 'kernel' else 'telephony/freeswitch-sounds' if record['storage'] == 'freeswitch-sounds' else record['section'])
        groups[key].append(record)
        feeds[key] = (SITE + '/' + key if record['storage'] == 'pages' else catalog['releases'][record['storage']]['url'])
    for key in groups:
        destination = site / key
        destination.mkdir(parents=True, exist_ok=True)
        (destination / 'index.html').write_text(page(key, key, groups, feeds, '../' * len(Path(key).parts)), encoding='utf-8')
    (site / 'index.html').write_text(page('GUI_ipk package catalog', None, groups, feeds, ''), encoding='utf-8')
    kernel_url = catalog['releases']['kernel']['url']
    for profile, origin in [('4.1.38-vbnto', '4.1.38-vbnto'), ('4.1.38-vbnts', '4.1.38-vbnts'),
                            ('4.1.52-vbntk', '4.1.52-vbntk'), ('4.1.52', '4.1.52-vbntk'),
                            ('4.1.38-vbnto-candidates', '4.1.38-vbnto'), ('4.1.38-vbnts-candidates', '4.1.38-vbnts')]:
        rows = [r for r in catalog['records'] if r['kind'] == 'kernel' and r['profile'] == origin]
        staging = profile.endswith('-candidates')
        rows = [r for r in rows if (parse(r['control']).get('X-Module-Staging-Only') == 'yes') == staging]
        destination = site / 'kernel' / profile
        destination.mkdir(parents=True, exist_ok=True)
        (destination / 'index.html').write_text(page(profile, profile, {profile: rows}, {profile: kernel_url}, '../../'), encoding='utf-8')
    legacy = site / 'kernel/4.1.38'
    legacy.mkdir(parents=True, exist_ok=True)
    (legacy / 'index.html').write_text('<!doctype html><h1>Legacy 4.1.38 buildroot archive</h1><p>No compatible runtime firmware has been identified.</p><a href="' + kernel_url + '/legacy-buildroot.tar.gz">Historical artifacts</a>')
    write_compatibility(site, pages.STYLE, pages.SCRIPT)
    pages.write_validation_page(site, asset_base=kernel_url + '/')
    with tempfile.TemporaryDirectory() as temp:
        source = Path(temp)
        shutil.copytree(ROOT / 'build/vbntj/validation', source, dirs_exist_ok=True)
        report = json.loads((source / 'results.json').read_text())
        report['asset_base'] = kernel_url + '/'
        (source / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
        write_report(source, site / 'validation/4.1.52', pages.STYLE, pages.SCRIPT)
    profiles = json.loads(next((publication / 'releases').glob('kernel-modules-*/profiles.json')).read_text())
    userspace = [{'name': 'modgui_' + key.replace('/', '_').replace('-', '_'), 'url': url,
                  'source': 'src/gz modgui_' + key.replace('/', '_').replace('-', '_') + ' ' + url}
                 for key, url in feeds.items() if key not in ('kernel', 'telephony/asterisk-20')]
    manifest = {'format_version': 1, 'userspace': userspace, 'kernel': {'url': kernel_url, 'profiles': [{'profile': key, 'kernel_package': value} for key, value in profiles.items()]},
                'optional': {'asterisk20': catalog['releases']['asterisk20']['url']}}
    (site / 'feeds.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (site / 'opkg-userspace.conf').write_text('\n'.join(r['source'] for r in userspace) + '\n')
    (site / 'opkg-kernel.conf').write_text('src/gz modgui_kernel ' + kernel_url + '\n')
    for helper in ('print-opkg-sources.sh', 'opkg-release-wget.sh'):
        shutil.copyfile(ROOT / 'scripts' / helper, site / helper)
    (site / '.nojekyll').touch()
    write_snapshot(site / 'publication.json.gz', catalog)
    if any(p.relative_to(site).parts[0] == 'kernel' for p in site.rglob('*.ipk')):
        raise ValueError('Kernel IPK leaked into Pages')
    size = sum(p.stat().st_size + 1024 for p in site.rglob('*') if p.is_file())
    if size >= 1073741824:
        raise ValueError('Pages archive would exceed 1 GiB')
    print('Rendered', len(catalog['records']), 'catalog entries;', len(list(site.rglob('*.ipk'))), 'Pages IPKs;', size, 'estimated TAR bytes')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('publication', type=Path)
    render(parser.parse_args().publication)
