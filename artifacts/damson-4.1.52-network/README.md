# Linux 4.1.52 network modules

The installable feed contains 43 networking IPKs, plus the separately published
TUN, connmark, WireGuard, SPU and CDC Ethernet/RNDIS packages. `xt_nat` is excluded.

The 27 October 2026 tests on VBNT-K firmware 19.4.1051-3401200 found two vendor
ABI differences in the GPL source: Zyxel QoS drop statistics enlarged Qdisc and
class layouts, and Zyxel one-to-one NAT fields enlarged NAT ranges. Patch
`002-damson-qos-nat-abi.patch` removes these extensions. Compile-time assertions
check the observed stock offsets and sizes. Corrected IPKs overwrite their existing filenames and retain version
`4.1.52-1`, as requested. Checksums changed; an already installed package will
not be updated by opkg upgrade at the same version.

[Exact-payload validation results](https://francyesco.github.io/GUI_ipk/validation/4.1.52/)
record 14 functional passes, two load/unload/namespace-only passes, and 33 busy
stock modules that were not substituted. Corrected HFSC, flow and REDIRECT
passed isolated traffic tests and stock restoration. Busy conntrack/NAT core
and firewall modules remain **runtime unvalidated**; compilation and ABI canaries
do not prove their complete compatibility.

Removing the stock `xt_nat` module caused loss of SSH followed by a changed boot
ID before its replacement loaded. That removal will not be repeated. The new
candidate remains untested and is withheld from the installable feed; its raw
payload is retained separately under `../damson-4.1.52-quarantine/`.

IPKs have no autoload files or installation scripts. Persistent installation
was not exercised: tests used raw IPK payloads in `/tmp`, disposable namespaces,
and normal module removal/restoration. Existing architecture and firmware
metadata guards remain; do not force installation to bypass a firmware mismatch.
