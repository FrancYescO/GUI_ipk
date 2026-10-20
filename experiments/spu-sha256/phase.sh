#!/bin/sh
set -eu
cd /tmp/spu-sha256
for mod in bcmspu spu_sha256_hybrid aes_arm sha256_arm damson_spu_test; do
 if grep -q "^$mod " /proc/modules; then echo "Refusing: $mod already loaded"; exit 1; fi
done
if ip netns list | grep -Eq '^spu-check-[ab]( |$)'; then echo 'Refusing existing namespaces'; exit 1; fi
if [ -n "$(ip xfrm state)" ] || [ -n "$(ip xfrm policy)" ]; then
 echo 'Refusing: active root-namespace IPsec configuration'
 exit 1
fi
cleanup() {
 ip netns del spu-check-a 2>/dev/null || true
 ip netns del spu-check-b 2>/dev/null || true
 sleep 3
 if grep -q '^spu_sha256_hybrid ' /proc/modules; then rmmod spu_sha256_hybrid || return; fi
 if grep -q '^bcmspu ' /proc/modules; then if ! spuctl stop; then sleep 3; spuctl stop || return 1; fi; rmmod bcmspu || return 1; fi
 if grep -q '^aes_arm ' /proc/modules; then rmmod aes_arm || return; fi
 if grep -q '^sha256_arm ' /proc/modules; then rmmod sha256_arm || return; fi
}
on_exit() {
 result=$1
 trap - EXIT HUP INT TERM
 cleanup || result=1
 if [ "$result" -eq 0 ]; then echo "PHASE_PASS $PHASE"; fi
 exit "$result"
}
trap 'on_exit $?' EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
case "${PHASE:?}" in
 stable_fallback) insmod ./bcmspu.ko; spuctl start ;;
 plain_generic) : ;;
 sha256_asm) insmod ./sha256-arm.ko ;;
 aes_asm) insmod ./aes-arm.ko ;;
 both_asm) insmod ./aes-arm.ko; insmod ./sha256-arm.ko ;;
 fallback_asm) insmod ./aes-arm.ko; insmod ./sha256-arm.ko; insmod ./bcmspu.ko; spuctl start ;;
 hybrid_generic) insmod ./bcmspu.ko; spuctl start; insmod ./spu_sha256_hybrid.ko in_place=0 ;;
 hybrid_inplace) insmod ./bcmspu.ko; spuctl start; insmod ./spu_sha256_hybrid.ko in_place=1 ;;
 hybrid_inplace_rekey) insmod ./sha256-arm.ko; insmod ./bcmspu.ko; spuctl start; insmod ./spu_sha256_hybrid.ko in_place=1 'sha256_driver=hmac(sha256-asm)' ;;
 hybrid_inplace_asm) insmod ./sha256-arm.ko; insmod ./bcmspu.ko; spuctl start; insmod ./spu_sha256_hybrid.ko in_place=1 'sha256_driver=hmac(sha256-asm)' ;;
 hybrid_sha1_generic) insmod ./bcmspu.ko; spuctl start; insmod ./spu_sha256_hybrid.ko in_place=0 private_sha1=1 ;;
 hybrid_sha1_asm) insmod ./sha256-arm.ko; insmod ./bcmspu.ko; spuctl start; insmod ./spu_sha256_hybrid.ko in_place=0 private_sha1=1 'sha256_driver=hmac(sha256-asm)' ;;
 hybrid_asm) insmod ./sha256-arm.ko; insmod ./bcmspu.ko; spuctl start; insmod ./spu_sha256_hybrid.ko in_place=0 'sha256_driver=hmac(sha256-asm)' ;;
 *) echo Unknown phase; exit 1 ;;
esac
export PHASE
if [ "$PHASE" = hybrid_inplace_rekey ]; then
 sh ./rekey-udp.sh
else
 sh ./benchmark.sh
fi
echo "TRAFFIC_PASS $PHASE"
