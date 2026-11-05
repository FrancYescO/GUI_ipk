#!/bin/sh
set -eu
cd /tmp/spu-sha256
. ./external-common.sh
wg_loaded=0
cleanup() {
 result=$1
 trap - EXIT HUP INT TERM
 external_cleanup || result=1
 sleep 3
 if [ "$wg_loaded" -eq 1 ]; then rmmod wireguard || result=1; fi
 if [ "$result" -eq 0 ]; then echo EXTERNAL_WIREGUARD_PASS; fi
 exit "$result"
}
external_preflight
if grep -Eq '^(bcmspu|spu_sha256_hybrid|wireguard|aes_arm|sha256_arm) ' /proc/modules; then exit 1; fi
trap 'cleanup $?' EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
test "$(sha256sum ./wireguard.ko | cut -d ' ' -f1)" = 98e392edb92a574444c0555c9576f6ded0041421c938d0a4921789836c46e6e5
insmod ./wireguard.ko; wg_loaded=1
external_setup
ip -n "$a" link add wgtest type wireguard
ip -n "$a" addr add 10.253.69.1/32 dev wgtest
case "${WG_MTU:-1420}" in 1280|1420) : ;; *) exit 1 ;; esac
ip -n "$a" link set wgtest mtu "${WG_MTU:-1420}"
if [ "${PEER_INITIATES:-0}" -eq 1 ]; then
 ip netns exec "$a" ./wg set wgtest private-key ./wg-a.key listen-port "$port" peer "$(cat ./wg-b.pub)" allowed-ips 10.253.69.2/32
else
 ip netns exec "$a" ./wg set wgtest private-key ./wg-a.key listen-port "$port" peer "$(cat ./wg-b.pub)" allowed-ips 10.253.69.2/32 endpoint "$peer:$port" persistent-keepalive 5
fi
ip -n "$a" link set wgtest up
ip -n "$a" route add 10.253.69.2/32 dev wgtest
if [ "${PEER_INITIATES:-0}" -eq 1 ]; then
 rm -f ./external-go
 echo EXTERNAL_WIREGUARD_READY
 for tick in $(seq 1 45); do
  if [ -f ./external-go ]; then break; fi
  sleep 1
 done
 test -f ./external-go
 for tick in $(seq 1 10); do
  if ip netns exec "$a" ./wg show wgtest endpoints | grep -qv '(none)'; then break; fi
  sleep 1
 done
 ip netns exec "$a" ./wg show wgtest endpoints | grep -qv '(none)'
fi
ip netns exec "$a" ping -c 3 -W 3 -s 1200 10.253.69.2
for direction in forward reverse; do
 echo "EXTERNAL_WG_BENCH $direction"
 reverse=
 if [ "$direction" = reverse ]; then reverse=-R; fi
 timeout -s INT 30 ip netns exec "$a" "${IPERF:-iperf3}" -c 10.253.69.2 -B 10.253.69.1 -p 26969 -t 10 $reverse -J
 done
ip netns exec "$a" ./wg show wgtest latest-handshakes
ip netns exec "$a" ./wg show wgtest transfer
