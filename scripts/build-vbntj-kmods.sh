#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_dir="${SOURCE_DIR:-/app}"
output_dir="${OUTPUT_DIR:-/out}"
module_set="${MODULE_SET:-tun}"
canary_dir="$source_dir/.vbntj-abi-canary"

case "$module_set" in
  tun)
    module_targets=(drivers/net/tun.ko)
    ;;
  network-smoke)
    module_targets=(drivers/net/tun.ko drivers/net/usb/usbnet.ko drivers/net/usb/cdc_ether.ko)
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

kernel_archive="$source_dir/dl/linux-4.1.52.tar.xz"
kernel_archive_sha256="6ad9389e55e0ea57768eae173747058a4487fa3630e10a7999cfec9f945e559c"
mkdir -p "$source_dir/dl"
if [[ ! -f "$kernel_archive" ]]; then
  kernel_archive_tmp="$kernel_archive.tmp"
  wget --tries=3 --timeout=30 \
    --output-document="$kernel_archive_tmp" \
    https://cdn.kernel.org/pub/linux/kernel/v4.x/linux-4.1.52.tar.xz
  mv "$kernel_archive_tmp" "$kernel_archive"
fi
echo "$kernel_archive_sha256  $kernel_archive" | sha256sum --check --status || {
  echo "Invalid Linux 4.1.52 source archive: $kernel_archive" >&2
  exit 1
}

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

export PATH="$toolchain_dir/bin:$PATH"
export BCM_BUILD_DIR="$sdk_dir"
export KERNEL_BUILD_DIR="$kernel_base"
export LINUX_DIR="$kernel_dir"
export TOOLCHAIN_DIR="$toolchain_dir"
export TARGET_DIR="$source_dir/staging_dir/target-arm_v7-a_glibc-2.26_eabi"
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

"${kernel_make[@]}" "${module_targets[@]}"
rm -rf "$canary_dir"
cp -R "$repo_root/build/vbntj-canary" "$canary_dir"
"${kernel_make[@]}" M="$canary_dir" modules

rm -rf "$output_dir"
mkdir -p "$output_dir"
for target in "${module_targets[@]}"; do
  module_name="$(basename "$target")"
  cp "$kernel_dir/$target" "$output_dir/$module_name"
done
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

"$cross_nm" --undefined-only "$output_dir/tun.ko" \
  | awk '{print $NF}' | LC_ALL=C sort -u > "$output_dir/tun.undefined-symbols"
if ! cmp -s "$repo_root/build/vbntj/tun.undefined-symbols" "$output_dir/tun.undefined-symbols"; then
  echo "tun.ko undefined-symbol ABI differs from the router-validated baseline" >&2
  diff -u "$repo_root/build/vbntj/tun.undefined-symbols" "$output_dir/tun.undefined-symbols" || true
  exit 1
fi

(
  cd "$output_dir"
  sha256sum ./*.ko > SHA256SUMS
)
cat > "$output_dir/BUILD-METADATA.txt" <<EOF
source=https://github.com/avwarez/vmg8825_b50b.git
source_commit=af23960e39003ba7788f5ced0c256b1bc676a712
target=VBNTJ_502L07p1
firmware=Damson 19.4.0866-3401052
kernel=4.1.52
compiler=OpenWrt GCC $compiler_version
module_set=$module_set
abi_patch=patches/vbntj-4.1.52/001-damson-network-abi.patch
kernel_config=build/vbntj/kernel-4.1.52-damson.config
EOF

echo "Built validated VBNTJ modules in $output_dir"
