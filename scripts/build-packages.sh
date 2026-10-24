#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_dir="${SOURCE_DIR:-$repo_root/.cache/sources}"
work_dir="${WORK_DIR:-$repo_root/.work/openwrt}"
output_dir="${OUTPUT_DIR:-$repo_root/dist}"
download_dir="${DOWNLOAD_DIR:-$repo_root/.cache/downloads}"
jobs="${JOBS:-$(getconf _NPROCESSORS_ONLN)}"
package_targets="${PACKAGE_TARGETS:-}"
shard_index="${PACKAGE_SHARD_INDEX:-}"
shard_count="${PACKAGE_SHARD_COUNT:-16}"
build_config="${BUILD_CONFIG:-$repo_root/build/openwrt.config}"
userspace_only="${USERSPACE_ONLY:-0}"
package_compile_failed=0

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

# Several pinned feed recipes still use the retired GitHub git:// transport.
# Keep the rewrite in this disposable build directory.
export GIT_CONFIG_GLOBAL="$work_dir/.gitconfig"
git config --global url.https://github.com/.insteadOf git://github.com/

# The snapshot intentionally has no build/staging products. J is an accidental
# nested tar file and is not used by the OpenWrt build system.
tar --extract --xz --file "$buildroot_archive" \
  --directory "$work_dir" --no-same-owner \
  --exclude J --exclude bin --exclude build_dir --exclude logs --exclude staging_dir

# Crypto++ is absent from the archived feeds but required by aMule.
mkdir -p "$work_dir/package/custom/cryptopp"
cp "$repo_root/build/cryptopp/Makefile" \
  "$work_dir/package/custom/cryptopp/Makefile"
# Provide the dedicated SWIG generator used by the legacy Node bindings.
mkdir -p "$work_dir/package/custom/swig4"
cp "$repo_root/build/host-swig4/Makefile" \
  "$work_dir/package/custom/swig4/Makefile"
# libpcap 1.9.1 uses the C99 `restrict` keyword in portability.h, while this
# archived recipe otherwise compiles it in the toolchain's default GNU89 mode.
patch --directory "$work_dir" --strip 1 \
  < "$repo_root/patches/libpcap-c99.patch"
# The snapshot's shared-library patch omits configure's fallback LIBOBJS.
# Supply PIC copies so libpcap.so exports the same symbols as libpcap.a.
cp "$repo_root/patches/libpcap-shared-libobjs.patch" \
  "$work_dir/package/libs/libpcap/patches/101-shared-libobjs.patch"
cp "$repo_root/patches/coova-chilli-sysinfo.patch" \
  "$work_dir/feeds/packages/net/coova-chilli/patches/402-chilli-sysinfo.patch"
cp "$repo_root/patches/crtmpserver-libdl.patch" \
  "$work_dir/feeds/packages/multimedia/crtmpserver/patches/100-link-libdl.patch"
cp "$repo_root/patches/twisted-incremental-pin.patch" \
  "$work_dir/feeds/packages/lang/python/twisted/patches/003-pin-build-incremental.patch"
cp "$repo_root/patches/dante-scheduler-guard.patch" \
  "$work_dir/package/network/utils/dante/patches/250-scheduler-guard.patch"
mkdir -p "$work_dir/feeds/routing/pimbd/patches"
cp "$repo_root/patches/pimbd-router-alert-init.patch" \
  "$work_dir/feeds/routing/pimbd/patches/001-router-alert-init.patch"
cp "$repo_root/patches/freeradius3-strerror-feature-test.patch" \
  "$work_dir/feeds/packages/net/freeradius3/patches/999-strerror-feature-test.patch"
cp "$repo_root/patches/tvheadend-hdhomerun-build.patch" \
  "$work_dir/feeds/packages/multimedia/tvheadend/patches/030-hdhomerun-build.patch"
mkdir -p "$work_dir/feeds/packages/net/noddos/patches"
cp "$repo_root/patches/noddos-reference-init.patch" \
  "$work_dir/feeds/packages/net/noddos/patches/001-reference-init.patch"
cp "$repo_root/patches/noddos-shared-ptr-log.patch" \
  "$work_dir/feeds/packages/net/noddos/patches/002-shared-ptr-log.patch"
