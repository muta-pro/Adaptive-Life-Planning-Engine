"""Application actions coordinate state; they do not read files or print."""

from dataclasses import dataclass, field, replace
from datetime import datetime

from skrov.domain import OverrideEvent, OverrideReason, Recommendation, Task, TaskEvent, TaskStatus, UserState
from skrov.scheduling import SchedulingDecision, filter_candidates, recommend


@dataclass
class WorkspaceState:
    # default_factory creates a new list for each workspace (no shared mutable default).
    tasks: list[Task] = field(default_factory=list)
    overrides: list[OverrideEvent] = field(default_factory=list)
    task_events: list[TaskEvent] = field(default_factory=list)
    last_recommendation: Recommendation | None = None
    next_recommendation_id: int = 1


class SkrovApplication:
    def __init__(self, state: WorkspaceState):
        # self refers to this application instance, like this in C++.
        self.state = state

    def task(self, task_id: int) -> Task:
        for task in self.state.tasks:
            if task.id == task_id:
                return task
        raise ValueError(f"Task {task_id} does not exist")

    def active_task(self) -> Task | None:
        active = [task for task in self.state.tasks if task.status == TaskStatus.IN_PROGRESS]
        if len(active) > 1:
            raise ValueError("Workspace contains multiple active tasks")
        return active[0] if active else None

    def add(self, task: Task) -> None:
        if any(existing.id == task.id for existing in self.state.tasks):
            raise ValueError(f"Task ID {task.id} already exists")
        for dependency in task.dependencies:
            self.task(dependency)  # Reject unknown dependencies without changing state.
        self.state.tasks.append(task)

    def now(self, user: UserState) -> SchedulingDecision:
        active = self.active_task()
        if active is not None:
            raise ValueError(f"Task {active.id} is in progress; use done or blocked before another recommendation")
        decision = recommend(self.state.tasks, user)
        if decision.recommendation is not None:
            # replace copies a dataclass with selected fields changed.
            saved = replace(decision.recommendation, id=self.state.next_recommendation_id)
            self.state.next_recommendation_id += 1
            decision = replace(decision, recommendation=saved)
        self.state.last_recommendation = decision.recommendation
        return decision

    def start(self, task_id: int | None, user: UserState, occurred_at: datetime) -> Task:
        if self.active_task() is not None:
            raise ValueError("Finish or block the active slice before starting another")
        if task_id is None:
            if self.state.last_recommendation is None:
                raise ValueError("Run now first, or supply a task ID to start")
            task_id = self.state.last_recommendation.task_id
        task = self.task(task_id)
        _, exclusions = filter_candidates(self.state.tasks, user)
        for exclusion in exclusions:
            if exclusion.task_id == task_id:
                raise ValueError("Cannot start: " + "; ".join(exclusion.reasons))
        self._transition(task, TaskStatus.IN_PROGRESS, occurred_at)
        return task

    def done(self, task_id: int | None, occurred_at: datetime) -> Task:
        task = self._resolve_active(task_id)
        if task.status != TaskStatus.IN_PROGRESS:
            raise ValueError("Only an in-progress slice can be completed; use start first")
        self._transition(task, TaskStatus.COMPLETED, occurred_at)
        task.completions_in_cycle += 1
        self.state.last_recommendation = None
        return task

    def blocked(self, task_id: int | None, reason: str, occurred_at: datetime) -> Task:
        if not reason.strip():
            raise ValueError("Blocking a task requires a reason")
        task = self._resolve_active(task_id)
        if task.status not in (TaskStatus.READY, TaskStatus.IN_PROGRESS):
            raise ValueError("Only a Ready or InProgress task can be blocked")
        self._transition(task, TaskStatus.BLOCKED, occurred_at, reason)
        task.blocked_reason = reason
        self.state.last_recommendation = None
        return task

    def unblock(self, task_id: int, occurred_at: datetime) -> Task:
        task = self.task(task_id)
        if task.status != TaskStatus.BLOCKED:
            raise ValueError("Only a blocked task can be unblocked")
        self._transition(task, TaskStatus.READY, occurred_at, "Block explicitly cleared")
        task.blocked_reason = None
        # Original blocking reasons remain in task_events.
        return task

    def override(
        self, reason: OverrideReason, occurred_at: datetime,
        alternative_task_id: int | None = None, note: str = ""
    ) -> OverrideEvent:
        recommendation = self.state.last_recommendation
        if recommendation is None:
            raise ValueError("Run now before recording an override")
        if alternative_task_id is not None:
            self.task(alternative_task_id)
            if alternative_task_id == recommendation.task_id:
                raise ValueError("An alternative must differ from the recommended task")
        event = OverrideEvent(recommendation, reason, occurred_at, alternative_task_id, note)
        self.state.overrides.append(event)
        self.state.last_recommendation = None
        # This event deliberately does not change any task's lifecycle.
        return event

    def _resolve_active(self, task_id: int | None) -> Task:
        # Leading _ marks a helper as internal by convention, not by access control.
        if task_id is not None:
            return self.task(task_id)
        active = self.active_task()
        if active is None:
            raise ValueError("No slice is in progress; supply a task ID or use start")
        return active

    def _transition(self, task: Task, status: TaskStatus, occurred_at: datetime, reason: str = "") -> None:
        self.state.task_events.append(TaskEvent(task.id, task.status, status, occurred_at, reason))
        task.status = status
