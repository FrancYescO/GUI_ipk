#!/bin/bash
set -e
base=/app/build_dir/target-arm_v7-a_glibc-2.26_eabi/linux-brcm963xx_vmg8825_b50b
cp -a "$base/linux-4.1.52" /tmp/linux-4.1.52
patch -d /tmp/linux-4.1.52 -p1 < /repo/patches/vbntj-4.1.52/001-damson-network-abi.patch
python - <<'PY'
p = '/tmp/linux-4.1.52/Makefile'
s = open(p).read()
s = s.replace('\t$(Q)$(MAKE) -C $(BRCMDRIVERS_DIR) symlinks', '\t@true')
open(p, 'w').write(s)
PY
export BCM_BUILD_DIR="$base/broadcom-sdk-502L07" KERNEL_BUILD_DIR="$base"
export LINUX_DIR=/tmp/linux-4.1.52
export TOOLCHAIN_DIR=/app/staging_dir/toolchain-arm_v7-a_gcc-5.5.0_glibc-2.26_eabi
export TARGET_DIR=/app/staging_dir/target-arm_v7-a_glibc-2.26_eabi
export BCM_PROFILE=VMG8825_B50B BRCM_CHIP=63138 BCM_KF=y
export PATH="$TOOLCHAIN_DIR/bin:$PATH"
cross="$TOOLCHAIN_DIR/bin/arm-openwrt-linux-gnueabi-"
export TARGET_CROSS="$cross" BCM_HOSTTOOLS_DIR=/app/staging_dir/host/bin/502L07
export MAKEFLAGS='--assume-old=prepare_bcm_driver'
/tmp/linux-4.1.52/scripts/config --file /tmp/linux-4.1.52/.config --enable WIRELESS_EXT --enable WEXT_CORE --enable WEXT_PROC --enable WEXT_SPY --enable WEXT_PRIV --disable BCM_MAP
make -C /tmp/linux-4.1.52 ARCH=arm CROSS_COMPILE="$cross" olddefconfig modules_prepare
/repo/scripts/build-damson-spu.sh "$BCM_BUILD_DIR" /tmp/linux-4.1.52 "$cross" /tmp/spu
patch -d /tmp/spu -p1 < /repo/experiments/spu-sha256/patches/001-hardware-capability-probe.patch
make -C /tmp/linux-4.1.52 ARCH=arm CROSS_COMPILE="$cross" SDK="$BCM_BUILD_DIR" M=/tmp/spu modules
cp -R /repo/build/vbntj-spu-test /tmp/spu-test
cp /repo/experiments/spu-sha256/kat_extended.c /tmp/spu-test/damson_spu_test.c
cp -R /tmp/linux-4.1.52/arch/arm/crypto /tmp/armcrypto
cat > /tmp/armcrypto/Makefile <<'EOF'
obj-m := aes-arm.o sha256-arm.o
aes-arm-y := aes-armv4.o aes_glue.o
sha256-arm-y := sha256-core.o sha256_glue.o
EOF
make -C /tmp/linux-4.1.52 ARCH=arm CROSS_COMPILE="$cross" M=/tmp/armcrypto modules
cp /tmp/armcrypto/*.ko /repo/.cache/tests/spu-sha256/output/
make -C /tmp/linux-4.1.52 ARCH=arm CROSS_COMPILE="$cross" M=/tmp/spu-test modules
cp -R /repo/build/vbntj-canary /tmp/canary
make -C /tmp/linux-4.1.52 ARCH=arm CROSS_COMPILE="$cross" M=/tmp/canary modules
cp -R /repo/experiments/spu-sha256 /tmp/hybrid
make -C /tmp/linux-4.1.52 ARCH=arm CROSS_COMPILE="$cross" M=/tmp/hybrid modules
cp /tmp/hybrid/spu_sha256_hybrid.ko /repo/.cache/tests/spu-sha256/output/
cp /tmp/spu/*.ko /tmp/spu-test/*.ko /tmp/canary/*.ko /repo/.cache/tests/spu-sha256/output/
