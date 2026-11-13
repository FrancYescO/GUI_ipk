#!/bin/sh
set -eu
ulimit -c 0
fixtures=$1
profile=$2
base=$fixtures/$profile
opkg_bin=${OPKG_BIN:-opkg}
run() { mode=$1; shift; "$opkg_bin" --offline-root "$base/$mode" -f "$base/$mode.conf" "$@"; }
for mode in native legacy; do tar -xzf "$base/$mode-payload.tar.gz" -C "$base/$mode"; done
for mode in clean native legacy wrong; do run "$mode" update; done
for mode in clean native; do
    run "$mode" install fixture-all
    python3 "$fixtures/verify.py" "$base" "$mode"
    echo "PASS $profile: all standard packages $mode installation"
done
if run wrong install fixture-all; then echo 'FAIL wrong ABI accepted' >&2; exit 1; fi
echo "PASS $profile: wrong ABI rejected"
if run legacy install fixture-all; then echo 'FAIL legacy ownership overwritten' >&2; exit 1; fi
first=$(head -n 1 "$base/migration-order")
package=$(tar -xOzf "$base/repo/$first" ./control.tar.gz | tar -xOzf - ./control | sed -n 's/^Package: //p')
path=$(tar -xOzf "$base/repo/$first" ./data.tar.gz | tar -tzf - | sed -n '/[.]ko$/p' | head -n 1)
module=${path##*/}; module=${module%.ko}; module=$(printf '%s' "$module" | tr '-' '_')
before=$(sha256sum "$base/legacy/usr/lib/opkg/status" | cut -d' ' -f1)
if OPKG_BIN="$opkg_bin" sh "$fixtures/migrate.sh" --apply --offline-root "$base/legacy" --config "$base/legacy.conf" --ipk "$base/tampered.ipk" "$package"; then
    echo 'FAIL migration accepted a corrupt payload' >&2; exit 1
fi
test "$(sha256sum "$base/legacy/usr/lib/opkg/status" | cut -d' ' -f1)" = "$before"
mkdir -p "$base/legacy/sys/module/$module"
before=$(sha256sum "$base/legacy/usr/lib/opkg/status" | cut -d' ' -f1)
if OPKG_BIN="$opkg_bin" sh "$fixtures/migrate.sh" --apply --offline-root "$base/legacy" --config "$base/legacy.conf" --ipk "$base/repo/$first" "$package"; then
    echo 'FAIL migration accepted an active module' >&2; exit 1
fi
test "$(sha256sum "$base/legacy/usr/lib/opkg/status" | cut -d' ' -f1)" = "$before"
rmdir "$base/legacy/sys/module/$module"
printf '\nPackage: fixture-unrelated-owner\nVersion: 1\nArchitecture: all\nStatus: install ok installed\n\n' >> "$base/legacy/usr/lib/opkg/status"
printf '/%s\n' "${path#./}" > "$base/legacy/usr/lib/opkg/info/fixture-unrelated-owner.list"
before=$(sha256sum "$base/legacy/usr/lib/opkg/status" | cut -d' ' -f1)
if OPKG_BIN="$opkg_bin" sh "$fixtures/migrate.sh" --apply --offline-root "$base/legacy" --config "$base/legacy.conf" --ipk "$base/repo/$first" "$package"; then
    echo 'FAIL migration accepted an unrelated file owner' >&2; exit 1
fi
test "$(sha256sum "$base/legacy/usr/lib/opkg/status" | cut -d' ' -f1)" = "$before"
run legacy remove fixture-unrelated-owner
while read -r filename; do
    package=$(tar -xOzf "$base/repo/$filename" ./control.tar.gz | tar -xOzf - ./control | sed -n 's/^Package: //p')
    OPKG_BIN="$opkg_bin" sh "$fixtures/migrate.sh" --apply --offline-root "$base/legacy" --config "$base/legacy.conf" --ipk "$base/repo/$filename" "$package"
done < "$base/migration-order"
run legacy install fixture-all
python3 "$fixtures/verify.py" "$base" legacy
run legacy status fixture-existing-consumer | grep -q 'Status:.* installed'
while read -r previous; do run legacy remove "$previous"; done < "$base/previous"
python3 "$fixtures/verify.py" "$base" legacy
echo "PASS $profile: legacy migration preserves consumer, bytes and ownership"
echo "ALL_CASES_PASSED=$profile"
