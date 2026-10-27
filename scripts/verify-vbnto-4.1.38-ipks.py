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
    parser.add_argument("--profile", choices=["vbnto", "vbnts"], default="vbnto")
    args = parser.parse_args()
    config = runpy.run_path(str(Path(__file__).with_name("package-vbnto-4.1.38.py")))
    config = config["profile_config"](args.profile)
    expected = dict(config["MODULES"])
    wireguard_ipk = args.directory / f"kmod-wireguard-{args.profile}-4.1.38-manual_4.1.38-1_arm_cortex-a9.ipk"
    if not wireguard_ipk.is_file():
        expected.pop("wireguard")
    kernel = config["KERNEL"]
    ipks = list(args.directory.glob("*.ipk"))
    if len(ipks) != len(expected):
        raise ValueError(f"Expected {len(expected)} packages, got {len(ipks)}")
    for module, digest in expected.items():
        package = f"kmod-{module}-{args.profile}-4.1.38-manual"
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
        if module == "wireguard" and "X-Required-Loaded-Modules: udp_tunnel, ip6_udp_tunnel\n" not in control:
            raise ValueError("WireGuard must document its stock UDP tunnel dependencies")
        for field in (
            f"Package: {package}\n",
            "Architecture: arm_cortex-a9\n",
            f"Depends: kernel (= {kernel})\n",
            "X-Manual-Install-Only: yes\n",
            f"X-Firmware: {config['FIRMWARE']}\n",
        ):
            if field not in control:
                raise ValueError(f"Missing {field.strip()} in {filename}")
        data = members(outer["./data.tar.gz"])
        path = f"./lib/modules/4.1.38/{module}.ko"
        if set(data) != {path} or hashlib.sha256(data[path]).hexdigest() != digest:
            raise ValueError(f"Unexpected module payload: {filename}")
    print(f"Verified {len(expected)} exact-ABI 4.1.38 modules; no install scripts or boot autoload")


if __name__ == "__main__":
    main()
