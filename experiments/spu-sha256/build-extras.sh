#!/usr/bin/env bash
# Called only by the raw-artifact laboratory profile, never by stable feeds.
set -euo pipefail
sdk=$1 kernel=$2 cross=$3 spu=$4 kat=$5 work=$6
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
patch --batch --directory "$spu" -p1 < "$repo_root/experiments/spu-sha256/patches/001-hardware-capability-probe.patch"
patch --batch --directory "$spu" -p1 < "$repo_root/experiments/spu-sha256/patches/002-host-transfer-pool.patch"
patch --batch --directory "$spu" -p1 < "$repo_root/experiments/spu-sha256/patches/003-rx-diagnostics-pool-fallback.patch"
make -C "$kernel" ARCH=arm CROSS_COMPILE="$cross" SDK="$sdk" M="$spu" modules
cp "$repo_root/experiments/spu-sha256/kat_extended.c" "$kat/damson_spu_test.c"
make -C "$kernel" ARCH=arm CROSS_COMPILE="$cross" M="$kat" modules
mkdir -p "$work"
cp -R "$kernel/arch/arm/crypto" "$work/armcrypto"
cat > "$work/armcrypto/Makefile" <<'KBUILD'
obj-m := aes-arm.o sha256-arm.o
aes-arm-y := aes-armv4.o aes_glue.o
sha256-arm-y := sha256-core.o sha256_glue.o
KBUILD
make -C "$kernel" ARCH=arm CROSS_COMPILE="$cross" M="$work/armcrypto" modules
mkdir -p "$work/hybrid"
cp "$repo_root/experiments/spu-sha256/Makefile" "$repo_root/experiments/spu-sha256/spu_sha256_hybrid.c" "$work/hybrid/"
make -C "$kernel" ARCH=arm CROSS_COMPILE="$cross" M="$work/hybrid" SPU_INPLACE_LAB="${SPU_INPLACE_LAB:-0}" modules
