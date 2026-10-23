import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

WORKFLOW = Path(__file__).resolve().parents[1] / '.github/workflows/build-asterisk20.yml'
BLOCK = WORKFLOW.read_text().split("          python3 - <<'PY'\n", 1)[1].split('          PY\n', 1)[0]
CODE = compile('\n'.join(line[10:] for line in BLOCK.splitlines()), str(WORKFLOW), 'exec')


class AsteriskReuseTests(unittest.TestCase):
    def validate(self, assembled=True, job='success', conclusion='failure', comparison='ahead'):
        run = dict(status='completed', conclusion=conclusion,
                   path='.github/workflows/build-packages.yml', head_sha='a' * 40,
                   head_repository=dict(full_name='owner/repo'))

        def api(command):
            url = command[-1]
            if '/compare/' in url:
                result = dict(status=comparison)
            elif '/artifacts?' in url:
                result = dict(artifacts=[dict(name='asterisk20-opkg-feed-123', expired=False)] if assembled else [])
            elif '/jobs?' in url:
                result = dict(jobs=[dict(name='Asterisk 20 feed / Build and verify Asterisk 20 feed', conclusion=job)])
            else:
                raise AssertionError(url)
            return json.dumps(result).encode()

        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / 'env'
            with mock.patch.dict(os.environ, dict(GITHUB_REPOSITORY='owner/repo', SOURCE_RUN_ID='123',
                                                   GITHUB_SHA='b' * 40, GITHUB_ENV=str(env_path))), \
                 mock.patch.object(Path, 'read_text', return_value=json.dumps(run)), \
                 mock.patch('subprocess.check_output', side_effect=api):
                exec(CODE, {})
            return env_path.read_text()

    def test_reuses_successful_asterisk_job_despite_unrelated_shard_failure(self):
        output = self.validate()
        self.assertIn('SOURCE_ASSEMBLED=1\n', output)
        self.assertIn('SOURCE_ARTIFACT=asterisk20-opkg-feed-123\n', output)

    def test_rejects_failed_asterisk_job(self):
        with self.assertRaisesRegex(AssertionError, 'Asterisk source job did not succeed'):
            self.validate(job='failure')

    def test_rejects_unsuccessful_targeted_source(self):
        with self.assertRaisesRegex(AssertionError, 'Targeted source run did not succeed'):
            self.validate(assembled=False)

    def test_accepts_successful_targeted_source(self):
        self.assertIn('SOURCE_ARTIFACT=userspace-shard-0-123\n',
                      self.validate(assembled=False, conclusion='success'))

    def test_rejects_unrelated_source_revision(self):
        with self.assertRaisesRegex(AssertionError, 'Source revision is not an ancestor'):
            self.validate(comparison='diverged')
