# GUI_ipk

OpenWrt package feed for the `brcm63xx-tch/VBNTS` target
(`arm_cortex-a9_neon`). Packages are compiled by GitHub Actions from the
archived custom OpenWrt 18.06 buildroot and its matching GCC 4.8/glibc
toolchain.

## Building packages

Use **Actions → Build OpenWrt packages → Run workflow**. Leave
the `full` profile and `package_targets` empty to build the complete feed. For
a quicker targeted build, enter one or more OpenWrt recipe paths such as
`zlib` or `feeds/packages/curl`. Select `kmod-tun-4.1.38` or
`kmod-tun-4.1.52` to build and inspect only the TUN kernel module for that
VBNTS kernel ABI.

Every run verifies the input archives by SHA-256, builds in Ubuntu 18.04 for
compatibility with the legacy toolchain, validates the generated package
indexes, and uploads the feed as a workflow artifact. A manual full build can
also publish the result to GitHub Pages.

Pull requests and pushes that change the build infrastructure or kernel patch
set run the `kmod-tun-4.1.38` profile. Full builds are manual because the full
configuration selects more than 1,400 packages and can take several hours.

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

To reproduce the conservative 4.1.38 TUN backport locally, use the same image
with the dedicated configuration:

```bash
docker run --rm --platform linux/amd64 --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -e WORK_DIR=/tmp/openwrt -e BUILD_CONFIG=/repo/build/kmod-tun.config \
  -e PACKAGE_TARGETS=kernel/linux -e KERNEL_VERSION=4.1.38 \
  -e VERIFY_KMOD_TUN=1 \
  -v "$PWD:/repo" gui-ipk-builder
scripts/verify-feed.sh dist
```

This profile backports only the empty `IFF_NO_PI` frame guard and the invalid
`TUNSETSNDBUF` rejection from Linux 4.1.52. It deliberately does not backport
the `dev_get_valid_name()` change because that symbol is not exported by the
4.1.38 tree. The resulting package is tied to the VBNTS Linux 4.1.38 ABI.

For 4.1.52, use the same command with `KERNEL_VERSION=4.1.52`. That kernel
already contains the two TUN fixes and exports `dev_get_valid_name`, so the
4.1.38-only backport patches are not applied. The verifier checks the selected
vermagic and source before accepting the package. Keep 4.1.52 artifacts on a
separate branch because their module ABI differs from the stock 4.1.38 build.
The build applies the official 4.1.38-to-4.1.52 stable changes, rebased onto
the Technicolor patch stack, after the vendor patches. Applying the Broadcom
base patch directly to a pristine 4.1.52 tree is not supported.

To use this repo /etc/opkg.conf MUST be changed and include this 4 lines

```bash
arch all 100
arch brcm63xx 200
arch brcm63xx-tch 300
arch arm_cortex-a9 400
```

[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.me/AnsuelS)
