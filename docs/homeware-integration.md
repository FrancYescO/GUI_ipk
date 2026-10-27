# Userspace feed integration

The comparison baseline in `build/homeware/catalog.tsv` records 4,562 package
files across the Homeware 18 and 19 generations. Reports compare exact package
names against all six userspace feed sections. Reports also list explicit OPKG
`Provides` declarations in `provided_by`, without changing exact-name counts
or assuming version/runtime equivalence. They preserve underscores and
distinguish library ABI suffixes. Generation labels alone do not establish
kernel ABI compatibility; kernel modules must match the installed firmware.

The imported recipes for `banip`, `https-dns-proxy`,
`luci-app-https-dns-proxy` and `luci-compat` retain their upstream files.
`build/homeware-overlay/SOURCES.json` pins the official OpenWrt revisions;
`SHA256SUMS` verifies the imported bytes. Loose LuCI translation templates do
not produce language packages.

Compatibility patches support the existing GCC 4.8 toolchain and vendor switch
headers. Mixed userspace/kernel recipes retain kernel metadata while userspace
builds skip module compilation and packaging. These changes do not establish
runtime compatibility on every router.

## Incremental assembly

The manual userspace workflow accepts `reuse_run_id` for a completed full build
and `repair_run_ids` for up to eight targeted builds. Assembly waits for each
repair run and stops if any fails; only successful outputs can be applied. This allows
corrected packages to be assembled with existing shard outputs. For a branch
validation run, leave `package_targets` and `shard_index` empty and set
`publish_pages=false`. The optional `asterisk_reuse_run_id` can reuse either a
successful targeted Asterisk build or a completed run with a successful
Asterisk feed job and its assembled artifact. Other shard failures do not
invalidate that successful job. Source workflow, repository and revision
ancestry are checked; the final assembly checks Asterisk dependencies against
the shared feed.

Repair downloads verify the source repository, workflow, successful completion
and revision ancestry. Assembly checks package metadata, architecture and
payloads, rejects kernel payloads, and preserves baseline package versions.
The workflow regenerates indexes and verifies the resulting feed. Its artifacts
include `repairs-report.md` and `homeware-coverage.{csv,json,md}`.

A failed compile shard can still contain usable packages. The aggregate report
records shard failures separately from the verified packages available in the
assembled feed. Review the coverage and repair reports before publication.

## Remaining compatibility work

Legacy Asterisk package names, renamed DDNS providers and firmware variants
need individual review. Native GCC and packages requiring a newer C++ compiler
need successful cross-builds before inclusion. The dedicated Asterisk 20 feed
has separate dependency checks and does not automatically satisfy legacy
Asterisk package names. Missing names remain visible in coverage reports.

## Verified candidate, 23 October 2026

