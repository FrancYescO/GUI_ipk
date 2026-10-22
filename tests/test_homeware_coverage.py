"""Exercise coverage semantics against small OPKG inventories and the baseline."""
import csv
import gzip
import hashlib
import importlib.util
import tempfile
import subprocess
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('homeware', ROOT / 'scripts/report-homeware-coverage.py')
HOMEWARE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HOMEWARE)


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.catalog = self.root / 'catalog.tsv'

    def tearDown(self):
        self.temp.cleanup()

    def catalog_rows(self, names):
        with self.catalog.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, ['homeware', 'section', 'name', 'version', 'architecture'], delimiter='\t')
            writer.writeheader()
            for name in names:
                writer.writerow(dict(homeware='18', section='base', name=name,
                                     version='1-1', architecture='arm_cortex-a9_neon'))

    def index(self, section, names, compressed=False):
        path = self.root / 'feed' / section
        path.mkdir(parents=True, exist_ok=True)
        text = '\n\n'.join('Package: {}\nVersion: 2-1\nArchitecture: arm_cortex-a9_neon'.format(n) for n in names) + '\n'
        if compressed:
            with gzip.open(str(path / 'Packages.gz'), 'wt') as stream:
                stream.write(text)
        else:
            (path / 'Packages').write_text(text)
        return self.root / 'feed'

    def test_name_presence_crosses_sections_but_not_abi_names(self):
        self.catalog_rows(['rtl_433', 'libcurl4'])
        feed = self.index('packages', ['rtl_433', 'libcurl'], compressed=True)
        rows, summary = HOMEWARE.compare(self.catalog, feed)
        self.assertEqual([row['status'] for row in rows], ['present', 'missing'])
        self.assertEqual(rows[0]['built_versions'], '2-1')
        self.assertTrue(rows[0]['source_url'].endswith('/base/rtl_433_1-1_arm_cortex-a9_neon.ipk'))
        self.assertEqual(summary['versions'][0]['present'], 1)

    def test_recipe_and_selection_distinguish_remaining_work(self):
        self.catalog_rows(['available', 'disabled', 'unknown'])
        feed = self.index('base', ['unrelated'])
        metadata = self.root / '.packageinfo'
        metadata.write_text('Source-Makefile: feeds/packages/net/example/Makefile\nPackage: available\n\nPackage: disabled\n')
        config = self.root / '.config'
        config.write_text('CONFIG_PACKAGE_available=m\n# CONFIG_PACKAGE_disabled is not set\n')
        rows, _ = HOMEWARE.compare(self.catalog, feed, metadata, config)
        self.assertEqual([row['status'] for row in rows], ['not-built', 'not-selected', 'no-recipe'])
        self.assertEqual(rows[0]['recipe'], 'feeds/packages/net/example/Makefile')

    def test_names_are_deduplicated_across_source_versions(self):
        self.catalog_rows(['example'])
        with self.catalog.open('a') as stream:
            stream.write('18\tpackages\texample\t2-1\tall\n')
        feed = self.index('base', ['example'])
        rows, summary = HOMEWARE.compare(self.catalog, feed)
        self.assertEqual(len(rows), 2)
        self.assertEqual(summary['versions'][0]['names'], 1)

    def test_no_indexes_and_duplicate_catalog_fail(self):
        self.catalog_rows(['example'])
        with self.assertRaisesRegex(ValueError, 'No OPKG indexes'):
            HOMEWARE.compare(self.catalog, self.root / 'absent')
        with self.catalog.open('a') as stream:
            stream.write('18\tbase\texample\t1-1\tarm_cortex-a9_neon\n')
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            HOMEWARE.inventory(self.catalog)

    def test_baseline_has_all_recorded_files_and_full_names(self):
        rows = HOMEWARE.inventory(ROOT / 'build/homeware/catalog.tsv')
        self.assertEqual(Counter(row['homeware'] for row in rows), {'18': 4068, '19': 494})
        self.assertEqual(len({row['name'] for row in rows if row['homeware'] == '18'}), 4066)
        names = {row['name'] for row in rows}
        self.assertTrue({'rtl_433', 'ddns-scripts_freedns_42_pl', 'busybox_telnet'} <= names)
        self.assertNotIn('rtl', names)

    def test_translation_templates_do_not_become_language_packages(self):
        source = self.root / 'feeds/luci/luci.mk'
        source.parent.mkdir(parents=True)
        source.write_text('\n' * 9 + 'LUCI_LANGUAGES:=$(sort $(filter-out templates,$(notdir $(wildcard ${CURDIR}/po/*))))\n')
        subprocess.run(['patch', '-s', '-p1', '-d', str(self.root), '-i',
                        str(ROOT / 'patches/homeware-luci-translation-directories.patch')], check=True)
        app = self.root / 'application'
        for language in ('en', 'de', 'templates'):
            (app / 'po' / language).mkdir(parents=True)
        (app / 'po' / 'application.pot').write_text('translation template')
        makefile = self.root / 'check.mk'
        makefile.write_text("all:\n\t@printf '%s\\n' '$(LUCI_LANGUAGES)'\n")
        result = subprocess.check_output(['make', '-s', '-f', str(source), '-f', str(makefile)], cwd=app)
        self.assertEqual(result.decode().strip(), 'de en')

    def test_imported_recipe_files_match_the_manifest(self):
        overlay = ROOT / 'build/homeware-overlay'
        expected = {}
        for line in (overlay / 'SHA256SUMS').read_text().splitlines():
            digest, name = line.split('  ', 1)
            self.assertNotIn(name, expected)
            expected[name] = digest
        actual = {p.relative_to(overlay).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in overlay.rglob('*') if p.is_file() and p.name != 'SHA256SUMS'}
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
