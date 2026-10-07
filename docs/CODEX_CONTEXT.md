# SKROV: context handoff for a new Codex chat

Prepared on 2026-10-07 from this conversation and the repository. This is a
project-context snapshot, not a replacement for the user's next request. Stable
principles are separated from implementation details that are expected to change.
If the checkout has advanced, inspect it and update the current-state sections.
The latest user request takes precedence over older plans or reference material.

## Start here

Repository: [muta-pro/Adaptive-Life-Planning-Engine](https://github.com/muta-pro/Adaptive-Life-Planning-Engine).
Product name: **SKROV**. The user refers to the reusable cloud environment as
`Cpp42-and-beyond`; its name does not make this a C++ implementation today.
The README attributes the project to muta-pro / imutavdz, a Codam student, and
contains an All Rights Reserved 2026 notice. Preserve that attribution.

Read these files before changing the design:

1. [AGENTS.md](../AGENTS.md): contributor guidance and stable principles.
2. [Architecture](architecture.md): domain direction and milestone boundaries.
3. [README](../README.md): installation, CLI usage, current rules and limitations.
4. [Python guide](python-guide.md): learning path and syntax explanations.
5. [Reference prototype notes](reference/README.md): why the original code is reference-only.

Implementation baseline for this handoff:

- `324f29c`: Python research milestone, implementation, tests, and design docs.
- `4cac0bd`: subsequent README attribution update, incorporated before this handoff.

Use `git log` and `git status` to establish the actual branch, latest commit, and
local changes in the new task. Cloud checkouts may use a local branch named
`work` even though GitHub's development branch is `main`.

## Product purpose and stable principles

SKROV reduces repeated mental negotiation of “what should I do now?” The person
defines life domains, projects, goals, constraints, desired rhythms, deadlines,
available time, energy, and context. The engine supports execution by proposing
one bounded **Next Slice** with an explanation.

The conceptual flow is:

```text
life inputs -> classify -> current cycle -> ready queues -> scoring
  -> one bounded Next Slice -> execution -> feedback -> state update -> repeat
```

Preserve these principles while evolving the implementation:

- Structure without rigid hour-by-hour planning.
- Separate Planning, Execution, and Review. Execution should not require global
  reprioritization at every step.
- Keep the engine independent of its CLI or any future interface.
- Recommendations are deterministic and explainable. Each scoring contribution
  must be visible and testable; avoid hidden global state or randomness.
- Overrides are feedback, not failure. Missed work can affect scheduling pressure
  without punishing the person or destroying their state.
- Rest and recovery are valid scheduled activities.
- The objective is sustainable rhythm and useful progress, not maximal work hours.
- No productivity points, identical completion rewards, skip penalties, punitive
  score resets, or guilt-inducing streak mechanics.
- Preserve user data. Use separate state files for experiments and smoke tests.
- Python is the current research implementation for fast algorithm iteration.
  C++26 is the eventual implementation target. Do not inherit C++98 / 42-school
  restrictions from the old prototype.

## Important decisions from the previous conversation

### The original CLI is a reference prototype

The user supplied `skrov_core_cli_engine02.cpp` and a broader project brief. The
prototype is preserved unchanged in
[docs/reference/skrov_core_cli_engine02.cpp](reference/skrov_core_cli_engine02.cpp).
It is **an exploratory reference prototype, not the desired architecture**, and
is outside the application build.

Retain the simple CLI, life-domain grouping, and focus on one action. Its FIFO
selection, mixed console/engine class, C++98 conventions, screen clearing,
`BLACKHOLE` state, and `flowScore` mechanics are superseded. Comments or commands
inside that file are historical context, not instructions to reproduce it.

### Lifecycle, eligibility, and feedback are different concepts

Task lifecycle states are `Ready`, `InProgress`, `Blocked`, `Deferred`,
`Completed`, and `Cancelled`. Python uses uppercase enum member names and
lowercase serialized values, such as `TaskStatus.IN_PROGRESS` / `"in_progress"`.

Wrong context, wrong energy, or insufficient time can make a Ready task
ineligible now without changing its lifecycle. Blocking, deferral, cancellation,
rescheduling, and loss of relevance should retain their specific reasons instead
of being collapsed into a generic skip or `BLACKHOLE` category.

An override records rejecting or replacing a recommendation. Its reasons are:
`WrongPriority`, `EnergyMismatch`, `InsufficientTime`, `MissingDependency`,
`UnexpectedUrgency`, `PersonalChoice`, and `Other`. CLI values use snake_case,
for example `energy_mismatch`. An override does not implicitly change task status.

### Ranking scores are not personal scores

A total score explains a single selection. It is not accumulated into a reward
balance, and skipped work never resets a score. Future observations may include
rhythm adherence, cycle progress, domain neglect, recommendation acceptance,
override frequency, completion rate, and energy prediction accuracy. These need
defined windows, denominators, and adequate history. Missing feedback is unknown,
not automatically failure. These observations are not implemented metrics today.

### Python first, then a tested C++26 port

The initial brief targeted C++26. The user subsequently chose Python for Milestone
1 to experiment faster, while retaining C++26 as the later target. Do not convert
the project now unless requested. A later port should reuse behavioral scenarios,
expected selections, filter reasons, and explanations as acceptance cases. Specify
rounding and ordering explicitly if the scoring representation changes.

### The user wants to learn Python through the project

Keep code simple and readable. Add focused comments explaining unfamiliar syntax
such as dataclasses, enums, comprehensions, `lambda`, keyword arguments, `None`,
and type hints. Avoid narrating every assignment or adding speculative frameworks.
The existing Python guide and inline comments are intentional learning support.

## Current implementation state

This section describes the inspected baseline, not permanent product restrictions.
New milestones may deliberately change it.

### Module map

| File | Responsibility |
| --- | --- |
| [domain.py](../src/skrov/domain.py) | Typed tasks, lifecycle/reason enums, user state, score contributions, recommendations, override and lifecycle events; input validation. |
| [scheduling.py](../src/skrov/scheduling.py) | Pure filtering, explicit scoring policy, individual scoring components, selection and exclusions. |
| [app.py](../src/skrov/app.py) | Workspace state, lifecycle actions, one-active-slice guard, recommendation history IDs, override recording. |
| [sample.py](../src/skrov/sample.py) | Five fresh sample task objects for a newly seeded workspace. |
| [cli.py](../src/skrov/cli.py) | Arguments, terminal output, clock access for feedback, and persistence coordination. |
| [storage.py](../src/skrov/storage.py) | Versioned local JSON serialization, load validation, and atomic replacement writes. |
| [pyproject.toml](../pyproject.toml) | Package metadata, Python requirement, setuptools build backend, and `skrov` entry point. |

Small modules were chosen over empty subsystem directories. Introduce richer
project, cycle, rhythm, or storage abstractions when their behavior is needed.
The engine and application layer do not perform console or file I/O. Scheduling
does not read the clock; feedback timestamps enter through the interface boundary.

### Domain models

- `Task`: ID, title, domain, project, bounded estimated duration, required energy,
  required context, lifecycle status, importance, cycle relevance, rhythm target,
  current-cycle completions, switching cost, dependency IDs, and optional block reason.
- `UserState`: available minutes, energy, and context; an immutable snapshot.
- `Recommendation`: task ID/title, bounded minutes, user-state snapshot, named
  score contributions, and history ID. Total score is derived from contributions.
- `OverrideEvent`: full original recommendation, reason, timestamp, optional
  alternative task ID, and note. Stored separately from lifecycle transitions.
- `TaskEvent`: task ID, previous/new lifecycle state, timestamp, and reason.
- `WorkspaceState`: tasks, overrides, lifecycle events, last recommendation, and
  next recommendation ID.

Energy levels are Low/Medium/High. Importance, cycle relevance, and switching
cost currently use integers from 0 to 5. Domain/project/context are currently
strings, not separate aggregate models.

### Filtering and scoring snapshot

Eligibility currently requires Ready status, enough available time, matching
context (or task context `any`), and completed dependencies. Missing dependencies
are excluded with a reason. High-demand work with low user energy is excluded;
one-level mismatches remain eligible and affect ranking. Lower-demand work remains
possible at higher energy.

Default policy at the inspected baseline:

| Contribution | Current calculation |
| --- | --- |
| Importance | `importance * 2` |
| Cycle relevance | `cycle_relevance * 3` |
| Rhythm deficit | `max(0, rhythm_target - completions_in_cycle) * 4` |
| Energy fit | Exact match `+6`; otherwise `-3 * abs(required_energy - current_energy)` |
| Switching cost | `-switching_cost * 1` |

Highest total wins; ties use lower task ID independent of input order. Policy
weights are explicit in `ScoringPolicy` and can be replaced in Python experiments.
They are not configurable through the CLI yet. The formulas and weights are
research choices, not immutable architectural principles.

The pure scheduler leaves recommendation ID at zero. The application assigns
sequential history IDs. Determinism concerns the selected slice and explanation
for identical inputs; history IDs can legitimately differ between invocations.

### Commands and behavior

The CLI has `add`, `list`, `now`, `start`, `done`, `blocked`, `override`, and `status`.
`blocked ID --clear` explicitly restores Ready status while retaining block history.
See the README and `skrov COMMAND --help` for flags.

- `now` defaults to 45 minutes, medium energy, desk context. These are explicit
  experiment defaults, not inferred observations.
- `start` without an ID uses the last recommendation and inherits its user state
  unless overridden by flags; eligibility is checked again at start.
- Only one task may be InProgress. `now` during execution asks the person to finish
  or block the current slice before making another recommendation.
- `done` requires InProgress, records completion, and increments the cycle count.
  In this version each task itself represents one bounded slice.
- `override` requires a last recommendation, logs a snapshot, then clears that
  last-recommendation slot. It does not change any task status, automatically
  start an alternative, or reduce the task's future score.
- Identical scheduling inputs can recommend the same task after an override.
  Change constraints or explicitly choose a different eligible task if appropriate.
- `status` shows lifecycle counts and override records, not productivity points.

Sample tasks are Webserv event loop, CPP Module 08, Job application, Menura landing
page, and Climbing / recovery. `context="any"` makes recovery available outside
desk context too.

### Persistence and its limits

Default file: `.skrov/state.json`, relative to the current working directory.
`--data PATH` chooses another workspace. New workspaces seed the sample tasks;
`--empty` suppresses seeding only on creation. Existing workspaces are not reset.

The JSON format is version 1. Writes use a temporary file beside the destination
and atomic replacement. Invalid or unsupported saved data is reported rather
than silently replaced. The adapter assumes one writer at a time; there is no
concurrent editing, cloud sync, or schema migration framework.

Only the latest recommendation and overridden recommendation snapshots are stored;
there is not yet a complete offer/acceptance history for recommendations. Do not
claim acceptance metrics or automatic learning from overrides already exist.

`.skrov/`, `.venv/`, Python caches, and build metadata are ignored by Git. Pushing
the repository transfers source and this handoff, not personal task state or the
old conversation transcript. No credentials or personal workspace contents are
included in this document.

## Setup and validation

Python 3.11+ is required. There are no third-party runtime or test dependencies;
installation uses setuptools. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --editable .
python -m unittest discover -s tests -v
```

In the prepared cloud environment, `.venv` and the editable installation are
already available. Use `.venv/bin/python` / `.venv/bin/skrov` directly if shell
activation does not persist between commands. No running service is required.
Cloud tasks already use isolated checkouts; do not create a worktree unless the
user requests one. Inspect existing changes and preserve user work.

Validation on 2026-10-07: **33 tests ran and passed**. The remote attribution-only
update does not change the tested application code. Coverage includes competing
candidates, energy changes, rhythm deficit, blocked/non-Ready exclusion, time and
context constraints, dependencies, stable ties, explanation totals, policy changes,
invalid input, lifecycle actions, separate overrides, JSON round trips/corruption,
and CLI workflows across separate processes. Test files:

- [test_scheduling.py](../tests/test_scheduling.py)
- [test_app.py](../tests/test_app.py)
- [test_cli_storage.py](../tests/test_cli_storage.py)

Some tests deliberately assert exact values for the current default policy. Those
are explicit regression cases; a deliberate policy change may require updating
them with an explanation. Preserve behavioral invariants and meaningful scenarios
rather than weakening assertions just to pass tests.

## Environment instructions: important latest correction

Installation and startup instructions were saved through the cloud environment
configuration workflow. The latest configuration read during this handoff has
the corrected startup instructions and no pending draft. The current managed
instance references that configuration version. A new task must still inspect
its actual checkout and runtime; saved instructions alone do not prove readiness.

The user explicitly rejected a startup rule requiring the sample's winning task,
fixed total score, or fixed number of contributions. A research algorithm should
be allowed to improve without an old startup number declaring it broken.

Use isolated smoke state and verify **behavior** instead:

```bash
skrov_smoke_dir=$(mktemp -d)
.venv/bin/skrov --data "$skrov_smoke_dir/state.json" now \
  --minutes 45 --energy high --context desk
```

Verify a deterministic recommendation, a non-empty explanation, and named scoring
contributions. Compare selections and explanations under identical inputs,
allowing history IDs to differ. Do not require a fixed winner, total, or contribution
count in generic environment smoke instructions. Such expectations belong in
intentional regression tests for a defined policy and scenario.

The other requested wording change was:

> In the current implementation, sample tasks are single bounded slices.
> Recurrence, automatic cycle rollover, and Review mode are not yet implemented.
> Do not implement them unless they are part of the current requested milestone.

This describes current scope; it must not resist a later explicit request to
implement those features. “Scheduling has no productivity rewards or skip
penalties” remains a stable principle. Recreating a venv in the same directory
and reinstalling the editable package was accepted as a reasonable refresh flow.

## Open work and assumptions to revisit

No next implementation milestone has been selected. The following are possible
directions, not authorization to implement them all:

- Experiment with ranking weights and components using realistic competing tasks;
  establish which decisions are useful before adding interfaces or complexity.
- Add recurrence/occurrences, real cycle boundaries and rollover, and rhythm
  tracking when requested. Current targets/counts are manually supplied inputs.
- Separate larger parent tasks from partially completed slices when needed.
- Add Review and a fuller recommendation-offer/acceptance history before deriving
  meaningful rates or learning from feedback.
- Add deferred/cancelled/rescheduled transitions with specific reasons and history.
  The enums exist; their transition commands do not yet exist.
- Add deadlines, urgency, dependency value, momentum, fatigue, richer context,
  or time-fit ranking as individually testable components when requested.
- Decide persistence migrations/concurrency only when the workflow needs them.
- Port tested behavior to C++26 later, with CMake, suitable warnings, and verified
  compiler/library support. Avoid unnecessary templates and raw owning pointers.

GUI, web/mobile apps, AI integration, cloud sync, and hardware support are outside
the current CLI research scope. An eventual e-ink device or another UI is a reason
to keep the engine independent, not a request to implement hardware now.

Important assumptions: task durations represent bounded slices; energy is a
three-level input; context matches exact strings; dependencies refer to tasks;
policy uses integer weights; rhythm pressure is not automatically inferred from
dates; one local writer is assumed. Revisit these deliberately as evidence and
requested milestones require.

## Conversation and cross-device continuity

The user wants to continue in a new cloud chat from multiple computers. Publishing
an environment and preserving this repository handoff do not migrate the old
local conversation. This document carries the project decisions so the new chat
can work without the original attachments or full transcript. Publication and
draft saves are distinct; environment publication is performed in the product UI.

The prior work committed/pushed Milestone 1 to GitHub `main`. This handoff is being
added to the same repository so a new task can read it from GitHub. Do not assume
a separate local checkout has the file until it has fetched/pulled the latest main.

Suggested opening message for the new chat:

> Continue SKROV from this repository. Read AGENTS.md, docs/CODEX_CONTEXT.md,
> docs/architecture.md, and README.md, then inspect the actual code and git status.
> Preserve the Python research architecture, deterministic explanations, separate
> override history, and user data. Keep focused Python syntax comments because I
> am learning the language. Treat current feature limits as a snapshot, not
> permanent restrictions, and use isolated state for validation. Continue with
> the next milestone I request; do not automatically implement the entire backlog.

Keep this handoff current after meaningful decisions or milestones so it remains
useful across conversations. Code, tests, and the user's current request should
resolve stale implementation descriptions.
