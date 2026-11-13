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
        cls.stock = json.loads(gzip.decompress((providers.BUILD / 'stock-kernel.json.gz').read_bytes()))
        cls.raw = layout.kernel_inputs(Path(cls.temp.name) / 'raw', normalize=False)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_all_published_kernel_bytes_are_reproduced(self):
        expected = {(r['section'], r['package'], r['version']): r for r in self.catalog['records'] if r['kind'] == 'kernel'}
        actual = {(r['section'], r['package'], r['version']): r for r in self.rows}
        self.assertEqual(set(expected), set(actual))
        for key in expected:
            for field in ('sha256', 'size', 'filename', 'control', 'architecture', 'profile'):
                self.assertEqual(expected[key][field], actual[key][field], (key, field))

    def test_every_verified_module_preserves_source_bytes_after_grouping(self):
        allowed = set()
        for row in self.raw:
            outer = providers.unpack(Path(row['_path']).read_bytes())
            for path, payload in providers.unpack(outer['data.tar.gz']).items():
                if path.endswith('.ko'):
                    allowed.add((row['profile'], Path(path).stem, providers.sha(payload)))
        counts = {}
        seen = set()
        for row in self.rows:
            f = providers.fields(row['control'])
            hashes = json.loads(f.get('X-Rebuilt-Modules', '{}'))
            outer = providers.unpack(Path(row['_path']).read_bytes())
            data = providers.unpack(outer['data.tar.gz'])
            actual = {Path(p).stem: providers.sha(b) for p, b in data.items() if p.endswith('.ko')}
            for module, checksum in hashes.items():
                self.assertEqual(actual[module], checksum)
                self.assertIn((row['profile'], module, checksum), allowed)
                self.assertNotIn((row['profile'], module), seen)
                seen.add((row['profile'], module))
            counts[row['profile']] = counts.get(row['profile'], 0) + len(hashes)
        self.assertEqual(counts, {'4.1.38-vbntk': 214, '4.1.38-vbnto': 223, '4.1.52-vbntk': 50,
                                 '4.1.52-vcnt3': 50, '4.1.52-vcnt2': 50, '4.1.52-vcntj': 50,
                                 '4.1.52-vcnta': 49, '4.1.52-vbntv': 49})

    def test_complete_native_groups_preserve_all_unmodified_files_and_symlinks(self):
        import base64
        for row in self.rows:
            original = self.stock[row['profile']]['packages'].get(row['package'])
            if not original:
                continue
            f = providers.fields(row['control'])
            rebuilt = json.loads(f.get('X-Rebuilt-Modules', '{}'))
            outer = providers.unpack(Path(row['_path']).read_bytes())
            with tarfile.open(fileobj=io.BytesIO(outer['data.tar.gz'])) as archive:
                actual = {m.name.removeprefix('./'): m for m in archive if not m.isdir()}
                self.assertEqual(set(actual), {p.lstrip('/') for p in original['list'].splitlines()}, row['package'])
                for path, member in actual.items():
                    if path.endswith('.ko') and Path(path).stem in rebuilt:
                        self.assertEqual(providers.sha(archive.extractfile(member).read()), rebuilt[Path(path).stem])
                        continue
                    item = original['data'][path]
                    content = base64.b64decode(item['base64'])
                    if item['mode'] == '120000':
                        self.assertTrue(member.issym())
                        self.assertEqual(member.linkname.encode(), content)
                    else:
                        self.assertEqual(archive.extractfile(member).read(), content)
                        self.assertEqual(member.mode, 0o755 if item['mode'] == '100755' else 0o644)
            for path in original.get('requires_rebuilt_files', []):
                self.assertIn(Path(path).stem, rebuilt, 'Missing original must be replaced by a verified rebuilt module')
            self.assertEqual(f['X-Stock-Control-SHA256'], original['control_sha256'])
            if not rebuilt:
                self.assertEqual(f['Version'], providers.fields(original['control'])['Version'])

    def test_dependency_graph_is_closed_versioned_and_acyclic(self):
        for profile, definition in providers.definitions().items():
            rows = {r['package']: r for r in self.rows if r['profile'] == profile and providers.fields(r['control']).get('X-Module-Staging-Only') != 'yes'}
            graph = {}
            for name, row in rows.items():
                f = providers.fields(row['control'])
                self.assertIn('kernel (= ' + definition['kernel_package'] + ')', f['Depends'])
                graph[name] = []
                for dep in f['Depends'].split(','):
                    dep = dep.strip()
                    target = dep.split()[0]
                    if target == 'kernel':
                        continue
                    self.assertIn(target, rows, (profile, name, target))
                    self.assertEqual(dep, target + ' (= ' + rows[target]['version'] + ')')
                    graph[name].append(target)
            visited, active = set(), set()
            def visit(name):
                self.assertNotIn(name, active, (profile, name, 'dependency cycle'))
                if name in visited:
                    return
                active.add(name)
                for target in graph[name]:
                    visit(target)
                active.remove(name)
                visited.add(name)
            for name in graph:
                visit(name)

    def test_standard_names_hooks_and_explicit_legacy_ownership(self):
        import os
        for row in self.rows:
            f = providers.fields(row['control'])
            outer = providers.unpack(Path(row['_path']).read_bytes())
            hooks = providers.unpack(outer['control.tar.gz'])
            self.assertNotIn('Replaces', f)
            if f.get('X-Module-Staging-Only') == 'yes':
                self.assertNotIn('Provides', f)
                continue
            self.assertNotIn('-manual', row['package'])
            self.assertNotIn('-compat', row['package'])
            self.assertNotIn('X-Manual-Install-Only', f)
            self.assertNotIn('Provides', f)
            self.assertEqual(set(hooks), {'control', 'preinst'})
            hook = hooks['preinst']
            with tarfile.open(fileobj=io.BytesIO(outer['data.tar.gz'])) as archive:
                checksums = {p.strip().split(':', 1)[1]: p.strip().split(':', 1)[0] for p in f.get('X-Payload-Checksums', '').split(',') if p.strip()}
                symlinks = {p.strip().split(':', 1)[0]: p.strip().split(':', 1)[1] for p in f.get('X-Payload-Symlinks', '').split(',') if p.strip()}
                self.assertEqual(checksums, {m.name.removeprefix('./'): providers.sha(archive.extractfile(m).read()) for m in archive if m.isfile()})
            with tarfile.open(fileobj=io.BytesIO(outer['data.tar.gz'])) as archive:
                self.assertEqual(symlinks, {m.name.removeprefix('./'): m.linkname for m in archive if m.issym()})
            self.assertEqual(subprocess.run(['sh', '-n'], input=hook, capture_output=True).returncode, 0)
            for forbidden in (b'insmod ', b'modprobe ', b'rmmod ', b'opkg ', b'--force'):
                self.assertNotIn(forbidden, hook)
            if f.get('X-Rebuilt-Modules'):
                self.assertTrue(f['Version'].startswith('1:'))
            if row['package'] not in ('kmod-tun', 'kmod-nf-conntrack', 'kmod-usb-net', 'kmod-usb-net-rndis'):
                continue
            with tempfile.TemporaryDirectory() as temporary:
                status = Path(temporary) / 'status'
                script = hook.replace(b'/usr/lib/opkg/status', str(status).encode())
                kernel = providers.definitions()[row['profile']]['kernel_package']
                base = PackageHookLockTests.stanza('kernel', kernel)
                cases = [(base, True), (base.replace(kernel, 'wrong'), False)]
                for previous in f.get('X-Previous-Module-Packages', '').split(','):
                    if previous.strip():
                        cases.append((base + PackageHookLockTests.stanza(previous.strip(), '1'), False))
                for content, accepted in cases:
                    status.write_text(content)
                    check = subprocess.run(['sh'], input=script, capture_output=True, env={**os.environ, 'IPKG_INSTROOT': ''})
                    self.assertEqual(check.returncode == 0, accepted, (row['profile'], row['package'], check.stderr))

    def test_immutable_source_urls_survive_group_merging(self):
        active = {(r['profile'], r['filename']) for r in self.rows}
        archives = [a for r in self.rows for a in r.get('_package_archives', [])]
        self.assertGreaterEqual(len(archives), 735)
        for row in self.rows:
            for entry in row.get('_package_archives', []):
                self.assertTrue(Path(entry['path']).is_file())
                self.assertNotIn((row['profile'], entry['filename']), active)

    def test_runtime_evidence_is_preserved_per_module_without_promotion(self):
        rows = {r['package']: r for r in self.rows if r['profile'] == '4.1.52-vcnt3'}
        for package, module in [('kmod-usb-net-cdc-ether', 'cdc_ether'), ('kmod-usb-net-rndis', 'rndis_host')]:
            f = providers.fields(rows[package]['control'])
            self.assertTrue(json.loads(f['X-Module-Validation'])[module])
        with self.assertRaises(ValueError):
            providers.runtime_evidence('4.1.52-vcnt3', 'rndis_host', b'different payload')

    def test_corrupt_stock_payload_fails_closed(self):
        from kernel_feed_packages import stock_data
        with self.assertRaises(ValueError):
            stock_data({'lib/test.ko': {'base64': 'YWJj', 'sha256': '0' * 64, 'mode': '100644'}})


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
