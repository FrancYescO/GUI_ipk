# Exact-ABI firmware kernel feeds

Five firmware profiles are compiled from the pinned GPL buildsystem,
Broadcom 502L07 SDK, GCC 5.5.0 and repository ABI/backport patches. These are
**installable packages with per-module validation levels**. Public packages use `/lib/modules/4.1.52/`; immutable source bundles retain their original staging layout for reproducibility.

| Feed on Pages | Original reference firmware | Architecture / vermagic | Packages |
|---|---|---|---:|
| `kernel/4.1.52-vcnt3` | DGA4331 / VCNT-3, AGTHF 1.3.0 and 1.1.2 | `arm_cortex-a9`, `4.1.52 SMP preempt mod_unload ARMv7` | 49 |
| `kernel/4.1.52-vcnt2` | DWA0122 / VCNT-2, Belong 19.4.l.0393-MR1-RB and 19.4.0381-4961004 | `arm_cortex-a7`, `4.1.52 SMP preempt mod_unload ARMv7 p2v8` | 49 |
| `kernel/4.1.52-vcntj` | DGA4134 / VCNT-J, Sorgenia 19.4.0629-5661052 | `arm_cortex-a7`, `4.1.52 SMP preempt mod_unload ARMv7 p2v8` | 49 |
| `kernel/4.1.52-vcnta` | DJA0231 / VCNT-A, Telstra 20.3.c.0501-MR22.1 | `arm_cortex-a9`, `4.1.52 SMP preempt mod_unload ARMv7` | 48 |
| `kernel/4.1.52-vbntv` | DJA0230 / VBNT-V, Telstra 20.3.c.0432-MR21.1 | `arm_cortex-a9`, `4.1.52 SMP preempt mod_unload ARMv7` | 48 |

Enable a source only after matching its complete virtual kernel package version. The source-selection helper now includes all five feeds automatically when the exact ABI matches.
The exact source lines are in the public kernel overview and each feed's
`opkg.conf`. These profiles cannot be interchanged despite sharing Linux 4.1.52.

The module set contains the existing network, netfilter and QoS targets, TUN,
WireGuard 1.0.20220627, CDC Ethernet, RNDIS and USBnet. SPU is not included:
VCNT-3, VCNT-2 and VCNT-J disable it; Telstra enables vendor implementation 3, which needs separate ABI checks. `xt_nat` remains quarantined across
profiles and was not loaded or tested. Published IPKs contain a single module under `/lib/modules/4.1.52/`, exact kernel/dependency versions and a pre-install ABI guard. They do not load modules or add boot autoload files. Stock-owned dependencies are reused; replacing a stock module itself requires the controlled migration helper. The archived source IPKs retain their original layout and hashes. TUN is already built into both Telstra kernels, so their feeds omit `tun.ko` and contain 48 packages each. The audit rejects modules that duplicate exports built into the kernel.

## Input recovery and checks

`scripts/extract-kernel-firmware.py` decodes an original RBI, decompresses the
kernel and extracts its embedded IKCONFIG without contacting a router. It also
accepts a decrypted image or raw bank dump. RBI decoding uses Python
`cryptography`; the kernel/ELF checks use the standard library. Extract stock
files with `unsquashfs` on a **case-sensitive filesystem** before invoking it.

VCNT-3 images require LZMA layers at offsets 38 and 16,836. The VCNT-2 RBI/bank dump
and VCNT-J bank dumps require only the layer at offset 38. Telstra VCNT-A and VBNT-V require layers at 38 and 16,820. The program locates absolute ARM export
tables using independent symbol anchors, parses stock ELF modules, and refuses
an input whose kernel and stock-module exports do not resolve every stock
module's strong imports. The checked inputs contain 267 stock modules per
VCNT-3 image, 255 for VCNT-2, 259 for VCNT-J, 287 for VCNT-A and 288 for VBNT-V.

The historical Git extraction of AGTHF 1.1.2 has at least one case-collision
error (`xt_DSCP.ko`). Its audit therefore uses stock modules directly from the
original RBI. All 267 modules of AGTHF 1.3.0 were independently compared with
the pinned Git extraction and match. The two original VCNT-3 configurations
have identical option values, although their formatting differs. Twelve
inventory entries share the 1.3.0 kernel package, source reference and complete
stock-module set; this is recorded as stock equivalence, not runtime validation.

Input hashes, exact kernel dependencies, recovered configurations, original
stock-symbol inventories and compiler/source references are committed under
`build/kernel-firmware-profiles/`. No original firmware image, router credentials
or personal router configuration is needed by the build workflow.

