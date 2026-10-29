import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import kernel_opkg_providers as providers
import publication_layout as layout


class KernelProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.rows = layout.kernel_inputs(Path(cls.temp.name) / 'inputs')
        cls.catalog = json.loads(gzip.decompress((ROOT / 'build/publication/bootstrap.json.gz').read_bytes()))
        cls.by_identity = {(r['section'], r['package'], r['version']): r for r in cls.rows}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_all_published_kernel_bytes_are_reproduced(self):
        expected = {(r['section'], r['package'], r['version']): r for r in self.catalog['records'] if r['kind'] == 'kernel'}
        self.assertEqual(set(expected), set(self.by_identity))
        for key, row in expected.items():
            actual = self.by_identity[key]
            for field in ('sha256', 'size', 'filename', 'control', 'architecture', 'profile'):
                self.assertEqual(actual[field], row[field], (key, field))

    def test_no_replaces_and_every_module_preserves_source_bytes(self):
        module_count = 0
        for row in self.rows:
            control = providers.fields(row['control'])
            self.assertNotIn('Replaces', control, row['package'])
            self.assertIn('kernel (= ' + providers.definitions()[row['profile']]['kernel_package'] + ')', control['Depends'])
            outer = providers.unpack(Path(row['_path']).read_bytes())
            data = providers.unpack(outer['data.tar.gz'])
            scripts = providers.unpack(outer['control.tar.gz'])
            if row.get('_archive_source'):
                original = providers.unpack(Path(row['_archive_source']).read_bytes())
                self.assertEqual(data, providers.unpack(original['data.tar.gz']), row['package'])
            module_count += len(data)
            self.assertTrue(all(name.endswith('.ko') for name in data))
            with tarfile.open(fileobj=io.BytesIO(outer['data.tar.gz'])) as archive:
                directories = {m.name.removeprefix('./').rstrip('/') for m in archive if m.isdir()}
            for name in data:
                self.assertTrue({str(p) for p in Path(name).parents if str(p) != '.'} <= directories, name)
            for name, script in scripts.items():
                if name == 'control':
                    continue
                check = subprocess.run(['sh', '-n'], input=script, capture_output=True)
                self.assertEqual(check.returncode, 0, (row['package'], name, check.stderr))
                self.assertNotIn(b'insmod ', script)
                self.assertNotIn(b'rmmod ', script)
                self.assertNotIn(b'--force-depends', script)
                self.assertNotIn(b'opkg status', script)
        self.assertEqual(module_count, 830)

    def test_staging_is_never_a_module_provider(self):
        for row in self.rows:
            control = providers.fields(row['control'])
            outer = providers.unpack(Path(row['_path']).read_bytes())
            data = providers.unpack(outer['data.tar.gz'])
            if any(name.startswith('usr/lib/kernel-module-candidates/') for name in data):
                self.assertNotIn('Provides', control)
                self.assertNotEqual(control['Package'], 'kmod-tun')

    def test_tun_and_complete_group_capabilities(self):
        for profile in providers.definitions():
            selected = [r for r in self.rows if r['profile'] == profile and r['section'] == providers.definitions()[profile]['feed']]
            advertised = {providers.fields(r['control'])['Package'] for r in selected}
            advertised |= {v.strip() for r in selected for v in providers.fields(r['control']).get('Provides', '').split(',') if v.strip()}
            self.assertEqual('kmod-tun' in advertised, profile in ('4.1.38-vbnto', '4.1.38-vbntk', '4.1.52-vbntk', '4.1.52-vcnta', '4.1.52-vbntv'))
            for row in selected:
                f = providers.fields(row['control'])
                if f.get('X-Kernel-Capability') == 'yes':
                    self.assertEqual(providers.unpack(providers.unpack(Path(row['_path']).read_bytes())['data.tar.gz']), {})
        # cls_basic is absent from the runtime replacement set on .69: do not lie
        # that four of its five stock modules replace all of kmod-sched-core.
        selected = [r for r in self.rows if r['profile'] == '4.1.52-vbntk']
        self.assertFalse(any(providers.fields(r['control']).get('X-Kernel-Capability-Name') == 'kmod-sched-core' for r in selected))

    def test_archived_sources_are_not_in_active_indexes(self):
        active = {(r['section'], r['filename']) for r in self.rows}
        for row in self.rows:
            if row.get('_archive_source'):
                self.assertNotIn((row['section'], row['_archive_filename']), active)
                self.assertEqual(hashlib.sha256(Path(row['_archive_source']).read_bytes()).hexdigest(), providers.fields(row['control'])['X-Original-IPK-SHA256'])


