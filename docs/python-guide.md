# Reading SKROV as a Python beginner

The implementation uses the standard library and small modules. Start with
[`domain.py`](../src/skrov/domain.py), then [`scheduling.py`](../src/skrov/scheduling.py).
These describe the data and decisions without files or terminal interaction.
Next read [`sample.py`](../src/skrov/sample.py), [`app.py`](../src/skrov/app.py),
[`cli.py`](../src/skrov/cli.py), and finally [`storage.py`](../src/skrov/storage.py).
Syntax comments appear where a new language feature is introduced.

## Basic syntax

```python
def rhythm_deficit(target: int, completed: int) -> int:
    return max(0, target - completed)
```

`def` defines a function. The colon starts its body; indentation defines the
block instead of C++ braces. `target: int` and `-> int` are type hints for readers
and tools. They do not enforce types at runtime, so domain constructors also
validate input. Python does not require semicolons at the end of statements.

`None` means no value. `Task | None` means a value can be a Task or absent.
Check `value is None` explicitly when zero or an empty collection could also be
meaningful. `True` and `False` are Boolean values; `and`, `or`, and `not` are
Boolean operators.

## Domain types

`Enum` provides named alternatives such as `TaskStatus.READY`. The uppercase
member name is a Python naming convention; its stored value is `"ready"`.
`Energy` uses `IntEnum`, so its levels can also be compared or subtracted.

`@dataclass` asks Python to generate an initializer and value comparison from
annotated fields. `Task(...)` constructs an instance, much like constructing a
C++ struct with data. Its methods receive `self`, the instance being operated on.
`__post_init__` runs after field assignment and checks invariants.

`@dataclass(frozen=True)` prevents field reassignment. User-state snapshots and
recommendation explanations are immutable, so later actions do not rewrite old
feedback. Task lifecycle state is intentionally mutable.

`@property` exposes a calculation as an attribute:
`task.rhythm_deficit` computes the current deficit each time it is read.

## Collections and iteration

`list[Task]` is a mutable list of tasks. `tuple[ScoreContribution, ...]` is an
immutable sequence of contributions. A dictionary maps keys to values, like a
lookup table. `{task.id: task for task in tasks}` builds an ID-to-task dictionary.

```python
values = [part.value for part in recommendation.contributions]
total = sum(part.value for part in recommendation.contributions)
```

The first expression is a list comprehension. The second uses a generator to
produce values one at a time instead of first constructing a list.

```python
ranked.sort(key=lambda item: (-item.total_score, item.task_id))
```

`lambda` defines a small anonymous function. Here it returns a tuple used as the
sort key. Python compares tuple elements in order: negative score puts the
highest score first, then task ID settles a tie. The engine does not rely on
the original order of tasks.

## Keyword arguments and files

`Task(id=1, title="Recovery", domain="Health")` uses named arguments.
`Task(**fields)` expands a dictionary into named arguments.
`def example(**changes)` collects named arguments into a dictionary instead.
`dataclasses.replace(value, energy=Energy.LOW)` copies a dataclass while changing
one field; `dataclasses.asdict(value)` recursively turns it into dictionaries.

`with` manages a resource and closes it even if an error occurs. `try` / `except`
handle errors; `raise ValueError(...)` reports invalid input. A name beginning
with `_` marks an internal helper by convention.

`f"{part.value:+d} {part.name}"` is an f-string: braces insert values. The `+d`
format prints an integer with a sign, which makes score explanations readable.

## Try the engine without the CLI

After installing the package, start `python` from the activated environment and
enter:

```python
from dataclasses import replace
from skrov.domain import Energy, UserState
from skrov.sample import sample_tasks
from skrov.scheduling import ScoringPolicy, recommend

tasks = sample_tasks()
user = UserState(available_minutes=30, energy=Energy.MEDIUM, context="desk")
policy = ScoringPolicy()
decision = recommend(tasks, user, policy)
print(decision.recommendation)

# Increase rhythm pressure without modifying the default policy object.
rhythm_experiment = replace(policy, rhythm_weight=8)
print(recommend(tasks, user, rhythm_experiment).recommendation)
```

There is no file write here. Experiment with one input or weight at a time and
observe how the named contributions change. Read
[`test_scheduling.py`](../tests/test_scheduling.py) to see repeatable examples.
`unittest.TestCase` groups tests; `self.assertEqual(actual, expected)` checks a
result, and `setUp` supplies fresh inputs before each test.
