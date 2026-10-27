#!/bin/sh
# Run only with no USB network devices attached. Modules remain in /tmp.
set -eu
root="${1:?temporary directory containing both modules required}"
case "$root" in /tmp/*) ;; *) echo 'Test modules must be in /tmp' >&2; exit 1 ;; esac
boot_before="$(cat /proc/sys/kernel/random/boot_id)"
taint_before="$(cat /proc/sys/kernel/tainted)"
route_before="$(ip route show default)"
usbnet_before="$(sha256sum /lib/modules/4.1.38/usbnet.ko)"
original_cdc=0
original_rndis=0
[ ! -d /sys/module/cdc_ether ] || original_cdc=1
[ ! -d /sys/module/rndis_host ] || original_rndis=1
# Refuse to disturb an attached USB network interface, even if another driver owns it.
for interface in /sys/class/net/*; do
  device="$(readlink -f "$interface/device" 2>/dev/null || true)"
  case "$device" in */usb[0-9]*/*) echo "USB network interface is in use: $interface" >&2; exit 1 ;; esac
done
if [ "$original_rndis" = 1 ]; then
  [ "$(cat /sys/module/rndis_host/refcnt)" = 0 ] || { echo 'RNDIS module busy'; exit 1; }
fi
cdc_removed=0
rndis_removed=0
restore() {
  result=$?
  trap - EXIT HUP INT TERM
  if [ "$cdc_removed" = 1 ]; then
    if [ -d /sys/module/rndis_host ]; then rmmod rndis_host || result=1; fi
    if [ -d /sys/module/cdc_ether ]; then rmmod cdc_ether || result=1; fi
    if [ "$original_cdc" = 1 ]; then insmod /lib/modules/4.1.38/cdc_ether.ko || result=1; fi
  fi
  if [ "$rndis_removed" = 1 ] && [ "$original_rndis" = 1 ]; then
    insmod /lib/modules/4.1.38/rndis_host.ko || result=1
  fi
  [ "$(cat /proc/sys/kernel/random/boot_id)" = "$boot_before" ] || result=1
  [ "$(cat /proc/sys/kernel/tainted)" = "$taint_before" ] || result=1
  [ "$(ip route show default)" = "$route_before" ] || result=1
  [ "$(sha256sum /lib/modules/4.1.38/usbnet.ko)" = "$usbnet_before" ] || result=1
  echo "RESTORE_RESULT=$result"
  echo "BOOT_ID=$(cat /proc/sys/kernel/random/boot_id)"
  echo "TAINT=$(cat /proc/sys/kernel/tainted)"
  lsmod | grep -E '^(usbnet|cdc_ether|rndis_host) ' || true
  exit "$result"
}
trap restore EXIT HUP INT TERM
if [ "$original_rndis" = 1 ]; then rmmod rndis_host; rndis_removed=1; fi
if [ "$original_cdc" = 1 ]; then
  [ "$(cat /sys/module/cdc_ether/refcnt)" = 0 ] || { echo 'CDC module busy'; exit 1; }
  rmmod cdc_ether
fi
cdc_removed=1
insmod "$root/cdc_ether.ko"
test -d /sys/bus/usb/drivers/cdc_ether
insmod "$root/rndis_host.ko"
test -d /sys/bus/usb/drivers/rndis_host
echo 'LOAD_AND_USB_DRIVER_REGISTRATION=PASS'
sha256sum "$root/cdc_ether.ko" "$root/rndis_host.ko"
lsmod | grep -E '^(usbnet|cdc_ether|rndis_host) '
rmmod rndis_host
rmmod cdc_ether
echo 'UNLOAD=PASS'
echo 'USB_DEVICE_TRAFFIC=NOT_TESTED_NO_DEVICE_ATTACHED'
