#!/usr/bin/env python3
"""Reject wrong-ABI or autoloading DGA4131FWB kernel packages."""

import argparse
import hashlib
import io
import runpy
import tarfile
from pathlib import Path


def members(data):
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        return {member.name: archive.extractfile(member).read()
                for member in archive if member.isfile()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    config = runpy.run_path(str(Path(__file__).with_name("package-vbnto-4.1.38.py")))
    expected = config["MODULES"]
    kernel = config["KERNEL"]
    ipks = list(args.directory.glob("*.ipk"))
    if len(ipks) != len(expected):
        raise ValueError(f"Expected {len(expected)} packages, got {len(ipks)}")
    for module, digest in expected.items():
        package = f"kmod-{module}-vbnto-4.1.38-manual"
        filename = f"{package}_4.1.38-1_arm_cortex-a9.ipk"
        outer = members((args.directory / filename).read_bytes())
        if set(outer) != {"./debian-binary", "./control.tar.gz", "./data.tar.gz"}:
            raise ValueError(f"Unexpected IPK members: {filename}")
        if outer["./debian-binary"] != b"2.0\n":
            raise ValueError(f"Unexpected IPK format: {filename}")
        control_files = members(outer["./control.tar.gz"])
        if set(control_files) != {"./control"}:
            raise ValueError(f"Unexpected control scripts: {filename}")
        control = control_files["./control"].decode()
        for field in (
            f"Package: {package}\n",
            "Architecture: arm_cortex-a9\n",
            f"Depends: kernel (= {kernel})\n",
            "X-Manual-Install-Only: yes\n",
            "X-Firmware: 18.3.n.0439\n",
        ):
            if field not in control:
                raise ValueError(f"Missing {field.strip()} in {filename}")
        data = members(outer["./data.tar.gz"])
        path = f"./lib/modules/4.1.38/{module}.ko"
        if set(data) != {path} or hashlib.sha256(data[path]).hexdigest() != digest:
            raise ValueError(f"Unexpected module payload: {filename}")
    print("Verified two exact-ABI 4.1.38 modules; no install scripts or boot autoload")


if __name__ == "__main__":
    main()
