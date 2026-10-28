import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from kernel_validation_page import write_report

spec = importlib.util.spec_from_file_location('validated_feed', ROOT / 'scripts/assemble-kernel-feed.py')
feed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(feed)
SOURCE = ROOT / 'build/vbntj/validation'


def archive(items):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as tar:
        for name, blob in items:
            member = tarfile.TarInfo(name)
            member.size = len(blob)
            tar.addfile(member, io.BytesIO(blob))
    return stream.getvalue()


class KernelValidationTests(unittest.TestCase):
    def test_changed_payload_cannot_reenter_the_feed(self):
        original = next((ROOT / 'artifacts/damson-4.1.52-manual').glob('kmod-tun-*.ipk'))
        with tarfile.open(original, 'r:gz') as tar:
            control = tar.extractfile('./control.tar.gz').read()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ipk = root / original.name
            ipk.write_bytes(archive([
                ('./debian-binary', b'2.0\n'), ('./control.tar.gz', control),
                ('./data.tar.gz', archive([('./lib/modules/4.1.52/tun.ko', b'changed payload')]))]))
            with self.assertRaisesRegex(ValueError, 'Payload differs'):
                feed.write_feed('4.1.52', [ipk], root / 'feed')
            self.assertFalse((root / 'feed/kernel/4.1.52/Packages').exists())

    def test_quarantined_module_cannot_be_added(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(feed, 'control_fields', return_value={'Package': 'kmod-xt-nat-4.1.52-manual'}):
                with self.assertRaisesRegex(ValueError, 'Quarantined'):
                    feed.write_feed('4.1.52', [root / 'xt_nat.ipk'], root / 'feed')

    def test_page_distinguishes_busy_and_smoke_tests_from_functional_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            write_report(SOURCE, destination, '', '')
            html = (destination / 'index.html').read_text()
            self.assertIn('14 functional passes; 2 load/unload and namespace smoke passes;', html)
            self.assertIn('32 busy stock modules', html)
            self.assertIn('WITHHELD: stock unload caused reboot; candidate untested', html)
            self.assertEqual(html.count('<tr>'), 51)
            self.assertNotIn('kmod-xt-nat-4.1.52-manual_', html)

    def test_report_covers_exactly_the_published_packages(self):
        report = json.loads((SOURCE / 'results.json').read_text())
        expected = {row['asset'] for row in report['modules'] if row['asset']}
        actual = {path.name for suffix in ['manual', 'network', 'spu', 'rndis-compat']
                  for path in (ROOT / ('artifacts/damson-4.1.52-' + suffix)).glob('*.ipk')}
        self.assertEqual(expected, actual)
        self.assertEqual(len(actual), 49)

    def test_removed_packages_are_not_left_as_direct_downloads(self):
        original = next((ROOT / 'artifacts/damson-4.1.52-manual').glob('kmod-tun-*.ipk'))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / 'kernel/4.1.52'
            destination.mkdir(parents=True)
            stale = destination / 'kmod-xt-nat-4.1.52-manual_4.1.52-1_brcm963xx.ipk'
            stale.write_bytes(b'withdrawn package')
            feed.write_feed('4.1.52', [original], root)
            self.assertFalse(stale.exists())


if __name__ == '__main__':
    unittest.main()
