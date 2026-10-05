"""Small domain types shared by the scheduler, application, and storage."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, IntEnum


# Enum gives names to a fixed set of choices. str makes their saved values readable.
class TaskStatus(str, Enum):
    READY = "ready"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DEFERRED = "deferred"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class OverrideReason(str, Enum):
    WRONG_PRIORITY = "wrong_priority"
    ENERGY_MISMATCH = "energy_mismatch"
    INSUFFICIENT_TIME = "insufficient_time"
    MISSING_DEPENDENCY = "missing_dependency"
    UNEXPECTED_URGENCY = "unexpected_urgency"
    PERSONAL_CHOICE = "personal_choice"
    OTHER = "other"


# IntEnum also allows subtraction: HIGH - MEDIUM is an energy gap of 1.
class Energy(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3


def require_integer(name: str, value: int, minimum: int, maximum: int | None = None) -> None:
    # Type annotations describe expected types; Python does not enforce them for us.
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be <= {maximum}")


def require_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must contain text")


def require_timestamp(value: datetime) -> None:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("Feedback timestamps must include a timezone")


# @dataclass generates an initializer and equality comparison from these fields.
@dataclass
class Task:
    id: int
    title: str
    domain: str
    estimated_minutes: int = 25
    energy_requirement: Energy = Energy.MEDIUM
    context: str = "desk"
    project: str = ""
    status: TaskStatus = TaskStatus.READY
    importance: int = 3
    cycle_relevance: int = 3
    rhythm_target: int = 1
    completions_in_cycle: int = 0
    switching_cost: int = 0
    # tuple[int, ...] means an immutable sequence containing any number of integers.
    dependencies: tuple[int, ...] = ()
    blocked_reason: str | None = None

    def __post_init__(self) -> None:
        # Python calls this after the dataclass initializer has assigned the fields.
        require_integer("Task ID", self.id, 1)
        require_text("Title", self.title)
        require_text("Domain", self.domain)
        require_text("Context", self.context)
        require_integer("Estimated minutes", self.estimated_minutes, 1)
        require_integer("Importance", self.importance, 0, 5)
        require_integer("Cycle relevance", self.cycle_relevance, 0, 5)
        require_integer("Rhythm target", self.rhythm_target, 0)
        require_integer("Cycle completions", self.completions_in_cycle, 0)
        require_integer("Switching cost", self.switching_cost, 0, 5)
        if not isinstance(self.energy_requirement, Energy):
            raise ValueError("Energy requirement must be an Energy enum")
        if not isinstance(self.status, TaskStatus):
            raise ValueError("Status must be a TaskStatus enum")
        if not isinstance(self.project, str):
            raise ValueError("Project must be text")
        if self.blocked_reason is not None:
            require_text("Blocking reason", self.blocked_reason)
        for dependency in self.dependencies:
            require_integer("Dependency ID", dependency, 1)
            if dependency == self.id:
                raise ValueError("A task cannot depend on itself")

    @property
    def rhythm_deficit(self) -> int:
        # A property is read like a field: task.rhythm_deficit, without parentheses.
        return max(0, self.rhythm_target - self.completions_in_cycle)


# frozen=True prevents reassignment, so a feedback snapshot cannot change later.
@dataclass(frozen=True)
class UserState:
    available_minutes: int = 45
    energy: Energy = Energy.MEDIUM
    context: str = "desk"

    def __post_init__(self) -> None:
        require_integer("Available minutes", self.available_minutes, 0)
        require_text("Context", self.context)
        if not isinstance(self.energy, Energy):
            raise ValueError("User energy must be an Energy enum")


@dataclass(frozen=True)
class ScoreContribution:
    name: str
    value: int
    detail: str

    def __post_init__(self) -> None:
        require_text("Contribution name", self.name)
        require_text("Contribution detail", self.detail)
        if type(self.value) is not int:
            raise ValueError("Score contributions must be integers")


@dataclass(frozen=True)
class Recommendation:
    task_id: int
    title: str
    slice_minutes: int
    user_state: UserState
    contributions: tuple[ScoreContribution, ...]
    # The pure scheduler leaves id at 0; the application assigns a history ID.
    id: int = 0

    def __post_init__(self) -> None:
        require_integer("Recommendation ID", self.id, 0)
        require_integer("Recommended task ID", self.task_id, 1)
        require_integer("Slice minutes", self.slice_minutes, 1)
        require_text("Recommendation title", self.title)
        if not isinstance(self.user_state, UserState):
            raise ValueError("Recommendation must retain a UserState snapshot")
        if not self.contributions or any(not isinstance(part, ScoreContribution) for part in self.contributions):
            raise ValueError("Recommendation must contain score contributions")

    @property
    def total_score(self) -> int:
        # The expression inside sum is a generator: it yields each value in turn.
        return sum(part.value for part in self.contributions)


@dataclass(frozen=True)
class OverrideEvent:
    recommendation: Recommendation
    reason: OverrideReason
    occurred_at: datetime
    alternative_task_id: int | None = None
    note: str = ""

    def __post_init__(self) -> None:
        require_timestamp(self.occurred_at)
        if not isinstance(self.reason, OverrideReason):
            raise ValueError("Override reason must be an OverrideReason enum")
        if self.alternative_task_id is not None:
            require_integer("Alternative task ID", self.alternative_task_id, 1)
        if not isinstance(self.note, str):
            raise ValueError("Override note must be text")


@dataclass(frozen=True)
class TaskEvent:
    """Preserve lifecycle feedback separately from recommendation overrides."""

    task_id: int
    previous_status: TaskStatus
    new_status: TaskStatus
    occurred_at: datetime
    reason: str = ""

    def __post_init__(self) -> None:
        require_timestamp(self.occurred_at)
        require_integer("Event task ID", self.task_id, 1)
        if not isinstance(self.previous_status, TaskStatus) or not isinstance(self.new_status, TaskStatus):
            raise ValueError("Lifecycle events must use TaskStatus enums")
        if not isinstance(self.reason, str):
            raise ValueError("Event reason must be text")
