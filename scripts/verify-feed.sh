#!/usr/bin/env bash
set -euo pipefail

feed_root="${1:-dist}"
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

echo "Verified $ipk_count packages across $index_count feed indexes"
