#!/usr/bin/env python3
"""Verify shard coverage and assemble one OPKG feed from successful jobs."""

import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path


FEEDS = {"base", "luci", "packages", "routing", "telephony", "target/packages"}


def control(ipk):
    archive = subprocess.check_output(["tar", "-xOzf", str(ipk), "./control.tar.gz"])
    text = subprocess.run(
        ["tar", "-xOzf", "-", "./control"], input=archive,
        check=True, capture_output=True,
    ).stdout.decode("utf-8").rstrip("\n")
    fields = {}
    for line in text.splitlines():
        if ": " in line and not line[0].isspace():
            key, value = line.split(": ", 1)
            fields[key] = value
    for required in ("Package", "Version", "Architecture"):
        if not fields.get(required):
            raise ValueError(f"Missing {required} in {ipk}")
    expected = f'{fields["Package"]}_{fields["Version"]}_{fields["Architecture"]}.ipk'
    if ipk.name != expected:
        raise ValueError(f"Package filename differs from control metadata: {ipk}")
    return text, fields


def write_index(directory, entries):
    directory.mkdir(parents=True, exist_ok=True)
    stanzas = []
    for ipk, control_text in sorted(entries, key=lambda item: item[0].name):
        stanzas.append(
            control_text + "\n"
            + f"Filename: {ipk.name}\n"
            + f"Size: {ipk.stat().st_size}\n"
            + f"SHA256sum: {hashlib.sha256(ipk.read_bytes()).hexdigest()}"
        )
    index = ("\n\n".join(stanzas) + "\n").encode()
    (directory / "Packages").write_bytes(index)
    with (directory / "Packages.gz").open("wb") as output:
        with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as zipped:
            zipped.write(index)


def merge(artifacts, output, count):
    manifests = {}
    problems = []
    reports = []
    for shard_dir in sorted(artifacts.glob("userspace-shard-*")):
        manifest_path = shard_dir / "shard-manifest.json"
        if not manifest_path.is_file():
            problems.append(f"{shard_dir.name}: missing shard manifest")
            continue
        manifest = json.loads(manifest_path.read_text())
        index = manifest["shard_index"]
        if index in manifests:
            problems.append(f"Duplicate shard {index}")
            continue
        manifests[index] = (shard_dir, manifest)
        report = shard_dir / "failed-packages.md"
        if report.is_file():
            reports.append((index, report.read_text()))
        if not any(shard_dir.rglob("*.ipk")) and not report.is_file():
            problems.append(f"Shard {index}: no IPKs or failure report")

    missing = sorted(set(range(count)) - set(manifests))
    if missing:
        problems.append(f"Missing shard artifacts: {', '.join(map(str, missing))}")

    if len(manifests) == count:
        digests = {m["all_recipes_sha256"] for _, m in manifests.values()}
        totals = {m["total_recipe_count"] for _, m in manifests.values()}
        counts = {m["shard_count"] for _, m in manifests.values()}
        recipes = [recipe for _, m in manifests.values() for recipe in m["recipes"]]
        if len(digests) != 1 or len(totals) != 1 or counts != {count}:
            problems.append("Shard manifests disagree on the recipe set")
        elif len(recipes) != len(set(recipes)) or len(recipes) != next(iter(totals)):
            problems.append("Shard recipe coverage has duplicates or gaps")
        elif hashlib.sha256(("\n".join(sorted(recipes)) + "\n").encode()).hexdigest() not in digests:
            problems.append("Shard recipe digest does not match their union")

    output.mkdir(parents=True, exist_ok=True)
    summary = ["# Userspace shard results", "", f"Expected shards: {count}", ""]
    summary.extend(f"- {problem}" for problem in problems)
    for index, report in sorted(reports):
        summary.extend([f"## Shard {index}", "", report, ""])
    if not problems and not reports:
        summary.extend(["All shard jobs produced IPKs and covered the full recipe set.", ""])
    (output / "shard-report.md").write_text("\n".join(summary))
    if problems or reports:
        raise ValueError(f"{len(problems)} shard problems, {len(reports)} failure reports")

    owners = {}
    candidates = defaultdict(list)
    for index, (shard_dir, manifest) in manifests.items():
        for package in manifest["packages"]:
            if package in owners:
                raise ValueError(f"Package assigned to multiple shards: {package}")
            owners[package] = index
        for ipk in shard_dir.rglob("*.ipk"):
            feed = ipk.relative_to(shard_dir).parent.as_posix()
            if feed not in FEEDS:
                raise ValueError(f"Unexpected package directory: {ipk}")
            text, fields = control(ipk)
            name = fields["Package"]
            if name == "kernel" or name.startswith("kmod-"):
                continue
            candidates[(feed, name)].append((index, ipk, text, fields))

    if not candidates:
        raise ValueError("No userspace packages in shard artifacts")
    feed_entries = defaultdict(list)
    for (feed, name), choices in sorted(candidates.items()):
        versions = {(item[3]["Version"], item[3]["Architecture"]) for item in choices}
        if len(versions) != 1:
            raise ValueError(f"Conflicting versions or architectures for {feed}/{name}")
        owner = owners.get(name)
        owned = [item for item in choices if item[0] == owner]
        chosen = (owned or sorted(choices, key=lambda item: item[0]))[0]
        _, source, text, _ = chosen
        destination = output / feed / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        feed_entries[feed].append((destination, text))

    for feed, entries in feed_entries.items():
        write_index(output / feed, entries)
    (output / ".nojekyll").touch()
    print(f"Merged {len(candidates)} userspace IPKs from {count} shards")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("count", type=int)
    args = parser.parse_args()
    try:
        merge(args.artifacts, args.output, args.count)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Shard merge failed: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
