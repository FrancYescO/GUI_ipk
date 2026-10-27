# Router-tested VBNT-S 4.1.38 modules

TUN, WireGuard and BCM SPU for the DGA4132 Homeware 18.3.k.0451 kernel ABI
`4.1.38-1-8dd693635a152c8c7b822a64e6c5c470`. Modules preserve the runtime
kernel configuration. Payload hashes are pinned in `build/vbnts-4.1.38/profile.json`.

On 2026-10-27 all three modules passed normal load and unload on 192.168.133.204:
TUN and WireGuard interface create/up/delete; SPU start/stats/stop, nine CryptoAPI
drivers. No new kernel fault, reboot or configuration/network/package change.
`validation-204.log` records that test. This does not establish VPN encrypted
traffic or OpenVPN acceleration. IPKs have exact kernel dependencies, no
maintainer scripts and no autoload. Verify SHA256SUMS before installation.

Compiled candidates, including USB and QoS modules, are published separately by
the VBNT-S workflow; they are not added to this tested feed until validated.
