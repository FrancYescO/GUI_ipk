include $(TOPDIR)/rules.mk

PKG_NAME:=rclone-webui-react
PKG_VERSION:=2.0.5
PKG_RELEASE:=1
PKG_SOURCE:=rclone-webui-react-$(PKG_VERSION).zip
PKG_SOURCE_URL:=https://github.com/rclone/rclone-webui-react/releases/download/v$(PKG_VERSION)
PKG_SOURCE_URL_FILE:=currentbuild.zip
PKG_HASH:=afd6836ecc5c5a1161e25cb0633c1167eb5933bb5069545680d69fcba635f011
PKG_LICENSE:=MIT
PKG_LICENSE_FILES:=LICENSE

include $(INCLUDE_DIR)/package.mk

define Package/rclone-webui-react
  SECTION:=net
  CATEGORY:=Network
  TITLE:=Rclone React web interface
  URL:=https://github.com/rclone/rclone-webui-react
  DEPENDS:=+rclone
  PKGARCH:=all
endef

define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
	unzip -q $(DL_DIR)/$(PKG_SOURCE) -d $(PKG_BUILD_DIR)
	$(CP) ./files/LICENSE $(PKG_BUILD_DIR)/LICENSE
endef

define Build/Configure
endef

define Build/Compile
endef

define Package/rclone-webui-react/install
	$(INSTALL_DIR) $(1)/usr/share/rclone/react $(1)/usr/share/licenses/rclone-webui-react
	$(CP) $(PKG_BUILD_DIR)/build/. $(1)/usr/share/rclone/react/
	$(INSTALL_DATA) ./files/LICENSE $(1)/usr/share/licenses/rclone-webui-react/
endef

$(eval $(call BuildPackage,rclone-webui-react))
