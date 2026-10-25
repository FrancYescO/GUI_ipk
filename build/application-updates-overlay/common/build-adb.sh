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
# android-tools links zlib directly rather than through an imported CMake target.
if [[ ! -f "$prefix/lib/libz.a" ]]; then
 extract_private zlib "$private/zlib"
 (cd "$private/zlib"; ./configure --static --prefix="$prefix"; make -j2; make install)
fi
# libziparchive's public header includes the production FRIEND_TEST macro.
# Copy upstream headers only; no Google Test binary is built or packaged.
if [[ ! -f "$prefix/include/gtest/gtest_prod.h" ]]; then
 extract_private gtest "$private/gtest"
 mkdir -p "$prefix/include"
 cp -R "$private/gtest/googletest/include/gtest" "$prefix/include/"
fi
build_cmake_dependency() {
  local name=$1 directory=$2
  shift 2
  "$cmake" -S "$directory" -B "$private/$name-build" \
    -DCMAKE_TOOLCHAIN_FILE="$toolchain" -DCMAKE_INSTALL_PREFIX="$prefix" \
    -DCMAKE_BUILD_TYPE=MinSizeRel -DBUILD_SHARED_LIBS=OFF -DBUILD_TESTING=OFF "$@"
  "$cmake" --build "$private/$name-build" --parallel 2
  "$cmake" --install "$private/$name-build"
}
if [[ ! -f "$prefix/lib/libbrotlicommon.a" ]]; then
  extract_private brotli "$private/brotli"
  build_cmake_dependency brotli "$private/brotli" -DBROTLI_DISABLE_TESTS=ON
fi
if [[ ! -f "$prefix/lib/liblz4.a" ]]; then
  extract_private lz4 "$private/lz4"
  build_cmake_dependency lz4 "$private/lz4/build/cmake" -DLZ4_BUILD_CLI=OFF -DLZ4_BUILD_LEGACY_LZ4C=OFF
fi
if [[ ! -f "$prefix/lib/libzstd.a" ]]; then
  extract_private zstd "$private/zstd"
  build_cmake_dependency zstd "$private/zstd/build/cmake" \
    -DZSTD_BUILD_PROGRAMS=OFF -DZSTD_BUILD_SHARED=OFF -DZSTD_BUILD_STATIC=ON -DZSTD_BUILD_TESTS=OFF
fi
if [[ ! -f "$prefix/lib/libpcre2-8.a" ]]; then
  extract_private pcre2 "$private/pcre2"
  build_cmake_dependency pcre2 "$private/pcre2" -DPCRE2_BUILD_TESTS=OFF -DPCRE2_BUILD_PCRE2GREP=OFF -DPCRE2_SUPPORT_JIT=OFF
fi
if [[ ! -f "$prefix/lib/libusb-1.0.a" ]]; then
  extract_private libusb "$private/libusb"
  (cd "$private/libusb"; ./configure --host=arm-buildroot-linux-musleabi \
    --prefix="$prefix" --disable-shared --enable-static --disable-udev --disable-tests; make -j2; make install)
fi
if [[ ! -f "$prefix/lib/libprotobuf.a" ]]; then
  extract_private protobuf "$private/protobuf"
  extract_private absl "$private/absl"
  mkdir -p "$private/protoc"
  unzip -qo "$downloads/$(source_file protoc)" -d "$private/protoc"
  build_cmake_dependency protobuf "$private/protobuf" \
    -DCMAKE_CXX_STANDARD=17 -Dprotobuf_BUILD_TESTS=OFF -Dprotobuf_BUILD_SHARED_LIBS=OFF \
    -Dprotobuf_BUILD_PROTOC_BINARIES=OFF -Dprotobuf_BUILD_LIBPROTOC=OFF \
    -Dprotobuf_WITH_ZLIB=OFF -DFETCHCONTENT_SOURCE_DIR_ABSL="$private/absl" \
    -DABSL_PROPAGATE_CXX_STD=ON -DABSL_BUILD_TESTING=OFF
fi
"$cmake" -S "$source_dir" -B "$private/adb-build" \
  -DCMAKE_TOOLCHAIN_FILE="$toolchain" -DCMAKE_INSTALL_PREFIX=/usr \
  -DCMAKE_BUILD_TYPE=MinSizeRel -DBUILD_SHARED_LIBS=OFF -DBUILD_TESTING=OFF \
  -DANDROID_TOOLS_PATCH_VENDOR=OFF -DANDROID_TOOLS_USE_BUNDLED_FMT=ON \
  -DANDROID_TOOLS_USE_BUNDLED_LIBUSB=OFF -DANDROID_TOOLS_ADB_ENABLE_MDNS=OFF \
  -DOPENSSL_NO_ASM=ON -Dprotobuf_MODULE_COMPATIBLE=ON \
  -DProtobuf_PROTOC_EXECUTABLE="$private/protoc/bin/protoc"
"$cmake" --build "$private/adb-build" --target adb --parallel 2
mkdir -p "$stage/usr/bin"
install -m755 "$private/adb-build/vendor/adb" "$stage/usr/bin/adb"
