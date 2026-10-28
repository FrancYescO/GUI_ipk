# Firmware kernel candidates from static images

Two additional firmware profiles are compiled from the pinned GPL buildsystem,
Broadcom 502L07 SDK, GCC 5.5.0 and repository ABI/backport patches. These are
**offline-checked candidates, not runtime-validated modules**.

| Feed on Pages | Original reference firmware | Architecture / vermagic | Packages |
|---|---|---|---:|
| `kernel/4.1.52-vcnt3-candidates` | DGA4331 / VCNT-3, AGTHF 1.3.0 and 1.1.2 | `arm_cortex-a9`, `4.1.52 SMP preempt mod_unload ARMv7` | 49 |
| `kernel/4.1.52-vcnt2-candidates` | DWA0122 / VCNT-2, Belong 19.4.0381-4961004 | `arm_cortex-a7`, `4.1.52 SMP preempt mod_unload ARMv7 p2v8` | 49 |

Enable a candidate source manually only after matching its complete virtual
kernel package version. The source-selection helper does not enable candidates.
The exact source lines are in the public kernel overview and each feed's
`opkg.conf`. The two profiles cannot be interchanged despite sharing Linux 4.1.52.

The module set contains the existing network, netfilter and QoS targets, TUN,
WireGuard 1.0.20220627, CDC Ethernet, RNDIS and USBnet. SPU is not included:
both original configurations disable it. `xt_nat` remains quarantined across
profiles and was not loaded or tested. IPKs contain a single module under
`/usr/lib/kernel-module-candidates/<profile>/`, an exact kernel dependency and
no maintainer scripts or boot autoload files.

## Input recovery and checks

`scripts/extract-kernel-firmware.py` decodes an original RBI, decompresses the
kernel and extracts its embedded IKCONFIG without contacting a router. It also
accepts a decrypted image or raw bank dump. RBI decoding uses Python
`cryptography`; the kernel/ELF checks use the standard library. Extract stock
files with `unsquashfs` on a **case-sensitive filesystem** before invoking it.

VCNT-3 images require LZMA layers at offsets 38 and 16,836. The VCNT-2 bank dump
requires only the layer at offset 38. The program locates absolute ARM export
tables using independent symbol anchors, parses stock ELF modules, and refuses
an input whose kernel and stock-module exports do not resolve every stock
module's strong imports. The checked inputs contain 267 stock modules per
VCNT-3 image and 255 for VCNT-2.

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
checked again after `olddefconfig`. The build records its final configuration.
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

## Remaining profile order

VCNT-3 was first, followed by VCNT-2 because a complete public bank dump and
matching SDK support were available. Fastweb FW261/FW264 remain next once a
complete original RBI or bank image can be acquired. Their server did not
respond and the bounded public torrent attempt downloaded no data. An SSH
runtime configuration is an alternative input, not a requirement.

Other kernel releases and CPU families require their own source, toolchain and
ABI checks. The newer VCNT-2 19.4.l.0393 firmware and older VCNT-3 ABI groups are
not claimed compatible solely because their Linux version or kernel package
fingerprint resembles a checked profile.
