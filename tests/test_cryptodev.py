"""Exercise the patched upstream page-pinning code, including partial failures."""
import hashlib
import json
import gzip
import shutil
import subprocess
import tarfile
import tempfile
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / 'artifacts/cryptodev/source/cryptodev-linux-08644db.tar.gz'
sys.path.insert(0, str(ROOT / 'scripts'))


class CryptodevTests(unittest.TestCase):
    def test_all_profiles_have_exact_abi_staged_packages(self):
        from cryptodev_packages import audit, definitions, publication_records, package
        from firmware_kernel_candidates import files
        from kernel_firmware import config_options
        rows = publication_records()
        self.assertEqual(len(rows), 5)
        for row in rows:
            profile = row['profile']
            definition = definitions()[profile]
            ipk = files(Path(row['_path']).read_bytes())
            self.assertEqual(set(ipk), {'./debian-binary', './control.tar.gz', './data.tar.gz'})
            controls = files(ipk['./control.tar.gz'])
            self.assertEqual(set(controls), {'./control'})  # No install/load hooks.
            self.assertEqual(controls['./control'].decode(), row['control'] + '\n')
            payloads = files(ipk['./data.tar.gz'])
            self.assertEqual(list(payloads), ['./usr/lib/kernel-module-candidates/' + profile + '/cryptodev.ko'])
            payload, = payloads.values()
            self.assertFalse(audit(profile, payload)['unresolved_symbols'])
            config = config_options(gzip.decompress((ROOT / 'build/cryptodev' / profile / 'build.config.gz').read_bytes()))
            self.assertEqual(config['CONFIG_MODVERSIONS'], 'n')
            with tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                (directory / 'cryptodev.ko').write_bytes(payload)
                result = package(profile, directory, directory / 'ipks')
                self.assertEqual(result['ipk_sha256'], row['sha256'])
            self.assertEqual(definition['runtime_validated'], profile.startswith('4.1.38-'))

    def test_pinned_source_and_page_ownership(self):
        self.assertEqual(hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
                         'e795acb85118f1f39f0155df8fd28a3d79de7d1240b91bdf8cc9e2a1747d2642')
        if not shutil.which('cc') or not shutil.which('patch'):
            self.skipTest('C compiler and patch required')
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            with tarfile.open(ARCHIVE) as archive:
                # The SHA-verified archive is pinned above (Python 3.9 compatible).
                archive.extractall(directory)
            source, = directory.glob('cryptodev-linux-*')
            subprocess.run(['patch', '--batch', '-p1', '-i', str(ROOT / 'patches/cryptodev/001-page-ownership-and-bounds.patch')],
                           cwd=source, check=True, capture_output=True)
            binary = directory / 'pin-regression'
            subprocess.run(['cc', '-std=gnu99', '-Wall', '-Wextra', '-Wno-sign-compare',
                            '-I' + str(source), '-I' + str(ROOT / 'build/cryptodev/tests'),
                            str(ROOT / 'build/cryptodev/tests/pin-regression.c'), '-o', str(binary)],
                           check=True, capture_output=True)
            result = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
            self.assertIn('10 regression scenarios passed', result.stdout)


if __name__ == '__main__':
    unittest.main()
