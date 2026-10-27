#!/usr/bin/env python3
"""Generate browsable GitHub Pages indexes from OPKG package indexes."""

import argparse
import html
import json
import shutil
from collections import Counter
from pathlib import Path
from urllib.parse import quote
from kernel_validation_page import write_report


USERSPACE_FEEDS = ("base", "luci", "packages", "routing", "telephony", "target/packages")
KERNEL_FEEDS = ("kernel/4.1.38", "kernel/4.1.38-vbnto", "kernel/4.1.38-vbnts", "kernel/4.1.52")
ASTERISK_FEED = "telephony/asterisk-20"
FEEDS = USERSPACE_FEEDS + KERNEL_FEEDS + (ASTERISK_FEED,)
STYLE = """
:root { color-scheme: light; font: 16px/1.5 system-ui, sans-serif; }
body { max-width: 78rem; margin: auto; padding: 2rem 1rem; color: #17212b; }
a { color: #075aa7; }
header { margin-bottom: 2rem; }
nav { display: flex; flex-wrap: wrap; gap: .5rem; margin: 1.5rem 0; }
nav a { padding: .35rem .7rem; border: 1px solid #bacbd9; border-radius: .4rem; }
input { box-sizing: border-box; width: 100%; padding: .75rem; font: inherit; border: 1px solid #8196a8; border-radius: .4rem; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
th, td { padding: .65rem; border-bottom: 1px solid #d8e0e7; text-align: left; vertical-align: top; }
th { background: #f0f4f7; }
td:first-child { font-weight: 600; }
td:last-child { min-width: 16rem; }
tr[hidden] { display: none; }
.muted { color: #526374; }
"""
SCRIPT = """
const search = document.querySelector('#search');
const rows = [...document.querySelectorAll('tbody tr')];
const count = document.querySelector('#count');
function filter() {
  const query = search.value.trim().toLocaleLowerCase();
  let shown = 0;
  for (const row of rows) {
    row.hidden = !row.textContent.toLocaleLowerCase().includes(query);
    if (!row.hidden) shown++;
  }
  count.textContent = `${shown} of ${rows.length} packages shown`;
}
search.addEventListener('input', filter);
filter();
"""


def packages(index):
    entries = []
    for paragraph in index.read_text(encoding="utf-8").split("\n\n"):
        fields = {}
        for line in paragraph.splitlines():
            if ": " in line and not line[0].isspace():
                key, value = line.split(": ", 1)
                fields[key] = value.strip()
        if fields.get("Package") and fields.get("Filename"):
            is_kernel_feed = "kernel" in index.parts
            kernel_package = fields["Package"] == "kernel" or fields["Package"].startswith("kmod-")
            if kernel_package != is_kernel_feed:
                raise ValueError(f"Package in wrong feed: {fields['Package']} in {index}")
            filename = fields["Filename"]
            if Path(filename).name != filename or not (index.parent / filename).is_file():
                raise ValueError(f"Invalid package filename in {index}: {filename}")
            entries.append(fields)
    return sorted(entries, key=lambda item: (item["Package"].lower(), item.get("Version", "")))


