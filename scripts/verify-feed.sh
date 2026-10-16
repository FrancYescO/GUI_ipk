#!/usr/bin/env bash
set -euo pipefail

feed_root="${1:-dist}"
allow_kmods=0
if [[ "${2:-}" == --allow-kmods ]]; then
  allow_kmods=1
elif [[ -n "${2:-}" ]]; then
  echo "Unsupported option: $2" >&2
  exit 1
fi
if [[ ! -d "$feed_root" ]]; then
  echo "Feed directory does not exist: $feed_root" >&2
  exit 1
fi

ipk_count="$(find "$feed_root" -type f -name '*.ipk' | wc -l | tr -d ' ')"
index_count=0

while IFS= read -r -d '' packages_file; do
  directory="$(dirname "$packages_file")"
  gzip -cd "$directory/Packages.gz" | cmp --silent - "$packages_file" || {
    echo "Packages.gz does not match $packages_file" >&2
    exit 1
  }

  while IFS= read -r filename; do
    [[ -z "$filename" ]] || [[ -f "$directory/$filename" ]] || {
      echo "Index references a missing package: $directory/$filename" >&2
      exit 1
    }
  done < <(sed -n 's/^Filename: //p' "$packages_file")

  index_count=$((index_count + 1))
done < <(find "$feed_root" -type f -name Packages -print0)

if [[ "$ipk_count" -eq 0 || "$index_count" -eq 0 ]]; then
  echo "Incomplete feed: $ipk_count packages, $index_count indexes" >&2
  exit 1
fi

if [[ "$allow_kmods" -eq 0 ]]; then
  unsafe_package="$(find "$feed_root" -type f \( -name 'kmod-*.ipk' -o -name 'kernel_*.ipk' \) -print -quit)"
  if [[ -n "$unsafe_package" ]]; then
    echo "Shared feed contains a kernel package: $unsafe_package" >&2
    exit 1
  fi

  if grep -R -l -E '^Package: (kmod-|kernel$)' "$feed_root" \
    --include=Packages --include=Packages.manifest | grep -q .; then
    echo "Shared feed index still advertises kernel packages" >&2
    exit 1
  fi

  python3 "$(dirname "${BASH_SOURCE[0]}")/check-userspace-payloads.py" "$feed_root"
fi

echo "Verified $ipk_count packages across $index_count feed indexes"
