import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import publication_layout as layout
spec = importlib.util.spec_from_file_location('fetch_publication', ROOT / 'scripts/fetch-publication-inputs.py')
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


class PublicationTests(unittest.TestCase):
    def test_complete_bootstrap_has_semantic_components_and_all_updates(self):
        catalog = json.loads(gzip.decompress((ROOT / 'build/publication/bootstrap.json.gz').read_bytes()))
        rows = catalog['records']
        self.assertEqual(len(rows), 6057)
        self.assertEqual(sum(r['storage'] == 'pages' for r in rows), 5533)
        self.assertEqual(set(catalog['releases']), {'kernel', 'asterisk20', 'freeswitch-sounds'})
        self.assertLess(sum(r['size'] for r in rows if r['storage'] == 'pages'), 750 * 1024**2)
        pins = json.loads((ROOT / 'build/application-archive/manifest.json').read_text())
        for pin in pins['packages']:
            matches = [r for r in rows if r['filename'] == pin['filename']]
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0]['sha256'], pin['sha256'])
            self.assertEqual(matches[0]['storage'], 'pages')
        self.assertTrue(all(r['storage'] == 'kernel' for r in rows if r['kind'] == 'kernel'))
        self.assertEqual(sum(r['storage'] == 'asterisk20' for r in rows), 25)
        self.assertEqual(sum(r['storage'] == 'freeswitch-sounds' for r in rows), 8)

    def test_cached_bytes_are_verified_and_remote_urls_are_restricted(self):
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            data = b'verified package'
            digest = hashlib.sha256(data).hexdigest()
            pin = {'sha256': digest, 'size': len(data), 'filename': 'test.ipk'}
            (cache / digest).write_bytes(data)
            with patch('urllib.request.urlopen', side_effect=AssertionError('Unexpected network')):
                self.assertEqual(fetch.retrieve(pin, cache, []), cache / digest)
            (cache / digest).write_bytes(b'corrupt')
            with self.assertRaises(ValueError):
                fetch.retrieve(pin, cache, ['https://example.org/foreign.ipk'])

    def test_snapshots_and_indexes_are_reproducible(self):
        row = {'control': 'Package: sample\nVersion: 1', 'filename': 'sample.ipk', 'size': 3, 'sha256': 'a' * 64}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            layout.write_index(root, [row])
            first = (root / 'Packages.gz').read_bytes()
            layout.write_index(root, [row])
            self.assertEqual(first, (root / 'Packages.gz').read_bytes())
            self.assertEqual(gzip.decompress(first), layout.index([row]))
            layout.write_snapshot(root / 'a.gz', {'records': [row]})
            layout.write_snapshot(root / 'b.gz', {'records': [row]})
            self.assertEqual((root / 'a.gz').read_bytes(), (root / 'b.gz').read_bytes())


if __name__ == '__main__':
    unittest.main()
