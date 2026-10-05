"""Argument parsing and presentation only; decisions live in the engine."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

from skrov.app import SkrovApplication, WorkspaceState
from skrov.domain import Energy, OverrideReason, Recommendation, Task, TaskStatus, UserState
from skrov.sample import sample_tasks
from skrov.storage import load_state, save_state


def _energy(text: str) -> Energy:
    try:
        # Enum lookup by name uses square brackets, e.g. Energy["HIGH"].
        return Energy[text.upper()]
    except KeyError as error:
        raise argparse.ArgumentTypeError("energy must be low, medium, or high") from error


def _text(text: str) -> str:
    if not text.strip():
        raise argparse.ArgumentTypeError("value must contain text")
    return text.strip()


def _user_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--minutes", type=int, help="available minutes (default: 45)")
    parser.add_argument("--energy", type=_energy, help="low, medium, or high (default: medium)")
    parser.add_argument("--context", type=_text, help="current context (default: desk)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skrov", description="Choose one bounded next slice.")
    parser.add_argument("--data", type=Path, default=Path(".skrov/state.json"),
                        help="workspace JSON file (default: .skrov/state.json)")
    parser.add_argument("--empty", action="store_true", help="omit sample tasks when creating a new workspace")
    # Subparsers give each command its own arguments and help screen.
    commands = parser.add_subparsers(dest="command", required=True)

    add = commands.add_parser("add", help="add one bounded task/slice")
    add.add_argument("title", type=_text)
    add.add_argument("--domain", type=_text, required=True)
    add.add_argument("--project", default="")
    add.add_argument("--minutes", type=int, default=25)
    add.add_argument("--energy", type=_energy, default=Energy.MEDIUM)
    add.add_argument("--context", type=_text, default="desk", help="required context, or any")
    add.add_argument("--importance", type=int, default=3, help="0 through 5")
    add.add_argument("--cycle-relevance", type=int, default=3, help="0 through 5")
    add.add_argument("--rhythm-target", type=int, default=1)
    add.add_argument("--cycle-completions", type=int, default=0)
    add.add_argument("--switching-cost", type=int, default=0, help="0 through 5")
    add.add_argument("--depends-on", type=int, nargs="*", default=[], metavar="ID")

    commands.add_parser("list", help="list all tasks and their lifecycle states")
    now = commands.add_parser("now", help="recommend the highest-scoring eligible Ready slice")
    _user_arguments(now)
    start = commands.add_parser("start", help="start an ID or the latest recommendation")
    start.add_argument("task_id", nargs="?", type=int)
    _user_arguments(start)
    done = commands.add_parser("done", help="complete an ID or the active slice")
    done.add_argument("task_id", nargs="?", type=int)
    blocked = commands.add_parser("blocked", help="record a block, or explicitly clear one")
    blocked.add_argument("task_id", nargs="?", type=int)
    choice = blocked.add_mutually_exclusive_group(required=True)
    choice.add_argument("--reason", type=_text)
    choice.add_argument("--clear", action="store_true")
    override = commands.add_parser("override", help="log feedback on the latest recommendation")
    override.add_argument("reason", choices=[reason.value for reason in OverrideReason])
    override.add_argument("--alternative", type=int, metavar="ID")
    override.add_argument("--note", default="")
    commands.add_parser("status", help="show lifecycle counts and override history")
    return parser


def _user_state(arguments: argparse.Namespace, previous: UserState | None = None) -> UserState:
    baseline = previous if previous is not None else UserState()
    # Use 'is not None', rather than truthiness, because zero available minutes is valid.
    return UserState(
        arguments.minutes if arguments.minutes is not None else baseline.available_minutes,
        arguments.energy if arguments.energy is not None else baseline.energy,
        arguments.context if arguments.context is not None else baseline.context,
    )


def print_recommendation(recommendation: Recommendation) -> None:
    # f-strings interpolate expressions inside braces; +d prints an integer's sign.
    print(f"Next Slice [{recommendation.task_id}]: {recommendation.title}")
    print(f"Duration: {recommendation.slice_minutes} minutes")
    print(f"Ranking score: {recommendation.total_score} (for this decision only)")
    print("Reasons:")
    for part in recommendation.contributions:
        print(f"  {part.value:+d} {part.name}: {part.detail}")
    print(f"Tie-break: lower task ID. Recommendation #{recommendation.id}.")


def _execute(arguments: argparse.Namespace, app: SkrovApplication) -> None:
    # Clock access is at the interface boundary; scheduling itself never reads it.
    occurred_at = datetime.now(timezone.utc)
    state = app.state
    command = arguments.command
    if command == "add":
        new_id = max((task.id for task in state.tasks), default=0) + 1
        task = Task(
            id=new_id, title=arguments.title, domain=arguments.domain,
            estimated_minutes=arguments.minutes, energy_requirement=arguments.energy,
            context=arguments.context, project=arguments.project, importance=arguments.importance,
            cycle_relevance=arguments.cycle_relevance, rhythm_target=arguments.rhythm_target,
            completions_in_cycle=arguments.cycle_completions, switching_cost=arguments.switching_cost,
            dependencies=tuple(arguments.depends_on),
        )
        app.add(task)
        print(f"Added [{task.id}] {task.title}")
    elif command == "list":
        if not state.tasks:
            print("No tasks. Use add to define a bounded slice.")
        for task in sorted(state.tasks, key=lambda item: item.id):
            print(f"[{task.id}] {task.title} | {task.status.value} | {task.domain} | "
                  f"{task.estimated_minutes} min | energy {task.energy_requirement.name.lower()} | "
                  f"context {task.context} | rhythm deficit {task.rhythm_deficit}")
            if task.blocked_reason:
                print(f"    Blocked: {task.blocked_reason}")
            if task.dependencies:
                print(f"    Dependencies: {', '.join(str(value) for value in task.dependencies)}")
    elif command == "now":
        decision = app.now(_user_state(arguments))
        if decision.recommendation is None:
            print("No eligible Ready slice fits the current state.")
        else:
            print_recommendation(decision.recommendation)
        if decision.exclusions:
            print("Excluded:")
            for exclusion in decision.exclusions:
                print(f"  [{exclusion.task_id}] {exclusion.title}: {'; '.join(exclusion.reasons)}")
    elif command == "start":
        previous = state.last_recommendation.user_state if state.last_recommendation else None
        task = app.start(arguments.task_id, _user_state(arguments, previous), occurred_at)
        print(f"Started [{task.id}] {task.title} ({task.estimated_minutes} minute slice)")
    elif command == "done":
        task = app.done(arguments.task_id, occurred_at)
        print(f"Completed slice [{task.id}] {task.title}")
    elif command == "blocked":
        if arguments.clear:
            if arguments.task_id is None:
                raise ValueError("Supply a task ID when clearing a block")
            task = app.unblock(arguments.task_id, occurred_at)
            print(f"Block cleared for [{task.id}] {task.title}; task is Ready")
        else:
            task = app.blocked(arguments.task_id, arguments.reason, occurred_at)
            print(f"Blocked [{task.id}] {task.title}: {task.blocked_reason}")
    elif command == "override":
        event = app.override(OverrideReason(arguments.reason), occurred_at,
                             arguments.alternative, arguments.note)
        print(f"Override logged for recommendation #{event.recommendation.id}: {event.reason.value}")
        print("Task lifecycle states are unchanged. Use start ID or request now with updated constraints.")
    elif command == "status":
        for status in TaskStatus:
            count = sum(task.status == status for task in state.tasks)
            print(f"{status.value}: {count}")
        active = app.active_task()
        if active:
            print(f"Active slice: [{active.id}] {active.title}")
        print(f"Override events: {len(state.overrides)}")
        for event in state.overrides:
            alternative = f"; alternative [{event.alternative_task_id}]" if event.alternative_task_id else ""
            note = f"; note: {event.note}" if event.note else ""
            print(f"  #{event.recommendation.id} [{event.recommendation.task_id}] "
                  f"{event.reason.value} at {event.occurred_at.isoformat()}{alternative}{note}")


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        state = load_state(arguments.data)
        if state is None:
            state = WorkspaceState(tasks=[] if arguments.empty else sample_tasks())
        app = SkrovApplication(state)
        _execute(arguments, app)
        save_state(arguments.data, state)
        return 0
    except (ValueError, OSError) as error:
        print(f"skrov: {error}", file=sys.stderr)
        return 1
