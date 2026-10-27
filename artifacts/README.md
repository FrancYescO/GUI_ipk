# Kernel module artifacts

Runtime profiles and public feeds:

- `4.1.38-vbnto`: DGA4131FWB, firmware 18.3.n.0439.
- `4.1.38-vbnts`: DGA4132, firmware 18.3.k.0451.
- `4.1.52-vbntk`: VBNT-K tested at .69, firmware 19.4.1051-3401200.

Each profile has exact kernel dependencies and per-payload validation records.
The 4.1.52 record distinguishes 14 functional passes, two load/unload namespace
passes, 33 busy stock modules left unchanged and withheld xt_nat. Module payloads
are unchanged by the neutral metadata/profile naming update.

[Compatibility and OPKG setup](../docs/kernel-compatibility.md)
[4.1.52 test evidence](../build/vbntj/validation/README.md)
[USB 4.1.38 test evidence](usb-rndis-4.1.38/README.md)
[Preserved candidate publisher inputs](kernel-candidates/README.md)
