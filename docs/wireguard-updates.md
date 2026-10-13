# WireGuard updates for legacy Technicolor kernels

## Sources

- `wg`: wireguard-tools 1.0.20260223, SHA256
  `af459827b80bfd31b83b08077f4b5843acb7d18ad9a33a2ef532d3090f291fbf`.
  Recipe from OpenWrt commit `c3ac7296bf46fce3d0e88d435b8e3291943035c2`.
- Shell netifd helper and watchdog from OpenWrt commit
  `33063b4ccf00d39393796499b23df55187b192dc`. Current OpenWrt uses ucode;
  this firmware retains its shell protocol API.
- Module: wireguard-linux-compat 1.0.20220627, SHA256
  `19b181e5c7d2260c23ecad4ad324425fd8e88200d97a885a2c7d4bd26cd61461`.
  This is the legacy backport for Linux 4.1, not the current in-tree module.
- Damson integration adapts PR #1 by HAL9000RELOADED, commit
  `ce8d5b7cedc3577c4f1f27358fdc8e4b173757fe`, to the current build scripts.
  Its fallthrough correction is shared by both kernel builds.

## Separate builds

1. Userspace workflow, targeted recipe `network/utils/wireguard-tools`.
2. Linux 4.1.38 workflow, `module_set=wireguard`: TUN/connmark with their
   existing kernel fixes, UDP tunnel dependencies and WireGuard backport.
3. Damson 4.1.52 workflow, `module_set=wireguard`: matching Broadcom GPL
   SDK, Damson ABI patch and canary, plus the external WireGuard module.

Tools depend on `ip` and do not force an unverified module installation.
The archived combined 2019 recipe is replaced with independent recipes.
A matching kernel module is still required to use the VPN. The 4.1.38
package has no autoload entry; the 4.1.52 IPK remains manual-only with no
maintainer scripts. Neither is added to the published feed by these tests.
WireGuard requires `udp_tunnel` and `ip6_udp_tunnel` from the matching
firmware/kernel. On Damson use existing stock dependencies when present.

## Verification status

Source hashes, patch application and shell syntax checked locally.
The wg 1.0.20260223 cross-build succeeded in run 38301065585.
Both kernel builds produced modules and reached verification; the initial
verifier rejected the conventional trailing space in vermagic. This is
fixed by trimming trailing whitespace before comparing all version/options.
Kernel cross-build verification is being repeated. Failed verifications
now also retain the generated artifacts for inspection. Workflow verification checks the ARM ELF,
full vermagic and UDP tunnel module dependencies. The Damson canary checks
selected kernel structure layouts; it does not prove all runtime ABI use.
The PR #1 author's 19.4.1051 results are reported evidence, not a router
runtime test performed by this project. Existing firmware metadata stays
restricted to the established build target.

Before publishing/promoting the modules, verify loading, key generation,
peer handshake, IPv4/IPv6 traffic and recovery on each matching router.
No router has been contacted or modified by this update.

## Router smoke test: 2026-10-13

Tested module SHA256:
`98e392edb92a574444c0555c9576f6ded0041421c938d0a4921789836c46e6e5`
from run 38358722087, commit `e1b63eb`.

Router: VBNT-K, firmware `19.4.1051-3401200`, AGTEF 2.4.5,
kernel `4.1.52 SMP preempt mod_unload ARMv7`, OpenWrt GCC 5.5.0.

- Copied the raw module and wg 1.0.20260223 into `/tmp` and verified SHA256.
- Loaded it with `insmod`; no IPK installation or autoload configuration.
- Created two temporary WireGuard interfaces, with fresh ephemeral keys
  and UDP endpoints on `127.0.0.1` only. No addresses/routes/firewall changes.
- Both peers completed a handshake and exchanged encrypted keepalive packets.
  Recorded counters: wgtsta RX 276 / TX 368 bytes; wgtstb RX 220 / TX 276 bytes.
- Deleted both interfaces and private keys, then unloaded the module.
- Boot ID unchanged, no new kernel Oops/panic/BUG messages, kernel taint
  unchanged at its existing value 4097.

This validates loading, interface setup, key exchange, encrypted keepalive
and unloading on this firmware. It does not validate routed VPN data,
throughput, prolonged operation, or other router/firmware versions.

Run 38358722087 still fails the CI metadata check: its module has an empty
`depends` field, since this standalone kernel build lacks the complete
symbol dependency dump. Both stock UDP tunnel modules were already loaded
for the runtime test. Dependency metadata/verification remains to be
resolved before describing the CI run as successful or publishing a feed.
