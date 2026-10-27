import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import network_kmods_4138 as network


class NetworkRuntimePackages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.inputs = Path(cls.temp.name)
        network.load('fetch-kernel-candidates').download(cls.inputs, 'unused/repository')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_both_profiles_reproduce_all_44_additions_with_unchanged_payloads(self):
        for profile in ('vbnto', 'vbnts'):
            candidates = self.inputs / profile / 'ipks'
            directory = ROOT / 'artifacts' / (profile + '-4.1.38-network')
            packages = network.expected(profile, candidates)
            self.assertEqual(len(packages), 44)
            network.materialize(profile, candidates, directory, verify=True)
            report = json.loads((ROOT / 'build' / (profile + '-4.1.38/runtime-validation/results.json')).read_text())
            records = {r['asset']: r for r in report['modules']}
            self.assertEqual(len(records), 49)
            self.assertNotIn('xt_nat', {r['name'] for r in records.values()})
            for name, blob in packages.items():
                self.assertEqual(blob, (directory / name).read_bytes())
                self.assertEqual(name, name.lower())
                with tarfile.open(fileobj=io.BytesIO(blob)) as outer:
                    with tarfile.open(fileobj=outer.extractfile('./control.tar.gz')) as control:
                        self.assertEqual(control.getnames(), ['./control'])
                        text = control.extractfile('./control').read().decode()
                        self.assertIn('Depends: kernel (= ' + report['kernel_package'] + ')\n', text)
                        self.assertIn('X-Runtime-Test-Status: ' + records[name]['status'] + '\n', text)
                    with tarfile.open(fileobj=outer.extractfile('./data.tar.gz')) as data:
                        self.assertEqual(data.getnames(), ['./lib/modules/4.1.38/' + records[name]['name'] + '.ko'])
                        payload = data.extractfile(data.getnames()[0]).read()
                        self.assertEqual(hashlib.sha256(payload).hexdigest(), records[name]['sha256'])

    def test_changed_candidate_is_rejected_before_packaging(self):
        report = json.loads((ROOT / 'build/vbnto-4.1.38/runtime-validation/results.json').read_text())
        first = next(r for r in report['modules'] if r['name'] not in network.CORE)
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / first['source_asset']).write_bytes(b'corrupt candidate')
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                network.expected('vbnto', directory)


if __name__ == '__main__':
    unittest.main()
