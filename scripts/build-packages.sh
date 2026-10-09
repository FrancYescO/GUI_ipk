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
userspace_only="${USERSPACE_ONLY:-0}"

buildroot_archive="$source_dir/openwrt_18.x_tch_buildroot_based_custom.tar.xz"
toolchain_archive="$source_dir/toolchain-arm_cortex-a9+neon_gcc-4.8-linaro_glibc_eabi.tar"

for archive in "$buildroot_archive" "$toolchain_archive"; do
  if [[ ! -f "$archive" ]]; then
    echo "Missing build input: $archive" >&2
    exit 1
  fi
done

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

# libpcap 1.9.1 uses the C99 `restrict` keyword in portability.h, while this
# archived recipe otherwise compiles it in the toolchain's default GNU89 mode.
patch --directory "$work_dir" --strip 1 \
  < "$repo_root/patches/libpcap-c99.patch"

# CONFIG_ALL in this snapshot selects kmod-* too. The userspace profile keeps
# every userspace recipe while leaving bulk kernel modules unselected.
if [[ "$userspace_only" == 1 ]]; then
  # In this fork CONFIG_ALL and CONFIG_ALL_NONSHARED both select ALL_KMODS.
  # Remove those selects so the userspace profile can keep ALL_KMODS disabled.
  patch --directory "$work_dir" --strip 1 \
    < "$repo_root/patches/userspace-no-all-kmods.patch"
  patch --directory "$work_dir" --strip 1 \
    < "$repo_root/patches/userspace-package-metadata.patch"
  # The archive contains a generated package Kconfig that predates the patch.
  rm -f "$work_dir/tmp/.config-package.in"
fi

# The historical archive was created with every directory named "bin"
# stripped recursively, including source payloads that are required by
# base-files, qos-scripts and the OpenWrt host tools. Restore the audited
# files kept in this repository before the build can use the snapshot.
cp -a "$repo_root/build/source-overlay/." "$work_dir/"

# The package and LuCI feeds retain their pinned Git object databases. Restore
# the other stripped source payloads directly from those exact commits rather
# than downloading moving branch heads.
git -C "$work_dir/feeds/packages" checkout HEAD -- \
  net/wifischedule/net/usr/bin \
  utils/bmx7-dnsupdate/files/usr/bin \
  utils/prometheus-node-exporter-lua/files/usr/bin \
  utils/yunbridge/files/usr/bin
git -C "$work_dir/feeds/luci" checkout HEAD -- \
  applications/luci-app-statistics/root/usr/bin \
  contrib/package/freifunk-common/files/usr/bin \
  contrib/package/meshwizard/files/usr/bin \
  libs/luci-lib-nixio/axTLS/www/bin \
  libs/luci-lib-nixio/axTLS/www/test_dir/bin

# OpenWrt's old kernel recipe has no usable checksum metadata for this
# version, so download the exact upstream archive ourselves and verify the
# pinned SHA-256 before exposing it through the buildroot's dl directory.
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

# The snapshot's active board patch directory contains absolute symlinks from
# the original maintainer machine. VBNTS and VANTW share the complete in-tree
# 4.1 patch stack, so preserve the generated local patch and repoint the board
# directory at that portable copy.
kernel_patch_target="$work_dir/target/linux/brcm63xx-tch/VANTW/patches-4.1"
if [[ ! -d "$kernel_patch_target" ]]; then
  echo "Expected vendor kernel patch directory was not found: $kernel_patch_target" >&2
  exit 1
fi
active_kernel_patches="$work_dir/target/linux/brcm63xx-tch/patches-4.1"
autodetected_patch="$active_kernel_patches/900-410-autodetected-bcmdrivers-kconfig.patch"
if [[ -f "$autodetected_patch" ]]; then
  cp "$autodetected_patch" "$kernel_patch_target/"
