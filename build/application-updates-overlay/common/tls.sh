#!/usr/bin/env bash
ensure_private_tls() {
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
}