The proven SDK configuration is adapted using differences between the original
VBNT-K runtime configuration and each original target configuration. This
preserves 22 VCNT-3-specific changes and 440 VCNT-2-specific changes before
Kconfig resolves dependencies. Required platform and changed Broadcom kernel-feature ABI options are
checked again after `olddefconfig`. The new configurations have 445 differences for VCNT-J, 175 for VCNT-A and 172 for VBNT-V relative to the reference; the exact counts are pinned in the profile definitions. The build records its final configuration.
Matching symbols and configuration do **not** prove every structure layout,
vendor patch or functional behavior. Device validation is still required.

## CI reproduction and publication

`Firmware kernel candidates` builds each profile independently from pinned GPL
sources and the verified compiler seed. It builds the allowlisted modules,
removes debug information and path-dependent build IDs, audits imports against
each pinned original-firmware symbol inventory, and deterministically rebuilds
the IPKs. WireGuard uses the canonical `/app/.wireguard-linux-compat` source
path to keep its `__FILE__` diagnostics stable. CI compares the complete generated
bundle SHA256 with the committed bundle; it does not merely repackage saved
modules. Compiler outputs and logs are retained as workflow artifacts.

The single Pages publisher restores these small verified bundles from the
repository, repeats ELF, dependency, staging-path and symbol checks, and publishes
their IPKs and evidence pages. No additional binary Release or assets split is
introduced. Existing userspace updates remain unchanged.

## Correction found by the offline audit

The SDK's conntrack source included Altibox UDP timeout and proc hooks requiring
`nf_ct_udp_STB_port` and `nf_ct_udp_STB_timeout`. Neither is exported by the
original checked Technicolor kernels or their stock modules. The new source
patch removes those SDK-only hooks while preserving Broadcom derived timeouts.

This also affected the previous VBNT-K 4.1.52 `nf_conntrack` candidate, which
had been skipped during runtime probing because the native module was busy.
Its replacement is package revision `4.1.52-2`, checked against the original
AGTEF 2.4.5 image and all 269 stock modules. All 49 published VBNT-K payloads now
have complete offline symbol closure. The replacement has not been loaded or
functionally tested; its previous payload and busy observation remain in the
validation history. No stock module was unloaded for this correction.

## Newer firmware and acquisition limits

AGTHF 1.3.6 is already mapped to the VCNT-3 exact-ABI feed because its kernel package, kernel source reference and all 267 stock module blobs match 1.3.0. This is stock equivalence only: the full 1.3.6 RBI could not be downloaded from the TIM server or public mirror, so no direct embedded configuration validation is claimed. The identical-hash CDC/RNDIS pair was subsequently tested on a VCNT-3 device as documented below.

VCNT-2 19.4.l.0393-MR1-RB was recovered from its public torrent after the HTTP/HTTPS server timed out. Its exact kernel package matches the older bank dump. The embedded configuration differs only in `CONFIG_NETFILTER_NETLINK_LOG` and `CONFIG_NETFILTER_XT_TARGET_NFLOG`, both enabled as modules in the newer image. The newest configuration is now the build reference, and the same 49 payloads are checked against both complete kernel/stock export inventories. All 255 new stock modules also match the historical Git extraction. No additional feed is needed.

Fastweb FW261/FW264 still require an original image; a saved runtime configuration remains an alternative.

The available VCNT-J Sorgenia image and latest inventoried Telstra images were therefore processed next. Each has a dedicated exact-dependency feed. Their modules remain offline checked except for the documented VCNT-3 USB pair. Other kernel releases and CPU families need their own source, toolchain and ABI checks.

## Publication and device validation — 2026-11-11

VCNT-3 CDC Ethernet and RNDIS host payloads passed explicit loading, Xiaomi Mi
10T Lite RNDIS binding, usb0 carrier at 480 Mbit/s and a DHCP lease probe.
Evidence is pinned by ELF SHA256 in `build/kernel-firmware-profiles/runtime-validation.json`.
Reboot persistence, reconnect and Internet traffic were not tested. This does
not validate DumaOS or the other modules. The remaining modules are labelled
`offline-checked` individually; these labels do not prevent installation.

The five canonical feed names no longer end in `-candidates`. Previous URLs
serve alias indexes pointing to the canonical IPKs. Public physical package
names use `-manual` instead of `-candidate`; old staging packages are not
automatically removed. Existing stock or staged installations require reviewed
migration with consumers stopped and the target module unloaded, followed by
removal of obsolete staging packages if present. No package hook forces file
ownership, unloads a driver or enables automatic loading.
