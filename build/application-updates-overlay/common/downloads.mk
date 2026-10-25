define Download/modern-sdk
  FILE:=armv5-eabi--musl--stable-2026.08-1.tar.xz
  URL:=https://toolchains.bootlin.com/downloads/releases/toolchains/armv5-eabi/tarballs
  HASH:=a7db571eaa0f1ba2eea9a3932e8ad64bfaf33bfb7e7b96dd09702fe3ecedcf1a
endef
ifneq ($(filter sdk,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-sdk))
endif

define Download/modern-cmake
  FILE:=cmake-3.31.8-linux-x86_64.tar.gz
  URL:=https://github.com/Kitware/CMake/releases/download/v3.31.8
  HASH:=630615d8e98ac33eba7fbe472626dff5c899c85af3c024585ae109166a6909d0
endef
ifneq ($(filter cmake,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-cmake))
endif

define Download/modern-openssl
  FILE:=openssl-3.5.9.tar.gz
  URL:=https://github.com/openssl/openssl/releases/download/openssl-3.5.9
  HASH:=603f5602e2eef00d77fbd429d34dcd5822bb301757a1bc9cdb24c670f1eb859a
endef
ifneq ($(filter openssl,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-openssl))
endif

define Download/modern-curl
  FILE:=curl-8.23.0.tar.gz
  URL:=https://github.com/curl/curl/releases/download/curl-8_23_0
  HASH:=e3de77cfa6367083c776a26647fc9f633b538c06c3baa73d931a252ac8f72b49
endef
ifneq ($(filter curl,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-curl))
endif

define Download/modern-zlib
  FILE:=zlib-1.3.2.tar.gz
  URL:=https://github.com/madler/zlib/releases/download/v1.3.2
  HASH:=bb329a0a2cd0274d05519d61c667c062e06990d72e125ee2dfa8de64f0119d16
endef
ifneq ($(filter zlib,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-zlib))
endif

define Download/modern-brotli
  FILE:=brotli-1.2.1.tar.gz
  URL:=https://codeload.github.com/google/brotli/tar.gz/refs/tags
  HASH:=98d35d11a78dc453aebb7d10c3748f3f73ff78c8267c0dc697b8631f67bf7e8f
endef
ifneq ($(filter brotli,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-brotli))
endif

define Download/modern-lz4
  FILE:=lz4-1.10.0.tar.gz
  URL:=https://codeload.github.com/lz4/lz4/tar.gz/refs/tags
  HASH:=537512904744b35e232912055ccf8ec66d768639ff3abe5788d90d792ec5f48b
endef
ifneq ($(filter lz4,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-lz4))
endif

define Download/modern-zstd
  FILE:=zstd-1.5.7.tar.gz
  URL:=https://github.com/facebook/zstd/releases/download/v1.5.7
  HASH:=eb33e51f49a15e023950cd7825ca74a4a2b43db8354825ac24fc1b7ee09e6fa3
endef
ifneq ($(filter zstd,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-zstd))
endif

define Download/modern-pcre2
  FILE:=pcre2-10.49.tar.bz2
  URL:=https://github.com/PCRE2Project/pcre2/releases/download/pcre2-10.49
  HASH:=53c156e1ba416a20da8e65395daa132da0d80e76910424caca3fcdae7831d384
endef
ifneq ($(filter pcre2,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-pcre2))
endif

define Download/modern-libusb
  FILE:=libusb-1.0.30.tar.bz2
  URL:=https://github.com/libusb/libusb/releases/download/v1.0.30
  HASH:=fea36f34f9156400209595e300840767ab1a385ede1dc7ee893015aea9c6dbaf
endef
ifneq ($(filter libusb,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-libusb))
endif

define Download/modern-protobuf
  FILE:=protobuf-36.2.tar.gz
  URL:=https://github.com/protocolbuffers/protobuf/releases/download/v36.2
  HASH:=3d9642a662d10e68ebae5e53f14dcce5105684212d5078f8e0d47d1ab3ae6b64
endef
ifneq ($(filter protobuf,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-protobuf))
endif

define Download/modern-protoc
  FILE:=protoc-36.2-linux-x86_64.zip
  URL:=https://github.com/protocolbuffers/protobuf/releases/download/v36.2
  HASH:=121f6c7afe1d4d0e3ea6aab9432038599250134cbf4474cb1167d2c7decd4278
endef
ifneq ($(filter protoc,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-protoc))
endif

define Download/modern-absl
  FILE:=abseil-20250512.1.tar.gz
  URL:=https://codeload.github.com/abseil/abseil-cpp/tar.gz
  HASH:=9b7a064305e9fd94d124ffa6cc358592eb42b5da588fb4e07d09254aa40086db
endef
ifneq ($(filter absl,$(MODERN_COMPONENTS)),)
$(eval $(call Download,modern-absl))
endif
