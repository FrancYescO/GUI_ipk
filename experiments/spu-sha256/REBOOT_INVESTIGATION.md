# Reboot investigation — 2026-10-21

The Runner hybrid remains unsafe for deployment. A private-copy test reproduced
loss of ping/SSH followed by a changed boot ID. This session sent no reboot
command. External intervention remains unconfirmed. This reproduces the failure
sequence; it does not diagnose a panic or establish a complete fix.

## Controlled comparisons

Same BCM63138 modem, Linux 4.1.52, static upstream iperf3 3.18, AES128 CBC /
HMAC-SHA256-128, two local namespaces, test-veth RPS mask 3. Runner uses private
copies (`in_place=0`), 64 host requests, polling 20 ms and BLOG disabled.
Successful Runner cases ran 10 seconds per direction; software ran 15 seconds.
These are local diagnostic comparisons, not WAN speeds or stability qualification.

| Configuration | Replay window | Forward / reverse Mbit/s | Outcome |
| --- | ---: | ---: | --- |
| ARM software, no Runner | 256 | 56.50 / 54.66 | Normal cleanup |
| Runner, polling only | 32 | 60.00 / 46.13 | Normal cleanup |
| Runner, polling only | 256 | 57.42 / 45.61 | Normal cleanup |
| Runner, polling + drain | 256 | 47.13 / 43.51 | Normal cleanup |
| Runner, polling + pool fallback | 256 | 54.71 / 60.92 | Normal cleanup; replay-window drops |
| Runner, polling + drain + pool fallback | 256 | No completed measurement | Lost ping/SSH during first TCP direction; later restarted |

The failed case requested 15 seconds per direction but never finished the
first. It must not contribute a speed result. These are single trials: neither
option is proven universally safe independently.

Completed Runner cases ended with zero pending requests, TX errors, invalid RX
completions, duplicate frees and hybrid bad tags. Pool exhaustions were 482,
361, 438 and 53,567 respectively. Fallback-only used software exactly 53,567
times but still exceeded the extended replay window (84 and 223 expired-window
counts in two SAs). It is not a loss-free fix.

Independent reference/tag/guard checks passed for AES128/192/256 at ESP offset
20, including corruption of the last tag byte. Hardware: 45 RX completions,
no fallback, zero pending. Forced software: 45 fallbacks, no hardware RX,
zero pending. Both unloaded normally.

## Failure observations

Runtime bcmspu SHA256:
`e58d572408a1b3200789880e85d8bb4985025db975e25ea87c25b7e1fdacc3f1`.
This is the Actions e83e33a bundle, including the previously compile-only RX
stop/error guards. Those guards do **not** prevent this failure.

Last complete snapshot: uptime 21440, boot
`fb4d1781-a9b6-41b7-92c7-901941cdb8fa`, available memory 194476 kB,
4094 exhaustions/fallbacks, 25188 RX completions, 32 pending requests,
zero TX/invalid-RX/duplicate-free errors. At uptime 21442 the next snapshot
stopped mid-output after 9574 exhaustions and 284 RX polls. Its final pending
count was not received. ICMP and SSH both failed.

First confirmed recovery: 06:06:41 UTC, new boot
`2db2518f-1aef-4f6a-866a-5efbadaebb00`. Boot log:

```
print_rst_status: Last RESET due to SW reset
```

This does not identify the caller or prove a panic. No panic/oops was captured.
The last snapshot does not suggest memory exhaustion. An empty remote crash
stream does not exclude a panic: networking or scheduling may stop first.

## Capture limits and containment

Running kernel: `panic=3`, `panic_on_oops=1`, `MAGIC_SYSRQ=y`, `CRASH_DUMP=y`.
`NETCONSOLE`, `NETPOLL`, `PSTORE`, `WATCHDOG` and `LOCKUP_DETECTOR` are disabled.
No `/proc/last_kmsg` or pstore log exists; no working crash capture kernel was
established. Sysctls and persistent configuration were unchanged. The boot
console is `ttyS0,115200`; serial capture is the preferred next diagnostic step
if accessible.

`crash-monitor.sh` streams bounded read-only counter/memory/RX-thread snapshots
and filtered crash messages to another machine. A separate bounded filtered
`/dev/kmsg` reader was also active. Neither captured the final cause. Do not
publish unfiltered vendor logs: they may contain credentials.

Both test scripts now reject nonzero RX_DRAIN together with POOL_FALLBACK before
loading modules. This contains the unsafe combination; it does not fix the
kernel driver. Further combined stress should first have working serial
capture. A stack trace could distinguish completion-path lockup, an interaction
between synchronous and asynchronous completions, or another vendor reset.

## Recovery and scope

Post-recovery assertions passed: kernel 4.1.52, new boot ID, no lab modules or
namespaces, no root XFRM states/policies, no `/tmp/spu-sha256`, no filtered new
oops/panic. hardwarecrypto SHA256 stayed
`9db4b90177169cbad1fcc4acc6a0dedcda50cb74dd07d27ebe211525abaa9058`.
No experiments were installed/autoloaded. Stable packages, feeds and main are
unchanged. Local evidence: `.cache/tests/spu-sha256/reboot-*.log`; hashes in
`reboot-logs.sha256`. Raw logs remain local.
