import gzip
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
ASSEMBLER = ROOT / "scripts/assemble-kernel-feed.py"
RNDIS = ROOT / "artifacts/damson-4.1.52-rndis-compat"
SPEC = importlib.util.spec_from_file_location("kernel_feed", ASSEMBLER)
kernel_feed = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(kernel_feed)


class RndisFeedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.base = self.work / "base"
        self.base.mkdir()
        for pattern in ("tun.ko", "act_connmark.ko", "kmod-tun-*.ipk", "kmod-act-connmark-*.ipk"):
            for artifact in (ROOT / "artifacts/damson-4.1.52-manual").glob(pattern):
                shutil.copy2(artifact, self.base)

    def assemble(self, rndis=RNDIS):
        return subprocess.run(
            ["python3", str(ASSEMBLER),
             str(self.base), str(self.work / "feed"),
             "--damson-rndis-dir", str(rndis)],
            capture_output=True, text=True,
        )

    def test_tested_pair_is_indexed_with_matching_downloads(self):
        result = self.assemble()
        self.assertEqual(result.returncode, 0, result.stderr)
        feed = self.work / "feed/kernel/4.1.52"
        index = (feed / "Packages").read_bytes()
        self.assertEqual(gzip.decompress((feed / "Packages.gz").read_bytes()), index)
        for ipk in RNDIS.glob("*.ipk"):
            self.assertIn(f"Filename: {ipk.name}\n", index.decode())
            self.assertEqual((feed / ipk.name).read_bytes(), ipk.read_bytes())
        self.assertEqual(len(list(feed.glob("*.ipk"))), 4)
        self.assertFalse((self.work / "feed/kernel/4.1.38").exists())

    def test_incomplete_pair_is_rejected(self):
        source = self.work / "rndis"
        shutil.copytree(RNDIS, source)
        next(source.glob("kmod-rndis-host*.ipk")).unlink()
        result = self.assemble(source)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Expected exactly the router-tested", result.stderr)
        self.assertFalse((self.work / "feed/kernel/4.1.52/Packages").exists())

    def test_packaged_module_must_match_raw_tested_artifact(self):
        source = self.work / "rndis"
        shutil.copytree(RNDIS, source)
        with (source / "cdc_ether.ko").open("ab") as output:
            output.write(b"corrupt")
        result = self.assemble(source)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Packaged module differs from raw artifact", result.stderr)

    def test_arm_packages_cannot_bypass_firmware_and_package_allowlist(self):
        ipk = next(RNDIS.glob("kmod-cdc-ether*.ipk"))
        original = kernel_feed.control_fields(ipk)
        for changes in (
            {"X-Kernel-Target": "another-board"},
            {"X-Firmware": "another-firmware"},
            {"Package": "kmod-untested-4.1.52-manual"},
        ):
            with self.subTest(changes=changes):
                fields = dict(original, **changes)
                with patch.object(kernel_feed, "control_fields", return_value=fields):
                    with self.assertRaisesRegex(ValueError, "Unexpected kernel package metadata"):
                        kernel_feed.write_feed("4.1.52", [ipk], self.work / "rejected")


if __name__ == "__main__":
    unittest.main()
