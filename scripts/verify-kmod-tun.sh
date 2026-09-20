#!/usr/bin/env bash
set -euo pipefail

feed_root="${1:-dist}"
work_dir="${2:-}"
expected_version="${3:-4.1.38}"

mapfile -t packages < <(find "$feed_root" -type f -name 'kmod-tun_*.ipk' -print)
if [[ "${#packages[@]}" -ne 1 ]]; then
  echo "Expected exactly one kmod-tun package, found ${#packages[@]}" >&2
  exit 1
fi

package="${packages[0]}"
if [[ "$package" = /* ]]; then
  package_path="$package"
else
  package_path="$(cd "$(dirname "$package")" && pwd)/$(basename "$package")"
fi
inspection_dir="$(mktemp -d)"
trap 'rm -rf "$inspection_dir"' EXIT

(
  cd "$inspection_dir"
  if ar t "$package_path" >/dev/null 2>&1; then
    ar x "$package_path"
  else
    # This legacy OpenWrt fork emits tar-based ipk files rather than the
    # Debian ar container used by current releases.
    tar -xf "$package_path"
  fi
  data_archive="$(find . -maxdepth 1 -type f -name 'data.tar.*' -print -quit)"
  if [[ -z "$data_archive" ]]; then
    echo "Package has no data archive: $package" >&2
    exit 1
  fi
  tar -xf "$data_archive"
)

module="$(find "$inspection_dir" -type f -name tun.ko -print -quit)"
if [[ -z "$module" ]]; then
  echo "Package does not contain tun.ko: $package" >&2
  exit 1
fi

elf_header="$(readelf -h "$module")"
grep -Eq 'Class:[[:space:]]+ELF32' <<<"$elf_header" || {
  echo "tun.ko is not ELF32" >&2
  exit 1
}
grep -Eq 'Machine:[[:space:]]+ARM' <<<"$elf_header" || {
  echo "tun.ko is not an ARM module" >&2
  exit 1
}

vermagic="$(strings "$module" | sed -n 's/^vermagic=//p' | head -n 1)"
if [[ "$vermagic" != "$expected_version"* ]]; then
  echo "Unexpected tun.ko vermagic: ${vermagic:-missing}" >&2
  exit 1
fi

symbol_table="$(readelf --symbols --wide "$module")"
if [[ "$expected_version" == 4.1.38 ]] && \
    grep -q ' UND .*dev_get_valid_name$' <<<"$symbol_table"; then
  echo "tun.ko unexpectedly depends on unexported dev_get_valid_name" >&2
  exit 1
fi

if [[ -n "$work_dir" ]]; then
  source_file="$(find "$work_dir/build_dir" -path "*/linux-$expected_version/drivers/net/tun.c" -print -quit)"
  if [[ -z "$source_file" ]]; then
    echo "Could not find the patched tun.c in $work_dir" >&2
    exit 1
  fi
  grep -Fq 'u8 ip_version = skb->len ? (skb->data[0] >> 4) : 0;' "$source_file"
  grep -Fq 'if (sndbuf <= 0)' "$source_file"
  if grep -q ' UND .*dev_get_valid_name$' <<<"$symbol_table"; then
    grep -Fq 'EXPORT_SYMBOL(dev_get_valid_name);' \
      "$(dirname "$source_file")/../../net/core/dev.c"
  fi
fi

manifest="$feed_root/kmod-tun-inspection.txt"
{
  echo "package=$package"
  echo "kernel_version=$expected_version"
  echo "sha256=$(sha256sum "$package" | awk '{print $1}')"
  echo "module=$(realpath --relative-to="$inspection_dir" "$module")"
  echo "file=$(file -b "$module")"
  echo "vermagic=$vermagic"
  echo "undefined_symbols:"
  awk '$7 == "UND" && $8 != "" { print $8 }' <<<"$symbol_table" \
    | sort -u \
    | sed 's/^/  /'
} > "$manifest"

echo "Verified patched kmod-tun: $package"
cat "$manifest"
