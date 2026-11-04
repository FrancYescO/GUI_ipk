#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work_dir="${1:?Usage: apply-luci-update.sh BUILDROOT}"
work_dir="$(cd "$work_dir" && pwd)"

# Fail before changing sources if the snapshot or maintained delta is wrong.
expected_base="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["base_revision"])' "$repo_root/build/luci-update.json")"
actual_base="$(git -C "$work_dir/feeds/luci" rev-parse HEAD)"
[[ "$actual_base" == "$expected_base" ]] || {
  echo "Unexpected archived LuCI revision: $actual_base (expected $expected_base)" >&2
  exit 1
}
(cd "$repo_root" && sha256sum --check build/luci-update.sha256)
# Apply relative to the buildroot even when it lives inside the checkout.
# Otherwise Git discovers the parent repository and silently skips these paths.
gzip -cd "$repo_root/patches/luci-18.06-update.patch.gz" |
  GIT_CEILING_DIRECTORIES="$(dirname "$work_dir")" git -C "$work_dir" apply --whitespace=nowarn -p1 -

# The archived .git database still names the old revision. Pin the displayed
# version as well as the IPK version instead of deriving either from that Git DB.
python3 - "$repo_root/build/luci-update.json" "$work_dir/feeds/luci/luci.mk" <<'PY'
import json
import sys
from pathlib import Path

source = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
path = Path(sys.argv[2])
text = path.read_text(encoding='utf-8')
needle = 'PKG_NAME?=$(LUCI_NAME)\n'
if text.count(needle) != 1:
    raise SystemExit('Unexpected luci.mk package metadata')
text = text.replace(needle, needle + '\nPKG_VERSION?=' + source['package_version'] +
                    '\nPKG_GITBRANCH?=LuCI ' + source['branch'] + ' branch\n', 1)
path.write_text(text, encoding='utf-8')
PY
