# GUI_ipk

OpenWrt package feed for the `brcm63xx-tch/VBNTS` target
(`arm_cortex-a9_neon`). Packages are compiled by GitHub Actions from the
archived custom OpenWrt 18.06 buildroot and its matching GCC 4.8/glibc
toolchain.

## What is built and where the sources come from

This repository has two independent build pipelines. The public userspace
feed comes from the archived **Technicolor OpenWrt 18.06 buildroot**; the
**Zyxel VMG8825-B50B GPL release** supplies the buildsystem and vendor kernel
sources used to reconstruct selected Damson kernel modules. The Zyxel GUI,
root filesystem and complete firmware image are not outputs of the Damson
module workflow.

| Pipeline / profile | Build inputs and configuration | Exported output |
| --- | --- | --- |
| `userspace` (default package workflow) | Archived VBNTS buildroot, prebuilt GCC 4.8 Linaro/glibc toolchain, [`build/userspace.config`](build/userspace.config) | Userspace `.ipk` packages, OPKG indexes and browsable package pages |
| `full` | Same VBNTS inputs, [`build/openwrt.config`](build/openwrt.config), including selected kernel packages | Package feed after removal of `kmod-*`; firmware images and standalone kernel images are not copied to `dist/` |
| `kmod-tun-4.1.38` | VBNTS kernel and [`build/kmod-tun.config`](build/kmod-tun.config), with the two repository TUN backports | Manual kernel-package artifact verified for VBNTS Linux 4.1.38 |
| `kmod-tun-vbnts-4.1.52` | Same VBNTS vendor tree plus the rebased Linux stable delta | Manual kernel-package artifact verified for VBNTS Linux 4.1.52 |
| Damson module sets | Pinned Zyxel GPL buildsystem, rebuilt GCC 5.5.0 toolchain, Damson kernel configuration and ABI patch | Selected `.ko` files, one manual-only IPK per runtime module, ABI canary and build metadata |

### Userspace package scope

[`scripts/build-packages.sh`](scripts/build-packages.sh) extracts a fresh
buildroot without archived `bin`, `build_dir` or `staging_dir` products, then
installs the matching prebuilt cross-toolchain and expands the selected seed
with `make defconfig`. The target is `brcm63xx-tch/VBNTS`, with package output
under `arm_cortex-a9_neon` and Cortex-A9/NEON compiler options.

With an empty `package_targets`, `make world` builds the selected packages
and their host tools and target/kernel prerequisites. `userspace` selects
`CONFIG_ALL` and `CONFIG_ALL_NONSHARED`, while
[`userspace-package-metadata.patch`](patches/userspace-package-metadata.patch)
separates `kmod-*` selection from those options. This means all userspace
recipes available **for this target in the archived snapshot**, subject to
their dependencies and availability; it does not mean every package in current
OpenWrt. Kernel preparation may still be needed for headers and dependencies.
`full` also enables `CONFIG_ALL_KMODS`.

The resulting feed sections reflect the archived recipes:

| Feed section | Recipe source / contents |
| --- | --- |
| `base` | Core OpenWrt userspace recipes, libraries and system utilities |
| `luci` | Archived LuCI applications, modules, themes and translations |
| `packages` | Archived packages feed, including additional networking tools and libraries |
| `routing` | Archived routing feed |
| `telephony` | Archived telephony feed |
| `target/packages` | Packages emitted under the VBNTS target output directory |

The snapshot's `feeds.conf.default` names the `openwrt-18.06` branches for
`packages`, `luci`, `routing` and `telephony`. The build uses the recipes
already present in the archive; it does not update these feeds to their latest
heads. The exact successful output of a run is its `Packages` indexes and IPK
artifact, rather than a fixed package count or the existing IPKs in this checkout.
With `package_targets` set, the script invokes `package/<recipe>/compile`
for each requested recipe and generates indexes instead of running `world`.

## Building packages

