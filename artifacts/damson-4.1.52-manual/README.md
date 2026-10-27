# Damson 4.1.52 manual kernel packages

The original modules came from [Actions run 35757010241](https://github.com/FrancYescO/GUI_ipk/actions/runs/35757010241).
The current TUN and connmark payloads match the exact modules tested on VBNT-K.
The updated connmark includes the shared QoS/NAT ABI correction described below;
TUN retains its original bytes. Names omit `damson-`, with `Conflicts` and
`Replaces` for the former names. Persistent IPK installation was not tested.

The current names are available in this directory and the versioned feed:

- [kmod-tun-4.1.52-manual_4.1.52-1_brcm963xx.ipk](https://francyesco.github.io/GUI_ipk/kernel/4.1.52/kmod-tun-4.1.52-manual_4.1.52-1_brcm963xx.ipk)
- [kmod-act-connmark-4.1.52-manual_4.1.52-1_brcm963xx.ipk](https://francyesco.github.io/GUI_ipk/kernel/4.1.52/kmod-act-connmark-4.1.52-manual_4.1.52-1_brcm963xx.ipk)

Use the versioned feed URLs in installation scripts and check the downloaded file against `SHA256SUMS` before installation. These packages target Damson `19.4.0866-3401052`, kernel `4.1.52`, `brcm963xx`. They contain no autoload configuration or installation scripts. Installing one through OPKG writes the module to persistent storage; loading the sibling `.ko` from `/tmp` remains the reversible first test on a different firmware.

They are deliberately outside the shared OPKG feed, which can be configured on routers with other kernels.

WireGuard 1.0.20220627 was added from run 38358722087 and reverified by
successful run 38444441090. The exact raw module passed temporary loading,
loopback handshake/keepalive and unloading on VBNT-K firmware 19.4.1051.
No routed VPN or prolonged-operation test was performed. The IPK is
manual-only, has no install scripts/autoload, and requires stock udp_tunnel
and ip6_udp_tunnel already loaded. See docs/wireguard-updates.md. The package
is published in the kernel/4.1.52 feed together with TUN and connmark.

The 27 October 2026 validation on firmware 19.4.1051-3401200 revalidated
TUN packet read/write, connmark traffic, and WireGuard two-peer encrypted
traffic. The updated connmark includes the shared QoS/NAT ABI correction;
TUN and WireGuard retain their byte-identical original payloads. See the
[per-module report](https://francyesco.github.io/GUI_ipk/validation/4.1.52/).
