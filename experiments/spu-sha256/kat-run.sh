#!/bin/sh
set -eu
cd /tmp/spu-sha256
if [ "${RX_DRAIN:-0}" -ne 0 ] && [ "${POOL_FALLBACK:-0}" -ne 0 ]; then
 echo 'Refusing RX drain + pool fallback: combination reproduced loss of modem ping/SSH; serial diagnosis required'
 exit 1
fi
if [ "${RX_POLL_MS:-0}" -ne 0 ] || [ "${RX_DRAIN:-0}" -ne 0 ] || [ "${POOL_FALLBACK:-0}" -ne 0 ] || [ "${FORCE_POOL_FALLBACK:-0}" -ne 0 ]; then
 test "${ALLOW_UNSTABLE_RUNNER:-0}" -eq 1 || { echo 'Queue diagnostics remain quarantined'; exit 1; }
fi
for mod in bcmspu spu_sha256_hybrid aes_arm sha256_arm damson_spu_test; do
 if grep -q "^$mod " /proc/modules; then echo "Refusing: $mod already loaded"; exit 1; fi
done
if [ -n "$(ip xfrm state)" ] || [ -n "$(ip xfrm policy)" ]; then
 echo 'Refusing: active root-namespace IPsec configuration'
 exit 1
fi
cleanup() {
 if grep -q '^damson_spu_test ' /proc/modules; then
  rmmod damson_spu_test || { echo 'KAT remains referenced; no forced unload'; return 1; }
 fi
 sleep 3
 if grep -q '^spu_sha256_hybrid ' /proc/modules; then rmmod spu_sha256_hybrid || return 1; fi
 if grep -q '^bcmspu ' /proc/modules; then
  if ! spuctl stop; then sleep 3; spuctl stop || return 1; fi
  rmmod bcmspu || return 1
 fi
 if grep -q '^aes_arm ' /proc/modules; then rmmod aes_arm || return 1; fi
 if grep -q '^sha256_arm ' /proc/modules; then rmmod sha256_arm || return 1; fi
 echo CLEANUP_OK
}
on_exit() {
 result=$1
 trap - EXIT HUP INT TERM
 cleanup || result=1
 exit "$result"
}
trap 'on_exit $?' EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
sha256sum -c SHA256SUMS
insmod ./bcmspu.ko "transfer_requests=${TRANSFER_REQUESTS:-64}" "rx_poll_ms=${RX_POLL_MS:-0}" "rx_drain=${RX_DRAIN:-0}" "pool_fallback=${POOL_FALLBACK:-0}" "force_pool_fallback=${FORCE_POOL_FALLBACK:-0}"
spuctl start
insmod ./spu_sha256_hybrid.ko "in_place=${IN_PLACE:-0}" "private_sha1=${PRIVATE_SHA1:-0}"
for bits in 128 192 256; do
 for part in 0 1 2 3 4; do
  echo "KAT_GROUP AES$bits corrupt_part=$part"
  insmod ./damson_spu_test.ko only_sha256=1 aesbits="$bits" corrupt_part="$part" "esp_offset=${ESP_OFFSET:-0}" target_driver=authenc-hybrid-sha256-spu
  rmmod damson_spu_test
 done
done
if [ "${IN_PLACE:-0}" -eq 1 ]; then
 borrowed=$(cat /sys/module/spu_sha256_hybrid/parameters/borrowed_packets)
 echo "BORROWED_KAT_PACKETS=$borrowed"
 test "$borrowed" -eq 45
fi
test "$(cat /sys/module/bcmspu/parameters/lab_double_free)" -eq 0
for stat in lab_rx_polls lab_rx_batches lab_rx_done lab_rx_invalid lab_inflight lab_pool_fallback_uses; do
 echo "$stat=$(cat /sys/module/bcmspu/parameters/$stat)"
done
test "$(cat /sys/module/bcmspu/parameters/lab_inflight)" -eq 0
if [ "${FORCE_POOL_FALLBACK:-0}" -eq 1 ]; then
 test "$(cat /sys/module/bcmspu/parameters/lab_pool_fallback_uses)" -gt 0
 test "$(cat /sys/module/bcmspu/parameters/lab_rx_done)" -eq 0
fi
echo KAT_GROUPS_PASS
