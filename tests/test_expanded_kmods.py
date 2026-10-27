import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
import importlib.util


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/package-expanded-kmods.py'


class ExpandedModulePackages(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'modules').mkdir()
        self.payload = b'candidate module payload'
        (self.root / 'modules/nf_conntrack.ko').write_bytes(self.payload)
        self.module = dict(name='nf_conntrack', path='modules/nf_conntrack.ko',
                           sha256=hashlib.sha256(self.payload).hexdigest())

    def package(self, modules):
        (self.root / 'modules.json').write_text(json.dumps(dict(modules=modules)))
        return subprocess.run(['python3', str(SCRIPT), str(self.root)],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_installation_cannot_replace_or_autoload_stock_module(self):
        result = self.package([self.module])
        self.assertEqual(result.returncode, 0, result.stderr)
        with tarfile.open(next((self.root / 'ipks').glob('*.ipk')), 'r:gz') as outer:
            control_blob = outer.extractfile('./control.tar.gz').read()
            data_blob = outer.extractfile('./data.tar.gz').read()
        with tarfile.open(fileobj=io.BytesIO(control_blob), mode='r:gz') as archive:
            self.assertEqual(archive.getnames(), ['./control'])
            control = archive.extractfile('./control').read().decode()
            self.assertIn('X-Module-Staging-Only: yes', control)
            self.assertIn('X-Runtime-Validated: no', control)
            self.assertIn('Depends: kernel (= 4.1.38-1-08839f3f6145d3a5d2d04be7567e3f9d)', control)
        with tarfile.open(fileobj=io.BytesIO(data_blob), mode='r:gz') as archive:
            self.assertEqual(archive.getnames(), [
                './usr/lib/kernel-module-candidates/4.1.38/nf_conntrack.ko'])
            self.assertEqual(archive.extractfile(archive.getmembers()[0]).read(), self.payload)

    def test_vbnts_has_its_own_abi_package_name_and_staging_path(self):
        (self.root / 'modules.json').write_text(json.dumps(dict(modules=[self.module])))
        result = subprocess.run(['python3', str(SCRIPT), str(self.root), '--profile', 'vbnts'],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, 0, result.stderr)
        ipk = next((self.root / 'ipks').glob('*.ipk'))
        self.assertIn('-vbnts-4.1.38-candidate_', ipk.name)
        with tarfile.open(ipk, 'r:gz') as outer:
            control_blob = outer.extractfile('./control.tar.gz').read()
            data_blob = outer.extractfile('./data.tar.gz').read()
        with tarfile.open(fileobj=io.BytesIO(control_blob), mode='r:gz') as archive:
            control = archive.extractfile('./control').read().decode()
            self.assertIn('kernel (= 4.1.38-1-8dd693635a152c8c7b822a64e6c5c470)', control)
            self.assertNotIn('08839f3f', control)
        with tarfile.open(fileobj=io.BytesIO(data_blob), mode='r:gz') as archive:
            self.assertEqual(archive.getnames(),
                             ['./usr/lib/kernel-module-candidates/4.1.38-vbnts/nf_conntrack.ko'])

    def test_vbnts_rejects_wrong_kernel_override(self):
        result = subprocess.run(['python3', str(SCRIPT), str(self.root), '--profile', 'vbnts',
                                 '--kernel-version', '4.1.38-1-08839f3f6145d3a5d2d04be7567e3f9d'],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'does not match', result.stderr)

    def test_changed_payload_is_rejected(self):
        (self.root / self.module['path']).write_bytes(b'changed')
        self.assertNotEqual(self.package([self.module]).returncode, 0)

    def test_conflicting_module_names_are_rejected(self):
        other = dict(self.module, sha256='0' * 64)
        self.assertNotEqual(self.package([self.module, other]).returncode, 0)

    def test_quarantined_payload_is_not_distributed(self):
        spec = importlib.util.spec_from_file_location('packager', SCRIPT)
        packager = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(packager)
        packager.QUARANTINED[self.module['sha256']] = 'test quarantine'
        (self.root / 'modules.json').write_text(json.dumps(dict(modules=[self.module])))
        import sys
        from unittest.mock import patch
        with patch.object(sys, 'argv', [str(SCRIPT), str(self.root)]):
            packager.main()
        self.assertEqual(list((self.root / 'ipks').glob('*.ipk')), [])
        self.assertIn('test quarantine', (self.root / 'ipks/QUARANTINED.txt').read_text())

    def test_netfilter_target_and_match_keep_distinct_package_names(self):
        modules = []
        for name, payload_file, payload in [('xt_DSCP', 'target.ko', b'target'),
                                            ('xt_dscp', 'match.ko', b'match')]:
            (self.root / 'modules' / payload_file).write_bytes(payload)
            modules.append(dict(name=name, path='modules/' + payload_file,
                                sha256=hashlib.sha256(payload).hexdigest()))
        result = self.package(modules)
        self.assertEqual(result.returncode, 0, result.stderr)
        names = {path.name for path in (self.root / 'ipks').glob('*.ipk')}
        self.assertEqual(names, {
            'kmod-xt-dscp-target-4.1.38-candidate_4.1.38-1_arm_cortex-a9.ipk',
            'kmod-xt-dscp-match-4.1.38-candidate_4.1.38-1_arm_cortex-a9.ipk'})
        checksums = (self.root / 'ipks/SHA256SUMS').read_text().splitlines()
        self.assertEqual(len(checksums), len(names))

    def test_rebuilding_xt_nat_cannot_bypass_quarantine(self):
        module = dict(self.module, name='xt_nat')
        result = self.package([module])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(list((self.root / 'ipks').glob('*.ipk')), [])

    def test_archive_preserves_case_sensitive_payloads(self):
        modules = []
        source = self.root / 'original.tar.gz'
        with tarfile.open(source, 'w:gz') as archive:
            for name in ('xt_DSCP', 'xt_dscp'):
                payload = name.encode()
                path = 'modules/' + name + '.ko'
                member = tarfile.TarInfo(path)
                member.size = len(payload)
                archive.addfile(member, io.BytesIO(payload))
                modules.append(dict(name=name, path=path,
                                    sha256=hashlib.sha256(payload).hexdigest()))
        (self.root / 'modules.json').write_text(json.dumps(dict(modules=modules)))
        subprocess.run(['python3', str(SCRIPT), str(self.root), '--module-archive', str(source)],
                       check=True, capture_output=True)
        payloads = set()
        for ipk in (self.root / 'ipks').glob('*.ipk'):
            with tarfile.open(ipk, 'r:gz') as outer:
                with tarfile.open(fileobj=io.BytesIO(outer.extractfile('./data.tar.gz').read()), mode='r:gz') as data:
                    payloads.add(data.extractfile(data.getmembers()[0]).read())
        self.assertEqual(payloads, {b'xt_DSCP', b'xt_dscp'})


if __name__ == '__main__':
    unittest.main()
