# Homeware integration baseline

`catalog.tsv` is the recorded compatibility inventory from 2026-10-22: 4,068 package files for generation 18 and 494 for generation 19, representing 4,066 and 494 distinct package names respectively. Names, versions and architectures are inferred from the recorded filenames, not their internal control metadata.

The catalog preserves names containing underscores, including `rtl_433` and `ddns-scripts_freedns_42_pl`. It is a recorded baseline, not an automatically refreshed mirror. Homeware 18 and 19 do not establish a kernel or libc ABI, and their packages are not downloaded into the shared feed.

`../homeware-overlay/` imports complete recipes and their local files from immutable official OpenWrt feed revisions. `SOURCES.json` records each origin; `SHA256SUMS` pins the imported bytes. The userspace build verifies those hashes, installs the overlay and registers its package links before `make defconfig`:

- `banip` 0.3.11-2 from the OpenWrt 19.07 packages feed;
- `https-dns-proxy` 2021-01-17-1 from the OpenWrt 18.06 packages feed;
- `luci-app-https-dns-proxy` and the transitional `luci-compat` package from LuCI 18.06.

This adds the missing recipes without replacing the existing libc, LuCI framework or library ABI names. Existing archived userspace recipes remain selected through `CONFIG_ALL`; recipe presence alone is not proof of a successful build or runtime support. Packages that require existing firmware kernel features retain that runtime requirement.

Generate the coverage report for a feed:

```sh
python3 scripts/report-homeware-coverage.py build/homeware/catalog.tsv dist
```

Add `--metadata /path/to/buildroot/tmp/.packageinfo --config /path/to/buildroot/.config` to distinguish missing recipes, disabled packages and selected packages not built. Per-shard reports describe the IPKs available in that shard, including dependencies; only the aggregate report measures the complete merged feed. Exact package names are compared across sections; versions are shown without treating newer ABI names as equivalents. Missing coverage is diagnostic and does not bypass the existing feed validation or shard checks.

The archived LuCI makefile also treated loose `.pot` template files as language directories. The userspace patch limits translation packages to directories, preventing an empty `luci-i18n-https-dns-proxy-https-dns-proxy.pot` package and its invalid UCI language registration. That malformed package remains in the baseline because it was present in the recorded inventory.

The proxy backport explicitly enables GNU99 for the GCC 4.8 toolchain. Reports use relative recorded filenames and contain no external repository download links.

The userspace profile keeps module metadata for dependency selection, but omits kernel IPK packaging and kernel compilation from mixed userspace/module recipes. Module overrides use empty Make values, because a literal `n` still evaluates as nonempty in several archived recipes. Runtime kernel requirements are retained in package metadata.

Additional compatibility fixes declare aMule's `libbfd` dependency, recover GCC 5.4 libgcc mode detection when bootstrapping with ARM GCC 4.8, and limit swconfig's structured-link code to headers that actually expose the necessary vendor UAPI. These changes preserve the firmware's header values and do not claim support for missing kernel features.
