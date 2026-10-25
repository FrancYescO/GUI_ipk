import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BOOTSTRAP=ROOT/'build/application-updates-overlay/common/bootstrap.sh'

class ModernPrefixTests(unittest.TestCase):
    def test_private_dependencies_bypass_legacy_pkgconfig_rewrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            work=Path(temporary)
            tools=work/'.modern-application-tools'
            tools.mkdir()
            (tools/'ready').touch()
            binaries=work/'staging_dir/host/bin'
            binaries.mkdir(parents=True)
            lock=binaries/'flock'
            lock.write_text('#!/bin/sh\nexit 0\n')
            lock.chmod(0o755)
            wrapper=binaries/'pkg-config'
            wrapper.write_text('#!/bin/sh\necho WRONG_LEGACY_PREFIX\n')
            wrapper.chmod(0o755)
            real=binaries/'pkg-config.real'
            real.write_text('#!/bin/sh\nprintf "%s\\n" "$PKG_CONFIG_LIBDIR" "$@"\n')
            real.chmod(0o755)
            prefix=work/'private-prefix'
            script=r'''
source "$1"
bootstrap_modern "$2" "$2/downloads"
setup_private_prefix "$2/private-prefix"
$PKG_CONFIG --cflags example
'''
            env=dict(os.environ,PATH=str(binaries)+':'+os.environ['PATH'],STAGING_PREFIX='/wrong/legacy/sysroot')
            result=subprocess.run(['bash','-c',script,'prefix-test',str(BOOTSTRAP),str(work)],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout.splitlines(),[str(prefix/'lib/pkgconfig'),'--static','--cflags','example'])
            self.assertNotIn('WRONG_LEGACY_PREFIX',result.stdout)

if __name__=='__main__':unittest.main()
