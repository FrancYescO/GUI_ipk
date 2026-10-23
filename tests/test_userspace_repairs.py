import hashlib
import importlib.util
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MERGE = load('merge-userspace-repairs')
FETCH = load('fetch-userspace-repairs')


def archive(entries):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as output:
        for name, data in entries:
            entry = tarfile.TarInfo(name)
            entry.size = len(data)
            output.addfile(entry, io.BytesIO(data))
    return stream.getvalue()


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.feed = self.root / 'feed'
        self.repairs = self.root / 'repairs'
        self.repairs.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def package(self, directory, name, version='1-1', section='packages', payload=b'old', module=False):
        control = 'Package: {}\nVersion: {}\nArchitecture: all\nDescription: test\n'.format(name, version)
        filename = '{}_{}_all.ipk'.format(name, version)
        target = directory / section / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        payload_path = './lib/modules/4.1.38/test.ko' if module else './usr/share/' + name
        target.write_bytes(archive([('./debian-binary', b'2.0\n'),
                                    ('./control.tar.gz', archive([('./control', control.encode())])),
                                    ('./data.tar.gz', archive([(payload_path, payload)]))]))
        return target, control

    def baseline(self):
        target, control = self.package(self.feed, 'example')
        index = control + 'Filename: {}\nSize: {}\nSHA256sum: {}\n'.format(target.name, target.stat().st_size, hashlib.sha256(target.read_bytes()).hexdigest())
        (target.parent / 'Packages').write_text(index)
        return target

    def test_replace_package_and_refresh_indexes_without_touching_other_feeds(self):
        original = self.baseline()
        extra = self.feed / 'kernel/4.1.52/manual.ipk'
        extra.parent.mkdir(parents=True)
        extra.write_bytes(b'untouched')
        replacement, _ = self.package(self.repairs / '100', 'example', section='base', payload=b'fixed')
        expected = replacement.read_bytes()
        result = MERGE.merge(self.feed, self.repairs)
        self.assertEqual(len(result['repaired_packages']), 1)
        self.assertFalse(original.exists())
        self.assertEqual((self.feed / 'base' / replacement.name).read_bytes(), expected)
        self.assertNotIn('Package: example', (self.feed / 'packages/Packages').read_text())
        self.assertIn(hashlib.sha256(expected).hexdigest(), (self.feed / 'base/Packages').read_text())
        self.assertEqual(extra.read_bytes(), b'untouched')
        self.assertEqual(json.loads((self.feed / 'repairs-report.json').read_text())['repaired_packages'][0]['previous_versions'], ['1-1'])

    def test_conflicting_repairs_leave_baseline_unchanged(self):
        original = self.baseline()
        before = original.read_bytes()
        self.package(self.repairs / '100', 'example')
        self.package(self.repairs / '200', 'example', version='2-1')
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            MERGE.merge(self.feed, self.repairs)
        self.assertEqual(original.read_bytes(), before)

    def test_existing_version_change_requires_a_full_build(self):
        original = self.baseline()
        before = original.read_bytes()
        self.package(self.repairs / '100', 'example', version='2-1')
        with self.assertRaisesRegex(ValueError, 'existing version'):
            MERGE.merge(self.feed, self.repairs)
        self.assertEqual(original.read_bytes(), before)

    def test_kernel_payload_cannot_enter_shared_repair_feed(self):
        original = self.baseline()
        before = original.read_bytes()
        self.package(self.repairs / '100', 'example', module=True, payload=b'\x7fELFmodule')
        with self.assertRaisesRegex(ValueError, 'kernel module payload'):
            MERGE.merge(self.feed, self.repairs)
        self.assertEqual(original.read_bytes(), before)

    def test_only_successful_same_repository_targeted_workflow_is_eligible(self):
        valid = dict(status='completed', conclusion='success', path=FETCH.WORKFLOW,
                     event='workflow_dispatch', head_sha='a' * 40,
                     head_repository=dict(full_name='owner/repo'))
        FETCH.validate_run(valid, 'owner/repo')
        for key, value in [('conclusion', 'failure'), ('event', 'pull_request'), ('head_sha', 'invalid'),
                           ('path', '.github/workflows/other.yml'), ('head_repository', dict(full_name='other/repo'))]:
            invalid = dict(valid)
            invalid[key] = value
            with self.assertRaises(ValueError):
                FETCH.validate_run(invalid, 'owner/repo')


if __name__ == '__main__':
    unittest.main()
