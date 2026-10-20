#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_dir="${SOURCE_DIR:-/app}"
output_dir="${OUTPUT_DIR:-/out}"
module_set="${MODULE_SET:-tun}"
canary_dir="$source_dir/.vbntj-abi-canary"
build_connmark=0
build_spu=0
build_spu_lab=0
build_spu_inplace_lab=0
lab_modules=()

case "$module_set" in
  tun)
    module_targets=(drivers/net/tun.ko)
    ;;
  network-smoke)
    module_targets=(drivers/net/tun.ko drivers/net/usb/usbnet.ko drivers/net/usb/cdc_ether.ko)
    ;;
  qos-probe)
    module_targets=(net/sched/act_connmark.ko)
    build_connmark=1
    ;;
  spu-sha256-inplace-lab)
    module_targets=()
    build_spu=1
    build_spu_lab=1
    build_spu_inplace_lab=1
    ;;
  spu-sha256-lab)
    module_targets=()
    build_spu=1
    build_spu_lab=1
    ;;
  spu-probe)
    module_targets=(bcmspu.ko)
    build_spu=1
    ;;
  router-tested)
    module_targets=(drivers/net/tun.ko net/sched/act_connmark.ko)
    build_connmark=1
    ;;
  *)
    echo "Unsupported MODULE_SET: $module_set" >&2
    exit 1
    ;;
esac

if [[ ! -f "$source_dir/configs/vmg8825_b50b/vmg8825_b50b.defconfig" ]]; then
  echo "The pinned VMG8825-B50B GPL source is missing from $source_dir" >&2
  exit 1
fi

case "$output_dir" in
  /|""|"$source_dir")
    echo "Refusing unsafe OUTPUT_DIR: $output_dir" >&2
    exit 1
    ;;
esac

cd "$source_dir"
export P=vmg8825_b50b
export TOPDIR="$source_dir"
./configs/preCfg.sh "$P"
make -j1 defconfig

# Inputs are verified against the repository manifest even when supplied by
# the host workflow/cache. Container builds do not contact upstream mirrors.
DAMSON_INCLUDE_GPL=0 DAMSON_INPUTS_MODE=verify \
  "$repo_root/scripts/fetch-damson-build-inputs.sh" "$source_dir/dl"

# The public GPL Kconfig does not define the seed's SDK patch/suffix options.
# defconfig removes them, selecting the base SDK while retaining P1 kernel
# patches. Reject future changes instead of silently renaming a different SDK.
if grep -Eq '^CONFIG_BRCM_SDK_(PATCH_VERSION|PACKAGE_SUFFIX)=".+"' .config; then
  echo "GPL configuration requests an SDK variant absent from the pinned inputs" >&2
  exit 1
fi
if ! grep -qx 'CONFIG_BRCM_SDK_VERSION="502L07"' .config; then
  echo "GPL configuration does not select the pinned 502L07 SDK" >&2
  exit 1
fi
sdk_archive="$source_dir/dl/broadcom_sdk_502L07_pkg.tar.bz2"
sdk_archive_sha256=87b0bd62c8988e01aae24a1c37bfe19805217900ef0b5b44348c5f3fd4b2927f
if [[ ! -f "$sdk_archive" ]]; then
  xz --decompress --stdout "$source_dir/dl/broadcom_sdk_502L07_pkg.tar.xz" \
    | bzip2 -9 > "$sdk_archive.tmp"
  mv "$sdk_archive.tmp" "$sdk_archive"
fi
printf '%s  %s\n' "$sdk_archive_sha256" "$sdk_archive" | sha256sum --check --status || {
  echo "Invalid recompressed Broadcom SDK: $sdk_archive" >&2
  exit 1
}

# The legacy OpenWrt rules address several already-installed host utilities
# through staging_dir/host/bin. Populate that prefix without rebuilding the
# same Ubuntu 12.04 tools from obsolete private mirrors.
host_bin="$source_dir/staging_dir/host/bin"
mkdir -p "$host_bin"
for host_tool in \
  aclocal autoconf autoheader autom4te automake autoreconf \
  find gettext libtool libtoolize m4 sed quilt; do
  host_tool_path="$(command -v "$host_tool")"
  ln -sf "$host_tool_path" "$host_bin/$host_tool"
