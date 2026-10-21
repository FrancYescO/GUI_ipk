# Further performance investigation

Update 2026-10-21: combined RX drain and pool fallback reproduced loss of
connectivity followed by a restart even with private copies and the new RX
guards. See [reboot investigation](REBOOT_INVESTIGATION.md). Runner remains
quarantined; successful isolated trials do not establish production safety.

Target: BCM63138 / VBNTJ Damson, Linux 4.1.52. No experimental module was
installed or configured for boot. Stable feed artifacts and SPU package patches
remain unchanged. All tunnel keys were disposable test keys.

## Comparable upstream-iperf3 results

The table uses **iperf3 3.18 on both endpoints**, TCP receiver Mbit/s,
forward / reverse. Both endpoints are namespaces on the modem; veth RPS mask
3 is applied only to the test interfaces. IPsec uses 5 seconds per direction,
WireGuard 10 seconds. These are bounded comparisons, not WAN guarantees.

| Configuration | AES128 | AES192 | AES256 |
| --- | ---: | ---: | ---: |
| Generic AES-CBC / HMAC-SHA256-128 | 43.33 / 42.77 | 38.04 / 43.83 | 38.34 / 33.34 |
| ARM AES-CBC / HMAC-SHA256-128 | 48.83 / 48.85 | 42.73 / 46.13 | 43.34 / 39.00 |
| ARM AES-GCM, 128-bit tag | 36.59 / 37.75 | 34.74 / 36.06 | 33.96 / 33.13 |

WireGuard (ChaCha20-Poly1305, not AES): **114.86 / 183.80 Mbit/s**.
All IPsec fragmented pings succeeded; authentication/replay failure counters
were zero. WireGuard bidirectional pings and normal cleanup succeeded.

With upstream iperf3, both the unencrypted UDP control and WireGuard reported
**zero lost datagrams** in both directions at 10, 30 and 60 Mbit/s,
1000-byte datagrams, 5 seconds per transfer. The vendor iperf3 3.1.4 had reported
loss even without encryption (up to 1.10% in this session), and emits
`tcpspdtest_protocol` warnings without requesting `-H`. Consequently the earlier
vendor-tool UDP loss observations must not all be attributed to the cipher or
SPU. The measured host-pool exhaustion counters in the SPU experiments remain
real driver observations.

## Scheduling and packet-size comparisons

These earlier controls use vendor iperf3 3.1.4 and must not be silently mixed
with the upstream-tool table. AES-CBC / HMAC-SHA256-128, ARM providers:

| Setting | AES128 forward / reverse Mbit/s |
| --- | ---: |
| Automatic scheduling, RPS 0 | 44.12 / 41.94 |
| Server CPU 0, client CPU 1 | 41.75 / 43.90 |
| Server CPU 1, client CPU 0 | 43.03 / 44.27 |
| Both processes CPU 0 | 38.96 / 39.84 |
| TCP MSS 1200 | 39.53 / 39.84 |
| TCP MSS 536 | 26.09 / 25.98 |
| RPS 3, short run | 48.26 / 59.73 |
| RPS 3, 10-second repeat | 48.41 / 51.43 |

The RPS-3 10-second repeat measured AES192 44.22/45.17 and AES256
44.09/39.15 Mbit/s. Pinning processes or lowering MSS did not improve on the
best RPS comparison. These settings concern test veths/processes, not a
validated physical-WAN configuration. Physical interrupt names include generic
`brcm_97`/`brcm_98` and shared platform services; their affinity was read but
not changed during the unresolved restart investigation.

Vendor-tool WireGuard controls measured 127.19/123.07 Mbit/s without RPS,
112.32/192.58 with RPS 3, and 113.23/195.29 on a further RPS-3 repeat.
Steering changes the balance between directions; no universal optimum is
claimed from these short single-flow tests.

## Quarantined Runner queue / fallback experiment

Patch 003 adds optional RX polling, full queue draining and atomic diagnostic
counters. The original thread stops at 32 completions under ordinary scheduling;
that motivated investigating missed/undrained completion notifications.
A pre-enqueue pool-exhaustion path can select the existing synchronous software
AEAD provider instead of returning a drop. It is never used after successful
hardware submission. All new operational flags default to zero/false.

The software-forced path and the hardware path each passed 60 independent
reference/tag/header/IV/ciphertext checks, including the last tag byte and
buffer-boundary guards, for AES128/192/256 at ESP offset 20. Each ended with
`lab_inflight=0`; forced fallback recorded 45 uses and zero RX completions.

A private-copy hybrid run with pool 64, RX drain, polling 20 ms, software pool
fallback and RPS 3 completed all six 10-second TCP directions:

| AES key | Forward / reverse Mbit/s |
| --- | ---: |
| 128 | 44.45 / 50.23 |
| 192 | 20.90 / 40.53 |
| 256 | 37.45 / 41.04 |

It recorded 9,863 pool exhaustions and exactly 9,863 software fallbacks, zero
driver drops, zero hardware authentication errors, zero duplicate frees and
zero pending requests at completion. However, mixing immediate software and
asynchronous hardware completion reordered packets beyond the 32-packet
anti-replay window: expired-window counters were nonzero. This is not a
loss-free or production-ready fix.

An AES128 test with anti-replay window 256 reached 66.81 Mbit/s forward, then
lost connectivity during reverse. The modem later returned with boot ID
`fb4d1781-a9b6-41b7-92c7-901941cdb8fa`, replacing
`5f336319-19e8-4890-b38d-1a456ae27fbc`. This session sent no reboot command.
Manual intervention was asked about but has not been confirmed; no retained
panic log was available. The cause of this restart is **undetermined**. The
failed pair must not be presented as a successful 67-Mbit/s result.

