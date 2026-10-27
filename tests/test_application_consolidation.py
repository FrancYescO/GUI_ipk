import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('consolidation', ROOT / 'scripts/consolidate-application-feed.py')
consolidation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(consolidation)


def archive(files):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as tar:
        for name, data in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            tar.addfile(member, io.BytesIO(data))
    return stream.getvalue()


class ApplicationConsolidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'snapshots'
        snapshot = self.source / 'extras-example'
        snapshot.mkdir(parents=True)
        self.filename = 'example_1.0-1_all.ipk'
        self.ipk = snapshot / self.filename
        self.payload = archive({'./control.tar.gz': archive({'./control': b'Package: example\nVersion: 1.0-1\nArchitecture: all\n'}),
                                './data.tar.gz': archive({'./usr/share/example': b'bytes'})})
        self.ipk.write_bytes(self.payload)
        record = {'package': 'example', 'version': '1.0-1', 'architecture': 'all', 'filename': self.filename,
                  'size': len(self.payload), 'sha256': hashlib.sha256(self.payload).hexdigest()}
        original = json.dumps({'packages': [record], 'source': {'run_id': '123'}}) + '\n'
        (snapshot / 'source.json').write_text(original)
        self.manifest = {'groups': {'example': {'former_tag': 'extras-example',
                                              'source_manifest_sha256': hashlib.sha256(original.encode()).hexdigest()}},
                         'packages': [dict(record, group='example')]}

    def test_original_bytes_and_relative_download_paths_are_preserved(self):
        output = self.root / 'output'
        self.assertEqual(consolidation.consolidate(self.source, output, self.manifest), 1)
        self.assertEqual((output / self.filename).read_bytes(), self.payload)
        self.assertIn('Filename: ' + self.filename, (output / 'Packages').read_text())
        self.assertNotIn('Filename: https://', (output / 'Packages').read_text())

    def test_archive_is_rebuildable_without_retired_snapshots(self):
        first, second = self.root / 'first', self.root / 'second'
        consolidation.consolidate(self.source, first, self.manifest)
        consolidation.consolidate(first, second, self.manifest)
        for file in first.iterdir():
            self.assertEqual(file.read_bytes(), (second / file.name).read_bytes())

    def test_changed_package_or_provenance_cannot_be_published(self):
        self.ipk.write_bytes(self.payload + b'changed')
        with self.assertRaisesRegex(ValueError, 'differs from pinned snapshot'):
            consolidation.consolidate(self.source, self.root / 'changed', self.manifest)
        self.assertFalse((self.root / 'changed').exists())
        self.ipk.write_bytes(self.payload)
        (self.ipk.parent / 'source.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'provenance mismatch'):
            consolidation.consolidate(self.source, self.root / 'provenance', self.manifest)

    def test_pinned_archive_covers_all_thirteen_packages(self):
        manifest = json.loads((ROOT / 'build/application-archive/manifest.json').read_text())
        self.assertEqual(len(manifest['packages']), 13)
        self.assertEqual(len(manifest['groups']), 7)
        self.assertEqual(len({p['package'] for p in manifest['packages']}), 13)
        self.assertTrue(manifest['url'].endswith('/application-packages-v1'))


if __name__ == '__main__':
    unittest.main()
