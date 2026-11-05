# LuCI 18.06 maintenance update

The archived Technicolor buildroot contains LuCI revision
`50788da24e87bf2298dd7a2cebb13f533a8a6616` (29 October 2019). This update
advances that feed to the final upstream `openwrt-18.06` revision,
`20b3600d4d64bf60588cf4975c7a62104411870e` (9 February 2021 in the
commit's timezone, 10 February UTC).

The 98 upstream commits include the stored XSS correction in
`luci-app-firewall` (`3961268597abba4c2b231790cb4aa7936e73cdf8`), JSON
handling changes in `luci-lib-jsonc`, CBI fixes and application/translation
updates. This keeps the Lua-based OpenWrt 18.06 interface and dependencies;
it does not migrate the firmware to a current LuCI release.

## Reproducible source update

`build/luci-update.json` records both full revisions and the package version.
`patches/luci-18.06-update.patch.gz` is a deterministic compressed Git diff
between those revisions, generated with rename detection disabled. Its SHA-256
is checked using `build/luci-update.sha256` before any source changes.
No upstream fetch is needed for the LuCI delta during the package build.

`scripts/apply-luci-update.sh` checks the archived feed HEAD, applies the
delta with `git apply` (including deleted and empty files), and fixes
`PKG_VERSION` to `git-21.041.07147-20b3600`. It also fixes the displayed branch
name. The archived Git database is retained for other buildroot restoration
operations; its older revision is not used to label the updated packages.

The build restores stripped LuCI source payloads before applying the update.
Existing Homeware and additional-language overlays follow the upstream delta,
preserving their intentional recipe and translation overrides. Local feed
indexes and package links are refreshed after all overlays, before `defconfig`,
without fetching moving branch heads.

To regenerate the upstream delta in a clone containing both revisions:

```sh
git diff --no-renames --no-ext-diff --binary \
  --src-prefix=a/feeds/luci/ --dst-prefix=b/feeds/luci/ \
  50788da24e87bf2298dd7a2cebb13f533a8a6616 \
  20b3600d4d64bf60588cf4975c7a62104411870e > luci-update.patch
```

Compress with Python `gzip.compress(data, mtime=0)` and update both checksum
records when regenerating the maintained patch.

## Validation and rollout

Source reconstruction was compared against all 2,263 upstream files other
than `luci.mk`, whose only additional changes pin package metadata. File
contents, symlink targets and the absence of obsolete files were checked,
both outside Git and with the buildroot nested inside the repository. This
also checks that Git cannot silently skip the update in the latter case.

The repository test suite passed: 138 tests run, one skipped. Lua 5.1 syntax
checks passed for the staged modules, libraries and firewall application.
`defconfig` retained all 34 additional translation packages and the six
explicit scanner package selections.

The targeted build covers `feeds/luci/luci-lib-jsonc`,
`feeds/luci/luci-base` and `feeds/luci/luci-app-firewall`
using the repository's Ubuntu 18.04 / GCC 4.8 environment. The archived
downloader first tries the retired LEDE mirror, causing repeated timeouts
for uncached dependencies. `patches/userspace-source-mirrors.patch` removes
that mirror and prefers the
current OpenWrt source cache before mirror2. Explicit recipe URLs and archive
checksums are unchanged. The firewall, rpcd and iptables archives were fetched
from the current mirror and verified against all three archived recipe hashes.

The [targeted GitHub Actions build](https://github.com/FrancYescO/GUI_ipk/actions/runs/41929440547)
passed for source commit `f6d6715`. It produced 128 IPKs across six feed indexes.
The repository feed verifier passed; all 127 indexed packages matched their
recorded sizes and SHA-256 values. The raw artifact also retains an unindexed
libc toolchain side product, which is not advertised by the feed indexes.

All three LuCI targets report `git-21.041.07147-20b3600-1`. The parser and JSON
modules were checked as 32-bit little-endian ARM ELF binaries, and the packaged
`luci/version.lua` reports the pinned revision and `openwrt-18.06` branch.
These are build and artifact checks; router runtime validation and public feed
publication remain pending.

Before publishing a complete feed, test login/logout, the status and network
pages, saving a firewall rule and the installed translations on a test router.
Check the updated JSON integer handling on its 32-bit Lua runtime as well:

```sh
lua -e 'assert(require("luci.jsonc").parse("{\"n\":4294967296}").n == 4294967296)'
```

Keep a backup of `/etc/config` and the existing LuCI packages for rollback.
The historical 18.06 branch is not maintained upstream; this update only
incorporates the fixes already present in that branch.
