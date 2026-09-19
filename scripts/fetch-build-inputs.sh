#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cache_dir="${1:-$repo_root/.cache/sources}"
mkdir -p "$cache_dir"

buildroot_name="openwrt_18.x_tch_buildroot_based_custom.tar.xz"
toolchain_name="toolchain-arm_cortex-a9+neon_gcc-4.8-linaro_glibc_eabi.tar"
buildroot_url="${BUILDROOT_URL:-https://mega.nz/#!Mpd2lK6B!Wqu7kcpkgxU_oK8AKBsTJWJ2CVIg7idmV19k1_zkvX0}"
toolchain_url="${TOOLCHAIN_URL:-https://mega.nz/#!V98jBIZQ!KNSVwznEz9mwJG18bkJoY-pLzn_NSvlJRCwMubKLsLs}"
release_tag="${BUILD_INPUTS_TAG:-build-inputs-v1}"

download() {
  local url="$1"
  local destination="$2"
  local filename
  filename="$(basename "$destination")"

  if [[ -s "$destination" ]]; then
    return
  fi

  # Convenience for local development: archives downloaded next to the README
  # are used directly, but remain ignored by Git.
  if [[ -s "$repo_root/$filename" ]]; then
    cp "$repo_root/$filename" "$destination"
    return
  fi

  # CI normally obtains the immutable inputs from a technical Release in this
  # same repository. Mega is needed only to seed that Release (or as fallback).
  if [[ -n "${GITHUB_REPOSITORY:-}" ]] && command -v gh >/dev/null 2>&1; then
    if gh release download "$release_tag" \
      --repo "$GITHUB_REPOSITORY" \
      --pattern "$filename" \
      --dir "$cache_dir" >/dev/null 2>&1; then
      return
    fi
  fi

  local partial="${destination}.part"
  rm -f "$partial"

  if [[ "$url" == *"mega.nz/"* ]]; then
    if ! command -v megadl >/dev/null 2>&1; then
      echo "megadl is required to download the archived Mega links" >&2
      exit 1
    fi
    local temporary_dir
    temporary_dir="$(mktemp -d)"
    megadl --path "$temporary_dir" "$url"
    local downloaded
    downloaded="$(find "$temporary_dir" -maxdepth 1 -type f -print -quit)"
    if [[ -z "$downloaded" ]]; then
      echo "Mega download did not produce a file for $url" >&2
      rm -rf "$temporary_dir"
      exit 1
    fi
    mv "$downloaded" "$partial"
    rm -rf "$temporary_dir"
  else
    curl --fail --location --retry 5 --retry-all-errors --output "$partial" "$url"
  fi
  mv "$partial" "$destination"
}

download "$buildroot_url" "$cache_dir/$buildroot_name"
download "$toolchain_url" "$cache_dir/$toolchain_name"

(
  cd "$cache_dir"
  sha256sum --check "$repo_root/build/checksums.sha256"
)
