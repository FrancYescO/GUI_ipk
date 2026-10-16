#!/usr/bin/env python3
"""Reject kernel payloads without mistaking Korean .ko documents for modules."""

import sys
import tarfile
from pathlib import Path, PurePosixPath


def check_payloads(feed_root):
    for package in sorted(feed_root.rglob("*.ipk")):
        with tarfile.open(package, "r:*") as archive:
            data = next(
                member for member in archive
                if member.name.lstrip("./") == "data.tar.gz"
            )
            with tarfile.open(fileobj=archive.extractfile(data), mode="r|gz") as payload:
                for member in payload:
                    parts = PurePosixPath(member.name).parts
                    module_directory = any(
                        parts[index:index + 2] == ("lib", "modules")
                        for index in range(len(parts) - 1)
                    )
                    module_file = member.name.endswith(".ko") and (
                        not member.isfile()
                        or payload.extractfile(member).read(4) == b"\x7fELF"
                    )
                    if module_directory or module_file:
                        raise ValueError(
                            "Shared feed package contains a kernel module payload: "
                            f"{package} ({member.name})"
                        )


if __name__ == "__main__":
    try:
        check_payloads(Path(sys.argv[1]))
    except (ValueError, tarfile.TarError, StopIteration, OSError) as error:
        print(str(error) or "Invalid IPK payload", file=sys.stderr)
        sys.exit(1)
