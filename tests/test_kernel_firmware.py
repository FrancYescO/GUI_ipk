import gzip
import importlib.util
import io
import json
import lzma
from pathlib import Path
import struct
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from kernel_firmware import config_options, decrypt_rbi, elf_module, extract_config, kernel_exports, unresolved
import firmware_kernel_candidates as candidates


class FirmwareKernelTests(unittest.TestCase):
    def test_plain_rbi_envelope_and_unknown_types(self):
        header = bytearray(0x144)
        struct.pack_into('>H', header, 0x2a, len(header))
        header[0x13c:0x142] = b'VCNT-3'
        self.assertEqual(decrypt_rbi(bytes(header) + b'\xb0' + b'\0' * 5 + b'kernel'), (b'kernel', 'VCNT-3'))
        with self.assertRaises(ValueError):
            decrypt_rbi(bytes(header) + b'\xff' + b'\0' * 5)

    def test_nested_kernel_config_recovery_and_malformed_inputs(self):
        config = b'CONFIG_SMP=y\n# CONFIG_MODVERSIONS is not set\n'
        kernel = b'ARM text\0IKCFG_ST' + gzip.compress(config) + b'IKCFG_ED'
        layer = b'prefix' + lzma.compress(b'inner' + lzma.compress(kernel, format=lzma.FORMAT_ALONE), format=lzma.FORMAT_ALONE)
        actual, recovered, trace = extract_config(layer, [6, 5])
        self.assertEqual(actual, kernel)
        self.assertEqual(recovered, config)
        self.assertEqual(len(trace), 2)
        self.assertEqual(config_options(recovered)['CONFIG_MODVERSIONS'], 'n')
        for data, offsets in [(b'no kernel', []), (kernel[:-8], []), (layer, [len(layer)]), (layer[:-4], [6])]:
            with self.assertRaises((ValueError, lzma.LZMAError, EOFError)):
                extract_config(data, offsets)

    def test_absolute_export_tables_require_consistent_image_base(self):
        base = 0xc0018000
        names = ['kfree', 'printk', '__kmalloc', 'schedule'] + ['symbol_%03d' % i for i in range(140)]
        data = bytearray(32768)
        offset = 8192
        for i, name in enumerate(names):
            raw = name.encode() + b'\0'
            data[offset:offset + len(raw)] = raw
            struct.pack_into('<II', data, 16384 + i * 8, base + 256, base + offset)
            offset += len(raw)
        result = kernel_exports(bytes(data))
        self.assertEqual(result['base_address'], hex(base))
        self.assertEqual(set(result['exports']), set(names))
        with self.assertRaises(ValueError):
            kernel_exports(b'no tables')

    def test_stock_import_closure_is_not_satisfied_by_unexported_names(self):
        modules = [{'imports': ['kernel_fn', 'other_module_fn'], 'exports': []},
                   {'imports': [], 'exports': ['other_module_fn']}]
        self.assertEqual(unresolved(modules, ['kernel_fn']), [])
        self.assertEqual(unresolved(modules, ['some_internal_kernel_fn']), ['kernel_fn'])

    def test_real_arm_module_parser_checks_architecture_and_bounds(self):
        source = next((ROOT / 'artifacts/vbnts-4.1.38-manual').glob('kmod-tun-*.ipk'))
        with tarfile.open(source, 'r:gz') as tar:
            blob = tar.extractfile('./data.tar.gz').read()
        with tarfile.open(fileobj=io.BytesIO(blob), mode='r:gz') as tar:
            payload = next(tar.extractfile(m).read() for m in tar if m.isfile() and m.name.endswith('.ko'))
        info = elf_module(payload)
        self.assertIn('tun_get_socket', info['exports'])
        self.assertTrue(info['imports'])
        self.assertTrue(info['modinfo']['vermagic'][0].startswith('4.1.38 '))
        for broken in [payload[:20], payload[:18] + b'\x03\x00' + payload[20:], payload[:32] + b'\xff' * 4 + payload[36:]]:
            with self.assertRaises(ValueError):
                elf_module(broken)

    def test_pinned_candidates_have_no_boot_payloads_or_runtime_claim(self):
        for profile, entry in candidates.definitions().items():
            if not entry.get('bundle'):
                continue
            with tempfile.TemporaryDirectory() as temp:
                report = candidates.restore(profile, Path(temp))
                self.assertEqual(len(report['modules']), entry['module_count'])
                self.assertFalse(report['runtime_validated'])
                self.assertNotIn('bcmspu', {m['name'] for m in report['modules']})
                self.assertNotIn('xt_nat', {m['name'] for m in report['modules']})
                for check in report['firmware_checks']:
                    self.assertEqual(check['unresolved_symbols'], [])
                for ipk in Path(temp).glob('*.ipk'):
                    outer = candidates.files(ipk.read_bytes())
                    self.assertEqual(set(candidates.files(outer['./control.tar.gz'])), {'./control'})
                    paths = candidates.files(outer['./data.tar.gz'])
                    self.assertTrue(all(p.startswith('./usr/lib/kernel-module-candidates/' + profile + '/') for p in paths))

    def test_vcnt3_config_adaptation_preserves_model_differences(self):
        spec = importlib.util.spec_from_file_location('prepare_firmware', ROOT / 'scripts/prepare-firmware-kernel-config.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        text, changes = module.prepare('4.1.52-vcnt3')
        options = config_options(text.encode())
        self.assertEqual(len(changes), 22)
        self.assertEqual(options['CONFIG_BCM_HNDROUTER'], 'y')
        self.assertEqual(options['CONFIG_BCM_PKTFWD'], 'y')
        self.assertEqual(options['CONFIG_BCM_USBNET_THREAD'], 'n')
        self.assertEqual(options['CONFIG_BCM_SPU'], 'n')

    def test_existing_vbntk_feed_has_complete_offline_symbol_closure(self):
        ipks = [p for suffix in ('manual', 'network', 'spu', 'rndis-compat')
                for p in (ROOT / ('artifacts/damson-4.1.52-' + suffix)).glob('*.ipk')]
        report = candidates.audit_vbntk_ipks(ipks)
        self.assertEqual(report['module_count'], 49)
        self.assertEqual(report['unresolved_symbols'], [])
        self.assertFalse(report['runtime_validation_performed'])

    def test_telstra_builtin_tun_is_preserved_and_not_packaged(self):
        spec = importlib.util.spec_from_file_location('prepare_telstra', ROOT / 'scripts/prepare-firmware-kernel-config.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for profile in ('4.1.52-vcnta', '4.1.52-vbntv'):
            options = config_options(module.prepare(profile)[0].encode())
            self.assertEqual(options['CONFIG_TUN'], 'y')
            self.assertEqual(options['CONFIG_BCM_USBNET_THREAD'], 'y')
            self.assertEqual(options['CONFIG_BCM_HNDROUTER'], 'n')
            with tempfile.TemporaryDirectory() as temp:
                report = candidates.restore(profile, Path(temp))
                self.assertEqual(len(report['modules']), 48)
                self.assertNotIn('tun', {m['name'] for m in report['modules']})
            entry = candidates.definitions()[profile]
            payloads = {}
            for name, ipk in candidates.files((ROOT / entry['bundle']).read_bytes()).items():
                if name.endswith('.ipk'):
                    data = candidates.files(candidates.files(ipk)['./data.tar.gz'])
                    path, raw = next(iter(data.items()))
                    payloads[Path(path).stem] = raw
            payloads['tun'] = (ROOT / 'artifacts/damson-4.1.52-manual/tun.ko').read_bytes()
            definitions = candidates.definitions()
            definitions[profile]['module_count'] = 49
            del definitions[profile]['excluded_modules']['tun']
            with patch.object(candidates, 'definitions', return_value=definitions):
                with self.assertRaisesRegex(ValueError, 'duplicates built-in kernel exports: tun'):
                    candidates.audit(profile, payloads)


if __name__ == '__main__':
    unittest.main()
