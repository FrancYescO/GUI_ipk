import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / 'build/rclone-overlay/feeds/packages/net/rclone/files/rclone.init'

# Model rc.common/procd with file operations recorded, never performed.
HARNESS = r'''
config_load() { :; }
config_get_bool() { printf -v "$1" '%s' "$TEST_ENABLED"; }
config_get() {
    case "$3" in
        port) printf -v "$1" '%s' "$TEST_PORT" ;;
        username) printf -v "$1" '%s' "$TEST_USERNAME" ;;
        password) printf -v "$1" '%s' "$TEST_PASSWORD" ;;
        interface) printf -v "$1" '%s' "$TEST_INTERFACE" ;;
    esac
}
record() { printf '%s\n' "$@" >> "$TEST_LOG"; }
mkdir() { record file-op; }
touch() { record file-op; }
chmod() { record file-op; }
chown() { record file-op; }
logger() { record "$@"; }
procd_open_instance() { record open; }
procd_set_param() { record param "$@"; }
procd_append_param() { record append "$@"; }
procd_close_instance() { record close; }
source "$1"
start_service
'''


class RcloneServiceTests(unittest.TestCase):
    def run_service(self, **values):
        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / 'log'
            env = dict(os.environ, TEST_ENABLED='1', TEST_PORT='5572',
                       TEST_USERNAME='rclone', TEST_PASSWORD='a secret $value',
                       TEST_INTERFACE='', TEST_LOG=str(log))
            env.update({'TEST_' + key.upper(): value for key, value in values.items()})
            result = subprocess.run(['bash', '-c', HARNESS, 'test-service', str(INIT)],
                                    env=env, capture_output=True, text=True)
            return result.returncode, log.read_text().splitlines() if log.exists() else []

    def test_disabled_service_does_nothing(self):
        self.assertEqual(self.run_service(enabled='0'), (0, []))

    def test_missing_credentials_refuse_start_without_file_changes(self):
        for values in (dict(username=''), dict(password='')):
            code, lines = self.run_service(**values)
            self.assertNotEqual(code, 0)
            self.assertNotIn('file-op', lines)
            self.assertNotIn('open', lines)

    def test_invalid_port_refuses_start(self):
        for port in ('0', '65536', 'not-a-port'):
            code, lines = self.run_service(port=port)
            self.assertNotEqual(code, 0)
            self.assertNotIn('open', lines)
            self.assertNotIn('file-op', lines)

    def test_unknown_or_missing_interface_refuses_start(self):
        for interface in ('unknown', 'react', 'ng'):
            code, lines = self.run_service(interface=interface)
            self.assertNotEqual(code, 0)
            self.assertNotIn('open', lines)
            self.assertNotIn('file-op', lines)

    def test_authentication_loopback_and_unprivileged_user(self):
        code, lines = self.run_service()
        self.assertEqual(code, 0)
        self.assertIn('--rc-addr=127.0.0.1:5572', lines)
        self.assertIn('--rc-user=rclone', lines)
        self.assertIn('--rc-pass=a secret $value', lines)
        self.assertIn('--config=/etc/rclone/rclone.conf', lines)
        self.assertIn('user', lines)
        self.assertIn('group', lines)
        self.assertEqual(lines[-1], 'close')


if __name__ == '__main__':
    unittest.main()
