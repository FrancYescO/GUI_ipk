#!/bin/sh
# Non-persistent two-peer IPsec exercise; touches only dedicated namespaces.
set -eu
a=spu-check-a
b=spu-check-b
server=
ip netns list | grep -Eq "^($a|$b)( |$)" && {
    echo 'Test namespace already exists; refusing to change it' >&2
    exit 1
}
grep -q '^bcmspu ' /proc/modules
cleanup() {
    if [ -n "$server" ]; then kill "$server" 2>/dev/null || true; fi
    ip netns del "$a" 2>/dev/null || true
    ip netns del "$b" 2>/dev/null || true
}
trap cleanup EXIT HUP INT TERM
for keybits in 128 192 256; do
case "$keybits" in
128) key=0x00112233445566778899aabbccddeeff ;;
192) key=0x00112233445566778899aabbccddeeff0001020304050607 ;;
256) key=0x00112233445566778899aabbccddeeff000102030405060708090a0b0c0d0e0f ;;
esac
for hash in sha1 sha256; do
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
        ip -n "$ns" xfrm state add src 198.18.69.1 dst 198.18.69.2 proto esp spi 0x10690001 reqid 69 mode tunnel \
            auth-trunc "hmac($hash)" "$auth" "$bits" enc 'cbc(aes)' "$key" replay-window 32
        ip -n "$ns" xfrm state add src 198.18.69.2 dst 198.18.69.1 proto esp spi 0x10690002 reqid 69 mode tunnel \
            auth-trunc "hmac($hash)" "$auth" "$bits" enc 'cbc(aes)' "$key" replay-window 32
    done
    ip -n "$a" xfrm policy add src 10.253.69.1/32 dst 10.253.69.2/32 dir out tmpl src 198.18.69.1 dst 198.18.69.2 proto esp reqid 69 mode tunnel
    ip -n "$a" xfrm policy add src 10.253.69.2/32 dst 10.253.69.1/32 dir in tmpl src 198.18.69.2 dst 198.18.69.1 proto esp reqid 69 mode tunnel
    ip -n "$b" xfrm policy add src 10.253.69.2/32 dst 10.253.69.1/32 dir out tmpl src 198.18.69.2 dst 198.18.69.1 proto esp reqid 69 mode tunnel
    ip -n "$b" xfrm policy add src 10.253.69.1/32 dst 10.253.69.2/32 dir in tmpl src 198.18.69.1 dst 198.18.69.2 proto esp reqid 69 mode tunnel
    echo "IPsec AES$keybits/$hash-$bits"
    ip netns exec "$a" ping -c 3 -W 3 -s 4000 10.253.69.2
    ip netns exec "$b" ping -c 3 -W 3 -s 4000 10.253.69.1
    # Update both SAs on both peers with a different disposable key.
  oldkey="$key"
  key="$(echo "$oldkey" | sed 's/00112233/ffeeddcc/')"
  for ns in "$a" "$b"; do
    ip -n "$ns" xfrm state update src 198.18.69.1 dst 198.18.69.2 proto esp spi 0x10690001 reqid 69 mode tunnel auth-trunc "hmac($hash)" "$auth" "$bits" enc 'cbc(aes)' "$key" replay-window 32
    ip -n "$ns" xfrm state update src 198.18.69.2 dst 198.18.69.1 proto esp spi 0x10690002 reqid 69 mode tunnel auth-trunc "hmac($hash)" "$auth" "$bits" enc 'cbc(aes)' "$key" replay-window 32
  done
  echo "REKEY AES$keybits/$hash"
  ip netns exec "$a" ping -c 3 -W 3 -s 4000 10.253.69.2
  ip netns exec "$b" ping -c 3 -W 3 -s 4000 10.253.69.1
  ip netns exec "$b" iperf3 -s -1 -B 10.253.69.2 > /tmp/spu-iperf-server.log 2>&1 &
  server=$!
  sleep 1
  ip netns exec "$a" iperf3 -c 10.253.69.2 -B 10.253.69.1 -u -b 10M -l 1000 -t 3
  wait "$server"
  server=
  key="$oldkey"
  ip -n "$a" -s xfrm state
  ip -n "$b" -s xfrm state
  spuctl showstats
    cleanup
done
done