done

# The public GPL repository intentionally omits the prebuilt cross-toolchain.
# GCC's configure step expects its host-side arithmetic dependencies in the
# OpenWrt host staging prefix. Build them explicitly in dependency order;
# toolchain/install does not pull them in early enough in this legacy tree.
cached_gcc="$source_dir/staging_dir/toolchain-arm_v7-a_gcc-5.5.0_glibc-2.26_eabi/bin/arm-openwrt-linux-gnueabi-gcc"
if [[ -x "$cached_gcc" ]] && \
   [[ "$("$cached_gcc" -dumpfullversion -dumpversion)" == 5.5.0 ]]; then
  echo 'Reusing verified cached OpenWrt GCC 5.5.0 toolchain'
else
  make -j1 V=s tools/gmp/install
  make -j1 V=s tools/mpfr/install
  make -j1 V=s tools/mpc/install
  make -j1 V=s toolchain/install
fi
make -j1 V=s target/linux/prepare

kernel_base="$source_dir/build_dir/target-arm_v7-a_glibc-2.26_eabi/linux-brcm963xx_vmg8825_b50b"
kernel_dir="$kernel_base/linux-4.1.52"
sdk_dir="$kernel_base/broadcom-sdk-502L07"
toolchain_dir="$source_dir/staging_dir/toolchain-arm_v7-a_gcc-5.5.0_glibc-2.26_eabi"
cross="$toolchain_dir/bin/arm-openwrt-linux-gnueabi-"
cross_gcc="${cross}gcc"
cross_nm="${cross}nm"
cross_readelf="${cross}readelf"
cross_strip="${cross}strip"

for required in "$kernel_dir/Makefile" "$sdk_dir" "$cross_gcc"; do
  if [[ ! -e "$required" ]]; then
    echo "Expected VBNTJ build component was not created: $required" >&2
    exit 1
  fi
done

compiler_version="$("$cross_gcc" -dumpfullversion -dumpversion)"
if [[ "$compiler_version" != 5.5.0 ]]; then
  echo "Refusing non-Damson compiler version: $compiler_version" >&2
  exit 1
fi

patch --batch --forward --directory "$kernel_dir" -p1 \
  < "$repo_root/patches/vbntj-4.1.52/001-damson-network-abi.patch"

cp "$repo_root/build/vbntj/kernel-4.1.52-damson.config" "$kernel_dir/.config"
"$kernel_dir/scripts/config" --file "$kernel_dir/.config" \
  --enable WIRELESS_EXT \
  --enable WEXT_CORE \
  --enable WEXT_PROC \
  --enable WEXT_SPY \
  --enable WEXT_PRIV \
  --disable BCM_MAP \
  --module TUN \
  --module USB_USBNET \
  --module USB_NET_CDCETHER
if [[ "$build_connmark" -eq 1 ]]; then
  "$kernel_dir/scripts/config" --file "$kernel_dir/.config" \
    --module NET_ACT_CONNMARK
fi

export PATH="$toolchain_dir/bin:$PATH"
export BCM_BUILD_DIR="$sdk_dir"
export KERNEL_BUILD_DIR="$kernel_base"
export LINUX_DIR="$kernel_dir"
export TOOLCHAIN_DIR="$toolchain_dir"
export TARGET_DIR="$source_dir/staging_dir/target-arm_v7-a_glibc-2.26_eabi"
export STAGING_DIR="$TARGET_DIR"
export BCM_PROFILE=VMG8825_B50B
export TARGET_CROSS="$cross"
export BCM_HOSTTOOLS_DIR="$source_dir/staging_dir/host/bin/502L07"
export BRCM_CHIP=63138
export BCM_KF=y

kernel_make=(make -C "$kernel_dir" ARCH=arm CROSS_COMPILE="$cross")
"${kernel_make[@]}" olddefconfig
"${kernel_make[@]}" modules_prepare

for symbol in WIRELESS_EXT WEXT_CORE WEXT_PROC WEXT_SPY WEXT_PRIV; do
  if ! grep -qx "CONFIG_${symbol}=y" "$kernel_dir/.config"; then
    echo "Required runtime ABI option CONFIG_${symbol}=y was lost" >&2
    exit 1
  fi
