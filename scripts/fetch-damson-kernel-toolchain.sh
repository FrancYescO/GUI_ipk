#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cache_dir="${1:-$repo_root/.cache/sources/damson-kernel-toolchain}"
archive=damson-kernel-gcc-5.5.0-linux-amd64.tgz
mkdir -p "$cache_dir"
if [[ ! -f "$cache_dir/$archive" ]]; then
  gh release download damson-kernel-toolchain-gcc5.5-v1 \
    --repo "${GITHUB_REPOSITORY:-FrancYescO/GUI_ipk}" \
    --pattern "$archive" --dir "$cache_dir"
fi
(cd "$cache_dir" && sha256sum --check "$repo_root/build/vbntj/kernel-toolchain-seed.sha256")
