#!/bin/sh
# Temporary .69 test; stock cryptodev is never used by the test processes.
set -eu
d=${1:?verified lab module and session-test directory}
mode=${2:-4}
hash=${3:-generic}
case "$hash" in generic|arm) ;; *) exit 2 ;; esac
case "$mode" in
  2) expected=spu-cbc-ecb-lab ;;
  4) expected=spu-cbc-native-lab ;;
  *) exit 2 ;;
esac
echo MODE="$mode"
export PATH="$d/apps/usr/bin:$d/apps/usr/sbin:$PATH"
export LD_LIBRARY_PATH="$d/apps/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
test "$(uname -r)" = 4.1.52
opkg status kernel | grep -q f4e97ee0656c3a247868bb0a3f9c7e55
test ! -d /sys/module/bcmspu
test ! -d /sys/module/spu_cbc_lab
test ! -d /sys/module/cryptodev_cbc_lab
test ! -d /sys/module/sha1_spu_cbc_lab
test ! -d /sys/module/spu_sha1_kat
test ! -e /dev/crypto-cbc-lab
node=/dev/crypto-cbc-lab
stock_node=$(cat /sys/class/misc/crypto/dev)
load_bridge() {
    insmod "$d/cryptodev_cbc_lab.ko" cbc_driver="$1"
    if test ! -c "$node"; then
        dev=$(cat /sys/class/misc/crypto-cbc-lab/dev)
        mknod "$node" c "${dev%:*}" "${dev#*:}"
    fi
    chmod 600 "$node"
    test "$(cat /sys/class/misc/crypto-cbc-lab/dev)" != "$stock_node"
}
unload_bridge() {
    if test -d /sys/module/cryptodev_cbc_lab; then
        test "$(cat /sys/module/cryptodev_cbc_lab/refcnt)" = 0 || return 1
        rmmod cryptodev_cbc_lab || return 1
        rm -f "$node"
    fi
}
cleanup() {
    unload_bridge || { echo 'BUSY/PENDING bridge; preserving dependent modules'; return 1; }
    for module in spu_sha1_kat spu_cbc_lab sha1_spu_cbc_lab bcmspu; do
        if test -d "/sys/module/$module"; then
            if test "$(cat "/sys/module/$module/refcnt")" != 0; then
                echo "BUSY/PENDING: preserving $module; no force/unload"
                return 1
            fi
            if test "$module" = bcmspu; then spuctl stop || return 1; fi
            rmmod "$module" || return 1
        fi
    done
    test "$(cat /sys/class/misc/crypto/dev)" = "$stock_node"
    echo CLEANUP_OK
    cat /proc/sys/kernel/random/boot_id
}
trap cleanup EXIT
load_bridge 'cbc(aes-generic)'
echo SOFTWARE_BEFORE
"$d/session-test" "$node" --bench
unload_bridge
insmod "$d/vbntj_abi_canary.ko"
rmmod vbntj_abi_canary
insmod "$d/bcmspu.ko" blog_offload=N lab_mode="$mode"
spuctl start
if test "$hash" = arm; then
    insmod "$d/sha1_spu_cbc_lab.ko"
    insmod "$d/spu_sha1_kat.ko"
    dmesg | grep 'spu_sha1_kat:' | tail -1
    rmmod spu_sha1_kat
    insmod "$d/spu_cbc_lab.ko" 'hash_driver=hmac(sha1-spu-cbc-lab-arm)'
else
    insmod "$d/spu_cbc_lab.ko"
fi
echo FRAMING_HASH
cat /sys/module/spu_cbc_lab/parameters/hash_driver
load_bridge spu-cbc-lab
echo HARDWARE_SESSION
"$d/session-test" "$node" --bench > "$d/hardware-session.log" 2>&1 || {
    cat "$d/hardware-session.log"; exit 1;
}
cat "$d/hardware-session.log"
grep -q "cipher=$expected" "$d/hardware-session.log"
spuctl showstats
echo CBC_ENCRYPT_CHUNKS
cat /sys/module/spu_cbc_lab/parameters/enc_chunks
echo CBC_DECRYPT_CHUNKS
cat /sys/module/spu_cbc_lab/parameters/dec_chunks
echo OPENSSL_EVP_ENGINE
LD_PRELOAD="$d/redirect-crypto.so" "$d/evp-test"
spuctl showstats
echo CBC_ENCRYPT_CHUNKS
cat /sys/module/spu_cbc_lab/parameters/enc_chunks
echo CBC_DECRYPT_CHUNKS
cat /sys/module/spu_cbc_lab/parameters/dec_chunks
if test "${CBC_OPENVPN:-0}" = 1; then
    sh "$d/openvpn-test.sh" "$d" "${CBC_OPENVPN_BITS:-128}"
fi
cleanup
load_bridge 'cbc(aes-generic)'
echo SOFTWARE_AFTER
"$d/session-test" "$node" --bench
