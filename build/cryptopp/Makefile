include $(TOPDIR)/rules.mk

PKG_NAME:=libcryptopp
PKG_VERSION:=8.9.0
PKG_RELEASE:=1
PKG_SOURCE:=CRYPTOPP_8_9_0.tar.gz
PKG_SOURCE_URL:=https://github.com/weidai11/cryptopp/archive
PKG_HASH:=ab5174b9b5c6236588e15a1aa1aaecb6658cdbe09501c7981ac8db276a24d9ab
PKG_BUILD_DIR:=$(BUILD_DIR)/cryptopp-CRYPTOPP_8_9_0
PKG_BUILD_PARALLEL:=1
PKG_LICENSE:=BSL-1.0
PKG_LICENSE_FILES:=License.txt

include $(INCLUDE_DIR)/package.mk

define Package/libcryptopp
  SECTION:=libs
  CATEGORY:=Libraries
  TITLE:=Crypto++ cryptographic library
  URL:=https://www.cryptopp.com/
  DEPENDS:=+libstdcpp +libpthread
endef

define Build/Configure
endef

define Build/Compile
	$(MAKE_VARS) $(MAKE) -C $(PKG_BUILD_DIR) \
		CXX="$(TARGET_CXX)" AR="$(TARGET_AR)" RANLIB="$(TARGET_RANLIB)" \
		CPPFLAGS="$(TARGET_CPPFLAGS)" \
		CXXFLAGS="$(TARGET_CXXFLAGS) -std=gnu++11 -fPIC" \
		LDFLAGS="$(TARGET_LDFLAGS)" HAS_SOLIB_VERSION=1 shared
endef

define Build/InstallDev
	$(INSTALL_DIR) $(1)/usr/include/cryptopp $(1)/usr/lib
	$(CP) $(PKG_BUILD_DIR)/*.h $(1)/usr/include/cryptopp/
	$(CP) $(PKG_BUILD_DIR)/libcryptopp.so* $(1)/usr/lib/
endef

define Package/libcryptopp/install
	$(INSTALL_DIR) $(1)/usr/lib
	$(CP) $(PKG_BUILD_DIR)/libcryptopp.so.* $(1)/usr/lib/
endef

$(eval $(call BuildPackage,libcryptopp))
