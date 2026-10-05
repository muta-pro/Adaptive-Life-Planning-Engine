from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from skrov.app import SkrovApplication, WorkspaceState
from skrov.domain import Energy, OverrideReason, TaskStatus, UserState
from skrov.sample import sample_tasks
from skrov.storage import load_state, save_state


class StorageTests(unittest.TestCase):
    def test_round_trip_preserves_enums_snapshots_and_timestamps(self):
        app = SkrovApplication(WorkspaceState(tasks=sample_tasks()))
        time = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
        app.now(UserState(45, Energy.HIGH, "desk"))
        app.override(OverrideReason.WRONG_PRIORITY, time, 3, "Deadline changed")
        app.blocked(1, "Waiting for documentation", time)
        app.now(UserState())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "state.json"
            save_state(path, app.state)
            self.assertEqual(load_state(path), app.state)
            self.assertEqual(load_state(path).overrides[0].reason, OverrideReason.WRONG_PRIORITY)
            self.assertIsInstance(load_state(path).tasks[0].status, TaskStatus)
            self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_corrupt_data_is_reported_without_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text("broken JSON", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not replaced"):
                load_state(path)
            self.assertEqual(path.read_text(), "broken JSON")

    def test_unknown_schema_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text('{"format_version": 99}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unsupported"):
                load_state(path)

    def test_invalid_saved_score_is_rejected_without_replacement(self):
        app = SkrovApplication(WorkspaceState(tasks=sample_tasks()))
        app.now(UserState())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            save_state(path, app.state)
            data = json.loads(path.read_text())
            data["last_recommendation"]["contributions"][0]["value"] = "not a number"
            path.write_text(json.dumps(data), encoding="utf-8")
            before = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "integers"):
                load_state(path)
            self.assertEqual(path.read_bytes(), before)


class CLITests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "state.json"

    def run_cli(self, *arguments, expected_code=0):
        # subprocess launches a NEW Python process; this tests real persistence.
        result = subprocess.run(
            [sys.executable, "-m", "skrov", "--data", str(self.path), *arguments],
            capture_output=True, text=True, cwd=self.directory.name,
        )
        self.assertEqual(result.returncode, expected_code, result.stdout + result.stderr)
        return result

    def test_all_eight_commands_work_across_processes(self):
        listing = self.run_cli("list").stdout
        for title in ["Webserv event loop", "CPP Module 08", "Job application",
                      "Menura landing page", "Climbing / recovery"]:
            self.assertIn(title, listing)
        output = self.run_cli("now", "--energy", "high").stdout
        self.assertIn("Next Slice [1]", output)
        self.assertIn("Ranking score: 32", output)
        for component in ["importance", "cycle relevance", "rhythm deficit", "energy fit", "switching cost"]:
            self.assertIn(component, output)
        self.run_cli("override", "energy_mismatch", "--alternative", "2", "--note", "Need a lighter slice")
        state = load_state(self.path)
        self.assertTrue(all(task.status == TaskStatus.READY for task in state.tasks))
        self.assertEqual(state.overrides[0].reason, OverrideReason.ENERGY_MISMATCH)
        self.run_cli("now", "--energy", "medium")
        self.run_cli("start")  # Inherits the last recommendation's user state.
        self.assertEqual(load_state(self.path).tasks[1].status, TaskStatus.IN_PROGRESS)
        self.run_cli("done")
        self.assertEqual(load_state(self.path).tasks[1].status, TaskStatus.COMPLETED)
        self.run_cli("blocked", "1", "--reason", "Missing dependency")
        self.assertIn("status is blocked", self.run_cli("now").stdout)
        self.run_cli("add", "Read a chapter", "--domain", "Learning", "--minutes", "15",
                     "--energy", "low", "--depends-on", "2")
        status = self.run_cli("status").stdout
        self.assertIn("completed: 1", status)
        self.assertIn("blocked: 1", status)
        self.assertIn("Override events: 1", status)
        self.assertIn("energy_mismatch", status)
        self.assertEqual(len(load_state(self.path).tasks), 6)
        saved = json.loads(self.path.read_text())
        self.assertNotIn("flowScore", saved)

    def test_empty_workspace_and_no_candidate_explanation(self):
        self.assertIn("No tasks", self.run_cli("--empty", "list").stdout)
        self.assertIn("No eligible", self.run_cli("now").stdout)
        self.run_cli("add", "Exercise", "--domain", "Health", "--context", "gym")
        result = self.run_cli("now", "--minutes", "0")
        self.assertIn("No eligible", result.stdout)
        self.assertIn("context gym", result.stdout)
        self.assertIn("0 available", result.stdout)

    def test_invalid_command_inputs_leave_file_unchanged(self):
        self.run_cli("list")
        before = self.path.read_bytes()
        self.run_cli("add", "Invalid", "--domain", "Learning", "--minutes", "0", expected_code=1)
        self.run_cli("done", "999", expected_code=1)
        self.run_cli("override", "other", expected_code=1)
        self.run_cli("now", "--energy", "unknown", expected_code=2)
        self.run_cli("now", "--minutes", "-1", expected_code=1)
        self.assertEqual(self.path.read_bytes(), before)

    def test_corrupt_workspace_is_not_silently_reseeded(self):
        self.path.write_text("broken JSON", encoding="utf-8")
        result = self.run_cli("list", expected_code=1)
        self.assertIn("not replaced", result.stderr)
        self.assertEqual(self.path.read_text(), "broken JSON")

    def test_clear_block_and_explicit_start(self):
        self.run_cli("blocked", "1", "--reason", "Waiting")
        self.run_cli("start", "1", "--energy", "high", expected_code=1)
        self.run_cli("blocked", "1", "--clear")
        self.run_cli("start", "1", "--energy", "high")
        self.run_cli("now", expected_code=1)
        self.run_cli("done")
        state = load_state(self.path)
        self.assertEqual(state.tasks[0].status, TaskStatus.COMPLETED)
        self.assertEqual(state.task_events[0].reason, "Waiting")


if __name__ == "__main__":
    unittest.main()
