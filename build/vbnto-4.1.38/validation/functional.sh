#!/bin/sh
# Exercise only interfaces, rules and sets owned by a disposable namespace.
set -eu
ns=$1
module=$2
peer=kmod38-peer
owned_peer=0
server=
kat_loaded=0
root=$(cd "$(dirname "$0")" && pwd)
cleanup() {
    [ -z "$server" ] || kill "$server" 2>/dev/null || true
    if [ "$owned_peer" -eq 1 ]; then ip netns del "$peer" 2>/dev/null || true; fi
    if [ "$kat_loaded" -eq 1 ]; then rmmod kmod38_kat 2>/dev/null || true; fi
}
trap cleanup EXIT
trap 'exit 124' HUP INT TERM
run() { ip netns exec "$ns" "$@"; }
remote() { ip netns exec "$peer" "$@"; }
pair() {
    ip netns list | grep -Eq "^$peer( |$)" && exit 1
    ip netns add "$peer"
    owned_peer=1
    ip -n "$ns" link add kvt-a type veth peer name kvt-b netns "$peer"
    ip -n "$ns" addr add 198.18.38.1/30 dev kvt-a
    ip -n "$peer" addr add 198.18.38.2/30 dev kvt-b
    ip -n "$ns" link set kvt-a up
    ip -n "$peer" link set lo up
    ip -n "$peer" link set kvt-b up
}
ping_peer() { run ping -c 2 -W 2 198.18.38.2; }
hit() {
    table=$1
    chain=$2
    run iptables -t "$table" -L "$chain" -v -n -x
    run iptables -t "$table" -L "$chain" -v -n -x \
        | awk '$1 ~ /^[0-9]+$/ && $1 > 0 { n++ } END { exit n > 0 ? 0 : 1 }'
}

