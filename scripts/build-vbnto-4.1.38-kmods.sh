#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work_dir="${WORK_DIR:-/build/openwrt}"
output_dir="${OUTPUT_DIR:-$repo_root/dist}"
runtime_config="$repo_root/build/vbnto-4.1.38/kernel.config.gz"

if [[ ! -f "$runtime_config" ]]; then
  echo "Missing router kernel configuration: $runtime_config" >&2
  exit 1
fi

BUILD_CONFIG="$repo_root/build/kmod-tun.config" \
BUILD_KMODS=1 BUILD_SPU=0 PREPARE_KERNEL_ONLY=1 \
  "$repo_root/scripts/build-packages.sh"

kernel_dir="$work_dir/build_dir/target-arm_cortex-a9+neon_glibc_eabi/linux-brcm63xx-tch_VBNTS/linux-4.1.38"
toolchain_bin="$work_dir/staging_dir/toolchain-arm_cortex-a9+neon_gcc-4.8-linaro_glibc_eabi/bin"
cross="$toolchain_bin/arm-openwrt-linux-gnueabi-"
probe_dir="$output_dir/vbnto-4.1.38-probe"

test -f "$kernel_dir/Makefile"
test -x "${cross}gcc"
mkdir -p "$probe_dir"
gzip -dc "$runtime_config" > "$kernel_dir/.config"
"$kernel_dir/scripts/config" --file "$kernel_dir/.config" --module TUN

export PATH="$toolchain_bin:$work_dir/staging_dir/host/bin:$PATH"
export BRCMDRIVERS_DIR="$work_dir/extern/bcmopen-iopsys-DG400/bcmdrivers"
export BCM_BUILD_DIR="$work_dir/extern/bcmopen-iopsys-DG400"
export LINUX_DIR="$kernel_dir"
export BRCM_CHIP=63138
export BCM_KF=y
export STAGING_DIR="$work_dir/staging_dir/target-arm_cortex-a9+neon_glibc_eabi"
kernel_make=(make -C "$kernel_dir" ARCH=arm CROSS_COMPILE="$cross")
"${kernel_make[@]}" olddefconfig

for required in \
  'CONFIG_TUN=m' \
  'CONFIG_BCM_KF_SKB_DEFINES=y' \
  'CONFIG_BCM_KF_NETDEV_PATH=y' \
  '# CONFIG_BCM_MAP is not set' \
  '# CONFIG_MODVERSIONS is not set'; do
  if ! grep -Fxq "$required" "$kernel_dir/.config"; then
    echo "Router ABI option changed after olddefconfig: $required" >&2
    exit 1
  fi
done

"${kernel_make[@]}" modules_prepare
if [[ "${BUILD_VALIDATION_KAT:-0}" == 1 ]]; then
  cp -R "$repo_root/build/vbnto-4.1.38/validation/kat" "$work_dir/candidate-kat"
  "${kernel_make[@]}" M="$work_dir/candidate-kat" modules
  cp "$work_dir/candidate-kat/kmod38_kat.ko" "$probe_dir/"
fi
"${kernel_make[@]}" -j2 drivers/net/tun.ko
cp "$kernel_dir/drivers/net/tun.ko" "$probe_dir/tun.ko"
cp "$kernel_dir/.config" "$probe_dir/build.config"
if [[ "${BUILD_SPU:-0}" == 1 ]]; then
  sdk_dir="$work_dir/extern/bcmopen-iopsys-DG400"
  SPU_OFFLOAD_PATCH="$repo_root/patches/vbnts-spu/002-opt-in-esp-flow-offload.patch" \
    "$repo_root/scripts/build-damson-spu.sh" \
    "$sdk_dir" "$kernel_dir" "$cross" "$work_dir/vbnto-spu"
  cp "$work_dir/vbnto-spu/bcmspu.ko" "$probe_dir/bcmspu.ko"
  "${cross}nm" --undefined-only "$probe_dir/bcmspu.ko" \
    | awk '{print $NF}' | LC_ALL=C sort -u \
    > "$probe_dir/bcmspu.undefined-symbols"
  "${cross}readelf" -p .modinfo "$probe_dir/bcmspu.ko" \
    > "$probe_dir/bcmspu.modinfo.txt"
  grep -Fq '4.1.38 SMP preempt mod_unload ARMv7' "$probe_dir/bcmspu.modinfo.txt"
  cp -R "$repo_root/build/vbntj-spu-test" "$work_dir/vbnto-spu-test"
  "${kernel_make[@]}" M="$work_dir/vbnto-spu-test" modules
  cp "$work_dir/vbnto-spu-test/damson_spu_test.ko" "$probe_dir/"
  "${cross}readelf" -p .modinfo "$probe_dir/damson_spu_test.ko" \
    > "$probe_dir/damson_spu_test.modinfo.txt"
  grep -Fq '4.1.38 SMP preempt mod_unload ARMv7' "$probe_dir/damson_spu_test.modinfo.txt"
fi
"${cross}nm" --undefined-only "$probe_dir/tun.ko" \
  | awk '{print $NF}' | LC_ALL=C sort -u \
  > "$probe_dir/tun.undefined-symbols"
"${cross}readelf" -p .modinfo "$probe_dir/tun.ko" \
  > "$probe_dir/tun.modinfo.txt"
grep -Fq '4.1.38 SMP preempt mod_unload ARMv7' "$probe_dir/tun.modinfo.txt"
(
  cd "$probe_dir"
  sha256sum tun.ko build.config tun.undefined-symbols > SHA256SUMS
  if [[ "${BUILD_SPU:-0}" == 1 ]]; then
    sha256sum bcmspu.ko bcmspu.undefined-symbols damson_spu_test.ko >> SHA256SUMS
  fi
)
echo "Built router-configured TUN probe in $probe_dir"
if [[ "${MODULE_SET:-tested}" == expanded ]]; then
  "$repo_root/scripts/build-vbnto-4.1.38-expanded.sh" \
    "$kernel_dir" "$cross" "$output_dir/vbnto-4.1.38-expanded"
fi
