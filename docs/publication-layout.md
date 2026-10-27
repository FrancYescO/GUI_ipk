# Public OPKG publication

Pages hosts the six main userspace feeds (`base`, `luci`, `packages`, `routing`,
`telephony`, `target/packages`) and a unified searchable catalog. All thirteen
verified application updates, including ADB, Tailscale and rclone, are promoted
into those feeds without changing the IPK bytes.

Three coherent components use GitHub Releases: kernel modules, Asterisk 20,
and FreeSWITCH sound packages. Releases are never divided into numbered asset
batches. The initial inventory retains 6,057 catalog records: 5,533 IPKs on
Pages (about 693 MiB), 491 kernel IPKs, 25 Asterisk IPKs and 8 sound IPKs.
FreeSWITCH sounds alone account for about 387 MiB. `feeds.json` and
`opkg-userspace.conf` expose the current source URLs; the catalog links directly
to the correct storage location.

## Kernel selection and existing clients

The kernel release contains all three runtime ABI profiles. `Packages.gz`
exposes only the 59 runtime packages. The 432 staging-only candidates remain
available as individual assets, in `Candidates` and in the web catalog, but are
excluded from automatic OPKG selection. Matching a kernel version alone is not
sufficient: use the complete `kernel` package version in `profiles.json`.
Firmware with the same ABI still requires runtime validation. No USB traffic
claim is made: CDC/RNDIS load, registration, unload and restoration were tested;
no tethering device was available.

The historical generic `kernel/4.1.38` buildroot has no identified compatible
firmware. Its 24 packages remain in `legacy-buildroot.tar.gz` for reproducibility,
without an active OPKG source. Existing Pages kernel and Asterisk source URLs
must be replaced with the URLs in `feeds.json`; HTML catalog pages cannot
redirect OPKG downloads. Existing GUI versions that generate the old sources
need their source configuration updated; publication does not patch the GUI.

Download `feeds.json` and `print-opkg-sources.sh` from Pages using a TLS-capable
client, then run `sh print-opkg-sources.sh feeds.json` on the router to print the
proposed sources. `--asterisk20` adds the optional Asterisk source. The helper
adds the kernel source only on an exact installed kernel-package match and
never writes configuration. Review its output and replace obsolete GUI source
entries before running `opkg update`.

Legacy firmware wget may fail on GitHub Release downloads. Put
`opkg-release-wget.sh` in a private directory under the name `wget`, mark it
executable, and invoke OPKG with `PATH=/path/to/private-bin:$PATH`. The wrapper
uses `/usr/bin/curl` with normal certificate verification. If the router's CA
store is obsolete, transfer a current trusted CA bundle and set
`CURL_CA_BUNDLE=/path/to/cacert.pem`; do not disable TLS verification. This does
not replace the global wget. A private-root OPKG update/download test on `.69`
verified Release transport and the downloaded SHA256 without installing a
package or changing system OPKG sources.

## Reproducibility and publication order

`publish-opkg-feed.yml` is the only Pages publisher. It restores userspace from
`publication.json.gz`, using a hash-verified content-addressed cache. On the
first migration only, a missing live manifest falls back to the committed
`build/publication/bootstrap.json.gz`. It preserves live versions rather than
requiring expiring Actions artifacts. Explicit complete userspace builds can
replace the baseline after successful-run provenance checks. OpenVPN snapshots
and all pinned application updates are overlaid before publication.

`prepare-publication.py` rebuilds kernel feeds from committed artifacts and
candidate bundles, running their strict validators. Original source recipes,
toolchains and build-input releases remain available. Historical internal input
tags are preserved to avoid breaking pinned builds. `application-packages-v1`
is retained as a verified update input, rather than advertised as an extra feed.

The uploader verifies every local size/SHA256, creates drafts, resumes missing
uploads, rejects conflicting assets, then publishes complete releases before
Pages deployment. Existing published component releases are immutable. PR runs
prepare and validate without publishing. Full userspace builds retain complete
inputs and trigger this publisher; they cannot independently deploy the old
oversized layout. `publication.json.gz`, provenance, checksums and compatibility
reports make the chosen storage and package bytes auditable.
