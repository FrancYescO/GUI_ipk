#!/bin/sh
set -eu
cd /tmp/spu-sha256
a=spu-check-a
b=spu-check-b
server=
loaded=0
if ip netns list | grep -Eq '^spu-check-[ab]( |$)'; then exit 1; fi
if grep -Eq '^(wireguard|bcmspu|spu_sha256_hybrid) ' /proc/modules; then exit 1; fi
test -z "$(ip xfrm state)"
test -z "$(ip xfrm policy)"
cleanup() {
 result=$1
 trap - EXIT HUP INT TERM
 if [ -n "$server" ]; then kill "$server" 2>/dev/null || true; fi
 ip netns del "$a" 2>/dev/null || true
 ip netns del "$b" 2>/dev/null || true
 sleep 3
 if [ "$loaded" -eq 1 ]; then rmmod wireguard || result=1; fi
 if [ "$result" -eq 0 ]; then echo LOCAL_WIREGUARD_PASS; fi
 exit "$result"
}
trap 'cleanup $?' EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
test "$(sha256sum wireguard.ko | cut -d ' ' -f1)" = 98e392edb92a574444c0555c9576f6ded0041421c938d0a4921789836c46e6e5
insmod ./wireguard.ko; loaded=1
umask 077
./wg genkey > wg-local-b.key
./wg pubkey < wg-local-b.key > wg-local-b.pub
ip netns add "$a"
ip netns add "$b"
ip -n "$a" link add spua type veth peer name spub netns "$b"
ip -n "$a" addr add 198.18.69.1/30 dev spua
ip -n "$b" addr add 198.18.69.2/30 dev spub
for ns in "$a" "$b"; do
 ip -n "$ns" link set lo up
 ip -n "$ns" link add wgtest type wireguard
 ip -n "$ns" link set wgtest mtu 1420 up
done
ip -n "$a" link set spua up
ip -n "$b" link set spub up
ip -n "$a" addr add 10.253.69.1/32 dev wgtest
ip -n "$b" addr add 10.253.69.2/32 dev wgtest
ip netns exec "$a" ./wg set wgtest private-key ./wg-a.key listen-port 45069 peer "$(cat wg-local-b.pub)" allowed-ips 10.253.69.2/32 endpoint 198.18.69.2:45069
ip netns exec "$b" ./wg set wgtest private-key ./wg-local-b.key listen-port 45069 peer "$(cat wg-a.pub)" allowed-ips 10.253.69.1/32 endpoint 198.18.69.1:45069
ip -n "$a" route add 10.253.69.2/32 dev wgtest
ip -n "$b" route add 10.253.69.1/32 dev wgtest
if [ -n "${RPS_MASK:-}" ]; then
 case "$RPS_MASK" in 0|1|2|3) : ;; *) exit 1 ;; esac
 ip netns exec "$a" sh -c 'echo "$1" > /sys/class/net/spua/queues/rx-0/rps_cpus' sh "$RPS_MASK"
 ip netns exec "$b" sh -c 'echo "$1" > /sys/class/net/spub/queues/rx-0/rps_cpus' sh "$RPS_MASK"
fi
ip netns exec "$a" ping -c 3 -W 3 -s 1200 10.253.69.2
ip netns exec "$b" ping -c 3 -W 3 -s 1200 10.253.69.1
for direction in forward reverse; do
 echo "LOCAL_WG_BENCH $direction"
 ip netns exec "$b" "${IPERF:-iperf3}" -s -1 -B 10.253.69.2 -p 26969 > /tmp/spu-iperf-server.log 2>&1 &
 server=$!
 sleep 1
 reverse=
 if [ "$direction" = reverse ]; then reverse=-R; fi
 timeout -s INT 30 ip netns exec "$a" "${IPERF:-iperf3}" -c 10.253.69.2 -B 10.253.69.1 -p 26969 -t "${SECONDS_PER_TEST:-10}" $reverse -J
 wait "$server"
 server=
done
for rate in ${UDP_RATES:-}; do
 case "$rate" in 10M|30M|60M) : ;; *) exit 1 ;; esac
 for direction in forward reverse; do
  echo "LOCAL_WG_UDP $rate $direction"
  ip netns exec "$b" "${IPERF:-iperf3}" -s -1 -B 10.253.69.2 -p 26969 > /tmp/spu-iperf-server.log 2>&1 &
  server=$!
  sleep 1
  reverse=
  if [ "$direction" = reverse ]; then reverse=-R; fi
  timeout -s INT 20 ip netns exec "$a" "${IPERF:-iperf3}" -c 10.253.69.2 -B 10.253.69.1 -p 26969 -u -b "$rate" -l 1000 -t 5 $reverse -J
  wait "$server"
  server=
 done
done
ip netns exec "$a" ./wg show wgtest latest-handshakes
ip netns exec "$a" ./wg show wgtest transfer
