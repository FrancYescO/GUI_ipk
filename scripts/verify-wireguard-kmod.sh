#!/usr/bin/env bash
set -euo pipefail

feed_root="${1:-dist}"
kernel_version="${2:-4.1.38}"
case "$kernel_version" in
  4.1.38|4.1.52) ;;
  *) echo "Unsupported WireGuard kernel: $kernel_version" >&2; exit 1 ;;
esac

mapfile -t packages < <(find "$feed_root" -type f -name 'kmod-wireguard*.ipk' -print)
[[ ${#packages[@]} -eq 1 ]] || {
  echo "Expected one WireGuard IPK, found ${#packages[@]}" >&2; exit 1
}
package_path="$(cd "$(dirname "${packages[0]}")" && pwd)/$(basename "${packages[0]}")"
inspection_dir="$(mktemp -d)"
trap 'rm -rf "$inspection_dir"' EXIT
(
  cd "$inspection_dir"
  if ar t "$package_path" >/dev/null 2>&1; then
    ar x "$package_path"
  else
    tar -xf "$package_path"
  fi
  data_archive="$(find . -maxdepth 1 -type f -name 'data.tar.*' -print -quit)"
  [[ -n "$data_archive" ]] || { echo 'Missing module data archive' >&2; exit 1; }
  tar -xf "$data_archive"
)
module="$inspection_dir/lib/modules/$kernel_version/wireguard.ko"
[[ -f "$module" ]] || { echo "Missing $kernel_version/wireguard.ko" >&2; exit 1; }
readelf -h "$module" | grep -Eq 'Class:[[:space:]]+ELF32'
readelf -h "$module" | grep -Eq 'Machine:[[:space:]]+ARM'
vermagic="$(strings "$module" | sed -n 's/^vermagic=//p' | head -n 1)"
[[ "$vermagic" == "$kernel_version SMP preempt mod_unload ARMv7" ]] || {
  echo "Unexpected WireGuard vermagic: ${vermagic:-missing}" >&2; exit 1
}
dependencies="$(strings "$module" | sed -n 's/^depends=//p' | head -n 1)"
for dependency in udp_tunnel ip6_udp_tunnel; do
  case ",$dependencies," in
    *",$dependency,"*) ;;
    *) echo "Missing WireGuard module dependency: $dependency" >&2; exit 1 ;;
  esac
done
printf 'Verified WireGuard ARM package: %s; dependencies: %s\n' "$vermagic" "$dependencies"