case "$module" in
    sha256_generic|sha512_generic|crc32c_generic|ecb|ctr|deflate|nls_utf8)
        case "$module" in
            sha256_generic) mode=sha256 ;;
            sha512_generic) mode=sha512 ;;
            crc32c_generic) mode=crc32c ;;
            nls_utf8) mode=nls ;;
            *) mode=$module ;;
        esac
        test ! -d /sys/module/kmod38_kat
        kat_loaded=1
        run insmod "$root/kmod38_kat.ko" "test=$mode"
        run rmmod kmod38_kat
        kat_loaded=0
        echo "FUNCTIONAL_KAT_PASS $mode"
        exit 0
        ;;
    nf_conntrack_netlink)
        pair
        run iptables -A OUTPUT -m conntrack --ctstate NEW,ESTABLISHED -j ACCEPT
        ping_peer
        run conntrack -L -f ipv4 -p icmp | grep 198.18.38
        run conntrack -D -f ipv4 -p icmp
        echo FUNCTIONAL_CONNTRACK_NETLINK_PASS
        exit 0
        ;;
    ip_set_*)
        case "$module" in
            ip_set_bitmap_ip) type=bitmap:ip; key=198.18.38.1; set -- range 198.18.38.0/24 ;;
            ip_set_bitmap_ipmac) type=bitmap:ip,mac; key=198.18.38.1,02:00:00:00:00:01; set -- range 198.18.38.0/24 ;;
            ip_set_bitmap_port) type=bitmap:port; key=10001; set -- range 10000-10010 ;;
            ip_set_hash_ipmark) type=hash:ip,mark; key=198.18.38.1,0x1; set -- ;;
            ip_set_hash_ipport) type=hash:ip,port; key=198.18.38.1,tcp:10001; set -- ;;
            ip_set_hash_ipportip) type=hash:ip,port,ip; key=198.18.38.1,tcp:10001,198.18.38.2; set -- ;;
            ip_set_hash_ipportnet) type=hash:ip,port,net; key=198.18.38.1,tcp:10001,198.18.39.0/24; set -- ;;
            ip_set_hash_mac) type=hash:mac; key=02:00:00:00:00:01; set -- ;;
            ip_set_hash_net) type=hash:net; key=198.18.38.0/24; set -- ;;
            ip_set_hash_netiface) type=hash:net,iface; key=198.18.38.0/24,lo; set -- ;;
            ip_set_hash_netnet) type=hash:net,net; key=198.18.38.0/24,198.18.39.0/24; set -- ;;
            ip_set_hash_netport) type=hash:net,port; key=198.18.38.0/24,tcp:10001; set -- ;;
            ip_set_hash_netportnet) type=hash:net,port,net; key=198.18.38.0/24,tcp:10001,198.18.39.0/24; set -- ;;
            ip_set_list_set)
                run ipset create kvchild hash:ip
                type=list:set; key=kvchild; set -- ;;
            *) exit 77 ;;
        esac
        run ipset create kvtest "$type" "$@"
        run ipset add kvtest "$key"
        run ipset test kvtest "$key"
        run ipset del kvtest "$key"
        run ipset destroy kvtest
        [ "$module" != ip_set_list_set ] || run ipset destroy kvchild
        echo FUNCTIONAL_IPSET_PASS
        exit 0
        ;;
    sch_codel|sch_fq|sch_pie|sch_red|sch_gred|sch_hfsc)
        pair
        kind=${module#sch_}
        case "$kind" in
            red) run tc qdisc add dev kvt-a root handle 1: red limit 100000 min 30000 max 40000 avpkt 1000 burst 40 bandwidth 10mbit ;;
            gred)
                run tc qdisc add dev kvt-a root handle 1: gred setup DPs 1 default 0
                run tc qdisc change dev kvt-a root handle 1: gred limit 100000 min 30000 max 40000 avpkt 1000 burst 40 DP 0 probability 0.02 ;;
            hfsc)
                run tc qdisc add dev kvt-a root handle 1: hfsc default 1
                run tc class add dev kvt-a parent 1: classid 1:1 hfsc sc rate 1mbit ;;
            *) run tc qdisc add dev kvt-a root handle 1: "$kind" ;;
        esac
        ping_peer
        run tc -s qdisc show dev kvt-a
        run tc -s qdisc show dev kvt-a | awk '$1 == "Sent" && $2 > 0 { n++ } END { exit n > 0 ? 0 : 1 }'
        echo FUNCTIONAL_QDISC_PASS
        exit 0
        ;;
    act_skbedit|act_connmark|act_ipt|cls_basic)
        pair
        run tc qdisc add dev kvt-a ingress
        case "$module" in
            act_skbedit) run tc filter add dev kvt-a parent ffff: protocol ip prio 1 u32 match u32 0 0 action skbedit mark 0x38 ;;
            act_connmark)
                run iptables -t mangle -A OUTPUT -j CONNMARK --set-mark 0x38
                run tc filter add dev kvt-a parent ffff: protocol ip prio 1 u32 match u32 0 0 action connmark ;;
            act_ipt) run tc filter add dev kvt-a parent ffff: protocol ip prio 1 u32 match u32 0 0 action ipt -j DSCP --set-dscp 8 ;;
            cls_basic) run tc filter add dev kvt-a parent ffff: protocol ip prio 1 basic action gact pass ;;
        esac
        case "$module" in
            act_ipt) run iptables -t mangle -A INPUT -m dscp --dscp 8 -j ACCEPT ;;
            cls_basic) ;;
            *) run iptables -A INPUT -m mark --mark 0x38 -j ACCEPT ;;
        esac
        ping_peer
        if [ "$module" = act_ipt ]; then hit mangle INPUT
        elif [ "$module" != cls_basic ]; then hit filter INPUT; fi
        run tc -s filter show dev kvt-a parent ffff:
        echo FUNCTIONAL_TC_PASS
        exit 0
        ;;
    xt_DSCP|xt_HL|xt_LOG|nf_log_ipv4|xt_NFQUEUE|xt_NETMAP|xt_TRACE|xt_bpf|xt_connbytes|xt_connlimit|xt_ecn|xt_esp|xt_hl|xt_iprange|xt_length|xt_mac|xt_owner|xt_pkttype|xt_policy|xt_quota|xt_recent|xt_socket|xt_state|xt_statistic|xt_string|xt_tcpmss|xt_time|ipt_ECN|ipt_rpfilter)
        pair
        table=filter
        chain=OUTPUT
        tcp=0
        udp_text=0
        case "$module" in
            xt_DSCP)
                table=mangle
                run iptables -t mangle -A OUTPUT -j DSCP --set-dscp 8
                remote iptables -t mangle -A INPUT -m dscp --dscp 8 -j ACCEPT ;;
            xt_HL)
                table=mangle
                run iptables -t mangle -A OUTPUT -j TTL --ttl-set 63
                remote iptables -t mangle -A INPUT -m ttl --ttl-eq 63 -j ACCEPT ;;
            xt_LOG|nf_log_ipv4) run iptables -A OUTPUT -j LOG --log-prefix KMOD38_TEST ;;
            xt_NFQUEUE) run iptables -A OUTPUT -j NFQUEUE --queue-num 4242 --queue-bypass ;;
            xt_NETMAP) table=nat; run iptables -t nat -A OUTPUT -j NETMAP --to 198.18.38.0/30 ;;
            xt_TRACE) table=raw; run iptables -t raw -A OUTPUT -p icmp -j TRACE ;;
            xt_bpf) run iptables -A OUTPUT -m bpf --bytecode '1,6 0 0 4294967295' -j ACCEPT ;;
            xt_connbytes)
                run sysctl -w net.netfilter.nf_conntrack_acct=1
                run iptables -A OUTPUT -m connbytes --connbytes 0: --connbytes-dir both --connbytes-mode bytes -j ACCEPT ;;
            xt_connlimit) tcp=1; run iptables -A OUTPUT -p tcp --syn -m connlimit --connlimit-above 0 --connlimit-mask 32 -j ACCEPT ;;
            xt_ecn) run iptables -A OUTPUT -m ecn --ecn-ip-ect 0 -j ACCEPT ;;
            xt_esp) exit 77 ;;
            xt_hl) run iptables -A OUTPUT -m ttl --ttl-eq 64 -j ACCEPT ;;
            xt_iprange) run iptables -A OUTPUT -m iprange --dst-range 198.18.38.2-198.18.38.2 -j ACCEPT ;;
            xt_length) run iptables -A OUTPUT -m length --length 1:1500 -j ACCEPT ;;
            xt_mac) chain=INPUT; run iptables -A INPUT -m mac ! --mac-source 00:00:00:00:00:00 -j ACCEPT ;;
            xt_owner) run iptables -A OUTPUT -m owner --uid-owner 0 -j ACCEPT ;;
            xt_pkttype) run iptables -A OUTPUT -m pkttype --pkt-type unicast -j ACCEPT ;;
            xt_policy) run iptables -A OUTPUT -m policy --dir out --pol none -j ACCEPT ;;
            xt_quota) run iptables -A OUTPUT -m quota --quota 4096 -j ACCEPT ;;
            xt_recent) run iptables -A OUTPUT -m recent --name KMOD38 --set -j ACCEPT ;;
            xt_socket) exit 77 ;;
            xt_state) run iptables -A OUTPUT -m state --state NEW,ESTABLISHED,RELATED -j ACCEPT ;;
            xt_statistic) run iptables -A OUTPUT -m statistic --mode nth --every 1 --packet 0 -j ACCEPT ;;
            xt_string) udp_text=1; run iptables -A OUTPUT -m string --algo bm --string kmod-validation -j ACCEPT ;;
            xt_tcpmss) tcp=1; run iptables -A OUTPUT -p tcp --syn -m tcpmss --mss 1:65535 -j ACCEPT ;;
            xt_time) run iptables -A OUTPUT -m time -j ACCEPT ;;
            ipt_ECN) table=mangle; tcp=1; run iptables -t mangle -A OUTPUT -p tcp --syn -j ECN --ecn-tcp-remove ;;
            ipt_rpfilter) table=raw; chain=PREROUTING; run iptables -t raw -A PREROUTING -m rpfilter -j ACCEPT ;;
        esac
        ping_peer
        if [ "$tcp" -eq 1 ]; then run nc -w 1 198.18.38.2 4242 </dev/null || true; fi
        if [ "$udp_text" -eq 1 ]; then printf kmod-validation | run nc -u -w 1 198.18.38.2 4242 || true; fi
        hit "$table" "$chain"
        if [ "$module" = xt_DSCP ] || [ "$module" = xt_HL ]; then
            remote iptables -t mangle -L INPUT -v -n -x \
                | awk '$1 ~ /^[0-9]+$/ && $1 > 0 { n++ } END { exit n > 0 ? 0 : 1 }'
        fi
        echo FUNCTIONAL_NETFILTER_PASS
        exit 0
        ;;
    *) exit 77 ;;
esac
