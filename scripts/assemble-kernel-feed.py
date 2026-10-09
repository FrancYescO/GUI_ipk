#!/usr/bin/env python3
"""Publish verified manual kernel IPKs in a version-specific OPKG index."""

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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("feed_root", type=Path)
    args = parser.parse_args()
    version = "4.1.52"
    destination = args.feed_root / "kernel" / version
    destination.mkdir(parents=True, exist_ok=True)
    entries = []
    for ipk in sorted(args.source.glob("*.ipk")):
        fields = control_fields(ipk)
        if not (
            fields.get("Package", "").startswith("kmod-")
            and fields.get("Version", "").startswith(version + "-")
            and fields.get("Architecture") == "brcm963xx"
            and fields.get("X-Kernel-Vermagic", "").startswith(version + " ")
            and fields.get("X-Manual-Install-Only") == "yes"
        ):
            raise ValueError(f"Unexpected kernel package metadata: {ipk}")
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
        raise ValueError(f"No kernel IPKs found in {args.source}")
    index = ("\n\n".join(entries) + "\n").encode("utf-8")
    (destination / "Packages").write_bytes(index)
    with (destination / "Packages.gz").open("wb") as output:
        with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as compressed:
            compressed.write(index)
    print(f"Indexed {len(entries)} kernel IPKs for {version}")


if __name__ == "__main__":
    main()
