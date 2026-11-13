#!/bin/sh
# Standard-name installs, native upgrades and legacy ownership, isolated roots.
set -eu
base=$1/$2
opkg_bin=${OPKG_BIN:-opkg}
run() {
    case_name=$1
    shift
    "$opkg_bin" --offline-root "$base/$case_name" -f "$base/$case_name.conf" "$@"
}
for case_name in usb-clean usb-native; do
    run "$case_name" update
    run "$case_name" install kmod-usb-net-cdc-ether kmod-usb-net-rndis
    (cd "$base/$case_name" && sha256sum -c "$base/usb-checks")
    run "$case_name" status kmod-usb-net | grep -q 'Status:.* installed'
    test -s "$base/$case_name/lib/modules/${2%%-*}/usbnet.ko"
    echo "PASS $2 $case_name: standard names and stock USBnet recovery"
done
run usb-wrong update
if run usb-wrong install kmod-usb-net-rndis; then
    echo 'FAIL wrong ABI accepted' >&2
    exit 1
fi
run usb-manual update
if run usb-manual install kmod-usb-net-cdc-ether kmod-usb-net-rndis; then
    echo 'FAIL legacy file ownership overwritten' >&2
    exit 1
fi
# Quiesce tethering first on a real modem; fixtures are inert.
while read -r previous; do
    run usb-manual remove "$previous"
done < "$base/usb-previous"
run usb-manual install kmod-usb-net-cdc-ether kmod-usb-net-rndis
(cd "$base/usb-manual" && sha256sum -c "$base/usb-checks")
echo "PASS $2: wrong ABI rejected and manual ownership migrated"
