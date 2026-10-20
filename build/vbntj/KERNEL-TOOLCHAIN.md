# Damson kernel-only compiler seed v1

This immutable snapshot preserves the existing Linux amd64 OpenWrt GCC 5.5.0
C compiler and its host libraries used for the successful preliminary SPU
runtime tests on VBNTJ Linux 4.1.52 on 20 October 2026. It is a kernel-only
build input, not a claim of a newly reconstructed complete userspace SDK.
Run it inside the repository Ubuntu 12.04 compatibility container at /app.

The archive contains only staging_dir/host and the corresponding toolchain
prefix. SHA256SUMS pins every asset. GCC-CONFIGURATION.txt records the actual
compiler configuration, including --without-headers and C-only bootstrap.

The exact source archives present alongside that compiler are included:
GCC 5.5.0, binutils 2.28.1, glibc 2.26, GMP 6.1.0, MPFR 3.1.4, MPC 1.0.3.
They have their own checksums and must not be confused with differently
packaged sources in damson-build-inputs-v1. GNU licenses and runtime exception
texts are included as COPYING*. Embedded component licenses remain applicable.

OpenWrt/GPL build recipes for this target are preserved in the separate
repository damson-build-inputs-v1 release (VMG8825-B50B GPL snapshot at
avwarez/vmg8825_b50b af23960e39003ba7788f5ced0c256b1bc676a712).
The full source-build path remains in scripts/build-vbntj-kmods.sh.

SPU builds verify the seed against the committed digest before extracting it,
check GCC version again in the container, and rebuild the kernel modules from
the pinned kernel/SDK inputs plus committed patches. No router binaries,
credentials or runtime logs are included in this seed.
