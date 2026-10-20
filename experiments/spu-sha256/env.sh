base=/app/build_dir/target-arm_v7-a_glibc-2.26_eabi/linux-brcm963xx_vmg8825_b50b
export BCM_BUILD_DIR="$base/broadcom-sdk-502L07" KERNEL_BUILD_DIR="$base"
export LINUX_DIR=/tmp/linux-4.1.52
export TOOLCHAIN_DIR=/app/staging_dir/toolchain-arm_v7-a_gcc-5.5.0_glibc-2.26_eabi
export TARGET_DIR=/app/staging_dir/target-arm_v7-a_glibc-2.26_eabi
export BCM_PROFILE=VMG8825_B50B BRCM_CHIP=63138 BCM_KF=y
export PATH="$TOOLCHAIN_DIR/bin:$PATH"
cross="$TOOLCHAIN_DIR/bin/arm-openwrt-linux-gnueabi-"
export TARGET_CROSS="$cross" BCM_HOSTTOOLS_DIR=/app/staging_dir/host/bin/502L07
export MAKEFLAGS='--assume-old=prepare_bcm_driver'