fi
if [[ "${BUILD_KMODS:-0}" == 1 ]]; then
  cp "$repo_root"/patches/kernel-4.1.38/*.patch "$kernel_patch_target/"
fi
rm -rf "$active_kernel_patches"
ln -s VANTW/patches-4.1 "$active_kernel_patches"

cp "$build_config" "$work_dir/.config"

make_args=(--directory "$work_dir" --jobs "$jobs" V=sc)
make "${make_args[@]}" defconfig
if [[ "$userspace_only" == 1 ]] && grep -qx 'CONFIG_ALL_KMODS=y' "$work_dir/.config"; then
  echo 'Userspace profile unexpectedly selected CONFIG_ALL_KMODS=y' >&2
  exit 1
fi

if [[ -n "$package_targets" ]]; then
  # Intended for smoke tests and targeted rebuilds. Targets are recipe paths,
  # for example: zlib or feeds/packages/curl.
  # Unlike `world`, a direct package target does not build all host utilities.
  # Use the compatible tools supplied by the container for a fast smoke build.
  mkdir -p "$work_dir/staging_dir/host/bin"
  ln -sf "$(command -v cmake)" "$work_dir/staging_dir/host/bin/cmake"
  ln -sf "$(command -v flock)" "$work_dir/staging_dir/host/bin/flock"
  ln -sf "$(command -v patchelf)" "$work_dir/staging_dir/host/bin/patchelf"
  if [[ "${BUILD_KMODS:-0}" == 1 ]]; then
    make "${make_args[@]}" target/linux/compile
  fi
  for target in $package_targets; do
    make "${make_args[@]}" "package/$target/compile"
  done
  make --directory "$work_dir" package/index
elif [[ "$userspace_only" == 1 ]]; then
  # `world` also compiles the vendor kernel, including modules unrelated to
  # this userspace feed. Some kmods are selected indirectly as dependencies;
  # override those selections for the package graph while retaining the
  # userspace packages that depend on modules already installed on the router.
  mapfile -t kmod_overrides < <(
    sed -n 's/^\(CONFIG_PACKAGE_kmod-[^=]*\)=[ym]$/\1=n/p' "$work_dir/.config"
  )
  make_args+=("${kmod_overrides[@]}")
  echo "Skipping ${#kmod_overrides[@]} kernel-module package selections"
  # The matching cross-toolchain is restored from the pinned input archive.
  # Rebuilding it would fetch an obsolete glibc-2.19-r25243 source URL.
  make "${make_args[@]}" tools/install
  if ! make "${make_args[@]}" package/compile; then
    error_file="$work_dir/logs/package/error.txt"
    if [[ -s "$error_file" ]]; then
      echo "Failed package recipes:" >&2
      cat "$error_file" >&2
      while IFS= read -r recipe; do
        log_dir="$work_dir/logs/$recipe"
        [[ -d "$log_dir" ]] || continue
        while IFS= read -r -d '' log_file; do
          echo "Last 80 lines of $log_file:" >&2
          tail -n 80 "$log_file" >&2
        done < <(find "$log_dir" -type f -name '*compile.txt' -print0)
      done < <(sed -n 's/.*ERROR: \(package\/[^ ]*\) failed to build.*/\1/p' "$error_file" | sort -u)
    fi
    echo "Retrying unfinished packages serially to expose the first error" >&2
    serial_log="$output_dir/serial-package-compile.log"
    if make --directory "$work_dir" --jobs 1 V=sc "${kmod_overrides[@]}" package/compile 2>&1 | tee "$serial_log"; then
      rm -f "$serial_log"
    else
      mapfile -t failure_lines < <(
        grep -E 'error:|fatal error:|undefined reference|No rule to make target|ERROR:|make(\[[0-9]+\])?: \*\*\*' "$serial_log" | tail -n 12 || true
      )
      if [[ ${#failure_lines[@]} -eq 0 ]]; then
        mapfile -t failure_lines < <(tail -n 8 "$serial_log")
      fi
      for line in "${failure_lines[@]}"; do
        printf '::error title=OpenWrt package compile::%s\n' "$line"
      done
      exit 1
    fi
  fi
  make --directory "$work_dir" package/index
else
  # Full builds still include the target kernel and firmware images.
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

ipk_count="$(find "$output_dir" -type f -name '*.ipk' | wc -l | tr -d ' ')"
if [[ "$ipk_count" -eq 0 ]]; then
  echo "The build completed without producing any .ipk files" >&2
  exit 1
fi

echo "Built $ipk_count packages in $output_dir"
if [[ "${VERIFY_KMOD_TUN:-0}" == 1 ]]; then
  "$repo_root/scripts/verify-kmod-tun.sh" "$output_dir" "$work_dir"
fi
if [[ "${VERIFY_KMOD_CONNMARK:-0}" == 1 ]]; then
  "$repo_root/scripts/verify-kmod-connmark.sh" "$output_dir"
fi
