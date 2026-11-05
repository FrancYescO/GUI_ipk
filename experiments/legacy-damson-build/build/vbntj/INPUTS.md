# Damson build inputs v1

Pinned inputs for the VMG8825-B50B GPL-based Damson Linux 4.1.52 module build.
The Release assets are preserved without overwriting existing releases.
`SHA256SUMS` and `INPUTS.tsv` record each archive's digest, original location,
license summary and purpose. Builds trust the manifest committed in GUI_ipk,
not a checksum downloaded alongside an untrusted archive.

The ten archives are the GPL buildsystem snapshot, Linux 4.1.52, Broadcom
502L07 SDK, binutils 2.28.1, GCC 5.5.0, glibc 2.26, GMP 6.1.0, MPC 1.0.3,
MPFR 3.1.4 and XZ 5.0.4. No new prebuilt cross-toolchain is published here;
the build reconstructs it from these sources and caches installed products.

The GPL snapshot is produced by `git archive --format=tar` at commit
`af23960e39003ba7788f5ced0c256b1bc676a712`, compressed on Linux with GNU `gzip -n -6`.
It contains the published Git tree, including its bundled prebuilt components
and license files, with no local edits or generated build directories.
The original repository is https://github.com/avwarez/vmg8825_b50b, tag
`V5.17(ABNY.6)C0`.

The SDK/toolchain archives originate from the public GPL mirror
https://github.com/threader/DX5401-B0-V517ABYO6C0_GPL at commit
`5df85c8c423ee935eed37b81f0d76dc569e2deb0`; Linux comes from kernel.org.
GCC is fetched through GitHub's media endpoint to obtain the actual archive,
rather than its Git LFS pointer. Archive contents and embedded licenses are
preserved; the manifest summaries do not replace each component's terms or
relicense vendor binaries as GPL.

The seed defconfig mentions SDK `P1` and suffix `_200630`, but the pinned
public Kconfig defines neither option. `make defconfig` removes both, leaving
SDK `502L07` and the `bcmsdk-502L07P1-` kernel patch prefix. The resulting
build requests `broadcom_sdk_502L07_pkg.tar.bz2`. The stored `.xz` is converted
with `xz -dc | bzip2 -9` and the result must match SHA-256
`87b0bd62c8988e01aae24a1c37bfe19805217900ef0b5b44348c5f3fd4b2927f`.
The build rejects a normalized configuration that requests another SDK variant.

Normal fetches use only this repository's Release or a locally cached archive
with the pinned digest. Upstream access is confined to explicit bootstrap mode.
This preserves source inputs; Docker base images, Ubuntu package repositories,
GitHub Actions and the installed toolchain cache remain separate dependencies.
