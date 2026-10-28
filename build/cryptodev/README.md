# Cryptodev for the eight kernel ABI profiles

Cryptodev exposes kernel CryptoAPI operations through `/dev/crypto`. The IPKs
are additive: they stage `cryptodev.ko` under
`/usr/lib/kernel-module-candidates/<profile>/`, without replacing a stock module,
installing an autoload entry, changing OpenSSL or loading a hardware accelerator.
The exact installed `kernel` package dependency must match. VBNT-S uses the
VBNT-K public feed alias.

| Profile | Feed | New module validation |
| --- | --- | --- |
| 4.1.38-vbnto | `kernel/4.1.38-vbnto` | Final CI artifact functionally tested on .45 |
| 4.1.38-vbntk | `kernel/4.1.38-vbntk` | Final CI artifact functionally tested on .204 |
| 4.1.52-vbntk | `kernel/4.1.52-vbntk` | Offline symbols; existing stock cryptodev busy on .69 |
| 4.1.52-vcnt3 | `kernel/4.1.52-vcnt3-candidates` | Offline candidates |
| 4.1.52-vcnt2 | `kernel/4.1.52-vcnt2-candidates` | Offline candidates (both firmware 19.4.0381 and 19.4.0393) |
| 4.1.52-vcntj | `kernel/4.1.52-vcntj-candidates` | Offline candidates |
| 4.1.52-vcnta | `kernel/4.1.52-vcnta-candidates` | Offline candidates; stock TUN is built in |
| 4.1.52-vbntv | `kernel/4.1.52-vbntv-candidates` | Offline candidates; stock TUN is built in |

Enable the matching source from https://francyesco.github.io/GUI_ipk/kernel/.
For example, on the matching VBNT-K/S 4.1.38 ABI:

```sh
opkg update
opkg install kmod-cryptodev-4.1.38-vbntk
# Only if no cryptodev is already loaded or in use:
insmod /usr/lib/kernel-module-candidates/4.1.38-vbntk/cryptodev.ko
chmod 600 /dev/crypto
# After applications have closed their handles:
rmmod cryptodev
```

A stock driver already in use must be left loaded. In particular, the .69 has
stock cryptodev open in nginx and generic_pnpd; the new module was not substituted.
Installing the staged package alone does not activate the driver. Applications
need explicit cryptodev support; installing this module does not automatically
accelerate OpenSSL. Actual drivers used by the 4.1.38 tests were `cbc(aes-generic)`,
`sha256-generic` and `hmac(sha256-generic)` (software implementations).

## Source and downstream changes

* Upstream: https://github.com/cryptodev-linux/cryptodev-linux
* Version: 1.14, commit `08644db02d43478f802755903212f5ee506af73b`.
* Source archive: `artifacts/cryptodev/source/cryptodev-linux-08644db.tar.gz`.
* Archive SHA256: `e795acb85118f1f39f0155df8fd28a3d79de7d1240b91bdf8cc9e2a1747d2642`.
* License: GPL-2.0, included in the pinned source archive (`COPYING`).
* Patch: `patches/cryptodev/001-page-ownership-and-bounds.patch`.

The downstream patch addresses partial/stale page ownership and range arithmetic
in the synchronous zero-copy path discussed in upstream PRs
[103](https://github.com/cryptodev-linux/cryptodev-linux/pull/103) and
[104](https://github.com/cryptodev-linux/cryptodev-linux/pull/104), associated with
CVE-2026-28529. It preserves ordinary in-place operation, bounds pinned buffers
and requires `CAP_SYS_ADMIN` when opening the device. This is a downstream patch,
not a claim that upstream has merged the proposals or that every API path has
been audited. Async builds are rejected at compile time. The requested device
mode is 0600; firmware mdev rules may override it, so the module also enforces the
capability check independently of filesystem modes.

## Tests and reproducibility

`tests/test_cryptodev.py` checks the immutable archive hash, applies the patch and
compiles the actual `zc.c` against a mock page-pinning environment. Ten scenarios
cover successful separate/in-place buffers, partial source/destination pins,
repeated failure after success, null input, overflow, oversized requests and
allocation failure. This regression test is run in CI before building modules.

`build/cryptodev/tests/runtime.c` exercises AES-CBC using NIST known answers
(encrypt/decrypt, separate/in-place buffers, copy/zero-copy), SHA256, RFC4231 HMAC,
invalid requests and unprivileged-open rejection. On both .45 and .204, the exact
CI payload (SHA256 `9736f4dc5d68dacbe021849f108fcaeefab611334302f79b74f9663ed96e65af`)
passed all these tests, including EPERM on a temporary node in `/dev` with mode
0666. The temporary nodes and modules were removed after testing. AES-GCM tests are included, but
GCM session creation was unavailable on both tested 4.1.38 configurations: GCM is
not marked runtime validated. Neither SPU loading nor performance/acceleration
claims are part of these tests. Boot IDs and kernel taint remained unchanged;
the temporary modules were unloaded and temporary device nodes/files removed.
Results are recorded under each profile in this directory and tied to the exact
tested CI module hashes. Earlier local-build logs are retained separately as
`preliminary-runtime.txt`. These preliminary binaries differed only in diagnostic
source filenames and have been superseded by the CI payloads for runtime evidence.

`.github/workflows/build-cryptodev.yml` builds all eight profiles from pinned GPL
sources/toolchains and original runtime configurations using the existing ABI
patches. `scripts/build-cryptodev.sh` builds only this external module and strips
debug/build-ID sections. `scripts/cryptodev_packages.py` checks original firmware
exports and produces deterministic IPKs; CI must reproduce the committed IPK
SHA256 byte for byte. Config snapshots and manifest hashes record the inputs.
Candidates have no hardware runtime validation: offline symbol closure alone
does not prove complete structure layout or behavior compatibility.

The first dedicated source CI run was
[40692416645](https://github.com/FrancYescO/GUI_ipk/actions/runs/40692416645).
It built all five modules and checked their firmware imports. Its byte comparison
against preliminary local builds failed because `WARN_ON` embeds absolute source
filenames. The committed IPKs now use that CI output, with the standard source
paths selected by the build recipes. The second clean CI run [40693292868](https://github.com/FrancYescO/GUI_ipk/actions/runs/40693292868) reproduced all original five packages; the extended matrix covers the three newer profiles as well;
overriding the build/source directories can change diagnostic strings and hashes.
