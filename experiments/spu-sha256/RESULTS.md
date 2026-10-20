# SHA256-128 investigation results — 20 October 2026

Target: BCM63138 / VBNTJ Damson, Linux 4.1.52. Tests used raw modules loaded
only from `/tmp`; the published feeds were not replaced.

## TCP comparison

All rows use SHA256 with a 128-bit outer authentication tag. Values are
receiver Mbit/s, **forward / reverse**, in separate 5-second tests with a
32-packet replay window. Both tunnel endpoints run on the same modem. These
are bounded functional comparisons, not WAN benchmarks or long-run stability
certification. Three 4,000-byte fragmented pings in each direction preceded
every AES case and succeeded; XFRM failure/replay counters remained zero.

| Configuration | AES128-CBC | AES192-CBC | AES256-CBC |
| --- | ---: | ---: | ---: |
| Fallback SPU pubblicato | 35.4 / 36.7 | 34.6 / 35.7 | 33.6 / 31.5 |
| Software generico senza SPU | 36.0 / 37.7 | 34.6 / 35.7 | 32.7 / 33.6 |
| Solo SHA256 ARM | 38.7 / 40.1 | 36.4 / 35.7 | 34.4 / 36.1 |
| Solo AES ARM | 41.8 / 40.1 | 39.0 / 38.8 | 36.6 / 35.8 |
| AES + SHA256 ARM | 42.9 / 43.7 | 39.0 / 42.2 | 39.4 / 39.2 |
| Fallback SPU + AES/SHA256 ARM | 42.2 / 42.2 | 44.8 / 42.2 | 37.1 / 39.0 |
| Ibrido AES Runner / framing SHA1 / SHA256 C | 35.0 / 37.8 | 32.2 / 37.6 | 37.7 / 38.0 |
| Ibrido AES Runner / framing SHA1 / SHA256 ARM | 40.4 / 39.4 | 40.5 / 40.2 | 39.0 / 40.7 |
| Ibrido AES Runner / framing SHA256 / SHA256 C | 40.7 / 42.3 | 40.3 / 42.6 | 41.5 / 42.4 |
| Ibrido AES Runner / framing SHA256 / SHA256 ARM | 41.8 / 44.7 | 46.0 / 44.2 | 44.1 / 45.9 |
| Ibrido senza copie / SHA256 C | 44.1 / 45.7 | 40.9 / 45.6 | 45.7 / 45.8 |
| Ibrido senza copie / SHA256 ARM | 49.3 / 48.7 | 49.1 / 49.5 | 41.4 / 50.2 |

`results.csv` preserves the individual rates without rounding to one decimal.
The software-only ARM path is simpler than the hybrid and improves all three
key sizes. The private-copy hybrid reached 44–46 Mbit/s with AES256. A subsequent
10-second in-place/ARM repeat reached 48.56/48.94, 48.02/48.80 and
48.66/49.45 Mbit/s for AES128/192/256 respectively. This is partial AES
acceleration; CPU SHA256 work remains.
These short tests are insufficient to rank small differences reliably.

## Correctness and limitations

* Direct hardware SHA256-128 failed on a valid independently generated packet
  with `-EBADMSG`: hardware ingress 1, fallback 0, hardware auth errors 1. This
  rules out fixing the installed Runner integration merely by removing the
  driver's authentication-size gate. Hardware SHA256-96 passed encryption,
  decryption and tag-rejection checks for all three AES key sizes.
* Both scalar ARM providers passed independent generic-reference tests for
  encryption, decryption and altered-tag rejection. NEON is not enabled or
  attempted on this target.
* Both hybrid framing variants passed 48 checks each covering encryption,
  decryption, and alterations to the outer tag, ESP header, IV and ciphertext
  across AES128/192/256. Full SHA256-128 is always checked before hardware
  decryption. The private 96-bit framing does not change the wire protocol.
* XFRM requires the full SHA256 digest size (32 bytes) in AEAD metadata before
  selecting the 16-byte tag. The initial prototype advertised only 16 and SA
  creation failed before traffic; this was corrected. Operational requests
  with any tag size other than 16 are rejected.