cp "$repo_root/patches/noddos-stdexcept.patch" \
  "$work_dir/feeds/packages/net/noddos/patches/003-stdexcept.patch"
cp "$repo_root/patches/postfix-target-platform.patch" \
  "$work_dir/feeds/packages/mail/postfix/patches/999-target-platform.patch"
mkdir -p "$work_dir/feeds/packages/devel/automake/patches"
cp "$repo_root/patches/automake-perl-regex.patch" \
  "$work_dir/feeds/packages/devel/automake/patches/001-perl-regex.patch"
mkdir -p "$work_dir/feeds/packages/net/ola/patches"
cp "$repo_root/patches/ola-widget-observer-templates.patch" \
  "$work_dir/feeds/packages/net/ola/patches/999-widget-observer-templates.patch"
cp "$repo_root/patches/libmraa-node-buffer-api.patch" \
  "$work_dir/feeds/packages/libs/libmraa/patches/999-node-buffer-api.patch"
mkdir -p "$work_dir/package/libs/wxwidgets/patches"
cp "$repo_root/patches/wxbase-optional-bakefile-presets.patch" \
  "$work_dir/package/libs/wxwidgets/patches/999-optional-bakefile-presets.patch"
mkdir -p "$work_dir/package/network/amule/patches"
cp "$repo_root/patches/amule-bootstrap.patch" \
  "$work_dir/package/network/amule/patches/999-bootstrap.patch"
patch --directory "$work_dir" --strip 1 \
  < "$repo_root/patches/amule-bootstrap-recipe.patch"
patch --directory "$work_dir" --strip 1 \
  < "$repo_root/patches/wxbase-sdk.patch"
mkdir -p "$work_dir/feeds/routing/cjdns/patches"
cp "$repo_root/patches/cjdns-build-flags.patch" \
  "$work_dir/feeds/routing/cjdns/patches/999-build-flags.patch"
cp "$repo_root/patches/cjdns-cnacl-build-flags.patch" \
  "$work_dir/feeds/routing/cjdns/patches/998-cnacl-build-flags.patch"
patch --directory "$work_dir" --strip 1 \
  < "$repo_root/patches/olsrd-release-flags.patch"
# BIND uses GNU typeof in ISC_ALIGN; strict C99 makes it an undeclared
# function with this historical GCC toolchain.
patch --directory "$work_dir" --strip 1 \
  < "$repo_root/patches/bind-gnu99.patch"
patch --directory "$work_dir" --strip 1 \
  < "$repo_root/patches/fftw3-soft-float-neon.patch"
patch --directory "$work_dir" --strip 1 \
  < "$repo_root/patches/nfs-gcc48-warning.patch"
patch --directory "$work_dir" --strip 1 \
  < "$repo_root/patches/archived-svn-sources.patch"
patch --directory "$work_dir" --strip 1 \
  < "$repo_root/patches/pthsem-sigaltstack.patch"
patch --directory "$work_dir" --strip 1 \
  < "$repo_root/patches/classpath-java8.patch"
patch --directory "$work_dir" --strip 1 \
  < "$repo_root/patches/libmraa-cxx11.patch"
patch --directory "$work_dir" --strip 1 \
  < "$repo_root/patches/libmraa-swig4-recipe.patch"
patch --directory "$work_dir" --strip 1 \
  < "$repo_root/patches/libupm-node8-recipe.patch"
cp "$repo_root/build/grilo-vapi/grilo-0.3.deps" \
  "$work_dir/feeds/packages/multimedia/grilo/files/grilo-0.3.deps"
# Match the archived host Vala compiler (0.34) when staging Grilo bindings.
patch --directory "$work_dir" --strip 1 \
  < "$repo_root/patches/grilo-vala-sdk.patch"
patch --directory "$work_dir" --strip 1 \
  < "$repo_root/patches/freeswitch-source-mirror.patch"
patch --directory "$work_dir" --strip 1 \
  < "$repo_root/patches/freeswitch-swig-patch-context.patch"
patch --directory "$work_dir" --strip 1 \
  < "$repo_root/patches/freeswitch-python2-recipe.patch"
