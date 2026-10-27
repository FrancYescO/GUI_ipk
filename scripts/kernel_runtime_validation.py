"""Render per-profile 4.1.38 evidence without treating busy modules as tested."""
from collections import Counter
import html
import json
from pathlib import Path
import shutil
from urllib.parse import quote


def write_runtime_report(source, destination, style):
    report = json.loads((source / 'results.json').read_text())
    destination.mkdir(parents=True, exist_ok=True)
    for name in ('results.json', 'results.tsv', 'functional-results.txt', 'run.log'):
        shutil.copyfile(source / name, destination / name)
    counts = Counter((r['status'], r['level']) for r in report['modules'])
    fresh = sum(n for (status, level), n in counts.items() if status == 'passed' and not level.startswith('previous-'))
    previous = sum(n for (status, level), n in counts.items() if status == 'passed' and level.startswith('previous-'))
    busy = sum(n for (status, _), n in counts.items() if status == 'skip_busy')
    rows = []
    for module in report['modules']:
        label = ('Not runtime validated: stock module in use' if module['status'] == 'skip_busy' else
                 'Previously validated exact core payload' if module['level'].startswith('previous-') else
                 'Functional pass' if module['level'] == 'load-unload-functional' else 'Load/unload and namespace smoke pass')
        rows.append('<tr><td>{}</td><td>{}<br>{}</td><td><code>{}</code></td><td><a href="{}">Manual IPK</a></td></tr>'.format(
            html.escape(module['name']), label, html.escape(module.get('note', '')),
            module['sha256'], report['asset_base'] + quote(module['asset'], safe='')))
    title = report['profile'] + ' runtime validation'
    content = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + title + '</title><style>' + style + 'code{overflow-wrap:anywhere}</style></head><body><h1>' + title + '</h1><p>' + html.escape(report['device'] + ', firmware ' + report['firmware']) + '. Exact kernel package: <code>' + html.escape(report['kernel_package']) + '</code>.</p><p>' + str(fresh) + ' new passes; ' + str(previous) + ' reused exact core validations; ' + str(busy) + ' busy stock modules not substituted. All 49 package names align with VBNT-K; test levels differ.</p><p>Boot ID, kernel taint, loaded module names, routes and checked OPKG/network/firewall configurations were unchanged. No packages were installed, no boot autoload was added, and tests used disposable namespaces and /tmp payloads. xt_nat was withheld and its previous crash was not retried. USB driver registration was previously verified; USB tethering traffic remains untested.</p><nav><a href="../../kernel/">Kernel feeds</a><a href="results.json">Evidence JSON</a><a href="results.tsv">New test results</a><a href="functional-results.txt">Functional output</a><a href="run.log">Probe lifecycle log</a></nav><div class="table-wrap"><table><thead><tr><th>Module</th><th>Validation</th><th>Module SHA256</th><th>Download</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div></body></html>'
    (destination / 'index.html').write_text(content)
