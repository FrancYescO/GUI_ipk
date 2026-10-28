#!/usr/bin/env bash
# Called only after the profile's pinned kernel configuration is prepared.
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
kernel="${1:?kernel directory}"
cross="${2:?cross compiler prefix}"
output="${3:?output directory}"
source="${CRYPTODEV_SOURCE_DIR:-${kernel%/*}/cryptodev-linux}"
archive="$repo_root/artifacts/cryptodev/source/cryptodev-linux-08644db.tar.gz"
expected=e795acb85118f1f39f0155df8fd28a3d79de7d1240b91bdf8cc9e2a1747d2642
echo "$expected  $archive" | sha256sum -c -
test ! -e "$source" # Fresh sources prevent reusing objects from another ABI.
mkdir -p "$source" "$output"
tar -xzf "$archive" --strip-components=1 -C "$source"
patch --batch -d "$source" -p1 < "$repo_root/patches/cryptodev/001-page-ownership-and-bounds.patch"
make -C "$source" KERNEL_DIR="$kernel" ARCH=arm CROSS_COMPILE="$cross" CRYPTODEV_CFLAGS=
cp "$source/cryptodev.ko" "$output/cryptodev.ko"
"${cross}strip" --strip-debug "$output/cryptodev.ko"
"${cross}objcopy" --remove-section .note.gnu.build-id "$output/cryptodev.ko"
cp "$kernel/.config" "$output/build.config"
if [[ "${BUILD_CRYPTODEV_TEST:-0}" == 1 ]]; then
  "${cross}gcc" -O2 -Wall -Wextra -I"$source" "$repo_root/build/cryptodev/tests/runtime.c" -o "$output/cryptodev-test"
  "${cross}strip" "$output/cryptodev-test"
fi
sha256sum "$output/cryptodev.ko"
