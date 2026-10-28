"""Render exact-payload kernel validation records for the package website."""
from collections import Counter
import html
import json
from pathlib import Path
import shutil
from urllib.parse import quote


def write_report(source, destination, style, script):
    report = json.loads((source / 'results.json').read_text())
    destination.mkdir(parents=True, exist_ok=True)
    for filename in ('results.json', 'results.tsv', 'functional-results.txt'):
        shutil.copyfile(source / filename, destination / filename)
    counts = Counter(row['status'] for row in report['modules'])
    functional = sum(row['status'] == 'passed' and row['level'] == 'load-unload-functional'
                     for row in report['modules'])
    smoke = counts['passed'] - functional
    rows = []
    for module in report['modules']:
        status = module['status']
        if status == 'passed':
            label = 'Functional test passed' if module['level'] == 'load-unload-functional' else 'Load/unload + namespace only'
        elif status == 'skip_busy':
            label = 'Not substituted: stock module in use'
        elif status == 'compiled' and module['level'] == 'offline-symbol-check':
            label = 'Offline symbols checked; not runtime validated'
        elif status.startswith('blocked'):
            label = 'WITHHELD: stock unload caused reboot; candidate untested'
        else:
            label = 'Functional validation incomplete'
        download = 'Withheld from installable feed'
        if module.get('asset'):
            url = report['asset_base'] + quote(module['asset'], safe='')
            download = f'<a href="{html.escape(url, quote=True)}">Manual IPK</a>'
        rows.append(
            f'<tr><td>{html.escape(module["name"])}</td><td>{label}</td>'
            f'<td>{html.escape(module.get("note", ""))}</td>'
            f'<td><code>{html.escape(module["sha256"])}</code></td><td>{download}</td></tr>'
        )
    content = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Linux 4.1.52 module validation</title><style>{style}code {{ overflow-wrap: anywhere; }}</style></head><body>
<header><h1>Linux 4.1.52 module validation</h1>
<p>Updated {html.escape(report['updated'])}. Device: VBNT-K at .69, firmware {html.escape(report['firmware'])}.
Kernel: 4.1.52 SMP preempt mod_unload ARMv7. Kernel package: <code>{html.escape(report['kernel_package'])}</code>.</p>
<p><strong>{functional} functional passes; {smoke} load/unload and namespace smoke passes;
{counts['skip_busy']} busy stock modules left unchanged; {counts['compiled']} replacement payloads checked offline only.</strong> A smoke pass does not establish full functionality.
Each result applies to the exact module SHA-256 and this firmware ABI.</p>
<p>Corrected Zyxel-only QoS drop-statistic and NAT range extensions absent from Technicolor firmware.
The original HFSC payload warned under traffic and pinned a test namespace; a controlled reboot restored stock modules.
Corrected HFSC, flow and REDIRECT passed traffic tests. Their filenames and version <code>4.1.52-1</code> are retained; payload and IPK checksums changed.</p>
<p>Conntrack revision <code>4.1.52-2</code> removes SDK-only Altibox UDP timeout and proc hooks.
Its original revision required two symbols absent from the firmware. The corrected payload passes offline symbol checks;
it has not been loaded or functionally tested. Its previous candidate and busy test history remain in the evidence.</p>
<p><strong>xt_nat is withheld.</strong> SSH was lost during removal of the stock module, before the new candidate loaded;
the modem returned with a different boot ID. The cause is unresolved and the removal will not be repeated.
The untested candidate is excluded from the installable feed. The final validation session retained its boot ID and initial taint.</p>
<p>WireGuard passed isolated two-peer handshake and encrypted traffic. SPU passed known-answer and ESP traffic tests with
BLOG offload disabled; this does not validate BLOG offload, sustained throughput or third-party client interoperability.
Busy conntrack, NAT core and firewall modules were not replaced or runtime validated.</p>
<p>Tests load raw IPK payloads from /tmp and use disposable namespaces. Original modules and parameters are restored;
no test IPK is installed, no boot autoload is added, and persistent configuration is unchanged.
Manual IPKs write modules to persistent storage when installed: these results do not validate persistent installation.
Existing package architecture/firmware guards remain; raw tests do not prove compatibility with every 4.1.52 firmware.</p></header>
<nav><a href="../../index.html">All packages</a><a href="../../kernel/4.1.52-vbntk/index.html">VBNT-K 4.1.52 manual feed</a>
<a href="results.json">Machine-readable results</a><a href="results.tsv">Test history</a>
<a href="functional-results.txt">Functional test output</a></nav>
<label for="search">Search modules or test results</label><input id="search" type="search" placeholder="Search modules…">
<p id="count" class="muted"></p><div class="table-wrap"><table><thead><tr><th>Module</th><th>Validation</th><th>Notes</th>
<th>Module SHA-256</th><th>Download</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<script>{script}</script></body></html>'''
    (destination / 'index.html').write_text(content, encoding='utf-8')
