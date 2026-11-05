#!/bin/sh
# Non-persistent two-peer IPsec exercise; touches only dedicated namespaces.
set -eu
a=spu-check-a
b=spu-check-b
server=
case "${SERVER_CPU:-}:${CLIENT_CPU:-}" in
 :|0:0|0:1|1:0|1:1) : ;;
 *) echo 'CPU choices must both be 0 or 1' >&2; exit 1 ;;
esac
ip netns list | grep -Eq "^($a|$b)( |$)" && {
    echo 'Test namespace already exists; refusing to change it' >&2
    exit 1
}
cleanup() {
    if [ -n "$server" ]; then kill "$server" 2>/dev/null || true; fi
    ip netns del "$a" 2>/dev/null || true
    ip netns del "$b" 2>/dev/null || true
}
trap cleanup EXIT HUP INT TERM
for keybits in ${KEYBITS:-128 192 256}; do
case "$keybits" in
128) key=0x00112233445566778899aabbccddeeff ;;
192) key=0x00112233445566778899aabbccddeeff0001020304050607 ;;
256) key=0x00112233445566778899aabbccddeeff000102030405060708090a0b0c0d0e0f ;;
esac
for hash in ${AUTH_MODE:-sha256}; do
    case "$hash" in sha256|gcm) : ;; *) exit 1 ;; esac
    ip netns add "$a"
    ip netns add "$b"
    ip -n "$a" link add spua type veth peer name spub netns "$b"
    ip -n "$a" addr add 198.18.69.1/30 dev spua
    ip -n "$b" addr add 198.18.69.2/30 dev spub
    ip -n "$a" addr add 10.253.69.1/32 dev lo
    ip -n "$b" addr add 10.253.69.2/32 dev lo
    ip -n "$a" link set lo up
    ip -n "$b" link set lo up
    ip -n "$a" link set spua up
    ip -n "$b" link set spub up
    ip -n "$a" route add 10.253.69.2/32 via 198.18.69.2 src 10.253.69.1
    ip -n "$b" route add 10.253.69.1/32 via 198.18.69.1 src 10.253.69.2
    # Public, disposable test keys; never reused for a real connection.
    auth=0x000102030405060708090a0b0c0d0e0f10111213
    bits=96
    if [ "$hash" = sha256 ]; then
        auth=0x000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f
        bits=128
    fi
    for ns in "$a" "$b"; do
      if [ "$hash" = gcm ]; then
        bits=128
        ip -n "$ns" xfrm state add src 198.18.69.1 dst 198.18.69.2 proto esp spi 0x10690001 reqid 69 mode tunnel aead 'rfc4106(gcm(aes))' "${key}11223344" 128 replay-window "${REPLAY_WINDOW:-32}"
        ip -n "$ns" xfrm state add src 198.18.69.2 dst 198.18.69.1 proto esp spi 0x10690002 reqid 69 mode tunnel aead 'rfc4106(gcm(aes))' "${key}11223344" 128 replay-window "${REPLAY_WINDOW:-32}"
      else
        ip -n "$ns" xfrm state add src 198.18.69.1 dst 198.18.69.2 proto esp spi 0x10690001 reqid 69 mode tunnel \
            auth-trunc "hmac($hash)" "$auth" "$bits" enc 'cbc(aes)' "$key" replay-window "${REPLAY_WINDOW:-32}"
        ip -n "$ns" xfrm state add src 198.18.69.2 dst 198.18.69.1 proto esp spi 0x10690002 reqid 69 mode tunnel \
            auth-trunc "hmac($hash)" "$auth" "$bits" enc 'cbc(aes)' "$key" replay-window "${REPLAY_WINDOW:-32}"
      fi
    done
    ip -n "$a" xfrm policy add src 10.253.69.1/32 dst 10.253.69.2/32 dir out tmpl src 198.18.69.1 dst 198.18.69.2 proto esp reqid 69 mode tunnel
    ip -n "$a" xfrm policy add src 10.253.69.2/32 dst 10.253.69.1/32 dir in tmpl src 198.18.69.2 dst 198.18.69.1 proto esp reqid 69 mode tunnel
    ip -n "$b" xfrm policy add src 10.253.69.2/32 dst 10.253.69.1/32 dir out tmpl src 198.18.69.2 dst 198.18.69.1 proto esp reqid 69 mode tunnel
    ip -n "$b" xfrm policy add src 10.253.69.1/32 dst 10.253.69.2/32 dir in tmpl src 198.18.69.1 dst 198.18.69.2 proto esp reqid 69 mode tunnel
    if [ -n "${RPS_MASK:-}" ]; then
      case "$RPS_MASK" in 0|1|2|3) : ;; *) exit 1 ;; esac
      ip netns exec "$a" sh -c 'echo "$1" > /sys/class/net/spua/queues/rx-0/rps_cpus' sh "$RPS_MASK"
      ip netns exec "$b" sh -c 'echo "$1" > /sys/class/net/spub/queues/rx-0/rps_cpus' sh "$RPS_MASK"
    fi
    echo "SETTINGS server_cpu=${SERVER_CPU:-auto} client_cpu=${CLIENT_CPU:-auto} mss=${TCP_MSS:-auto} rps=${RPS_MASK:-0}"
    echo "IPsec AES$keybits/$hash-$bits"
    ip netns exec "$a" ping -c 3 -W 3 -s 4000 10.253.69.2
    ip netns exec "$b" ping -c 3 -W 3 -s 4000 10.253.69.1
    for direction in forward reverse; do
        echo "BENCHMARK ${PHASE:?} AES$keybits $direction"
        ip netns exec "$b" "${IPERF:-iperf3}" -s -1 -B 10.253.69.2 -p "${TEST_PORT:-26969}" ${SERVER_CPU:+-A "$SERVER_CPU"} > /tmp/spu-iperf-server.log 2>&1 &
        server=$!
        sleep 1
        reverse=
        if [ "$direction" = reverse ]; then reverse=-R; fi
        timeout -s INT "${TEST_TIMEOUT:-30}" ip netns exec "$a" "${IPERF:-iperf3}" -c 10.253.69.2 -B 10.253.69.1 -p "${TEST_PORT:-26969}" ${CLIENT_CPU:+-A "$CLIENT_CPU"} ${TCP_MSS:+-M "$TCP_MSS"} -t "${SECONDS_PER_TEST:-5}" $reverse -J
        wait "$server"
        server=
    done
    echo PROVIDERS
    cat /proc/crypto | grep -E '^name|^driver|^priority|^refcnt' | grep -A3 -B1 -E 'authenc|sha256|aes' || true
  ip -n "$a" -s xfrm state | grep -E "lifetime current|stats:|replay-window [0-9]+ replay"
  ip -n "$b" -s xfrm state | grep -E "lifetime current|stats:|replay-window [0-9]+ replay"
  if grep -q '^bcmspu ' /proc/modules; then
 spuctl showstats
 for stat in transfer_requests lab_no_slot lab_tx_error lab_recycle lab_double_free lab_rx_polls lab_rx_batches lab_rx_done lab_rx_invalid lab_inflight lab_pool_fallback_uses; do
  echo "$stat=$(cat /sys/module/bcmspu/parameters/$stat)"
 done
 test "$(cat /sys/module/bcmspu/parameters/lab_double_free)" -eq 0
fi
  if [ -d /sys/module/spu_sha256_hybrid ]; then
    for stat in enc_packets dec_packets bad_tags borrowed_packets; do
      echo "$stat=$(cat /sys/module/spu_sha256_hybrid/parameters/$stat)"
    done
  fi
    cleanup
done
done
