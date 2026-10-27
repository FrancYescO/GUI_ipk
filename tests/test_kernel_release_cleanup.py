import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('candidate_stage', ROOT / 'scripts/fetch-kernel-candidates.py')
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


def files(blob):
    with tarfile.open(fileobj=io.BytesIO(blob), mode='r:gz') as tar:
        return {m.name: tar.extractfile(m).read() for m in tar if m.isfile()}


class KernelReleaseCleanupTests(unittest.TestCase):
    def test_all_432_original_candidates_can_be_staged_without_network_or_releases(self):
        sources = json.loads((ROOT / 'build/kernel-candidates/sources.json').read_text())
        with tempfile.TemporaryDirectory() as directory, patch('subprocess.run', side_effect=AssertionError('Network subprocess invoked')):
            root = Path(directory)
            stage.download(root, 'unused/repository')
            count = 0
            for profile, record in sources.items():
                self.assertNotIn('tag', record)
                self.assertEqual(hashlib.sha256((ROOT / record['bundle']).read_bytes()).hexdigest(), record['bundle_sha256'])
                expected = {}
                for line in (ROOT / 'build/kernel-candidates' / (profile + '.sha256')).read_text().splitlines():
                    sha, name = line.split()
                    expected[name] = sha
                ipks = list((root / profile / 'ipks').glob('*.ipk'))
                self.assertEqual({p.name for p in ipks}, set(expected))
                for ipk in ipks:
                    self.assertEqual(hashlib.sha256(ipk.read_bytes()).hexdigest(), expected[ipk.name])
                    self.assertNotIn('kmod-xt-nat-', ipk.name)
                count += len(ipks)
            self.assertEqual(count, 432)

    def test_vbntk_metadata_keeps_every_recorded_module_payload_unchanged(self):
        profile = json.loads((ROOT / 'build/kernel-profiles/vbntk-4.1.52.json').read_text())
        report = json.loads((ROOT / 'build/vbntj/validation/results.json').read_text())
        records = {r['asset']: r for r in report['modules'] if r.get('asset')}
        checked = 0
        for suffix in ('manual', 'network', 'spu', 'rndis-compat'):
            for ipk in (ROOT / ('artifacts/damson-4.1.52-' + suffix)).glob('*.ipk'):
                outer = files(ipk.read_bytes())
                control = files(outer['./control.tar.gz'])
                self.assertEqual(set(control), {'./control'})
                text = control['./control'].decode()
                self.assertNotIn('X-Damson-', text)
                self.assertNotIn('Description: Manual-only Damson', text)
                self.assertIn('Depends: kernel (= ' + profile['kernel_package'] + ')', text)
                self.assertIn('X-Kernel-Profile: 4.1.52-vbntk', text)
                self.assertIn('X-Firmware: ' + report['firmware'], text)
                self.assertIn('Architecture: arm_cortex-a9', text)
                payloads = files(outer['./data.tar.gz'])
                self.assertEqual(len(payloads), 1)
                self.assertEqual(hashlib.sha256(next(iter(payloads.values()))).hexdigest(), records[ipk.name]['sha256'])
                checked += 1
        self.assertEqual(checked, 49)

    def test_shared_kernel_package_is_a_candidate_not_a_claim_of_runtime_coverage(self):
        report = json.loads((ROOT / 'build/kernel-candidates/firmware-compatibility.json').read_text())
        matches = [r for r in report['firmwares'] if r['profile'] == '4.1.52-vbntk']
        self.assertEqual(len(matches), 25)
        self.assertTrue(all(r['status'] == 'same-kernel-package-runtime-check-required' for r in matches))


if __name__ == '__main__':
    unittest.main()
