#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_dir="${SOURCE_DIR:-$repo_root/.cache/sources}"
work_dir="${WORK_DIR:-$repo_root/.work/openwrt}"
output_dir="${OUTPUT_DIR:-$repo_root/dist}"
download_dir="${DOWNLOAD_DIR:-$repo_root/.cache/downloads}"
jobs="${JOBS:-$(getconf _NPROCESSORS_ONLN)}"
package_targets="${PACKAGE_TARGETS:-}"
build_config="${BUILD_CONFIG:-$repo_root/build/openwrt.config}"

buildroot_archive="$source_dir/openwrt_18.x_tch_buildroot_based_custom.tar.xz"
toolchain_archive="$source_dir/toolchain-arm_cortex-a9+neon_gcc-4.8-linaro_glibc_eabi.tar"

for archive in "$buildroot_archive" "$toolchain_archive"; do
  if [[ ! -f "$archive" ]]; then
    echo "Missing build input: $archive" >&2
    exit 1
  fi
done

if [[ ! -f "$build_config" ]]; then
  echo "Build configuration does not exist: $build_config" >&2
  exit 1
fi

(
  cd "$source_dir"
  sha256sum --check "$repo_root/build/checksums.sha256"
)

case "$work_dir" in
  /|""|"$repo_root")
    echo "Refusing unsafe WORK_DIR: $work_dir" >&2
    exit 1
    ;;
esac

rm -rf "$work_dir" "$output_dir"
mkdir -p "$work_dir" "$output_dir"

# The snapshot intentionally has no build/staging products. J is an accidental
# nested tar file and is not used by the OpenWrt build system.
tar --extract --xz --file "$buildroot_archive" \
  --directory "$work_dir" --no-same-owner \
  --exclude J --exclude bin --exclude build_dir --exclude logs --exclude staging_dir

mkdir -p "$download_dir"
kernel_archive="$download_dir/linux-4.1.38.tar.xz"
kernel_sha256="b8c23117cb08cb0bfc9660375130caaee2fabb39bc5d680557d4521e7e08bd56"
if [[ ! -f "$kernel_archive" ]]; then
  kernel_archive_tmp="$download_dir/.linux-4.1.38.tar.xz.tmp"
  curl --fail --location --retry 3 \
    --output "$kernel_archive_tmp" \
    https://cdn.kernel.org/pub/linux/kernel/v4.x/linux-4.1.38.tar.xz
  mv "$kernel_archive_tmp" "$kernel_archive"
fi
echo "$kernel_sha256  $kernel_archive" | sha256sum --check --status || {
  echo "Invalid Linux 4.1.38 source archive: $kernel_archive" >&2
  exit 1
}
rm -rf "$work_dir/dl"
ln -s "$download_dir" "$work_dir/dl"

mkdir -p "$work_dir/staging_dir"
tar --extract --file "$toolchain_archive" \
  --directory "$work_dir/staging_dir" --no-same-owner

# Add repository-maintained kernel fixes after the archived vendor patch set.
# VBNTS shares the VANTW 4.1 patch directory in this buildroot snapshot.
kernel_patch_source="$repo_root/patches/kernel-4.1"
kernel_patch_target="$work_dir/target/linux/brcm63xx-tch/VANTW/patches-4.1"
if [[ -d "$kernel_patch_source" ]]; then
  if [[ ! -d "$kernel_patch_target" ]]; then
    echo "Expected kernel patch directory was not found: $kernel_patch_target" >&2
    exit 1
  fi
  cp "$kernel_patch_source"/*.patch "$kernel_patch_target/"
fi

# The archived buildroot contains generated absolute symlinks in the board
# patch directory that only worked on the original maintainer's machine.
# Point it back to the complete in-archive patch set shared by VANTW/VBNTS.
active_kernel_patches="$work_dir/target/linux/brcm63xx-tch/patches-4.1"
autodetected_patch="$active_kernel_patches/900-410-autodetected-bcmdrivers-kconfig.patch"
if [[ -f "$autodetected_patch" ]]; then
  cp "$autodetected_patch" "$kernel_patch_target/"
fi
rm -rf "$active_kernel_patches"
ln -s VANTW/patches-4.1 "$active_kernel_patches"

cp "$build_config" "$work_dir/.config"

make_args=(--directory "$work_dir" --jobs "$jobs" V=sc)
make "${make_args[@]}" defconfig

if [[ -n "$package_targets" ]]; then
  # Intended for smoke tests and targeted rebuilds. Targets are recipe paths,
  # for example: zlib or feeds/packages/curl.
  # Unlike `world`, a direct package target does not build all host utilities.
  # Use the compatible tools supplied by the container for a fast smoke build.
  mkdir -p "$work_dir/staging_dir/host/bin"
  ln -sf "$(command -v cmake)" "$work_dir/staging_dir/host/bin/cmake"
  ln -sf "$(command -v flock)" "$work_dir/staging_dir/host/bin/flock"
  ln -sf "$(command -v patchelf)" "$work_dir/staging_dir/host/bin/patchelf"
  if [[ " $package_targets " == *" kernel/linux "* ]]; then
    # Kernel module packages require the configured kernel tree, generated
    # headers, Module.symvers and modules.builtin before packaging can start.
    make "${make_args[@]}" target/linux/compile
  fi
  for target in $package_targets; do
    make "${make_args[@]}" "package/$target/compile"
  done
  make --directory "$work_dir" package/index
else
  # `world` builds host tools, target/kernel prerequisites, every selected
  # package, package indexes and checksums in dependency order.
  make "${make_args[@]}" world
fi

packages_root="$work_dir/bin/brcm63xx-tch/VBNTS/packages/arm_cortex-a9_neon"
targets_root="$work_dir/bin/brcm63xx-tch/VBNTS/targets"

if [[ ! -d "$packages_root" ]]; then
  echo "Expected package output was not created: $packages_root" >&2
  exit 1
fi

cp -a "$packages_root/." "$output_dir/"
target_packages="$(find "$targets_root" -type d -name packages -print -quit 2>/dev/null || true)"
if [[ -n "$target_packages" ]]; then
  mkdir -p "$output_dir/target/packages"
  find "$target_packages" -maxdepth 1 -type f \
    \( -name '*.ipk' -o -name 'Packages*' \) \
    -exec cp -a {} "$output_dir/target/packages/" \;
fi

if [[ "${VERIFY_KMOD_TUN:-0}" == 1 ]]; then
  "$repo_root/scripts/verify-kmod-tun.sh" "$output_dir" "$work_dir"
fi

ipk_count="$(find "$output_dir" -type f -name '*.ipk' | wc -l | tr -d ' ')"
if [[ "$ipk_count" -eq 0 ]]; then
  echo "The build completed without producing any .ipk files" >&2
  exit 1
fi

echo "Built $ipk_count packages in $output_dir"
