# Linux 4.1.38 VBNTS buildroot packages

These IPKs came from GitHub Actions run [37938282306](https://github.com/FrancYescO/GUI_ipk/actions/runs/37938282306) at commit `2be3a4a`. The build used the pinned OpenWrt snapshot, toolchain, Linux 4.1.38 source archive, and the patches under `patches/kernel-4.1.38/`. The workflow verified the OPKG indexes, `tun.ko`, and `act_connmark.ko` before exporting the packages. `SHA256SUMS` records the copied files.

The directory contains one virtual `kernel` ABI package and 19 `kmod-*` packages. Thirteen kmod IPKs contain one or more ARM ELF `.ko` files with Linux 4.1.38 vermagic. Six packages are empty dependency placeholders for modules built into the kernel: `kmod-ipv6`, `kmod-lib-crc-ccitt`, `kmod-ppp`, `kmod-pppoe`, `kmod-pppox`, and `kmod-slhc`.

The kernel package records ABI hash `e5d0b8e85af0ba3d06a2ba17859e868a`, while the older virtual kernel IPK in `target/packages` records `7397148622e5d2b409e0a61fdeb09c77`. These packages have not been tested on a router. Confirm the firmware's exact kernel ABI before installing a module.
