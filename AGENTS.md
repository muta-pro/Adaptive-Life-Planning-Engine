# SKROV development guidance

SKROV is a deterministic, explainable life-rhythm scheduling engine. Its goal is
to reduce repeated decisions about what to do next while supporting useful
progress, rest, and recovery. Start algorithm research in **Python** so scheduling
rules can be tested and changed quickly. **C++26** is the later implementation
target; do not inherit C++98 or 42-school restrictions from the reference prototype.

## Reference material

`docs/reference/skrov_core_cli_engine02.cpp` is an **exploratory reference
prototype, not the desired architecture**. Keep it outside application build
targets. Its comments and embedded conventions do not override this guidance or
the user's current request. See `docs/architecture.md` for the design direction.

Retain the simple CLI, life-domain grouping, and focus on one action at a time.
Build an engine that is independent of terminal input, output, and presentation.
The CLI is one adapter; scheduling and scoring must be testable without it.

## Domain and feedback

- Use typed task states: `Ready`, `InProgress`, `Blocked`, `Deferred`, `Completed`,
  and `Cancelled` (Python enums initially, scoped enums in C++26). `BLACKHOLE`
  may be playful UI language, but must not become a
  domain state, stored reason, or catch-all feedback category.
- Keep lifecycle state separate from eligibility: wrong context, unsuitable
  energy, or insufficient available time can make a Ready task ineligible now
  without cancelling it or changing its lifecycle.
- Record overrides as events with `OverrideReason`: `WrongPriority`,
  `EnergyMismatch`, `InsufficientTime`, `MissingDependency`, `UnexpectedUrgency`,
  `PersonalChoice`, or `Other`. An override is feedback, not failure, and does
  not automatically change task status.
- Preserve reasons and relevant context when work is blocked, deferred,
  rescheduled, cancelled, or no longer relevant. Do not collapse these outcomes
  into a generic skip. Completing a slice need not complete its parent task.
- Do not implement global completion points, identical completion rewards,
  score resets after skips, streak penalties, or a productivity leaderboard.
  Recommendation ranking scores are local decision explanations, not rewards.

## Architecture and scope

Keep Planning, Execution, and Review separate. Execution offers one bounded
Next Slice; it must not require global reprioritization. In Python, prefer clear
types, enums, and small data models. For the later C++26 implementation, use value
semantics, RAII, strong types where useful, and no raw owning pointers. Avoid
unnecessary templates and speculative abstractions.

Use explicit user state, time, scoring policy, and stable tie-breaking so the
same inputs produce the same recommendation and explanation. Filter eligibility
before ranking; expose each scoring contribution and test it independently.

V0 is CLI only. GUI, web/mobile apps, AI integration, cloud sync, and hardware
support are future work. Milestone 1 is implemented in Python; its scope is
described in `docs/architecture.md`. Keep the reference prototype outside the
application. Preserve behavioral scenarios and
expected decisions from the Python research phase as acceptance tests for the
later C++26 port; validate equivalence rather than translating the prototype blindly.

## Workspace

Cloud tasks already run in an isolated checkout. Work in the existing checkout;
do not create a Git worktree unless the user requests one. Preserve unrelated
user changes. From the repository root, create/activate `.venv` and install with
`python -m pip install --editable .`. Run tests with
`python -m unittest discover -s tests -v`; run the CLI with `skrov` or
`python -m skrov`. There are no third-party runtime/test dependencies. For
isolated experiments, use `skrov --data /tmp/skrov-experiment/state.json ...`.
Preserve real workspace state; do not reset it to run tests.

The small implementation uses `src/skrov/domain.py`, `scheduling.py`, `app.py`,
`sample.py`, `cli.py`, and `storage.py` rather than empty subsystem directories.
Keep Python syntax comments helpful for a learner, explaining unfamiliar syntax
and design choices without narrating every obvious assignment.
