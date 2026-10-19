include $(TOPDIR)/rules.mk

PKG_NAME:=swig4
PKG_VERSION:=4.0.2
PKG_RELEASE:=1
PKG_SOURCE:=swig-$(PKG_VERSION).tar.gz
PKG_SOURCE_URL:=https://sources.openwrt.org
PKG_HASH:=d53be9730d8d58a16bf0cbd1f8ac0c0c3e1090573168bfa151b01eb47fa906fc
PKG_BUILD_DIR:=$(BUILD_DIR)/swig-$(PKG_VERSION)
HOST_BUILD_DIR:=$(BUILD_DIR_HOST)/swig-$(PKG_VERSION)
HOST_BUILD_PARALLEL:=1
PKG_LICENSE:=GPL-3.0
PKG_LICENSE_FILES:=LICENSE

include $(INCLUDE_DIR)/host-build.mk
include $(INCLUDE_DIR)/package.mk

define Package/swig4
  SECTION:=libs
  CATEGORY:=Libraries
  TITLE:=SWIG 4 host binding generator
  BUILDONLY:=1
endef

HOST_CONFIGURE_ARGS += \
  --without-pcre \
  --prefix=$(STAGING_DIR_HOSTPKG)/swig4 \
  --exec-prefix=$(STAGING_DIR_HOSTPKG)/swig4

$(eval $(call HostBuild))
$(eval $(call BuildPackage,swig4))
