#!/usr/bin/env bash
set -euo pipefail
source_dir=$1
stage=$2
downloads=$3
topdir=$4
source "$(dirname "$0")/bootstrap.sh"
bootstrap_modern "$topdir" "$downloads"
private="$source_dir/.private"
mkdir -p "$private"
setup_private_prefix "$private/prefix"
if [[ ! -f "$prefix/lib/libz.a" ]]; then
  extract_private zlib "$private/zlib"
  (cd "$private/zlib"; ./configure --static --prefix="$prefix"; make -j2; make install)
fi
if [[ ! -f "$prefix/lib/libssl.a" ]]; then
  extract_private openssl "$private/openssl"
  (cd "$private/openssl"; perl Configure linux-generic32 no-shared no-tests no-module no-asm \
    --prefix="$prefix" --libdir=lib --openssldir=/etc/ssl -Os; make -j2; make install_sw)
fi
if [[ ! -f "$prefix/lib/libcurl.a" ]]; then
  extract_private curl "$private/curl"
  "$cmake" -S "$private/curl" -B "$private/curl-build" \
    -DCMAKE_TOOLCHAIN_FILE="$toolchain" -DCMAKE_INSTALL_PREFIX="$prefix" \
    -DBUILD_SHARED_LIBS=OFF -DBUILD_STATIC_LIBS=ON -DBUILD_CURL_EXE=OFF \
    -DBUILD_TESTING=OFF -DBUILD_LIBCURL_DOCS=OFF -DBUILD_MISC_DOCS=OFF \
    -DCURL_USE_OPENSSL=ON -DOPENSSL_ROOT_DIR="$prefix" -DOPENSSL_USE_STATIC_LIBS=ON \
    -DCURL_ZLIB=ON -DZLIB_ROOT="$prefix" -DCURL_USE_LIBPSL=OFF \
    -DCURL_BROTLI=OFF -DCURL_ZSTD=OFF -DCURL_USE_LIBSSH2=OFF \
    -DCURL_USE_LIBSSH=OFF -DCURL_USE_GSSAPI=OFF -DCURL_USE_LIBIDN2=OFF \
    -DCURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
  "$cmake" --build "$private/curl-build" --parallel 2
  "$cmake" --install "$private/curl-build"
fi
"$cmake" -S "$source_dir" -B "$private/transmission-build" \
  -DCMAKE_TOOLCHAIN_FILE="$toolchain" -DCMAKE_INSTALL_PREFIX=/usr \
  -DCMAKE_BUILD_TYPE=MinSizeRel -DBUILD_SHARED_LIBS=OFF \
  -DENABLE_GTK=OFF -DENABLE_QT=OFF -DENABLE_MAC=OFF -DENABLE_TESTS=OFF \
  -DENABLE_CLI=ON -DENABLE_DAEMON=ON -DENABLE_UTILS=ON -DINSTALL_WEB=OFF \
  -DPREFER_SYSTEM_LIB=OFF -DWITH_CRYPTO=openssl \
  -DCURL_ROOT="$prefix" -DOPENSSL_ROOT_DIR="$prefix" -DOPENSSL_USE_STATIC_LIBS=ON
"$cmake" --build "$private/transmission-build" --parallel 2
DESTDIR="$stage" "$cmake" --install "$private/transmission-build"
mkdir -p "$stage/usr/share/transmission/web"
cp -a "$source_dir/web/public_html/." "$stage/usr/share/transmission/web/"