cp "$repo_root/patches/freeswitch-target-perl-flags.patch" \
  "$work_dir/feeds/telephony/net/freeswitch/patches/glibc/zz-target-perl-flags.patch"
cp "$repo_root/patches/freeswitch-target-python.patch" \
  "$work_dir/feeds/telephony/net/freeswitch/patches/glibc/zz-target-python.patch"

# Retrieve the identical pinned board data from the official source mirror.
patch --directory "$work_dir" --strip 1 \
  < "$repo_root/patches/ath10k-board-source-mirror.patch"

# CONFIG_ALL in this snapshot selects kmod-* too. The userspace profile keeps
# every userspace recipe while leaving bulk kernel modules unselected.
if [[ "$userspace_only" == 1 ]]; then
  # In this fork CONFIG_ALL and CONFIG_ALL_NONSHARED both select ALL_KMODS.
  # Remove those selects so the userspace profile can keep ALL_KMODS disabled.
  patch --directory "$work_dir" --strip 1 \
    < "$repo_root/patches/userspace-no-all-kmods.patch"
  patch --directory "$work_dir" --strip 1 \
    < "$repo_root/patches/userspace-package-metadata.patch"
  patch --directory "$work_dir" --strip 1 \
    < "$repo_root/patches/userspace-skip-kernel-package.patch"
  patch --directory "$work_dir" --strip 1 \
    < "$repo_root/patches/userspace-ipset-no-kmod.patch"
  patch --directory "$work_dir" --strip 1 \
    < "$repo_root/patches/userspace-legacy-recipes.patch"
  patch --directory "$work_dir" --strip 1 \
    < "$repo_root/patches/userspace-mixed-recipes.patch"
  patch --directory "$work_dir" --strip 1 \
    < "$repo_root/patches/swconfig-vendor-uapi.patch"
  patch --directory "$work_dir" --strip 1 \
    < "$repo_root/patches/userspace-dependency-repairs.patch"
  # Import selected source updates while keeping the legacy build framework.
  patch --directory "$work_dir" --strip 1 \
    < "$repo_root/patches/userspace-package-updates.patch"
  patch --directory "$work_dir" --strip 1 \
    < "$repo_root/patches/userspace-kernel-configure.patch"
  # The archive contains a generated package Kconfig that predates the patch.
  rm -f "$work_dir/tmp/.config-package.in"
fi

# The historical archive was created with every directory named "bin"
# stripped recursively, including source payloads that are required by
# base-files, qos-scripts and the OpenWrt host tools. Restore the audited
# files kept in this repository before the build can use the snapshot.
cp -a "$repo_root/build/source-overlay/." "$work_dir/"

# Replace the archived combined WireGuard recipe with independent wg tools
# and the legacy module backport. Keep kernel compilation in kernel jobs.
rm -rf "$work_dir/package/network/services/wireguard"
cp -a "$repo_root/build/wireguard-overlay/." "$work_dir/"
if [[ "${BUILD_SPU:-0}" == 1 ]]; then
  cat "$repo_root/build/spu-module.mk" >> "$work_dir/target/linux/brcm63xx-tch/modules.mk"
  spu_source="$work_dir/extern/bcmopen-iopsys-DG400/bcmdrivers/opensource/char/spudd/impl3"
  test -f "$spu_source/spu.c"
  for spu_patch in \
    "$repo_root/patches/vbntj-spu/001-authsize-software-fallback.patch" \
    "$repo_root/patches/vbnts-spu/002-opt-in-esp-flow-offload.patch" \
    "$repo_root/patches/vbntj-spu/003-idempotent-ipsec-object-destroy.patch"; do
    patch --batch --forward -d "$spu_source" -p1 < "$spu_patch"
  done
fi
rm -f "$work_dir/tmp/.config-package.in" "$work_dir/tmp/.packagedeps"

if [[ "$userspace_only" == 1 ]]; then
  # Import complete pinned network recipes, including provider data and patches.
  rm -rf "$work_dir/package/network/utils/iperf3" \
    "$work_dir/package/network/utils/tcpdump" \
    "$work_dir/feeds/packages/net/ddns-scripts"
  cp -a "$repo_root/build/network-updates-overlay/." "$work_dir/"
  rm -f "$work_dir/tmp/.config-package.in" "$work_dir/tmp/.packagedeps"
