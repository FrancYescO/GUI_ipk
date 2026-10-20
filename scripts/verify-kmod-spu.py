#!/usr/bin/env python3
"""Verify the SPU IPK's architecture, ARM ELF, vermagic and lack of boot autoload."""
import argparse
import io
import re
import struct
import tarfile
from pathlib import Path, PurePosixPath


def verify(root, version):
    pattern = "kmod-bcm63xx-tch-spu_*.ipk" if version == "4.1.38" else "kmod-bcmspu-*.ipk"
    packages = list(root.rglob(pattern))
    if len(packages) != 1:
        raise ValueError(f"Expected one SPU IPK, found {len(packages)}")
    with tarfile.open(packages[0], "r:*") as outer:
        members = {m.name.removeprefix("./"): m for m in outer}
        control_bytes = outer.extractfile(members["control.tar.gz"]).read()
        data_bytes = outer.extractfile(members["data.tar.gz"]).read()
    with tarfile.open(fileobj=io.BytesIO(control_bytes), mode="r:gz") as control:
        fields_text = next(control.extractfile(m).read().decode() for m in control
                           if m.name.removeprefix("./") == "control")
    fields = dict(line.split(": ", 1) for line in fields_text.splitlines() if ": " in line and not line[0].isspace())
    architecture = "arm_cortex-a9_neon" if version == "4.1.38" else "arm_cortex-a9"
    if fields.get("Architecture") != architecture or not fields.get("Version", "").startswith(version + "-"):
        raise ValueError("Unexpected SPU package version/architecture")
    with tarfile.open(fileobj=io.BytesIO(data_bytes), mode="r:gz") as data:
        modules = []
        for member in data:
            name = member.name.removeprefix("./")
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or member.issym() or member.islnk():
                raise ValueError(f"Unsafe SPU payload member: {name}")
            if name.startswith(("etc/modules.d", "etc/rc.d", "etc/init.d")):
                raise ValueError("SPU must not autoload at boot")
            if member.isfile():
                if name != f"lib/modules/{version}/bcmspu.ko":
                    raise ValueError(f"Unexpected SPU payload file: {name}")
                modules.append(data.extractfile(member).read())
    if len(modules) != 1:
        raise ValueError("SPU package must contain exactly one module")
    module = modules[0]
    if module[:6] != b"\x7fELF\x01\x01" or struct.unpack_from("<H", module, 18)[0] != 40:
        raise ValueError("SPU module must be little-endian ELF32 ARM")
    magic = re.search(rb"\x00vermagic=([^\x00]+)", module)
    expected = f"{version} SMP preempt mod_unload ARMv7"
    if not magic or magic[1].decode().strip() != expected:
        raise ValueError("SPU vermagic does not match its feed")
    if b"parm=blog_offload:" not in module:
        raise ValueError("Missing explicit ESP flow-offload policy")
    print(f"Verified SPU {version}: ARM ELF, architecture, vermagic, payload and no autoload")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("version", choices=("4.1.38", "4.1.52"))
    args = parser.parse_args()
    verify(args.root, args.version)
