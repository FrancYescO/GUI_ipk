#!/usr/bin/env python3
"""Select a disjoint group of enabled OpenWrt userspace recipes."""

import argparse
import hashlib
import json
import re
from pathlib import Path


PACKAGE_CONFIG = re.compile(r"^CONFIG_PACKAGE_(.+)=[ym]$")
PACKAGE_RECIPE = re.compile(r"^package-\$\(CONFIG_PACKAGE_([^)]+)\) \+= (\S+)$")


def select(config_path, dependencies_path, index, count):
    selected = {
        match.group(1)
        for line in config_path.read_text().splitlines()
        if (match := PACKAGE_CONFIG.match(line))
        and not match.group(1).startswith("kmod-")
        and match.group(1) != "kernel"
    }
    package_recipes = {}
    for line in dependencies_path.read_text().splitlines():
        match = PACKAGE_RECIPE.match(line)
        if match and match.group(1) in selected:
            recipe = match.group(2)
            if not recipe.startswith("kernel/"):
                package_recipes[match.group(1)] = recipe

    recipes = sorted(set(package_recipes.values()))
    if len(recipes) < count:
        raise ValueError(f"Only {len(recipes)} enabled userspace recipes for {count} shards")
    assigned = recipes[index::count]
    assigned_set = set(assigned)
    digest = hashlib.sha256(("\n".join(recipes) + "\n").encode()).hexdigest()
    return {
        "shard_index": index,
        "shard_count": count,
        "total_recipe_count": len(recipes),
        "all_recipes_sha256": digest,
        "recipes": assigned,
        "packages": sorted(
            package for package, recipe in package_recipes.items()
            if recipe in assigned_set
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("dependencies", type=Path)
    parser.add_argument("index", type=int)
    parser.add_argument("count", type=int)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.count < 1 or not 0 <= args.index < args.count:
        parser.error("shard index must be within the shard count")

    manifest = select(args.config, args.dependencies, args.index, args.count)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "shard-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    (args.output / "shard-targets.txt").write_text(
        "".join(f"package/{recipe}/compile\n" for recipe in manifest["recipes"])
    )
    print(
        f"Shard {args.index + 1}/{args.count}: "
        f"{len(manifest['recipes'])} of {manifest['total_recipe_count']} userspace recipes"
    )


if __name__ == "__main__":
    main()
