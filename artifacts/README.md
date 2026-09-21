# Tested VBNTJ TUN module

`tun-vbntj-damson-4.1.52.ko` targets the Technicolor VBNT-K firmware
Damson `19.4.0866-3401052` (`VBNTJ_502L07p1`) with Linux `4.1.52`.

The module was built with OpenWrt GCC 5.5.0 and has this vermagic:

```text
4.1.52 SMP preempt mod_unload ARMv7
```

SHA-256:

```text
374b8399951a4fa75a0b9c68b6eced9d064cc442d3150d2210d75623c275354e
```

It was tested from `/tmp` on the target router through all of these stages:

1. `insmod` and `rmmod`;
2. open and close `/dev/net/tun`;
3. `TUNSETIFF`, interface up/down and removal;
4. a bidirectional ICMP packet through the TUN file descriptor.

The datapath test reported one 84-byte TX packet and one 84-byte RX packet,
with zero errors and zero drops. The exact strip-debug artifact in this
directory was used for the final test.

Do not substitute the `kmod-tun-vbnts-4.1.52` artifact produced by the legacy
VBNTS/GCC 4.8 workflow. VBNTJ/Damson uses a different vendor ABI even when
the kernel version and vermagic appear compatible.

For a non-persistent test, copy the module to `/tmp`, verify its SHA-256, and
load it directly with `insmod`. Do not install an IPK or copy it to `/overlay`
until the target firmware and board have been verified.
