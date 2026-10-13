#!/usr/bin/env python3
"""Generate browsable GitHub Pages indexes from OPKG package indexes."""

import argparse
import html
from pathlib import Path
from urllib.parse import quote


FEEDS = ("base", "luci", "packages", "routing", "telephony", "target/packages")
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
            if fields["Package"].startswith("kmod-"):
                continue
            filename = fields["Filename"]
            if Path(filename).name != filename or not (index.parent / filename).is_file():
                raise ValueError(f"Invalid package filename in {index}: {filename}")
            entries.append(fields)
    return sorted(entries, key=lambda item: (item["Package"].lower(), item.get("Version", "")))


def page(title, selected, groups, prefix):
    nav = [f'<a href="{prefix}index.html">All packages</a>']
    nav.extend(
        f'<a href="{prefix}{feed}/index.html">{html.escape(feed)} ({len(groups[feed])})</a>'
        for feed in FEEDS
    )
    rows = []
    for feed in (FEEDS if selected is None else (selected,)):
        for item in groups[feed]:
            name = html.escape(item["Package"])
            version = html.escape(item.get("Version", ""))
            arch = html.escape(item.get("Architecture", ""))
            description = html.escape(item.get("Description", "").splitlines()[0])
            url = prefix + feed + "/" + quote(item["Filename"], safe="")
            rows.append(
                f'<tr><td>{name}</td><td>{version}</td><td>{arch}</td>'
                f'<td>{description}</td><td><a href="{html.escape(url, quote=True)}">Download IPK</a></td></tr>'
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
<p>Userspace OPKG feed for brcm63xx-tch/VBNTS. Browse packages or download an IPK file.</p></header>
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("feed_root", type=Path)
    root = parser.parse_args().feed_root
    groups = {feed: packages(root / feed / "Packages") for feed in FEEDS}
    (root / ".nojekyll").touch()
    (root / "index.html").write_text(page("All packages", None, groups, ""), encoding="utf-8")
    for feed in FEEDS:
        prefix = "../" * len(Path(feed).parts)
        (root / feed / "index.html").write_text(
            page(feed, feed, groups, prefix), encoding="utf-8"
        )
    print(f"Generated browsable pages for {sum(map(len, groups.values()))} packages")


if __name__ == "__main__":
    main()
