# Legacy kernel backport; userspace wg is packaged independently.
include $(TOPDIR)/rules.mk
include $(INCLUDE_DIR)/kernel.mk

PKG_NAME:=wireguard-linux-compat
PKG_VERSION:=1.0.20220627
PKG_RELEASE:=1
PKG_SOURCE:=$(PKG_NAME)-$(PKG_VERSION).tar.xz
PKG_SOURCE_URL:=https://git.zx2c4.com/wireguard-linux-compat/snapshot/
PKG_HASH:=19b181e5c7d2260c23ecad4ad324425fd8e88200d97a885a2c7d4bd26cd61461
PKG_LICENSE:=GPL-2.0
PKG_LICENSE_FILES:=COPYING
PKG_BUILD_DIR:=$(KERNEL_BUILD_DIR)/$(PKG_NAME)-$(PKG_VERSION)
PKG_BUILD_PARALLEL:=1
PKG_USE_MIPS16:=0

include $(INCLUDE_DIR)/package.mk

# Installing a module is a separate decision from installing wg.
define KernelPackage/wireguard
  SUBMENU:=Network Support
  TITLE:=WireGuard legacy kernel module
  DEPENDS:=+kmod-udptunnel4 +IPV6:kmod-udptunnel6
  FILES:=$(PKG_BUILD_DIR)/src/wireguard.$(LINUX_KMOD_SUFFIX)
endef

define Build/Compile
	$(MAKE) $(KERNEL_MAKEOPTS) M="$(PKG_BUILD_DIR)/src" modules
endef

$(eval $(call KernelPackage,wireguard))
