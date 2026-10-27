# VBNT-K 4.1.52 RNDIS compatibility modules

Package names omit `damson-`. Only package metadata and filenames were renamed; the module payloads are unchanged. Each new package replaces and conflicts with its former package name.

This manual-only artifact set adds recognition of USB miscellaneous-class
RNDIS (`ef/04/01`) to `rndis_host` and the CDC descriptor parser. The CDC module
also omits Zyxel-specific LED callbacks that VBNT-K does not export. The native
`usbnet` module is retained.

The pair was built with the VBNT-K configuration, ABI patch and OpenWrt GCC 5.5.0.
The ABI canary passed, and both modules retain the original VBNT-K undefined-symbol
sets. `BUILD-METADATA.txt` records configuration and patch hashes. `SHA256SUMS`
verifies the raw modules and their manual IPK containers.

Use both `cdc_ether.ko` and `rndis_host.ko` together. The canary is a build check,
not a boot dependency. Matching `4.1.52` alone does not establish firmware
compatibility. Preserve original modules before testing and unload only when
existing USB network users can be stopped. Load CDC first, then RNDIS; use the
same order for rollback after unloading RNDIS first.

The IPKs contain one module each and no installation scripts, network settings
or boot autoload entries. The publication workflow includes this tested pair
in the separate `kernel/4.1.52` OPKG feed, with architecture `arm_cortex-a9`.
They retain their manual-installation and firmware metadata. Existing
firmware packages may own the same module paths; do not bypass ownership checks
as a substitute for a verified backup and firmware-specific installation.

USB network configuration is separate from driver loading. A local DHCP test
can disable default routes and peer DNS to retain the existing WAN connection.
No captured device data is included in this artifact set or its documentation.
