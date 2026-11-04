#!/bin/bash
# Private, low-priority scalar ARM SHA1 implementation for framing HMAC only.
set -euo pipefail
kernel=${1:?prepared kernel}
cross=${2:?cross compiler prefix}
work=${3:?fresh work directory}
out=${4:?output directory}
test ! -e "$work"
mkdir -p "$work" "$out"
cp "$kernel/arch/arm/crypto/sha1_glue.c" "$kernel/arch/arm/crypto/sha1-armv4-large.S" \
  "$kernel/arch/arm/crypto/sha1.h" "$work/"
python - "$work" <<'PY'
import os, re, sys
root = sys.argv[1]
for name in ('sha1_glue.c', 'sha1-armv4-large.S', 'sha1.h'):
    path = os.path.join(root, name)
    with open(path) as stream:
        source = stream.read()
    source = re.sub(r'EXPORT_SYMBOL_GPL\([^\n]+\);|MODULE_ALIAS_CRYPTO\([^\n]+\);', '', source)
    for symbol in ('sha1_block_data_order', 'sha1_update_arm', 'sha1_finup_arm'):
        source = source.replace(symbol, 'spu_cbc_' + symbol)
    if name.endswith('.c'):
        source, n = re.subn(r'(\.cra_driver_name\s*=\s*)"[^"]+"', r'\1"sha1-spu-cbc-lab-arm"', source)
        assert n == 1
        source, n = re.subn(r'(\.cra_priority\s*=\s*)\d+', r'\g<1>1', source)
        assert n == 1
    with open(path, 'w') as stream:
        stream.write(source)
PY
cat > "$work/Makefile" <<'EOF'
obj-m := sha1_spu_cbc_lab.o
sha1_spu_cbc_lab-y := sha1_glue.o sha1-armv4-large.o
EOF
make -C "$kernel" ARCH=arm CROSS_COMPILE="$cross" M="$work" modules
cp "$work/sha1_spu_cbc_lab.ko" "$out/"
"${cross}strip" --strip-debug "$out/sha1_spu_cbc_lab.ko"
"${cross}nm" --undefined-only "$out/sha1_spu_cbc_lab.ko" | awk '{print $NF}' | LC_ALL=C sort -u > "$out/sha1_spu_cbc_lab.ko.undefined-symbols"
