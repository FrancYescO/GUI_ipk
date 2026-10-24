import gzip
import hashlib
import importlib.util
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / ('scripts/' + name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prepare = load('prepare-release-feed')
publish = load('publish-release-feed')


def archive(files):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:gz') as target:
        for name, content in files.items():
            entry = tarfile.TarInfo(name)
            entry.size = len(content)
            target.addfile(entry, io.BytesIO(content))
    return output.getvalue()


class ReleaseFeedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.output = self.root / 'output'
        self.provenance = dict(run_id='123', revision='a' * 40,
                               workflow='.github/workflows/build-packages.yml',
                               url='https://github.com/example/feed/actions/runs/123')
        (self.source / 'source-run.json').write_text(json.dumps(self.provenance))
        self.ipk = self.source / 'example_1.0-1_all.ipk'
        self.package()

    def package(self, extra=''):
        control = ('Package: example\nVersion: 1.0-1\nArchitecture: all\n' + extra).encode()
        self.ipk.write_bytes(archive({'./control.tar.gz': archive({'./control': control}),
                                      './data.tar.gz': archive({'./usr/share/example': b'payload'})}))

    def prepared(self):
        return prepare.prepare(self.source, self.output, ['example'], 'example/feed')

    def test_relative_filenames_and_reproducible_snapshot(self):
        info = self.prepared()
        other = self.root / 'other'
        self.assertEqual(info, prepare.prepare(self.source, other, ['example'], 'example/feed'))
        for path in self.output.iterdir():
            self.assertEqual(path.read_bytes(), (other / path.name).read_bytes())
        index = (self.output / 'Packages').read_bytes()
        self.assertIn(b'Filename: example_1.0-1_all.ipk\n', index)
        self.assertEqual(gzip.decompress((self.output / 'Packages.gz').read_bytes()), index)
        self.assertIn(hashlib.sha256(self.ipk.read_bytes()).hexdigest().encode(), index)
        self.assertNotIn(b'https://', index)

    def test_missing_package_fails_before_output(self):
        with self.assertRaisesRegex(ValueError, 'Missing requested'):
            prepare.prepare(self.source, self.output, ['missing'], 'example/feed')
        self.assertFalse(self.output.exists())

    def test_duplicate_candidates_are_rejected(self):
        directory = self.source / 'duplicate'
        directory.mkdir()
        (directory / self.ipk.name).write_bytes(self.ipk.read_bytes())
        with self.assertRaisesRegex(ValueError, 'Multiple candidates'):
            self.prepared()

    def test_transport_metadata_is_rejected(self):
        self.package('Filename: https://example.org/untrusted.ipk\n')
        with self.assertRaisesRegex(ValueError, 'transport fields'):
            self.prepared()

    def test_symlinks_are_rejected(self):
        directory = self.source / 'linked'
        directory.mkdir()
        (directory / self.ipk.name).symlink_to(self.ipk)
        with self.assertRaisesRegex(ValueError, 'symlinks'):
            self.prepared()

    def test_provenance_repository_must_match(self):
        self.provenance['url'] = 'https://github.com/other/feed/actions/runs/123'
        (self.source / 'source-run.json').write_text(json.dumps(self.provenance))
        with self.assertRaisesRegex(ValueError, 'provenance'):
            self.prepared()

    def test_native_compiler_and_kernel_packages_are_rejected(self):
        for name in ('gcc', 'kmod-tun'):
            with self.assertRaisesRegex(ValueError, 'separate profiles'):
                prepare.prepare(self.source, self.output, [name], 'example/feed')

    def test_draft_is_exposed_only_after_all_uploads(self):
        info = self.prepared()
        metadata = self.root / 'info.json'
        metadata.write_text(json.dumps(info))
        calls = []
        release = dict(id=1, draft=True, tag_name=info['tag'], target_commitish=info['revision'])

        def gh(*args):
            calls.append(args)
            if args[:3] == ('api', '--paginate', '--slurp'):
                return json.dumps([[]]).encode()
            if args[:2] == ('release', 'view'):
                return b'{"databaseId": 1}'
            if args[0] == 'api':
                return json.dumps(release).encode()
            return b''

        with patch.object(publish, 'gh', gh):
            self.assertEqual(publish.publish(self.output, metadata), info['url'])
        self.assertEqual(calls[-1][:3], ('release', 'edit', info['tag']))
        uploads = [call for call in calls if call[:2] == ('release', 'upload')]
        self.assertEqual(len(uploads), len(list(self.output.iterdir())))
        self.assertTrue(uploads[0][3].endswith('.ipk'))
        self.assertFalse(any('--clobber' in call for call in calls))

    def test_published_snapshot_rejects_additional_assets(self):
        info = self.prepared()
        metadata = self.root / 'info.json'
        metadata.write_text(json.dumps(info))
        release = dict(id=1, draft=False, tag_name=info['tag'], target_commitish=info['revision'])
        calls = []

        def gh(*args):
            calls.append(args)
            if args[-1].endswith('/assets?per_page=100'):
                return b'[[]]'
            return json.dumps([[release]]).encode()

        with patch.object(publish, 'gh', gh):
            with self.assertRaisesRegex(ValueError, 'cannot be modified'):
                publish.publish(self.output, metadata)
        self.assertFalse(any(call[0] == 'release' for call in calls))

    def test_retry_checks_every_asset_and_makes_no_changes(self):
        info = self.prepared()
        metadata = self.root / 'info.json'
        metadata.write_text(json.dumps(info))
        release = dict(id=1, draft=False, tag_name=info['tag'], target_commitish=info['revision'])
        calls = []

        def gh(*args):
            calls.append(args)
            if args[0] == 'api':
                records = ([dict(name=p.name) for p in self.output.iterdir()]
                           if args[-1].endswith('/assets?per_page=100') else [release])
                return json.dumps([records]).encode()
            self.assertEqual(args[:2], ('release', 'download'))
            name = args[args.index('--pattern') + 1]
            target = Path(args[args.index('--dir') + 1]) / name
            target.write_bytes((self.output / name).read_bytes())
            return b''

        with patch.object(publish, 'gh', gh):
            self.assertEqual(publish.publish(self.output, metadata), info['url'])
        self.assertEqual(sum(c[:2] == ('release', 'download') for c in calls),
                         len(list(self.output.iterdir())))

    def test_differing_remote_asset_fails_before_any_upload(self):
        info = self.prepared()
        metadata = self.root / 'info.json'
        metadata.write_text(json.dumps(info))
        release = dict(id=1, draft=True, tag_name=info['tag'], target_commitish=info['revision'])
        calls = []

        def gh(*args):
            calls.append(args)
            if args[0] == 'api':
                return json.dumps([[dict(name=self.ipk.name)] if args[-1].endswith('/assets?per_page=100')
                                   else [release]]).encode()
            self.assertEqual(args[:2], ('release', 'download'))
            (Path(args[args.index('--dir') + 1]) / self.ipk.name).write_bytes(b'different bytes')
            return b''

        with patch.object(publish, 'gh', gh):
            with self.assertRaisesRegex(ValueError, 'Refusing to overwrite'):
                publish.publish(self.output, metadata)
        self.assertFalse(any(c[:2] == ('release', 'upload') for c in calls))

    def test_local_tampering_fails_before_contacting_github(self):
        info = self.prepared()
        metadata = self.root / 'info.json'
        metadata.write_text(json.dumps(info))
        (self.output / self.ipk.name).write_bytes(b'changed')
        with patch.object(publish, 'gh') as gh:
            with self.assertRaisesRegex(ValueError, 'checksum differs'):
                publish.publish(self.output, metadata)
            gh.assert_not_called()


if __name__ == '__main__':
    unittest.main()
