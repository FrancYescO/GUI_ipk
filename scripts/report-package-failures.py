#!/usr/bin/env python3
"""Summarize all package failures from a keep-going OpenWrt compile."""

import re
import sys
from collections import deque
from pathlib import Path


RECIPE_FAILURE = re.compile(
    r"make(?:\[\d+\])?: \*\*\* \[(package/[^\]\s]+/compile)\]"
)
RECIPE_ERROR_LOG = re.compile(r"ERROR: (package/\S+) failed to build\.")
BLOCKED_RECIPE = re.compile(
    r"Target ['`](package/[^'`\s]+/compile)['`] not remade because of errors"
)
DIAGNOSTIC = re.compile(
    r"(?:\berror:|undefined reference|No rule to make target|collect2: error:)",
    re.IGNORECASE,
)
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def summarize(serial_log: Path, error_log: Path):
    failed = {}
    blocked = set()
    recent_errors = deque(maxlen=5)

    with serial_log.open(errors="replace") as stream:
        for raw in stream:
            line = ANSI_ESCAPE.sub("", raw).strip()
            if DIAGNOSTIC.search(line) and "requested URL returned error" not in line:
                recent_errors.append(line)

            match = RECIPE_FAILURE.search(line)
            if match:
                recipe = match.group(1)
                failed.setdefault(recipe, list(recent_errors))
                recent_errors.clear()

            match = BLOCKED_RECIPE.search(line)
            if match:
                blocked.add(match.group(1))

    if error_log.is_file():
        for line in error_log.read_text(errors="replace").splitlines():
            match = RECIPE_ERROR_LOG.search(line)
            if match:
                recipe = match.group(1)
                if not recipe.endswith("/compile"):
                    recipe += "/compile"
                failed.setdefault(recipe, [])

    blocked.difference_update(failed)
    return failed, blocked


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: report-package-failures.py SERIAL_LOG ERROR_LOG OUTPUT_DIR", file=sys.stderr)
        return 2

    serial_log, error_log, output_dir = map(Path, sys.argv[1:])
    failed, blocked = summarize(serial_log, error_log)
    output_dir.mkdir(parents=True, exist_ok=True)
    recipes = sorted(failed)
    (output_dir / "failed-packages.txt").write_text(
        "".join(f"{recipe}\n" for recipe in recipes)
    )

    report = [
        "# Userspace package build failures",
        "",
        f"Failed recipes: {len(recipes)}",
        "",
    ]
    if recipes:
        for recipe in recipes:
            report.append(f"## `{recipe}`")
            report.append("")
            diagnostics = failed[recipe]
            if diagnostics:
                report.append("```text")
                report.extend(diagnostics)
                report.append("```")
            report.append("")
    else:
        report.extend(["No package recipe was identified in the make output.", ""])

    if blocked:
        report.extend(["## Blocked by failed dependencies", ""])
        report.extend(f"- `{recipe}`" for recipe in sorted(blocked))
        report.append("")

    report.extend(
        [
            "The artifact also contains `serial-package-compile.log` with the full compiler output.",
            "",
        ]
    )
    (output_dir / "failed-packages.md").write_text("\n".join(report))
    print(f"Package failure report: {len(recipes)} failed, {len(blocked)} blocked")
    for recipe in recipes:
        print(f"  {recipe}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
