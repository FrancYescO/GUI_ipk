# Public OPKG publication

Pages hosts the six main userspace feeds (`base`, `luci`, `packages`, `routing`,
`telephony`, `target/packages`), Asterisk 20, eight installable exact-ABI kernel profiles with historical candidate URL aliases. Only the eight large FreeSWITCH sound
packages use a binary Release feed (about 387 MiB).

The catalog contains 7,275 records: 7,267 are on Pages, including 1,709 kernel
module/capability IPKs; eight FreeSWITCH sound packages use Release. Kernel ELF
payloads are unchanged by the standard-path repack. `feeds.json` lists each
source, while descriptions and validation reports distinguish hardware tests
from offline checks.

## Kernel feeds and ABI selection

The [kernel overview](https://francyesco.github.io/GUI_ipk/kernel/) shows each
source, required kernel-package version, reference firmware and validation
status. Kernel release alone, such as `uname -r`, does not identify the ABI.

| Pages path | Reference device / firmware | IPKs | Use |
|---|---|---:|---|
| `kernel/4.1.38-vbnto` | DGA4131FWB / VBNT-O, 18.3.n.0439 | 223 | Installable modules; per-module test levels differ |
| `kernel/4.1.38-vbntk` | DGA4132 / VBNT-S, 18.3.k.0451 | 214 | Installable modules; per-module test levels differ |
| `kernel/4.1.52-vbntk` | DGA4130 / VBNT-K, 19.4.1051-3401200 | 50 | Installable modules; per-module test levels differ |
| `kernel/4.1.38-vbnto-candidates` | VBNT-O ABI above | — | Historical alias of the canonical ordinary feed |
| `kernel/4.1.38-vbntk-candidates` | VBNT-S ABI above | — | Historical alias of the canonical ordinary feed |

Five additional ordinary feeds are available: `kernel/4.1.52-vcnt3`,
`kernel/4.1.52-vcnt2`, `kernel/4.1.52-vcntj`, `kernel/4.1.52-vcnta`, and
`kernel/4.1.52-vbntv`. They contain 50/50/50/49/49 physical module packages
including cryptodev, plus complete capabilities. VCNT-2/J use arm_cortex-a7;
VCNT-3/A and VBNT-V use arm_cortex-a9. Telstra TUN is built in.

All five sources participate in exact-ABI automatic selection. Modules install
under `/lib/modules/4.1.52/` with no automatic loading. VCNT-3 CDC/RNDIS has
USB-binding/DHCP hardware evidence; the other modules retain offline labels.
All former `-candidates` URLs, including 4.1.38, are aliases of ordinary feeds.
The 4.1.38 feeds contain 223 and 214 unique module payloads after duplicate consolidation. Stock ownership and dependency checks
remain enforced; xt_nat is withheld. See [firmware feeds](firmware-kernel-candidates.md).

## Reproducibility and release retention

`publish-opkg-feed.yml` is the only Pages publisher. It restores complete
userspace from `publication.json.gz`, using a hash-verified content-addressed
cache. A missing live manifest falls back to the committed bootstrap. Explicit
complete userspace builds are accepted after successful-run provenance checks.
OpenVPN snapshots and all pinned application updates are overlaid before
publication. Application inputs use versioned Pages URLs and pinned hashes.

`prepare-publication.py` rebuilds all kernel indexes from committed verified
artifacts and candidate bundles. Candidate diagnostics, compatibility reports
and the historical buildroot archive are hosted on Pages beside the feeds.
Full userspace builds produce inputs for this single publisher and cannot
independently deploy an obsolete layout. PR runs prepare and validate without
publishing. The FreeSWITCH release uploader verifies all hashes, resumes drafts
and rejects conflicting assets before Pages deployment.

Three source/SDK/toolchain releases remain required by CI: legacy kernel build
inputs, 4.1.52 GPL inputs and the GCC compiler seed. They are not user-installable
package feeds. Their historical tags remain stable for reproducibility. After
retiring duplicate kernel and Asterisk binary releases, FreeSWITCH sounds is the
only binary package Release; the three CI input releases remain separate.

VBNT-K is the canonical public feed name: `kernel/4.1.38-vbntk` and
`kernel/4.1.52-vbntk`. The corresponding versioned `vbnts` URLs are OPKG aliases
serving real indexes with relative paths to the canonical IPKs. The 4.1.38
candidate feed follows the same convention. Unversioned device aliases are removed.
Package names, payloads, exact ABI dependencies and original validation evidence
are unchanged; the 4.1.38 reference test device remains VBNT-S.

Conntrack in the VBNT-K 4.1.52 runtime-profile feed is revision `4.1.52-2`: SDK-only Altibox imports were removed. This replacement has offline symbol checks only; its historical busy probe is preserved separately.
