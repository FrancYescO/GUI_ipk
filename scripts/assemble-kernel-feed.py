#!/usr/bin/env python3
"""Publish verified kernel IPKs in version-specific OPKG indexes."""

import argparse
import gzip
import hashlib
import io
import json
import shutil
import subprocess
import tarfile
from pathlib import Path


def control_fields(ipk):
    control_archive = subprocess.check_output(["tar", "-xOzf", str(ipk), "./control.tar.gz"])
    control = subprocess.run(
        ["tar", "-xOzf", "-", "./control"], input=control_archive,
        check=True, capture_output=True,
    ).stdout.decode("utf-8")
    fields = {}
    for line in control.splitlines():
        if ": " in line and not line[0].isspace():
            key, value = line.split(": ", 1)
            fields[key] = value
    return fields


def write_feed(version, ipks, feed_root):
    destination = feed_root / "kernel" / version
    destination.mkdir(parents=True, exist_ok=True)
    entries = []
    package_names = set()
    records = {}
    if version == "4.1.52":
        source = Path(__file__).resolve().parents[1] / "build/vbntj/validation/results.json"
        records = {row["package"]: row for row in json.loads(source.read_text())["modules"]}
    for ipk in sorted(ipks):
        fields = control_fields(ipk)
        if version == "4.1.52":
            record = records.get(fields.get("Package"))
            if record is None:
                raise ValueError(f"Unexpected kernel package metadata (missing validation record): {ipk}")
            if record["status"].startswith("blocked"):
                raise ValueError(f"Quarantined 4.1.52 module: {ipk}")
            if record["asset"] != ipk.name:
                raise ValueError(f"Package differs from 4.1.52 validation record: {ipk}")
            with tarfile.open(ipk, "r:gz") as outer:
                data = outer.extractfile("./data.tar.gz").read()
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
                modules = [member for member in archive if member.isfile() and member.name.endswith(".ko")]
                if len(modules) != 1:
                    raise ValueError(f"Expected one module in {ipk}")
                digest = hashlib.sha256(archive.extractfile(modules[0]).read()).hexdigest()
            if digest != record["sha256"]:
                raise ValueError(f"Payload differs from 4.1.52 validation record: {ipk}")
        if fields.get("Package") in package_names:
            raise ValueError(f"Duplicate kernel package: {fields['Package']}")
        package_names.add(fields.get("Package"))
        manual_module = (
            version == "4.1.52"
            and fields.get("Package", "").startswith("kmod-")
            and (fields.get("Architecture") == "brcm963xx" or (
                fields.get("Package") in {
                    "kmod-bcmspu-4.1.52-manual",
                    "kmod-cdc-ether-4.1.52-manual",
                    "kmod-rndis-host-4.1.52-manual",
                }
                and fields.get("Architecture") == "arm_cortex-a9"
                and fields.get("X-Damson-Target") == "VBNTJ_502L07p1"
                and fields.get("X-Damson-Firmware") == "19.4.0866-3401052"
            ))
            and fields.get("X-Kernel-Vermagic", "").startswith(version + " ")
            and fields.get("X-Manual-Install-Only") == "yes"
        )
        virtual_kernel = (
            version == "4.1.38"
            and fields.get("Package") == "kernel"
            and fields.get("Architecture") == "arm_cortex-a9_neon"
            and fields.get("Description", "").strip() == "Virtual kernel package"
        )
        buildroot_module = (
            version == "4.1.38"
            and fields.get("Package", "").startswith("kmod-")
            and fields.get("Architecture") == "arm_cortex-a9_neon"
        )
        vbnto_module = (
            version == "4.1.38-vbnto"
            and fields.get("Package") in {
                "kmod-tun-vbnto-4.1.38-manual",
                "kmod-bcmspu-vbnto-4.1.38-manual",
                "kmod-wireguard-vbnto-4.1.38-manual",
            }
            and fields.get("Architecture") == "arm_cortex-a9"
            and fields.get("Depends") ==
                "kernel (= 4.1.38-1-08839f3f6145d3a5d2d04be7567e3f9d)"
            and fields.get("X-Firmware") == "18.3.n.0439"
            and fields.get("X-Manual-Install-Only") == "yes"
            and fields.get("X-Kernel-Vermagic", "").startswith("4.1.38 ")
        )
        wireguard_backport_version = (
            buildroot_module
            and fields.get("Package") == "kmod-wireguard"
            and fields.get("Version") == "4.1.38+1.0.20220627-1"
        )
        if not ((manual_module or virtual_kernel or buildroot_module or vbnto_module)
                and (fields.get("Version", "").startswith(version.split("-vbnto")[0] + "-")
                     or wireguard_backport_version)):
            raise ValueError(f"Unexpected kernel package metadata: {ipk}")
        if virtual_kernel:
            payload = subprocess.check_output(["tar", "-xOzf", str(ipk), "./data.tar.gz"])
            members = subprocess.run(
                ["tar", "-tzf", "-"], input=payload, check=True, capture_output=True,
            ).stdout.decode("utf-8").splitlines()
            if members != ["./"]:
                raise ValueError(f"Virtual kernel IPK unexpectedly contains payload: {ipk}")
        if ipk.name != f'{fields["Package"]}_{fields["Version"]}_{fields["Architecture"]}.ipk':
            raise ValueError(f"Filename does not match package metadata: {ipk}")
        shutil.copy2(ipk, destination / ipk.name)
        fields.update({
            "Filename": ipk.name,
            "Size": str(ipk.stat().st_size),
            "SHA256sum": hashlib.sha256(ipk.read_bytes()).hexdigest(),
        })
        entries.append("\n".join(f"{key}: {value}" for key, value in fields.items()))
    if not entries:
        raise ValueError(f"No kernel IPKs found for {version}")
    current_files = {ipk.name for ipk in ipks}
    for previous in destination.glob("*.ipk"):
        if previous.name not in current_files:
            previous.unlink()
    index = ("\n\n".join(entries) + "\n").encode("utf-8")
    (destination / "Packages").write_bytes(index)
    with (destination / "Packages.gz").open("wb") as output:
        with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as compressed:
            compressed.write(index)
    print(f"Indexed {len(entries)} kernel IPKs for {version}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="directory with verified 4.1.52 modules")
    parser.add_argument("feed_root", type=Path)
    parser.add_argument("--legacy-kernel-dir", type=Path, help="directory with the 4.1.38 virtual kernel IPK")
    parser.add_argument("--buildroot-kernel-dir", type=Path, help="directory with verified 4.1.38 kernel and kmod IPKs")
    parser.add_argument("--vbnto-kernel-dir", type=Path, help="router-tested DGA4131FWB 4.1.38 IPKs")
    parser.add_argument("--damson-extra-dir", type=Path, help="directory with additional verified manual-only Damson IPKs")
    parser.add_argument("--damson-spu-dir", type=Path, help="directory with the verified manual-only SPU IPK")
    parser.add_argument("--damson-rndis-dir", type=Path, help="directory with the router-tested CDC Ethernet/RNDIS pair")
    args = parser.parse_args()
    damson_ipks = list(args.source.glob("*.ipk"))
    if args.damson_extra_dir:
        extra_ipks = list(args.damson_extra_dir.glob("*.ipk"))
        if not extra_ipks:
            raise ValueError("No additional Damson IPKs found")
        damson_ipks.extend(extra_ipks)
    if args.damson_spu_dir:
        subprocess.run([str(Path(__file__).resolve().with_name("verify-manual-kmod-ipks.sh")),
                        str(args.damson_spu_dir)], check=True)
        spu_ipks = list(args.damson_spu_dir.glob("*.ipk"))
        if len(spu_ipks) != 1 or not spu_ipks[0].name.startswith("kmod-bcmspu-"):
            raise ValueError("Expected exactly the verified SPU package")
        damson_ipks.extend(spu_ipks)
    if args.damson_rndis_dir:
        subprocess.run([str(Path(__file__).resolve().with_name("verify-manual-kmod-ipks.sh")),
                        str(args.damson_rndis_dir)], check=True)
        rndis_ipks = list(args.damson_rndis_dir.glob("*.ipk"))
        expected = {
            "kmod-cdc-ether-4.1.52-manual_4.1.52-1_arm_cortex-a9.ipk",
            "kmod-rndis-host-4.1.52-manual_4.1.52-1_arm_cortex-a9.ipk",
        }
        if {ipk.name for ipk in rndis_ipks} != expected:
            raise ValueError("Expected exactly the router-tested CDC Ethernet/RNDIS package pair")
        damson_ipks.extend(rndis_ipks)
    verifier = Path(__file__).resolve().with_name("verify-wireguard-kmod.sh")
    for directory in (args.source, args.damson_extra_dir):
        if directory and list(directory.glob("kmod-wireguard*.ipk")):
            subprocess.run([str(verifier), str(directory), "4.1.52"], check=True)
    write_feed("4.1.52", damson_ipks, args.feed_root)
    if args.buildroot_kernel_dir:
        candidates = list(args.buildroot_kernel_dir.glob("*.ipk"))
        if len(list(args.buildroot_kernel_dir.glob("kernel_4.1.38-*.ipk"))) != 1:
            raise ValueError("Expected exactly one built 4.1.38 kernel IPK")
        if not any(ipk.name.startswith("kmod-tun_") for ipk in candidates):
            raise ValueError("Missing built kmod-tun IPK")
        if not any(ipk.name.startswith("kmod-sched-connmark_") for ipk in candidates):
            raise ValueError("Missing built kmod-sched-connmark IPK")
        if any(ipk.name.startswith("kmod-wireguard_") for ipk in candidates):
            subprocess.run([str(verifier), str(args.buildroot_kernel_dir), "4.1.38"], check=True)
        write_feed("4.1.38", candidates, args.feed_root)
    elif args.legacy_kernel_dir:
        candidates = list(args.legacy_kernel_dir.glob("kernel_4.1.38-*.ipk"))
        if len(candidates) != 1:
            raise ValueError(f"Expected one 4.1.38 kernel IPK, found {len(candidates)}")
        write_feed("4.1.38", candidates, args.feed_root)
    if args.vbnto_kernel_dir:
        subprocess.run(["python3", str(Path(__file__).resolve().with_name(
            "verify-vbnto-4.1.38-ipks.py")), str(args.vbnto_kernel_dir)], check=True)
        write_feed("4.1.38-vbnto", list(args.vbnto_kernel_dir.glob("*.ipk")), args.feed_root)


if __name__ == "__main__":
    main()
