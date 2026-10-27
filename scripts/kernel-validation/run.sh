#!/bin/sh
set -eu
root=$(cd "$(dirname "$0")" && pwd)
export PATH="$root/bin:$PATH"
export LD_LIBRARY_PATH="$root/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
[ "$(uname -r)" = 4.1.38 ]
installed=$(opkg status kernel | sed -n 's/^Version: //p')
[ "$installed" = "$(cat "$root/kernel-package")" ]
[ ! -e /tmp/kv38maps ] || { echo 'Temporary map directory already exists' >&2; exit 1; }
mkdir -m 700 /tmp/kv38maps
cp "$root/ematch_map" /tmp/kv38maps/ematch_map
cleanup() {
    if [ "${owned_basic:-0}" -eq 1 ]; then rmmod cls_basic || return 1; fi
    rm -f /tmp/kv38maps/ematch_map
    rmdir /tmp/kv38maps
}
trap 'cleanup || exit 1' EXIT
case "${1:-all}" in pilot) plan="$root/pilot.tsv";; all) plan="$root/plan.tsv";; *) exit 2;; esac
while IFS="$(printf '\t')" read -r name digest profile; do
    [ "$(cat /proc/sys/kernel/random/boot_id)" = "$(cat "$root/boot-id")" ]
    owned_basic=0
    if [ "$name" = em_u32 ] && [ -f "$root/support/cls_basic.ko" ] && ! grep -q '^cls_basic ' /proc/modules; then
        (cd "$root/support" && sha256sum -c SHA256SUMS)
        insmod "$root/support/cls_basic.ko"
        owned_basic=1
    fi
    probe_rc=0
    sh "$root/probe.sh" "$root" "$name" "$digest" "$profile" || probe_rc=$?
    if [ "$owned_basic" -eq 1 ]; then
        rmmod cls_basic
        owned_basic=0
    fi
    [ "$probe_rc" -eq 0 ] || exit "$probe_rc"
done < "$plan"
echo BATCH_COMPLETE
