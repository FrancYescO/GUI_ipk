define Download/modern-sdk
  FILE:=armv5-eabi--musl--stable-2026.08-1.tar.xz
  URL:=https://toolchains.bootlin.com/downloads/releases/toolchains/armv5-eabi/tarballs
  URL_FILE:=armv5-eabi--musl--stable-2026.08-1.tar.xz
  HASH:=a7db571eaa0f1ba2eea9a3932e8ad64bfaf33bfb7e7b96dd09702fe3ecedcf1a
endef
ifneq ($(filter sdk,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-sdk))
endif

define Download/modern-cmake
  FILE:=cmake-3.31.8-linux-x86_64.tar.gz
  URL:=https://github.com/Kitware/CMake/releases/download/v3.31.8
  URL_FILE:=cmake-3.31.8-linux-x86_64.tar.gz
  HASH:=630615d8e98ac33eba7fbe472626dff5c899c85af3c024585ae109166a6909d0
endef
ifneq ($(filter cmake,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-cmake))
endif

define Download/modern-openssl
  FILE:=openssl-3.5.9.tar.gz
  URL:=https://github.com/openssl/openssl/releases/download/openssl-3.5.9
  URL_FILE:=openssl-3.5.9.tar.gz
  HASH:=603f5602e2eef00d77fbd429d34dcd5822bb301757a1bc9cdb24c670f1eb859a
endef
ifneq ($(filter openssl,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-openssl))
endif

define Download/modern-curl
  FILE:=curl-8.23.0.tar.gz
  URL:=https://github.com/curl/curl/releases/download/curl-8_23_0
  URL_FILE:=curl-8.23.0.tar.gz
  HASH:=e3de77cfa6367083c776a26647fc9f633b538c06c3baa73d931a252ac8f72b49
endef
ifneq ($(filter curl,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-curl))
endif

define Download/modern-zlib
  FILE:=zlib-1.3.2.tar.gz
  URL:=https://github.com/madler/zlib/releases/download/v1.3.2
  URL_FILE:=zlib-1.3.2.tar.gz
  HASH:=bb329a0a2cd0274d05519d61c667c062e06990d72e125ee2dfa8de64f0119d16
endef
ifneq ($(filter zlib,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-zlib))
endif

define Download/modern-brotli
  FILE:=brotli-1.2.1.tar.gz
  URL:=https://codeload.github.com/google/brotli/tar.gz/refs/tags
  URL_FILE:=v1.2.1
  HASH:=98d35d11a78dc453aebb7d10c3748f3f73ff78c8267c0dc697b8631f67bf7e8f
endef
ifneq ($(filter brotli,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-brotli))
endif

define Download/modern-lz4
  FILE:=lz4-1.10.0.tar.gz
  URL:=https://codeload.github.com/lz4/lz4/tar.gz/refs/tags
  URL_FILE:=v1.10.0
  HASH:=537512904744b35e232912055ccf8ec66d768639ff3abe5788d90d792ec5f48b
endef
ifneq ($(filter lz4,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-lz4))
endif

define Download/modern-zstd
  FILE:=zstd-1.5.7.tar.gz
  URL:=https://github.com/facebook/zstd/releases/download/v1.5.7
  URL_FILE:=zstd-1.5.7.tar.gz
  HASH:=eb33e51f49a15e023950cd7825ca74a4a2b43db8354825ac24fc1b7ee09e6fa3
endef
ifneq ($(filter zstd,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-zstd))
endif

define Download/modern-pcre2
  FILE:=pcre2-10.49.tar.bz2
  URL:=https://github.com/PCRE2Project/pcre2/releases/download/pcre2-10.49
  URL_FILE:=pcre2-10.49.tar.bz2
  HASH:=53c156e1ba416a20da8e65395daa132da0d80e76910424caca3fcdae7831d384
endef
ifneq ($(filter pcre2,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-pcre2))
endif

define Download/modern-libusb
  FILE:=libusb-1.0.30.tar.bz2
  URL:=https://github.com/libusb/libusb/releases/download/v1.0.30
  URL_FILE:=libusb-1.0.30.tar.bz2
  HASH:=fea36f34f9156400209595e300840767ab1a385ede1dc7ee893015aea9c6dbaf
