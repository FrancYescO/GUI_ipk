# VBNT-S Linux 4.1.38 runtime ABI

Runtime profile from the DGA4132 at 192.168.133.204, Homeware 18.3.k.0451.
Exact OPKG kernel version: `4.1.38-1-8dd693635a152c8c7b822a64e6c5c470`.
`kernel.config.gz` contains the kernel configuration only, no user configuration.

The public **VBNT-S Linux 4.1.38 kernel modules** workflow compiles all available
modules selected by the runtime configuration, plus WireGuard, optional QoS
(including act_connmark for DumaOS), and iPhone / CDC EEM / CDC MBIM USB tethering.
RNDIS, CDC Ethernet/NCM, QMI, WDM and USB serial dependencies are priority targets.
Every existing enabled or built-in option is preserved. Missing priority modules
fail the build; incomplete vendor driver compilation is retained in diagnostics.

Router-tested TUN, WireGuard and SPU are in `artifacts/vbnts-4.1.38-manual` and
published in the separate `kernel/4.1.38-vbnts` OPKG feed. The generic 4.1.38 and
VBNT-O feeds have different ABIs and are not substitutes for this profile.

Expanded modules are published as a separate public prerelease with staged IPKs,
raw modules, hashes, build config and diagnostics. Candidate packages use their
own VBNT-S package names and `/usr/lib/kernel-module-candidates/4.1.38-vbnts/`;
installing them cannot replace stock boot modules or autoload untested code.
They have an exact kernel dependency and no maintainer scripts. The xt_nat
candidate remains quarantined across profiles pending investigation of the
previous crash. Compilation is not runtime validation or a USB tethering test.
