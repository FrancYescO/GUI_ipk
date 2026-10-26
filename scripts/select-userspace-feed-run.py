#!/usr/bin/env python3
"""Find a successful complete userspace feed; never fall back to static packages."""

import argparse
import json
import subprocess


WORKFLOW = "Userspace OPKG feed (brcm63xx-tch)"


def api(path):
    return json.loads(subprocess.check_output(["gh", "api", path], text=True))


def select_run(repository, requested=None, query=api):
    if requested:
        candidates = [query(f"repos/{repository}/actions/runs/{requested}")]
    else:
        candidates = query(
            f"repos/{repository}/actions/workflows/build-packages.yml/runs"
            "?branch=main&status=success&per_page=100"
        )["workflow_runs"]
    for run in candidates:
        if (run.get("name") != WORKFLOW or run.get("head_branch") != "main"
                or run.get("conclusion") != "success"):
            continue
        artifacts = query(
            f"repos/{repository}/actions/runs/{run['id']}/artifacts?per_page=100"
        )["artifacts"]
        complete = [artifact for artifact in artifacts
                    if artifact["name"].startswith("userspace-opkg-feed-")
                    and not artifact.get("expired", True)]
        if len(complete) == 1:
            return run["id"]
    raise RuntimeError(
        "No successful complete userspace feed artifact is available. "
        "Keeping the published feed unchanged; rebuild userspace or supply a valid run ID."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository")
    parser.add_argument("--run-id", type=int)
    args = parser.parse_args()
    print(select_run(args.repository, args.run_id))


if __name__ == "__main__":
    main()
