import gzip
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('dependencies', ROOT / 'scripts/report-feed-dependencies.py')
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class DependencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def index(self, section, text, compressed=False):
        directory = self.root / section
        directory.mkdir(parents=True, exist_ok=True)
        if compressed:
            with gzip.open(str(directory / 'Packages.gz'), 'wt') as stream:
                stream.write(text)
        else:
            (directory / 'Packages').write_text(text)

    def test_alternatives_and_explicit_providers_resolve_names(self):
        self.index('base', 'Package: app\nVersion: 1\nDepends: absent | renamed, old_name\n\n')
        self.index('packages', 'Package: renamed\nVersion: 2\nProvides: old_name\n\n', compressed=True)
        issues, summary = AUDIT.audit(self.root)
        self.assertEqual(issues, [])
        self.assertEqual(summary['statuses'], {'name-available': 2})

    def test_library_abi_names_are_not_inferred(self):
        self.index('base', 'Package: app\nVersion: 1\nDepends: libcurl4, kmod-cake\n\nPackage: libcurl\nVersion: 7\n\n')
        issues, summary = AUDIT.audit(self.root)
        self.assertEqual({r['dependency']: r['status'] for r in issues},
                         {'libcurl4': 'unresolved-userspace', 'kmod-cake': 'unresolved-kernel'})
        self.assertEqual(summary['missing'][0]['affected_packages'], 1)

    def test_versioned_provider_is_not_silently_accepted(self):
        self.index('base', 'Package: app\nVersion: 1\nDepends: old_name (>= 3)\n\nPackage: replacement\nVersion: 2\nProvides: old_name\n\n')
        issues, _ = AUDIT.audit(self.root)
        self.assertEqual(issues[0]['status'], 'version-check-required')
        self.assertIn('replacement=2 [base]', issues[0]['providers'])

    def test_inline_versioned_provider_retains_declared_version(self):
        self.index('base', 'Package: app\nVersion: 1\nDepends: erlang-erts (>= 6.4)\n\nPackage: erlang\nVersion: 20\nProvides: erlang-erts=6.4\n\n')
        issues, _ = AUDIT.audit(self.root)
        self.assertEqual(issues[0]['status'], 'version-check-required')
        self.assertIn('Provides: erlang-erts=6.4', issues[0]['providers'])

    def test_kernel_profiles_do_not_supply_each_others_modules(self):
        self.index('base', 'Package: app\nVersion: 1\nDepends: kmod-example\n\n')
        self.index('kernel/4.1.38', 'Package: kernel\nVersion: 4.1.38\n\n')
        self.index('kernel/4.1.52', 'Package: kmod-example\nVersion: 4.1.52\n\n')
        issues, _ = AUDIT.audit(self.root, ['kernel/4.1.38'])
        self.assertEqual(issues[0]['status'], 'unresolved-kernel')
        issues, _ = AUDIT.audit(self.root, ['kernel/4.1.52'])
        self.assertEqual(issues, [])

    def test_folded_dependency_fields_are_retained(self):
        self.index('base', 'Package: app\nVersion: 1\nDepends: libc,\n libmissing\n\nPackage: libc\nVersion: 1\n\n')
        issues, _ = AUDIT.audit(self.root)
        self.assertEqual([r['dependency'] for r in issues], ['libmissing'])

    def test_invalid_and_missing_indexes_fail(self):
        with self.assertRaisesRegex(ValueError, 'No OPKG indexes'):
            AUDIT.audit(self.root)
        with self.assertRaisesRegex(ValueError, 'relative path'):
            AUDIT.audit(self.root, ['../other'])
        with self.assertRaisesRegex(ValueError, 'has no index'):
            AUDIT.audit(self.root, ['kernel/4.1.38'])
        self.index('base', 'Package: app\nVersion: 1\nDepends: invalid???\n\n')
        with self.assertRaisesRegex(ValueError, 'Unrecognized dependency'):
            AUDIT.audit(self.root)
