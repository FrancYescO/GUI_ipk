# Optional application updates

Baseline and upstream releases inspected on 2026-10-25:

| Application | Published baseline | Optional version | Validation state |
|---|---|---|---|
| Transmission | 2.94 | 4.1.4 | Static IPKs, authenticated RPC and web tested on router |
| aria2 | 1.33.0 | 1.37.0 | Static IPK, HTTP/HTTPS and protected RPC tested on router |
| aMule | 2.3.2 | 3.0.0 | Static IPK and authenticated daemon/client tested on router |
| Android Debug Bridge | android.5.0.2_r1 | android.37.0.0p1 | Static IPK and private client/server tested on router |
| Tailscale | Not in the shared feed | 1.104.2 | Static IPK and private userspace daemon tested on router |
| WireGuard tools | 1.0.20260223-2 | Already at inspected upstream release | No tool update needed |

All thirteen verified application packages are now promoted into the main
Pages feeds: Transmission (4), aria2, aMule, ADB, Tailscale, rclone (4) and
libgomp. Their original versions, package bytes, source build provenance and
SHA256 pins are preserved in `build/application-archive/manifest.json`.

## Published application updates

Use the main `base` and `packages` sources listed in
[the public feed manifest](https://francyesco.github.io/GUI_ipk/feeds.json).
No separate optional application source is required. Remove retired
`extras-*` and `application-packages-v1` sources when adopting the new sources.

Kernel modules, Asterisk 20 and FreeSWITCH sounds are stored in coherent
Releases, leaving the six main Pages feeds at about 693 MiB including all
application updates. CI fetches each versioned application URL from Pages and
checks its pinned size and SHA256, independently of the duplicate application
archive. Targeted modern application source recipes remain available for
rebuilds. See [the publication layout](publication-layout.md) for feed selection
and the TLS downloader required by legacy firmware.

## Compatibility boundary

Transmission 4 requires C++17 and newer crypto libraries; aMule 3 requires
wxWidgets 3.2 and Boost; portable ADB 37 uses C++20. aria2 is also built with
a private modern TLS stack. These updates cannot be implemented by relabelling
the shared legacy libraries.

The modern path uses the SHA256-pinned Bootlin ARMv5 EABI musl SDK 2026.08-1
(GCC 15.3.0, musl 1.2.6) and CMake 3.31.8. Applications and their required modern
libraries are built privately and linked statically. The shared glibc, C++ and
crypto packages are not replaced. The SDK's software floating point avoids
assuming VFP/NEON from the feed's architecture name.

An extracted SDK built `tests/modern-cpp-smoke.cpp` on Linux. The resulting
static ARM EABI5 program passed threads, 64-bit atomics, filesystem queries and
monotonic clock checks on the VBNTJ running kernel 4.1.52. Its temporary file was
removed, with unchanged boot ID and taint. This validates the toolchain baseline;
each application still requires its own build and runtime checks.

## Installation space

The raw Transmission payload is about 38.6 MiB for all four packages; the daemon
and web alone are about 6.5 MiB. Tailscale's combined executable is about 35.2
MiB. The tested router reported about 29 MiB free on its writable root filesystem.
Flash compression can change actual consumption, but the temporary RAM tests do
not establish that every package fits in internal storage. Select the required
components and verify available writable space or an external installation
location before deployment.

## Certificate trust

Private TLS libraries still need a current trusted CA store. The legacy
`ca-bundle` package in the shared feed dates from 2019; upgrading OpenSSL alone
does not refresh its certificates. HTTPS smoke tests use a current temporary CA
bundle with certificate verification enabled. A deployment must provide an
up-to-date trust store; these optional application builds do not replace the
router's system trust configuration or disable certificate verification.

## Transmission

Run `40177095441` produced the four 4.1.4-1 packages:
`transmission-daemon-openssl`, `transmission-cli-openssl`,
`transmission-remote-openssl` and `transmission-web`. All six executable files
are static ARM with software floating point, without ELF interpreters or dynamic
dependencies. The private stack uses OpenSSL 3.5.9, curl 8.23.0 and zlib 1.3.2.

On the kernel 4.1.52 router, an isolated daemon accepted the legacy hyphenated
settings format (including `cache-size-mb: 7`). RPC bound to loopback returned
401 without authentication, 409 for the session challenge and a successful
`session-get` with credentials and the session header. The packaged remote
client retrieved session information; all packaged CLI tools reported 4.1.4.
The authenticated web index matched the packaged file byte for byte.

DHT, LPD, PEX, port mapping and uTP were disabled, with peer listeners restricted
to loopback. No torrents or P2P transfers were used. The temporary daemon and
payload were removed; boot ID and kernel taint were unchanged. The existing UCI
configuration/service is retained and defaults to disabled; persistent service
startup and real P2P traffic still need deployment validation. These packages
update the OpenSSL variants; they do not replace the legacy mbedTLS variants.

## aria2

Run `40181376755` produced `aria2_1.37.0-2_arm_cortex-a9_neon.ipk`.
The executable is static ARM with software floating point, without an ELF
interpreter or dynamic dependencies, and uses OpenSSL 3.5.9. Upstream's
`ARIA2_STATIC=yes` mode is enabled; shared-runtime libtool metadata is removed
from the private SDK before building. The fixed profile retains BitTorrent,
GZip, HTTPS and message-digest support, matching the previous default features.
Metalink/XML, SFTP, asynchronous DNS and SQLite cookies are not enabled.

On the kernel 4.1.52 router, a loopback HTTP download matched its source byte for
byte. An HTTPS download from a fixed Git commit also matched an independent curl
download, with certificate verification enabled and a current temporary CA
bundle. A private loopback RPC server rejected requests without its secret and
returned version 1.37.0 and the expected features with the correct token.

No BitTorrent traffic or persistent service startup was tested. The HTTP/RPC
processes and payload were removed, with unchanged boot ID and kernel taint.
The existing UCI service/configuration is retained. The optional static recipe
has a fixed feature profile; it does not expose the legacy build menu toggles.

## aMule

Run `40180412146` produced `amule_3.0.0-1_arm_cortex-a9_neon.ipk`.
`amuled`, `amulecmd` and `amuleweb` are static ARM executables with software
floating point, without ELF interpreters or dynamic dependencies. The private
stack includes wxBase 3.2.12, Boost 1.92.0 and Crypto++ 8.9.0; GD is not needed
for the selected daemon, command client and webserver targets.

On the kernel 4.1.52 router, all three programs reported 3.0.0. The daemon started
with temporary home, configuration, incoming and temporary-file directories;
peer and EC sockets used loopback. eD2K, Kad, automatic connection/reconnection,
server-list/IP-filter/version updates, UPnP and automatic web startup were
disabled. `amulecmd` authenticated to the private EC port and retrieved status
with no P2P connections. `amuled --version` returns 255 after displaying its
version, as expected from upstream's early initialization exit.

The daemon and payload were removed, with unchanged boot ID and kernel taint.
No P2P traffic, persistent installation or live web interface was tested. The
package retains the previous three-program layout and adds no automatic service.

## Android Debug Bridge

Run `40182356876` produced `adb_android.37.0.0p1-1_arm_cortex-a9_neon.ipk`.
The 6,048,932-byte executable is static ARM with software floating point, without
an ELF interpreter or dynamic dependencies. It uses portable android-tools
37.0.0p1, with the Rust mDNS component omitted. The package continues to install
only the host client `/usr/bin/adb`, without `adbd` or automatic startup.

On the kernel 4.1.52 router, `adb version` reported protocol version 1.0.41 and
build 37.0.0p1-android-tools. The client launched its matching server on the
private default-loopback socket `tcp:15037`, retrieved `server-status` and
terminated it. Status identified the extracted executable and temporary log,
key and known-host paths. Home and temporary directories were private to the
test. OPKG's version comparison confirms the package sorts after the shared
`android.5.0.2_r1-1` version.

The temporary server, keys and payload were removed; boot ID and kernel taint
were unchanged. No Android device commands, USB transfer, network pairing or
mDNS discovery were tested. USB/device compatibility still requires a physical
device test; the local client/server check establishes runtime compatibility on
this router.

## Tailscale

Run `40175326506` produced `tailscale_1.104.2-1_arm_cortex-a9_neon.ipk`.
The combined daemon/CLI is 36,909,272 bytes. ELF inspection confirms static ARM
without an interpreter or dynamic dependencies; Go metadata records Go 1.27.3,
`GOARM=7,softfloat`, disabled CGO and the upstream `ts_include_cli` feature.
The installed `tailscale` command is a symlink to the combined `tailscaled` binary.

Both commands reported 1.104.2 on the router. A private daemon with in-memory
state, an isolated Unix socket, `--tun=userspace-networking`, a temporary log
directory and log upload disabled reached `NeedsLogin`; its CLI returned that
state. No login, peer connection, routed VPN test or persistent installation was
performed. Temporary processes and files were removed; boot ID and taint were
unchanged. The packaged service defaults to disabled and never runs `tailscale
up` automatically. Normal TUN mode still requires appropriate device/kernel
support; userspace mode does not require installing a kernel WireGuard module.

## WireGuard

The current command-line tools are already updated. Linux 4.1 uses the separate
`wireguard-linux-compat` 1.0.20220627 backport and matching kernel-specific IPKs.
A newer tool version does not update the kernel implementation or prove module
ABI compatibility. See [wireguard-updates.md](wireguard-updates.md) for the
existing kernel builds and firmware-specific validation. Running a modern
in-tree WireGuard implementation requires a newer supported kernel/firmware.