* Historical packet drops in the original 64-slot driver were observed. The SHA256 framing/ARM hybrid reached 298
  encryption and 420 decryption drops over its three AES cases, with no
  hardware authentication errors or unexpected outer-tag failures. The
  shared RDPA IPv4 host-address table still reports resource exhaustion when
  synthetic namespace addresses are added. The host-pool investigation below resolves the reproduced pool exhaustion;
  the shared address-table warning is not claimed fixed.
* The user explicitly authorized the `in_place=1` test after the initial
  automatic approval rejection. Before real tunnel traffic, 96 synthetic
  KAT/guard checks passed at ESP offsets 0 and 20, with 36 successful
  borrowed-buffer operations for each offset. Both full tunnel comparisons
  then passed. The fast path is optional and does not establish safety for
  every production skb layout. Normal lab builds continue to reject activation;
  the separate in-place lab requires explicit build and load opt-ins.


## Source and remote builds

The laboratory is now integrated into `kmods-4.1.52`. The original experiment
branch was `codex/spu-sha256-experiments`; the runs below retain their original
source commit identities.
The raw-only Actions laboratory profile compiled successfully in
[run 39472713533](https://github.com/FrancYescO/GUI_ipk/actions/runs/39472713533).
That first run predates the XFRM metadata correction and final buffer guards;
its artifacts are not the final runtime-tested revision. The later source build
and its runtime outcome are recorded below. Stable feeds retain their previous
SPU packages. No new firmware or undocumented hardware register was written.

## Final copy-path checks

The strengthened KAT passed 96 further checks with 0- and 20-byte ESP offsets,
heap-backed request scatterlists/IVs, tail guard bytes and IPv4-header
preservation checks, with `in_place=0`. A final AES256/ASM hybrid repeat gave
45.86 / 45.61 Mbit/s. No guard/header corruption was detected.

After the initial copy-path phase, SSH checks found no SPU, hybrid, AES/SHA256 ARM, KAT or canary modules,
no test namespaces, and no root XFRM state/policy. The boot ID and persistent
hardwarecrypto checksum remained identical to the initial values. No new
kernel oops or panic was observed; no persistent SPU module was installed.


## Final host-pool and full-tag validation

The final KAT includes corruption of the **last** tag byte, explicitly proving
that the extra 32 bits beyond the hardware's 96-bit framing are authenticated.
At pool 256, the in-place path passed 60 checks at ESP offset 0 and another
60 at offset 20 (45 borrowed operations per offset). The private-copy path
passed another 60 at offset 20. All use an independent generic software
reference and include tail/length/header guards; no duplicate free occurred.

The host transfer pool, originally 64 entries, was exhausted under UDP bursts.
At 10 Mbit/s / 1000-byte datagrams / 3 seconds after a key update:

| AES-CBC key | Pool 64: lost / sent | Pool 256: lost / sent |
| --- | ---: | ---: |
| 128 | 1305 / 3639 | 3 / 3644 |
| 192 | 1272 / 3638 | 0 / 3638 |
| 256 | 1291 / 3638 | 0 / 3639 |

Every loss in the pool-64 run matched a `lab_no_slot` increment. All pool-256
cases reported `lab_no_slot=lab_tx_error=lab_recycle=lab_double_free=0`.
The three residual datagrams were not accounted for as driver drops; universal
loss-free delivery is not claimed. Fragmented pings before and after key
updates succeeded. Patch 002 bounds the host pool to 64/128/256 and removes
an O(N) free-list scan; SA descriptors, firmware and registers are unchanged.
The default remains 64, with 256 selected explicitly for these tests.


## Stress-repeat caveat

A later 10-second-per-direction sequence with pool 256 was **not a clean
performance pass**. AES128 measured 9.08/51.71, AES192 44.24/5.98, AES256
forward 51.36 Mbit/s; the last reverse case stopped making progress and was
interrupted after about 101 seconds. Test processes were stopped with SIGINT;
normal module and namespace cleanup succeeded, with no reboot, authentication
failures, transmit errors, recycling or duplicate frees. Cumulative host-pool
exhaustions reached 751. No cause for the TCP stall is established.

An isolated fresh-load AES256 repeat then passed at 48.87/51.32 Mbit/s
(207 host-pool exhaustions, all other diagnostic errors zero). This does not
invalidate the failed sequence or establish sustained throughput. The modem's
vendor iperf3 3.1.4 also emits `tcpspdtest_protocol` stream-index warnings on
UDP completion even without requesting its `-H` hardware-test option; these
warnings alone do not identify the cause of the TCP stall. The experimental
hybrid therefore remains unsuitable for replacing the stable feed.

## Actions artifact provenance

The final code revision f503bc0 compiled successfully in
[Actions run 39478521997](https://github.com/FrancYescO/GUI_ipk/actions/runs/39478521997).
All six downloaded raw modules passed checksum, ARM ELF and exact 4.1.52
vermagic verification. The bundle contains no IPKs. The actual downloaded
ABI canary loaded/unloaded successfully on the modem, followed by 60 full-tag
and buffer-guard checks with in-place operation at ESP offset 20 and pool 256.
The normal non-in-place profile also built successfully in
[run 39475046727](https://github.com/FrancYescO/GUI_ipk/actions/runs/39475046727);
that earlier bundle predates host-pool patch 002.


The Actions bundle then passed the longer UDP exercise: 10 Mbit/s,
1000-byte datagrams, 10 seconds per direction, updated SAs and fragmented
pings, all AES key sizes. Receiver losses were:

| AES-CBC key | Forward lost / sent | Reverse lost / sent |
| --- | ---: | ---: |
| 128 | 0 / 12388 | 0 / 12513 |
| 192 | 2 / 12400 | 5 / 12520 |
| 256 | 2 / 12388 | 4 / 12513 |

All driver diagnostic counters and outer-tag error counters remained zero.
Both peers were on the modem; this is not a WAN or external-client validation.


## Final TCP failure and recovery state

The actual Actions modules also reproduced the TCP stall, this time during
AES128 forward in the short 5-second-per-direction sequence. The iperf client
and server were stopped normally with SIGINT. Unlike the earlier local-build
interruption, this run retained pending kernel requests after the test
namespaces were deleted: `spu_sha256_hybrid` (4 references), `bcmspu` (8),
and `sha256_arm` (12) remained loaded. A later ordinary unload attempt did not
remove them; **no forced removal** was attempted. A planned copy-path/software
control could not start because the phase script correctly refused existing
SPU modules. The stall's root cause is therefore unresolved; successful KATs
and UDP do not establish TCP stability or in-place memory safety under load.

The modem stayed reachable over SSH. Root XFRM state and policy were empty,
and no test namespaces remained. The hardwarecrypto configuration checksum
was unchanged (`9db4b90177169cbad1fcc4acc6a0dedcda50cb74dd07d27ebe211525abaa9058`),
with no experimental boot autoload. No kernel oops/panic was found by filtered
checks. The user subsequently authorized an orderly reboot for recovery; temporary
modules were not installed into a feed or persistent filesystem.


## Authorized reboot recovery — verified

The modem accepted an orderly `sync; reboot` after explicit user approval.
SSH returned with boot ID `5f336319-19e8-4890-b38d-1a456ae27fbc`, replacing
`2ad6a90e-2eec-4b54-b483-e865a24a31b8`. Post-boot checks confirmed:

* Linux 4.1.52 and the identical hardwarecrypto configuration checksum.
* No SPU, hybrid, AES/SHA256 ARM, KAT or ABI-canary test modules loaded.
* No test namespaces and no root-namespace XFRM state or policy.
* No filtered kernel oops or panic.

No experimental module was loaded again after recovery. The local temporary
Docker lab container was removed; source, build artifacts and test reports
were retained. Published kernel feeds remain unchanged by this experiment.


## Consolidation on kmods-4.1.52

The six laboratory commits were selectively applied to `kmods-4.1.52`, keeping
that branch's pinned build-input pipeline and stable module/package behavior.
No stable SPU patches or committed feed artifacts changed. Consolidated source
revision `d345307` passed [Actions run 39481039995](https://github.com/FrancYescO/GUI_ipk/actions/runs/39481039995):
all six laboratory modules built, checksums passed, no IPKs were emitted, and
the non-in-place compile guard was verified. The publication job was skipped.
No further modem tests were run during this branch consolidation.

The original laboratory history is retained at tag
`archive/spu-sha256-experiments-20261020`. The integrated local and remote
`codex/spu-sha256-experiments` and `codex/spu-damson-4.1.52` branches were
removed. Other branches with changes absent from `kmods-4.1.52` were retained.
