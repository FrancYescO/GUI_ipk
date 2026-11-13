#!/bin/sh
# Audited migration of a complete standard kernel package. No dependency bypass.
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
        --*) exit 2 ;;
        *) package=$1; shift; [ $# = 0 ] || exit 2 ;;
    esac
done
: "${package:?Usage: migrate-standard-kernel-package.sh [--apply] [--ipk FILE] PACKAGE}"
case "$package" in kmod-*[!a-zA-Z0-9_+.-]*|'') exit 2 ;; kmod-*) ;; *) exit 2 ;; esac
run_opkg() {
    if [ -n "$root" ]; then
        [ -n "$config" ] || exit 2
        "$opkg_bin" --offline-root "$root" -f "$config" "$@"
    else
        "$opkg_bin" "$@"
    fi
}
work=$(mktemp -d /tmp/gui-ipk-standard.XXXXXX)
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
[ "$(field Package)" = "$package" ] && [ "$(field X-Standard-Kernel-Package)" = yes ] || exit 1
[ "$(field X-Kernel-OPKG-Metadata)" = 6 ] || exit 1
required=$(field Depends | sed -n 's/.*kernel (= \([^)]*\)).*/\1/p')
metadata=$(run_opkg status kernel)
printf '%s\n' "$metadata" | grep -q '^Status:.* installed' || exit 1
installed=$(printf '%s\n' "$metadata" | sed -n 's/^Version: //p')
[ -n "$required" ] && [ "$required" = "$installed" ] || { echo 'Kernel ABI mismatch' >&2; exit 1; }
release=$(field X-Kernel-Profile | cut -d- -f1)
[ -n "$root" ] || [ "$(uname -r)" = "$release" ] || exit 1
field X-Payload-Checksums | tr ',' '\n' | sed 's/^ *//' > "$work/checksums"
field X-Payload-Symlinks | tr ',' '\n' | sed '/^ *$/d;s/^ *//' > "$work/symlinks"
# Validate paths before extraction. No scripts, arbitrary files or links outside
# the firmware module/sysctl configuration directories and exact module release.
tar -tzf "$work/data.tar.gz" > "$work/members"
while read -r path; do
    case "$path" in *..*|/*|*[!a-zA-Z0-9_./+-]*) echo 'Unsafe payload path' >&2; exit 1 ;; esac
    case "$path" in
        ./etc/|./etc/modules.d/|./etc/modules-boot.d/|./etc/sysctl.d/|./lib/|./lib/modules/|"./lib/modules/$release/") ;;
        ./etc/modules.d/*|./etc/modules-boot.d/*|./etc/sysctl.d/*.conf|"./lib/modules/$release/"*.ko)
            name=${path#./}
            cut -d: -f2 "$work/checksums" | grep -Fxq "$name" || cut -d: -f1 "$work/symlinks" | grep -Fxq "$name" || exit 1 ;;
        *) echo "Unsupported payload: $path" >&2; exit 1 ;;
    esac
done < "$work/members"
[ -z "$(sort "$work/members" | uniq -d)" ] || exit 1
while IFS=: read -r hash path; do
    [ -n "$hash" ] || continue
    case "$hash" in *[!0-9a-f]*) exit 1 ;; esac
    [ ${#hash} = 64 ] || exit 1
    tar -xOzf "$work/data.tar.gz" "./$path" > "$work/file"
    [ "$(sha256sum "$work/file" | cut -d' ' -f1)" = "$hash" ] || exit 1
    case "$path" in
        *.ko)
            module=${path##*/}; module=${module%.ko}
            module=$(printf '%s' "$module" | tr '-' '_')
            [ ! -d "$root/sys/module/$module" ] || { echo "Module active: $module; quiesce consumers before migration" >&2; exit 1; } ;;
    esac
done < "$work/checksums"
mkdir -p "$work/payload/etc/modules-boot.d"
while IFS=: read -r path target; do
    case "$path" in etc/modules-boot.d/*) ;; *) exit 1 ;; esac
    link=${target#../modules.d/}
    case "$link" in *[!a-zA-Z0-9_.+-]*|*..*|'') echo 'Unsupported payload symlink' >&2; exit 1 ;; esac
    [ "$target" = "../modules.d/$link" ] || exit 1
    tar -xzf "$work/data.tar.gz" -C "$work/payload" "./$path"
    [ "$(readlink "$work/payload/$path")" = "$target" ] || exit 1
done < "$work/symlinks"
allowed=" $package $(field X-Previous-Module-Packages | tr ',' ' ') "
while read -r member; do
    case "$member" in */) continue ;; esac
    path=${member#./}
    owners=$(run_opkg search "$root/$path" 2>/dev/null | sed -n 's/ - .*//p' || true)
    for owner in $owners; do
        case "$allowed" in *" $owner "*) ;; *) echo "Unrelated owner $owner for $path" >&2; exit 1 ;; esac
    done
done < "$work/members"
if [ "$apply" != yes ]; then
    echo "Verified $package; migration ready (--apply required)"
    exit 0
fi
MODGUI_KERNEL_MIGRATION="$package" run_opkg --force-overwrite --force-reinstall install "$ipk"
while IFS=: read -r hash path; do
    [ -n "$hash" ] || continue
    [ "$(sha256sum "$root/$path" | cut -d' ' -f1)" = "$hash" ] || exit 1
done < "$work/checksums"
echo "Verified complete package and file ownership: $package"