Use **Actions → Build OpenWrt packages → Run workflow**. Leave
the `userspace` profile and `package_targets` empty to build all userspace
packages. For a quicker targeted build, enter one or more OpenWrt recipe paths such as
`zlib` or `feeds/packages/curl`. Select `kmod-tun-4.1.38` or
`kmod-tun-vbnts-4.1.52` to build and inspect only the TUN kernel module for
that VBNTS kernel ABI.

Every run verifies the input archives by SHA-256, builds in Ubuntu 18.04 for
compatibility with the legacy toolchain, validates the generated package
indexes, and uploads the feed as a workflow artifact. A manual userspace or
full build can also publish the result to GitHub Pages.

Pull requests and pushes that change the build infrastructure or kernel patch
set build all userspace packages and upload the feed as an artifact. This can
take several hours. The `full` profile remains available manually to compile
kernel modules as well; kernel packages are removed from the shared feed.

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

That workflow profile targets VBNTS and must not be used for VBNTJ merely
because both kernels report Linux 4.1.x.

## Building Damson 4.1.52 kernel modules

Use **Actions → Damson 4.1.52 kernel-module artifacts → Run workflow** for
the Damson Linux 4.1.52 ABI reconstructed using the Zyxel GPL source and
router-matched adjustments. The workflow default is `router-tested` (the
standalone script defaults to `tun` when `MODULE_SET` is unset).

### Cross-reference with the Zyxel GPL release

