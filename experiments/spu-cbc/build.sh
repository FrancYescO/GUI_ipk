#!/bin/bash
# Called after the normal pinned kernel prepare/configuration and ABI patches.
# Output is deliberately raw lab modules, never a feed IPK.
set -euo pipefail
sdk=${1:?SDK}
kernel=${2:?prepared kernel}
cross=${3:?cross compiler prefix}
work=${4:?fresh working directory}
out=${5:?output directory}
repo=$(cd "$(dirname "$0")/../.." && pwd)
test ! -e "$work"
mkdir -p "$work" "$out"
bash "$repo/scripts/build-damson-spu.sh" "$sdk" "$kernel" "$cross" "$work/driver"
cp "$work/driver/bcmspu.ko" "$out/baseline-bcmspu.ko"
python "$repo/experiments/spu-cbc/prepare.py" "$work/driver"
make -C "$kernel" ARCH=arm CROSS_COMPILE="$cross" SDK="$sdk" M="$work/driver" modules
cp -R "$repo/experiments/spu-cbc" "$work/test"
make -C "$kernel" ARCH=arm CROSS_COMPILE="$cross" \
  KBUILD_EXTRA_SYMBOLS="$work/driver/Module.symvers" M="$work/test" modules
cp -R "$repo/build/vbntj-canary" "$work/canary"
make -C "$kernel" ARCH=arm CROSS_COMPILE="$cross" M="$work/canary" modules
cp "$work/driver/bcmspu.ko" "$work/test/"*.ko "$work/canary/vbntj_abi_canary.ko" "$out/"
cp "$kernel/.config" "$out/build.config"
for module in "$out"/*.ko; do
 "${cross}strip" --strip-debug "$module"
 "${cross}readelf" -p .modinfo "$module" | grep -F 'vermagic=4.1.52 SMP preempt mod_unload ARMv7'
 "${cross}nm" --undefined-only "$module" | awk '{print $NF}' | LC_ALL=C sort -u > "$module.undefined-symbols"
done
(cd "$out" && sha256sum *.ko > SHA256SUMS)
