#!/usr/bin/env python3
"""Bind the private lab bundle to its build and pinned application inputs."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

root = Path(sys.argv[1]).resolve()
report = {
    "schema": 1,
    "experimental": True,
    "runtime_profile": "4.1.52-vbntk",
    "kernel_abi": "f4e97ee0656c3a247868bb0a3f9c7e55",
    "source_commit": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True).strip(),
    "test_apps": json.loads(Path(__file__).with_name("app-inputs.json").read_text()),
    "files": {},
}
for path in sorted(root.rglob("*")):
    if path.is_file() and not path.is_symlink() and path.name != "bundle.json":
        report["files"][path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
(root / "bundle.json").write_text(json.dumps(report, indent=2) + "\n")
