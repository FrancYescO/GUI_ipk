# SPU validation — 20 October 2026

Runtime: BCM63138, `brcm6xxx-tch/VBNTJ_502L07p1`, OpenWrt revision
`r14144-e2ae576c18`, Linux `4.1.52 #0 SMP PREEMPT Fri Oct 28 16:57:49 2022`.
OPKG accepts `arm_cortex-a9`; it does not list `brcm963xx`.

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
