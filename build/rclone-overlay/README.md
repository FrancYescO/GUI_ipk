# Rclone userspace overlay

This overlay adds four names from the generation-19 inventory. The runtime is
upstream Rclone 1.75.2; it supersedes the inventory's 1.57.0. The Angular and React
interfaces retain their upstream release versions 0.5.0 and 2.0.5.

Rclone requires a newer Go compiler than the archived feed's Go 1.10. Its recipe
extracts a SHA256-pinned Go 1.26.10 Linux/amd64 host toolchain inside its build
directory. Other Go recipes are unchanged. Go modules are resolved using the
pinned upstream go.mod/go.sum with readonly module mode and checksum database
verification. The target is Linux ARMv7, CGO disabled, with paths and build IDs
removed and self-update disabled. Go 1.26 requires Linux 3.2 or later according to
[the supported platform requirements](https://go.dev/wiki/MinimumRequirements).
The Linux CI runner builds the packages with the existing OpenWrt packaging tools.

`rclone-config` supplies an initially disabled procd service. Enabling it requires
setting a nonempty username and password in `/etc/config/rclone`. The remote
control listener binds to `127.0.0.1`, runs as `rclone`, and uses the persistent
`/etc/rclone/rclone.conf`. It starts no cloud transfer automatically. The optional
`interface` value is empty, `ng` or `react`; the selected interface must be
installed before starting the service. Use an SSH tunnel for access from another
machine. No firewall or network configuration is installed.

Both interfaces install immutable upstream release assets beneath separate
`/usr/share/rclone` directories. Their original MIT licenses and bundled third
party notices are preserved. Releases and license source revisions are pinned
in `SOURCES.json`; local overlay files are covered by `SHA256SUMS`.

Cloud HTTPS connections require a current trusted CA store. An older firmware
bundle can reject current server certificates; a temporary `SSL_CERT_FILE` can
be used for an isolated test. FUSE and its helper are needed only for `mount`.
The runtime does not force the feed's `fuse-utils` dependency chain because its
generic `kmod-fuse` marker is absent on some supported firmware. This overlay
neither supplies a kernel alias nor enables a mount. Check kernel support and
matching helper availability before using that command.

Build these three recipe targets together:

```
feeds/packages/rclone feeds/packages/rclone-ng feeds/packages/rclone-webui-react
```

Distribute the resulting packages through an optional release snapshot; they
are excluded from the shared Pages assembly by its size limit until a separate
storage migration is implemented.
