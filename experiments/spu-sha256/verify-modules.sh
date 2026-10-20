#!/bin/bash
set -euo pipefail
out=${1:?module directory}
cross=/app/staging_dir/toolchain-arm_v7-a_gcc-5.5.0_glibc-2.26_eabi/bin/arm-openwrt-linux-gnueabi-
for module in "$out"/*.ko; do
  "${cross}strip" --strip-debug "$module"
  magic=$(strings "$module" | sed -n 's/^vermagic=//p' | sed 's/[[:space:]]*$//')
  test "$magic" = '4.1.52 SMP preempt mod_unload ARMv7'
  "${cross}readelf" -h "$module" | grep -Eq 'Machine:[[:space:]]+ARM'
  "${cross}nm" --undefined-only "$module" | awk '{print $NF}' | sort -u > "$module.undefined-symbols"
done
(cd "$out" && sha256sum ./*.ko > SHA256SUMS)
