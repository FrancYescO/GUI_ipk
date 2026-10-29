"""Exercise private bridge preparation and process-only device redirection."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / 'experiments/spu-cbc'


class PrivateBridgeTests(unittest.TestCase):
    def test_real_pinned_source_is_copy_only_and_has_private_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            archive = ROOT / 'artifacts/cryptodev/source/cryptodev-linux-08644db.tar.gz'
            with tarfile.open(archive) as source:
                for member in source.getmembers():
                    relative = Path(*Path(member.name).parts[1:])
                    if not relative.parts:
                        continue
                    self.assertNotIn('..', relative.parts)
                    self.assertFalse(member.issym() or member.islnk())
                    member.name = str(relative)
                    source.extract(member, work)
            subprocess.run(['patch', '--batch', '--forward', '-d', str(work), '-p1',
                            '-i', str(ROOT / 'patches/cryptodev/001-page-ownership-and-bounds.patch')],
                           check=True, capture_output=True)
            subprocess.run([sys.executable, str(LAB / 'prepare-bridge.py'), str(work)], check=True)
            ioctl = (work / 'ioctl.c').read_text()
            self.assertIn('.name = "crypto-cbc-lab"', ioctl)
            self.assertIn('.minor = MISC_DYNAMIC_MINOR', ioctl)
            self.assertIn('.mode = 0600', ioctl)
            self.assertIn('sop->cipher != CRYPTO_AES_CBC || sop->mac', ioctl)
            self.assertIn('kcop->cop.flags |= COP_FLAG_NO_ZC', ioctl)
            self.assertIn('kcop->mm = NULL', ioctl)
            self.assertNotIn('MODULE_ALIAS(', ioctl)
            for filename in ('ioctl.c', 'authenc.c', 'zc.c', 'cryptodev_int.h'):
                source = (work / filename).read_text()
                for member in ('mm', 'comm', 'pid'):
                    self.assertNotIn('current->' + member, source)
            self.assertIn('if (!mm)', (work / 'zc.c').read_text())
            self.assertIn('obj-m += cryptodev_cbc_lab.o', (work / 'Makefile').read_text())

    @unittest.skipUnless(sys.platform == 'linux' and shutil.which('cc'), 'Linux headers required')
    def test_session_tool_refuses_stock_device_before_open(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            with tarfile.open(ROOT / 'artifacts/cryptodev/source/cryptodev-linux-08644db.tar.gz') as source:
                header = next(m for m in source if m.name.endswith('/crypto/cryptodev.h'))
                (work / 'crypto').mkdir()
                (work / 'crypto/cryptodev.h').write_bytes(source.extractfile(header).read())
            subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', '-I'+str(work),
                            str(LAB / 'session-test.c'), '-o', str(work / 'session-test')], check=True)
            result = subprocess.run([str(work / 'session-test'), '/dev/crypto'], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'/dev/crypto-cbc-lab', result.stdout + result.stderr)

    @unittest.skipUnless(sys.platform == 'linux' and shutil.which('cc'), 'Linux LD_PRELOAD required')
    def test_redirect_only_exact_path_and_preserve_create_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            origin, target, other = [work / name for name in ('origin', 'target', 'other')]
            origin.write_text('ORIGINAL')
            target.write_text('PRIVATE')
            other.write_text('OTHER')
            shim = work / 'redirect.so'
            subprocess.run(['cc', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror',
                            '-DSPU_CRYPTO_FROM="'+str(origin)+'"',
                            '-DSPU_CRYPTO_TO="'+str(target)+'"', str(LAB / 'redirect-crypto.c'),
                            '-ldl', '-o', str(shim)], check=True)
            client = work / 'client.c'
            client.write_text(r'''
#define _GNU_SOURCE
#include <fcntl.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>
int main(int argc, char **argv) {
    char buf[16] = {0}; struct stat st;
    int fd = open(argv[1], O_RDONLY);
    if (argc != 5 || fd < 0 || read(fd, buf, 15) != 7 || strcmp(buf, "PRIVATE")) return 1;
    close(fd); memset(buf, 0, sizeof(buf));
    fd = open64(argv[1], O_RDONLY);
    if (fd < 0 || read(fd, buf, 15) != 7 || strcmp(buf, "PRIVATE")) return 2;
    close(fd); memset(buf, 0, sizeof(buf));
    fd = open(argv[2], O_RDONLY);
    if (fd < 0 || read(fd, buf, 15) != 5 || strcmp(buf, "OTHER")) return 3;
    close(fd); umask(0);
    fd = open(argv[3], O_WRONLY|O_CREAT|O_EXCL, 0640);
    if (fd < 0 || fstat(fd, &st) || (st.st_mode & 0777) != 0640) return 4;
    close(fd);
    fd = open64(argv[4], O_WRONLY|O_CREAT|O_EXCL, 0600);
    if (fd < 0 || fstat(fd, &st) || (st.st_mode & 0777) != 0600) return 5;
    close(fd); return 0;
}
''')
            subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', str(client), '-o', str(work / 'client')], check=True)
            import os
            subprocess.run([str(work / 'client'), str(origin), str(other), str(work / 'created'),
                            str(work / 'created64')], env={**os.environ, 'LD_PRELOAD':str(shim)}, check=True)
            self.assertEqual(origin.read_text(), 'ORIGINAL')

    def test_bundle_manifest_binds_payloads(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            (work / 'sample').write_bytes(b'abc')
            subprocess.run([sys.executable, str(LAB / 'manifest.py'), temporary], check=True, cwd=ROOT)
            report = json.loads((work / 'bundle.json').read_text())
            self.assertTrue(report['experimental'])
            self.assertEqual(report['files']['sample'], 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')
            self.assertEqual(report['runtime_profile'], '4.1.52-vbntk')


if __name__ == '__main__':
    unittest.main()
