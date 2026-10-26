import importlib.util
import unittest
from pathlib import Path


spec = importlib.util.spec_from_file_location(
    "selection", Path(__file__).resolve().parents[1] / "scripts/select-userspace-feed-run.py"
)
selection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(selection)


class UserspaceFeedSelection(unittest.TestCase):
    def run_info(self, identifier, **overrides):
        return dict(id=identifier, name=selection.WORKFLOW, head_branch="main",
                    conclusion="success", **overrides)

    def artifact(self, name="userspace-opkg-feed-tested", expired=False):
        return dict(name=name, expired=expired)

    def query(self, runs, artifacts):
        def read(path):
            if "/workflows/" in path:
                return {"workflow_runs": runs}
            identifier = int(path.split("/runs/")[1].split("/")[0])
            if "/artifacts?" in path:
                return {"artifacts": artifacts.get(identifier, [])}
            return next(run for run in runs if run["id"] == identifier)
        return read

    def test_selects_latest_complete_feed_over_shards_and_expired_feeds(self):
        runs = [self.run_info(i) for i in (3, 2, 1)]
        read = self.query(runs, {3: [self.artifact("userspace-shard-0")],
                                 2: [self.artifact(expired=True)],
                                 1: [self.artifact()]})
        self.assertEqual(selection.select_run("owner/repo", query=read), 1)

    def test_explicit_run_is_verified(self):
        read = self.query([self.run_info(1)], {1: [self.artifact()]})
        self.assertEqual(selection.select_run("owner/repo", 1, read), 1)

    def test_missing_baseline_stops_publication(self):
        with self.assertRaisesRegex(RuntimeError, "Keeping the published feed unchanged"):
            selection.select_run("owner/repo", query=self.query([], {}))

    def test_failed_or_wrong_branch_run_is_rejected(self):
        for key, value in (("conclusion", "failure"), ("head_branch", "feature"),
                           ("name", "Other workflow")):
            run = self.run_info(1)
            run[key] = value
            with self.assertRaises(RuntimeError):
                selection.select_run("owner/repo", 1,
                                     self.query([run], {1: [self.artifact()]}))


if __name__ == "__main__":
    unittest.main()
