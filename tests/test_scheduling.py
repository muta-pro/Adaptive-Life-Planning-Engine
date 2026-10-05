"""Behavior scenarios can also become acceptance cases for the C++26 port."""

from dataclasses import replace
import unittest

from skrov.domain import Energy, Task, TaskStatus, UserState
from skrov.scheduling import ScoringPolicy, energy_score, filter_candidates, recommend, rhythm_score, score_task


def example(task_id: int, **changes) -> Task:
    # **changes collects named arguments in a dictionary, then expands them below.
    fields = dict(id=task_id, title=f"Task {task_id}", domain="Learning",
                  importance=0, cycle_relevance=0, rhythm_target=0)
    fields.update(changes)
    return Task(**fields)


class SchedulingTests(unittest.TestCase):
    def setUp(self):
        # unittest runs setUp before EACH test, giving it fresh inputs.
        self.user = UserState(30, Energy.MEDIUM, "desk")
        self.policy = ScoringPolicy()

    def test_importance_explains_why_a_task_outranks_another(self):
        low = example(1, importance=1)
        high = example(2, importance=5)
        winner = recommend([low, high], self.user).recommendation
        self.assertEqual(winner.task_id, 2)
        self.assertEqual(winner.total_score, 16)  # importance 10 + exact energy 6
        self.assertEqual(winner.contributions[0].value, 10)
        self.assertEqual(score_task(low, self.user, self.policy).total_score, 8)

    def test_energy_match_changes_the_winner_without_changing_status(self):
        high = example(1, energy_requirement=Energy.HIGH)
        medium = example(2, energy_requirement=Energy.MEDIUM)
        high_user = replace(self.user, energy=Energy.HIGH)
        self.assertEqual(recommend([medium, high], high_user).recommendation.task_id, 1)
        self.assertEqual(recommend([medium, high], self.user).recommendation.task_id, 2)
        self.assertEqual(energy_score(high, self.user, self.policy).value, -3)
        self.assertEqual(energy_score(medium, self.user, self.policy).value, 6)
        self.assertEqual(high.status, TaskStatus.READY)

    def test_severe_energy_mismatch_excludes_high_demand_but_not_recovery(self):
        high = example(1, energy_requirement=Energy.HIGH)
        rest = example(2, title="Recovery", energy_requirement=Energy.LOW, context="any")
        decision = recommend([high, rest], UserState(30, Energy.LOW, "home"))
        self.assertEqual(decision.recommendation.task_id, 2)
        self.assertIn("energy demand", " ".join(decision.exclusions[0].reasons))

    def test_rhythm_deficit_changes_ranking_and_has_visible_contribution(self):
        met = example(1, rhythm_target=2, completions_in_cycle=2)
        neglected = example(2, rhythm_target=3, completions_in_cycle=1)
        winner = recommend([met, neglected], self.user).recommendation
        self.assertEqual(winner.task_id, 2)
        rhythm = next(part for part in winner.contributions if part.name == "rhythm deficit")
        self.assertEqual(rhythm.value, 8)
        self.assertIn("target 3 - completions 1", rhythm.detail)
        self.assertEqual(rhythm_score(met, self.policy).value, 0)

    def test_extra_completions_do_not_create_negative_rhythm_pressure(self):
        task = example(1, rhythm_target=1, completions_in_cycle=4)
        self.assertEqual(task.rhythm_deficit, 0)

    def test_blocked_task_is_excluded_even_with_higher_importance(self):
        blocked = example(1, importance=5, status=TaskStatus.BLOCKED,
                          blocked_reason="Waiting for API access")
        ready = example(2, importance=1)
        decision = recommend([blocked, ready], self.user)
        self.assertEqual(decision.recommendation.task_id, 2)
        self.assertIn("status is blocked", decision.exclusions[0].reasons[0])
        self.assertEqual(blocked.status, TaskStatus.BLOCKED)

    def test_time_and_context_filters_preserve_all_exclusion_reasons(self):
        task = example(1, estimated_minutes=40, context="gym")
        candidates, exclusions = filter_candidates([task], self.user)
        self.assertEqual(candidates, [])
        self.assertEqual(len(exclusions[0].reasons), 2)
        self.assertIn("40 minutes", exclusions[0].reasons[0])
        self.assertIn("context gym", exclusions[0].reasons[1])
        self.assertEqual(task.status, TaskStatus.READY)

    def test_slice_that_exactly_fits_available_time_is_eligible(self):
        task = example(1, estimated_minutes=30)
        self.assertEqual(recommend([task], self.user).recommendation.task_id, 1)

    def test_unfinished_and_missing_dependencies_are_excluded(self):
        prerequisite = example(1)
        dependent = example(2, dependencies=(1,))
        missing = example(3, dependencies=(99,))
        candidates, exclusions = filter_candidates([prerequisite, dependent, missing], self.user)
        self.assertEqual([task.id for task in candidates], [1])
        self.assertIn("not completed", exclusions[0].reasons[0])
        self.assertIn("missing", exclusions[1].reasons[0])
        completed = replace(prerequisite, status=TaskStatus.COMPLETED)
        self.assertEqual(recommend([completed, dependent], self.user).recommendation.task_id, 2)

    def test_each_non_ready_lifecycle_state_is_excluded(self):
        for status in TaskStatus:
            if status != TaskStatus.READY:
                # subTest reports which particular enum value failed.
                with self.subTest(status=status):
                    self.assertIsNone(recommend([example(1, status=status)], self.user).recommendation)

    def test_stable_tie_breaking_ignores_input_order(self):
        tasks = [example(7), example(2)]
        first = recommend(tasks, self.user)
        second = recommend(list(reversed(tasks)), self.user)
        self.assertEqual(first, second)
        self.assertEqual(first.recommendation.task_id, 2)
        self.assertEqual(first, recommend(tasks, self.user))

    def test_explanation_contains_every_component_and_sums_to_total(self):
        task = example(1, importance=4, cycle_relevance=3, rhythm_target=2,
                       switching_cost=2, energy_requirement=Energy.HIGH)
        result = score_task(task, self.user, self.policy)
        self.assertEqual([part.name for part in result.contributions],
                         ["importance", "cycle relevance", "rhythm deficit", "energy fit", "switching cost"])
        self.assertEqual([part.value for part in result.contributions], [8, 9, 8, -3, -2])
        self.assertEqual(result.total_score, 20)

    def test_policy_can_be_changed_for_experiments(self):
        important = example(1, importance=5)
        rhythmic = example(2, rhythm_target=2)
        self.assertEqual(recommend([important, rhythmic], self.user).recommendation.task_id, 1)
        policy = replace(self.policy, rhythm_weight=10)
        self.assertEqual(recommend([important, rhythmic], self.user, policy).recommendation.task_id, 2)

    def test_no_candidates_including_zero_available_time_is_explicit(self):
        self.assertIsNone(recommend([], self.user).recommendation)
        decision = recommend([example(1)], replace(self.user, available_minutes=0))
        self.assertIsNone(decision.recommendation)
        self.assertEqual(len(decision.exclusions), 1)

    def test_duplicate_ids_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            recommend([example(1), example(1)], self.user)

    def test_invalid_domain_values_are_rejected(self):
        for fields in [dict(importance=6), dict(estimated_minutes=0), dict(title=" "),
                       dict(completions_in_cycle=-1), dict(dependencies=(1,))]:
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                example(1, **fields)
        with self.assertRaises(ValueError):
            UserState(-1)

    def test_invalid_experiment_weights_are_rejected(self):
        with self.assertRaises(ValueError):
            ScoringPolicy(rhythm_weight=-1)
        with self.assertRaises(ValueError):
            ScoringPolicy(importance_weight=1.5)
