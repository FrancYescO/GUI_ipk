#!/usr/bin/env bash
set -euo pipefail

kernel_dir="$1"
cross="$2"
output_dir="$3"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$output_dir"
cp "$kernel_dir/.config" "$output_dir/tested.config"

# Preserve every existing built-in/module setting; add only optional modules.
for option in IFB NET_ACT_CONNMARK NET_ACT_SKBEDIT NET_SCH_FQ_CODEL \
  NET_SCH_HFSC NET_SCH_HTB NET_SCH_INGRESS NET_CLS_U32; do
  if ! grep -Eq "^CONFIG_${option}=[ym]$" "$kernel_dir/.config"; then
    "$kernel_dir/scripts/config" --file "$kernel_dir/.config" --module "$option"
  fi
done
kernel_make=(make -C "$kernel_dir" ARCH=arm CROSS_COMPILE="$cross")
"${kernel_make[@]}" olddefconfig
cp "$kernel_dir/.config" "$output_dir/build.config"
python3 - "$output_dir/tested.config" "$output_dir/build.config" <<'PY'
import sys
def enabled(path):
    result = {}
    for line in open(path):
        if line.startswith('CONFIG_') and '=' in line:
            name, value = line.strip().split('=', 1)
            if value in ('y', 'm'):
                result[name] = value
    return result
before, after = [enabled(path) for path in sys.argv[1:]]
changed = [name for name, value in before.items() if after.get(name) != value]
if changed:
    raise SystemExit('Existing firmware options changed: ' + ', '.join(changed))
PY
"${kernel_make[@]}" modules_prepare

priority_targets=(
  net/netfilter/nf_conntrack.ko
  net/ipv4/netfilter/nf_conntrack_ipv4.ko
  net/ipv6/netfilter/nf_conntrack_ipv6.ko
  net/netfilter/nf_conntrack_netlink.ko
  net/netfilter/nf_conntrack_rtcache.ko
  net/netfilter/xt_conntrack.ko
  net/netfilter/xt_connmark.ko
  net/sched/act_connmark.ko
  net/ipv4/udp_tunnel.ko
  net/ipv6/ip6_udp_tunnel.ko
)
printf '%s\n' "${priority_targets[@]}" > "$output_dir/priority-targets.txt"
priority_rc=0
"${kernel_make[@]}" -k -j"${JOBS:-2}" "${priority_targets[@]}" \
  > "$output_dir/priority-build.log" 2>&1 || priority_rc=$?

wg_dir="$kernel_dir/../wireguard-linux-compat"
mkdir -p "$wg_dir"
curl --fail --location --retry 3 \
  https://git.zx2c4.com/wireguard-linux-compat/snapshot/wireguard-linux-compat-1.0.20220627.tar.xz \
  -o "$output_dir/wireguard-linux-compat-1.0.20220627.tar.xz"
printf '%s  %s\n' \
  19b181e5c7d2260c23ecad4ad324425fd8e88200d97a885a2c7d4bd26cd61461 \
  "$output_dir/wireguard-linux-compat-1.0.20220627.tar.xz" | sha256sum --check
tar -xJf "$output_dir/wireguard-linux-compat-1.0.20220627.tar.xz" \
  -C "$wg_dir" --strip-components=1
patch --batch --forward -d "$wg_dir" -p1 \
  < "$repo_root/patches/wireguard-linux-compat/001-define-fallthrough-for-old-kernels.patch"
wireguard_rc=0
"${kernel_make[@]}" -j"${JOBS:-2}" M="$wg_dir/src" modules \
  > "$output_dir/wireguard-build.log" 2>&1 || wireguard_rc=$?

# Continue through unavailable vendor drivers and retain every successful module.
full_rc=0
"${kernel_make[@]}" -k -j"${JOBS:-2}" modules \
  > "$output_dir/full-build.log" 2>&1 || full_rc=$?

mkdir -p "$output_dir/modules"
while IFS= read -r -d '' module; do
  relative="${module#"$kernel_dir/"}"
  mkdir -p "$output_dir/modules/$(dirname "$relative")"
  cp "$module" "$output_dir/modules/$relative"
done < <(find "$kernel_dir" -type f -name '*.ko' -print0)
if [[ -f "$wg_dir/src/wireguard.ko" ]]; then
  cp "$wg_dir/src/wireguard.ko" "$output_dir/modules/wireguard.ko"
fi
export CROSS_COMPILE="$cross"
python3 "$repo_root/scripts/report-expanded-kmods.py" "$output_dir" \
  --priority-exit "$priority_rc" --wireguard-exit "$wireguard_rc" --full-exit "$full_rc"
test -f "$output_dir/modules/wireguard.ko"
while IFS= read -r target; do
  test -f "$output_dir/modules/$target" || {
    echo "Missing priority module: $target" >&2
    exit 1
  }
done < "$output_dir/priority-targets.txt"