fi

# Build the additional Homeware userspace recipes from pinned source overlays.
# Keep upstream payloads immutable and register the new recipes before defconfig.
if [[ "$userspace_only" == 1 ]]; then
  (cd "$repo_root/build/homeware-overlay" && sha256sum --check SHA256SUMS)
  cp -a "$repo_root/build/homeware-overlay/feeds/." "$work_dir/feeds/"
  # Build OpenMP separately: the supplied cross-toolchain has no libgomp.
  patch --directory "$work_dir" --strip 1 \
    < "$repo_root/patches/userspace-libgomp-runtime.patch"
  cp -a "$repo_root/build/libgomp-overlay/." "$work_dir/"
  # Large optional packages are built only by explicit targeted jobs, never
  # selected by the shared Pages profile's CONFIG_ALL.
  if [[ "$package_targets" == *feeds/packages/rclone* ]]; then
    (cd "$repo_root/build/rclone-overlay" && sha256sum --check SHA256SUMS)
    cp -a "$repo_root/build/rclone-overlay/feeds/." "$work_dir/feeds/"
    mkdir -p "$work_dir/package/feeds/packages"
    for package in rclone rclone-ng rclone-webui-react; do
      ln -sfn "../../../feeds/packages/net/$package" "$work_dir/package/feeds/packages/$package"
    done
  fi
  (cd "$repo_root/build/luci-translations-overlay" && sha256sum --check SHA256SUMS)
  cp -a "$repo_root/build/luci-translations-overlay/feeds/." "$work_dir/feeds/"
  patch --directory "$work_dir" --strip 1 \
    < "$repo_root/patches/luci-additional-languages.patch"
  # New po directories change the package list without changing recipe Makefiles.
  # The archived scanner does not track luci.mk or translation directory globs.
  rm -f "$work_dir/tmp/.packageinfo" "$work_dir/tmp/.config-package.in" \
    "$work_dir/tmp/.packagedeps" "$work_dir/tmp/info"/.packageinfo-*luci*
  # Translation templates are source files, not language directories.
  patch --directory "$work_dir" --strip 1 \
    < "$repo_root/patches/homeware-luci-translation-directories.patch"
  patch --directory "$work_dir" --strip 1 \
    < "$repo_root/patches/https-dns-proxy-gnu99.patch"
  mkdir -p "$work_dir/package/feeds/packages" "$work_dir/package/feeds/luci"
  for package in banip https-dns-proxy; do
    ln -sfn "../../../feeds/packages/net/$package" "$work_dir/package/feeds/packages/$package"
  done
  ln -sfn ../../../feeds/luci/applications/luci-app-https-dns-proxy \
    "$work_dir/package/feeds/luci/luci-app-https-dns-proxy"
  ln -sfn ../../../feeds/luci/modules/luci-compat "$work_dir/package/feeds/luci/luci-compat"
  rm -f "$work_dir/tmp/.config-package.in" "$work_dir/tmp/.packagedeps"
fi

if [[ "${ENABLE_ASTERISK20:-0}" == 1 ]]; then
  # Keep the new PJSIP ABI scoped to the experimental SIP profile.
  rm -rf "$work_dir/feeds/telephony/libs/pjproject"
  rm -rf "$work_dir/feeds/packages/libs/jansson"
  cp -a "$repo_root/build/asterisk20-overlay/." "$work_dir/"
  mkdir -p "$work_dir/package/feeds/telephony"
  ln -sfn ../../../feeds/telephony/net/asterisk \
    "$work_dir/package/feeds/telephony/asterisk"
  rm -f "$work_dir/tmp/.config-package.in" "$work_dir/tmp/.packagedeps"
fi

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
if [[ "$userspace_only" == 1 ]]; then
  python3 - "$repo_root/build/luci-translations-overlay/SOURCES.json" "$work_dir" <<'PY'
import json
import sys
from pathlib import Path

