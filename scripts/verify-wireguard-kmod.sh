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
# Kernel modinfo conventionally terminates vermagic with a space.
vermagic="$(strings "$module" | sed -n 's/^vermagic=//p' | head -n 1 | sed 's/[[:space:]]*$//')"
[[ "$vermagic" == "$kernel_version SMP preempt mod_unload ARMv7" ]] || {
  echo "Unexpected WireGuard vermagic: ${vermagic:-missing}" >&2; exit 1
}
dependencies="$(strings "$module" | sed -n 's/^depends=//p' | head -n 1)"
if [[ -z "$dependencies" && "$kernel_version" == 4.1.52 &&
      "$(basename "$package_path")" == kmod-wireguard-damson-4.1.52-manual_* ]]; then
  # The standalone Damson build does not have a full kernel Module.symvers.
  # Its manual-only package requires the stock UDP modules to be loaded first.
  # Accept this case only after validating the package guards and actual
  # undefined UDP symbols; normal packages still require depends metadata.
  "$(dirname "$0")/verify-manual-kmod-ipks.sh" "$feed_root"
  undefined_symbols="$(readelf --wide --symbols "$module" | awk 'NF >= 8 && $(NF-1) == "UND" {print $NF}')"
  for symbol in udp_sock_create4 udp_sock_create6 setup_udp_tunnel_sock \
    udp_tunnel_sock_release udp_tunnel_xmit_skb udp_tunnel6_xmit_skb; do
    grep -Fxq "$symbol" <<< "$undefined_symbols" || {
      echo "Missing required WireGuard UDP symbol: $symbol" >&2; exit 1
    }
  done
  printf 'Verified WireGuard ARM manual package: %s; requires stock udp_tunnel and ip6_udp_tunnel already loaded (depends metadata unavailable)\n' "$vermagic"
  exit 0
fi
for dependency in udp_tunnel ip6_udp_tunnel; do
  case ",$dependencies," in
    *",$dependency,"*) ;;
    *) echo "Missing WireGuard module dependency: $dependency" >&2; exit 1 ;;
  esac
done
printf 'Verified WireGuard ARM package: %s; dependencies: %s\n' "$vermagic" "$dependencies"
