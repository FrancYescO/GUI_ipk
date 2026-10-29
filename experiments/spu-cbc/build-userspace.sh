#!/bin/bash
# Complete legacy GCC/glibc toolchain, not the kernel-only GCC 5.5 seed.
set -euo pipefail
cross=${1:?legacy cross compiler prefix}
openssl_archive=${2:?openssl-1.0.2t.tar.gz}
work=${3:?fresh work directory}
out=${4:?output directory}
repo=$(cd "$(dirname "$0")/../.." && pwd)
test ! -e "$work"
mkdir -p "$work/headers" "$work/openssl" "$out"
echo "14cb464efe7ac6b54799b34456bd69558a749a4931ecfd9cf9f71d7881cac7bc  $openssl_archive" | sha256sum -c -
echo "e795acb85118f1f39f0155df8fd28a3d79de7d1240b91bdf8cc9e2a1747d2642  $repo/artifacts/cryptodev/source/cryptodev-linux-08644db.tar.gz" | sha256sum -c -
tar -xzf "$openssl_archive" --strip-components=1 -C "$work/openssl"
tar -xzf "$repo/artifacts/cryptodev/source/cryptodev-linux-08644db.tar.gz" --strip-components=1 -C "$work/headers"
(cd "$work/openssl" && perl Configure linux-armv4 > configure.log)
"${cross}gcc" -O2 -Wall -Wextra -Werror -I"$work/headers" \
  "$repo/experiments/spu-cbc/session-test.c" -lrt -o "$out/session-test"
"${cross}gcc" -O2 -Wall -Wextra -Werror -shared -fPIC \
  "$repo/experiments/spu-cbc/redirect-crypto.c" -ldl -o "$out/redirect-crypto.so"
"${cross}gcc" -O2 -Wall -Wextra -Werror -I"$work/openssl/include" \
  "$repo/experiments/spu-cbc/evp-test.c" -ldl -lrt -o "$out/evp-test"
(cd "$out" && sha256sum session-test redirect-crypto.so evp-test > userspace.SHA256SUMS)
