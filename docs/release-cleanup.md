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

The seven former optional application feed Releases were subsequently
consolidated into `application-packages-v1`. It preserves all 13 original IPKs,
original source manifests and a common OPKG index. The seven `extras-*`
Releases can therefore be removed after independent archive verification.
There are four retained Releases: three immutable build inputs/toolchains and
one consolidated application package archive.
