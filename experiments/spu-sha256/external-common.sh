#!/bin/sh
# Temporary underlay/NAT for one reserved namespace and one explicit lab peer.
# Does not create root-namespace XFRM state/policy or change persistent files.
set -eu
a=spu-check-a
peer=${PEER_IP:-192.168.133.100}
port=45069
ns_created=0
filter_created=0
nat_created=0
dnat_created=0
external_preflight() {
 test "$peer" = 192.168.133.100
 test "$(cat /proc/sys/net/ipv4/ip_forward)" -eq 1
 test -z "$(ip xfrm state)"
 test -z "$(ip xfrm policy)"
 if ip netns list | grep -Eq '^spu-check-[ab]( |$)'; then return 1; fi
 if ip link show spub >/dev/null 2>&1; then return 1; fi
 if iptables -nL SPU2FORW >/dev/null 2>&1; then return 1; fi
 if iptables -t nat -nL SPU2NAT >/dev/null 2>&1; then return 1; fi
 if iptables -t nat -nL SPU2DNAT >/dev/null 2>&1; then return 1; fi
 test -z "$(ip route show 198.18.69.0/30)"
 iptables-save | sed '/^#/d;s/\[[0-9][0-9]*:[0-9][0-9]*\]/[0:0]/g' | sha256sum > /tmp/spu-sha256/firewall-before.sha256
}
external_setup() {
 ip netns add "$a"; ns_created=1
 ip -n "$a" link add spua type veth peer name spub netns 1
 ip -n "$a" addr add 198.18.69.1/30 dev spua
 ip addr add 198.18.69.2/30 dev spub
 ip -n "$a" link set lo up
 ip -n "$a" link set spua up
 ip link set spub up
 ip -n "$a" route add default via 198.18.69.2
 if [ -n "${RPS_MASK:-}" ]; then
  case "$RPS_MASK" in 0|1|2|3) : ;; *) exit 1 ;; esac
  ip netns exec "$a" sh -c 'echo "$1" > /sys/class/net/spua/queues/rx-0/rps_cpus' sh "$RPS_MASK"
  echo "$RPS_MASK" > /sys/class/net/spub/queues/rx-0/rps_cpus
 fi
 if [ "${VETH_OFFLOADS_OFF:-0}" -eq 1 ]; then
  ip netns exec "$a" /tmp/spu-sha256/veth-offloads spua
  /tmp/spu-sha256/veth-offloads spub
 fi
 iptables -N SPU2FORW; filter_created=1
 if [ "${PEER_INITIATES:-0}" -eq 1 ]; then
  iptables -A SPU2FORW -i spub -s 198.18.69.1/32 -d "$peer"/32 -p udp --sport "$port" -j ACCEPT
  iptables -A SPU2FORW -o spub -s "$peer"/32 -d 198.18.69.1/32 -p udp --dport "$port" -j ACCEPT
 else
  iptables -A SPU2FORW -i spub -s 198.18.69.1/32 -d "$peer"/32 -p udp --dport "$port" -j ACCEPT
  iptables -A SPU2FORW -o spub -s "$peer"/32 -d 198.18.69.1/32 -p udp --sport "$port" -j ACCEPT
 fi
 iptables -I FORWARD 1 -j SPU2FORW
 if [ "${EXTERNAL_PLAIN:-0}" -eq 1 ]; then
  iptables -A SPU2FORW -i spub -s 198.18.69.1/32 -d "$peer"/32 -p tcp --dport 26969 -j ACCEPT
  iptables -A SPU2FORW -o spub -s "$peer"/32 -d 198.18.69.1/32 -p tcp --sport 26969 -j ACCEPT
 fi
 iptables -t nat -N SPU2NAT; nat_created=1
 if [ "${PEER_INITIATES:-0}" -eq 0 ]; then
  iptables -t nat -A SPU2NAT -s 198.18.69.1/32 -d "$peer"/32 -p udp --dport "$port" -j MASQUERADE
 else
  iptables -t nat -N SPU2DNAT; dnat_created=1
  iptables -t nat -A SPU2DNAT -p udp -j DNAT --to-destination 198.18.69.1:45069
  iptables -t nat -I PREROUTING 1 -s "$peer"/32 -d 192.168.133.69/32 -p udp --dport "$port" -j SPU2DNAT
 fi
 iptables -t nat -I POSTROUTING 1 -j SPU2NAT
 if [ "${EXTERNAL_PLAIN:-0}" -eq 1 ]; then
  iptables -t nat -A SPU2NAT -s 198.18.69.1/32 -d "$peer"/32 -p tcp --dport 26969 -j MASQUERADE
 fi
}
external_cleanup() {
 if [ "$dnat_created" -eq 1 ]; then
  if iptables -t nat -C PREROUTING -s "$peer"/32 -d 192.168.133.69/32 -p udp --dport "$port" -j SPU2DNAT 2>/dev/null; then
   iptables -t nat -D PREROUTING -s "$peer"/32 -d 192.168.133.69/32 -p udp --dport "$port" -j SPU2DNAT
  fi
  iptables -t nat -F SPU2DNAT
  iptables -t nat -X SPU2DNAT
 fi
 if [ "$filter_created" -eq 1 ]; then
  iptables -D FORWARD -j SPU2FORW 2>/dev/null || true
  iptables -F SPU2FORW
  iptables -X SPU2FORW
 fi
 if [ "$nat_created" -eq 1 ]; then
  iptables -t nat -D POSTROUTING -j SPU2NAT 2>/dev/null || true
  iptables -t nat -F SPU2NAT
  iptables -t nat -X SPU2NAT
 fi
 if [ "$ns_created" -eq 1 ]; then
  ip -n "$a" xfrm policy flush
  ip -n "$a" xfrm state flush
  ip netns del "$a"
 fi
 iptables-save | sed '/^#/d;s/\[[0-9][0-9]*:[0-9][0-9]*\]/[0:0]/g' | sha256sum > /tmp/spu-sha256/firewall-after.sha256
 if cmp -s /tmp/spu-sha256/firewall-before.sha256 /tmp/spu-sha256/firewall-after.sha256; then
  echo FIREWALL_RESTORED
 else
  echo 'Firewall changed concurrently; test chains removed without restoring foreign rules'
 fi
}
