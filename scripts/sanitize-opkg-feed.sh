#!/usr/bin/env bash
set -euo pipefail

feed_root="${1:-dist}"
if [[ ! -d "$feed_root" ]]; then
  echo "Feed directory does not exist: $feed_root" >&2
  exit 1
fi

# Kernel packages are tied to an exact vendor tree, configuration and ABI.
# Never expose them through the shared userspace feed: even a matching uname
# and vermagic are insufficient to make automatic OPKG installation safe.
find "$feed_root" -type f -name 'kmod-*.ipk' -delete

filter_index() {
  local index="$1"
  local filtered="${index}.safe"

  awk '
    BEGIN { RS = ""; ORS = "\n\n" }
    $0 !~ /(^|\n)Package: kmod-[^\n]*/ { print }
  ' "$index" > "$filtered"
  mv "$filtered" "$index"
}

while IFS= read -r -d '' packages_file; do
  directory="$(dirname "$packages_file")"
  filter_index "$packages_file"
  if [[ -f "$directory/Packages.manifest" ]]; then
    filter_index "$directory/Packages.manifest"
  fi
  gzip -9n -c "$packages_file" > "$directory/Packages.gz"
  rm -f "$directory/Packages.sig"
done < <(find "$feed_root" -type f -name Packages -print0)

echo "Removed kernel-module packages from shared OPKG feed: $feed_root"
