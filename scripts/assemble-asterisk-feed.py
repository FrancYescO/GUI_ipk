#!/usr/bin/env python3
"""Assemble or verify the isolated Asterisk 20 OPKG feed."""

import argparse
import gzip
import hashlib
import io
import json
import re
import runpy
import shutil
import struct
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEED = Path("telephony/asterisk-20")
SHARED = runpy.run_path(str(ROOT / "scripts/merge-userspace-shards.py"))
control = SHARED["control"]
write_index = SHARED["write_index"]
PJ_LIBS = {
    "libpj", "libpjlib-util", "libpjmedia", "libpjnath", "libpjsip-simple",
    "libpjsip-ua", "libpjsip", "libpjsua", "libpjsua2",
}


def recipe_version(relative):
    text = (ROOT / "build/asterisk20-overlay" / relative / "Makefile").read_text()
    values = dict(re.findall(r"^PKG_(VERSION|RELEASE):=([^\n]+)$", text, re.M))
    return values["VERSION"] + "-" + values["RELEASE"]


def expected():
    config = (ROOT / "build/asterisk20.config").read_text()
    required = set(re.findall(r"^CONFIG_PACKAGE_(asterisk[^=]*)=[my]$", config, re.M))
    return required | PJ_LIBS | {"jansson"}, {
        "asterisk": recipe_version("feeds/telephony/net/asterisk"),
        "pjproject": recipe_version("feeds/telephony/libs/pjproject"),
        "jansson": recipe_version("feeds/packages/libs/jansson"),
    }


def selected(filename):
    return filename.startswith(("asterisk_", "asterisk-", "libpj", "jansson_"))


def inspect_payload(ipk):
    count = 0
    with tarfile.open(ipk, "r:gz") as outer:
        member = next(m for m in outer if m.name.lstrip("./") == "data.tar.gz")
        blob = outer.extractfile(member).read()
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as data:
        for member in data:
            path = Path(member.name)
            if path.is_absolute() or ".." in path.parts or member.name.endswith(".ko"):
                raise ValueError(f"Unexpected payload path in {ipk}: {member.name}")
            if not member.isfile():
                continue
            header = data.extractfile(member).read(52)
            if header[:4] != b"\x7fELF":
                continue
            if (len(header) < 52 or header[4:6] != b"\x01\x01"
                    or struct.unpack_from("<H", header, 18)[0] != 40
                    or struct.unpack_from("<I", header, 36)[0] & 0x400):
                raise ValueError(f"Unexpected ELF ABI in {ipk}: {member.name}")
            count += 1
    if not count:
        raise ValueError(f"No ARM ELF payload in {ipk}")
    return count


def candidates(source):
    required, versions = expected()
    entries = {}
    for ipk in sorted(source.rglob("*.ipk")):
        if not selected(ipk.name):
            continue
        text, fields = control(ipk)
        name = fields["Package"]
        kind = "asterisk" if name == "asterisk" or name.startswith("asterisk-") else (
            "pjproject" if name in PJ_LIBS else "jansson" if name == "jansson" else None
        )
        if (kind is None or fields["Version"] != versions[kind]
                or fields["Architecture"] != "arm_cortex-a9_neon"):
            raise ValueError(f"Unexpected package or version: {ipk}")
        if name in entries:
            raise ValueError(f"Duplicate package: {name}")
        inspect_payload(ipk)
        entries[name] = (ipk, text, fields)
    if required - entries.keys():
        raise ValueError(f"Missing required packages: {sorted(required - entries.keys())}")
    return entries


def index_fields(index):
    for stanza in index.read_text().split("\n\n"):
        fields = {}
        for line in stanza.splitlines():
            if ": " in line and not line[0].isspace():
                key, value = line.split(": ", 1)
                fields[key] = value
        if fields.get("Package"):
            yield fields


def dependency_check(entries, base, allow_unindexed=False):
    available = set(entries)
    for index in base.rglob("Packages"):
        if index.is_file():
            available.update(fields["Package"] for fields in index_fields(index))
    if allow_unindexed:
        # OpenWrt's raw build index may omit libc. The final merged feed must
        # still resolve every dependency from its published indexes.
        for ipk in base.rglob("*.ipk"):
            try:
                _, fields = control(ipk)
            except (ValueError, subprocess.CalledProcessError, UnicodeDecodeError):
                continue
            available.add(fields["Package"])
    missing = []
    for name, (_, _, fields) in entries.items():
        for group in fields.get("Depends", "").split(","):
            choices = {re.split(r"[\s(]", dep.strip())[0] for dep in group.split("|")}
            choices.discard("")
            if choices and not choices & available:
                missing.append(f"{name}: {group.strip()}")
    if missing:
        raise ValueError(f"Unresolved feed dependencies: {missing}")


def verify(feed_root, base, allow_unindexed=False):
    directory = feed_root / FEED
    entries = candidates(directory)
    indexed = {fields["Package"]: fields for fields in index_fields(directory / "Packages")}
    if len(indexed) != len(entries) or set(indexed) != set(entries):
        raise ValueError("Asterisk package index differs from its payload")
    for name, (ipk, _, fields) in entries.items():
        item = indexed[name]
        if any(item.get(k) != fields[k] for k in ("Version", "Architecture")):
            raise ValueError(f"Index metadata mismatch: {name}")
        if (item.get("Filename") != ipk.name
                or item.get("SHA256sum") != hashlib.sha256(ipk.read_bytes()).hexdigest()
                or item.get("Size") != str(ipk.stat().st_size)):
            raise ValueError(f"Index checksum or filename mismatch: {name}")
    if gzip.decompress((directory / "Packages.gz").read_bytes()) != (directory / "Packages").read_bytes():
        raise ValueError("Packages.gz differs from Packages")
    dependency_check(entries, base, allow_unindexed)
    print(f"Verified {len(entries)} Asterisk/PJPROJECT/Jansson packages in {FEED}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--base-feed", type=Path)
    parser.add_argument("--source-run-id", default="")
    parser.add_argument("--source-commit", default="")
    args = parser.parse_args()
    if args.verify:
        verify(args.source, args.base_feed or args.source)
        return
    if args.output is None:
        parser.error("output is required when assembling a feed")
    entries = candidates(args.source)
    dependency_check(entries, args.source, allow_unindexed=True)
    destination = args.output / FEED
    if destination.exists():
        raise ValueError(f"Output feed already exists: {destination}")
    destination.mkdir(parents=True)
    output_entries = []
    for name, (source, text, _) in sorted(entries.items()):
        target = destination / source.name
        shutil.copy2(source, target)
        output_entries.append((target, text))
    write_index(destination, output_entries)
    (destination / "build-info.json").write_text(json.dumps({
        "source_run_id": args.source_run_id,
        "source_commit": args.source_commit,
        "packages": sorted(entries),
        "versions": expected()[1],
        "architecture": "arm_cortex-a9_neon",
    }, indent=2) + "\n")
    verify(args.output, args.source, allow_unindexed=True)


if __name__ == "__main__":
    main()
