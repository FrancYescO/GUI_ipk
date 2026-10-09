#!/usr/bin/env bash
set -euo pipefail

feed_root="${1:-dist}"
mapfile -t packages < <(find "$feed_root" -type f -name 'kmod-sched-connmark_*.ipk' -print)
if [[ "${#packages[@]}" -ne 1 ]]; then
  echo "Expected exactly one kmod-sched-connmark package, found ${#packages[@]}" >&2
  exit 1
fi
package="${packages[0]}"
package_path="$(cd "$(dirname "$package")" && pwd)/$(basename "$package")"
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
  [[ -n "$data_archive" ]] || { echo "Missing data archive in $package" >&2; exit 1; }
  tar -xf "$data_archive"
)
module="$(find "$inspection_dir" -type f -name act_connmark.ko -print -quit)"
[[ -n "$module" ]] || { echo "Missing act_connmark.ko in $package" >&2; exit 1; }
readelf -h "$module" | grep -Eq 'Class:[[:space:]]+ELF32' || { echo 'Module is not ELF32' >&2; exit 1; }
readelf -h "$module" | grep -Eq 'Machine:[[:space:]]+ARM' || { echo 'Module is not ARM' >&2; exit 1; }
vermagic="$(strings "$module" | sed -n 's/^vermagic=//p' | head -n 1)"
[[ "$vermagic" == 4.1.38* ]] || { echo "Unexpected vermagic: ${vermagic:-missing}" >&2; exit 1; }
printf 'Verified %s: %s\n' "$package" "$vermagic"
