#!/bin/bash
set -euo pipefail
kernel=${1:?prepared kernel}
cross=${2:?cross compiler prefix}
work=${3:?fresh work directory}
out=${4:?output directory}
repo=$(cd "$(dirname "$0")/../.." && pwd)
test ! -e "$work"
mkdir -p "$work" "$out"
archive="$repo/artifacts/cryptodev/source/cryptodev-linux-08644db.tar.gz"
echo "e795acb85118f1f39f0155df8fd28a3d79de7d1240b91bdf8cc9e2a1747d2642  $archive" | sha256sum -c -
tar -xzf "$archive" --strip-components=1 -C "$work"
patch --batch --forward -d "$work" -p1 < "$repo/patches/cryptodev/001-page-ownership-and-bounds.patch"
python "$repo/experiments/spu-cbc/prepare-bridge.py" "$work"
make -C "$work" KERNEL_DIR="$kernel" ARCH=arm CROSS_COMPILE="$cross" CRYPTODEV_CFLAGS=
cp "$work/cryptodev_cbc_lab.ko" "$out/"
"${cross}strip" --strip-debug "$out/cryptodev_cbc_lab.ko"
"${cross}nm" --undefined-only "$out/cryptodev_cbc_lab.ko" | awk '{print $NF}' | LC_ALL=C sort -u > "$out/cryptodev_cbc_lab.ko.undefined-symbols"
