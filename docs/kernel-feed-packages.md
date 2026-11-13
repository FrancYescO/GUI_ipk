# Standard kernel packages

All eight exact-ABI feeds use standard package names for every installable
module. Native package groups retain their complete original file lists,
configuration files and symlinks. Verified rebuilt modules replace matching
members; other members retain their original firmware bytes. Packages absent
from the firmware use the standard `kmod-<module>` name. Capability aliases and
verified builtins remain available under their ordinary names.

Rebuilt groups and aliases use version `1:<kernel>-7`, newer than native
versions and the earlier USB packages. Original dependency packages without
rebuilt members retain their native version. Every dependency resolves within
the same exact-ABI feed, with consistent version constraints. Experimental
source modules do not become providers. No maintainer hook loads or unloads a
module, changes OPKG's database, or bypasses dependencies. Running modules
remain loaded until the operator reconnects their consumers or reboots.

## Installation and updates

Configure only the correct kernel profile for the modem, run `opkg update`,
then install or upgrade the desired standard names. For example:

```sh
opkg install kmod-usb-net-cdc-ether kmod-usb-net-rndis
opkg install kmod-tun
```

Groups such as `kmod-nf-conntrack` and `kmod-sched-core` contain the complete
native group, including original members not present in the rebuilt set.
A package with builtin modules is not treated as an incomplete rebuilt group.
`X-Rebuilt-Modules` and `X-Module-Validation` record hashes and runtime evidence
for each rebuilt member. Firmware membership does not imply runtime validation
of a rebuilt member.

## Migration from previous manual providers

An ordinary install refuses to overwrite a previous manual package's files.
The previous names and paths are recorded in `X-Previous-Module-Packages` and
`X-Previous-Module-Owners`. For a simple installation with no dependent
packages, stop the consumers, remove the previous packages and install the
standard names.

For an installed provider with dependents, use
`scripts/migrate-standard-kernel-package.sh`. This checks the exact kernel
ABI, all payload checksums, configuration symlinks, existing file owners, and
all module activity before installing. It supports complete multi-module
groups and preserves consumers. It refuses unrelated file owners and active
modules. It never unloads modules or bypasses dependencies.

```sh
sh migrate-standard-kernel-package.sh kmod-nf-conntrack
# After quiescing consumers and unloading affected modules explicitly:
sh migrate-standard-kernel-package.sh --apply kmod-nf-conntrack
```

Migrate dependencies first when required by OPKG. After installing the desired
standard packages and upgrading their aliases, remove obsolete manual
packages with ordinary `opkg remove`. The controlled migration verifies the
entire payload before using `--force-overwrite`; never use that option against
an unchecked IPK.

## Pinned inputs and validation

`build/kernel-opkg-providers/stock-kernel.json.gz` records original package
controls, file lists, payload bytes, modes, symlinks and Git commit provenance.
Missing case-sensitive files in the extracted firmware mirror can only be
filled by a separately verified rebuilt module; another case variant is never
substituted. A group is rejected if any listed file remains unavailable.

`pin-stock-kernel.py` regenerates the snapshot from the firmware Git mirror,
profile source records and catalog. Pass an explicit `roots` list in each
profile's source record to reproduce a fixed selected dependency closure.

Tests compare every rebuilt module against pinned source bytes, verify complete
native file lists and stock content, reject dependency cycles and unresolved
versions, and reproduce the publication catalog. The unpatched 2017 OPKG is
then used to install every package, upgrade native packages, reject wrong ABIs,
exercise audited legacy migration, reject corrupt payloads and unrelated
owners, and verify installed bytes, ownership and versions on all eight ABIs.
These isolated tests do not replace modem hardware validation.