Assembly run [39994950251](https://github.com/FrancYescO/GUI_ipk/actions/runs/39994950251)
passed feed, payload, Asterisk dependency and versioned kernel checks. It
contains 5,501 names in the shared userspace sections and 5,597 IPKs overall.

| Generation | Exact names present | Inventory names | Missing | Missing with explicit provider |
| --- | ---: | ---: | ---: | ---: |
| 18 | 3,954 | 4,066 | 112 | 6 |
| 19 | 342 | 494 | 152 | 0 |

The 112 unmatched generation-18 names comprise 104 legacy Asterisk names,
six DDNS aliases declared by current packages, `libgomp`, and one translation
template that should not be packaged. These counts do not imply compatibility
between old Asterisk modules and Asterisk 20, or between distinct library ABIs.

The candidate occupies 1,063,428,691 bytes (about 1,014 MiB), close to the
hosting limit. The workflow measures the real TAR and blocks publication above
that threshold while retaining the complete downloadable build artifact.
Native GCC is excluded from the shared profile and this verified candidate. Publication has not been enabled for these runs. The generated dependency
audits contain no unresolved userspace dependency names. Kernel dependencies
and the remaining version-order check are recorded separately.

## Declared dependency audit

`report-feed-dependencies.py` reads the six shared indexes plus explicitly
selected extra feeds. CI writes separate reports under `dependencies-4.1.38/`
and `dependencies-4.1.52/`. It recognizes alternatives and declared providers,
keeps version constraints for review, and never supplies modules from the
other kernel profile. The dedicated Asterisk feed retains its own checks.

The 5,500-name candidate audit found two unresolved userspace dependency
names: `giflib-utils` for `ddns-scripts-cnkuai`, and `gnu-wget` for `acme`.
The repair packages the eight existing giflib tools and declares `gnu-wget`
only on the TLS-enabled GNU Wget variant. The eight tools passed a local ARM
cross-build and the repaired recipes passed targeted CI in run
[39994353632](https://github.com/FrancYescO/GUI_ipk/actions/runs/39994353632).

Manual-only kernel packages remain distinct from generic `kmod-*` names.
Their presence does not automatically satisfy application dependencies.
The report also lists version checks separately from unavailable names.

For the current candidate, 15 versioned dependency groups use exactly the
explicit version available and can be checked without approximating version
ordering. Other comparisons remain listed for review. Unversioned virtual
providers are not assumed to satisfy versioned dependencies.

Native GCC is explicitly excluded from the shared profile. The pinned GCC 4.8
cross-toolchain and runtime libraries remain enabled. The incomplete compiler
bootstrap investigation is preserved on the separate
[`codex/native-gcc-bootstrap` branch](https://github.com/FrancYescO/GUI_ipk/tree/codex/native-gcc-bootstrap),
and is not part of this feed integration. Assembly rejects accidental native
compiler IPKs. A newer suitable bootstrap compiler is needed before publishing
that experiment.

## Published feed, 24 October 2026

[Publication 40085533067](https://github.com/FrancYescO/GUI_ipk/actions/runs/40085533067)
preserves all 5,501 shared userspace names and publishes 50 kernel packages for
4.1.52. Coverage and the 4.1.52 dependency audit were independently recomputed
from the public indexes and match the published reports. The final publisher
now regenerates both kernel-profile audits after adding SPU and RNDIS packages.

[Incremental publication 40087647605](https://github.com/FrancYescO/GUI_ipk/actions/runs/40087647605)
adds `libgomp` 4.8.3-1, bringing the shared feed to 5,502 names. The published
IPK's SHA-256 matches the CI artifact tested with an ARM OpenMP parallel
reduction under QEMU. Generation 18 now has 3,955/4,066 exact names present,
with 111 missing. Generation 19 remains at 342/494 before the translation batch.
The packaged runtime also passed the four-thread reduction on a VBNTJ router
with Linux 4.1.52 and glibc 2.27. The library and test executable were extracted
under `/tmp` and removed afterward. Boot ID and kernel taint remained unchanged,
with no new kernel Oops, BUG or panic messages. This verifies the smoke test on
that firmware, not prolonged stability or all OpenMP applications.

With the verified translation batch applied, the shared feed contains 5,536
names. Generation 19 reaches 376/494 exact names, leaving 118 missing;
generation 18 remains at 3,955/4,066, with 111 missing. The candidate indexes
were checked using the same coverage reporter before incremental publication.

The remaining exact-name gaps can be grouped as follows. These are inventory
categories, not assertions that packages with different names are equivalent.

| Remaining category | Generation 18 | Generation 19 |
| --- | ---: | ---: |
| Legacy Asterisk | 104 | 22 |
| Libraries and runtimes | 0 | 34 |
| LuCI translations | 0 | 38 |
| LuCI/web stack | 0 | 16 |
| CUPS printing applications | 0 | 4 |
| Rclone and interfaces | 0 | 4 |
| DDNS names with declared providers | 6 | 0 |
| Translation template | 1 | 0 |

The runtime recipe in `build/libgomp-overlay` builds OpenMP with the existing
cross-compiler and retains the disabled native compiler. Distinct library ABIs
and the newer LuCI/web stack require their own compatibility work.

`build/luci-translations-overlay` supplies 34 nonempty official dictionaries
for existing applications. Run
[40096559656](https://github.com/FrancYescO/GUI_ipk/actions/runs/40096559656)
produced 250 targeted IPKs, including all 34 new names. Existing package versions
and architectures are preserved. Every new LMO payload matches the legacy
generator's output; the parser binary matches the one tested on the router,
where the private Italian catalog translated `Services` to `Servizi`.

The overlay excludes eight dictionaries with no translated messages and one
identity-only dictionary that produces no LMO. It maps language identifiers to
the legacy framework and preserves partial translation coverage. The build
invalidates stale LuCI scan metadata and checks that all imported names are
declared and selected by the full profile before compilation.

## Inspected router dependency availability

The pre-existing package database on the inspected VBNTJ contains 52 exact
names that the 4.1.52 feed-only audit marks as missing. Adding those installed
names to a local audit reduces unresolved kernel dependency groups from 192
to 106. This checks name availability on that device; it does not audit the
firmware's own dependency closure or verify every module's functionality.
The `tun` module is present and loaded even though the generic `kmod-tun`
package marker is absent. Manual feed packages retain their distinct names;
no generic kernel providers are inferred from these observations.

The remaining version check for `dovecot-pigeonhole` was reviewed using the
router's OPKG comparator: `dovecot` 2.2.36.4-1 satisfies the required
`>= 2.2.36.4`. The automatic reporter intentionally retains its conservative
version-check classification.

## Published application inputs

All thirteen verified application updates are included in the main Pages
`base` and `packages` feeds. Their original build provenance, versioned Pages
URLs and SHA256 pins remain in `build/application-archive/manifest.json`.
The seven former `extras-*` Releases and the duplicate consolidated application
release are superseded by these main feeds.

See [publication layout](publication-layout.md) for current source URLs and
verified TLS downloader instructions. Keeping only the large
FreeSWITCH sound packages in a binary Release leaves room for all application
updates, kernel profiles and Asterisk 20 on Pages (about 700 MiB).
The preparation workflow retains targeted build artifacts for review; future
promotions update the pinned package registry and the main feeds.

## Published optional Rclone feed

Targeted run
[40138032911](https://github.com/FrancYescO/GUI_ipk/actions/runs/40138032911)
produced `rclone`, `rclone-config`, `rclone-ng` and `rclone-webui-react`.
The runtime is upstream 1.75.2, replacing the inventory's older 1.57.0;
the two interfaces retain versions 0.5.0 and 2.0.5. All packaged interface files
match the SHA256-pinned upstream release archives byte for byte.

The runtime was compiled by the isolated Go 1.26.10 toolchain with
`CGO_ENABLED=0` and `GOARM=7,softfloat`. Its ARM EABI5 ELF has no dynamic loader
or dynamic library dependencies. The inspected BCM963138 reports ARMv7 but no
VFP/NEON features, so hardware floating point is deliberately avoided.

On the VBNTJ running Linux 4.1.52, the extracted CI binary copied and checked
three local files, including an empty file and binary data. Authenticated RC
calls to version, remote enumeration and local directory listing succeeded;
unauthenticated calls returned HTTP 401. Both interfaces served their original
index bytes. A public HTTPS download through Rclone, using a temporary current
CA bundle, matched the expected SHA256. Temporary files were removed; the boot
ID and kernel taint were unchanged. No package, user, service or persistent
configuration was installed. Real cloud accounts, FUSE mounts, a persistent
procd installation and a physical 4.1.38 device have not been tested.

The runtime binary alone is 79,238,320 bytes (75.6 MiB). The inspected root has
about 29 MiB free, so permanent installation needs suitable external storage
or another destination with enough space. The service package defaults to
disabled and requires credentials before enabling its loopback-only listener.

Run
[40174844214](https://github.com/FrancYescO/GUI_ipk/actions/runs/40174844214)
originally published the four packages, now retained in the main
[Pages packages feed](https://francyesco.github.io/GUI_ipk/packages/).
All four public IPKs were downloaded independently and matched the verified
build hashes. The plain and compressed indexes agree, and all index entries,
sizes and SHA256 values match the published package manifest. The package
assets total 36,477,076 bytes.

OPKG source:

```text
src/gz modgui_packages https://francyesco.github.io/GUI_ipk/packages
```

Use a working TLS downloader and current certificates as described above.
Adding the source or installing packages is a separate device administration
step; publication did not change any router configuration.

The Rclone-only coverage audit originally reported 5,540 distinct package
names and generation-19 coverage of 380/494 (114 missing). These are historical
measurements. Rclone and the other verified updates now belong to the main
feeds. Their recipes still use explicit targeted builds; the centralized
publisher preserves the verified updates over complete legacy userspace builds.
See [application updates](application-updates.md#published-application-updates)
for the preserved versions and runtime validation limits.
