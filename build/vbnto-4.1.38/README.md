# Linux 4.1.38 runtime ABI

`kernel.config.gz` is the runtime configuration from the tested DGA4131FWB
18.3.n.0439 firmware. Its kernel OPKG version is
`4.1.38-1-08839f3f6145d3a5d2d04be7567e3f9d`.

The **Linux 4.1.38 stock ABI kernel modules** workflow has two profiles:

- `tested`: reproduce the router-tested TUN and SPU bytes and manual IPKs.
- `expanded`: first reproduce those modules, then build conntrack, its netlink
  interface and helpers, connmark, UDP tunnel dependencies, WireGuard
  `1.0.20220627`, optional QoS modules, and all modules already selected by the
  firmware configuration. A full `make -k modules` retains every successful
  module even when an unavailable vendor driver fails.

The expanded profile preserves every existing `CONFIG_*=y/m` setting. It
records all build exit codes, missing priority targets, per-module SHA-256,
exports and undefined symbols in `BUILD-REPORT.md`, `modules.json` and the
build logs. Missing WireGuard or a priority conntrack module fails the job;
available candidates and diagnostics are uploaded even after a failure.

Expanded IPKs have an exact kernel dependency and no installation scripts.
They stage `.ko` files in `/usr/lib/kernel-module-candidates/4.1.38/`, outside
the firmware's `/lib/modules` boot path. Installing one therefore does not
replace a stock conntrack module already loaded at boot. These candidates
remain separate from the router-tested feed until runtime validation.
