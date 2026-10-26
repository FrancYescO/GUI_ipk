import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest


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

    def test_changed_payload_is_rejected(self):
        (self.root / self.module['path']).write_bytes(b'changed')
        self.assertNotEqual(self.package([self.module]).returncode, 0)

    def test_conflicting_module_names_are_rejected(self):
        other = dict(self.module, sha256='0' * 64)
        self.assertNotEqual(self.package([self.module, other]).returncode, 0)


if __name__ == '__main__':
    unittest.main()
