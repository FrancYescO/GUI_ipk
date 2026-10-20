# Appended only by the dedicated Linux 4.1.38 SPU profile.
define KernelPackage/bcm63xx-tch-spu
  SUBMENU:=Broadcom specific kernel modules
  TITLE:=Broadcom BCM63138 SPU cryptography
  DEPENDS:=@TARGET_brcm63xx_tch
  KCONFIG:=CONFIG_BCM_SPU CONFIG_BCM_SPU_IMPL=3
  FILES:=$(BRCMDRIVERS_DIR)/opensource/char/spudd/impl3/bcmspu.ko
  # Deliberately no AUTOLOAD: first test from /tmp on each firmware.
endef

$(eval $(call KernelPackage,bcm63xx-tch-spu))
