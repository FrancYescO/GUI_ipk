"""Publish the firmware inventory without treating ABI matches as runtime tests."""
import csv
import html
import json
from pathlib import Path
import shutil


def write_compatibility(root, style, script):
    repo = Path(__file__).resolve().parents[1]
    source = repo / 'build/kernel-candidates'
    report = json.loads((source / 'firmware-compatibility.json').read_text())
    destination = root / 'compatibility'
    destination.mkdir(parents=True, exist_ok=True)
    for filename in ('firmware-compatibility.json', 'planned-profiles.json'):
        shutil.copyfile(source / filename, destination / filename)
    shutil.copyfile(repo / 'docs/kernel-compatibility.md', destination / 'kernel-compatibility.md')
    with (destination / 'firmware-compatibility.csv').open('w', newline='') as output:
        writer = csv.DictWriter(output, fieldnames=list(report['firmwares'][0]))
        writer.writeheader()
        writer.writerows(report['firmwares'])
    rows = []
    for row in report['firmwares']:
        profile = row['profile'] or 'Separate ABI/build investigation required'
        url = report['source'] + '/tree/' + row['commit']
        rows.append('<tr><td><a href="{}">{}</a></td><td>{}</td><td>{}</td><td><code>{}</code></td><td>{}</td><td>{}</td></tr>'.format(
            html.escape(url, quote=True), html.escape(row['firmware']),
            html.escape(row['kernel_release']), html.escape(row['architecture'] or 'unknown'),
            html.escape(row['kernel_package'] or 'metadata missing'),
            html.escape(profile), html.escape(row['status'])))
    content = '''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kernel firmware compatibility</title><style>''' + style + '''
code { overflow-wrap: anywhere; }</style></head><body>
<h1>Kernel firmware compatibility</h1>
<p>279 extracted firmware branches. Updated ''' + html.escape(report['updated']) + '''.</p>
<p>Operator branding does not determine whether a module can load. CPU, vendor SDK,
kernel sources, configuration, exported symbols and structure layouts must match.
Equal kernel packages or stock modules identify candidates; they do not certify newly built modules.</p>
<p>The tested 4.1.38 profiles cover DGA4131FWB 18.3.n.0439 and DGA4132 18.3.k.0451.
Other operators in this inventory do not share their complete kernel package identifiers.
Damson 4.1.52 tests are firmware-specific and are not automatically assigned to other 4.1.52 rows.</p>
<p>FW261/FW264 are awaiting runtime kernel configurations. No supported feed is claimed for them.
Optional candidate feeds install modules in a staging directory and require manual dependency and loading checks.
They do not replace stock modules or configure autoload. xt_nat remains withheld.</p>
<nav><a href="../index.html">All packages</a>
<a href="../kernel/4.1.38-vbnto-candidates/index.html">VBNT-O candidates</a>
<a href="../kernel/4.1.38-vbnts-candidates/index.html">VBNT-S candidates</a>
<a href="kernel-compatibility.md">Feed setup and scope</a>
<a href="firmware-compatibility.json">JSON inventory</a>
<a href="firmware-compatibility.csv">CSV inventory</a>
<a href="planned-profiles.json">Profiles awaiting inputs</a></nav>
<label for="search">Search firmware, kernel, profile or status</label>
<input id="search" type="search" placeholder="Search firmware…"><p id="count"></p>
<div class="table-wrap"><table><thead><tr><th>Firmware</th><th>Kernel</th><th>Architecture</th>
<th>Exact kernel package</th><th>Build profile candidate</th><th>Evidence status</th></tr></thead><tbody>''' + ''.join(rows) + '''</tbody></table></div>
<script>''' + script + '</script></body></html>'
    (destination / 'index.html').write_text(content, encoding='utf-8')
    write_usb_report(root, style)


def write_usb_report(root, style):
    repo = Path(__file__).resolve().parents[1]
    source = repo / 'artifacts/usb-rndis-4.1.38'
    registry = repo / 'build/usb-rndis/validation.json'
    if not registry.is_file():
        return
    report = json.loads(registry.read_text())
    destination = root / 'validation/usb-4.1.38'
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(registry, destination / 'results.json')
    shutil.copyfile(source / 'README.md', destination / 'README.md')
    rows = []
    for profile, record in report['profiles'].items():
        shutil.copytree(source / profile, destination / profile, dirs_exist_ok=True)
        rows.append('<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td><a href="{}/router-test.log">Probe log</a> · <a href="{}/BUILD-METADATA.txt">Build inputs</a> · <a href="../../kernel/4.1.38-{}/index.html">IPKs</a></td></tr>'.format(
            profile, html.escape(record['firmware']), html.escape(record['status']),
            html.escape(record['traffic']), profile, profile, profile))
    page = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>USB RNDIS 4.1.38 validation</title><style>' + style + '</style></head><body>'
    page += '<h1>USB RNDIS 4.1.38 validation</h1><p>Both profiles produced identical cdc_ether and rndis_host payloads. They use the same miscellaneous-class RNDIS patch as the Damson 4.1.52 pair, while retaining native usbnet.</p>'
    page += '<p>Loading, USB driver registration, unloading and stock restoration passed on both modems. Boot IDs, kernel taint and default routes were unchanged. No USB network device was attached: enumeration, DHCP and traffic remain untested.</p>'
    page += '<nav><a href="../../index.html">All packages</a><a href="results.json">Exact payload hashes</a><a href="README.md">Build and test details</a></nav><table><thead><tr><th>Profile</th><th>Firmware</th><th>Result</th><th>Device traffic</th><th>Evidence</th></tr></thead><tbody>'
    page += ''.join(rows) + '</tbody></table></body></html>'
    (destination / 'index.html').write_text(page, encoding='utf-8')
