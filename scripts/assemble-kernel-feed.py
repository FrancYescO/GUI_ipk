#!/usr/bin/env python3
"""Publish verified kernel IPKs in version-specific OPKG indexes."""

import argparse
import gzip
import hashlib
import shutil
import subprocess
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
    for ipk in sorted(ipks):
        fields = control_fields(ipk)
        manual_module = (
            version == "4.1.52"
            and fields.get("Package", "").startswith("kmod-")
            and fields.get("Architecture") == "brcm963xx"
            and fields.get("X-Kernel-Vermagic", "").startswith(version + " ")
            and fields.get("X-Manual-Install-Only") == "yes"
        )
        virtual_kernel = (
            version == "4.1.38"
            and fields.get("Package") == "kernel"
            and fields.get("Architecture") == "arm_cortex-a9_neon"
            and fields.get("Description", "").strip() == "Virtual kernel package"
        )
        if not ((manual_module or virtual_kernel) and fields.get("Version", "").startswith(version + "-")):
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
    args = parser.parse_args()
    write_feed("4.1.52", args.source.glob("*.ipk"), args.feed_root)
    if args.legacy_kernel_dir:
        candidates = list(args.legacy_kernel_dir.glob("kernel_4.1.38-*.ipk"))
        if len(candidates) != 1:
            raise ValueError(f"Expected one 4.1.38 kernel IPK, found {len(candidates)}")
        write_feed("4.1.38", candidates, args.feed_root)


if __name__ == "__main__":
    main()
