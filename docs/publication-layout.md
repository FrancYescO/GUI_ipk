# Public OPKG publication

Pages hosts the six main userspace feeds (`base`, `luci`, `packages`, `routing`,
`telephony`, `target/packages`), Asterisk 20, all three runtime kernel profiles
and two separate candidate feeds. Only the eight large FreeSWITCH sound
packages use a binary Release feed (about 387 MiB).

All 6,145 catalog records are retained: 6,137 IPKs are on Pages, about 700 MiB,
including all thirteen promoted application updates and all 579 kernel IPKs.
Package bytes and SHA256 values are unchanged. `feeds.json` lists every source;
the catalog links directly to Pages or the FreeSWITCH sound release.

## Kernel feeds and ABI selection

The [kernel overview](https://francyesco.github.io/GUI_ipk/kernel/) shows each
source, required kernel-package version, reference firmware and validation
status. Kernel release alone, such as `uname -r`, does not identify the ABI.

| Pages path | Reference device / firmware | IPKs | Use |
|---|---|---:|---|
| `kernel/4.1.38-vbnto` | DGA4131FWB / VBNT-O, 18.3.n.0439 (.45) | 49 | Runtime packages; per-module test levels differ |
| `kernel/4.1.38-vbnts` | DGA4132 / VBNT-S, 18.3.k.0451 (.204) | 49 | Runtime packages; per-module test levels differ |
| `kernel/4.1.52-vbntk` | DGA4130 / VBNT-K, 19.4.1051-3401200 (.69) | 49 | Runtime packages; per-module test levels differ |
| `kernel/4.1.38-vbnto-candidates` | VBNT-O ABI above | 220 | Optional staging only; manual validation |
| `kernel/4.1.38-vbnts-candidates` | VBNT-S ABI above | 212 | Optional staging only; manual validation |

Enable one runtime source only after matching the complete installed `kernel`
package version. Firmware sharing an ABI still needs runtime validation. The
source-selection helper never enables candidate sources. Their packages stage
modules outside boot paths; xt_nat remains withheld. All three runtime profiles publish the same 49 module names. VBNT-O has 14
new functional passes and 30 busy stock modules left unchanged; VBNT-S has 15
new functional passes, one namespace smoke pass and 28 busy stock modules left
unchanged. Both also retain the five previously validated core payloads. See
the per-profile reports for hashes, exact test levels and reused evidence. CDC/RNDIS load, registration, unload and
restoration were tested; USB tethering traffic was not tested.

`kernel/4.1.52` remains an OPKG-compatible alias of `4.1.52-vbntk`, using relative
filenames without duplicating IPKs. The generic `kernel/4.1.38` has no identified
compatible firmware. Its 24 historical packages remain in the Pages
`legacy-buildroot.tar.gz`; it has no active OPKG source.

Kernel and Asterisk sources temporarily pointing at Releases must be replaced
with the Pages URLs in `feeds.json`. The kernel and Asterisk binary Releases can
be removed after the Pages deployment is verified. Existing profile-specific
Pages paths work again; no HTML redirect is required for package downloads.

Download `feeds.json` and `print-opkg-sources.sh` from Pages, then run
`sh print-opkg-sources.sh feeds.json` on the router. It prints userspace sources
and adds exactly the runtime kernel source matching the installed kernel-package
version. `--asterisk20` adds the optional Pages Asterisk source. The helper never
writes configuration. Each profile also has an `opkg.conf`; the root
`opkg-kernel.conf` is an annotated list with sources commented out for selection.

Legacy firmware wget may fail on GitHub downloads, including FreeSWITCH sounds.
Use the private `opkg-release-wget.sh` curl wrapper and a current trusted CA
bundle if needed. Set `CURL_CA_BUNDLE` to the transferred bundle; do not disable
certificate verification or replace global wget. Isolated tests on `.69` used
private OPKG roots, without installing packages or changing system sources.

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

Device aliases `kernel/vbnts` → `kernel/4.1.38-vbnts` and `kernel/vbntk` →
`kernel/4.1.52-vbntk` provide OPKG indexes without duplicating IPKs. Use either
the alias or its canonical feed. Exact kernel ABI dependencies remain unchanged;
the device name does not imply compatibility with every firmware.

Versioned device aliases also serve real OPKG indexes: `kernel/4.1.38-vbntk`
uses the `4.1.38-vbnts` packages, and `kernel/4.1.52-vbnts` uses the
`4.1.52-vbntk` packages. `Packages` and `Packages.gz` are generated files,
not HTML redirects. These aliases retain the canonical feed’s exact kernel ABI
dependency and do not add runtime validation for another firmware.
