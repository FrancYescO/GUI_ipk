include $(TOPDIR)/rules.mk

PKG_NAME:=libgomp
PKG_VERSION:=4.8.3
PKG_RELEASE:=1
PKG_SOURCE:=gcc-$(PKG_VERSION).tar.bz2
PKG_SOURCE_URL:=https://ftp.gnu.org/gnu/gcc/gcc-$(PKG_VERSION)/
PKG_HASH:=6a8e4f11b185f4fe2ed9d7fc053e80f8c7e73f800c045f51f9d8bea33f080f1e
PKG_BUILD_DIR:=$(BUILD_DIR)/libgomp-$(PKG_VERSION)/gcc-$(PKG_VERSION)
PKG_LICENSE:=GPL-3.0-with-GCC-exception
PKG_LICENSE_FILES:=COPYING3 COPYING.RUNTIME
PKG_BUILD_PARALLEL:=1
PKG_INSTALL:=1

include $(INCLUDE_DIR)/package.mk

define Package/libgomp
  SECTION:=libs
  CATEGORY:=Libraries
  TITLE:=GNU OpenMP runtime library
  URL:=https://gcc.gnu.org/projects/gomp/
  DEPENDS:=+libgcc +libpthread
endef

define Package/libgomp/description
 GNU OpenMP runtime built with the existing ARM cross-toolchain.
endef

# Build the runtime alone; the supplied toolchain has no libgomp payload.
define Build/Configure
	mkdir -p $(PKG_BUILD_DIR)/build
	(cd $(PKG_BUILD_DIR)/build; \
		$(TARGET_CONFIGURE_OPTS) \
		$(CONFIGURE_VARS) \
		../libgomp/configure $(CONFIGURE_ARGS) \
		--enable-shared --disable-static --disable-multilib --disable-nls \
	)
endef

MAKE_PATH:=build

define Build/InstallDev
	$(INSTALL_DIR) $(1)/usr/include $(1)/usr/lib
	$(CP) $(PKG_BUILD_DIR)/build/omp.h $(1)/usr/include/
	$(CP) $(PKG_INSTALL_DIR)/usr/lib/libgomp.so* $(1)/usr/lib/
	$(CP) $(PKG_INSTALL_DIR)/usr/lib/libgomp.spec $(1)/usr/lib/
endef

define Package/libgomp/install
	$(INSTALL_DIR) $(1)/usr/lib
	$(CP) $(PKG_INSTALL_DIR)/usr/lib/libgomp.so.* $(1)/usr/lib/
endef

$(eval $(call BuildPackage,libgomp))
