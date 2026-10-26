#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work_dir="${1:?Usage: apply-userspace-overlay.sh BUILDROOT}"
overlay="$repo_root/build/userspace-overlay"
openvpn="$work_dir/package/network/services/openvpn"
[[ -f "$openvpn/Makefile" ]] || { echo "Missing archived OpenVPN recipe" >&2; exit 1; }
# 2.4 patches target removed APIs and the old bundled LZ4 implementation.
rm -rf "$openvpn/patches"
cp "$overlay/openvpn/Makefile" "$overlay/openvpn/Config-"*.in "$openvpn/"
cp -R "$overlay/openvpn/patches" "$openvpn/"
cp "$overlay/openvpn/openvpn.options" "$openvpn/files/openvpn.options"
mkdir -p "$work_dir/package/libs/libcap-ng"
cp "$overlay/libcap-ng/Makefile" "$work_dir/package/libs/libcap-ng/Makefile"
