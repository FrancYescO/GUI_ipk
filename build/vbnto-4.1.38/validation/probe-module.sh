#!/bin/sh
# Run from /tmp only. Never force removal or change boot/module configuration.
set -u
root=$1
name=$2
case "$name" in xt_nat) echo "Blocked: previous validation session crashed while starting xt_nat" >&2; exit 1 ;; esac
digest=$3
profile=${4:-namespace}
kernel_name=$(printf '%s' "$name" | tr '-' '_')
payload="$root/modules/$digest.ko"
case "$root" in /tmp/*) ;; *) echo 'Probe root must be under /tmp' >&2; exit 1 ;; esac
test "$(sha256sum "$payload" | awk '{print $1}')" = "$digest" || exit 1
state="$root/results/$name"
ns=kmod38-probe
initial_loaded=0
original=
replaced=0
candidate_loaded=0
owned_ns=0
load_rc=0
functional_rc=0
restore_rc=0
status=passed
level=load-unload
boot=$(cat /proc/sys/kernel/random/boot_id)
taint_before=$(cat /proc/sys/kernel/tainted)
mkdir -p "$state"

refs() {
    awk -v module="$kernel_name" '$1 == module { print $3 }' /proc/modules
}

restore() {
    if [ "$owned_ns" -eq 1 ]; then
        ip netns del "$ns" 2>/dev/null || true
        owned_ns=0
        sleep 1
    fi
    if [ "$candidate_loaded" -eq 1 ]; then
        printf 'STEP\t%s\tremove-candidate\n' "$name"
        removed=0
        for attempt in 1 2 3 4 5; do
            if rmmod "$kernel_name" >> "$state/cleanup.log" 2>&1; then
                candidate_loaded=0
                removed=1
                break
            fi
            sleep 1
        done
        [ "$removed" -eq 1 ] || return 1
    fi
    if [ "$replaced" -eq 1 ]; then
        printf 'STEP\t%s\trestore-original\n' "$name"
        set -- "$original"
        tab=$(printf '\t')
        while IFS="$tab" read -r key value; do
            [ -n "$key" ] || continue
            case "$value" in '<NULL>'|'(null)') continue ;; esac
            set -- "$@" "$key=$value"
        done < "$state/parameters.tsv"
        insmod "$@" >> "$state/cleanup.log" 2>&1 || return 1
        replaced=0
    fi
    return 0
}

finish() {
    trap - EXIT HUP INT TERM
    restore || restore_rc=1
    [ "$restore_rc" -eq 0 ] || status=restore_failed
    taint_after=$(cat /proc/sys/kernel/tainted)
    new_taint=$((taint_after & ~taint_before & ~12289))
    if [ "$new_taint" -ne 0 ]; then status=kernel_warning; fi
    dmesg > "$state/dmesg-after.txt"
    printf 'RESULT\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$name" "$digest" "$status" "$level" "$initial_loaded" \
        "$load_rc" "$functional_rc" "$restore_rc" "$boot" \
        | tee "$state/result.tsv"
    if [ "$restore_rc" -ne 0 ] || [ "$new_taint" -ne 0 ]; then exit 1; fi
    case "$status" in payload_mismatch|namespace_in_use|unexpected_module_name|interrupted) exit 1 ;; esac
    exit 0
}
trap finish EXIT
trap 'status=interrupted; finish' HUP INT TERM
printf 'BEGIN\t%s\t%s\t%s\n' "$name" "$digest" "$boot"
dmesg > "$state/dmesg-before.txt"
if [ "$kernel_name" = xt_nat ]; then status=blocked_known_crash; exit 0; fi
actual=$(sha256sum "$payload" | awk '{print $1}')
if [ "$actual" != "$digest" ]; then status=payload_mismatch; exit 1; fi
if ip netns list | grep -Eq "^$ns( |$)"; then status=namespace_in_use; exit 1; fi
before_refs=$(refs)
if [ -n "$before_refs" ]; then
    initial_loaded=1
    if [ "$before_refs" -ne 0 ]; then status=skip_busy; exit 0; fi
    for path in /lib/modules/4.1.38/*.ko; do
        base=$(basename "$path" .ko | tr '-' '_')
        if [ "$base" = "$kernel_name" ]; then original=$path; break; fi
    done
    if [ -z "$original" ]; then status=skip_original_missing; exit 0; fi
    : > "$state/parameters.tsv"
    for parameter in /sys/module/"$kernel_name"/parameters/*; do
        [ -f "$parameter" ] || continue
        printf '%s\t%s\n' "$(basename "$parameter")" "$(cat "$parameter")" \
            >> "$state/parameters.tsv"
    done
    sha256sum "$original" > "$state/original.sha256"
    replaced=1
    printf 'STEP\t%s\tremove-original\n' "$name"
    rmmod "$kernel_name" > "$state/remove-original.log" 2>&1 || {
        replaced=0
        status=skip_remove_busy
        exit 0
    }
    printf 'STEP\t%s\toriginal-removed\n' "$name"
fi
candidate_loaded=1
printf 'STEP\t%s\tload-candidate\n' "$name"
insmod "$payload" > "$state/load.log" 2>&1 || load_rc=$?
if [ "$load_rc" -ne 0 ]; then candidate_loaded=0; status=load_failed; exit 0; fi
if [ -z "$(refs)" ]; then status=unexpected_module_name; exit 1; fi
printf 'STEP\t%s\tcandidate-loaded\n' "$name"

if [ "$profile" != load-only ]; then
    printf 'STEP\t%s\tcreate-namespace\n' "$name"
    ip netns add "$ns" > "$state/functional.log" 2>&1 || functional_rc=$?
    if [ "$functional_rc" -eq 0 ]; then
        owned_ns=1
        ip -n "$ns" link set lo up >> "$state/functional.log" 2>&1 || functional_rc=$?
        ip netns exec "$ns" ping -c 1 -W 2 127.0.0.1 \
            >> "$state/functional.log" 2>&1 || functional_rc=$?
        level=load-unload-namespace
        if [ "$functional_rc" -eq 0 ] && [ -f "$root/functional.sh" ]; then
            printf 'STEP\t%s\texercise-namespace\n' "$name"
            exercise_rc=0
            timeout -t 20 sh "$root/functional.sh" "$ns" "$name" \
                >> "$state/functional.log" 2>&1 || exercise_rc=$?
            if [ "$exercise_rc" -eq 0 ]; then
                level=load-unload-functional
            elif [ "$exercise_rc" -ne 77 ]; then
                functional_rc=$exercise_rc
            fi
        fi
    fi
fi
if [ "$functional_rc" -ne 0 ]; then status=functional_failed; fi
exit 0
