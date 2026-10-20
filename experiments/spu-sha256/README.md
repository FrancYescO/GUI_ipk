# SHA256-128 laboratory for Damson / BCM63138 / Linux 4.1.52

This branch keeps experimental raw modules separate from published kernel feeds.
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
It makes private packet copies, checks tags in constant time, and does not
return decrypted bytes on authentication failure. All requests must complete
before unloading; a timed-out KAT deliberately retains its outstanding request
and callback rather than freeing memory still owned by hardware.

`kat_extended.c` uses explicitly selected generic software algorithms as its
independent reference, checks encryption as well as decryption, and can corrupt
the tag, ESP header, IV or ciphertext. `kat-run.sh` checks initial module state
and checksums, fails on the first unsuccessful test, and uses signal/exit traps
for normal cleanup. No forced module removal or reboot is used.

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
