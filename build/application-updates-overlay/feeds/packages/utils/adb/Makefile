include $(TOPDIR)/rules.mk

PKG_NAME:=android-tools
PKG_VERSION:=37.0.0p1
PKG_RELEASE:=1
PKG_SOURCE:=android-tools-$(PKG_VERSION).tar.xz
PKG_SOURCE_URL:=https://github.com/nmeum/android-tools/releases/download/$(PKG_VERSION)
PKG_HASH:=2c6de1abe16b211c7d9f59276217e14fd9e0e18b20e331d3c84358f5dffd576e
PKG_LICENSE:=Apache-2.0 BSD-3-Clause MIT
PKG_BUILD_PARALLEL:=1
MODERN_COMPONENTS:=sdk cmake brotli lz4 zstd pcre2 libusb protobuf protoc absl

include $(INCLUDE_DIR)/package.mk
include $(TOPDIR)/.application-build/downloads.mk

define Package/adb
  SECTION:=utils
  CATEGORY:=Utilities
  TITLE:=Android Debug Bridge client
  URL:=https://github.com/nmeum/android-tools
  DEPENDS:=@arm
  VERSION:=android.$(PKG_VERSION)-$(PKG_RELEASE)
endef

define Build/Configure
endef

define Build/Compile
	bash $(TOPDIR)/.application-build/build-adb.sh $(PKG_BUILD_DIR) $(PKG_INSTALL_DIR) $(DL_DIR) $(TOPDIR)
endef

define Package/adb/install
	$(INSTALL_DIR) $(1)/usr/bin
	$(INSTALL_BIN) $(PKG_INSTALL_DIR)/usr/bin/adb $(1)/usr/bin/
endef

$(eval $(call BuildPackage,adb))
