# USB tethering packages

Each of the eight exact-ABI kernel feeds publishes `kmod-usb-net-cdc-ether`
and `kmod-usb-net-rndis` with the repaired ELF modules at their standard
`/lib/modules/<release>/` paths. The `1:` version epoch makes these packages
newer than the firmware's original versions, including versions beginning
with `git_`. RNDIS requires the repaired CDC package at its exact version.
Other experimental modules keep their existing publication policy.

The feeds also include the original `kmod-usb-net` and its complete dependency
closure (`kmod-mii`, `kmod-usb-core`, `kmod-nls-base` where required).
These packages retain their original version, dependencies, payload bytes,
file modes and symlinks. Their only installation hook checks the kernel ABI;
no installation or removal hook loads or unloads modules. They can restore a
dependency recorded as not installed without editing the OPKG database.

## Install or upgrade

Use the feed for the modem's exact profile, for example VCNT-3:

```text
src/gz modgui_kernel_4.1.52_vcnt3 https://francyesco.github.io/GUI_ipk/kernel/4.1.52-vcnt3
```

After publishing the updated feed:

```sh
opkg update
opkg install kmod-usb-net-cdc-ether kmod-usb-net-rndis
```

An already installed native package upgrades under the same name. Installation
does not activate the modules; reconnect tethering through the application
after installation. Hardware reconnection and Internet traffic still require
verification on the target modem.

## Previous manual packages

The standard packages refuse installation while their previous `-manual`
package is installed. OPKG also prevents overwriting another package's files.
Stop USB tethering and quiesce its consumers before migration. Remove the two
previous package names reported by the error, then install the standard names.
For VCNT-3 the previous names are:

```sh
opkg remove kmod-rndis-host-vcnt3-4.1.52-manual kmod-cdc-ether-vcnt3-4.1.52-manual
opkg install kmod-usb-net-cdc-ether kmod-usb-net-rndis
```

Do not force dependency checks or file overwrites. The previous names vary by
profile and are recorded in `X-Previous-Module-Package` in each new IPK.

## Pinned firmware inputs and verification

`build/kernel-opkg-providers/stock-usb.json.gz` records the source repository,
commit, original controls and file lists, plus every payload's hash and mode.
To reproduce it, export each profile's `repository`, `commit`, and `firmware`
fields to a JSON object keyed by profile and run:

```sh
python3.12 scripts/pin-stock-usb.py /path/to/tch_firmware_extracted sources.json stock-usb.json.gz
```

The generator validates the original kernel ABI and known package metadata.
The publication tests reproduce IPKs against the bootstrap catalog and check
stock bytes, symlinks and controls. `tests/opkg/usb.sh` uses the pinned 2017 OPKG
in isolated roots for clean installation, native upgrades, missing USBnet,
wrong ABI rejection and migration from manual file ownership on all profiles.
The existing publication workflow regenerates `Packages` and `Packages.gz`
and deploys only after its checks pass.
