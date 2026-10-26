# GUI_ipk

OpenWrt package feed for the `brcm63xx-tch/VBNTS` target
(`arm_cortex-a9_neon`). Shared packages are compiled by GitHub Actions from the
archived custom OpenWrt 18.06 buildroot and its matching GCC 4.8/glibc
toolchain.

Newer optional ARM applications use pinned static SDKs. See
[application updates](docs/application-updates.md) for versions, completed router
checks, installation requirements and publication status.

### OpenVPN backport

The userspace recipe overlay in `build/userspace-overlay/` updates OpenVPN
from 2.4.5 to **2.6.23**, with OpenSSL and mbedTLS variants, and adds libcap-ng
0.8.5. It uses the archived OpenSSL 1.0.2t / mbedTLS 2.16.3 libraries; updating
OpenVPN alone does not update those libraries. OpenVPN 2.7 requires newer TLS
libraries. The obsolete plaintext `openvpn-nossl` variant is no longer built.
DCO is disabled: this build uses the existing TUN interface and does not
introduce a new kernel module. LZ4 support now depends on `liblz4`.

The upstream [DCO documentation](https://github.com/OpenVPN/openvpn/blob/v2.6.23/README.dco.md) documents Linux 5.4 or
newer as known working. The vendor 4.1.38/4.1.52 kernels in this repository
are outside that baseline; a DCO module would require a separate driver
backport and ABI/runtime validation, not just enabling the OpenVPN flag.

For a targeted build, set `package_targets` to
`network/services/openvpn` in the userspace profile; its build path prepares
the kernel headers and host tools required by the archived snapshot.
Install one TLS variant and its dependencies. Before upgrading a router,
back up the configuration and review the OpenVPN 2.6 migration notes:
old directives such as `ns-cert-type`, `keysize`, and `ncp-disable` were
removed. Use `data_ciphers` and, only when required by an older peer,
`data_ciphers_fallback` in UCI. Raw `.conf` files use hyphenated names.
An existing `cipher` setting alone does not select TLS data-channel ciphers
in 2.6. The UCI allowlist includes the new cipher and TLS options.

The verified IPKs and provenance are in
[`artifacts/openvpn-2.6.23`](artifacts/openvpn-2.6.23/README.md). Pages publication
applies these four packages over the assembled userspace feed, preserving
other packages and retiring the old plaintext variant.

## Building packages

Use **Actions → Build OpenWrt packages → Run workflow**. Leave
`package_targets` empty to build every userspace package. For a quicker targeted
build, enter one or more OpenWrt recipe paths such as `zlib` or
`feeds/packages/curl`.

Every run verifies the input archives by SHA-256, builds in Ubuntu 18.04 for
compatibility with the legacy toolchain, validates the generated package
indexes, and uploads the feed as a workflow artifact. A manual full build also
publishes the result to GitHub Pages by default; clear `publish_pages` to keep
the build as artifacts only.

Kernel and package-overlay publications preserve the latest successful complete
userspace feed artifact. If no valid complete artifact is available, publication
stops and keeps the live site intact. The `reuse_userspace_run_id` input can
select a specific successful baseline.

Pull requests and pushes that change the build infrastructure run the full
userspace build. It can take several hours.

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

## OPKG feeds

The six shared feeds contain userspace packages. Kernel IPKs are split into
[`kernel/4.1.38`](https://francyesco.github.io/GUI_ipk/kernel/4.1.38/) and
[`kernel/4.1.52`](https://francyesco.github.io/GUI_ipk/kernel/4.1.52/).
The DGA4131FWB / VBNT-O firmware 18.3.n.0439 has a different 4.1.38 ABI;
its router-tested TUN, SPU and WireGuard modules use the separate
[`kernel/4.1.38-vbnto`](https://francyesco.github.io/GUI_ipk/kernel/4.1.38-vbnto/)
feed, with an exact kernel dependency and no boot autoload. See
[`artifacts/vbnto-4.1.38-manual/README.md`](artifacts/vbnto-4.1.38-manual/README.md)
for the validation and firmware identity.
The 4.1.38 feed contains a virtual kernel ABI package and 19 `kmod-*` IPKs
built from the archived VBNTS buildroot. Thirteen IPKs contain `.ko` files;
six are empty dependency packages for modules built into this kernel. The
kernel IPK contains no image and cannot upgrade a router. The compiled ABI
hash differs from the older virtual kernel package in this repository, so
verify the firmware's exact kernel ABI before installing any module. These
packages have not been tested on a router. They do not include the separate
Damson 4.1.52 ABI adaptation and must not be used on VBNT-K Damson.

The two router-tested 4.1.52 manual modules target Damson `19.4.0866-3401052` on VBNT-K with
kernel `4.1.52` and architecture `brcm963xx`. Check the exact firmware and
module ABI before installing one. A matching Linux version alone is not
sufficient. Additional 4.1.52 modules are build-verified only and should be
tested as raw `.ko` files from `/tmp` before any persistent installation.
The kernel feed is not part of the userspace source list below.

The `kernel/4.1.52` feed also includes the router-tested `cdc_ether` and
`rndis_host` compatibility pair from PR #7, using architecture `arm_cortex-a9`.
Both modules support miscellaneous-class USB RNDIS (`ef/04/01`) and must be
used together with the firmware's native `usbnet`. Their IPKs have no boot
autoload entries or installation scripts. They target the exact Damson
firmware above; the publication workflow verifies their checksums and payloads
before indexing both packages and deploying the feed.

Browse and search the published packages at
[francyesco.github.io/GUI_ipk](https://francyesco.github.io/GUI_ipk/).
Each feed section has its own package list and direct IPK download links.

Add the package feeds with:

```text
src/gz gui_base https://francyesco.github.io/GUI_ipk/base
src/gz gui_luci https://francyesco.github.io/GUI_ipk/luci
src/gz gui_packages https://francyesco.github.io/GUI_ipk/packages
src/gz gui_routing https://francyesco.github.io/GUI_ipk/routing
src/gz gui_telephony https://francyesco.github.io/GUI_ipk/telephony
src/gz gui_target https://francyesco.github.io/GUI_ipk/target/packages
```

On the exact Damson firmware above, add the kernel feed separately if needed:

```text
src/gz gui_kernel_4_1_52 https://francyesco.github.io/GUI_ipk/kernel/4.1.52
```

The following architecture priorities are also required:

```bash
arch all 100
arch brcm63xx 200
arch brcm63xx-tch 300
arch arm_cortex-a9 400
```

Do not run a blanket `opkg upgrade` on vendor firmware. Install only the
specific packages needed and review replacements of core components
such as BusyBox, `procd`, OpenSSL or the package manager itself.

[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.me/AnsuelS)
