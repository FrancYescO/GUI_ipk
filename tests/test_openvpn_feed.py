import gzip
import hashlib
import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('openvpn_feed', ROOT / 'scripts/overlay-openvpn-feed.py')
feed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(feed)


class OpenVPNFeedTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name) / 'feed'
        self.source = ROOT / 'artifacts/openvpn-2.6.23'
        base = self.output / 'base'
        base.mkdir(parents=True)
        (self.output / 'packages').mkdir()
        stanzas = (ROOT / 'base/Packages').read_text().split('\n\n')
        keep = {'openvpn-openssl', 'openvpn-mbedtls', 'openvpn-nossl', 'openvpn-easy-rsa'}
        selected = []
        for stanza in stanzas:
            fields = dict(line.split(': ', 1) for line in stanza.splitlines() if ': ' in line and not line[0].isspace())
            if fields.get('Package') in keep:
                shutil.copyfile(ROOT / 'base' / fields['Filename'], base / fields['Filename'])
                selected.append(stanza)
        self.assertEqual(len(selected), 4)
        (base / 'Packages').write_text('\n\n'.join(selected) + '\n\n')
        (self.output / 'packages/Packages').write_text('')

    def test_update_preserves_unrelated_package_and_is_repeatable(self):
        unrelated = next((self.output / 'base').glob('openvpn-easy-rsa_*.ipk'))
        before = unrelated.read_bytes()
        feed.overlay(self.source, self.output)
        self.assertEqual(before, unrelated.read_bytes())
        self.assertFalse(list((self.output / 'base').glob('openvpn-nossl_*.ipk')))
        self.assertFalse(list((self.output / 'base').glob('openvpn-*_2.4.5-*.ipk')))
        for name, (section, version) in feed.PACKAGES.items():
            target = self.output / section / f'{name}_{version}_arm_cortex-a9_neon.ipk'
            self.assertEqual(target.read_bytes(), (self.source / target.name).read_bytes())
        indexes = {}
        for section in ('base', 'packages'):
            index = self.output / section / 'Packages'
            self.assertEqual(index.read_bytes(), gzip.decompress(index.with_suffix('.gz').read_bytes()))
            indexes[section] = hashlib.sha256(index.read_bytes()).digest()
        feed.overlay(self.source, self.output)
        for section in indexes:
            self.assertEqual(indexes[section], hashlib.sha256((self.output / section / 'Packages').read_bytes()).digest())

    def test_corrupt_snapshot_rejected_before_output_changes(self):
        source = Path(self.temporary.name) / 'corrupt'
        source.mkdir()
        shutil.copyfile(self.source / 'SHA256SUMS', source / 'SHA256SUMS')
        for ipk in self.source.glob('*.ipk'):
            shutil.copyfile(ipk, source / ipk.name)
        next(source.glob('*.ipk')).write_bytes(b'invalid')
        before = (self.output / 'base/Packages').read_bytes()
        with self.assertRaises(ValueError):
            feed.overlay(source, self.output)
        self.assertEqual(before, (self.output / 'base/Packages').read_bytes())

    def test_unexpected_newer_version_is_not_downgraded(self):
        index = self.output / 'base/Packages'
        index.write_text(index.read_text().replace('Version: 2.4.5-4.2', 'Version: 2.7.8-1'))
        before = index.read_bytes()
        with self.assertRaises(ValueError):
            feed.overlay(self.source, self.output)
        self.assertEqual(before, index.read_bytes())


if __name__ == '__main__':
    unittest.main()
