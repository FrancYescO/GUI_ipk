import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('candidates', ROOT / 'scripts/assemble-kernel-candidates.py')
candidates = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidates)
from kernel_compatibility_page import write_compatibility


def archive(files):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:gz') as tar:
        for name, data in files:
            member = tarfile.TarInfo(name)
            member.size = len(data)
            tar.addfile(member, io.BytesIO(data))
    return output.getvalue()


class KernelCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = json.loads(candidates.SOURCES.read_text())['vbnts']
        self.payload = b'test module bytes'
        self.sha = hashlib.sha256(self.payload).hexdigest()
        self.fields = {
            'Package': 'kmod-tun-vbnts-4.1.38-candidate',
            'Architecture': 'arm_cortex-a9', 'Version': '4.1.38-1',
            'Depends': 'kernel (= ' + self.source['kernel_package'] + ')',
            'X-Manual-Install-Only': 'yes', 'X-Runtime-Validated': 'no',
            'X-Module-Staging-Only': 'yes',
            'X-Kernel-Vermagic': '4.1.38 SMP preempt mod_unload ARMv7',
            'X-Module-Path': '/usr/lib/kernel-module-candidates/4.1.38-vbnts/tun.ko',
        }

    def package(self, path=None, postinst=False):
        control = '\n'.join(k + ': ' + v for k, v in self.fields.items()).encode() + b'\n'
        items = [('./control', control)]
        if postinst:
            items.append(('./postinst', b'#!/bin/sh\nmodprobe tun\n'))
        raw = archive([('./debian-binary', b'2.0\n'),
                       ('./control.tar.gz', archive(items)),
                       ('./data.tar.gz', archive([(path or '.' + self.fields['X-Module-Path'], self.payload)]))])
        ipk = self.root / (self.fields['Package'] + '_4.1.38-1_arm_cortex-a9.ipk')
        ipk.write_bytes(raw)
        return ipk, hashlib.sha256(raw).hexdigest()

    def verify(self, ipk, sha):
        return candidates.verify_ipk(ipk, sha, self.source, 'vbnts', {'tun': self.sha})

    def test_exact_profile_and_module_are_accepted(self):
        fields, module, sha = self.verify(*self.package())
        self.assertEqual((module, sha), ('tun', self.sha))
        self.assertEqual(fields['X-Module-Staging-Only'], 'yes')

    def test_same_linux_release_with_wrong_kernel_hash_is_rejected(self):
        self.fields['Depends'] = 'kernel (= 4.1.38-1-08839f3f6145d3a5d2d04be7567e3f9d)'
        with self.assertRaisesRegex(ValueError, 'ABI guard mismatch'):
            self.verify(*self.package())

    def test_stock_path_and_path_traversal_are_rejected(self):
        for path in ['./lib/modules/4.1.38/tun.ko',
                     './usr/lib/kernel-module-candidates/4.1.38-vbnts/../../tun.ko']:
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'outside the boot module path'):
                self.verify(*self.package(path=path))

    def test_autoload_installation_script_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'installation scripts'):
            self.verify(*self.package(postinst=True))

    def test_download_and_module_tampering_are_rejected(self):
        ipk, sha = self.package()
        with self.assertRaisesRegex(ValueError, 'pinned release'):
            self.verify(ipk, '0' * 64)
        self.payload = b'different module bytes'
        with self.assertRaisesRegex(ValueError, 'build manifest'):
            self.verify(*self.package())

    def test_quarantined_module_is_rejected_even_with_valid_ipk_hash(self):
        self.fields['Package'] = 'kmod-xt-nat-vbnts-4.1.38-candidate'
        self.fields['X-Module-Path'] = '/usr/lib/kernel-module-candidates/4.1.38-vbnts/xt_nat.ko'
        with self.assertRaisesRegex(ValueError, 'Quarantined module'):
            self.verify(*self.package())

    def test_all_pinned_packages_are_separate_from_tested_packages(self):
        sources = json.loads(candidates.SOURCES.read_text())
        self.assertEqual(sum(s['package_count'] for s in sources.values()), 432)
        for profile, source in sources.items():
            names = candidates.checksums(ROOT / 'build/kernel-candidates' / (profile + '.sha256'))
            self.assertEqual(len(names), source['package_count'])
            self.assertTrue(source['feed'].endswith('-candidates'))
            self.assertFalse(any('xt-nat-' in name for name in names))

    def test_inventory_does_not_claim_runtime_validation_for_matching_hash(self):
        data = json.loads((ROOT / 'build/kernel-candidates/firmware-compatibility.json').read_text())
        self.assertEqual(len(data['firmwares']), 279)
        tim = next(r for r in data['firmwares'] if r['firmware'] == 'AGTHP_2.2.0_CLOSED')
        self.assertEqual(tim['status'], 'stock-modules-identical-runtime-check-required')
        planned = json.loads((ROOT / 'build/kernel-candidates/planned-profiles.json').read_text())
        self.assertIsNone(planned['4.1.38-fastweb-fw261']['feed'])
        self.assertEqual(planned['4.1.38-fastweb-fw261']['status'], 'runtime-config-required')

    def test_public_inventory_exports_all_firmware_rows_and_setup(self):
        write_compatibility(self.root, '', '')
        page = (self.root / 'compatibility/index.html').read_text()
        self.assertEqual(page.count('<tr>'), 280)
        self.assertIn('FW261/FW264 are awaiting runtime kernel configurations', page)
        self.assertTrue((self.root / 'compatibility/firmware-compatibility.csv').is_file())
        self.assertTrue((self.root / 'compatibility/kernel-compatibility.md').is_file())

    def test_publication_is_centralized_and_preserves_candidate_reconstruction(self):
        publisher = (ROOT / '.github/workflows/publish-opkg-feed.yml').read_text()
        builder = (ROOT / '.github/workflows/build-packages.yml').read_text()
        layout = (ROOT / 'scripts/publication_layout.py').read_text()
        self.assertIn('scripts/prepare-publication.py', publisher)
        self.assertIn('scripts/fetch-publication-inputs.py', publisher)
        self.assertNotIn('actions/deploy-pages', builder)
        self.assertIn('userspace-opkg-feed-${{ github.sha }}', builder)
        self.assertIn("load_script('fetch-kernel-candidates')", layout)
        self.assertIn("load_script('assemble-kernel-candidates')", layout)
        self.assertIn("'X-Module-Staging-Only'", layout)


if __name__ == '__main__':
    unittest.main()
