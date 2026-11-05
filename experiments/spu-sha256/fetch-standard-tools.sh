#!/usr/bin/env bash
set -euo pipefail
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cache=${1:?source cache directory}
mkdir -p "$cache"
while IFS=$'\t' read -r filename sha url; do
 if [[ ! -f "$cache/$filename" ]]; then
  curl --fail --location --retry 2 --connect-timeout 15 "$url" --output "$cache/$filename.tmp"
  mv "$cache/$filename.tmp" "$cache/$filename"
 fi
 echo "$sha  $cache/$filename" | sha256sum --check --status
done < "$here/standard-sources.tsv"
