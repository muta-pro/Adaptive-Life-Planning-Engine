# SKROV design direction

SKROV helps a person choose what to do now from their life domains, projects,
goals, constraints, desired rhythms, available time, and current energy/context.
The objective is sustainable rhythm and useful progress. The person supplies
direction; the engine recommends one bounded Next Slice with an explanation.
Rest and recovery are valid activities.

Start with a Python research implementation to make scheduling experiments and
changes fast. C++26 remains the later implementation target. The research
implementation is now present in Python; a subsequent port should preserve the
tested decisions and explanations. The C++26 implementation remains future work.

The attached CLI code is preserved at
[`reference/skrov_core_cli_engine02.cpp`](reference/skrov_core_cli_engine02.cpp)
as an **exploratory reference prototype, not the desired architecture**. This
document records the user's explicit corrections and draws design context from
the accompanying brief. The Python milestone implements the core boundaries and
commands described below; recurrence and the broader product remain future work.

## What carries forward

Retain the lightweight CLI, domain grouping, and single-action focus. Replace
the monolithic engine that performs console I/O, FIFO selection, and state
mutation. Terminal colours and playful wording belong to the CLI adapter.
Screen clearing and the prototype's day-burn display are not engine behavior.

Remove `BLACKHOLE` from domain modeling. Remove `flowScore`, uniform `+15`
completion rewards, and resets on skips. These hide scheduling information and
attach penalties to ordinary changes in a person's circumstances.

## Lifecycle, eligibility, and events

Use typed lifecycle states. The C++ notation below names the domain concepts;
the Python research implementation should use enums with the same meanings:

```cpp
enum class TaskStatus {
    Ready,
    InProgress,
    Blocked,
    Deferred,
    Completed,
    Cancelled
};
```

These states describe the task's lifecycle. Eligibility answers a separate
question: can a Ready task supply a suitable slice under the current constraints?
Preserve filter reasons so the engine can explain why a task was excluded.

| Feedback | Domain meaning |
| --- | --- |
| Blocked | A prerequisite prevents progress; retain the dependency or blocking reason. |
| Deferred | Intentionally postponed; retain the reason and any reconsideration time. |
| Wrong context | Current eligibility mismatch; retain the required and observed context. |
| Wrong energy | Current eligibility mismatch; retain required and observed energy. |
| Insufficient time | The bounded slice does not fit the available time. |
| No longer relevant | A cancellation reason, with the prior task history retained. |
| Rescheduled | A scheduling event with old/new timing; it may accompany deferral. |
| Cancelled | A lifecycle transition with a reason, not completion. |
| Override | A recommendation was rejected or replaced; retain the decision and its reason. |

An override is its own event:

```cpp
enum class OverrideReason {
    WrongPriority,
    EnergyMismatch,
    InsufficientTime,
    MissingDependency,
    UnexpectedUrgency,
    PersonalChoice,
    Other
};
```

An override event should retain the recommendation identifier, recommended
task/slice, reason, occurrence time, relevant user-state snapshot, and optional
chosen alternative or note. `Other` allows an explanatory note rather than
discarding unknown reasons. An override alone does not change the recommended
task's lifecycle. For example, `MissingDependency` can accompany a separate
blocking transition, but it does not silently imply one.

Completion feedback must distinguish finishing a bounded slice from finishing
the task. Recurring work will need occurrence history so completing one instance
does not erase its rhythm requirements. Add that model when recurrence is built.

## Engine boundaries

```text
src/skrov/
  domain.py      Task, TaskStatus, UserState, Recommendation, feedback types
  scheduling.py  candidate filtering, scoring functions/policy, deterministic selection
  app.py         command actions and lifecycle/feedback coordination
  sample.py      five bounded example slices
  cli.py         argument parsing and presentation
  storage.py     small JSON persistence adapter
tests/          domain, filtering, ranking, explanation, and CLI smoke tests
```

These boundaries apply to the Python package and the later C++ engine. Add
project, cycle, rhythm tracking, and storage components as their behavior is
implemented. Avoid empty subsystems or a persistence framework in the first
milestone. The JSON adapter persists task state, lifecycle events, and separate
override snapshots. It supports sequential local commands, not concurrent writers.

