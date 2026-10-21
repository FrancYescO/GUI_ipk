#!/bin/sh
# Run only in the task-owned Docker peer; no real VPN state is touched.
set -eu
export LD_LIBRARY_PATH=/tmp/peer-root/usr/lib/aarch64-linux-gnu
export PATH=/tmp/peer-root/usr/sbin:/tmp/peer-root/usr/bin:$PATH
test -z "$(ip xfrm state)"
test -z "$(ip xfrm policy)"
local_ip=$(ip -4 -o addr show dev eth0 | awk '{split($4,a,"/"); print a[1]}')
gateway=$(ip route show default | awk 'NR == 1 {print $3}')
test -n "$local_ip"
test -n "$gateway"
case "${KEYBITS:-128}" in
 128) key=0x00112233445566778899aabbccddeeff ;;
 256) key=0x00112233445566778899aabbccddeeff000102030405060708090a0b0c0d0e0f ;;
 *) exit 1 ;;
esac
auth=0x000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f
ip addr add 10.253.69.2/32 dev lo
ip route add 10.253.69.1/32 via "$gateway" dev eth0 src 10.253.69.2
ip xfrm state add src "$local_ip" dst 192.168.133.69 proto esp spi 0x10690002 reqid 69 mode tunnel auth-trunc 'hmac(sha256)' "$auth" 128 enc 'cbc(aes)' "$key" replay-window 32 encap espinudp 45069 45069 0.0.0.0
ip xfrm state add src 192.168.133.69 dst "$local_ip" proto esp spi 0x10690001 reqid 69 mode tunnel auth-trunc 'hmac(sha256)' "$auth" 128 enc 'cbc(aes)' "$key" replay-window 32 encap espinudp 45069 45069 0.0.0.0
ip xfrm policy add src 10.253.69.2/32 dst 10.253.69.1/32 dir out tmpl src "$local_ip" dst 192.168.133.69 proto esp reqid 69 mode tunnel
ip xfrm policy add src 10.253.69.1/32 dst 10.253.69.2/32 dir in tmpl src 192.168.133.69 dst "$local_ip" proto esp reqid 69 mode tunnel
echo PEER_IPSEC_CONFIGURED
