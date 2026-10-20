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

`results.csv` preserves the individual rates without rounding to one decimal.
The software-only ARM path is simpler than the hybrid and improves all three
key sizes. The hybrid's best repeatable benefit is with AES256; its 44–46
Mbit/s is still far below a claim of full hardware SHA256-128 acceleration.
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
* Hardware packet drops remain. The SHA256 framing/ARM hybrid reached 298
  encryption and 420 decryption drops over its three AES cases, with no
  hardware authentication errors or unexpected outer-tag failures. The
  shared RDPA IPv4 host-address table still reports resource exhaustion when
  synthetic namespace addresses are added. Neither issue is claimed fixed.
* The optional `in_place=1` branch exists for review but has **not** been run
  on the modem. It shortens/restores live linear skb buffers and skips copies
  only after layout, exclusivity and length checks. Automatic approval review
  rejected its live test because real ESP buffer safety was not yet proven;
  a specific user approval has been requested. Standard builds reject activation
  before algorithm registration unless explicitly rebuilt with
  `SPU_INPLACE_LAB=1`. All measured runs explicitly
  used `in_place=0` (private copies).

## Source and remote builds

The experiment branch is `codex/spu-sha256-experiments`.
The raw-only Actions laboratory profile compiled successfully in
[run 39472713533](https://github.com/FrancYescO/GUI_ipk/actions/runs/39472713533).
That first run predates the XFRM metadata correction and final buffer guards;
its artifacts are not the final runtime-tested revision. A final source build
will be recorded below after validation. Stable feeds retain their previous
SPU packages. No new firmware or undocumented hardware register was written.

## Final copy-path checks

The strengthened KAT passed 96 further checks with 0- and 20-byte ESP offsets,
heap-backed request scatterlists/IVs, tail guard bytes and IPv4-header
preservation checks, with `in_place=0`. A final AES256/ASM hybrid repeat gave
45.86 / 45.61 Mbit/s. No guard/header corruption was detected.

Final SSH checks found no SPU, hybrid, AES/SHA256 ARM, KAT or canary modules,
no test namespaces, and no root XFRM state/policy. The boot ID and persistent
hardwarecrypto checksum remained identical to the initial values. No new
kernel oops or panic was observed; no persistent SPU module was installed.
