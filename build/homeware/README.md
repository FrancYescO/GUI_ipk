# Homeware integration baseline

`catalog.tsv` records all 4,562 IPK links observed in the public Homeware directory listings on 2026-10-22: 4,068 from Homeware 18 and 494 from Homeware 19. These represent 4,066 and 494 distinct package names respectively. Directory listings were read in the browser after Cloudflare verification; the OPKG indexes and README downloads could not be retrieved. Package names, versions and architectures therefore come from filenames, not control metadata.

Sources:

- https://repository.macoers.com/homeware/18/brcm63xx-tch/VANTW/
- https://repository.macoers.com/homeware/19/brcm6xxx-tch/VANTW/

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
