# DGA4131FWB Linux 4.1.38 modules

These IPKs contain the exact TUN, SPU and WireGuard modules tested on a DGA4131FWB / VBNT-O,
firmware 18.3.n.0439, Linux 4.1.38. The firmware reports target
`brcm63xx-tch/VBNTJ`, architecture `arm_cortex-a9`, and kernel package
`4.1.38-1-08839f3f6145d3a5d2d04be7567e3f9d`. The separate VBNTS
`kernel/4.1.38` feed has a different kernel ABI and must not be used on this
firmware. The packages here declare the exact kernel dependency.

The build uses the router's `/proc/config.gz` (SHA-256
`c653774986e2a0ce0a1a0614f374c7ba3af830ba49cc2ad195e4fc151991432e`),
the pinned 4.1.38 source and the Broadcom `impl3` SPU source. The TUN/SPU probe adds only `CONFIG_TUN=m`. The expanded build also enables optional
modules while preserving all existing built-in and module settings. The SPU build applies the authsize fallback,
disabled-by-default ESP BLOG offload, and idempotent RDPA teardown patches.

## Router validation

The raw `.ko` files were copied only to `/tmp` and loaded without OPKG.
The boot ID remained `c0db9ffe-ef96-43ad-955d-84438ac3043c` throughout.

- TUN loaded, created and configured a temporary `ip tuntap` interface, then
  unloaded cleanly.
- SPU loaded with `blog_offload=0`; `spuctl start` registered its algorithms.
  The Crypto API test passed AES128/SHA256-128 software fallback and
  AES128/SHA1-96 Runner decryption, including rejection of altered tags.
- WireGuard `1.0.20220627` (SHA-256 `feb7ac9824f0615fe62a20ae4f1ff4385c0422d9f7892a20da6f4f4f64f97336`) passed loading, handshake and encrypted traffic between two temporary namespaces: 5/5 pings in each direction and matching transfer counters. It unloaded normally. It requires the stock `udp_tunnel` and `ip6_udp_tunnel` modules already loaded.
- Two temporary IPsec namespaces exchanged 5/5 pings in both directions for
  SHA1-96 and SHA256-128. SPU reported 40 ingress, 40 egress, 20 fallback,
  zero errors and zero drops for both encryption and decryption.
- `spuctl stop`, `rmmod` and namespace cleanup succeeded. No TUN, SPU, WireGuard or
  test module remained loaded. No file was written to `/overlay`.

The IPKs contain one `.ko` each, with no install scripts and no boot autoload.
Installation writes the module to `/lib/modules/4.1.38` but does not load it.
The separate feed will be published at
`https://francyesco.github.io/GUI_ipk/kernel/4.1.38-vbnto/` after the
publishing workflow runs on `main`. Direct downloads from this repository's
branch are possible before that deployment.

Do not use `--force-depends`: a mismatched kernel ABI can crash the router.
These tests do not establish compatibility with another firmware or validate
ESP BLOG offload, which remains disabled by default.
