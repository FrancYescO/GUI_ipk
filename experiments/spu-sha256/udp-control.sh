#!/bin/sh
set -eu
a=spu-check-a
b=spu-check-b
server=
if ip netns list | grep -Eq '^spu-check-[ab]( |$)'; then exit 1; fi
if grep -Eq '^(wireguard|bcmspu|spu_sha256_hybrid) ' /proc/modules; then exit 1; fi
cleanup() {
 result=$1
 trap - EXIT HUP INT TERM
 if [ -n "$server" ]; then kill "$server" 2>/dev/null || true; fi
 ip netns del "$a" 2>/dev/null || true
 ip netns del "$b" 2>/dev/null || true
 if [ "$result" -eq 0 ]; then echo UDP_CONTROL_PASS; fi
 exit "$result"
}
trap 'cleanup $?' EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
ip netns add "$a"
ip netns add "$b"
ip -n "$a" link add spua type veth peer name spub netns "$b"
ip -n "$a" addr add 198.18.69.1/30 dev spua
ip -n "$b" addr add 198.18.69.2/30 dev spub
ip -n "$a" link set lo up
ip -n "$b" link set lo up
ip -n "$a" link set spua up
ip -n "$b" link set spub up
case "${RPS_MASK:-0}" in 0|1|2|3) : ;; *) exit 1 ;; esac
ip netns exec "$a" sh -c 'echo "$1" > /sys/class/net/spua/queues/rx-0/rps_cpus' sh "${RPS_MASK:-0}"
ip netns exec "$b" sh -c 'echo "$1" > /sys/class/net/spub/queues/rx-0/rps_cpus' sh "${RPS_MASK:-0}"
for rate in 10M 30M 60M; do
 for direction in forward reverse; do
  echo "UDP_CONTROL $rate $direction"
  ip netns exec "$b" "${IPERF:-iperf3}" -s -1 -B 198.18.69.2 -p 26969 > /tmp/spu-iperf-server.log 2>&1 &
  server=$!
  sleep 1
  reverse=
  if [ "$direction" = reverse ]; then reverse=-R; fi
  timeout -s INT 20 ip netns exec "$a" "${IPERF:-iperf3}" -c 198.18.69.2 -B 198.18.69.1 -p 26969 -u -b "$rate" -l 1000 -t 5 $reverse -J
  wait "$server"
  server=
 done
done
ip -n "$a" -s link show spua
ip -n "$b" -s link show spub
