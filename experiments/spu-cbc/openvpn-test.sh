#!/bin/sh
# Two loopback UDP peers, with their TUN devices moved into isolated namespaces.
# The module stack and private bridge are already running in run-engine.sh.
set -eu
umask 077
d=${1:?lab directory}
bits=${2:-128}
case "$bits" in 128|256) ;; *) exit 2 ;; esac
ovpn="$d/apps/usr/sbin/openvpn"
test -x "$ovpn"
test -c /dev/crypto-cbc-lab
test -d /sys/module/spu_cbc_lab
echo '374b8399951a4fa75a0b9c68b6eced9d064cc442d3150d2210d75623c275354e  /lib/modules/4.1.52/tun.ko' | sha256sum -c -
for suffix in a b; do
    if ip netns list | grep -Eq "^spucbc-$suffix( |$)"; then exit 1; fi
    if ip link show "spucbc-$suffix" >/dev/null 2>&1; then exit 1; fi
done
if grep -Eiq ':B0E[12][[:space:]]' /proc/net/udp /proc/net/udp6; then exit 1; fi

stop_peer() {
    suffix=$1
    pidfile="$d/openvpn-$suffix.pid"
    test -s "$pidfile" || return 0
    pid=$(cat "$pidfile")
    case "$pid" in ''|*[!0-9]*) return 1 ;; esac
    if test -e "/proc/$pid/cmdline"; then
        grep -Fq "$d/openvpn-$suffix.conf" "/proc/$pid/cmdline" || return 1
        kill -TERM "$pid"
        for wait_step in 1 2 3 4 5; do
            test -e "/proc/$pid" || return 0
            sleep 1
        done
        echo "PENDING: peer $suffix still alive, preserving namespace"
        return 1
    fi
}
cleanup() {
    stop_peer a || return 1
    stop_peer b || return 1
    for suffix in a b; do
        ip netns del "spucbc-$suffix" 2>/dev/null || true
        ip link del "spucbc-$suffix" 2>/dev/null || true
    done
    rm -f "$d/openvpn.key" "$d/openvpn-a.pid" "$d/openvpn-b.pid"
    echo OPENVPN_CLEANUP_OK
}
trap cleanup EXIT
ip netns add spucbc-a
ip netns add spucbc-b
ip -n spucbc-a link set lo up
ip -n spucbc-b link set lo up
LD_PRELOAD="$d/redirect-crypto.so" "$ovpn" --genkey secret "$d/openvpn.key"
for suffix in a b; do
    if test "$suffix" = a; then
        local_ip=198.19.253.1; peer_ip=198.19.253.2; local_port=45281; peer_port=45282; direction=0
    else
        local_ip=198.19.253.2; peer_ip=198.19.253.1; local_port=45282; peer_port=45281; direction=1
    fi
    cat > "$d/openvpn-up-$suffix.sh" <<EOF
#!/bin/sh
set -eu
ip link set dev spucbc-$suffix netns spucbc-$suffix
ip -n spucbc-$suffix addr add $local_ip peer $peer_ip dev spucbc-$suffix
ip -n spucbc-$suffix link set dev spucbc-$suffix mtu 1400 up
EOF
    chmod 700 "$d/openvpn-up-$suffix.sh"
    cat > "$d/openvpn-$suffix.conf" <<EOF
dev spucbc-$suffix
dev-type tun
proto udp4
local 127.0.0.1
lport $local_port
remote 127.0.0.1 $peer_port
secret "$d/openvpn.key" $direction
cipher AES-$bits-CBC
data-ciphers AES-$bits-CBC
auth SHA256
engine cryptodev
ifconfig $local_ip $peer_ip
ifconfig-noexec
route-noexec
tun-mtu 1400
script-security 2
up "$d/openvpn-up-$suffix.sh"
persist-key
persist-tun
verb 3
writepid "$d/openvpn-$suffix.pid"
log "$d/openvpn-$suffix.log"
EOF
    LD_PRELOAD="$d/redirect-crypto.so" "$ovpn" --config "$d/openvpn-$suffix.conf" --daemon "spu-cbc-$suffix"
done
for wait_step in 1 2 3 4 5; do
    if grep -q 'UDPv4 link remote:' "$d/openvpn-a.log" &&
       grep -q 'UDPv4 link remote:' "$d/openvpn-b.log"; then break; fi
    sleep 1
done
grep 'UDPv4 link remote:' "$d/openvpn-a.log" "$d/openvpn-b.log"
echo "OPENVPN_AES${bits}_CBC"
ip netns exec spucbc-a ping -c 5 -W 1 -w 8 -s 1000 198.19.253.2 > "$d/ping-a.log"
cat "$d/ping-a.log"
grep -q ', 0% packet loss' "$d/ping-a.log"
ip netns exec spucbc-b ping -c 5 -W 1 -w 8 -s 1000 198.19.253.1 > "$d/ping-b.log"
cat "$d/ping-b.log"
grep -q ', 0% packet loss' "$d/ping-b.log"
echo OPENVPN_DATA_PASS
spuctl showstats
echo CBC_ENCRYPT_CHUNKS
cat /sys/module/spu_cbc_lab/parameters/enc_chunks
echo CBC_DECRYPT_CHUNKS
cat /sys/module/spu_cbc_lab/parameters/dec_chunks
