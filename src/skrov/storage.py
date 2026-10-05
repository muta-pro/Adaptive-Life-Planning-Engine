"""A small JSON adapter, preserving lifecycle events and override snapshots."""

from dataclasses import asdict
from datetime import datetime
import json
import os
from pathlib import Path
import tempfile

from skrov.app import WorkspaceState
from skrov.domain import Energy, OverrideEvent, OverrideReason, Recommendation, ScoreContribution, Task, TaskEvent, TaskStatus, UserState


def _recommendation_from_dict(data: dict) -> Recommendation:
    # ** expands a dictionary into named arguments, e.g. UserState(energy=..., ...).
    user_data = dict(data["user_state"])
    user_data["energy"] = Energy(user_data["energy"])
    return Recommendation(
        task_id=data["task_id"], title=data["title"], slice_minutes=data["slice_minutes"],
        user_state=UserState(**user_data), id=data["id"],
        contributions=tuple(ScoreContribution(**part) for part in data["contributions"]),
    )


def load_state(path: Path) -> WorkspaceState | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["format_version"] != 1:
            raise ValueError("Unsupported state format version")
        tasks = []
        for saved in data["tasks"]:
            fields = dict(saved)
            fields["status"] = TaskStatus(fields["status"])
            fields["energy_requirement"] = Energy(fields["energy_requirement"])
            fields["dependencies"] = tuple(fields["dependencies"])
            tasks.append(Task(**fields))
        overrides = [
            OverrideEvent(
                _recommendation_from_dict(saved["recommendation"]),
                OverrideReason(saved["reason"]), datetime.fromisoformat(saved["occurred_at"]),
                saved["alternative_task_id"], saved["note"],
            )
            for saved in data["overrides"]
        ]
        events = [
            TaskEvent(saved["task_id"], TaskStatus(saved["previous_status"]),
                      TaskStatus(saved["new_status"]), datetime.fromisoformat(saved["occurred_at"]),
                      saved["reason"])
            for saved in data["task_events"]
        ]
        last = data["last_recommendation"]
        state = WorkspaceState(tasks, overrides, events,
                               _recommendation_from_dict(last) if last is not None else None,
                               data["next_recommendation_id"])
        if len({task.id for task in tasks}) != len(tasks):
            raise ValueError("Duplicate task IDs")
        if sum(task.status == TaskStatus.IN_PROGRESS for task in tasks) > 1:
            raise ValueError("Multiple active tasks")
        if type(state.next_recommendation_id) is not int or state.next_recommendation_id < 1:
            raise ValueError("Invalid next recommendation ID")
        return state
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        # 'from error' preserves the original cause for debugging if needed.
        raise ValueError(f"Cannot load {path}: {error}. Existing data was not replaced.") from error


def _encode_extra(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Cannot encode {type(value).__name__} as JSON")


def save_state(path: Path, state: WorkspaceState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # asdict recursively turns dataclasses into dictionaries for JSON serialization.
    data = {"format_version": 1, **asdict(state)}
    temporary_path = None
    try:
        # 'with' closes the file automatically, including when an exception occurs.
        # Write beside the real file, then replace it only after a complete write.
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".skrov-", suffix=".tmp", delete=False) as stream:
            temporary_path = Path(stream.name)
            json.dump(data, stream, indent=2, default=_encode_extra)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
