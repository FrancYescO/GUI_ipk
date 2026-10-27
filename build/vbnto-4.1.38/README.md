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
remain separate from the router-tested feed until runtime validation. WireGuard
has already passed a temporary two-peer handshake and encrypted-traffic test;
the expanded build checks its bytes before producing its tested manual IPK.

Expanded builds upload workflow artifacts. The public candidate feed is assembled
from the checksum-pinned repository bundle, with its configuration and build logs.
The build no longer creates duplicate candidate Releases.

Per-payload results are in [validation/results.json](validation/results.json)
and the [public validation page](https://francyesco.github.io/GUI_ipk/validation/4.1.38/).
Functional tests and load/unload/namespace smoke tests are separate levels.
They apply to the exact SHA-256 payloads and firmware ABI recorded there.
Stock busy conntrack core is not replaced on the live router.

`xt_nat` payload `340112b7526852684bf03b922da156c524ac436a663b101c0eaff23892563120`
is quarantined: a previous session emitted its test-start record, then a kernel
NULL dereference and reboot before a result. The cause is unresolved. Its IPK
is withheld and the probe refuses to test it. Rebuilding with a different hash
does not bypass the module quarantine. Raw diagnostic archives can still
contain this module.

The helpers in `validation/` are temporary, manual tools. The probe verifies the
payload hash, checks module references, records existing parameters and restores
original modules. It stops on restore failures or new kernel warning taints.
The functional tests use disposable namespaces. `BUILD_VALIDATION_KAT=1` builds
a crypto/compression/NLS known-answer helper; never install it or load it at boot.
Retain an external kernel log while probing.

Netfilter target/match pairs such as `xt_DSCP`/`xt_dscp` have distinct `-target`
and `-match` candidate package names. When repackaging on a case-insensitive host,
use `--module-archive` to read exact-case paths directly from the original tar.
