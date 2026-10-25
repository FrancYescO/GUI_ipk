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
build_cmake_dependency() {
 local name=$1 directory=$2
 shift 2
 "$cmake" -S "$directory" -B "$private/$name-build" \
  -DCMAKE_TOOLCHAIN_FILE="$toolchain" -DCMAKE_INSTALL_PREFIX="$prefix" \
  -DCMAKE_BUILD_TYPE=MinSizeRel -DBUILD_SHARED_LIBS=OFF -DBUILD_TESTING=OFF "$@"
 "$cmake" --build "$private/$name-build" --parallel 2
 "$cmake" --install "$private/$name-build"
}
if [[ ! -f "$prefix/lib/libpng16.a" ]]; then
 extract_private png "$private/png"
 build_cmake_dependency png "$private/png" -DPNG_SHARED=OFF -DPNG_STATIC=ON -DPNG_TESTS=OFF -DPNG_TOOLS=OFF -DZLIB_ROOT="$prefix"
fi
if [[ ! -f "$prefix/lib/libgd.a" ]]; then
 extract_private gd "$private/gd"
 build_cmake_dependency gd "$private/gd" -DENABLE_PNG=ON -DENABLE_JPEG=OFF \
  -DENABLE_TIFF=OFF -DENABLE_FREETYPE=OFF -DENABLE_FONTCONFIG=OFF \
  -DENABLE_WEBP=OFF -DENABLE_HEIF=OFF -DENABLE_AVIF=OFF -DENABLE_XPM=OFF
fi
if [[ ! -f "$prefix/lib/libcryptopp.a" ]]; then
 extract_private cryptopp "$private/cryptopp"
 (cd "$private/cryptopp"; make -j2 static CXX="$CXX" AR="$AR" RANLIB="$RANLIB" \
  CXXFLAGS='-Os -DNDEBUG -DCRYPTOPP_DISABLE_ASM')
 mkdir -p "$prefix/lib" "$prefix/include/cryptopp"
 cp "$private/cryptopp/libcryptopp.a" "$prefix/lib/"
 cp "$private/cryptopp/"*.h "$prefix/include/cryptopp/"
fi
if [[ ! -f "$prefix/lib/libncurses.a" ]]; then
 extract_private ncurses "$private/ncurses"
 (cd "$private/ncurses"; ./configure --host=arm-buildroot-linux-musleabi --prefix="$prefix" \
  --with-build-cc=/usr/bin/gcc --disable-widec --without-shared --with-normal \
  --without-progs --without-manpages --without-tests --without-ada --without-cxx --without-cxx-binding; make -j2; make install)
fi
if [[ ! -f "$prefix/lib/libreadline.a" ]]; then
 extract_private readline "$private/readline"
 (cd "$private/readline"; LIBS=-lncurses ./configure --host=arm-buildroot-linux-musleabi \
  --prefix="$prefix" --disable-shared --enable-static --with-curses; make -j2; make install)
fi
if [[ ! -f "$prefix/bin/wx-config" ]]; then
 extract_private wx "$private/wx"
 (cd "$private/wx"; CURL_CONFIG="$prefix/bin/curl-config" ./configure \
  --host=arm-buildroot-linux-musleabi --prefix="$prefix" \
  --disable-shared --disable-gui --enable-unicode --disable-debug \
  --with-zlib=sys --with-regex=builtin --with-expat=builtin \
  --enable-webrequest --with-libcurl --without-libtiff --without-libjpeg --without-libpng \
  --without-opengl --without-sdl --without-libnotify; make -j2; make install)
fi
if [[ ! -d "$prefix/lib/cmake/Boost-1.92.0" ]]; then
 extract_private boost "$private/boost"
 build_cmake_dependency boost "$private/boost" -DBOOST_INCLUDE_LIBRARIES=asio -DCMAKE_CXX_STANDARD=17
fi
# The pinned Crypto++ source supplies its version; a cross build cannot run
# upstream's target-side version probe on the x86 builder.
"$cmake" -S "$source_dir" -B "$private/amule-build" \
 -DCMAKE_TOOLCHAIN_FILE="$toolchain" -DCMAKE_INSTALL_PREFIX=/usr \
 -DCMAKE_BUILD_TYPE=MinSizeRel -DCMAKE_CXX_STANDARD=17 \
 -DCMAKE_CXX_FLAGS="-Os -I$prefix/include" \
 -DBUILD_MONOLITHIC=OFF -DBUILD_REMOTEGUI=OFF -DBUILD_ALC=OFF -DBUILD_ALCC=OFF \
 -DBUILD_CAS=OFF -DBUILD_WXCAS=OFF -DBUILD_ED2K=OFF -DBUILD_FILEVIEW=OFF \
 -DBUILD_DAEMON=ON -DBUILD_AMULECMD=ON -DBUILD_WEBSERVER=ON -DBUILD_TESTING=OFF \
 -DENABLE_UPNP=OFF -DENABLE_IP2COUNTRY=OFF -DENABLE_NLS=ON \
 -DwxWidgets_CONFIG_EXECUTABLE="$prefix/bin/wx-config" -DwxWidgets_USE_STATIC=ON \
 -DCRYPTOPP_INCLUDE_PREFIX=cryptopp -DCRYPTOPP_INCLUDE_DIR="$prefix/include" \
 -DCRYPTOPP_VERSION=8.9.0 -DCRYPTOPP_LIBRARY="$prefix/lib/libcryptopp.a" \
 -DCURL_ROOT="$prefix" -DOPENSSL_ROOT_DIR="$prefix" -DOPENSSL_USE_STATIC_LIBS=ON
"$cmake" --build "$private/amule-build" --parallel 2
DESTDIR="$stage" "$cmake" --install "$private/amule-build"
