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
                original_data = providers.unpack(original['data.tar.gz'])
                self.assertEqual({Path(p).name: b for p, b in data.items()},
                                 {Path(p).name: b for p, b in original_data.items()}, row['package'])
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
        self.assertEqual(module_count, 735)

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
            self.assertIn('kmod-tun', advertised)
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

    def test_promoted_profiles_use_standard_paths_and_module_validation(self):
        profiles = {p for p, entry in providers.firmware_definitions().items() if entry.get('installable')}
        tested = []
        for row in self.rows:
            f = providers.fields(row['control'])
            if row['profile'] not in profiles:
                continue
            self.assertEqual(row['section'], 'kernel/' + row['profile'])
            self.assertNotIn('X-Module-Staging-Only', f)
            self.assertNotIn('-candidate', row['package'])
            outer = providers.unpack(Path(row['_path']).read_bytes())
            for path in providers.unpack(outer['data.tar.gz']):
                self.assertTrue(path.startswith('lib/modules/4.1.52/'), path)
                self.assertEqual('/' + path, f['X-Module-Path'])
                self.assertIn(f['X-Validation-Level'], ('runtime-tested', 'offline-checked'))
                if f.get('X-Runtime-Validated') == 'yes':
                    tested.append((row['profile'], Path(path).stem))
        self.assertEqual(sorted(tested), [('4.1.52-vcnt3', 'cdc_ether'), ('4.1.52-vcnt3', 'rndis_host')])

    def test_runtime_evidence_rejects_different_payload(self):
        with self.assertRaises(ValueError):
            providers.runtime_evidence('4.1.52-vcnt3', 'rndis_host', b'different payload')

    def test_legacy_profiles_are_unique_and_installable(self):
        for profile, count in [('4.1.38-vbnto', 223), ('4.1.38-vbntk', 214)]:
            modules = {}
            for row in self.rows:
                if row['profile'] != profile:
                    continue
                fields = providers.fields(row['control'])
                self.assertEqual(row['section'], 'kernel/' + profile)
                self.assertNotIn('X-Module-Staging-Only', fields)
                self.assertNotIn('-candidate', row['package'])
                path = fields.get('X-Module-Path')
                if path:
                    self.assertTrue(path.startswith('/lib/modules/4.1.38/'))
                    self.assertNotIn(Path(path).stem, modules)
                    modules[Path(path).stem] = fields['X-Module-SHA256']
            self.assertEqual(len(modules), count)
            internal = 'vbnts' if profile.endswith('vbntk') else 'vbnto'
            report = json.loads((ROOT / ('build/' + internal + '-4.1.38/runtime-validation/results.json')).read_text())
            for module in report['modules']:
                self.assertEqual(modules[module['name']], module['sha256'])

    def test_module_dependencies_preserve_stock_owners(self):
        firmware = json.loads((providers.BUILD / 'firmware-packages.json').read_text())
        configs = {p: providers.config(p)[0] for p in providers.definitions()}
        mapping = json.loads((providers.BUILD / 'legacy-map.json').read_text())
        checked = 0
        for row in self.rows:
            stock = firmware.get(row['profile'], {}).get('packages', {})
            outer = providers.unpack(Path(row['_path']).read_bytes())
            for path, payload in providers.unpack(outer['data.tar.gz']).items():
                if not path.startswith('lib/modules/'):
                    continue
                cfg = configs[row['profile']]
                for module in providers.elf_module(payload)['modinfo'].get('depends', [''])[0].split(','):
                    if Path(path).stem == 'rndis_host' and module == 'cdc_ether' and row['profile'] != '4.1.52-vbntk':
                        dependency = next(r['package'] for r in self.rows if r['profile'] == row['profile'] and providers.fields(r['control']).get('X-Module-Path', '').endswith('/cdc_ether.ko'))
                        self.assertIn(dependency + ' (= ', row['control'])
                        continue
                    if cfg.get(mapping['builtin_configs'].get(module, '')) == 'y':
                        continue
                    owners = sorted(p for p, value in stock.items() if module in value['modules'])
                    if not owners:
                        continue
                    name = owners[0]
                    self.assertIn(name + ' (= ' + stock[name]['version'] + ')',
                                  providers.fields(row['control'])['Depends'], row['package'])
                    preinst = providers.unpack(outer['control.tar.gz'])['preinst']
                    self.assertIn(('package_status ' + name).encode(), preinst)
                    checked += 1
        self.assertGreater(checked, 0)

    def test_dumaos_qos_dependencies_do_not_replace_stock_firewall(self):
        profile = '4.1.52-vbntk'
        stock = json.loads((providers.BUILD / 'firmware-packages.json').read_text())[profile]['packages']
        rows = {r['package']: r for r in self.rows if r['profile'] == profile}
        pending = ['kmod-act-connmark']
        visited = set()
        while pending:
            name = pending.pop()
            if name in visited or name in stock or name == 'kernel':
                continue
            visited.add(name)
            row = rows[name]
            outer = providers.unpack(Path(row['_path']).read_bytes())
            payload = providers.unpack(outer['data.tar.gz'])
            self.assertTrue(all(Path(p).stem == 'act_connmark' for p in payload), name)
            for dependency in providers.fields(row['control'])['Depends'].split(','):
                dep = dependency.strip().split()[0]
                if dep in stock:
                    self.assertEqual(dependency.strip(), dep + ' (= ' + stock[dep]['version'] + ')')
                pending.append(dep)
        self.assertEqual(visited, {'kmod-act-connmark', 'kmod-act-connmark-4.1.52-manual'})

    def test_ip_tables_capability_uses_stock_owner_without_payload(self):
        rows = [r for r in self.rows if r['profile'] == '4.1.52-vbntk' and r['package'] == 'kmod-ip-tables']
        self.assertEqual(len(rows), 1)
        row = rows[0]
        outer = providers.unpack(Path(row['_path']).read_bytes())
        self.assertEqual(providers.unpack(outer['data.tar.gz']), {})
        self.assertIn('kmod-nf-ipt (= ', providers.fields(row['control'])['Depends'])
        self.assertNotIn('kmod-ip-tables-4.1.52-manual', row['control'])


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
                (self.stanza('kmod-base', '1', 'kernel (=4.1.38-1-exact)'), True),
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
