#!/usr/bin/env bash
# Build the exact unpatched 2017 package manager used by the tested firmware.
set -euo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work="${1:?fresh build directory}"
mkdir -p "$work/source" "$work/install"
inputs="$repo/artifacts/opkg-provider-test-sources"
echo "38e8996e1776b3ce10897ee4fb6afc60910b399ddd53e718e72f3308633bca3f  $inputs/opkg-4bd8601.tar.gz" | sha256sum -c -
echo "cc059c5d48dd24182a917c758ca2e6710db17d3a5c2cc7474f1cb40ce5b40c72  $inputs/libubox-fd57eea.tar.gz" | sha256sum -c -
tar -xzf "$inputs/opkg-4bd8601.tar.gz" -C "$work/source"
tar -xzf "$inputs/libubox-fd57eea.tar.gz" -C "$work/source"
cmake -S "$work/source/libubox-fd57eea9f37e447814afbf934db626288aac23c4" -B "$work/ubox-build" \
  -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DCMAKE_C_FLAGS="-U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0 -Wno-error=array-bounds" -DBUILD_LUA=OFF -DBUILD_EXAMPLES=OFF -DCMAKE_INSTALL_PREFIX="$work/install"
cmake --build "$work/ubox-build" --parallel 2
cmake --install "$work/ubox-build"
cmake -S "$work/source/opkg-lede-4bd8601ebd95c130e504cc724b0c5eb163050982" -B "$work/opkg-build" \
  -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DCMAKE_PREFIX_PATH="$work/install" \
  -DCMAKE_C_FLAGS="-I$work/install/include -fcommon -D_GNU_SOURCE" \
  -DCMAKE_EXE_LINKER_FLAGS="-L$work/install/lib -Wl,-rpath,$work/install/lib" \
  -DBUILD_TESTS=OFF -DENABLE_USIGN=OFF -DVERSION=4bd8601-2017-07-28
cmake --build "$work/opkg-build" --parallel 2
"$work/opkg-build/src/opkg-cl" --version
