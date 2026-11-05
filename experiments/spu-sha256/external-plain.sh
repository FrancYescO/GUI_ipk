#!/bin/sh
set -eu
cd /tmp/spu-sha256
. ./external-common.sh
EXTERNAL_PLAIN=1
external_preflight
cleanup() {
 result=$1
 trap - EXIT HUP INT TERM
 external_cleanup || result=1
 if [ "$result" -eq 0 ]; then echo EXTERNAL_PLAIN_PASS; fi
 exit "$result"
}
trap 'cleanup $?' EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
external_setup
for direction in forward reverse; do
 echo "EXTERNAL_PLAIN_BENCH $direction"
 reverse=
 if [ "$direction" = reverse ]; then reverse=-R; fi
 timeout -s INT 20 ip netns exec "$a" "${IPERF:-iperf3}" -c "$peer" -B 198.18.69.1 -p 26969 -t 5 $reverse -J
done
