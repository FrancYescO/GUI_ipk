# Linux 4.1.52 runtime validation — 27 October 2026

Device: VBNT-K / Damson 19.4.1051-3401200, Linux 4.1.52 SMP PREEMPT ARMv7.
The exact kernel package version and raw payload hashes are in `results.json`.
[Published results](https://francyesco.github.io/GUI_ipk/validation/4.1.52/).

Final session: 14 functional passes, two load/unload/namespace smoke passes,
33 busy stock modules left unchanged, and xt_nat withheld. The final boot ID
`0d16759c-1f14-4012-9dce-c4b6291fef23` and initial taint 4097 remained unchanged.
No test IPK was installed. Original module files, autoload configuration and
hardwarecrypto configuration remained unchanged. Test namespaces, temporary
WireGuard keys, SPU test helper, SPU and WireGuard were removed after testing.

## Corrections

The GPL SDK adds Zyxel `dropbytes`/`dropbps` fields to generic scheduling
statistics. These changed Qdisc queue-length offset from the stock 0x64 to 0x6c,
and changed private class/Qdisc layouts. The original HFSC candidate emitted
warnings under traffic and pinned a test namespace; a controlled reboot restored
stock HFSC. Patch `002-damson-qos-nat-abi.patch` excludes these fields.

The same GPL SDK adds one-to-one port-mapping fields to NAT ranges. The REDIRECT
rule was rejected as `invalid size 32 (kernel) != (user) 24`. The patch excludes
those fields and their code paths, restoring the stock range layouts.
The ABI canary checks statistics sizes, Qdisc size and qlen offset, and both NAT
range sizes. Corrected HFSC, cls_flow and REDIRECT passed traffic and restoration
checks twice. Corrected IPKs replace the existing files, retaining version 4.1.52-1 as requested.
Checksums changed; opkg upgrade cannot detect a replacement at the same version.

## Limits and the stock xt_nat incident

An attempt to test the corrected xt_nat candidate lost SSH while executing
`remove-original`, before `original-removed` or `load-candidate` was emitted.
The modem returned with a new boot ID. This mirrors the earlier 4.1.38 test-start
failure, but no replacement candidate was loaded in this 4.1.52 attempt. Root
cause of stock-module removal is unresolved. Do not repeat this removal. The
probe always skips xt_nat and the feed publisher rejects it. Only a raw untested
candidate is retained in the separate quarantine directory.

Busy conntrack/NAT/firewall core modules were not substituted; their runtime
compatibility remains unvalidated. The state userspace iptables extension is
absent, so xt_state has only a load/unload/namespace pass. RNDIS has no new USB
device traffic test. SPU passed known-answer, altered-tag and ESP tests with
BLOG offload disabled; runner address-table messages remain visible during
namespace tests. This does not prove BLOG offload, sustained load or real-client
interoperability. WireGuard passed handshake and 5/5 encrypted 1000-byte pings
in each direction between two isolated peers.

These are raw-module tests. Many historical manual IPKs retain the GPL
`brcm963xx` package label while this router reports `arm_cortex-a9`; no forced
architecture installation was attempted. Persistent IPK installation was not
tested. Preserve firmware/ABI guards when using these artifacts.

The probe uses `/tmp`, checks hashes and references, restores original modules,
refuses the failed HFSC payload, skips xt_nat, and stops on restore failures or
new kernel taints. It supports both BusyBox timeout syntaxes. The functional
helper explicitly deletes test qdiscs before unlinking namespace handles.
`tun-packet-probe.c` is a freestanding ARM userspace syscall test (no libc or
kernel helper): it injects IPv4/UDP and reads an ICMP reply through TUN. Compile
with the preserved kernel compiler using `-Os -marm -march=armv7-a -ffreestanding
-fno-builtin -fno-stack-protector -nostdlib -static -Wl,--build-id=none -Wl,-e,_start`.
Keep a reconnecting external kernel-log capture during any future testing.
