include $(TOPDIR)/rules.mk

PKG_NAME:=amule
PKG_VERSION:=3.0.0
PKG_RELEASE:=1
PKG_SOURCE:=amule-$(PKG_VERSION).tar.gz
PKG_SOURCE_URL:=https://codeload.github.com/amule-project/amule/tar.gz/refs/tags/$(PKG_VERSION)?
PKG_HASH:=850a09d1a5ec7d1b8962e4051d51b29355ac3df84a7b0b1209f2d0dd5c62eab4
PKG_LICENSE:=GPL-2.0-or-later
PKG_LICENSE_FILES:=COPYING
PKG_BUILD_PARALLEL:=1
MODERN_COMPONENTS:=sdk cmake openssl curl zlib wx cryptopp boost png ncurses readline

include $(INCLUDE_DIR)/package.mk
include $(TOPDIR)/.application-build/downloads.mk

define Package/amule
  SECTION:=net
  CATEGORY:=Network
  SUBMENU:=P2P
  TITLE:=aMule daemon, command client and webserver
  URL:=https://www.amule.org
  DEPENDS:=@arm +ca-bundle
endef

define Build/Configure
endef

define Build/Compile
	bash $(TOPDIR)/.application-build/build-amule.sh $(PKG_BUILD_DIR) $(PKG_INSTALL_DIR) $(DL_DIR) $(TOPDIR)
endef

define Package/amule/install
	$(INSTALL_DIR) $(1)/usr/bin $(1)/usr/share
	$(INSTALL_BIN) $(PKG_INSTALL_DIR)/usr/bin/amulecmd $(PKG_INSTALL_DIR)/usr/bin/amuled $(PKG_INSTALL_DIR)/usr/bin/amuleweb $(1)/usr/bin/
	$(CP) $(PKG_INSTALL_DIR)/usr/share/amule $(1)/usr/share/
	if [ -d $(PKG_INSTALL_DIR)/usr/share/locale ]; then $(CP) $(PKG_INSTALL_DIR)/usr/share/locale $(1)/usr/share/; fi
endef

$(eval $(call BuildPackage,amule))
