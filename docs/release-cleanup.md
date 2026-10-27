# Release retention

Kernel module packages and candidate diagnostics are published in their OPKG
feeds. The following duplicate binary Releases are removed after the feed
publisher has been verified without them:

- `kernel-4.1.38-candidates-a94ca43`
- `kernel-4.1.38-vbnts-candidates-d399eee`
- `damson-4.1.52-manual-f7ba516`
- `damson-4.1.52-manual-1587d4a`
- `damson-4.1.52-manual-d56c283`
- `damson-spu-4.1.52-c3a4dae`

The candidate IPKs, manifests, configs and build logs are preserved in pinned
repository bundles. Current 4.1.52 payloads and their source recipes and
validation records are already committed. The cleanup does not delete Git
source tags or change module payloads.

Retain the three immutable build-input/toolchain Releases: the legacy 4.1.38
build inputs, the 4.1.52 GPL inputs, and the GCC 5.5.0 compiler seed. Their
historical tag names remain stable for reproducibility; their visible titles
use the kernel version. They are required by rebuild workflows.

The seven former optional application feed Releases were first consolidated
into `application-packages-v1`. All thirteen packages have since been promoted
into the main Pages feeds and independently downloaded with matching SHA256
values. CI now pins their versioned Pages URLs; the duplicate application
release can be deleted after deploying that configuration.

The kernel and Asterisk 20 binary releases are superseded by their Pages
feeds. Remove those duplicates only after the new Pages deployment and indexes
are verified. FreeSWITCH sounds remains the only binary package Release because
of its size. The three source/SDK/toolchain input releases remain necessary for
CI. Original application build provenance and hashes remain committed in
`build/application-archive/manifest.json` and `build/application-archive/source.json`.
