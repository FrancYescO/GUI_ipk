# Damson 4.1.52 manual kernel packages

These are the exact IPKs produced by [GitHub Actions run 35757010241](https://github.com/FrancYescO/GUI_ipk/actions/runs/35757010241). The packaged `tun.ko` and `act_connmark.ko` match the modules tested on the VBNT-K router, byte for byte. The IPK installation itself has not been tested on the router.

The files are available both in this directory and as direct [Release downloads](https://github.com/FrancYescO/GUI_ipk/releases/tag/damson-4.1.52-manual-f7ba516):

- [kmod-tun-damson-4.1.52-manual_4.1.52-1_brcm963xx.ipk](https://github.com/FrancYescO/GUI_ipk/releases/download/damson-4.1.52-manual-f7ba516/kmod-tun-damson-4.1.52-manual_4.1.52-1_brcm963xx.ipk)
- [kmod-act-connmark-damson-4.1.52-manual_4.1.52-1_brcm963xx.ipk](https://github.com/FrancYescO/GUI_ipk/releases/download/damson-4.1.52-manual-f7ba516/kmod-act-connmark-damson-4.1.52-manual_4.1.52-1_brcm963xx.ipk)

Use the pinned Release URLs in installation scripts and check the downloaded file against `SHA256SUMS` before installation. These packages target Damson `19.4.0866-3401052`, kernel `4.1.52`, `brcm963xx`. They contain no autoload configuration or installation scripts. Installing one through OPKG writes the module to persistent storage; loading the sibling `.ko` from `/tmp` remains the reversible first test on a different firmware.

They are deliberately outside the shared OPKG feed, which can be configured on routers with other kernels.
