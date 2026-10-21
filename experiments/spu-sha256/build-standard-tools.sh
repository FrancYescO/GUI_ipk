#!/usr/bin/env bash
# Optional raw laboratory artifacts. Never called for stable package profiles.
set -euo pipefail
kernel=${1:?prepared matching kernel}
cross=${2:?cross compiler prefix}
cache=${3:?verified source cache}
out=${4:?output directory}
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
while IFS=$'\t' read -r filename sha _url; do
 echo "$sha  $cache/$filename" | sha256sum --check --status
done < "$here/standard-sources.tsv"
work=$(mktemp -d /tmp/spu-standard.XXXXXX)
trap 'rm -rf -- "$work"' EXIT
mkdir -p "$out"
tar -C "$work" -xzf "$cache/musl-1.2.5.tar.gz"
(
 cd "$work/musl-1.2.5"
 CC="${cross}gcc" CROSS_COMPILE="$cross" CFLAGS='-Os -march=armv7-a -mfloat-abi=soft' ./configure --prefix="$work/musl" --target=arm-linux-musleabi --disable-shared
 make -j4
 make install
)
make -C "$kernel" ARCH=arm headers_install INSTALL_HDR_PATH="$work/musl"
sh "$work/musl-1.2.5/tools/musl-gcc.specs.sh" "$work/musl/include" "$work/musl/lib" /lib/ld-musl-arm.so.1 > "$work/musl/lib/musl-gcc.specs"
printf '#!/bin/sh\nexec "%s" "$@" -specs="%s"\n' "${cross}gcc" "$work/musl/lib/musl-gcc.specs" > "$work/musl-gcc"
chmod +x "$work/musl-gcc"
tar -C "$work" -xJf "$cache/wireguard-tools-1.0.20210914.tar.xz"
make -C "$work/wireguard-tools-1.0.20210914/src" CC="$work/musl-gcc" CFLAGS='-Os -march=armv7-a -mfloat-abi=soft' LDFLAGS=-static WITH_BASHCOMPLETION=no WITH_WGQUICK=no -j4
cp "$work/wireguard-tools-1.0.20210914/src/wg" "$out/wg"
tar -C "$work" -xzf "$cache/iperf-3.18.tar.gz"
(
 cd "$work/iperf-3.18"
 # Legacy Linux headers lack musl's IPv6 flow-label compatibility definitions.
 # IPv4 TCP/UDP remains upstream; no vendor hardware speed-test hooks are used.
 iperf3_cv_header_flowlabel=no CC="$work/musl-gcc" CFLAGS='-Os -march=armv7-a -mfloat-abi=soft' LDFLAGS=-static ./configure --host=arm-linux-musleabi --disable-shared --enable-static --without-openssl
 make -j4
)
cp "$work/iperf-3.18/src/iperf3" "$out/iperf3-lab"
"$work/musl-gcc" -static -Os -march=armv7-a -mfloat-abi=soft -Wall -Wextra -Werror "$here/udp-encap.c" -o "$out/udp-encap"
"$work/musl-gcc" -static -Os -march=armv7-a -mfloat-abi=soft -Wall -Wextra -Werror "$here/veth-offloads.c" -o "$out/veth-offloads"
for binary in wg iperf3-lab udp-encap veth-offloads; do
 "${cross}strip" "$out/$binary"
 "${cross}readelf" -h "$out/$binary" | grep -Eq 'Machine:[[:space:]]+ARM'
 if "${cross}readelf" -l "$out/$binary" | grep -q INTERP; then
  echo "Unexpected runtime loader dependency: $binary" >&2; exit 1
 fi
done
for option in GCM GHASH GF128MUL CTR SEQIV; do
 grep -qx "CONFIG_CRYPTO_$option=m" "$kernel/.config"
done
make -C "$kernel" ARCH=arm CROSS_COMPILE="$cross" crypto/gcm.ko crypto/ghash-generic.ko crypto/gf128mul.ko crypto/ctr.ko crypto/seqiv.ko
for module in gcm ghash-generic gf128mul ctr seqiv; do
 cp "$kernel/crypto/$module.ko" "$out/"
 "${cross}strip" --strip-debug "$out/$module.ko"
done
cp "$cache/wireguard.ko" "$out/"
cp "$here/standard-sources.tsv" "$out/STANDARD-SOURCES.tsv"
