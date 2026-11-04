#!/bin/sh
# Run only on the verified 4.1.52 VBNT-K ABI with SPU initially unloaded.
set -eu
directory=${1:?directory containing the three verified lab modules}
mode=${2:?mode 0..4}
case "$mode" in 0|1|2|3|4) ;; *) exit 2 ;; esac
test "$(uname -r)" = 4.1.52
opkg status kernel | grep -q 'f4e97ee0656c3a247868bb0a3f9c7e55'
test ! -d /sys/module/bcmspu
test ! -d /sys/module/spu_cbc_probe
test ! -d /sys/module/spu_cbc_kat
test ! -d /sys/module/spu_cbc_lab
test ! -d /sys/module/vbntj_abi_canary
echo "MODE=$mode"
cat /proc/sys/kernel/random/boot_id
cleanup() {
    for module in spu_cbc_kat spu_cbc_lab; do
        if test -d "/sys/module/$module"; then
            if test "$(cat "/sys/module/$module/refcnt")" != 0; then
                echo "PENDING/BUSY: preserving $module and SPU; no stop/unload permitted"
                return 1
            fi
            rmmod "$module" || return 1
        fi
    done
    if test -d /sys/module/spu_cbc_probe; then
        if test "$(cat /sys/module/spu_cbc_probe/refcnt)" != 0; then
            echo 'PENDING: preserving probe and SPU; no stop/unload permitted'
            return 1
        fi
        rmmod spu_cbc_probe || return 1
    fi
    if test -d /sys/module/bcmspu; then
        if test "$(cat /sys/module/bcmspu/refcnt)" != 0; then
            echo 'BUSY: preserving SPU'
            return 1
        fi
        spuctl stop || return 1
        rmmod bcmspu || return 1
    fi
    echo CLEANUP_OK
    cat /proc/sys/kernel/random/boot_id
}
insmod "$directory/vbntj_abi_canary.ko"
rmmod vbntj_abi_canary
insmod "$directory/bcmspu.ko" blog_offload=N lab_mode="$mode"
trap cleanup EXIT
spuctl start
cat /sys/module/bcmspu/parameters/lab_mode
# Abort if any production name was accidentally registered by the prototype.
awk 'BEGIN { RS=""; failed=0; count=0 }
 /module[[:space:]]*:[[:space:]]*bcmspu/ {
   count++
   if ($0 !~ /name[[:space:]]*:[[:space:]]*lab-/) failed=1
 }
 END { if (!count || failed) exit 1; print "PRIVATE_ALGORITHMS=" count }' /proc/crypto
if test -n "${CBC_KAT_MAX:-}"; then
    case "$mode" in 2|4) ;; *) exit 2 ;; esac
    insmod "$directory/spu_cbc_lab.ko"
    insmod "$directory/spu_cbc_kat.ko" max_len="$CBC_KAT_MAX"
    dmesg | grep 'spu_cbc_kat:' | tail -45
else
    if test "$mode" = 4; then
        insmod "$directory/spu_cbc_probe.ko" downstream_encrypt=1
    else
        insmod "$directory/spu_cbc_probe.ko"
    fi
    dmesg | grep 'spu_cbc_probe:' | tail -4
fi
spuctl showstats
if test -d /sys/module/spu_cbc_lab; then
    echo CBC_ENCRYPT_CHUNKS
    cat /sys/module/spu_cbc_lab/parameters/enc_chunks
    echo CBC_DECRYPT_CHUNKS
    cat /sys/module/spu_cbc_lab/parameters/dec_chunks
fi
