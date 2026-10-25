include $(TOPDIR)/rules.mk

PKG_NAME:=transmission
PKG_VERSION:=4.1.4
PKG_RELEASE:=1
PKG_SOURCE:=transmission-$(PKG_VERSION).tar.xz
PKG_SOURCE_URL:=https://github.com/transmission/transmission/releases/download/$(PKG_VERSION)
PKG_HASH:=86e7aa020cdf64826447034bc85f4d3b7c848d8c0891d9dc9b9fddfb2c805d22
PKG_LICENSE:=GPL-2.0-or-later MIT
PKG_LICENSE_FILES:=COPYING
PKG_BUILD_PARALLEL:=1
MODERN_COMPONENTS:=sdk cmake openssl curl zlib

include $(INCLUDE_DIR)/package.mk
include $(TOPDIR)/.application-build/downloads.mk

define Package/transmission/template
  SECTION:=net
  CATEGORY:=Network
  SUBMENU:=BitTorrent
  URL:=https://transmissionbt.com
  TITLE:=Transmission 4 client (private static OpenSSL)
  DEPENDS:=@arm +ca-bundle
endef

define Package/transmission-daemon-openssl
  $(call Package/transmission/template)
  USERID:=transmission=224:transmission=224
endef

define Package/transmission-cli-openssl
  $(call Package/transmission/template)
endef

define Package/transmission-remote-openssl
  $(call Package/transmission/template)
endef

define Package/transmission-web
  SECTION:=net
  CATEGORY:=Network
  TITLE:=Transmission 4 web interface
  PKGARCH:=all
endef

define Package/transmission-daemon-openssl/conffiles
/etc/config/transmission
endef

define Build/Configure
endef

define Build/Compile
	bash $(TOPDIR)/.application-build/build-transmission.sh $(PKG_BUILD_DIR) $(PKG_INSTALL_DIR) $(DL_DIR) $(TOPDIR)
endef

define Package/transmission-daemon-openssl/install
	$(INSTALL_DIR) $(1)/usr/bin $(1)/etc/config $(1)/etc/init.d
	$(INSTALL_BIN) $(PKG_INSTALL_DIR)/usr/bin/transmission-daemon $(1)/usr/bin/
	$(INSTALL_CONF) ./files/transmission.config $(1)/etc/config/transmission
	$(INSTALL_BIN) ./files/transmission.init $(1)/etc/init.d/transmission
endef

define Package/transmission-cli-openssl/install
	$(INSTALL_DIR) $(1)/usr/bin
	$(INSTALL_BIN) $(PKG_INSTALL_DIR)/usr/bin/transmission-cli $(PKG_INSTALL_DIR)/usr/bin/transmission-create $(PKG_INSTALL_DIR)/usr/bin/transmission-edit $(PKG_INSTALL_DIR)/usr/bin/transmission-show $(1)/usr/bin/
endef

define Package/transmission-remote-openssl/install
	$(INSTALL_DIR) $(1)/usr/bin
	$(INSTALL_BIN) $(PKG_INSTALL_DIR)/usr/bin/transmission-remote $(1)/usr/bin/
endef

define Package/transmission-web/install
	$(INSTALL_DIR) $(1)/usr/share/transmission/web
	$(CP) $(PKG_INSTALL_DIR)/usr/share/transmission/web/. $(1)/usr/share/transmission/web/
endef

$(eval $(call BuildPackage,transmission-daemon-openssl))
$(eval $(call BuildPackage,transmission-cli-openssl))
$(eval $(call BuildPackage,transmission-remote-openssl))
$(eval $(call BuildPackage,transmission-web))
