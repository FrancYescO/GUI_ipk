import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / 'scripts/verify-vbnto-4.1.38-ipks.py'
REGISTRY = json.loads((ROOT / 'build/usb-rndis/validation.json').read_text())


def contents(blob):
    with tarfile.open(fileobj=io.BytesIO(blob), mode='r:gz') as tar:
        return {m.name: tar.extractfile(m).read() for m in tar if m.isfile()}


def archive(files):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as tar:
        for name, data in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            tar.addfile(member, io.BytesIO(data))
    return stream.getvalue()


class UsbRndis4138Tests(unittest.TestCase):
    def copy_profile(self, directory, profile):
        for ipk in (ROOT / f'artifacts/{profile}-4.1.38-manual').glob('*.ipk'):
            shutil.copyfile(ipk, directory / ipk.name)

    def verify(self, directory, profile):
        return subprocess.run([sys.executable, str(VERIFY), str(directory), '--profile', profile],
                              capture_output=True)

    def test_both_actual_pairs_match_the_runtime_records(self):
        for profile, record in REGISTRY['profiles'].items():
            root = ROOT / f'artifacts/{profile}-4.1.38-manual'
            result = self.verify(root, profile)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(record['status'], 'load-unload-driver-registration')
            self.assertEqual(record['traffic'], 'not-tested-no-device-attached')
            for name, digest in record['modules'].items():
                package = next(root.glob('kmod-' + name.replace('_', '-') + '-*.ipk'))
                outer = contents(package.read_bytes())
                control = contents(outer['./control.tar.gz'])
                self.assertEqual(set(control), {'./control'})
                self.assertIn(('Depends: kernel (= ' + record['kernel_package'] + ')').encode(), control['./control'])
                payloads = contents(outer['./data.tar.gz'])
                self.assertEqual(set(payloads), {'./lib/modules/4.1.38/' + name + '.ko'})
                self.assertEqual(hashlib.sha256(next(iter(payloads.values()))).hexdigest(), digest)

    def test_identical_payloads_do_not_make_profile_dependencies_interchangeable(self):
        self.assertEqual(REGISTRY['profiles']['vbnto']['modules'], REGISTRY['profiles']['vbnts']['modules'])
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.copy_profile(root, 'vbnts')
            ipk = next(root.glob('kmod-cdc-ether-*.ipk'))
            outer = contents(ipk.read_bytes())
            control = contents(outer['./control.tar.gz'])
            control['./control'] = control['./control'].replace(
                REGISTRY['profiles']['vbnts']['kernel_package'].encode(),
                REGISTRY['profiles']['vbnto']['kernel_package'].encode())
            outer['./control.tar.gz'] = archive(control)
            ipk.write_bytes(archive(outer))
            self.assertNotEqual(self.verify(root, 'vbnts').returncode, 0)

    def test_missing_driver_tampered_payload_and_autoload_are_rejected(self):
        for mutation in ('missing', 'payload', 'postinst'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                self.copy_profile(root, 'vbnto')
                ipk = next(root.glob('kmod-rndis-host-*.ipk'))
                if mutation == 'missing':
                    ipk.unlink()
                else:
                    outer = contents(ipk.read_bytes())
                    if mutation == 'payload':
                        outer['./data.tar.gz'] = archive({'./lib/modules/4.1.38/rndis_host.ko': b'changed'})
                    else:
                        files = contents(outer['./control.tar.gz'])
                        files['./postinst'] = b'#!/bin/sh\nmodprobe rndis_host\n'
                        outer['./control.tar.gz'] = archive(files)
                    ipk.write_bytes(archive(outer))
                self.assertNotEqual(self.verify(root, 'vbnto').returncode, 0)

    def test_runtime_configs_preserve_existing_enabled_options(self):
        for profile in ('vbnto', 'vbnts'):
            baseline = gzip.decompress((ROOT / f'build/{profile}-4.1.38/kernel.config.gz').read_bytes()).decode()
            built = (ROOT / f'artifacts/usb-rndis-4.1.38/{profile}/kernel.config').read_text().splitlines()
            enabled = {line for line in baseline.splitlines() if line.startswith('CONFIG_') and line.endswith(('=y', '=m'))}
            self.assertFalse(enabled - set(built))
            self.assertIn('CONFIG_USB_NET_RNDIS_HOST=m', built)

    def test_shared_patch_matches_the_published_damson_build(self):
        metadata = (ROOT / 'artifacts/damson-4.1.52-rndis-compat/BUILD-METADATA.txt').read_text()
        digest = hashlib.sha256((ROOT / 'patches/usb-rndis/001-misc-class.patch').read_bytes()).hexdigest()
        self.assertIn('002-rndis-misc-class.patch_sha256=' + digest, metadata)
        self.assertEqual(digest, REGISTRY['shared_patch_sha256'])

    def test_native_usbnet_is_not_packaged_and_original_state_was_restored(self):
        for profile in ('vbnto', 'vbnts'):
            self.assertFalse(list((ROOT / f'artifacts/{profile}-4.1.38-manual').glob('*usbnet*.ipk')))
            log = (ROOT / f'artifacts/usb-rndis-4.1.38/{profile}/router-test.log').read_text()
            self.assertIn('RESTORE_RESULT=0', log)
            self.assertIn('BOOT_ID=' + REGISTRY['profiles'][profile]['boot_id'], log)


if __name__ == '__main__':
    unittest.main()
