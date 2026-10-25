import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / 'build/application-updates-overlay/feeds/packages/net/tailscale/files/tailscale.init'
HARNESS = r'''
config_load() { :; }
config_get_bool() { printf -v "$1" '%s' "$TEST_ENABLED"; }
config_get() {
 case "$3" in
  port) printf -v "$1" '%s' "$TEST_PORT" ;;
  tun) printf -v "$1" '%s' "$TEST_TUN" ;;
 esac
}
record() { printf '%s\n' "$@" >> "$TEST_LOG"; }
mkdir() { record file-op; }
chmod() { record file-op; }
procd_open_instance() { record open; }
procd_set_param() { record param "$@"; }
procd_close_instance() { record close; }
source "$1"
start_service
'''


class TailscaleServiceTests(unittest.TestCase):
    def service(self, **values):
        with tempfile.TemporaryDirectory() as temp:
            log=Path(temp)/'log'
            env=dict(os.environ, TEST_ENABLED='1', TEST_PORT='41641', TEST_TUN='tailscale0', TEST_LOG=str(log))
            env.update({'TEST_'+k.upper():v for k,v in values.items()})
            result=subprocess.run(['bash','-c',HARNESS,'test-service',str(INIT)],env=env,capture_output=True,text=True)
            return result.returncode, log.read_text().splitlines() if log.exists() else []

    def test_disabled_starts_nothing(self):
        self.assertEqual(self.service(enabled='0'),(0,[]))

    def test_invalid_ports_refuse_before_file_operations(self):
        for port in ('-1','65536','invalid'):
            code,lines=self.service(port=port)
            self.assertNotEqual(code,0)
            self.assertEqual(lines,[])

    def test_invalid_tun_refuses_start(self):
        for tun in ('','../other','name with spaces'):
            code,lines=self.service(tun=tun)
            self.assertNotEqual(code,0)
            self.assertEqual(lines,[])

    def test_enabled_service_starts_daemon_without_login(self):
        code,lines=self.service()
        self.assertEqual(code,0)
        self.assertIn('/usr/sbin/tailscaled',lines)
        self.assertIn('--state=/etc/tailscale/tailscaled.state',lines)
        self.assertIn('--socket=/var/run/tailscale/tailscaled.sock',lines)
        self.assertNotIn('up',lines)
        self.assertNotIn('login',lines)
        self.assertEqual(lines[-1],'close')

    def test_explicit_userspace_mode_is_supported(self):
        code,lines=self.service(port='0',tun='userspace-networking')
        self.assertEqual(code,0)
        self.assertIn('--tun=userspace-networking',lines)
        self.assertIn('--port=0',lines)


if __name__=='__main__':
    unittest.main()
