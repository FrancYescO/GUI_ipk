#!/bin/sh
# Controlled ownership repair for one exact-ABI, one-module IPK.
set -eu
apply=no
root=
config=
ipk=
opkg_bin=${OPKG_BIN:-opkg}
while [ $# -gt 0 ]; do
 case "$1" in
  --apply) apply=yes; shift ;;
  --offline-root) root=$2; [ "$root" != / ] && [ -d "$root" ] || exit 2; shift 2 ;;
  --config) config=$2; shift 2 ;;
  --ipk) ipk=$2; shift 2 ;;
  --*) echo 'Unknown option' >&2; exit 2 ;;
  *) package=$1; shift; [ $# = 0 ] || exit 2 ;;
 esac
done
: "${package:?Usage: migrate-kernel-package.sh [--apply] [--ipk FILE] ABI_SPECIFIC_PACKAGE}"
case "$package" in kmod-*[!a-zA-Z0-9+.-]*|'') exit 2 ;; kmod-*) ;; *) exit 2 ;; esac
run_opkg() {
 if [ -n "$root" ]; then
  [ -n "$config" ] || { echo 'Offline tests require an explicit config' >&2; return 2; }
  "$opkg_bin" --offline-root "$root" -f "$config" "$@"
 else
  "$opkg_bin" "$@"
 fi
}
work=$(mktemp -d /tmp/gui-ipk-kmod.XXXXXX)
trap 'rm -rf "$work"' EXIT HUP INT TERM
if [ -z "$ipk" ]; then
 (cd "$work"; run_opkg download "$package")
 set -- "$work"/*.ipk
 [ $# = 1 ] && [ -f "$1" ] || exit 1
 ipk=$1
fi
tar -xOzf "$ipk" ./control.tar.gz > "$work/control.tar.gz"
tar -xOzf "$work/control.tar.gz" ./control > "$work/control"
tar -xOzf "$ipk" ./data.tar.gz > "$work/data.tar.gz"
field() { sed -n "s/^$1: //p" "$work/control"; }
[ "$(field Package)" = "$package" ] || { echo 'Unexpected package identity' >&2; exit 1; }
case "$(field X-Kernel-OPKG-Metadata)" in 1|2) ;; *) echo 'Use a normalized kernel IPK' >&2; exit 1 ;; esac
required=$(field Depends | sed -n 's/.*kernel (= \([^)]*\)).*/\1/p')
installed=$(run_opkg status kernel | sed -n 's/^Version: //p')
[ -n "$required" ] && [ "$required" = "$installed" ] || { echo 'Kernel ABI mismatch' >&2; exit 1; }
module_path=$(field X-Module-Path)
expected=$(field X-Module-SHA256)
release=$(field X-Kernel-Vermagic | cut -d' ' -f1)
[ -n "$root" ] || [ "$(uname -r)" = "$release" ] || exit 1
module=$(basename "$module_path" .ko)
case "$module" in ''|*[!a-zA-Z0-9_-]*) echo 'Invalid module name' >&2; exit 1 ;; esac
[ "$module_path" = "/lib/modules/$release/$module.ko" ] || { echo 'Staging-only or unexpected module path' >&2; exit 1; }
case "$expected" in *[!0-9a-f]*|'') exit 1 ;; esac
[ "${#expected}" = 64 ] || exit 1
# --force-overwrite will apply only to this single audited file, never arbitrary IPK data.
for member in $(tar -tzf "$work/data.tar.gz"); do
 case "$member" in ./lib/|./lib/modules/|"./lib/modules/$release/"|".$module_path") ;; *) echo "Unexpected payload: $member" >&2; exit 1 ;; esac
done
tar -xOzf "$work/data.tar.gz" ".$module_path" > "$work/module.ko"
[ "$(sha256sum "$work/module.ko" | cut -d' ' -f1)" = "$expected" ] || { echo 'Module checksum mismatch' >&2; exit 1; }
[ ! -d "$root/sys/module/$(printf '%s' "$module" | tr '-' '_')" ] || {
 echo 'Module is active: quiesce its consumers and review unloading before migration' >&2
 exit 1
}
if [ "$apply" != yes ]; then
 echo "Verified $package for kernel $installed; migration ready (--apply required)"
 exit 0
fi
run_opkg --force-overwrite --force-reinstall install "$ipk"
for alias in $(field X-Canonical-Provider-Packages | tr ',' ' '); do
 run_opkg install "$alias"
done
[ "$(sha256sum "$root$module_path" | cut -d' ' -f1)" = "$expected" ] || { echo 'Installed module checksum differs; migration incomplete' >&2; exit 1; }
echo "Verified module file and OPKG ownership updated: $package"
