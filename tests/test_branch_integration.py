"""Check the remaining userspace changes without enabling unfinished GCC builds."""

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
LINK_IDS = (
    'SWITCH_TYPE_LINK', 'SWITCH_ATTR_OP_VALUE_LINK', 'SWITCH_LINK_ATTR_MAX',
    'SWITCH_LINK_FLAG_ANEG', 'SWITCH_LINK_FLAG_DUPLEX',
    'SWITCH_LINK_FLAG_EEE_1000BASET', 'SWITCH_LINK_FLAG_EEE_100BASET',
    'SWITCH_LINK_FLAG_LINK', 'SWITCH_LINK_FLAG_RX_FLOW',
    'SWITCH_LINK_FLAG_TX_FLOW', 'SWITCH_LINK_SPEED',
)


class ExperimentalCompilerTests(unittest.TestCase):
    def preflight(self, flag, target='', userspace='1'):
        with tempfile.TemporaryDirectory() as temporary:
            env = dict(os.environ, ENABLE_NATIVE_GCC_BOOTSTRAP=flag,
                       USERSPACE_ONLY=userspace, PACKAGE_TARGETS=target,
                       SOURCE_DIR=temporary)
            return subprocess.run(['bash', str(ROOT / 'scripts/build-packages.sh')],
                                  env=env, capture_output=True, text=True)

    def test_shared_build_cannot_enable_experimental_compiler(self):
        result = self.preflight('1')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('explicit PACKAGE_TARGETS=feeds/packages/gcc', result.stderr)

    def test_only_an_explicit_native_gcc_target_passes_the_guard(self):
        result = self.preflight('1', 'package/feeds/packages/gcc/compile')
        self.assertIn('Missing build input:', result.stderr)
        self.assertNotIn('requires USERSPACE_ONLY', result.stderr)
        for target in ('feeds/packages/gcc-other', 'feeds/packages/curl'):
            self.assertIn('requires USERSPACE_ONLY', self.preflight('1', target).stderr)

    def test_default_build_and_invalid_flag(self):
        self.assertIn('Missing build input:', self.preflight('0').stderr)
        self.assertIn('must be 0 or 1', self.preflight('2').stderr)


@unittest.skipUnless(shutil.which('cc') and shutil.which('make'), 'C compiler and make required')
class SwitchHeaderProbeTests(unittest.TestCase):
    def probe(self, header):
        patch = (ROOT / 'patches/swconfig-vendor-uapi.patch').read_text()
        additions = '\n'.join(line[1:] for line in patch.splitlines()
                              if line.startswith('+') and not line.startswith('+++'))
        expression = re.search(r'SWCONFIG_HAS_LINK := \$\(shell .*?echo 1\)',
                               additions, re.S).group()
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            include = work / 'user_headers/include/linux'
            include.mkdir(parents=True)
            (include / 'switch.h').write_text(header)
            (work / 'Makefile').write_text(
                'TARGET_CC := ' + shutil.which('cc') + '\nLINUX_DIR := ' + str(work) + '\n' +
                expression + "\nall:\n\t@printf '%s' '$(SWCONFIG_HAS_LINK)'\n")
            return subprocess.check_output(['make', '--no-print-directory', '-s', '-C', str(work)],
                                           text=True).strip()

    def test_complete_link_uapi_is_enabled(self):
        self.assertEqual(self.probe('enum { ' + ', '.join(LINK_IDS) + ' };\n'), '1')

    def test_missing_flow_flag_is_disabled(self):
        ids = [item for item in LINK_IDS if item != 'SWITCH_LINK_FLAG_TX_FLOW']
        self.assertEqual(self.probe('enum { ' + ', '.join(ids) + ' };\n'), '')

    def test_names_in_comments_do_not_enable_legacy_headers(self):
        self.assertEqual(self.probe('/* ' + ' '.join(LINK_IDS) + ' */\n'), '')
