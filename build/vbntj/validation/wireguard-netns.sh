#!/bin/sh
# Temporary two-peer test; requires raw module and wg tool already in /tmp.
set -eu
a=wg52-check-a
b=wg52-check-b
keys=/tmp/wg52-check-keys
wg="$(cd "$(dirname "$0")" && pwd)/wg"
loaded=0
ip netns list | grep -Eq "^($a|$b)( |$)" && exit 1
test ! -e "$keys"
test -d /sys/module/wireguard
cleanup() {
    result=$?
    trap - EXIT HUP INT TERM
    ip netns del "$a" 2>/dev/null || true
    ip netns del "$b" 2>/dev/null || true
    rm -rf "$keys"
    if [ "$loaded" -eq 1 ]; then
        for attempt in 1 2 3 4 5; do
            sleep 1
            rmmod wireguard 2>/dev/null && break
        done
        if [ -d /sys/module/wireguard ]; then
            echo 'WireGuard still referenced; no forced removal attempted' >&2
            result=1
        fi
    fi
    exit "$result"
}
trap cleanup EXIT HUP INT TERM
umask 077
mkdir "$keys"
"$wg" genkey > "$keys/a"
"$wg" genkey > "$keys/b"
"$wg" pubkey < "$keys/a" > "$keys/a.pub"
"$wg" pubkey < "$keys/b" > "$keys/b.pub"
ip netns add "$a"
ip netns add "$b"
ip -n "$a" link add wga-under type veth peer name wgb-under netns "$b"
ip -n "$a" addr add 198.18.152.1/30 dev wga-under
ip -n "$b" addr add 198.18.152.2/30 dev wgb-under
ip -n "$a" link set wga-under up
ip -n "$b" link set wgb-under up
for ns in "$a" "$b"; do
    ip -n "$ns" link set lo up
    ip -n "$ns" link add wg52 type wireguard
done
ip -n "$a" addr add 10.253.152.1/30 dev wg52
ip -n "$b" addr add 10.253.152.2/30 dev wg52
ip netns exec "$a" "$wg" set wg52 private-key "$keys/a" listen-port 51852 \
    peer "$(cat "$keys/b.pub")" allowed-ips 10.253.152.2/32 endpoint 198.18.152.2:51853
ip netns exec "$b" "$wg" set wg52 private-key "$keys/b" listen-port 51853 \
    peer "$(cat "$keys/a.pub")" allowed-ips 10.253.152.1/32 endpoint 198.18.152.1:51852
ip -n "$a" link set wg52 up
ip -n "$b" link set wg52 up
ip netns exec "$a" ping -c 5 -W 3 -s 1000 10.253.152.2
ip netns exec "$b" ping -c 5 -W 3 -s 1000 10.253.152.1
for ns in "$a" "$b"; do
    ip netns exec "$ns" "$wg" show wg52 latest-handshakes \
        | awk '$2 > 0 { n++ } END { exit n == 1 ? 0 : 1 }'
    ip netns exec "$ns" "$wg" show wg52 transfer \
        | awk '{ print "WireGuard received=" $2 " sent=" $3 }'
done
echo WIREGUARD_NETNS_PASS
