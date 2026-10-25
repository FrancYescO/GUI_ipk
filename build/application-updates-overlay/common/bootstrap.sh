#!/usr/bin/env bash
# Source from a private application build; no target libraries are installed globally.
set -euo pipefail
common_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source_file() {
  python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]]["file"])' "$common_dir/sources.json" "$1"
}
bootstrap_modern() {
  local topdir=$1 downloads=$2
  # The buildroot wrapper forcibly rewrites prefix to its legacy sysroot.
  native_pkg_config="$topdir/staging_dir/host/bin/pkg-config.real"
  test -x "$native_pkg_config"
  tools="$topdir/.modern-application-tools"
  mkdir -p "$tools"
  exec 9>"$tools/bootstrap.lock"
  flock 9
  if [[ ! -f "$tools/ready" ]]; then
    mkdir -p "$tools/sdk" "$tools/cmake"
    tar -xJf "$downloads/$(source_file sdk)" -C "$tools/sdk" --strip-components=1
    "$tools/sdk/relocate-sdk.sh"
    tar -xzf "$downloads/$(source_file cmake)" -C "$tools/cmake" --strip-components=1
    touch "$tools/ready"
  fi
  # This SDK is private to static applications. Legacy libtool can otherwise
  # resolve its runtime .la metadata to absolute shared-object paths. Keep all
  # actual libraries, and perform metadata cleanup before releasing the lock.
  if [[ ! -f "$tools/static-runtime-ready" ]]; then
    find "$tools/sdk/arm-buildroot-linux-musleabi" -type f -name '*.la' -delete
    touch "$tools/static-runtime-ready"
  fi
  flock -u 9
  exec 9>&-
  sdk="$tools/sdk"
  cmake="$tools/cmake/bin/cmake"
  export CC="$sdk/bin/arm-linux-gcc" CXX="$sdk/bin/arm-linux-g++"
  export AR="$sdk/bin/arm-linux-ar" RANLIB="$sdk/bin/arm-linux-ranlib" STRIP="$sdk/bin/arm-linux-strip"
  export PATH="$tools/cmake/bin:$sdk/bin:$PATH"
  unset LD_LIBRARY_PATH PKG_CONFIG_PATH PKG_CONFIG_SYSROOT_DIR CROSS_COMPILE
}
setup_private_prefix() {
  prefix=$1
  mkdir -p "$prefix"
  export PKG_CONFIG_LIBDIR="$prefix/lib/pkgconfig"
  export PKG_CONFIG="$native_pkg_config --static"
  export CFLAGS=-Os CXXFLAGS=-Os CPPFLAGS="-I$prefix/include" LDFLAGS="-static -L$prefix/lib"
  # CMake's Linux platform initialization resets library suffixes after loading
  # the toolchain. Reapply the static-only policy after each project() call so
  # imported pkg-config dependencies cannot resolve an SDK .so by accident.
  cat > "$prefix/static-libraries.cmake" <<'EOF'
set(CMAKE_FIND_LIBRARY_SUFFIXES ".a")
EOF
  toolchain="$prefix/toolchain.cmake"
  cat > "$toolchain" <<EOF
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_PROJECT_INCLUDE "$prefix/static-libraries.cmake")
set(CMAKE_SYSTEM_PROCESSOR arm)
set(CMAKE_C_COMPILER "$CC")
set(CMAKE_CXX_COMPILER "$CXX")
set(CMAKE_AR "$AR")
set(CMAKE_RANLIB "$RANLIB")
set(CMAKE_C_FLAGS_INIT "-Os")
set(CMAKE_CXX_FLAGS_INIT "-Os")
set(CMAKE_EXE_LINKER_FLAGS_INIT "-static")
set(CMAKE_C_STANDARD_LIBRARIES "-latomic" CACHE STRING "" FORCE)
set(CMAKE_CXX_STANDARD_LIBRARIES "-latomic" CACHE STRING "" FORCE)
set(CMAKE_FIND_ROOT_PATH "$prefix" "$sdk/arm-buildroot-linux-musleabi/sysroot")
set(CMAKE_PREFIX_PATH "$prefix")
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)
set(CMAKE_FIND_LIBRARY_SUFFIXES ".a")
EOF
}
extract_private() {
  local component=$1 destination=$2
  if [[ ! -d "$destination" ]]; then
    mkdir -p "$destination"
    tar -xf "$downloads/$(source_file "$component")" -C "$destination" --strip-components=1
  fi
}
