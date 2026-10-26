# Damson SPU validation

This profile reconstructs `bcmspu.ko` for **VBNTJ / BCM63138, Damson
19.4.0866-3401052, Linux 4.1.52** using the pinned Zyxel 502L07 GPL SDK and
the repository's Damson kernel ABI adjustments. It is not the historical
VBNTS Linux 4.1.38 IPK, and neither artifact is interchangeable with the other.

Run `build-vbntj-kmods.yml` with `module_set=spu-probe`. This profile can use
the [checksum-pinned kernel compiler seed](../vbntj/KERNEL-TOOLCHAIN.md); it
rebuilds SPU and its tests on Actions, without rebuilding a userspace libc. Its output includes
`bcmspu.ko`, `damson_spu_test.ko`, the ABI canary, undefined-symbol lists,
checksums and a manual-only `kmod-bcmspu-4.1.52-manual` IPK. The IPK
uses `Architecture: arm_cortex-a9`, accepted by OPKG on the tested router;
the GPL target name `brcm963xx` is not an enabled OPKG architecture there. It
has no installation scripts or boot autoload file and is excluded from the
shared OPKG feed. Keep the router's existing `spuctl` and `libspuctl.so`.

## Source findings and changes

The [original forum post](https://www.ilpuntotecnico.com/forum/index.php/topic,82673.msg265543.html#msg265543)
and replies #102, #104, #107 and #152 describe the historical module,
target-specific kernel configurations, SHA256-128 rejection, Windows/DHCP
crashes and variable performance. [LuKePicci's source tree](https://github.com/LuKePicci/brcm63xx-tch-src)
contains the corresponding older Broadcom SPU implementations. The
[OpenWrt BCM63xx reference](https://openwrt.org/docs/techref/hardware/soc/soc.broadcom.bcm63xx)
provides family context; its mainline BCM63xx support is not proof of
compatibility with this vendor ARM kernel.

The Damson `impl3` driver hard-codes a 12-byte authentication tag. Patch 001
accepts other tag sizes validated by the existing synchronous software AEAD
and routes those requests entirely through that implementation. SHA256-128
therefore remains software cryptography, while SHA1-96 can use Runner.
It does not add unsupported 128-bit ICV handling to Runner firmware.

Patch 002 defaults the separate BLOG ESP flow offload to off, while retaining
hardware cipher requests. `blog_offload=1` is an experimental load-time opt-in.
This avoids the flow path implicated in the Windows/DHCP reports, but is
not proof that those client-specific crashes are fixed. The parameter is
read-only after loading so registration and teardown remain consistent.

Patch 003 clears the successfully destroyed RDPA IPsec object handle. The
upstream unload path otherwise destroys the same object once in Runner
unregistration and again in deinitialization.

The forum also discusses DHCP/RPF filtering and UDP rate limits. Those are
firewall/configuration issues, separate from module compilation; the test
does not change the router's firewall or VPN configuration.

## Temporary tests

The [20 October validation report](VALIDATION.md) records tests of the actual
Actions IPK, including limitations and cleanup checks.

First verify the router's kernel, configuration, module symbols and archive
checksums. Extract the payload to `/tmp`; do not install it with OPKG or
copy anything to `/lib/modules` or `/etc/modules.d`. Never force module load.

```sh
insmod /tmp/damson-spu/bcmspu.ko
spuctl start
cat /sys/module/bcmspu/parameters/blog_offload
insmod /tmp/damson-spu/damson_spu_test.ko
dmesg | grep damson_spu_test
rmmod damson_spu_test
sh /tmp/damson-spu/ipsec-netns.sh
spuctl showstats
spuctl stop
rmmod bcmspu
```

The raw test module compares AES128/SHA256-128 software fallback and
AES128/SHA1-96 Runner decryption with the synchronous software implementation,
including rejection of an altered authentication tag. It supplies the SKB
callback context expected by this vendor driver. A 10-second timeout keeps
the outstanding request and pins the test module to avoid freeing callback
code or buffers still in use; stop testing if that occurs.

`ipsec-netns.sh` exercises ESP encryption and decryption between two temporary
network namespaces using synthetic public test keys, bidirectional pings and
a short TCP throughput run. Its trap removes only its own namespaces; it
refuses to reuse existing names. This is a same-router functional exercise,
not a WAN speed claim or a Windows/Android interoperability test.

Afterward confirm the original boot ID, unchanged persistent hardwarecrypto
configuration, no test namespaces or XFRM state, and no new oops/panic.

The extended `ipsec-matrix.sh` exercises all three AES key lengths, SHA1/SHA256,
fragmented packets and TCP in both directions. `ipsec-rekey.sh` additionally
updates live SAs with new keys and sends UDP at 10 Mbit/s. Both create only their
dedicated namespaces, and require a module already loaded from `/tmp`. Wait
for asynchronous namespace teardown before `spuctl stop`; verify successful
stop and normal unload rather than forcing removal.

The dedicated `build-kmods-4.1.38.yml` dispatch profile `spu` appends
`build/spu-module.mk` to the archived VBNTS buildroot and applies
`patches/vbnts-spu/002-opt-in-esp-flow-offload.patch` between the common patches
001 and 003. It produces `kmod-bcm63xx-tch-spu` without boot autoload. The older
SDK has different BLOG call sites, so its patch must remain version specific.
A 4.1.38 build is not runtime validation on the 4.1.52 modem.
