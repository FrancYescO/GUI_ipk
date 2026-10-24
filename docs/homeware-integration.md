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

The remaining exact-name gaps can be grouped as follows. These are inventory
categories, not assertions that packages with different names are equivalent.

| Remaining category | Generation 18 | Generation 19 |
| --- | ---: | ---: |
| Legacy Asterisk | 104 | 22 |
| Libraries and runtimes | 0 | 34 |
| LuCI translations | 0 | 72 |
| LuCI/web stack | 0 | 16 |
| CUPS printing applications | 0 | 4 |
| Rclone and interfaces | 0 | 4 |
| DDNS names with declared providers | 6 | 0 |
| Translation template | 1 | 0 |

The runtime recipe in `build/libgomp-overlay` builds OpenMP with the existing
cross-compiler and retains the disabled native compiler. Distinct library ABIs
and the newer LuCI/web stack require their own compatibility work.

`build/luci-translations-overlay` stages 34 nonempty official dictionaries for
existing applications. It excludes eight dictionaries with no translated
messages plus one identity-only dictionary, maps language identifiers to the legacy framework, and preserves
partial translation coverage. These additions require a successful packaged
build and incremental publication before changing the inventory counts above.
