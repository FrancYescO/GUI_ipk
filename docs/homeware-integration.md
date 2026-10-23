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

Assembly run [39977638070](https://github.com/FrancYescO/GUI_ipk/actions/runs/39977638070)
passed feed, payload, Asterisk dependency and versioned kernel checks. It
contains 5,500 names in the shared userspace sections and 5,596 IPKs overall.

| Generation | Exact names present | Inventory names | Missing | Missing with explicit provider |
| --- | ---: | ---: | ---: | ---: |
| 18 | 3,954 | 4,066 | 112 | 6 |
| 19 | 342 | 494 | 152 | 0 |

The 112 unmatched generation-18 names comprise 104 legacy Asterisk names,
six DDNS aliases declared by current packages, `libgomp`, and one translation
template that should not be packaged. These counts do not imply compatibility
between old Asterisk modules and Asterisk 20, or between distinct library ABIs.

The candidate occupies 1,063,287,580 bytes (about 1,014 MiB), close to the
hosting limit. A GNU TAR fixture with identical file names and sizes measured
1,067,642,880 bytes, leaving 6,098,944 bytes below the deployment action's 1 GiB
threshold. The workflow measures the real TAR and blocks publication above
that threshold while retaining the complete downloadable build artifact.
The native GCC repair is a separate build and is not included
in this verified candidate. Publication has not been enabled for these runs.

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
cross-build; the repaired recipe outputs still require CI verification.

Manual-only kernel packages remain distinct from generic `kmod-*` names.
Their presence does not automatically satisfy application dependencies.
The report also lists version checks separately from unavailable names.

For the current candidate, 15 versioned dependency groups use exactly the
explicit version available and can be checked without approximating version
ordering. Other comparisons remain listed for review. Unversioned virtual
providers are not assumed to satisfy versioned dependencies.

The native GCC CRT repair maps the older ARM target section definitions to
the private names introduced in GCC 5, only for ARM GCC 4.8. A local source
check reproduced the unpatched failure, compiled all four begin/end and
normal/PIC combinations, and verified emitted init/fini array sections using
an ARM EABI header fixture. The full configured cross-build remains required.
