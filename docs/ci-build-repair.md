# Complete userspace CI repair and device-profile audit

The complete build of main `bc89c2a` failed independently of the successful
targeted LuCI build. The failed run is 41940459355.

## Observed failures and corrections

- Shards 12 and 13 exhausted the hosted runner disk, including the runner log
  filesystem. The workflow frees unused host SDKs on GitHub-hosted runners
  and checks available space before restoring the large archived inputs.
- Shards 1, 6, 7 and 10 compiled packages but had no OPKG indexes for the
  coverage reporter. The sharded path now generates indexes before export,
  just like the direct-target and complete-package paths.
- The archived buildsystem replaces `GIT_CONFIG_PARAMETERS` and its Git 2.17
  does not use the newer `GIT_CONFIG_GLOBAL` override. The HTTPS rewrite now
  lives in the actual make export, preserving all pinned source revisions.
  All four routing commits were verified to exist at their upstream locations.
- rssileds links libnl-tiny directly but omitted its runtime dependency.
- hostapd's taxonomy caller must use the same `NEED_AP_MLME` guard as the
  provider in beacon.c. The fix preserves taxonomy when MLME is built and
  avoids an undefined reference in non-MLME variants; it does not disable
  the feature for valid wireless builds. The mesh supplicant also explicitly
  enables MLME, which its mesh/SAE objects require even when the selected
  driver does not enable it implicitly.
- MPD 0.20.9 needs C++14 and the bundled ZeroTier JSON header rejects GCC 4.8.
  Their versions and compiler checks remain unchanged. An explicit package
  constraint makes these recipes unavailable to the pinned 4.8 toolchain.
  Coverage still counts them as missing and reports `toolchain-unavailable`
  with the metadata constraint, rather than pretending they were built.

## Device and kernel management remains intact

The model/profile registries, per-firmware kernel configurations, package ABI
records and pinned candidate bundles are unchanged from pre-consolidation
main `bee39fd`. Kernel candidate and cryptodev workflows on `bc89c2a` passed.

Runtime feeds remain for DGA4131FWB (4.1.38 VBNT-O), DGA4132 (canonical
4.1.38 VBNT-K feed), and DGA4130/VBNT-K (4.1.52). Original source aliases,
including the 4.1.38 VBNT-S source identity, remain distinct from public
canonical names. Selection uses the complete kernel package identifier.

The five separate 4.1.52 candidate profiles remain:

| Profile | Device | Package architecture | Modules |
| --- | --- | --- | ---: |
| VCNT-3 | DGA4331 | arm_cortex-a9 | 49 |
| VCNT-2 | DWA0122 | arm_cortex-a7 | 49 |
| VCNT-J | DGA4134 | arm_cortex-a7 | 49 |
| VCNT-A | DJA0231 | arm_cortex-a9 | 48 |
| VBNT-V | DJA0230 | arm_cortex-a9 | 48 |

The 48-module profiles preserve stock builtin TUN instead of packaging it.
Candidate status is still offline-checked, not a claim of hardware runtime
validation. The inventory retains 281 firmwares: 118 with Linux 3.4.11,
55 with 4.1.38, 14 with 4.1.45 and 94 with 4.1.52. Inventory-only entries
and planned Fastweb FW261/FW264 work are not advertised as installable feeds.
