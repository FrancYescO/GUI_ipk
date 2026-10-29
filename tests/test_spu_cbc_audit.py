"""Do not mistake nested AEAD names or comments for standalone AES-CBC support."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('spu_cbc_audit', ROOT / 'scripts/audit-spu-cbc.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SpuCbcAuditTests(unittest.TestCase):
    def fixture(self, root, extra=''):
        source = root / 'bcmdrivers/opensource/char/spudd/impl3'
        source.mkdir(parents=True)
        (source / 'spu.c').write_text('''
            .cra_name = "authenc(hmac(sha1),cbc(aes))",
            .givencrypt = spu_aead_givencrypt,
            /* .encrypt = unsupported; .cra_name = "cbc(aes)"; */
        ''' + extra)
        (source / 'spu_runner.c').write_text('/* fixture */')
        helper = root / 'rdp/drivers/rdpa_gpl/include'
        helper.mkdir(parents=True)
        (helper / 'rdpa_ipsec_helper.h').write_text('''
            typedef enum { rdpa_auth_alg_sha1, rdpa_auth_alg_checksum }
                rdpa_ipsec_auth_alg_e;
            int rdpa_ipsec_sa_desc_setting(int dir, int auth_algorithm);
        ''')

    def test_combined_name_and_comment_are_not_cbc_support(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            report = module.audit(str(root))
            self.assertFalse(report['plain_cbc_aes_registered'])
            self.assertEqual(report['aead_encrypt_callbacks'], [])
            self.assertEqual(report['aead_givencrypt_callbacks'], ['spu_aead_givencrypt'])
            self.assertEqual(len(report['source_sha256']), 3)

    def test_source_registration_does_not_certify_hardware(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root, '.cra_name = "cbc(aes)", .encrypt = lab_encrypt,')
            report = module.audit(str(root))
            self.assertTrue(report['plain_cbc_aes_registered'])
            self.assertEqual(report['hardware_plain_cbc_validation'], 'not-established')

    def test_unknown_source_layout_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            (root / 'bcmdrivers/opensource/char/spudd/impl3/spu.c').write_text('')
            with self.assertRaises(ValueError):
                module.audit(str(root))