if __name__ == '__main__':
    unittest.main()

class PackageHookLockTests(unittest.TestCase):
    def run_guard(self, status, replacements=None, dependencies=None, active=()):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / 'status'
            database.write_text(status)
            module_root = root / 'sys/module'
            module_root.mkdir(parents=True)
            for name in active:
                (module_root / name).mkdir()
            # Any nested OPKG call would fail under the parent install's lock.
            opkg = root / 'opkg'
            marker = root / 'nested-opkg'
            opkg.write_text('#!/bin/sh\ntouch "'+str(marker)+'"\nexit 99\n')
            opkg.chmod(0o755)
            script = providers.guard('4.1.38-1-exact', replacements or {}, dependencies)
            script = script.replace(b'/usr/lib/opkg/status', str(database).encode())
            script = script.replace(b'/sys/module/', (str(module_root)+'/').encode())
            import os
            result = subprocess.run(['sh'], input=script, capture_output=True,
                                    env={**os.environ, 'PATH':str(root)+':'+os.environ['PATH'], 'IPKG_INSTROOT':''})
            self.assertFalse(marker.exists(), 'Maintainer hook must not invoke OPKG while its lock is held')
            return result

    @staticmethod
    def stanza(name, version, depends='', state='install ok installed'):
        return 'Package: '+name+'\nVersion: '+version+'\nStatus: '+state+'\nDepends: '+depends+'\n\n'

    def test_exact_kernel_passes_without_nested_opkg(self):
        status = self.stanza('kernel-extra', 'wrong') + self.stanza('kernel', '4.1.38-1-exact')
        self.assertEqual(self.run_guard(status).returncode, 0)

    def test_missing_uninstalled_and_wrong_kernel_fail_closed(self):
        for status in ('', self.stanza('kernel', 'wrong'),
                       self.stanza('kernel', '4.1.38-1-exact', state='deinstall ok not-installed')):
            with self.subTest(status=status):
                self.assertNotEqual(self.run_guard(status).returncode, 0)

    def test_stock_dependency_requires_installed_exact_abi(self):
        base = self.stanza('kernel', '4.1.38-1-exact')
        for dep, accepted in [('', False),
                (self.stanza('kmod-base', '1', 'kernel (= wrong)'), False),
                (self.stanza('kmod-base', '1', 'kernel (= 4.1.38-1-exact)'), True),
                (self.stanza('kmod-base-extra', '1', 'kernel (= 4.1.38-1-exact)'), False)]:
            with self.subTest(dep=dep):
                result = self.run_guard(base+dep, dependencies=['kmod-base'])
                self.assertEqual(result.returncode == 0, accepted, result.stderr)

    def test_active_legacy_module_still_blocks_migration(self):
        base = self.stanza('kernel', '4.1.38-1-exact')
        legacy = self.stanza('kmod-tun', '4.1.38-1', 'kernel')
        result = self.run_guard(base+legacy, {'kmod-tun':['tun']}, active=['tun'])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'active module tun', result.stderr)
        self.assertEqual(self.run_guard(base+legacy, {'kmod-tun':['tun']}).returncode, 0)

    def test_uninstalled_duplicates_cannot_supply_abi_evidence(self):
        exact = 'kernel (= 4.1.38-1-exact)'
        base = self.stanza('kernel', '4.1.38-1-exact')
        stale_kernel = self.stanza('kernel', 'old', state='install ok not-installed')
        self.assertEqual(self.run_guard(stale_kernel+base).returncode, 0)
        stale_dependency = self.stanza('kmod-base', '1', exact, state='install ok not-installed')
        installed_dependency = self.stanza('kmod-base', '0', 'kernel (= wrong)')
        result = self.run_guard(base+stale_dependency+installed_dependency, dependencies=['kmod-base'])
        self.assertNotEqual(result.returncode, 0)
        stale_alias = self.stanza('kmod-tun', '2', exact, state='install ok not-installed')
        installed_alias = self.stanza('kmod-tun', '1', 'kernel')
        result = self.run_guard(base+stale_alias+installed_alias, {'kmod-tun':['tun']}, active=['tun'])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'active module tun', result.stderr)

    def test_ambiguous_installed_records_fail_closed(self):
        base = self.stanza('kernel', '4.1.38-1-exact')
        self.assertNotEqual(self.run_guard(base+base).returncode, 0)
