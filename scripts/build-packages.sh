#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_dir="${SOURCE_DIR:-$repo_root/.cache/sources}"
work_dir="${WORK_DIR:-$repo_root/.work/openwrt}"
output_dir="${OUTPUT_DIR:-$repo_root/dist}"
jobs="${JOBS:-$(getconf _NPROCESSORS_ONLN)}"
package_targets="${PACKAGE_TARGETS:-}"

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

mkdir -p "$work_dir/staging_dir"
tar --extract --file "$toolchain_archive" \
  --directory "$work_dir/staging_dir" --no-same-owner

cp "$repo_root/build/openwrt.config" "$work_dir/.config"

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

ipk_count="$(find "$output_dir" -type f -name '*.ipk' | wc -l | tr -d ' ')"
if [[ "$ipk_count" -eq 0 ]]; then
  echo "The build completed without producing any .ipk files" >&2
  exit 1
fi

echo "Built $ipk_count packages in $output_dir"