def page(title, selected, groups, prefix, partial=False):
    nav = [f'<a href="{prefix}index.html">All packages</a>']
    nav.append(f'<a href="{prefix}validation/4.1.38/index.html">4.1.38 validation results</a>')
    nav.append(f'<a href="{prefix}validation/4.1.52/index.html">4.1.52 validation results</a>')
    nav.extend(
        f'<a href="{prefix}{feed}/index.html">{html.escape(feed)} ({len(groups[feed])})</a>'
        for feed in groups
    )
    rows = []
    for feed in (groups if selected is None else (selected,)):
        for item in groups[feed]:
            name = html.escape(item["Package"])
            version = html.escape(item.get("Version", ""))
            arch = html.escape(item.get("Architecture", ""))
            description = html.escape(next(iter(item.get("Description", "").splitlines()), ""))
            url = prefix + feed + "/" + quote(item["Filename"], safe="")
            rows.append(
                f'<tr><td>{name}</td><td>{version}</td><td>{arch}</td>'
                f'<td>{description}</td><td><a href="{html.escape(url, quote=True)}">Download IPK</a></td></tr>'
            )
    notice = (
        "<p><strong>Linux 4.1.38 modules were built for the VBNTS buildroot.</strong> "
        "The kernel IPK records the build ABI but contains no kernel image. "
        "These packages do not include the Damson 4.1.52 ABI adaptation and "
        "must not be used on VBNT-K Damson. Check the exact VBNTS firmware "
        "ABI before installation; they have not been tested on a router.</p>"
        if selected == "kernel/4.1.38" else
        "<p><strong>Damson 4.1.52 modules require the exact firmware ABI.</strong> "
        "TUN, act_connmark and the cdc_ether/rndis_host compatibility pair "
        "were tested on VBNT-K Damson 19.4.0866-3401052. "
        "The RNDIS pair uses the firmware's native usbnet module. "
        "WireGuard passed loading, local handshake and "
        "unloading on VBNT-K 19.4.1051; routed VPN traffic remains untested. "
        "WireGuard requires the stock udp_tunnel and ip6_udp_tunnel modules "
        "already loaded. Other additional modules passed build checks only. "
        "All IPKs are manual-only: test a raw module from /tmp before "
        "installing it on persistent storage.</p>"
        if selected in KERNEL_FEEDS else
        "<p>Kernel IPKs are grouped by kernel version. Check the firmware and ABI "
        "before downloading or installing a module.</p>"
        if selected is None else ""
    )
    if selected == "kernel/4.1.52":
        notice = (
            '<p><strong>Linux 4.1.52 requires the matching firmware ABI.</strong> '
            'Runtime tests on VBNT-K Damson 19.4.1051 distinguish functional '
            'passes from smoke tests and busy stock modules that were not replaced. '
            'Corrected QoS statistic and NAT range layouts retain version 4.1.52-1. '
            'xt_nat is withheld pending safe validation. '
            f'<a href="{prefix}validation/4.1.52/index.html">Read exact-payload validation results</a>. '
            'IPKs are manual-only; raw-module tests do not validate persistent installation.</p>'
        )
    if partial:
        notice += (
            '<p><strong>Some packages did not build.</strong> This feed contains the '
            'packages that succeeded. <a href="'
            f'{prefix}shard-report.md">View the build failure report</a>.</p>'
        )
    if selected == ASTERISK_FEED or (selected is None and ASTERISK_FEED in groups):
        notice += (
            "<p><strong>Asterisk 20 has a dedicated feed.</strong> It includes matching "
            "PJPROJECT and Jansson libraries. Do not combine these libraries with "
            "legacy Asterisk 13/15 installations. Basic SIP and G.711 echo calls were "
            "tested on VBNTJ 4.1.52; persistent installation and provider trunks "
            "remain untested. "
            f'<a href="{prefix}{ASTERISK_FEED}/Packages.gz">OPKG index</a> · '
            f'<a href="{prefix}{ASTERISK_FEED}/build-info.json">Build information</a>.</p>'
        )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} · GUI_ipk</title>
