#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
kernel_dir="${1:?kernel source directory required}"
compatibility_patch="$repo_root/patches/usb-rndis/001-misc-class.patch"
if patch --dry-run --batch --forward -d "$kernel_dir" -p1 < "$compatibility_patch" >/dev/null 2>&1; then
  patch --batch --forward -d "$kernel_dir" -p1 < "$compatibility_patch"
else
  patch --dry-run --batch --reverse -d "$kernel_dir" -p1 < "$compatibility_patch" >/dev/null
fi
grep -q 'is_misc_rndis(&intf->cur_altsetting->desc)' "$kernel_dir/drivers/net/usb/cdc_ether.c"
grep -q 'USB_INTERFACE_INFO(USB_CLASS_MISC, 4, 1)' "$kernel_dir/drivers/net/usb/rndis_host.c"
