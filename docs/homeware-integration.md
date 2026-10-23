# Userspace feed integration

The comparison baseline in `build/homeware/catalog.tsv` records 4,562 package
files across the Homeware 18 and 19 generations. Reports compare exact package
names against all six userspace feed sections. They preserve underscores and
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
