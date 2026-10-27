#!/usr/bin/env bash
# Compile only the replacement pair; usbnet is a build prerequisite, never exported.
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
kernel_dir="${1:?prepared kernel directory required}"
cross="${2:?cross compiler prefix required}"
output="${3:?output directory required}"
profile="${RUNTIME_PROFILE:?vbnto or vbnts required}"
case "$profile" in vbnto|vbnts) ;; *) exit 1 ;; esac
export PATH="$(dirname "$cross"):$PATH"
export STAGING_DIR="${STAGING_DIR:-$(dirname "$(dirname "$cross")")}"
work_dir="${WORK_DIR:-$(dirname "$(dirname "$(dirname "$(dirname "$cross")")")")}"
export BRCMDRIVERS_DIR="${BRCMDRIVERS_DIR:-$work_dir/extern/bcmopen-iopsys-DG400/bcmdrivers}"
export BCM_BUILD_DIR="${BCM_BUILD_DIR:-$work_dir/extern/bcmopen-iopsys-DG400}"
export LINUX_DIR="$kernel_dir" BRCM_CHIP=63138 BCM_KF=y
for headers in \
  "$BCM_BUILD_DIR/bcmdrivers/opensource/include/bcm963xx" \
  "$BCM_BUILD_DIR/bcmdrivers/broadcom/include/bcm963xx" \
  "$BCM_BUILD_DIR/shared/opensource/include/bcm963xx" \
  "$BCM_BUILD_DIR/shared/opensource/include" \
  "$BCM_BUILD_DIR/shared/opensource/include/rdp" \
  "$BCM_BUILD_DIR/shared/opensource/include/pmc" \
  "$BCM_BUILD_DIR/shared/broadcom/include/bcm963xx"; do
  export KCFLAGS="${KCFLAGS:-} -I$headers"
done
mkdir -p "$output"
bash "$repo_root/scripts/apply-usb-rndis-compat.sh" "$kernel_dir"
gzip -dc "$repo_root/build/$profile-4.1.38/kernel.config.gz" > "$kernel_dir/.config"
"$kernel_dir/scripts/config" --file "$kernel_dir/.config" \
  --module USB_USBNET --module USB_NET_CDCETHER --module USB_NET_RNDIS_HOST
kernel_make=(make -C "$kernel_dir" ARCH=arm CROSS_COMPILE="$cross")
"${kernel_make[@]}" olddefconfig modules_prepare
python3 - "$repo_root/build/$profile-4.1.38/kernel.config.gz" "$kernel_dir/.config" <<'PY'
import gzip, pathlib, sys
baseline = {line for line in gzip.decompress(pathlib.Path(sys.argv[1]).read_bytes()).decode().splitlines()
            if line.startswith('CONFIG_') and line.endswith(('=y', '=m'))}
actual = set(pathlib.Path(sys.argv[2]).read_text().splitlines())
missing = baseline - actual
if missing:
    raise SystemExit('Lost runtime options: ' + ', '.join(sorted(missing)))
PY
"${kernel_make[@]}" -j"${JOBS:-2}" drivers/net/usb/usbnet.ko
"${kernel_make[@]}" -j"${JOBS:-2}" drivers/net/usb/cdc_ether.ko drivers/net/usb/rndis_host.ko
for module in cdc_ether rndis_host; do
  cp "$kernel_dir/drivers/net/usb/$module.ko" "$output/$module.ko"
  "${cross}strip" --strip-debug "$output/$module.ko"
  "${cross}nm" --undefined-only "$output/$module.ko" | awk '{print $NF}' | LC_ALL=C sort -u > "$output/$module.undefined-symbols"
  "${cross}readelf" -p .modinfo "$output/$module.ko" > "$output/$module.modinfo"
  grep -q 'vermagic=4.1.38 SMP preempt mod_unload ARMv7' "$output/$module.modinfo"
  dependencies="$(sed -n 's/.*depends=//p' "$output/$module.modinfo" | tr ',' '\n' | LC_ALL=C sort | paste -sd, -)"
  expected=usbnet
  [[ "$module" != rndis_host ]] || expected=cdc_ether,usbnet
  [[ "$dependencies" == "$expected" ]] || { echo "Wrong $module dependencies: $dependencies" >&2; exit 1; }
done
grep -qi 'alias=.*icEFisc04ip01' "$output/rndis_host.modinfo"
cp "$kernel_dir/.config" "$output/kernel.config"
cp "$kernel_dir/drivers/net/usb/cdc_ether.c" "$output/cdc_ether.c"
cp "$kernel_dir/drivers/net/usb/rndis_host.c" "$output/rndis_host.c"
{
  echo "runtime_profile=$profile"
  echo "compiler=$(${cross}gcc --version | head -1)"
  echo 'native_usbnet=retained; compiled only to supply modpost dependencies'
  sha256sum "$repo_root/patches/usb-rndis/001-misc-class.patch" "$output/kernel.config"
} > "$output/BUILD-METADATA.txt"
(cd "$output" && sha256sum ./*.ko > SHA256SUMS)
