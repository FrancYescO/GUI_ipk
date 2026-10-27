#!/usr/bin/env python3
"""Create manual-only IPKs for the tested DGA4131FWB Linux 4.1.38 ABI."""

import argparse
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path


KERNEL = "4.1.38-1-08839f3f6145d3a5d2d04be7567e3f9d"
VERMAGIC = "4.1.38 SMP preempt mod_unload ARMv7"
MODULES = {
    "tun": "bb0ef2f018acad6904c5505a9a164dd23136c809b2294cf9d9c4dce1eded8430",
    "bcmspu": "f5280ce13913803daf53ad500b55b478ecd5575fa0014323471223ab329016b1",
    "wireguard": "feb7ac9824f0615fe62a20ae4f1ff4385c0422d9f7892a20da6f4f4f64f97336",
}


def profile_config(profile):
    if profile == "vbnts":
        config = json.loads((Path(__file__).resolve().parents[1] /
                             "build/vbnts-4.1.38/profile.json").read_text())
    else:
        config = dict(KERNEL=KERNEL, VERMAGIC=VERMAGIC, MODULES=MODULES,
                      TARGET="DGA4131FWB/VBNT-O", FIRMWARE="18.3.n.0439")
    usb = Path(__file__).resolve().parents[1] / 'build/usb-rndis/validation.json'
    if usb.is_file():
        record = json.loads(usb.read_text())['profiles'][profile]
        if record['kernel_package'] != config['KERNEL']:
            raise ValueError('USB validation profile has the wrong kernel package')
        config['USB_MODULES'] = record['modules']
    return config


def archive(files):
    raw = io.BytesIO()
    with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as zipped:
        with tarfile.open(fileobj=zipped, mode="w") as tar:
            for name, data, mode in files:
                member = tarfile.TarInfo("./" + name)
                member.size = len(data)
                member.mode = mode
                member.uid = member.gid = 0
                member.uname = member.gname = "root"
                member.mtime = 0
                tar.addfile(member, io.BytesIO(data))
    # zlib may write a host-specific OS byte; normalize the gzip header.
    result = bytearray(raw.getvalue())
    result[9] = 255
    return bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="directory containing tested .ko files")
    parser.add_argument("output", type=Path, help="directory for manual IPKs")
    parser.add_argument("--profile", choices=["vbnto", "vbnts"], default="vbnto")
    args = parser.parse_args()
    config = profile_config(args.profile)
    args.output.mkdir(parents=True, exist_ok=True)
    sums = []
    for module, expected in config["MODULES"].items():
        if module == "wireguard" and not (args.source / "wireguard.ko").is_file():
            continue
        payload = (args.source / (module + ".ko")).read_bytes()
        actual = hashlib.sha256(payload).hexdigest()
        if actual != expected:
            raise ValueError(f"{module}.ko differs from router-tested module: {actual}")
        package = f"kmod-{module}-{args.profile}-4.1.38-manual"
        filename = f"{package}_4.1.38-1_arm_cortex-a9.ipk"
        control = (
            f"Package: {package}\n"
            "Version: 4.1.38-1\n"
            "Architecture: arm_cortex-a9\n"
            "Section: kernel\n"
            f"Depends: kernel (= {config['KERNEL']})\n"
            "Maintainer: GUI_ipk\n"
            f"Description: Router-tested {module} module for {config['TARGET']} {config['FIRMWARE']}\n"
            f"X-Target: {config['TARGET']}\n"
            f"X-Firmware: {config['FIRMWARE']}\n"
            f"X-Kernel-Vermagic: {config['VERMAGIC']}\n"
            "X-Manual-Install-Only: yes\n"
        ).encode()
        if module == "wireguard":
            control += b"X-Required-Loaded-Modules: udp_tunnel, ip6_udp_tunnel\n"
        contents = archive([
            ("debian-binary", b"2.0\n", 0o644),
            ("control.tar.gz", archive([("control", control, 0o644)]), 0o644),
            ("data.tar.gz", archive([(f"lib/modules/4.1.38/{module}.ko", payload, 0o644)]), 0o644),
        ])
        (args.output / filename).write_bytes(contents)
        sums.append(f"{hashlib.sha256(contents).hexdigest()}  {filename}")
    (args.output / "SHA256SUMS").write_text("\n".join(sums) + "\n")


if __name__ == "__main__":
    main()
