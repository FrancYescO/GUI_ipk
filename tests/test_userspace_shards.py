import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("shards", ROOT / "scripts/select-userspace-shard.py")
shards = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shards)


class UserspaceShardTests(unittest.TestCase):
    def test_script_under_kernel_directory_is_not_lost(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config"
            deps = root / "deps"
            config.write_text("CONFIG_PACKAGE_om-watchdog=m\nCONFIG_PACKAGE_kernel=y\n"
                              "CONFIG_PACKAGE_kmod-example=m\nCONFIG_PACKAGE_libc=y\n")
            deps.write_text("package-$(CONFIG_PACKAGE_om-watchdog) += kernel/om-watchdog\n"
                            "package-$(CONFIG_PACKAGE_kernel) += kernel/linux\n"
                            "package-$(CONFIG_PACKAGE_kmod-example) += kernel/example\n"
                            "package-$(CONFIG_PACKAGE_libc) += libs/toolchain\n")
            results = [shards.select(config, deps, i, 2) for i in range(2)]
            recipes = [recipe for result in results for recipe in result["recipes"]]
            self.assertEqual(sorted(recipes), ["kernel/om-watchdog", "libs/toolchain"])
            self.assertEqual(len(recipes), len(set(recipes)))
            self.assertEqual(results[0]["all_recipes_sha256"], results[1]["all_recipes_sha256"])


if __name__ == "__main__":
    unittest.main()
