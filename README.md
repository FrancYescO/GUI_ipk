# GUI_ipk

OpenWrt package feed for the `brcm63xx-tch/VBNTS` target
(`arm_cortex-a9_neon`). Packages are compiled by GitHub Actions from the
archived custom OpenWrt 18.06 buildroot and its matching GCC 4.8/glibc
toolchain.

## Building packages

Use **Actions → Build OpenWrt packages → Run workflow**. Leave
`package_targets` empty to build the complete feed. For a quicker targeted
build, enter one or more OpenWrt recipe paths such as `zlib` or
`feeds/packages/curl`.

Every run verifies the input archives by SHA-256, builds in Ubuntu 18.04 for
compatibility with the legacy toolchain, validates the generated package
indexes, and uploads the feed as a workflow artifact. A manual full build can
also publish the result to GitHub Pages.

Pull requests and pushes that change the build infrastructure run a `zlib`
smoke build; full builds are manual because this configuration selects more
than 1,400 packages and can take several hours.

The two source archives are deliberately not committed, extracted, or kept on
an orphan branch: together they are about 908 MB compressed, expand beyond
1 GB, contain generated build state, and each exceeds GitHub's normal file-size
limit. Keeping tens of thousands of legacy files in Git would permanently slow
down every clone and fetch.

Instead, run **Actions → Bootstrap build inputs** once. It verifies the original
downloads and stores them in the immutable `build-inputs-v1` Release of this
repository. Normal builds fetch them from that same Release and cache them in
Actions; the original locations are only a bootstrap/fallback:

- [matching toolchain](https://mega.nz/#!V98jBIZQ!KNSVwznEz9mwJG18bkJoY-pLzn_NSvlJRCwMubKLsLs)
- [custom OpenWrt buildroot](https://mega.nz/#!Mpd2lK6B!Wqu7kcpkgxU_oK8AKBsTJWJ2CVIg7idmV19k1_zkvX0)

For local Linux builds (or Docker on macOS), keep those files in
`.cache/sources/` and run:

```bash
scripts/fetch-build-inputs.sh
docker build --platform linux/amd64 -t gui-ipk-builder -f build/Dockerfile .
docker run --rm --platform linux/amd64 --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -e WORK_DIR=/tmp/openwrt -e PACKAGE_TARGETS=zlib \
  -v "$PWD:/repo" gui-ipk-builder
scripts/verify-feed.sh dist
```

## Safe OPKG feed

The published OPKG feed is userspace-only. Kernel packages are deliberately
excluded because they depend on an exact vendor kernel ABI and can crash or
boot-loop a different firmware even when `uname` and vermagic look compatible.
Tested kernel modules remain manual artifacts and are never advertised to
OPKG.

Add the package feeds with:

```text
src/gz gui_base https://francyesco.github.io/GUI_ipk/base
src/gz gui_luci https://francyesco.github.io/GUI_ipk/luci
src/gz gui_packages https://francyesco.github.io/GUI_ipk/packages
src/gz gui_routing https://francyesco.github.io/GUI_ipk/routing
src/gz gui_telephony https://francyesco.github.io/GUI_ipk/telephony
src/gz gui_target https://francyesco.github.io/GUI_ipk/target/packages
```

The following architecture priorities are also required:

```bash
arch all 100
arch brcm63xx 200
arch brcm63xx-tch 300
arch arm_cortex-a9 400
```

Adding the feed is safe from cross-kernel module installation, but a blanket
`opkg upgrade` is still not recommended on vendor firmware. Install only the
specific userspace packages needed and review replacements of core components
such as BusyBox, `procd`, OpenSSL or the package manager itself.

[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.me/AnsuelS)