done
if grep -qx 'CONFIG_MODVERSIONS=y' "$kernel_dir/.config"; then
  echo "Damson runtime has CONFIG_MODVERSIONS disabled" >&2
  exit 1
fi
if [[ "$build_connmark" -eq 1 ]]; then
  for symbol in IFB NET_SCH_INGRESS NET_CLS_U32 NET_ACT_POLICE; do
    if ! grep -qx "CONFIG_${symbol}=y" "$kernel_dir/.config"; then
      echo "Required built-in QoS option CONFIG_${symbol}=y was lost" >&2
      exit 1
    fi
  done
  if ! grep -qx 'CONFIG_NET_ACT_CONNMARK=m' "$kernel_dir/.config"; then
    echo "QoS probe requires CONFIG_NET_ACT_CONNMARK=m" >&2
    exit 1
  fi
fi

if [[ "$build_spu" -eq 0 ]]; then
  "${kernel_make[@]}" "${module_targets[@]}"
fi
if [[ "$build_spu" -eq 1 ]]; then
  "$repo_root/scripts/build-damson-spu.sh" "$sdk_dir" "$kernel_dir" "$cross" "$source_dir/.damson-spu"
  cp -R "$repo_root/build/vbntj-spu-test" "$source_dir/.damson-spu-test"
  "${kernel_make[@]}" M="$source_dir/.damson-spu-test" modules
fi
if [[ "$build_spu_lab" -eq 1 ]]; then
  lab_dir="$source_dir/.spu-sha256-lab"
  rm -rf "$lab_dir"
  SPU_INPLACE_LAB="$build_spu_inplace_lab" bash "$repo_root/experiments/spu-sha256/build-extras.sh"     "$sdk_dir" "$kernel_dir" "$cross" "$source_dir/.damson-spu"     "$source_dir/.damson-spu-test" "$lab_dir"
  lab_modules=("$lab_dir/armcrypto/aes-arm.ko" "$lab_dir/armcrypto/sha256-arm.ko" "$lab_dir/hybrid/spu_sha256_hybrid.ko")
fi
rm -rf "$canary_dir"
cp -R "$repo_root/build/vbntj-canary" "$canary_dir"
"${kernel_make[@]}" M="$canary_dir" modules

