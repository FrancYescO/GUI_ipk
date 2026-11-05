#!/bin/sh
# Read-only observer. Stream stdout to another machine before starting tests.
# Do not collect unfiltered vendor logs: they can contain wireless credentials.
set -eu
limit=${MONITOR_SECONDS:-600}
case "$limit" in ''|*[!0-9]*) exit 1 ;; esac
test "$limit" -le 3600
start=$(cut -d. -f1 /proc/uptime)
while :; do
 now=$(cut -d. -f1 /proc/uptime)
 test "$((now - start))" -lt "$limit" || break
 test ! -e /tmp/spu-sha256/monitor.stop || break
 echo "SNAPSHOT uptime=$now boot=$(cat /proc/sys/kernel/random/boot_id)"
 grep -E '^(MemFree|MemAvailable|Slab|SUnreclaim):' /proc/meminfo
 cat /proc/loadavg
 for name in lab_no_slot lab_tx_error lab_rx_polls lab_rx_batches lab_rx_done lab_rx_invalid lab_inflight lab_pool_fallback_uses lab_double_free; do
  path=/sys/module/bcmspu/parameters/$name
  if test -r "$path"; then printf '%s=' "$name"; cat "$path"; fi
 done
 for pid in $(ps | awk '$NF == "[spu_rx]" {print $1}'); do
  echo "RX_THREAD pid=$pid"
  cat "/proc/$pid/wchan" 2>/dev/null || true
  echo
  cat "/proc/$pid/stack" 2>/dev/null || true
  echo
 done
 dmesg | grep -E 'BUG:|Oops:|Kernel panic|Unable to handle kernel|Internal error:|PC is at |LR is at |Call trace:|Call Trace:|Backtrace:|^\[[ 0-9.]+\] (CPU:|Process |task:|[[:space:]]*\[<)' | tail -20 || true
 sleep 2
done
echo MONITOR_DONE
