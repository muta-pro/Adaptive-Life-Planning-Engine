"""Pure filtering and scoring: no terminal, files, clock, or random state."""

from dataclasses import dataclass

from skrov.domain import Recommendation, ScoreContribution, Task, TaskStatus, UserState, require_integer


@dataclass(frozen=True)
class ScoringPolicy:
    """Explicit integer weights make experiments and a later C++ port reproducible."""

    importance_weight: int = 2
    cycle_weight: int = 3
    rhythm_weight: int = 4
    exact_energy_bonus: int = 6
    energy_mismatch_cost: int = 3
    switching_weight: int = 1

    def __post_init__(self) -> None:
        for name in ("importance_weight", "cycle_weight", "rhythm_weight",
                     "exact_energy_bonus", "energy_mismatch_cost", "switching_weight"):
            require_integer(name, getattr(self, name), 0)


@dataclass(frozen=True)
class CandidateExclusion:
    task_id: int
    title: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class SchedulingDecision:
    # A | None annotation means the result may have no recommendation.
    recommendation: Recommendation | None
    exclusions: tuple[CandidateExclusion, ...]


def filter_candidates(
    tasks: list[Task], user: UserState
) -> tuple[list[Task], tuple[CandidateExclusion, ...]]:
    # A dictionary comprehension builds a lookup table: task ID -> task.
    by_id = {task.id: task for task in tasks}
    if len(by_id) != len(tasks):
        raise ValueError("Task IDs must be unique")
    candidates = []
    exclusions = []
    for task in sorted(tasks, key=lambda item: item.id):
        # lambda is a small anonymous function used here to select a sort key.
        reasons = []
        if task.status != TaskStatus.READY:
            reasons.append(f"status is {task.status.value}")
            if task.status == TaskStatus.BLOCKED and task.blocked_reason:
                reasons.append(f"blocked because: {task.blocked_reason}")
        if task.estimated_minutes > user.available_minutes:
            reasons.append(f"needs {task.estimated_minutes} minutes; {user.available_minutes} available")
        if task.context != "any" and task.context != user.context:
            reasons.append(f"needs context {task.context}; current context is {user.context}")
        # A one-level mismatch remains eligible and is penalized during scoring.
        # HIGH demand with LOW energy is excluded; lower-demand work remains possible.
        if task.energy_requirement - user.energy >= 2:
            reasons.append("energy demand is two levels above current energy")
        for dependency_id in task.dependencies:
            dependency = by_id.get(dependency_id)
            if dependency is None:
                reasons.append(f"dependency {dependency_id} is missing")
            elif dependency.status != TaskStatus.COMPLETED:
                reasons.append(f"dependency {dependency_id} is not completed")
        if reasons:
            exclusions.append(CandidateExclusion(task.id, task.title, tuple(reasons)))
        else:
            candidates.append(task)
    return candidates, tuple(exclusions)


def importance_score(task: Task, policy: ScoringPolicy) -> ScoreContribution:
    return ScoreContribution("importance", task.importance * policy.importance_weight,
                             f"{task.importance} × weight {policy.importance_weight}")


def cycle_score(task: Task, policy: ScoringPolicy) -> ScoreContribution:
    return ScoreContribution("cycle relevance", task.cycle_relevance * policy.cycle_weight,
                             f"{task.cycle_relevance} × weight {policy.cycle_weight}")


def rhythm_score(task: Task, policy: ScoringPolicy) -> ScoreContribution:
    return ScoreContribution("rhythm deficit", task.rhythm_deficit * policy.rhythm_weight,
                             f"max(0, target {task.rhythm_target} - completions "
                             f"{task.completions_in_cycle}) × weight {policy.rhythm_weight}")


def energy_score(task: Task, user: UserState, policy: ScoringPolicy) -> ScoreContribution:
    gap = abs(task.energy_requirement - user.energy)
    value = policy.exact_energy_bonus if gap == 0 else -gap * policy.energy_mismatch_cost
    return ScoreContribution("energy fit", value,
                             f"requires {task.energy_requirement.name.lower()}, "
                             f"current {user.energy.name.lower()}; "
                             f"exact match +{policy.exact_energy_bonus}, "
                             f"otherwise -{policy.energy_mismatch_cost} × gap {gap}")


def switching_score(task: Task, policy: ScoringPolicy) -> ScoreContribution:
    return ScoreContribution("switching cost", -task.switching_cost * policy.switching_weight,
                             f"-{task.switching_cost} × weight {policy.switching_weight}")


def score_task(task: Task, user: UserState, policy: ScoringPolicy) -> Recommendation:
    contributions = (
        importance_score(task, policy),
        cycle_score(task, policy),
        rhythm_score(task, policy),
        energy_score(task, user, policy),
        switching_score(task, policy),
    )
    return Recommendation(task.id, task.title, task.estimated_minutes, user, contributions)


def recommend(
    tasks: list[Task], user: UserState, policy: ScoringPolicy = ScoringPolicy()
) -> SchedulingDecision:
    candidates, exclusions = filter_candidates(tasks, user)
    ranked = [score_task(task, user, policy) for task in candidates]
    # A negative score sorts higher scores first; the second key breaks ties by ID.
    ranked.sort(key=lambda item: (-item.total_score, item.task_id))
    winner = ranked[0] if ranked else None
    return SchedulingDecision(winner, exclusions)