mkdir -p "$output_dir"
rm -f -- \
  "$output_dir"/*.ko \
  "$output_dir"/*.ipk \
  "$output_dir"/*.undefined-symbols \
  "$output_dir/SHA256SUMS" \
  "$output_dir/BUILD-METADATA.txt"
if [[ "$build_spu" -eq 0 ]]; then
  for target in "${module_targets[@]}"; do
    module_name="$(basename "$target")"
    cp "$kernel_dir/$target" "$output_dir/$module_name"
  done
fi
for module in ${lab_modules[@]+"${lab_modules[@]}"}; do
  cp "$module" "$output_dir/$(basename "$module")"
done
if [[ "$build_spu" -eq 1 ]]; then
  cp "$source_dir/.damson-spu/bcmspu.ko" "$output_dir/"
  cp "$source_dir/.damson-spu-test/damson_spu_test.ko" "$output_dir/"
fi
cp "$canary_dir/vbntj_abi_canary.ko" "$output_dir/"

for module in "$output_dir"/*.ko; do
  "$cross_strip" --strip-debug "$module"
  vermagic="$("$cross_readelf" -p .modinfo "$module" \
    | sed -n 's/.*vermagic=//p' | head -n1 | sed 's/[[:space:]]*$//')"
  if [[ "$vermagic" != '4.1.52 SMP preempt mod_unload ARMv7' ]]; then
    echo "Unexpected vermagic in $(basename "$module"): $vermagic" >&2
    exit 1
  fi
done

for module in "$output_dir"/*.ko; do
  module_name="$(basename "$module" .ko)"
  "$cross_nm" --undefined-only "$module" \
    | awk '{print $NF}' | LC_ALL=C sort -u \
    > "$output_dir/${module_name}.undefined-symbols"
done
if [[ -f "$output_dir/tun.ko" ]] && \
   ! cmp -s "$repo_root/build/vbntj/tun.undefined-symbols" "$output_dir/tun.undefined-symbols"; then
  echo "tun.ko undefined-symbol ABI differs from the router-validated baseline" >&2
  diff -u "$repo_root/build/vbntj/tun.undefined-symbols" "$output_dir/tun.undefined-symbols" || true
  exit 1
fi

build_manual_ipk() {
  local module="$1"
  local module_stem package_name package_version package_arch package_file
  local package_root control_root data_root

  module_stem="$(basename "$module" .ko)"
  package_name="kmod-${module_stem//_/-}-damson-4.1.52-manual"
  package_version="4.1.52-1"
  package_arch="brcm963xx"
  if [[ "$module_stem" == bcmspu ]]; then
    # This is the architecture accepted by OPKG on the validated VBNTJ.
    package_arch="arm_cortex-a9"
  fi
  package_file="$output_dir/${package_name}_${package_version}_${package_arch}.ipk"
  package_root="$output_dir/.ipk-build/$package_name"
  control_root="$package_root/control"
  data_root="$package_root/data"

  rm -rf "$package_root"
  mkdir -p "$control_root" "$data_root/lib/modules/4.1.52"
  cp "$module" "$data_root/lib/modules/4.1.52/$module_stem.ko"
  cat > "$control_root/control" <<EOF
Package: $package_name
Version: $package_version
Architecture: $package_arch
Section: kernel
Priority: optional
Maintainer: GUI_ipk reproducible build
Description: Manual-only Damson 4.1.52 kernel module ($module_stem)
X-Damson-Firmware: 19.4.0866-3401052
X-Damson-Target: VBNTJ_502L07p1
X-Kernel-Vermagic: 4.1.52 SMP preempt mod_unload ARMv7
X-Manual-Install-Only: yes
EOF

  (
    cd "$control_root"
    tar --owner=0 --group=0 --numeric-owner -czf "$package_root/control.tar.gz" ./control
  )
  (
    cd "$data_root"
    tar --owner=0 --group=0 --numeric-owner -czf "$package_root/data.tar.gz" \
      "./lib/modules/4.1.52/$module_stem.ko"
  )
  printf '2.0\n' > "$package_root/debian-binary"
  (
    cd "$package_root"
    tar --owner=0 --group=0 --numeric-owner -czf "$package_file" \
      ./debian-binary ./data.tar.gz ./control.tar.gz
  )
}

rm -rf "$output_dir/.ipk-build"
if [[ "$build_spu_lab" -eq 0 ]]; then
for target in "${module_targets[@]}"; do
  build_manual_ipk "$output_dir/$(basename "$target")"
done
fi
rm -rf "$output_dir/.ipk-build"

(
  cd "$output_dir"
  if [[ "$build_spu_lab" -eq 1 ]]; then
    sha256sum ./*.ko > SHA256SUMS
  else
    sha256sum ./*.ko ./*.ipk > SHA256SUMS
  fi
)
cat > "$output_dir/BUILD-METADATA.txt" <<EOF
source=https://github.com/avwarez/vmg8825_b50b.git
source_commit=af23960e39003ba7788f5ced0c256b1bc676a712
inputs_release=damson-build-inputs-v1
inputs_manifest=build/vbntj/inputs.tsv
target=VBNTJ_502L07p1
firmware=Damson 19.4.0866-3401052
kernel=4.1.52
compiler=OpenWrt GCC $compiler_version
module_set=$module_set
spu_inplace_lab=$build_spu_inplace_lab
abi_patch=patches/vbntj-4.1.52/001-damson-network-abi.patch
kernel_config=build/vbntj/kernel-4.1.52-damson.config
spu_patches=patches/vbntj-spu/*.patch (spu-probe only)
kernel_compiler_seed_manifest=build/vbntj/kernel-toolchain-seed.sha256 (SPU workflow fallback)
EOF

if [[ "$build_spu_lab" -eq 1 ]]; then
  cp "$repo_root/experiments/spu-sha256/README.md" "$output_dir/LAB-README.md"
  echo "Built experimental raw modules only (no IPKs) in $output_dir"
else
  echo "Built validated Damson modules and manual-only IPKs in $output_dir"
fi
