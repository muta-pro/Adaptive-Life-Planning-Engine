from datetime import datetime, timezone
import unittest

from skrov.app import SkrovApplication, WorkspaceState
from skrov.domain import Energy, OverrideReason, Task, TaskStatus, UserState
from skrov.sample import sample_tasks


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.app = SkrovApplication(WorkspaceState(tasks=sample_tasks()))
        self.user = UserState(45, Energy.HIGH, "desk")
        self.time = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)

    def test_recommend_start_done_preserves_lifecycle_history(self):
        recommendation = self.app.now(self.user).recommendation
        task = self.app.start(None, self.user, self.time)
        self.assertEqual(task.id, recommendation.task_id)
        self.assertEqual(task.status, TaskStatus.IN_PROGRESS)
        self.app.done(None, self.time)
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertEqual(task.completions_in_cycle, 1)
        self.assertEqual([event.new_status for event in self.app.state.task_events],
                         [TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED])
        self.assertNotEqual(self.app.now(self.user).recommendation.task_id, task.id)

    def test_execution_does_not_silently_reprioritize_or_start_two_slices(self):
        self.app.start(1, self.user, self.time)
        with self.assertRaisesRegex(ValueError, "in progress"):
            self.app.now(self.user)
        with self.assertRaisesRegex(ValueError, "active slice"):
            self.app.start(2, self.user, self.time)

    def test_override_preserves_every_task_status_and_the_recommendation_snapshot(self):
        recommendation = self.app.now(self.user).recommendation
        before = [task.status for task in self.app.state.tasks]
        event = self.app.override(OverrideReason.ENERGY_MISMATCH, self.time, 2,
                                  "Energy dropped after lunch")
        self.assertEqual([task.status for task in self.app.state.tasks], before)
        self.assertEqual(event.recommendation, recommendation)
        self.assertEqual(event.recommendation.user_state, self.user)
        self.assertEqual(event.reason, OverrideReason.ENERGY_MISMATCH)
        self.assertEqual(event.alternative_task_id, 2)
        self.assertEqual(event.occurred_at, self.time)
        self.assertEqual(len(self.app.state.overrides), 1)
        # Unchanged inputs produce the same decision; an override is not a penalty.
        again = self.app.now(self.user).recommendation
        self.assertEqual(again.task_id, recommendation.task_id)
        self.assertEqual(again.total_score, recommendation.total_score)

    def test_block_and_clear_keep_the_original_reason(self):
        self.app.blocked(1, "Missing socket API notes", self.time)
        self.assertEqual(self.app.task(1).status, TaskStatus.BLOCKED)
        self.assertNotEqual(self.app.now(self.user).recommendation.task_id, 1)
        self.app.unblock(1, self.time)
        self.assertEqual(self.app.task(1).status, TaskStatus.READY)
        self.assertIsNone(self.app.task(1).blocked_reason)
        self.assertEqual(self.app.state.task_events[0].reason, "Missing socket API notes")
        self.assertEqual(len(self.app.state.overrides), 0)

    def test_start_rechecks_current_eligibility(self):
        self.app.now(self.user)
        with self.assertRaisesRegex(ValueError, "energy demand"):
            self.app.start(None, UserState(45, Energy.LOW, "desk"), self.time)
        self.assertEqual(self.app.task(1).status, TaskStatus.READY)

    def test_invalid_actions_do_not_change_state(self):
        with self.assertRaises(ValueError):
            self.app.override(OverrideReason.OTHER, self.time)
        with self.assertRaises(ValueError):
            self.app.done(1, self.time)
        with self.assertRaises(ValueError):
            self.app.blocked(1, " ", self.time)
        with self.assertRaises(ValueError):
            self.app.add(Task(6, "Invalid dependency", "Learning", dependencies=(99,)))
        self.assertEqual(len(self.app.state.tasks), 5)
        self.assertEqual(self.app.state.task_events, [])
        self.assertEqual(self.app.state.overrides, [])

    def test_invalid_alternative_does_not_consume_recommendation(self):
        recommendation = self.app.now(self.user).recommendation
        with self.assertRaises(ValueError):
            self.app.override(OverrideReason.PERSONAL_CHOICE, self.time, recommendation.task_id)
        self.assertEqual(self.app.state.last_recommendation, recommendation)
        self.assertEqual(self.app.state.overrides, [])