endef
ifneq ($(filter libusb,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-libusb))
endif

define Download/modern-protobuf
  FILE:=protobuf-36.2.tar.gz
  URL:=https://github.com/protocolbuffers/protobuf/releases/download/v36.2
  URL_FILE:=protobuf-36.2.tar.gz
  HASH:=3d9642a662d10e68ebae5e53f14dcce5105684212d5078f8e0d47d1ab3ae6b64
endef
ifneq ($(filter protobuf,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-protobuf))
endif

define Download/modern-protoc
  FILE:=protoc-36.2-linux-x86_64.zip
  URL:=https://github.com/protocolbuffers/protobuf/releases/download/v36.2
  URL_FILE:=protoc-36.2-linux-x86_64.zip
  HASH:=121f6c7afe1d4d0e3ea6aab9432038599250134cbf4474cb1167d2c7decd4278
endef
ifneq ($(filter protoc,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-protoc))
endif

define Download/modern-absl
  FILE:=abseil-20250512.1.tar.gz
  URL:=https://codeload.github.com/abseil/abseil-cpp/tar.gz
  URL_FILE:=20250512.1
  HASH:=9b7a064305e9fd94d124ffa6cc358592eb42b5da588fb4e07d09254aa40086db
endef
ifneq ($(filter absl,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-absl))
endif

define Download/modern-wx
  FILE:=wxWidgets-3.2.12.tar.bz2
  URL:=https://github.com/wxWidgets/wxWidgets/releases/download/v3.2.12
  URL_FILE:=wxWidgets-3.2.12.tar.bz2
  HASH:=a62719bb5e1dcc41c1a6fc1eecd499c7ee8521f70402c7b1bb3342a1e16344e0
endef
ifneq ($(filter wx,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-wx))
endif

define Download/modern-cryptopp
  FILE:=cryptopp-8.9.0.tar.gz
  URL:=https://codeload.github.com/weidai11/cryptopp/tar.gz/refs/tags
  URL_FILE:=CRYPTOPP_8_9_0
  HASH:=ab5174b9b5c6236588e15a1aa1aaecb6658cdbe09501c7981ac8db276a24d9ab
endef
ifneq ($(filter cryptopp,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-cryptopp))
endif

define Download/modern-boost
  FILE:=boost-1.92.0-cmake.tar.xz
  URL:=https://github.com/boostorg/boost/releases/download/boost-1.92.0
  URL_FILE:=boost-1.92.0-cmake.tar.xz
  HASH:=9bed76128d4e46755dbe818487788c6fceb6f72b378f4daa49b7e1e600d9088d
endef
ifneq ($(filter boost,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-boost))
endif

define Download/modern-gd
  FILE:=libgd-2.3.3.tar.gz
  URL:=https://github.com/libgd/libgd/releases/download/gd-2.3.3
  URL_FILE:=libgd-2.3.3.tar.gz
  HASH:=dd3f1f0bb016edcc0b2d082e8229c822ad1d02223511997c80461481759b1ed2
endef
ifneq ($(filter gd,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-gd))
endif

define Download/modern-png
  FILE:=libpng-1.6.59.tar.gz
  URL:=https://codeload.github.com/pnggroup/libpng/tar.gz/refs/tags
  URL_FILE:=v1.6.59
  HASH:=2540302a1844ad2b2b501977abecfa850f265f97b78f065a712ab4074a89f5b5
endef
ifneq ($(filter png,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-png))
endif

define Download/modern-ncurses
  FILE:=ncurses-6.6.tar.gz
  URL:=https://ftp.gnu.org/gnu/ncurses
  URL_FILE:=ncurses-6.6.tar.gz
  HASH:=355b4cbbed880b0381a04c46617b7656e362585d52e9cf84a67e2009b749ff11
endef
ifneq ($(filter ncurses,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-ncurses))
endif

define Download/modern-readline
  FILE:=readline-8.3.tar.gz
  URL:=https://ftp.gnu.org/gnu/readline
  URL_FILE:=readline-8.3.tar.gz
  HASH:=fe5383204467828cd495ee8d1d3c037a7eba1389c22bc6a041f627976f9061cc
endef
ifneq ($(filter readline,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-readline))
endif
