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
