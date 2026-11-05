#!/usr/bin/env bash
set -euo pipefail
sdk="$1"
kernel="$2"
cross="$3"
module_dir="$4"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
test -f "$sdk/bcmdrivers/opensource/char/spudd/impl3/spu.c"
grep -qx 'CONFIG_BCM_SPU_IMPL=3' "$kernel/.config"
mkdir -p "$module_dir"
cp "$sdk/bcmdrivers/opensource/char/spudd/impl3/"*.[ch] "$module_dir/"
for spu_patch in "$repo_root"/patches/vbntj-spu/*.patch; do
  patch --batch --forward -d "$module_dir" -p1 < "$spu_patch"
done
cat > "$module_dir/Makefile" <<'EOF'
obj-m := bcmspu.o
bcmspu-y := spu.o spu_runner.o
bcmspu-$(CONFIG_BLOG) += spu_blog.o
project := $(SDK)/rdp/projects/DSL_63138
TOP_DIR := $(SDK)/rdp
include $(project)/make.proj_flags
ccflags-y += $(PROJ_DEFS)
ccflags-y += -I$(src)
ccflags-y += -I$(SDK)/bcmdrivers/opensource/include/bcm963xx
ccflags-y += -I$(SDK)/bcmdrivers/broadcom/include/bcm963xx
ccflags-y += -I$(SDK)/shared/opensource/include/bcm963xx
ccflags-y += -I$(SDK)/shared/opensource/include/rdp
ccflags-y += -I$(SDK)/shared/opensource/include/pmc
ccflags-y += -I$(SDK)/shared/broadcom/include/bcm963xx
ccflags-y += -I$(SDK)/shared/opensource/boardparms/bcm963xx
ccflags-y += -I$(SDK)/bcmdrivers/opensource/char/rdpa_mw/impl1
ccflags-y += -I$(project)/target/bdmf/system
ccflags-y += -I$(project)/target/bdmf/system/linux
ccflags-y += -I$(project)/target/bdmf/system/linux/ce
ccflags-y += -I$(project)/target/bdmf/framework
ccflags-y += -I$(project)/target/rdpa
ccflags-y += -I$(project)/target/rdpa_gpl
ccflags-y += -I$(project)/target/rdd
ccflags-y += -I$(project)/target/rdp_subsystem
ccflags-y += -Werror -Wfatal-errors
EOF
make -C "$kernel" ARCH=arm CROSS_COMPILE="$cross" SDK="$sdk" M="$module_dir" modules
