include $(TOPDIR)/rules.mk

PKG_NAME:=rclone-ng
PKG_VERSION:=0.5.0
PKG_RELEASE:=1
PKG_SOURCE:=RcloneNg-v$(PKG_VERSION).tar.gz
PKG_SOURCE_URL:=https://github.com/ElonH/RcloneNg/releases/download/v$(PKG_VERSION)
PKG_HASH:=0b4916ddd0bacb5b358dc8d36b64c30f4182c0ace3eb06cda94b6578c419dcd9
PKG_LICENSE:=MIT
PKG_LICENSE_FILES:=LICENSE

include $(INCLUDE_DIR)/package.mk

define Package/rclone-ng
  SECTION:=net
  CATEGORY:=Network
  TITLE:=Rclone Angular web interface
  URL:=https://github.com/ElonH/RcloneNg
  DEPENDS:=+rclone
  PKGARCH:=all
endef

define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
	tar -xzf $(DL_DIR)/$(PKG_SOURCE) -C $(PKG_BUILD_DIR)
	$(CP) ./files/LICENSE $(PKG_BUILD_DIR)/LICENSE
endef

define Build/Configure
endef

define Build/Compile
endef

define Package/rclone-ng/install
	$(INSTALL_DIR) $(1)/usr/share/rclone/ng $(1)/usr/share/licenses/rclone-ng
	$(CP) $(PKG_BUILD_DIR)/RcloneNg/. $(1)/usr/share/rclone/ng/
	$(INSTALL_DATA) ./files/LICENSE $(1)/usr/share/licenses/rclone-ng/
endef

$(eval $(call BuildPackage,rclone-ng))