manifest, work = Path(sys.argv[1]), Path(sys.argv[2])
expected = set()
for entry in json.loads(manifest.read_text(encoding='utf-8')):
    path = Path(entry['destination'])
    module = path.parts[-4]
    module = module[len('luci-app-'):] if module.startswith('luci-app-') else module[len('luci-'):]
    expected.add('luci-i18n-{}-{}'.format(module, path.parts[-2]))
metadata = {line[len('Package: '):] for line in (work / 'tmp/.packageinfo').read_text(encoding='utf-8').splitlines()
            if line.startswith('Package: ')}
missing = expected - metadata
if missing:
    raise SystemExit('LuCI translations absent from metadata: ' + ', '.join(sorted(missing)))
config = set((work / '.config').read_text(encoding='utf-8').splitlines())
if 'CONFIG_ALL=y' in config:
    unselected = {name for name in expected
                  if not any('CONFIG_PACKAGE_{}={}'.format(name, flag) in config for flag in ('y', 'm'))}
    if unselected:
        raise SystemExit('LuCI translations not selected: ' + ', '.join(sorted(unselected)))
print('Verified {} additional LuCI translation package declarations'.format(len(expected)))
PY
fi
if [[ "$userspace_only" == 1 ]] && grep -qx 'CONFIG_ALL_KMODS=y' "$work_dir/.config"; then
  echo 'Userspace profile unexpectedly selected CONFIG_ALL_KMODS=y' >&2
  exit 1
fi

configure_kmod_overrides() {
  # Keep non-kernel packages selected while avoiding an unrelated kernel build.
  mapfile -t kmod_overrides < <(
    sed -n 's/^\(CONFIG_PACKAGE_kmod-[^=]*\)=[ym]$/\1=/p' "$work_dir/.config"
  )
  make_args+=("${kmod_overrides[@]}")
  echo "Skipping ${#kmod_overrides[@]} kernel-module package selections"
}

prepare_kernel_modules() {
  # The top-level OpenWrt dispatcher does not expose custom target/linux
  # targets. Its normal recursive invocation also adds host tools and the
  # cross-compiler to PATH; preserve that environment for this direct call.
  local toolchain_bin="$work_dir/staging_dir/toolchain-arm_cortex-a9+neon_gcc-4.8-linaro_glibc_eabi/bin"
  PATH="$work_dir/staging_dir/host/bin:$toolchain_bin:$PATH" \
    make --directory "$work_dir/target/linux" --jobs "$jobs" V=sc \
    TOPDIR="$work_dir" modules_prepare
}

compile_with_report() {
  local error_file="$work_dir/logs/package/error.txt"
  local serial_log="$output_dir/serial-package-compile.log"
  if ! make --keep-going "${make_args[@]}" "$@"; then
    if [[ -s "$error_file" ]]; then
      echo "Failed package recipes in the parallel pass:" >&2
      cat "$error_file" >&2
    fi
    echo "Retrying unfinished packages serially and continuing past failures" >&2
    rm -f "$error_file"
    if make --directory "$work_dir" --keep-going --jobs 1 V=sc \
      "${kmod_overrides[@]}" "$@" 2>&1 | tee "$serial_log"; then
      rm -f "$serial_log"
    else
      python3 "$repo_root/scripts/report-package-failures.py" \
        "$serial_log" "$error_file" "$output_dir"
      mapfile -t failed_recipes < "$output_dir/failed-packages.txt"
      for recipe in "${failed_recipes[@]}"; do
        printf '::error title=OpenWrt package compile::%s failed\n' "$recipe"
      done
      package_compile_failed=1
    fi
  fi
}

install_host_tools() {
  local tools_log="$output_dir/host-tools-install.log"
  if make "${make_args[@]}" tools/install 2>&1 | tee "$tools_log"; then
    rm -f "$tools_log"
    return 0
  fi
  echo "Retrying host tools serially after the parallel preparation failed" >&2
  if make --directory "$work_dir" --jobs 1 V=sc tools/install 2>&1 | tee -a "$tools_log"; then
    return 0
  fi
  {
    echo '# Userspace build preparation failed'
    echo
    echo 'Host tools failed in both parallel and serial builds. No package recipes were attempted.'
    echo 'See host-tools-install.log for the complete output.'
    echo
    echo '```text'
    tail -n 40 "$tools_log"
    echo '```'
  } > "$output_dir/failed-packages.md"
  return 1
}

