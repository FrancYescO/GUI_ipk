#!/bin/sh
set -eu
cd /tmp/spu-sha256
PEER_INITIATES=1
. ./external-common.sh
udp_pid=
aes_loaded=0
sha_loaded=0
unload_own() {
 for attempt in $(seq 1 90); do
  if ! grep -q "^$1 " /proc/modules; then return 0; fi
  if rmmod "$1" 2>/dev/null; then return 0; fi
  sleep 1
 done
 echo "Module still referenced: $1; no forced unload"
 return 1
}
external_preflight
if grep -Eq '^(bcmspu|spu_sha256_hybrid|wireguard|aes_arm|sha256_arm) ' /proc/modules; then exit 1; fi
cleanup() {
 result=$1
 trap - EXIT HUP INT TERM
 if [ -n "$udp_pid" ]; then kill "$udp_pid" 2>/dev/null || true; wait "$udp_pid" 2>/dev/null || true; fi
 external_cleanup || result=1
 sleep 3
 if [ "$aes_loaded" -eq 1 ]; then unload_own aes_arm || result=1; fi
 if [ "$sha_loaded" -eq 1 ]; then unload_own sha256_arm || result=1; fi
 if [ "$result" -eq 0 ]; then echo EXTERNAL_IPSEC_PASS; fi
 exit "$result"
}
trap 'cleanup $?' EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
insmod ./aes-arm.ko; aes_loaded=1
insmod ./sha256-arm.ko; sha_loaded=1
external_setup
ip -n "$a" addr add 10.253.69.1/32 dev lo
ip -n "$a" route add 10.253.69.2/32 via 198.18.69.2 src 10.253.69.1
rm -f ./udp-peer ./external-go
ip netns exec "$a" ./udp-encap 198.18.69.1 45069 ./udp-peer > ./udp-encap.log 2>&1 &
udp_pid=$!
echo EXTERNAL_ESP_LISTENING
for tick in $(seq 1 35); do
 if [ -f ./udp-peer ]; then break; fi
 sleep 1
done
test -f ./udp-peer
read remote_ip remote_port < ./udp-peer
test "$remote_ip" = "$peer"
case "$remote_port" in ''|*[!0-9]*) exit 1 ;; esac
test "$remote_port" -ge 1
test "$remote_port" -le 65535
case "${KEYBITS:-128}" in
 128) key=0x00112233445566778899aabbccddeeff ;;
 256) key=0x00112233445566778899aabbccddeeff000102030405060708090a0b0c0d0e0f ;;
 *) exit 1 ;;
esac
auth=0x000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f
ip -n "$a" xfrm state add src 198.18.69.1 dst "$peer" proto esp spi 0x10690001 reqid 69 mode tunnel auth-trunc 'hmac(sha256)' "$auth" 128 enc 'cbc(aes)' "$key" replay-window 32 encap espinudp 45069 "$remote_port" 0.0.0.0
ip -n "$a" xfrm state add src "$peer" dst 198.18.69.1 proto esp spi 0x10690002 reqid 69 mode tunnel auth-trunc 'hmac(sha256)' "$auth" 128 enc 'cbc(aes)' "$key" replay-window 32 encap espinudp "$remote_port" 45069 0.0.0.0
ip -n "$a" xfrm policy add src 10.253.69.1/32 dst 10.253.69.2/32 dir out tmpl src 198.18.69.1 dst "$peer" proto esp reqid 69 mode tunnel
ip -n "$a" xfrm policy add src 10.253.69.2/32 dst 10.253.69.1/32 dir in tmpl src "$peer" dst 198.18.69.1 proto esp reqid 69 mode tunnel
echo EXTERNAL_ESP_READY
for tick in $(seq 1 35); do
 if [ -f ./external-go ]; then break; fi
 sleep 1
done
test -f ./external-go
ip netns exec "$a" ping -c 3 -W 3 -s 1200 10.253.69.2
for direction in forward reverse; do
 echo "EXTERNAL_ESP_BENCH AES${KEYBITS:-128} $direction"
 reverse=
 if [ "$direction" = reverse ]; then reverse=-R; fi
 timeout -s INT 20 ip netns exec "$a" "${IPERF:-iperf3}" -c 10.253.69.2 -B 10.253.69.1 -p 26969 -t 5 $reverse -J
done
ip -n "$a" -s xfrm state | grep -E 'stats:|replay-window [0-9]+ replay'
