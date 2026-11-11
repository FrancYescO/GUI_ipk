#!/bin/sh
# The caller supplies a fixture directory; every opkg operation is offline-root.
set -eu
ulimit -c 0
fixtures=$1
base=$1/$2
profile=$2
opkg_bin=${OPKG_BIN:-opkg}
. "$base/case.env"
run() { mode=$1; shift; "$opkg_bin" --offline-root "$base/$mode" -f "$base/$mode.conf" "$@"; }
if [ -n "$QOS_PACKAGE" ]; then
    find "$base/qos/lib/modules" -type f -exec sha256sum {} \; | sort > "$base/stock-before.sha256"
    cp "$base/qos/usr/lib/opkg/status" "$base/stock-before.status"
    run qos update
    run qos install "$QOS_PACKAGE"
    sha256sum -c "$base/stock-before.sha256"
    # Preserve installed firmware versions/states/dependencies across OPKG's rewrite.
    python3 - "$base/stock-before.status" "$base/qos/usr/lib/opkg/status" <<'PY'
import sys
from pathlib import Path
def records(path):
    result = {}
    for block in Path(path).read_text().strip().split('\n\n'):
        fields = dict(line.split(': ', 1) for line in block.splitlines() if ': ' in line)
        if fields:
            result[fields['Package']] = tuple(''.join(fields.get(k, '').split())
                                            for k in ('Version', 'Status', 'Depends'))
    return result
before, after = map(records, sys.argv[1:])
assert all(after.get(name) == value for name, value in before.items())
PY
    echo 'PASS QoS installation preserves stock module files and package records'
fi
if [ -n "$CDC_PACKAGE" ]; then
    # Explicit one-file migrations in inert offline roots; stock USBnet is retained.
    before=$(sha256sum "$base/usb/lib/modules/${profile%%-*}/usbnet.ko" | cut -d' ' -f1)
    run usb update
    OPKG_BIN="$opkg_bin" sh "$fixtures/migrate.sh" --apply --offline-root "$base/usb" --config "$base/usb.conf" --ipk "$base/repo/$CDC_FILENAME" "$CDC_PACKAGE"
    OPKG_BIN="$opkg_bin" sh "$fixtures/migrate.sh" --apply --offline-root "$base/usb" --config "$base/usb.conf" --ipk "$base/repo/$RNDIS_FILENAME" "$RNDIS_PACKAGE"
    test "$(sha256sum "$base/usb/lib/modules/${profile%%-*}/usbnet.ko" | cut -d' ' -f1)" = "$before"
    run usb search "$base/usb/lib/modules/${profile%%-*}/cdc_ether.ko" | grep -F "$CDC_PACKAGE"
    run usb search "$base/usb/lib/modules/${profile%%-*}/rndis_host.ko" | grep -F "$RNDIS_PACKAGE"
    echo 'PASS standard-path CDC/RNDIS migration preserves stock USBnet'
fi
for mode in clean legacy group wrong; do run "$mode" update; done
if [ -z "$TUN_PACKAGE" ]; then
 if run clean install fixture-vpn; then echo 'FAIL staging-only module satisfied TUN'; exit 1; fi
 echo "PASS staging-only candidates do not provide TUN: $profile"
 exit 0
fi
run clean install fixture-vpn
run clean status fixture-vpn | grep '^Status:.* installed'
run clean status "$TUN_PACKAGE" | grep '^Status:.* installed'
if [ "$MODULAR" = yes ]; then
 test "$(sha256sum "$base/clean/lib/modules/${profile%%-*}/tun.ko" | cut -d' ' -f1)" = "$MODULE_SHA256"
 run legacy install "$base/legacy-tun.ipk" "$base/unrelated.ipk"
 run legacy install fixture-vpn
 # Deliberate fixture-only file takeover, restricted to the validated module IPK.
 # No force-depends and no kernel loading occurs.
 package_file=$(awk -v p="$TUN_PACKAGE" 'BEGIN {RS="";FS="\n"} $0 ~ "Package: " p "\n" {for(i=1;i<=NF;i++) if($i ~ /^Filename: /) print substr($i,11)}' "$base/repo/Packages")
 before=$(sha256sum "$base/legacy/usr/lib/opkg/status" | cut -d' ' -f1)
 mkdir -p "$base/legacy/sys/module/tun"
 if OPKG_BIN="$opkg_bin" sh "$fixtures/migrate.sh" --apply --offline-root "$base/legacy" --config "$base/legacy.conf" --ipk "$base/repo/$package_file" "$TUN_PACKAGE"; then
  echo 'FAIL migration accepted active module'; exit 1
 fi
 test "$(sha256sum "$base/legacy/usr/lib/opkg/status" | cut -d' ' -f1)" = "$before"
 rmdir "$base/legacy/sys/module/tun"
 OPKG_BIN="$opkg_bin" sh "$fixtures/migrate.sh" --apply --offline-root "$base/legacy" --config "$base/legacy.conf" --ipk "$base/repo/$package_file" "$TUN_PACKAGE"
 if [ "$CANONICAL_TUN" = yes ]; then
  run legacy install kmod-tun
  run legacy status kmod-tun | grep -F "kernel (= $KERNEL)"
 fi
 test "$(cat "$base/legacy/usr/share/fixture-unrelated")" = KEEP-ME
 run legacy status fixture-vpn | grep '^Status:.* installed'
 cmp "$base/clean/lib/modules/${profile%%-*}/tun.ko" "$base/legacy/lib/modules/${profile%%-*}/tun.ko"
 run legacy search "$base/legacy/lib/modules/${profile%%-*}/tun.ko" | grep -F "$TUN_PACKAGE"
 echo 'PASS generic migration preserves module bytes, ownership and consumer'
else
 test ! -f "$base/clean/lib/modules/${profile%%-*}/tun.ko"
 echo 'PASS builtin TUN capability installs no module'
fi
if [ -n "$GROUP_PACKAGE" ]; then
 run group install "$base/legacy-group.ipk"
 run group install fixture-group
 for package in $COMPONENTS; do run group --force-overwrite install "$package"; done
 run group install "$GROUP_PACKAGE"
 run group status fixture-group | grep '^Status:.* installed'
 run group status "$GROUP_PACKAGE" | grep '^Status:.* installed'
 for item in $COMPONENT_CHECKS; do
  path=${item%:*}; expected=${item##*:}
  test "$(sha256sum "$base/group/$path" | cut -d' ' -f1)" = "$expected"
 done
 echo 'PASS complete multi-module group migration'
fi
if run wrong install fixture-vpn; then echo 'FAIL wrong ABI accepted'; exit 1; fi
echo 'PASS wrong kernel ABI rejected'
echo "ALL_CASES_PASSED=$profile"
