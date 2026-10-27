# USB RNDIS backport on the two runtime 4.1.38 profiles

The shared `patches/usb-rndis/001-misc-class.patch` is byte-identical to the
RNDIS patch originally used for the tested Damson 4.1.52 pair (SHA-256
`d806795622dc638b7e9bcea70219b5fc0f11309b42e72c7bc4072b52677a3e04`). It
adds `ef/04/01` recognition in both the RNDIS match table and CDC parser.
The Damson-only LED callback removal remains a separate 4.1.52 vendor ABI patch.

The 4.1.38 build uses the archived Technicolor source and GCC 4.8 Linaro,
each modem's stored runtime configuration, and the same vendor include paths
as the expanded-module workflow. It preserves every existing `y/m` option.
FW258 originally disables RNDIS; the replacement build enables it as a module.
The VBNT-S profile already selects RNDIS. Native `usbnet` is compiled only
to provide modpost symbol ownership and is never packaged or substituted.
The two firmware usbnet modules are byte-identical and all existing USB
module import sets are retained.

Both configurations produced identical stripped payloads:

| Module | SHA-256 |
| --- | --- |
| cdc_ether | `7883cd569ee0132f646ef501c67dec02e281dc8d826b9bfbd3814f93cc0e67d2` |
| rndis_host | `9bc13ec5f901f6ac7a0d8cdcb286a8bd4c861bb26fa8595bf7553c7299ef20d6` |

On 27 October 2026, both pairs passed temporary loading, USB driver registration
and unloading on DGA4131FWB 18.3.n.0439 and DGA4132 18.3.k.0451. The
probe first checks that no USB network interface is attached and refuses
busy driver references. It retains native usbnet, restores the original
module set, and checks boot ID, taint, default route and stock usbnet hash.
Both tests returned `RESTORE_RESULT=0`; no persistent package was installed.
The per-profile logs, kernel configs, compiler metadata, symbol import sets
and modinfo are stored here. The digest registry is
`build/usb-rndis/validation.json`.

**No device traffic test was possible:** neither modem had a USB network
device attached. These results do not validate enumeration with a phone,
DHCP, throughput or reconnection. The existing kernel ABI restrictions remain.

The IPKs are in `artifacts/vbnto-4.1.38-manual` and
`artifacts/vbnts-4.1.38-manual`, and are indexed in those profiles' public
feeds. They install only one module each, with no maintainer scripts or
autoload entries. Stock OPKG ownership checks still apply; do not force
an overwrite to bypass a firmware conflict.

Rebuild with the **Build 4.1.38 USB RNDIS compatibility pair** workflow.
It prepares each pinned runtime profile and calls
`scripts/build-usb-rndis-4.1.38.sh`. Rebuild the 4.1.52 pair using
`module_set=rndis-compat` in the Damson workflow. Both use the shared patch;
the 4.1.52 build retains its GCC 5.5.0 toolchain and Damson layout canary.

The restored 4.1.52 build reproduces every byte of the historical driver pair
except the linker's GNU build-id, which depends on stripped build context.
For this pair only, the build compares the complete stripped ELF against
the committed runtime-tested reference and normalizes that note only when
every other byte is identical. It then verifies the complete SHA-256 against
the runtime registry. Any code, data, relocation, import or other metadata
difference rejects normalization. Published 4.1.52 module bytes remain unchanged.
