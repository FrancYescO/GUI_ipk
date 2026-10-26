include $(TOPDIR)/rules.mk

PKG_NAME:=libcap-ng
PKG_VERSION:=0.8.5
PKG_RELEASE:=1
PKG_SOURCE:=$(PKG_NAME)-$(PKG_VERSION).tar.gz
PKG_SOURCE_URL:=https://people.redhat.com/sgrubb/libcap-ng/
PKG_HASH:=3ba5294d1cbdfa98afaacfbc00b6af9ed2b83e8a21817185dfd844cc8c7ac6ff
PKG_LICENSE:=LGPL-2.1+
PKG_LICENSE_FILES:=COPYING.LIB
PKG_INSTALL:=1
PKG_BUILD_PARALLEL:=1

include $(INCLUDE_DIR)/package.mk

define Package/libcap-ng
  SECTION:=libs
  CATEGORY:=Libraries
  TITLE:=POSIX capabilities library
  URL:=https://people.redhat.com/sgrubb/libcap-ng/
endef

CONFIGURE_ARGS += --without-python3

define Build/InstallDev
	$(INSTALL_DIR) $(1)/usr/include $(1)/usr/lib/pkgconfig
	$(CP) $(PKG_INSTALL_DIR)/usr/include/cap-ng.h $(1)/usr/include/
	$(CP) $(PKG_INSTALL_DIR)/usr/lib/libcap-ng.{a,so*} $(1)/usr/lib/
	$(CP) $(PKG_INSTALL_DIR)/usr/lib/pkgconfig/libcap-ng.pc $(1)/usr/lib/pkgconfig/
endef

define Package/libcap-ng/install
	$(INSTALL_DIR) $(1)/usr/lib
	$(CP) $(PKG_INSTALL_DIR)/usr/lib/libcap-ng.so.* $(1)/usr/lib/
endef

$(eval $(call BuildPackage,libcap-ng))
