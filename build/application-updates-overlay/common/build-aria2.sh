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
source "$(dirname "$0")/tls.sh"
ensure_private_tls
cd "$source_dir"
CXXFLAGS='-Os -std=gnu++11 -pthread' LIBS=-latomic ./configure \
 --host=arm-buildroot-linux-musleabi --prefix=/usr --disable-shared --enable-static \
 --disable-libaria2 --disable-nls --disable-dependency-tracking \
 --with-openssl --with-libz --without-gnutls --without-libnettle --without-libgcrypt \
 --without-gmp --without-libxml2 --without-libexpat --without-libssh2 --without-libcares \
 --without-sqlite3 --without-libuv --enable-bittorrent --disable-metalink --enable-websocket
# libtool interprets -static as library selection only; -all-static also
# makes the compiler runtime and libc static in the final executable.
make -j2 LDFLAGS="$LDFLAGS -all-static"
make DESTDIR="$stage" install
