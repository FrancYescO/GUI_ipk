# SPU validation — 20 October 2026

Runtime: BCM63138, `brcm6xxx-tch/VBNTJ_502L07p1`, OpenWrt revision
`r14144-e2ae576c18`, Linux `4.1.52 #0 SMP PREEMPT Fri Oct 28 16:57:49 2022`.
OPKG accepts `arm_cortex-a9`; it does not list `brcm963xx`.

## Final Actions artifact

[Actions run 39433551005](https://github.com/FrancYescO/GUI_ipk/actions/runs/39433551005)
succeeded at source commit `c3a4dae3fb8498b59b27772e379d523cf9b0e6ff`.
It rebuilt SPU, the test module and ABI canary remotely using the preserved
kernel compiler seed, verified the module vermagic, checked all checksums
and validated the manual-only IPK contents.

Package: `kmod-bcmspu-damson-4.1.52-manual_4.1.52-1_arm_cortex-a9.ipk`

SHA-256: `a082030e1d2f93cb17bb9f61eb7b550895d38bdc2087560d6ae677a7b7796cda`

The package was transferred to `/tmp`, verified again on the router, accepted
by `opkg --noaction`, and unpacked there. Its payload matched the sibling
raw module exactly. The module loaded for the final tests was extracted
directly from this IPK, not reused from the preliminary local build.

All four cryptographic tests passed again: SHA256-128 software fallback,
SHA1-96 hardware decrypt, and altered-tag rejection for both. `blog_offload`
remained `N`. Both isolated ESP tunnel suites returned all 20 ping replies.
Three-second same-router TCP receiver rates were 86.3 Mbit/s for SHA1-96
and 37.6 Mbit/s for SHA256-128. These are functional test observations only.
The driver recorded 12 encryption drops and 45 additional decryption drops
under the hardware traffic exercise; the software exercise added no further
drops. The deliberate bad-tag tests account separately for one hardware
authentication error and one software drop.

Finally `spuctl stop` and module unload succeeded. The boot ID and persistent
`hardwarecrypto` checksum still matched the initial readings; no test modules,
test namespaces, XFRM states, installed SPU package, or persistent SPU module
file remained. The checked kernel log contained no oops or panic.

## Preliminary local build

The existing GCC 5.5.0 Linux build environment compiled the SPU driver and
test module after applying the current Damson ABI patch. All canary offset
checks passed. Every imported symbol exists in the running kernel or its
export table. Transferred module SHA-256 digests matched before loading.

Only `/tmp` was used on the device. Module loading created `/dev/spu0`;
`blog_offload` read `N`, and `spuctl start` registered 12 crypto algorithms.

| Exercise | Result |
| --- | --- |
| AES128/SHA256-128 software fallback decrypt | PASS |
| AES128/SHA256-128 altered-tag rejection | PASS |
| AES128/SHA1-96 hardware decrypt | PASS |
| AES128/SHA1-96 altered-tag rejection | PASS |
| Isolated ESP tunnel, SHA1-96, ping both ways | 10/10 replies |
| Isolated ESP tunnel, SHA256-128, ping both ways | 10/10 replies |
| OPKG package architecture, `--noaction` | Accepted |
| Stop and unload | PASS |

Three-second same-router TCP exercises reported about **86.0 Mbit/s** with
hardware SHA1-96 and **36.3 Mbit/s** with software SHA256-128. Both peers run
on the same router: these are functional observations, not WAN benchmarks.
The hardware exercise recorded 12 encryption drops and 35 additional
decryption drops; the earlier negative tests deliberately added one
authentication error and one software drop. The software traffic exercise
added no further drops. Congestion/drop handling has not been eliminated.

The vendor RDPA address notifier also reported a full
`ipv4_host_address_table` when adding the synthetic namespace addresses.
The isolated tunnels still worked. This is a separate shared vendor table
limit, not evidence that the SPU patch expands that table.

Cleanup removed both test namespaces and all their XFRM states. SPU and its
test modules were unloaded. The boot ID and `hardwarecrypto` checksum were
unchanged, and the checked kernel log contained no oops or panic. OPKG's
dry-run left no installed package, `/lib/modules/4.1.52/bcmspu.ko`, or boot
autoload entry.

## Scope

SHA256-128 compatibility is provided by software fallback, not a new Runner
hardware capability. BLOG ESP flow offload stays off by default. The forum's
Windows/DHCP crash scenario has not been reproduced with real clients, and
no long-duration or WAN interoperability certification is claimed.

## Extended matrix and lifecycle

Ten consecutive load/start/KAT/stop/unload cycles passed all 40 known-answer
and altered-tag checks. A six-case matrix combined AES128/192/256 with
SHA1-96 hardware and SHA256-128 software fallback, with a 32-packet replay
window. All 36 fragmented 4,000-byte ping requests succeeded in both directions;
all twelve TCP forward/reverse transfers completed. Receiver throughput was
70.3–84.7 Mbit/s for SHA1 and 31.7–37.0 Mbit/s for SHA256, measured between
namespaces on the same router, not across a WAN. XFRM reported zero failed
authentication and replay errors. Hardware counters reached 105 encryption
drops and 366 decryption drops under load; software cases did not increase them.

An immediate stop after namespace removal reported a crypto reference still
held. Namespace destruction releases XFRM/crypto objects asynchronously.
A subsequent ordinary stop and unload both returned success after teardown
completed, with no forced unload or router reboot. Test runners must wait for
that cleanup, check return codes, and never label a best-effort unload as a pass.

## Live SA key update and UDP

The six AES/SHA combinations were repeated with replacement encryption keys
on both live SAs in both namespaces. All 72 fragmented ping requests before
and after key changes succeeded. Six 3-second UDP transfers at 10 Mbit/s
completed: SHA256 software had zero reported datagram loss; hardware SHA1
reported 3.1%, 0%, and 5.4% loss for AES128/192/256 respectively. This confirms
that hardware packet loss is not limited to maximum-throughput TCP testing.
The precise vendor Runner resource/drop cause remains unresolved; do not
interpret successful transfer completion as loss-free hardware operation.
The source recycle callback can report drops as `-ENOBUFS`, but these tests
do not instrument the firmware and cannot establish every drop's cause.

Waiting three seconds for asynchronous namespace cleanup allowed ordinary
stop and unload to finish successfully. Final SSH checks found no SPU, KAT or
canary module, no test namespace and no XFRM state/policy in the root namespace.
Boot ID and persistent hardwarecrypto checksum remained unchanged. No new
kernel oops/panic was observed. This is temporary `/tmp` validation, not a
long-duration WAN or real Windows-client test.
