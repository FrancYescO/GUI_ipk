#!/bin/sh
set -eu
cd /tmp/spu-sha256
server=
chain=0
if iptables -nL SPU2INPUT >/dev/null 2>&1; then exit 1; fi
cleanup() {
 result=$1
 trap - EXIT HUP INT TERM
 if [ -n "$server" ]; then kill "$server" 2>/dev/null || true; wait "$server" 2>/dev/null || true; fi
 if [ "$chain" -eq 1 ]; then
  iptables -D INPUT -s 192.168.133.100/32 -d 192.168.133.69/32 -p tcp --dport 26969 -j SPU2INPUT
  iptables -F SPU2INPUT
  iptables -X SPU2INPUT
 fi
 echo EXTERNAL_PLAIN_SERVER_CLEANUP
 exit "$result"
}
trap 'cleanup $?' EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
rm -f ./plain-stop
iptables -N SPU2INPUT; chain=1
iptables -A SPU2INPUT -j ACCEPT
iptables -I INPUT 1 -s 192.168.133.100/32 -d 192.168.133.69/32 -p tcp --dport 26969 -j SPU2INPUT
"${IPERF:-iperf3}" -s -B 192.168.133.69 -p 26969 > /tmp/spu-plain-server.log 2>&1 &
server=$!
sleep 1
kill -0 "$server"
echo EXTERNAL_PLAIN_SERVER_READY
for tick in $(seq 1 90); do
 if [ -f ./plain-stop ]; then exit 0; fi
 sleep 1
done
exit 124
