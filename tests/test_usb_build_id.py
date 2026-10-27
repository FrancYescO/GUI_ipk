import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_id', ROOT / 'scripts/normalize-usb-build-id.py')
build_id = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_id)
REFERENCE = ROOT / 'artifacts/damson-4.1.52-rndis-compat/cdc_ether.ko'


class UsbBuildIdTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'cdc_ether.ko'
        self.original = REFERENCE.read_bytes()
        self.digest = hashlib.sha256(self.original).hexdigest()

    def test_only_build_id_difference_is_normalized_to_exact_tested_bytes(self):
        modified = bytearray(self.original)
        offset, size = build_id.build_id_range(modified)
        modified[offset + size - 1] ^= 1
        self.path.write_bytes(modified)
        self.assertTrue(build_id.normalize(self.path, REFERENCE, self.digest))
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_any_executable_or_other_metadata_change_is_rejected(self):
        modified = bytearray(self.original)
        modified[100] ^= 1
        self.path.write_bytes(modified)
        with self.assertRaisesRegex(ValueError, 'outside GNU build-id'):
            build_id.normalize(self.path, REFERENCE, self.digest)
        self.assertEqual(self.path.read_bytes(), modified)

    def test_changed_reference_is_rejected(self):
        self.path.write_bytes(self.original)
        with self.assertRaisesRegex(ValueError, 'Reference differs'):
            build_id.normalize(self.path, REFERENCE, '0' * 64)

    def test_identical_payload_requires_no_normalization(self):
        self.path.write_bytes(self.original)
        self.assertFalse(build_id.normalize(self.path, REFERENCE, self.digest))


if __name__ == '__main__':
    unittest.main()