<style>{STYLE}</style>
</head>
<body>
<header><h1>{html.escape(title)}</h1>
<p>OPKG packages for brcm63xx-tch/VBNTS. Browse packages or download an IPK file.</p>
{notice}</header>
<nav aria-label="Feed sections">{' '.join(nav)}</nav>
<label for="search">Search by name, version, architecture, or description</label>
<input id="search" type="search" autocomplete="off" placeholder="Search packages…">
<p id="count" class="muted"></p>
<div class="table-wrap"><table>
<thead><tr><th>Package</th><th>Version</th><th>Architecture</th><th>Description</th><th>Download</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table></div>
<script>{SCRIPT}</script>
</body></html>
"""


def write_validation_page(root):
    source = Path(__file__).resolve().parents[1] / "build/vbnto-4.1.38/validation"
    report = json.loads((source / "results.json").read_text())
    destination = root / "validation/4.1.38"
    destination.mkdir(parents=True, exist_ok=True)
    for filename in ("results.json", "results.tsv", "additional-functional-results.txt"):
        shutil.copyfile(source / filename, destination / filename)
    counts = Counter((row["status"], row["level"]) for row in report["modules"])
    functional = counts["passed", "load-unload-functional"]
    smoke = counts["passed", "load-unload-namespace"]
    previous = counts["passed", "previous-functional-validation"]
    labels = {
        "load-unload-functional": "Functional test passed",
        "load-unload-namespace": "Load/unload + namespace only",
        "previous-functional-validation": "Previously validated; tested feed",
        "build-only": "Built; runtime not tested",
        "crash-during-test-start": "BLOCKED: crash during test start",
    }
    rows = []
    for module in report["modules"]:
        label = labels[module["level"]]
        if module["status"] == "functional_failed":
            label = "Functional test incomplete; load/unload passed"
        download = "Withheld"
        if module["status"] != "blocked":
            url = report["asset_base"] + quote(module["asset"], safe="")
            download = f'<a href="{html.escape(url, quote=True)}">Staged candidate IPK</a>'
        rows.append(
            f'<tr><td>{html.escape(module["name"])}</td><td>{label}</td>'
            f'<td>{html.escape(module.get("note", ""))}</td>'
            f'<td><code>{html.escape(module["sha256"])}</code></td><td>{download}</td></tr>'
        )
    content = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Linux 4.1.38 module validation</title><style>{STYLE}code {{ overflow-wrap: anywhere; }}</style></head><body>
<header><h1>Linux 4.1.38 module validation</h1>
<p>Updated {html.escape(report['updated'])}. Device: {html.escape(report['device'])}, firmware {html.escape(report['firmware'])}.
Exact kernel package: <code>{html.escape(report['kernel_package'])}</code>.</p>
<p>{functional} candidates passed functional tests; {smoke} passed load/unload and namespace smoke tests only;
{previous} exact candidate payloads were already validated (TUN and WireGuard).
SPU is validated separately in the tested feed. A successful smoke test does not establish full functionality.</p>
<p><strong>xt_nat is blocked:</strong> a previous session crashed after starting its test, before a result was recorded.
The cause remains unresolved. Stock conntrack core remains in use; its candidate has not been runtime validated.</p>
<p>New tests use temporary payloads under /tmp and disposable network namespaces. The latest session retained its boot ID,
restored original modules and left no test namespaces or test helper loaded. An earlier session rebooted as described above.</p>
<p>Downloads below are <strong>staged candidates, separate from the tested OPKG feed</strong>.
They install under <code>/usr/lib/kernel-module-candidates/4.1.38/</code>, with no boot autoload or stock module replacement.
Tested-feed TUN, SPU and WireGuard are available in the <a href="../../kernel/4.1.38-vbnto/index.html">manual feed</a>.
These results apply to the listed SHA-256 payloads and firmware ABI, not every Linux 4.1.38 device.</p></header>
<nav><a href="../../index.html">All packages</a><a href="results.json">Machine-readable results</a>
<a href="results.tsv">Test history</a><a href="additional-functional-results.txt">Additional functional test output</a>
<a href="{html.escape(report['release'], quote=True)}">Candidate release and build diagnostics</a></nav>
<label for="search">Search modules or test results</label><input id="search" type="search" placeholder="Search modules…">
<p id="count" class="muted"></p><div class="table-wrap"><table><thead><tr><th>Module</th><th>Validation</th><th>Notes</th>
<th>Module SHA-256</th><th>Download</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<script>{SCRIPT}</script></body></html>'''
    (destination / "index.html").write_text(content, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("feed_root", type=Path)
    root = parser.parse_args().feed_root
    groups = {
        feed: packages(root / feed / "Packages")
        for feed in FEEDS
        if (root / feed / "Packages").is_file()
    }
    missing_userspace = set(USERSPACE_FEEDS) - groups.keys()
    if missing_userspace:
        raise ValueError(f"Missing userspace feeds: {sorted(missing_userspace)}")
    (root / ".nojekyll").touch()
    write_validation_page(root)
    write_report(Path(__file__).resolve().parents[1] / "build/vbntj/validation",
                 root / "validation/4.1.52", STYLE, SCRIPT)
    report = root / "shard-report.md"
    report_text = report.read_text() if report.is_file() else ""
    partial = "## Shard " in report_text or "## Skipped malformed IPKs" in report_text
    (root / "index.html").write_text(
        page("All packages", None, groups, "", partial), encoding="utf-8"
    )
    for feed in groups:
        prefix = "../" * len(Path(feed).parts)
        (root / feed / "index.html").write_text(
            page(feed, feed, groups, prefix, partial), encoding="utf-8"
        )
    print(f"Generated browsable pages for {sum(map(len, groups.values()))} packages")


if __name__ == "__main__":
    main()
