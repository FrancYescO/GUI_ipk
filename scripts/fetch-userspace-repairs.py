#!/usr/bin/env python3
"""Download successful targeted build outputs from this repository's workflow."""
import argparse
import json
import os
import re
import subprocess
from pathlib import Path

WORKFLOW = '.github/workflows/build-packages.yml'


def api(path):
    return json.loads(subprocess.check_output(['gh', 'api', path]))


def validate_run(run, repository):
    if run.get('status') != 'completed' or run.get('conclusion') != 'success':
        raise ValueError('Repair run must have completed successfully')
    if run.get('path', '').split('@', 1)[0] != WORKFLOW or run.get('event') != 'workflow_dispatch':
        raise ValueError('Repair must come from the userspace workflow dispatch')
    if run.get('head_repository', {}).get('full_name', '').lower() != repository.lower():
        raise ValueError('Repair must come from this repository')
    if not re.fullmatch('[0-9a-f]{40}', run.get('head_sha', '')):
        raise ValueError('Invalid repair source revision')


def fetch(run_ids, destination, repository, revision):
    ids = run_ids.split()
    if not ids or len(ids) > 8 or len(ids) != len(set(ids)) or any(not re.fullmatch('[0-9]+', value) for value in ids):
        raise ValueError('Provide up to eight distinct numeric repair run IDs')
    if not repository or not revision:
        raise ValueError('Repository and current revision are required')
    runs = []
    for run_id in ids:
        run = api('repos/{}/actions/runs/{}'.format(repository, run_id))
        validate_run(run, repository)
        comparison = api('repos/{}/compare/{}...{}'.format(repository, run['head_sha'], revision))
        if comparison.get('status') not in ('identical', 'ahead'):
            raise ValueError('Repair revision is not an ancestor of this workflow revision')
        runs.append((run_id, run))
    destination.mkdir(parents=True, exist_ok=True)
    for run_id, run in runs:
        target = destination / run_id
        if target.exists():
            raise ValueError('Repair destination already exists: ' + str(target))
        target.mkdir()
        subprocess.run(['gh', 'run', 'download', run_id, '--repo', repository,
                        '--name', 'userspace-shard-0-' + run_id, '--dir', str(target)], check=True)
        if (target / 'shard-manifest.json').exists():
            raise ValueError('A full shard cannot be used as a targeted repair')
        (target / 'source-run.json').write_text(json.dumps(dict(
            run_id=run_id, revision=run['head_sha'], url=run['html_url'], workflow=WORKFLOW), indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_ids', help='Space-separated successful targeted run IDs')
    parser.add_argument('destination', type=Path)
    parser.add_argument('--repository', default=os.environ.get('GITHUB_REPOSITORY'))
    parser.add_argument('--revision', default=os.environ.get('GITHUB_SHA'))
    args = parser.parse_args()
    try:
        fetch(args.run_ids, args.destination, args.repository, args.revision)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, 'Repair download failed: {}\n'.format(error))


if __name__ == '__main__':
    main()
