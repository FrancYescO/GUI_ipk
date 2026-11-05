"""Regressions observed in the complete legacy userspace CI build."""

import os
import csv
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('git') and shutil.which('make'), 'git and make required')
class GitTransportTests(unittest.TestCase):
    def test_rewrite_survives_make_config_sanitization(self):
        patch = (ROOT / 'patches/userspace-ci-compat.patch').read_text()
        export = next(line[1:] for line in patch.splitlines()
                      if line.startswith('+export GIT_CONFIG_PARAMETERS='))
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            (work / 'Makefile').write_text(export + '\nall:\n\t@git ls-remote --get-url git://github.com/example/repository.git\n')
            env = dict(os.environ, GIT_CONFIG_NOSYSTEM='1',
                       GIT_CONFIG_GLOBAL=str(work / 'unused-config'))
            actual = subprocess.check_output(['make', '-s', '-C', str(work)],
                                             env=env, universal_newlines=True)
            self.assertEqual(actual.strip(), 'https://github.com/example/repository.git')


@unittest.skipUnless(shutil.which('cc'), 'C compiler required')
class HostapdTaxonomyTests(unittest.TestCase):
    def link(self, taxonomy, mlme, provider):
        patch = (ROOT / 'patches/hostapd-taxonomy-mlme.patch').read_text()
        guard = next(line[1:] for line in patch.splitlines() if line.startswith('+#if '))
        source = 'void sta_track_claim_taxonomy_info(void);\n'
        if provider:
            source += 'void sta_track_claim_taxonomy_info(void) {}\n'
        source += 'int main(void) {\n' + guard + '\nsta_track_claim_taxonomy_info();\n#endif\nreturn 0;\n}\n'
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            (work / 'fixture.c').write_text(source)
            args = ['cc', str(work / 'fixture.c'), '-o', str(work / 'fixture')]
            if taxonomy:
                args.append('-DCONFIG_TAXONOMY')
            if mlme:
                args.append('-DNEED_AP_MLME')
            return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode

    def test_non_mlme_variants_do_not_require_beacon_taxonomy(self):
        self.assertEqual(self.link(True, False, False), 0)
        self.assertEqual(self.link(False, True, False), 0)

    def test_wireless_taxonomy_still_requires_and_uses_its_provider(self):
        self.assertNotEqual(self.link(True, True, False), 0)
        self.assertEqual(self.link(True, True, True), 0)


class CompilerEligibilityTests(unittest.TestCase):
    def test_unavailable_compiler_is_reported_without_counting_it_as_built(self):
        spec = importlib.util.spec_from_file_location('ci_coverage', ROOT / 'scripts/report-homeware-coverage.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            catalog = work / 'catalog.tsv'
            with catalog.open('w', newline='') as stream:
                writer = csv.DictWriter(stream, ['homeware', 'section', 'name', 'version', 'architecture'], delimiter='\t')
                writer.writeheader()
                writer.writerow(dict(homeware='18', section='packages', name='mpd-full',
                                     version='0.20.9-2', architecture='arm_cortex-a9_neon'))
            (work / 'base').mkdir()
            (work / 'base/Packages').write_text('Package: example\nVersion: 1\n')
            metadata = work / 'metadata'
            metadata.write_text('Source-Makefile: package/feeds/packages/mpd/Makefile\nPackage: mpd-full\nDepends: @!GCC_VERSION_4_8 +libstdcpp\n')
            config = work / 'config'
            config.write_text('CONFIG_GCC_VERSION_4_8=y\n')
            rows, summary = module.compare(catalog, work, metadata, config)
            self.assertEqual(rows[0]['status'], 'toolchain-unavailable')
            self.assertIn('GCC_VERSION_4_8', rows[0]['unavailable_reason'])
            self.assertEqual(summary['versions'][0]['present'], 0)
            self.assertEqual(summary['versions'][0]['missing'], 1)
            config.write_text('CONFIG_GCC_VERSION_5=y\n')
            self.assertEqual(module.compare(catalog, work, metadata, config)[0][0]['status'], 'not-selected')
            config.write_text('CONFIG_GCC_VERSION_5=y\nCONFIG_PACKAGE_mpd-full=m\n')
            self.assertEqual(module.compare(catalog, work, metadata, config)[0][0]['status'], 'not-built')
