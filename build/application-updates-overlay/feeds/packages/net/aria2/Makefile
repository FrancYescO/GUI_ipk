#
# Copyright (C) 2012-2017 OpenWrt.org
#
# This is free software, licensed under the GNU General Public License v2.
# See /LICENSE for more information.
#
include $(TOPDIR)/rules.mk

PKG_NAME:=aria2
PKG_VERSION:=1.37.0
PKG_RELEASE:=2

PKG_SOURCE:=$(PKG_NAME)-$(PKG_VERSION).tar.xz
PKG_SOURCE_URL:=https://github.com/aria2/aria2/releases/download/release-$(PKG_VERSION)/
PKG_HASH:=60a420ad7085eb616cb6e2bdf0a7206d68ff3d37fb5a956dc44242eb2f79b66b

PKG_MAINTAINER:=Imre Kaloz <kaloz@openwrt.org>, \
	Hsing-Wang Liao <kuoruan@gmail.com>
PKG_LICENSE:=GPLv2
PKG_LICENSE_FILES:=COPYING

MODERN_COMPONENTS:=sdk cmake openssl curl zlib

include $(INCLUDE_DIR)/package.mk
include $(TOPDIR)/.application-build/downloads.mk

define Package/aria2
  SECTION:=net
  CATEGORY:=Network
  SUBMENU:=File Transfer
  TITLE:=aria2 download client (private static OpenSSL)
  URL:=https://aria2.github.io/
  DEPENDS:=@arm +ca-bundle
  USERID:=aria2=6800:aria2=6800
endef

define Package/aria2/description
  aria2 is a lightweight multi-protocol & multi-source command-line download
  utility
endef

define Build/Configure
endef

define Build/Compile
	bash $(TOPDIR)/.application-build/build-aria2.sh $(PKG_BUILD_DIR) $(PKG_INSTALL_DIR) $(DL_DIR) $(TOPDIR)
endef

define Package/aria2/install
	$(INSTALL_DIR) $(1)/usr/bin
	$(INSTALL_BIN) $(PKG_INSTALL_DIR)/usr/bin/aria2c $(1)/usr/bin

	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) ./files/aria2.init $(1)/etc/init.d/aria2

	$(INSTALL_DIR) $(1)/etc/config
	$(INSTALL_CONF) ./files/aria2.conf $(1)/etc/config/aria2
endef

$(eval $(call BuildPackage,aria2))
