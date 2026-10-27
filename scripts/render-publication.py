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
    nav = [f'<a href="{prefix}index.html">All packages</a>', f'<a href="{prefix}kernel/index.html">Kernel feeds and ABI selection</a>', f'<a href="{prefix}feeds.json">Feed manifest</a>',
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
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + html.escape(title) + '</title><style>' + pages.STYLE + '</style></head><body><h1>' + html.escape(title) + '</h1><p>Userspace, Asterisk 20 and kernel IPKs are hosted on Pages. Only the large FreeSWITCH sound packages use a Release. <a href="' + prefix + 'kernel/index.html">Choose a kernel feed by device and exact ABI</a>; candidate feeds require manual validation.</p>' + source + '<nav>' + ''.join(nav) + '</nav><label for="search">Search name, version, architecture or description</label><input id="search" type="search" placeholder="Search packages…"><p id="count"></p><div class="table-wrap"><table><thead><tr><th>Package</th><th>Version</th><th>Architecture</th><th>Description</th><th>Download</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div><script>' + pages.SCRIPT + '</script></body></html>'


def kernel_manifest(records):
    vbntk = json.loads((ROOT / 'build/kernel-profiles/vbntk-4.1.52.json').read_text())
    definitions = [
        ('4.1.38-vbnto', 'DGA4131FWB / VBNT-O', '18.3.n.0439', '.45', '4.1.38-1-08839f3f6145d3a5d2d04be7567e3f9d'),
        ('4.1.38-vbnts', 'DGA4132 / VBNT-S', '18.3.k.0451', '.204', '4.1.38-1-8dd693635a152c8c7b822a64e6c5c470'),
        ('4.1.52-vbntk', vbntk['device'], vbntk['firmware'], '.69', vbntk['kernel_package']),
    ]
    profiles, candidates = [], []
    for profile, device, firmware, router, version in definitions:
        for staging in (False, True):
            key = profile + ('-candidates' if staging else '')
            selected = [r for r in records if r['section'] == 'kernel/' + key]
            if not selected:
                continue
            name = 'modgui_kernel_' + key.replace('.', '_').replace('-', '_')
            url = SITE + '/kernel/' + key
            row = {'profile': key, 'device': device, 'firmware': firmware, 'validation_router': router,
                   'kernel_package': version, 'count': len(selected), 'url': url,
                   'source': 'src/gz ' + name + ' ' + url, 'staging_only': staging,
                   'status': 'Staging only; manual validation required' if staging else
                             'Runtime packages; see per-module test results'}
            (candidates if staging else profiles).append(row)
    return {'index_url': SITE + '/kernel/', 'profiles': profiles, 'candidates': candidates,
            'aliases': [{'url': SITE + '/kernel/4.1.52', 'profile': '4.1.52-vbntk'}],
            'legacy': {'url': SITE + '/kernel/4.1.38/', 'status': 'Archive only; no compatible firmware identified'}}


def write_kernel_overview(site, manifest):
    rows = []
    for row in manifest['profiles'] + manifest['candidates']:
        rows.append('<tr><td><a href="{url}/">{profile}</a></td><td>{device}<br>{firmware} ({router})</td>'
                    '<td>{count}</td><td>{status}</td><td><code>{abi}</code></td></tr>'.format(
                        url=html.escape(row['url']), profile=html.escape(row['profile']),
                        device=html.escape(row['device']), firmware=html.escape(row['firmware']),
                        router=row['validation_router'], count=row['count'], status=row['status'],
                        abi=html.escape(row['kernel_package'])))
    sources = ''.join('<h3>' + html.escape(r['profile']) + '</h3><pre>' + html.escape(r['source']) + '</pre>'
                      for r in manifest['profiles'])
    candidates = ''.join('<h3>' + html.escape(r['profile']) + '</h3><pre>' + html.escape(r['source']) + '</pre>'
                         for r in manifest['candidates'])
    content = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Available kernel OPKG feeds</title><style>''' + pages.STYLE + '''code, pre {overflow-wrap:anywhere;white-space:pre-wrap}</style></head><body>
<h1>Available kernel OPKG feeds</h1><p>Three runtime feeds and two separate candidate feeds, all hosted on Pages.
Enable only the runtime feed matching your complete installed <code>kernel</code> package version.
Linux version or operator branding alone is insufficient. Other firmware sharing the ABI still needs runtime validation.</p>
<nav><a href="../index.html">All packages</a><a href="../compatibility/">Firmware compatibility</a>
<a href="../feeds.json">Feed manifest</a><a href="../validation/4.1.38/">4.1.38 tests</a><a href="../validation/4.1.52/">4.1.52 tests</a></nav>
<pre>opkg status kernel</pre><div class="table-wrap"><table><thead><tr><th>Feed</th><th>Reference device / firmware</th><th>IPKs</th><th>Validation</th><th>Required kernel package version</th></tr></thead><tbody>''' + ''.join(rows) + '''</tbody></table></div>
<h2>Runtime OPKG sources — choose one exact ABI</h2>''' + sources + '''
<p>The two 4.1.38 runtime feeds each contain TUN, WireGuard, SPU, CDC Ethernet and RNDIS host.
The 4.1.52 feed contains 49 packages: 14 functional passes, 2 smoke passes and 33 busy stock modules left unchanged.
See the linked reports for exact payloads and test limits; USB tethering traffic has not been tested.</p>
<h2>Candidate sources — optional manual validation</h2><p>220 VBNT-O and 212 VBNT-S staging-only packages.
These feeds are separate from the runtime sources and are never enabled by the source-selection helper.
They stage modules outside boot paths; a successful build does not prove runtime compatibility. xt_nat remains withheld.</p>''' + candidates + '''
<h2>Historical paths</h2><p><a href="4.1.52/">kernel/4.1.52</a> is an OPKG-compatible alias of 4.1.52-vbntk.
<a href="4.1.38/">kernel/4.1.38</a> contains the generic buildroot archive only; no compatible runtime firmware is identified and it has no active OPKG feed.</p></body></html>'''
    (site / 'kernel/index.html').write_text(content)
    (site / 'kernel/profiles.json').write_text(json.dumps(manifest, indent=2) + '\n')


def render(publication):
    catalog = json.loads((publication / 'catalog.json').read_text())
    site = publication / 'site'
    groups, feeds = defaultdict(list), {}
    for record in catalog['records']:
        key = ('telephony/freeswitch-sounds' if record['storage'] == 'freeswitch-sounds' else record['section'])
        groups[key].append(record)
        feeds[key] = (SITE + '/' + key if record['storage'] == 'pages' else catalog['releases'][record['storage']]['url'])
    for key in groups:
        destination = site / key
        destination.mkdir(parents=True, exist_ok=True)
        (destination / 'index.html').write_text(page(key, key, groups, feeds, '../' * len(Path(key).parts)), encoding='utf-8')
    (site / 'index.html').write_text(page('GUI_ipk package catalog', None, groups, feeds, ''), encoding='utf-8')
    kernels = kernel_manifest(catalog['records'])
    write_kernel_overview(site, kernels)
    for row in kernels['profiles'] + kernels['candidates']:
        (site / 'kernel' / row['profile'] / 'opkg.conf').write_text(row['source'] + '\n')
    alias = site / 'kernel/4.1.52/index.html'
    alias.write_text('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=../4.1.52-vbntk/"><a href="../4.1.52-vbntk/">VBNT-K 4.1.52 runtime feed</a>')
    legacy = site / 'kernel/4.1.38'
    (legacy / 'index.html').write_text('<!doctype html><h1>Legacy 4.1.38 buildroot archive</h1><p>No compatible runtime firmware has been identified. No active OPKG source.</p><a href="legacy-buildroot.tar.gz">Historical artifacts</a><p><a href="../">Available kernel feeds</a></p>')
    write_compatibility(site, pages.STYLE, pages.SCRIPT)
    pages.write_validation_page(site)
    with tempfile.TemporaryDirectory() as temp:
        source = Path(temp)
        shutil.copytree(ROOT / 'build/vbntj/validation', source, dirs_exist_ok=True)
        report = json.loads((source / 'results.json').read_text())
        report['asset_base'] = SITE + '/kernel/4.1.52-vbntk/'
        (source / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
        write_report(source, site / 'validation/4.1.52', pages.STYLE, pages.SCRIPT)
    userspace = [{'name': 'modgui_' + key.replace('/', '_').replace('-', '_'), 'url': url,
                  'source': 'src/gz modgui_' + key.replace('/', '_').replace('-', '_') + ' ' + url}
                 for key, url in feeds.items() if not key.startswith('kernel/') and key != 'telephony/asterisk-20']
    manifest = {'format_version': 2, 'userspace': userspace, 'kernel': kernels,
                'optional': {'asterisk20': SITE + '/telephony/asterisk-20'}}
    (site / 'feeds.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (site / 'opkg-userspace.conf').write_text('\n'.join(r['source'] for r in userspace) + '\n')
    (site / 'opkg-kernel.conf').write_text('# Enable only one runtime source matching the exact installed kernel package.\n' + '\n'.join('# ' + r['kernel_package'] + '\n# ' + r['source'] for r in kernels['profiles']) + '\n')
    for helper in ('print-opkg-sources.sh', 'opkg-release-wget.sh'):
        shutil.copyfile(ROOT / 'scripts' / helper, site / helper)
    (site / '.nojekyll').touch()
    write_snapshot(site / 'publication.json.gz', catalog)
    size = sum(p.stat().st_size + 1024 for p in site.rglob('*') if p.is_file())
    if size >= 1073741824:
        raise ValueError('Pages archive would exceed 1 GiB')
    print('Rendered', len(catalog['records']), 'catalog entries;', len(list(site.rglob('*.ipk'))), 'Pages IPKs;', size, 'estimated TAR bytes')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('publication', type=Path)
    render(parser.parse_args().publication)
