# Kernel module feeds and firmware compatibility

Operator branding does not determine module compatibility. The relevant inputs
are the CPU/platform, vendor SDK and kernel source, kernel configuration,
exported symbols and structure layouts. An equal Linux release or vermagic
does not prove that these match. SPU additionally depends on the Broadcom
hardware and firmware integration.

## Public OPKG feeds

Base URL: `https://francyesco.github.io/GUI_ipk/`. All kernel IPKs are on Pages.
The [kernel feed overview](https://francyesco.github.io/GUI_ipk/kernel/) lists
source lines, package counts, exact ABIs and reference firmware.

| Feed | Scope |
| --- | --- |
| `kernel/4.1.38-vbnto` | 5 packages: TUN, WireGuard, SPU, CDC Ethernet and RNDIS host on DGA4131FWB, 18.3.n.0439, kernel package ending `08839f3f6145d3a5d2d04be7567e3f9d` |
| `kernel/4.1.38-vbnts` | 5 packages: TUN, WireGuard, SPU, CDC Ethernet and RNDIS host on DGA4132, 18.3.k.0451, kernel package ending `8dd693635a152c8c7b822a64e6c5c470` |
| `kernel/4.1.52-vbntk` | VBNT-K at .69, firmware 19.4.1051-3401200; per-module validation levels |
| `kernel/4.1.52` | Compatibility alias of `4.1.52-vbntk` |
| `kernel/4.1.38-vbnto-candidates` | 220 staged candidate IPKs for the exact VBNT-O kernel package above |
| `kernel/4.1.38-vbnts-candidates` | 212 staged candidate IPKs for the exact VBNT-S kernel package above |
| `kernel/4.1.38` | Historical archive only; no active OPKG feed or identified compatible firmware |

There are three runtime feeds. Enable only the one whose complete kernel
package version matches `opkg status kernel`:

```text
src/gz modgui_kernel_4_1_38_vbnto https://francyesco.github.io/GUI_ipk/kernel/4.1.38-vbnto
src/gz modgui_kernel_4_1_38_vbnts https://francyesco.github.io/GUI_ipk/kernel/4.1.38-vbnts
src/gz modgui_kernel_4_1_52_vbntk https://francyesco.github.io/GUI_ipk/kernel/4.1.52-vbntk
```

These lines are alternatives, not a combined configuration. The source-selection
helper chooses exactly one matching ABI. See the per-module reports for test
levels; matching firmware metadata alone is not runtime validation.

### Optional staging-only candidates

The two candidate feeds are separate and are not enabled by the helper. Add
one only for manual validation, matching the firmware's installed `kernel` package, for example:

```text
src/gz gui_kernel_vbnts_candidates https://francyesco.github.io/GUI_ipk/kernel/4.1.38-vbnts-candidates
```

Check the installed kernel package with `opkg status kernel`. These IPKs retain
an exact kernel dependency. Do not replace the virtual kernel package or use
`--force-depends` to bypass a mismatch.

`opkg update` exposes the candidates; installing one stages its module under
`/usr/lib/kernel-module-candidates/4.1.38/` (VBNT-O) or
`/usr/lib/kernel-module-candidates/4.1.38-vbnts/` (VBNT-S). It does not replace
stock modules, add boot autoload or activate the module. Loading is a separate
manual operation after ABI and dependency checks. Candidate dependencies on
other modules must be checked against stock exports and the build manifest;
the packages do not represent a complete automatic kernel-module dependency
resolver. Per-payload test status is exposed in the OPKG indexes; most
candidates have only been compiled. Existing functional results apply only
to their exact SHA-256 payload and firmware. `xt_nat` remains withheld.

## Firmware inventory

The public compatibility page lists 279 firmware branches from
`FrancYescO/tch_firmware_extracted`, with source commits, kernel package,
architecture, vendor kernel source and stock-module fingerprint. It describes
build candidates, not a list of devices on which every module is supported.

| Linux release | Firmware branches | Distinct complete kernel package identifiers |
| --- | ---: | ---: |
| 3.4.11 | 118 | 35 |
| 4.1.38 | 55 | 12 |
| 4.1.45 | 14 | 2 |
| 4.1.52 | 92 | 17; three branches lack package metadata |

The 66 identifiers are not 66 mandatory Git branches or proof of 66 incompatible
module ABIs. The OpenWrt package fingerprint covers selected `y/m` configuration
options; it does not identify every source change or full configuration.

Four AGTHP/AGTEF 2.2.0 firmware branches have identical kernel package, source
reference and all 245 stock modules. They are the strongest candidates for
reusing the VBNT-S profile, but newly built modules still need runtime checks.
The broader 33-firmware group has multiple source references and stock module
sets. No non-TIM/Fastweb branch in this inventory has either tested 4.1.38
profile's complete kernel package identifier. Other operators therefore need
their own ABI comparison and, where necessary, a separate build profile.

VBNT-K's runtime-tested firmware is not mapped to other archive branches solely
because they report 4.1.52. This includes the 25 AGTHP/AGTEF 2.3.5–2.4.5
branches with fingerprint `f4e97ee0…`: comparison against the VBNT-K ABI is a
separate step.

## Next build profile

Fastweb FW261 and FW264 share kernel package
`4.1.38-1-42740ce3f7be0198c1d4501cfd664fa0`. Their kernel sources differ;
they are candidates for one shared profile, pending comparison of runtime
configurations and module tests. The extracted filesystems do not contain the
full kernel configurations. The profile is recorded as awaiting those inputs;
there is no installable feed claiming support for these firmwares yet.

All profiles share the repository and build tooling. Git branches are used
for development; separate configurations and OPKG feed paths identify runtime
compatibility.

## Legacy generic 4.1.38 feed

`kernel/4.1.38` is retained as an archive of the historical VBNTS buildroot.
Its virtual kernel package is `4.1.38-1-e5d0b8e85af0ba3d06a2ba17859e868a`.
None of the 279 inventoried firmware branches declares that complete package
identifier. There is no identified runtime target for these modules, and no
claim that the generic feed works on the .45 or .204. It is useful as a build
reference; the two exact runtime feeds provide the supported deployment path.

## USB RNDIS compatibility pair

Both exact 4.1.38 runtime feeds include `kmod-cdc-ether-<profile>-4.1.38-manual`
and `kmod-rndis-host-<profile>-4.1.38-manual`. Use both drivers together with
the firmware's native `usbnet`. They share the same `ef/04/01` USB miscellaneous
class backport as the 4.1.52 VBNT-K pair. The two 4.1.38 profiles produce
identical module payloads but retain separate kernel dependencies and packages.

Loading, USB driver registration, unloading and restoration of stock modules
passed on both modems. Boot IDs, kernel taint and default routes were unchanged.
No USB network device was attached: tethering enumeration, DHCP and traffic
remain untested. See [USB build and runtime evidence](https://francyesco.github.io/GUI_ipk/validation/usb-4.1.38/).

Candidate publisher inputs are preserved in checksum-pinned repository bundles,
so duplicate candidate Releases can be removed without affecting future builds.
All promoted application packages are retained in the main Pages feeds. Only
FreeSWITCH sounds uses a binary package Release. The three immutable
compiler/build-input releases remain necessary for CI.

The VBNT-K 4.1.52 packages declare `arm_cortex-a9`, confirmed in OPKG on
.69. The former `brcm963xx` package architecture is not accepted by that modem.
Package names and version `4.1.52-1` are retained; container metadata and
filenames change, while every module payload remains identical to the registry.
Run `opkg update` to obtain the refreshed indexes.
