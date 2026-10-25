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
