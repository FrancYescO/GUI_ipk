# Tested Damson 4.1.52 modules

## TUN

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

## Conntrack mark action

`act-connmark-damson-4.1.52.ko` was built by the allowlisted `qos-probe`
profile from the same pinned GPL source, GCC 5.5.0 toolchain, reconstructed
kernel configuration and network ABI patch. It has the same kernel vermagic.

SHA-256:

```text
9bbd94d4e1ed2d02e1c990797b6540d3af3a4a13680099cb7014c4e211bc83ff
```

The exact artifact was tested non-persistently on the VBNT-K router from
`/tmp`. The test covered `insmod`, dependency resolution against the running
`nf_conntrack`, creation and inspection of a `tc` U32 filter with
`action connmark`, automatic removal of the isolated IFB/qdisc/filter, and
`rmmod`. Uptime was unchanged, the kernel log contained no Oops, `/overlay`
was untouched, and all temporary files were removed afterward.

The action was instantiated but no production interface or live traffic was
used. Treat installation as a separate step; test from `/tmp` first on every
new firmware build.

## Manual-only IPKs

The Damson workflow also packages each requested runtime module as an IPK
named `kmod-*-damson-4.1.52-manual`. These packages use the target-specific
`brcm963xx` architecture and contain exactly one file under
`/lib/modules/4.1.52/`.

They intentionally contain no `postinst`, `preinst`, removal script,
`/etc/modules.d` autoload entry, or OPKG feed index. They are available only
inside the workflow artifact and are never copied into the public OPKG feed.
Keep using the sibling raw `.ko` from `/tmp` for the first test on each
firmware; installing an IPK writes to persistent overlay storage.

Select the `router-tested` workflow profile to build `tun` and `act_connmark`
together and receive both raw modules and both manual-only IPKs in one
artifact.