The workflow pins [avwarez/vmg8825_b50b](https://github.com/avwarez/vmg8825_b50b)
at tag `V5.17(ABNY.6)C0`, commit
[`af23960e39003ba7788f5ced0c256b1bc676a712`](https://github.com/avwarez/vmg8825_b50b/tree/af23960e39003ba7788f5ced0c256b1bc676a712).
The GPL target is **Zyxel VMG8825-B50B**; `VBNTJ_502L07p1` identifies the
Technicolor Damson runtime being matched, not the name of the Zyxel GPL release.

| Evidence in the pinned GPL tree | Consequence for this build |
| --- | --- |
| [`configs/vmg8825_b50b/vmg8825_b50b.defconfig`](https://github.com/avwarez/vmg8825_b50b/blob/af23960e39003ba7788f5ced0c256b1bc676a712/configs/vmg8825_b50b/vmg8825_b50b.defconfig) | Selects `brcm963xx/vmg8825_b50b`, SDK `502L07` with `P1`, GCC `5.5.0`, glibc `2.26` and the `bcmsdk-502L07P1-` kernel patch prefix |
| [`target/linux/brcm963xx/Makefile`](https://github.com/avwarez/vmg8825_b50b/blob/af23960e39003ba7788f5ced0c256b1bc676a712/target/linux/brcm963xx/Makefile) | Maps SDK `502L07` to Linux `4.1.52` and extracts the Broadcom SDK during kernel preparation |
| [`target/linux/brcm963xx/vmg8825_b50b/target.mk`](https://github.com/avwarez/vmg8825_b50b/blob/af23960e39003ba7788f5ced0c256b1bc676a712/target/linux/brcm963xx/vmg8825_b50b/target.mk) | Sets `ARCH=arm`, `BRCM_CHIP=63138` and `BCM_PROFILE=VMG8825_B50B` |
| [`target/linux/brcm963xx/bcmsdk-502L07P1-patches-4.1`](https://github.com/avwarez/vmg8825_b50b/tree/af23960e39003ba7788f5ced0c256b1bc676a712/target/linux/brcm963xx/bcmsdk-502L07P1-patches-4.1) | Supplies the Broadcom kernel base patch and Zyxel integration/networking patches, rather than a vanilla Linux ABI |

[`scripts/build-vbntj-kmods.sh`](scripts/build-vbntj-kmods.sh) runs
`configs/preCfg.sh vmg8825_b50b`, `make defconfig`, the host GMP/MPFR/MPC
builds, `toolchain/install` and `target/linux/prepare`. The bootstrap obtains Linux
4.1.52 from kernel.org and checksum-pinned SDK/toolchain source archives from
[threader's DX5401 GPL mirror at commit `5df85c8c423ee935eed37b81f0d76dc569e2deb0`](https://github.com/threader/DX5401-B0-V517ABYO6C0_GPL/tree/5df85c8c423ee935eed37b81f0d76dc569e2deb0/dl).
The compiler is rebuilt as `arm-openwrt-linux-gnueabi-gcc` 5.5.0 with
binutils 2.28.1 and glibc 2.26; the VBNTS GCC 4.8 archive is not used here.
The compatibility container is Ubuntu 12.04, separate from the Ubuntu 18.04
container used for the userspace feed.

The original Zyxel seed mentions SDK patch `P1` and suffix `_200630`, but
neither option is defined in the pinned public Kconfig. A clean Linux
`make defconfig` removes both, while retaining
`CONFIG_CUSTOM_KPATCH_PREFIX="bcmsdk-502L07P1-"`. The normalized build therefore
requests **`broadcom_sdk_502L07_pkg.tar.bz2`**, not the P1-named SDK archive.
The script checks this configuration, converts the stored `.xz` to `.bz2`
and verifies the converted checksum before kernel preparation. This is the
base SDK combined with the GPL P1 kernel patch set, not a renamed P1 SDK.

### Preserved Damson build inputs

The [**`damson-build-inputs-v1` Release](https://github.com/FrancYescO/GUI_ipk/releases/tag/damson-build-inputs-v1)
is separate from the existing VBNTS `build-inputs-v1` Release. It stores all
ten source archives needed by the Damson module pipeline:

| Preserved input | Version / identity |
| --- | --- |
| Zyxel GPL buildsystem snapshot | `vmg8825_b50b`, commit `af23960e39003ba7788f5ced0c256b1bc676a712` |
| Linux | `4.1.52` |
| Broadcom SDK | `502L07`, original `.tar.xz` |
| binutils / GCC / glibc | `2.28.1` / `5.5.0` / `2.26` |
| GMP / MPC / MPFR / XZ | `6.1.0` / `1.0.3` / `3.1.4` / `5.0.4` |

[`build/vbntj/inputs.tsv`](build/vbntj/inputs.tsv) records each filename,
SHA-256, original URL, license summary and purpose;
[`inputs.sha256`](build/vbntj/inputs.sha256) provides the checksum list.
The Release also includes these as `INPUTS.tsv` and `SHA256SUMS`, plus
[`INPUTS.md`](build/vbntj/INPUTS.md). The GPL snapshot is made from the committed
Git tree with `git archive --format=tar COMMIT | gzip -n -6`, preserving bundled
components and their licenses without including local edits or generated state.
License summaries do not replace the embedded terms or relicense vendor binaries.

Normal builds use [`scripts/fetch-damson-build-inputs.sh`](scripts/fetch-damson-build-inputs.sh)
to obtain these inputs exclusively from this repository's Release, or reuse
cached files after verifying their digests against the **committed** manifest.
A missing Release/asset or incorrect digest fails the build; there is no silent
fallback to upstream. The workflow extracts the GPL snapshot on Linux, stages
the source archives and verifies them again in the build container. Installed
toolchains are cached separately and can be rebuilt from the preserved sources.

**Actions → Bootstrap Damson build inputs → Run workflow** downloads the
pinned originals, checks every archive and creates the Release once. It refuses
to replace an existing Release. To change inputs, create a new versioned tag
and update the committed manifest; do not overwrite `v1`. Upstream access is
limited to explicit bootstrap mode (run snapshot reseeding on Linux with GNU gzip):

```bash
# Normal local fetch from the preserved Release:
scripts/fetch-damson-build-inputs.sh
# Explicit reseeding from original upstreams, if needed:
DAMSON_INPUTS_MODE=bootstrap scripts/fetch-damson-build-inputs.sh
# Offline integrity check of cached inputs:
DAMSON_INPUTS_MODE=verify scripts/fetch-damson-build-inputs.sh
```

For a local Damson build, extract the verified GPL snapshot to a fresh
case-sensitive Linux filesystem, copy the other nine archives into its `dl/`
directory and mount it as `/app` in the `build/vbntj` container, with this
repository mounted at `/repo`. Run `/repo/scripts/build-vbntj-kmods.sh` with
`MODULE_SET` and `OUTPUT_DIR` as in the workflow. The build script requires
verified inputs to be staged first and makes no upstream downloads itself.

This removes upstream GPL/kernel/toolchain archive dependencies during normal
builds. Docker base images, Ubuntu package repositories, GitHub Actions and
GitHub Release availability remain external dependencies; this is not a fully
offline or hermetic build environment.

### Damson adjustments and module outputs

After GPL kernel preparation, the script replaces the kernel configuration
with [`kernel-4.1.52-damson.config`](build/vbntj/kernel-4.1.52-damson.config)
and applies [`001-damson-network-abi.patch`](patches/vbntj-4.1.52/001-damson-network-abi.patch).
The patch adds 32 bytes after `net_device.mc`, removes `sk_buff.in_dev`,
and preserves the WEXT options needed by the Damson layout. These are local
ABI reconstruction changes, not claims that the unmodified Zyxel kernel is
binary-compatible with Damson. `CONFIG_BCM_MAP` and `CONFIG_MODVERSIONS` are
disabled for this reconstruction.

| `module_set` | Runtime modules compiled | Purpose |
| --- | --- | --- |
| `tun` | `drivers/net/tun.ko` | TUN/TAP virtual network interfaces |
| `network-smoke` | `drivers/net/tun.ko`, `drivers/net/usb/usbnet.ko`, `drivers/net/usb/cdc_ether.ko` | Additional USB networking compilation checks |
| `qos-probe` | `net/sched/act_connmark.ko` | Traffic-control conntrack mark action; IFB, ingress, U32 and police stay built into the kernel configuration |
| `router-tested` (workflow default) | `drivers/net/tun.ko`, `net/sched/act_connmark.ko` | Builds both module types with documented router tests |

Every set also compiles the repository's
[`vbntj_abi_canary.ko`](build/vbntj-canary/vbntj_abi_canary.c), which checks
`sizeof(net_device)=0x4c0`, the offsets of `flags`, `mc.count` and `_tx`, and
`sk_buff.end` at compile time. It is included as a raw module, without an IPK.
Only the allowlisted module targets and this canary are compiled after
`modules_prepare`; enabling USB modules in the configuration does not export
them unless `network-smoke` is selected. This pipeline does not run `make world`
or replace the running kernel, Broadcom DSL/Wi-Fi drivers or Zyxel userspace.

Output goes to `dist/vbntj-kmods/`: stripped-debug `.ko` files, a
`kmod-<module>-damson-4.1.52-manual_4.1.52-1_brcm963xx.ipk` for each runtime
module, per-module `.undefined-symbols`, `SHA256SUMS` and `BUILD-METADATA.txt`.
Each IPK contains only `/lib/modules/4.1.52/<module>.ko`, with no installation
scripts or boot autoload entry. The workflow uploads these files as an Actions
artifact; the publish job creates versioned Release downloads under its branch
and module-set conditions, without adding them to the shared OPKG feed.

This separate workflow pins the GPL buildsystem and OpenWrt GCC 5.5.0,
prepares the kernel on a case-sensitive Linux filesystem, then applies the
Damson compatibility patch and the router-matched kernel configuration before
any module is compiled. It rejects wrong structure offsets, WEXT
configuration, compiler version, vermagic, or TUN undefined-symbol set. The
module selector is an allowlisted choice rather than an arbitrary shell
target. These build-time checks do not replace the runtime tests documented
for the exact TUN and connmark artifacts; `network-smoke` is a compilation
probe, not evidence of USB networking tests on the router.

The exact router-tested artifact and non-persistent test guidance are in
[`artifacts/README.md`](artifacts/README.md).

## Safe OPKG feed

The published OPKG feed is userspace-only. Kernel packages are deliberately
excluded because they depend on an exact vendor kernel ABI and can crash or
boot-loop a different firmware even when `uname` and vermagic look compatible.
Tested kernel modules remain manual artifacts and are never advertised to
OPKG.

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
