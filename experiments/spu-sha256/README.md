# SHA256-128 laboratory: DGA4130 / VBNT-K, firmware 19.4.1051

Target: Technicolor DGA4130 / VBNT-K, BCM63138, firmware 19.4.1051,
Linux 4.1.52. Historical build identifiers in filenames do not name the modem.
The hybrid remains laboratory-only: it has reproduced TCP stalls and loss of
connectivity followed by a restart even with private copies. Standard software,
AES-GCM and WireGuard tests completed; they do not validate the hybrid.
Queue-diagnostic flags default to false/zero. RX drain together with software
pool fallback is rejected by both test scripts before module loading because
that combination reproduced the failure. No Runner experiment is recommended
for production or included in the stable feed.

The `kmods-4.1.52` branch contains this laboratory alongside the stable builds.
Experimental raw modules remain separate from published kernel feeds.
The Actions profile `build-vbntj-kmods.yml: module_set=spu-sha256-lab` rebuilds
SPU, an extended independent-reference KAT, the ABI canary, scalar ARM AES and
SHA256 modules from the pinned kernel, and the experimental hybrid wrapper.
It deliberately emits no IPKs. Do not install these modules or add boot autoload.

## Investigated paths

* Direct Runner SHA256-128: an explicit read-only load parameter bypasses only
  the existing size gate. A valid software-generated SHA256-128 packet returned
  `-EBADMSG`, with one actual hardware request and no software fallback. This
  is a negative capability probe, not a working hardware mode. SHA256-96 passed
  encryption, decryption and altered-tag checks with AES128/192/256.
* Later Broadcom `impl4` supports variable tag sizes but the SDK's autodetection
  assigns it to other chips (BCM94908/63158/6858/47622). BCM63138/63148 use impl3.
  It is not a drop-in hardware driver replacement for the tested modem.
* Firmware support: available DSL Runner sources expose no ICV-length argument
  in `rdpa_ipsec_sa_desc_setting`; the firmware instructions are provided as
  binary C arrays, not an assembler implementation of the IPsec routine. No
  unknown register bit or replacement Runner firmware is written on the modem.
* Hybrid wrapper: the default private Runner framing uses SHA256-96 with the
  actual key. Incoming full SHA256-128 is checked in software before AES
  decryption; outgoing tags are extended in software after checking the Runner
  prefix. This does not claim full SHA256-128 hardware acceleration. The
  `private_sha1=1` comparison variant uses a private dummy SHA1 tag and an extra
  software HMAC on decryption; it never substitutes SHA1 for the outer SHA256.
* Scalar ARM assembly AES and SHA256: the modem has no advertised NEON/VFP.
  Only the kernel's non-NEON ARM implementations are built. These can improve
  software processing without relying on the Runner's tag-size handling.

## Safety and limitations

The hybrid is a prototype, not a production VPN driver. It supports ESP's
8-byte associated data, AES-CBC, a 16-byte outer tag, bounded payloads, and
AES128/192/256. The default SHA256 Runner mode currently accepts authentication
keys up to 32 bytes. Hardware encryption and decryption have distinct contexts.
It uses private copies unless the explicit in-place profile is activated, checks tags in constant time, and does not
return decrypted bytes on authentication failure. All requests must complete
before unloading; a timed-out KAT deliberately retains its outstanding request
and callback rather than freeing memory still owned by hardware.

`kat_extended.c` uses explicitly selected generic software algorithms as its
independent reference, checks encryption as well as decryption, and can corrupt
the first or last tag byte, ESP header, IV or ciphertext. `kat-run.sh` checks initial module state
and checksums, fails on the first unsuccessful test, and uses signal/exit traps
for normal cleanup. No forced module removal is used; one stalled run needed an explicitly
authorized orderly reboot. Other failed stress runs lost connectivity and
subsequently showed a changed boot ID without a reboot sent by the test session.

`phase.sh` compares providers using `benchmark.sh`, which creates only the
reserved `spu-check-a/b` namespaces and public disposable test keys. TCP JSON
is read by `summarize.py`. Both peers are on the modem: these are functional
same-device comparisons, not WAN performance claims. Wait for asynchronous
namespace teardown before unregistering SPU. Never force unloading if a
reference remains.