# Fail before rebuilding host tools if a targeted recipe path is misspelled.
if [[ -n "$package_targets" ]]; then
  for target in $package_targets; do
    target="${target#package/}"
    target="${target%/compile}"
    if [[ ! -f "$work_dir/package/$target/Makefile" ]]; then
      echo "Unknown package target: package/$target (expected a recipe under package/)" >&2
      exit 1
    fi
  done
fi

if [[ -n "$package_targets" ]]; then
  if [[ "$userspace_only" == 1 ]]; then
    # Direct userspace targets still need pinned host tools and kernel headers.
    configure_kmod_overrides
    install_host_tools
    make "${make_args[@]}" target/linux/prepare
    make "${make_args[@]}" target/linux/configure
    prepare_kernel_modules
    target_list=()
    for target in $package_targets; do
      target="${target#package/}"
      target="${target%/compile}"
      target_list+=("package/$target/compile")
    done
    compile_with_report "${target_list[@]}"
  else
    # Preserve the lightweight targeted kernel-module build path.
    mkdir -p "$work_dir/staging_dir/host/bin"
    ln -sf "$(command -v cmake)" "$work_dir/staging_dir/host/bin/cmake"
    ln -sf "$(command -v flock)" "$work_dir/staging_dir/host/bin/flock"
    ln -sf "$(command -v patchelf)" "$work_dir/staging_dir/host/bin/patchelf"
    if [[ "${BUILD_KMODS:-0}" == 1 ]]; then
      make "${make_args[@]}" target/linux/compile
    fi
    for target in $package_targets; do
      target="${target#package/}"
      target="${target%/compile}"
      make "${make_args[@]}" "package/$target/compile"
    done
  fi
  make --directory "$work_dir" package/index
elif [[ "$userspace_only" == 1 && -n "$shard_index" ]]; then
  python3 "$repo_root/scripts/select-userspace-shard.py" \
    "$work_dir/.config" "$work_dir/tmp/.packagedeps" \
    "$shard_index" "$shard_count" "$output_dir"
  mapfile -t shard_targets < "$output_dir/shard-targets.txt"
  configure_kmod_overrides
  install_host_tools
  make "${make_args[@]}" target/linux/prepare
  make "${make_args[@]}" target/linux/configure
  prepare_kernel_modules
  compile_with_report "${shard_targets[@]}"
elif [[ "$userspace_only" == 1 ]]; then
  # `world` also compiles the vendor kernel, including modules unrelated to
  # this userspace feed. Some kmods are selected indirectly as dependencies;
  # override those selections for the package graph while retaining the
  # userspace packages that depend on modules already installed on the router.
  configure_kmod_overrides
  # The matching cross-toolchain is restored from the pinned input archive.
  # Rebuilding it would fetch an obsolete glibc-2.19-r25243 source URL.
  install_host_tools
  make "${make_args[@]}" target/linux/prepare
  make "${make_args[@]}" target/linux/configure
  prepare_kernel_modules
  compile_with_report package/compile
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
if [[ "$userspace_only" == 1 ]]; then
  python3 "$repo_root/scripts/report-homeware-coverage.py" \
    "$repo_root/build/homeware/catalog.tsv" "$output_dir" \
    --metadata "$work_dir/tmp/.packageinfo" --config "$work_dir/.config"
fi

if [[ "$package_compile_failed" -ne 0 ]]; then
  echo "Some package recipes failed; successful IPKs and diagnostics were preserved in $output_dir" >&2
  exit 1
fi
if [[ "${VERIFY_KMOD_TUN:-0}" == 1 ]]; then
  "$repo_root/scripts/verify-kmod-tun.sh" "$output_dir" "$work_dir"
fi
if [[ "${VERIFY_KMOD_CONNMARK:-0}" == 1 ]]; then
  "$repo_root/scripts/verify-kmod-connmark.sh" "$output_dir"
fi
