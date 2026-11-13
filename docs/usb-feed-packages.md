# USB tethering packages

The standard USB packages are now produced by the common kernel package
pipeline for all eight profiles. See [Standard kernel packages](kernel-feed-packages.md)
for installation, complete native groups, dependency recovery and controlled
migration from previous manual providers.

The USB package names remain `kmod-usb-net-cdc-ether`, `kmod-usb-net-rndis` and
`kmod-usb-net`. RNDIS requires the rebuilt CDC package at the exact feed version.