The runtime-tested diagnostic bcmspu SHA256 was
`9288e0a42306bd5ff05e7952ab57bd333f3f4be81cd80da35467e9916b35fe27`.
The stored patch subsequently gained stop/error guards to bound the drain loop
on teardown or unexpected RDPA errors. Those additional guards are compile
validated only; this combination was not loaded again after the restart.
The Runner experiment remains quarantined and is not promoted to the feed.

## External peer controls

A task-owned Linux Docker container on the Mac provided a peer outside the
modem. Plain TCP with the peer as client measured **490.91 Mbit/s to the modem**
and **811.25 Mbit/s from the modem**. Root-generated direct client tests and a
TCP relay did not complete; those failures are excluded from throughput tables.

WireGuard external tests used one reserved modem namespace with an isolated
veth, precise temporary forwarding/NAT rules and the Mac address/port only.
They completed at roughly 12–13 Mbit/s. Reversing handshake initiation did not
remove the limitation. Upstream-tool MTU-1280 tests gave 11.28/11.01 Mbit/s;
disabling TX checksum/GSO/GRO on the two veths gave 12.53/12.16. Physical
interfaces and their offloads were not changed. The normalized firewall rules
were identical before/after the completed updated-controller runs (timestamps
and policy counters are excluded from that comparison).

An external AES128-CBC/SHA256-128 software ARM test completed at 14.14/13.63
Mbit/s with zero authentication/replay errors. Its asynchronous namespace
teardown initially retained provider references; they later reached zero and
ordinary unload succeeded without force or reboot. The controller now flushes
only its own namespace's SAs/policies and retries ordinary unload for up to
90 seconds. Further external results and final cleanup are recorded below.

These virtualized/NAT external results do not establish the WAN limit of any
cipher. The shared encapsulated path remains a limitation of this setup.

## Reproducible raw tools

`standard_tools=true` on either raw Actions lab profile builds pinned musl
1.2.5, wg 1.0.20210914, upstream iperf3 3.18 and the two restricted UDP/veth
helpers, plus standard AES-GCM dependencies. The WireGuard kernel module is
the exact previously validated artifact (SHA256 pinned in `standard-sources.tsv`).
Tools are static ARMv7 soft-float; IPv6 flow-label support is disabled for the
legacy-header build, while IPv4 TCP/UDP remains upstream. No IPKs are emitted.


## Completed external controls and data record

With upstream iperf3, WireGuard external MTU 1420 remained around 12–13 Mbit/s;
MTU 1280 and veth-offload removal did not improve it. Native software IPsec
AES256/SHA256 with RPS 3 measured 13.94/14.68 Mbit/s. AES128 with the same RPS
was repeated; both directions completed without authentication/replay errors.
Some NAT-T teardown references outlasted the first bounded unload retries and
were removed by subsequent ordinary unload after reference counts reached
zero. No forced module removal or reboot was used for that cleanup. The
controller's wait bound is now 90 seconds per owned provider.

`round2-results.csv` records 98 measurements with tool version, topology,
configuration, key size, direction, rate, loss and completion status. The
incomplete/restarted Runner pair is explicitly marked and excluded from the
comparable upstream table. `round2-logs.sha256` identifies the 27 original
local logs under `.cache/tests/spu-sha256/`; no private keys are published.
`collect-round2.py` regenerates the CSV from those preserved workspace logs.
The Runner's extended-window test remains excluded from recommended settings.


## Final remote build and runtime verification

[Actions run 39524956679](https://github.com/FrancYescO/GUI_ipk/actions/runs/39524956679)
succeeded for source `e83e33a` with `standard_tools=true`; publication was
skipped. The downloaded bundle contains 12 matching ARM kernel modules and
four static ARM tools. All 16 checksums, exact 4.1.52 vermagic values, absence
of userspace ELF interpreter dependencies and the pinned WireGuard module
hash were verified. It contains no IPKs.

The actual downloaded files were uploaded to `/tmp` and verified there again.
The ABI canary loaded/unloaded successfully. AES-GCM/AES128 bidirectional
fragmented pings and TCP passed, followed by WireGuard bidirectional pings/TCP
and UDP at 30 Mbit/s with zero loss. Both scripts completed ordinary cleanup.
The quarantined Runner module was not loaded for this validation; its latest
stop/error guards remain compile-only validation.

Final assertions passed on the modem: same post-restart boot ID, kernel 4.1.52,
unchanged hardwarecrypto SHA256, no test modules, namespaces, root XFRM state
or policy, test route or firewall chains, and no filtered new kernel oops or
panic. The temporary modem directory and test keys were deleted. Both task-owned
Docker containers and the host TCP relay were removed; unrelated containers,
volumes and the pre-existing `scripts/__pycache__/` were preserved.

No further restart occurred during the standard software/GCM/WireGuard tests.
The Runner experiment's restart cause remains unresolved. A native external
Linux peer without this nested Docker/NAT path is still needed before claiming
physical WAN throughput or recommending a particular physical IRQ/RPS setting.

The external AES128/RPS-3 repeat measured **14.75 / 14.26 Mbit/s**, with no
replay/authentication errors. This confirms the similar encapsulated-path
result across AES128, AES256 and WireGuard in this setup, despite the much
faster plain TCP control. It does not identify the responsible component.
