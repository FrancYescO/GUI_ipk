# Damson 4.1.52 manual kernel packages

The modules originate from [GitHub Actions run 35757010241](https://github.com/FrancYescO/GUI_ipk/actions/runs/35757010241). The packaged `tun.ko` and `act_connmark.ko` match the modules tested on the VBNT-K router, byte for byte. Package names now omit `damson-`; only control metadata was changed, with `Conflicts` and `Replaces` for each previous name. The IPK installation itself has not been tested on the router.

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
