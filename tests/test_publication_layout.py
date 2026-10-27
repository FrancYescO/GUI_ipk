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
        self.assertEqual(sum(r['storage'] == 'pages' for r in rows), 6049)
        self.assertEqual(set(catalog['releases']), {'freeswitch-sounds'})
        self.assertLess(sum(r['size'] for r in rows if r['storage'] == 'pages'), 750 * 1024**2)
        pins = json.loads((ROOT / 'build/application-archive/manifest.json').read_text())
        for pin in pins['packages']:
            matches = [r for r in rows if r['filename'] == pin['filename']]
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0]['sha256'], pin['sha256'])
            self.assertEqual(matches[0]['storage'], 'pages')
        self.assertTrue(all(r['storage'] == 'pages' for r in rows if r['kind'] == 'kernel'))
        self.assertEqual(sum(r['section'] == 'telephony/asterisk-20' for r in rows), 25)
        self.assertEqual(sum(r['storage'] == 'freeswitch-sounds' for r in rows), 8)

    def test_kernel_sources_are_separated_by_exact_abi_and_staging(self):
        spec = importlib.util.spec_from_file_location('render_publication', ROOT / 'scripts/render-publication.py')
        renderer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(renderer)
        catalog = fetch.read_catalog(ROOT / 'build/publication/bootstrap.json.gz', live=False)
        manifest = renderer.kernel_manifest(catalog['records'])
        self.assertNotIn('url', manifest)  # No misleading combined OPKG source.
        self.assertEqual([(r['profile'], r['count']) for r in manifest['profiles']],
                         [('4.1.38-vbnto', 5), ('4.1.38-vbnts', 5), ('4.1.52-vbntk', 49)])
        self.assertEqual([(r['profile'], r['count']) for r in manifest['candidates']],
                         [('4.1.38-vbnto-candidates', 220), ('4.1.38-vbnts-candidates', 212)])
        for row in manifest['profiles'] + manifest['candidates']:
            self.assertEqual(row['url'], layout.SITE + '/kernel/' + row['profile'])
            self.assertTrue(row['source'].endswith(' ' + row['url']))
            records = [r for r in catalog['records'] if r['section'] == 'kernel/' + row['profile']]
            self.assertTrue(all((layout.parse(r['control']).get('X-Module-Staging-Only') == 'yes') == row['staging_only'] for r in records))
            self.assertTrue(all(row['kernel_package'] in layout.parse(r['control'])['Depends'] for r in records))
        with tempfile.TemporaryDirectory() as temp:
            site = Path(temp)
            (site / 'kernel').mkdir()
            renderer.write_kernel_overview(site, manifest)
            page = (site / 'kernel/index.html').read_text()
            for row in manifest['profiles'] + manifest['candidates']:
                self.assertIn(row['source'], page)
            self.assertIn('no compatible runtime firmware', page)

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