The local build uses a read-only `vbntj-gpl-work` compiler/source volume and a
private tmpfs kernel tree. `build-extras.sh` is the portable Actions entry;
`build-local.sh` and `env.sh` support incremental local investigation. The
module checker validates architecture, exact vermagic and checksums. The
actual modem's ABI canary must pass before any experimental load.

## Explicit in-place laboratory profile

The user specifically authorized the in-place test after reviewing its kernel
buffer risk. The strengthened in-place KAT passed 120 guard/header checks at ESP offsets 0 and 20, with
45 successful borrowed-buffer operations per offset, then real isolated
ESP tunnels for AES128/192/256. This remains experimental, not a guarantee
for every skb layout or long-running production use.

Normal `spu-sha256-lab` builds reject `in_place=1` before registering any
algorithm. `spu-sha256-inplace-lab` is the separate explicit Actions build
profile: it sets `SPU_INPLACE_LAB=1`, and loading still requires `in_place=1`.
Neither profile emits IPKs or modifies the published feeds. The fast path
requires a linear, exclusive, uncloned skb and an exact ESP layout/length;
other requests use private copies. Full incoming SHA256-128 is checked before
trimming the private hardware framing, and the original length is restored
before completion. The KAT uses heap-backed scatterlists/IVs, tail guards and
optional `esp_offset=20` synthetic IPv4 framing.


## Current runtime status

The final Actions bundle passes full-tag KATs and bounded UDP exercises but
has reproduced TCP stalls. One interrupted run retained pending kernel requests
and prevented normal unload, requiring orderly-reboot recovery. Do not treat
its 48–51 Mbit/s successful samples as stable throughput. The latest guarded
RX build also reproduced loss of ping/SSH and a restart when drain and pool
fallback were combined with polling. Crash logging over SSH stopped without
a panic trace; serial capture is the next useful diagnostic. These modules
must remain laboratory-only.

## Host transfer pool experiment

Lab-only patch 002 adds `transfer_requests=64|128|256` (default 64), bounded by
256 host request slots; it does not alter the 64 Runner SA descriptors or the
firmware CPU ring. Allocation removes list nodes with `list_del_init`; completion
checks list membership in constant time instead of scanning every free node.
Read-only counters expose pool exhaustion, transmit errors, recycling and
duplicate frees. The option applies only to raw laboratory builds.

With a pool of 64, three AES cases at UDP 10 Mbit/s lost 35–36% of datagrams:
the loss count matched `lab_no_slot` exactly. At 256, loss was 3/3644, 0/3638,
and 0/3639, with all four driver error counters zero. These short same-device
runs include key updates and fragmented pings. Later TCP stress still stalled;
the larger pool does not establish stability or universally loss-free delivery.


## Standard comparison tools and external peer

Dispatch either raw profile with `standard_tools=true` to include static
upstream iperf3/wg, the tested WireGuard module and AES-GCM dependencies.
`standard-sources.tsv` pins every download; `build-standard-tools.sh` uses the
preserved compiler and a temporary static musl sysroot. The default stable
profiles do not invoke it. Artifact checksums include the userspace tools.

Test scripts accept `IPERF=/tmp/spu-sha256/iperf3-lab`. `benchmark.sh` supports
`AUTH_MODE=gcm`, CPU affinity pairs, MSS and test-veth RPS; it bounds client
runtime with `timeout`. `udp-control.sh` measures the same UDP rates without a
VPN. `wireguard-local.sh` compares the same two-modem-namespace topology.

External scripts require a dedicated peer at the explicitly allowlisted Mac
address, synthetic keys and no root-namespace XFRM configuration. They create
only their own namespace/veth and scoped temporary firewall chains, never flush
foreign rules and remove their changes on exit. `veth-offloads` accepts only
`spua`/`spub`; it cannot alter physical interfaces. `peer-ipsec.sh` must run only
inside the task-owned container. Private test keys stay in temporary storage.


Hybrid benchmark modes and queue-diagnostic KATs now also require
`ALLOW_UNSTABLE_RUNNER=1`. This is a technical lab opt-in, not evidence of a
fix. The unsafe drain/fallback combination remains rejected even with this
opt-in. Standard software/GCM/WireGuard comparisons do not require it.
