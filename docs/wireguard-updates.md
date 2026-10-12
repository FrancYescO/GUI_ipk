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
Three cross-builds are pending. Workflow verification checks the ARM ELF,
full vermagic and UDP tunnel module dependencies. The Damson canary checks
selected kernel structure layouts; it does not prove all runtime ABI use.
The PR #1 author's 19.4.1051 results are reported evidence, not a router
runtime test performed by this project. Existing firmware metadata stays
restricted to the established build target.

Before publishing/promoting the modules, verify loading, key generation,
peer handshake, IPv4/IPv6 traffic and recovery on each matching router.
No router has been contacted or modified by this update.
