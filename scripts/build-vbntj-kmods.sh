#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_dir="${SOURCE_DIR:-/app}"
output_dir="${OUTPUT_DIR:-/out}"
module_set="${MODULE_SET:-tun}"
canary_dir="$source_dir/.vbntj-abi-canary"
build_connmark=0

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

sdk_archive_xz="$source_dir/dl/broadcom_sdk_502L07_pkg.tar.xz"
sdk_archive_xz_sha256="73b1888527dfb3792df82ff6f48c44a0423165e128f4d1ea9e7f07561618a9ac"
sdk_archive="$source_dir/dl/broadcom_sdk_502L07_pkg.tar.bz2"
sdk_archive_sha256="87b0bd62c8988e01aae24a1c37bfe19805217900ef0b5b44348c5f3fd4b2927f"
if [[ ! -f "$sdk_archive_xz" ]]; then
  sdk_archive_xz_tmp="$sdk_archive_xz.tmp"
  wget --tries=3 --timeout=30 \
    --output-document="$sdk_archive_xz_tmp" \
    https://raw.githubusercontent.com/threader/DX5401-B0-V517ABYO6C0_GPL/5df85c8c423ee935eed37b81f0d76dc569e2deb0/dl/broadcom_sdk_502L07_pkg.tar.xz
  mv "$sdk_archive_xz_tmp" "$sdk_archive_xz"
fi
echo "$sdk_archive_xz_sha256  $sdk_archive_xz" | sha256sum --check --status || {
  echo "Invalid Broadcom 502L07 GPL SDK source archive: $sdk_archive_xz" >&2
  exit 1
}
if [[ ! -f "$sdk_archive" ]]; then
  sdk_archive_tmp="$sdk_archive.tmp"
  xz --decompress --stdout "$sdk_archive_xz" | bzip2 -9 > "$sdk_archive_tmp"
  mv "$sdk_archive_tmp" "$sdk_archive"
fi
echo "$sdk_archive_sha256  $sdk_archive" | sha256sum --check --status || {
  echo "Invalid Broadcom 502L07 GPL SDK build archive: $sdk_archive" >&2
  exit 1
}

fetch_verified_source() {
  local filename="$1"
  local expected_sha256="$2"
  local url="$3"
  local destination="$source_dir/dl/$filename"

  if [[ ! -f "$destination" ]]; then
    wget --tries=3 --timeout=30 \
      --output-document="$destination.tmp" "$url"
    mv "$destination.tmp" "$destination"
  fi
  echo "$expected_sha256  $destination" | sha256sum --check --status || {
    echo "Invalid pinned toolchain source archive: $destination" >&2
    exit 1
  }
}

toolchain_source_base="https://raw.githubusercontent.com/threader/DX5401-B0-V517ABYO6C0_GPL/5df85c8c423ee935eed37b81f0d76dc569e2deb0/dl"
fetch_verified_source binutils-2.28.1.tar.bz2 \
  d06a446d5bad9828bf1f1ad35b312ccc45e272def70faac6f4517197053e5afb \
  "$toolchain_source_base/binutils-2.28.1.tar.bz2"
fetch_verified_source gcc-5.5.0.tar.bz2 \
  af91860cb80100aa7d21b5118c3b0800319d2c6d5676a321fb1b7a1d65b06b50 \
  "https://media.githubusercontent.com/media/threader/DX5401-B0-V517ABYO6C0_GPL/5df85c8c423ee935eed37b81f0d76dc569e2deb0/dl/gcc-5.5.0.tar.bz2"
fetch_verified_source glibc-2.26.tar.bz2 \
  5690dbde0a12973102289eb67c09173ab757657f26f405747b3d19c363956391 \
  "$toolchain_source_base/glibc-2.26.tar.bz2"
fetch_verified_source gmp-6.1.0.tar.xz \
  68dadacce515b0f8a54f510edf07c1b636492bcdb8e8d54c56eb216225d16989 \
  "$toolchain_source_base/gmp-6.1.0.tar.xz"
fetch_verified_source mpc-1.0.3.tar.gz \
  617decc6ea09889fb08ede330917a00b16809b8db88c29c31bfbb49cbf88ecc3 \
  "$toolchain_source_base/mpc-1.0.3.tar.gz"
fetch_verified_source mpfr-3.1.4.tar.bz2 \
  d3103a80cdad2407ed581f3618c4bed04e0c92d1cf771a65ead662cc397f7775 \
  "$toolchain_source_base/mpfr-3.1.4.tar.bz2"
fetch_verified_source xz-5.0.4.tar.bz2 \
  5cd9b060d3a1ad396b3be52c9b9311046a1c369e6062aea752658c435629ce92 \
  "$toolchain_source_base/xz-5.0.4.tar.bz2"

# The legacy OpenWrt rules address several already-installed host utilities
# through staging_dir/host/bin. Populate that prefix without rebuilding the
# same Ubuntu 12.04 tools from obsolete private mirrors.
host_bin="$source_dir/staging_dir/host/bin"
mkdir -p "$host_bin"
for host_tool in \
  aclocal autoconf autoheader autom4te automake autoreconf \
  find gettext libtool libtoolize m4 sed; do
  host_tool_path="$(command -v "$host_tool")"
  ln -sf "$host_tool_path" "$host_bin/$host_tool"
done

# The public GPL repository intentionally omits the prebuilt cross-toolchain.
# GCC's configure step expects its host-side arithmetic dependencies in the
# OpenWrt host staging prefix. Build them explicitly in dependency order;
# toolchain/install does not pull them in early enough in this legacy tree.
make -j1 V=s tools/gmp/install
make -j1 V=s tools/mpfr/install
make -j1 V=s tools/mpc/install

# Build the configured OpenWrt GCC 5.5.0 toolchain before the kernel prepare
# target tries to invoke it.
make -j1 V=s toolchain/install
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

"${kernel_make[@]}" "${module_targets[@]}"
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
for target in "${module_targets[@]}"; do
  build_manual_ipk "$output_dir/$(basename "$target")"
done
rm -rf "$output_dir/.ipk-build"

(
  cd "$output_dir"
  sha256sum ./*.ko ./*.ipk > SHA256SUMS
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

echo "Built validated Damson modules and manual-only IPKs in $output_dir"
