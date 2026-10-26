# OpenVPN 2.6.23 for the archived VBNTS userspace

ARM Cortex-A9/NEON IPKs built with the repository's GCC 4.8.3/glibc
toolchain. Choose **one** of `openvpn-openssl` and `openvpn-mbedtls`.
The directory also contains the new `libcap-ng` dependency and `liblz4`.
Other dependencies, including the selected TLS library and `liblzo`, use
the versions in the existing feed. These IPKs have not been tested on a router.

This is a userspace update, with the existing OpenWrt init script and UCI
configuration. OpenSSL remains 1.0.2t and mbedTLS remains 2.16.3. The archived
recipe's disabled NTLM proxy support is preserved; mbedTLS has no DES support.

Back up and review existing configurations before installing. OpenVPN 2.6
removes options such as `ns-cert-type`, `keysize` and `ncp-disable`; `cipher`
alone no longer selects TLS data-channel ciphers. The UCI allowlist accepts
`data_ciphers`, `data_ciphers_fallback`, `tls_crypt_v2` and `tls_ciphersuites`,
and retains `ncp_ciphers` as a compatibility alias.

## DCO

DCO is disabled. The upstream OpenVPN 2.6 DCO documentation identifies Linux
5.4 and newer as known working. The vendor kernels in this repository are
4.1.38/4.1.52 and require a dedicated driver backport plus ABI and runtime
validation. No kernel module is included here. Existing TUN support is required.

## Rebuild

Use the normal userspace workflow, which applies `build/userspace-overlay/`
before generating package metadata. For a clean targeted build, select
`network/services/openvpn` in the userspace profile, which prepares the
archived kernel headers and host tools. The published feed sanitizer still
excludes kernel packages.

The local verification built the userspace dependencies first, then ran
`make -j8 package/network/services/openvpn/compile NO_DEPS=1 V=s` in the
Linux buildroot to verify OpenVPN independently of kernel-module packaging.
This does not establish that a complete clean kernel or feed build passed.

## Verification

Both variants compiled successfully. Each packaged ARM executable was extracted
from its final IPK and started through the toolchain's ARM loader in Docker.
Both reported version 2.6.23 and passed OpenVPN's AES-256-CBC / SHA256 encryption
and decryption self-test. This is an emulated userspace test, not a VPN tunnel
or router runtime test. The small package index was checked with
`scripts/verify-feed.sh`; `SHA256SUMS` covers the four IPKs.