The scheduling pipeline is:

```text
Tasks + UserState + explicit scheduling policy/time
  -> eligibility filtering with reasons
  -> individually testable scoring contributions
  -> deterministic selection with stable task-ID tie-breaking
  -> one bounded Next Slice and its explanation, or an explicit no-candidate result
```

Supply time explicitly rather than reading the clock inside scoring. Stable
ranking must not depend on container iteration order or hidden global state.
Each explanation contains named contributions and the total that selected the
candidate. Ranking scores belong to that decision; do not accumulate them into
a personal score.

Keep Planning, Execution, and Review as separate modes. Planning changes
direction and constraints. Execution uses the current cycle and records
feedback without asking for global reprioritization. Review interprets history
and supports deliberate adjustments.

## First implementation milestone

Use Python first, with an isolated virtual environment, a small package, typed
models/enums, and an easy test command. Standard-library tools are sufficient
for the initial engine and tests; introduce dependencies only when needed.

1. Establish a small engine package, a CLI entry point, and tests.
2. Model task identity, title, domain/project, bounded duration, energy/context,
   status, and the fields used by the initial scoring policy. Model UserState
   with available minutes, energy, and context. More advanced fields can follow.
3. Filter Ready candidates by current constraints and dependency readiness.
   For this milestone, sample tasks represent bounded slices; do not reject an
   entire future project merely because its total duration exceeds this session.
4. Implement five named scoring components: importance, cycle relevance, rhythm
   deficit, energy fit, and switching cost. Available time is a hard eligibility
   constraint. Make weights explicit policy and show each contribution.
5. Implement `skrov now` over a realistic sample dataset: Webserv event loop,
   CPP Module 08, job application, Menura landing page, climbing/recovery.
   Print the chosen slice and score explanation, or why no candidate fits.
6. Test competing candidates, exclusions, stable ties, repeated decisions with
   identical inputs, the explanation total, and the no-candidate outcome.

The Python CLI exposes `add`, `list`, `now`, `start`, `done`, `blocked`, `override`,
and `status`; `blocked --clear` explicitly restores a blocked task to Ready while
retaining its history. Only one slice can be active, and requesting another
recommendation during execution is rejected. Overrides retain the full original
decision and do not automatically change task status or select an alternative.

Rhythm deficit uses a supplied current-cycle target and completion count.
Completing one bounded sample task increments its count and completes that task;
recurring activities and partial completion of larger tasks are not implemented.
Review, automatic cycle tracking, and broader scoring terms remain future work.
See [the README](../README.md) for commands and policy calculations, and
[the Python guide](python-guide.md) for the learning path.

## Later C++26 implementation

After the Python milestone demonstrates useful decisions, implement the same
domain model and deterministic behavior in C++26. Carry over scenario inputs,
expected selections, exclusion reasons, and score explanations as acceptance
cases. Define rounding and ordering explicitly so language differences do not
change recommendations. Treat this as a tested port, not an automatic conversion.

Use CMake, useful GCC/Clang warnings (`-Wall -Wextra -Wpedantic`), and an easy test
command. Verify compiler and standard-library support; report unsupported
features rather than silently lowering the language target. Prefer
`std::optional`, `std::chrono`, algorithms/ranges, RAII, and value semantics.
Use `std::expected` where available and useful; avoid unnecessary templates.

## Future observations

Use history to understand scheduling quality and adapt deliberately. Candidate
observations include:

| Observation | What must be preserved |
| --- | --- |
| Rhythm adherence | Desired frequency and actual occurrences over a defined window. |
| Cycle progress | Cycle goals, relevant work, and completion/slice progress. |
| Domain neglect | Domain targets and elapsed time since relevant activity. |
| Recommendation acceptance | Recommendations offered and subsequent decisions. |
| Override frequency | Override events, reasons, and recommendations offered. |
| Completion rate | A defined denominator and separate slice/task outcomes. |
| Energy prediction accuracy | Predicted energy fit and actual user feedback. |

Keep these separate observations with explicit windows and denominators.
Missing feedback is unknown, not automatic failure. They support explanations
and review rather than a composite productivity score. Any future adaptation
must use an explicit, reproducible policy instead of hidden or random changes.
