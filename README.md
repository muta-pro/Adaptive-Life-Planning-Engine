# SKROV — Adaptive Life Planning Engine

SKROV recommends one bounded next action from your life domains, current cycle,
available time, energy, and context. It supports useful progress and recovery
without requiring an hourly plan. This **Python research implementation** makes
scheduling rules easy to experiment with. **C++26** remains the later target.

## Run Milestone 1

Use Python 3.11 or newer. Run these commands from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --editable .
skrov now --minutes 45 --energy high --context desk
python -m unittest discover -s tests -v
```

There are no third-party runtime or test dependencies. Installation uses
setuptools as its build tool. Editable installation means source edits take
effect without reinstalling. `python -m skrov` also works after installation.

On first use, the CLI seeds five sample slices: Webserv event loop, CPP Module
08, Job application, Menura landing page, and Climbing / recovery. The high-energy
example selects Webserv and explains its score:

```text
Next Slice [1]: Webserv event loop
Duration: 25 minutes
Ranking score: 32 (for this decision only)
Reasons:
  +8 importance
  +15 cycle relevance
  +4 rhythm deficit
  +6 energy fit
  -1 switching cost
```

The actual output also includes each calculation, tie-breaking, and exclusions.
With medium energy, CPP Module 08 wins instead.

## Commands

| Command | Example |
| --- | --- |
| Add one bounded slice | `skrov add "Read a chapter" --domain Learning --minutes 15 --energy low` |
| List all states | `skrov list` |
| Recommend | `skrov now --minutes 30 --energy medium --context desk` |
| Start the latest recommendation | `skrov start` |
| Start a specific eligible slice | `skrov start 3 --energy low` |
| Complete the active slice | `skrov done` |
| Record a block | `skrov blocked 1 --reason "Waiting for API documentation"` |
| Clear a block explicitly | `skrov blocked 1 --clear` |
| Record recommendation feedback | `skrov override energy_mismatch --alternative 3 --note "Need a lighter slice"` |
| Show states and override history | `skrov status` |

`done` and `blocked` can omit the ID to use the active slice. `start` inherits the
latest recommendation's user state unless you supply new constraints. Defaults
for `now` are 45 minutes, medium energy, and desk context; these are explicit
experiment inputs, not inferred observations. Use `skrov COMMAND --help` for options.

Only one slice can be active. During execution, `now` asks you to finish or block
that slice before making another recommendation.

An override requires a preceding `now`. Reasons are `wrong_priority`,
`energy_mismatch`, `insufficient_time`, `missing_dependency`, `unexpected_urgency`,
`personal_choice`, and `other`. It stores the original recommendation, all score
contributions, user-state snapshot, timestamp, optional alternative, and note.
It does not change task status or automatically start the alternative. After an
override, use `start ID` or request `now` with updated constraints. Identical
inputs can recommend the same task again; overrides are not penalties.

## Experiment with the scheduler

Eligibility requires Ready status, enough time, matching context (or task
context `any`), and completed dependencies. High-demand work is excluded at low
energy. A one-level energy mismatch remains eligible with a ranking penalty.

The five contributions are independently testable functions in
[`scheduling.py`](src/skrov/scheduling.py). Default policy:

| Component | Calculation |
| --- | --- |
| Importance | `importance × 2` |
| Cycle relevance | `cycle_relevance × 3` |
| Rhythm deficit | `max(0, rhythm_target - completions_in_cycle) × 4` |
| Energy fit | `+6` for an exact match; otherwise `-3 × energy-level gap` |
| Switching cost | `-switching_cost × 1` |

Highest total wins; ties use the lower task ID, regardless of input order. There
is no clock or randomness in scheduling. `ScoringPolicy` exposes weights to
Python experiments; it is not yet a CLI configuration feature. Ranking scores
explain a decision and never accumulate into productivity points.

`add` accepts `--importance`, `--cycle-relevance`, and `--switching-cost` on a 0–5
scale, plus `--rhythm-target`, `--cycle-completions`, and `--depends-on ID ...`.
Rhythm targets/completions are explicitly supplied for the current cycle. Each
task is one bounded slice: `done` completes it and increments its cycle count.
Recurring activities, automatic cycle rollover, partial-task progress, deadlines,
and Review mode are future work. Deferred/Cancelled states are modeled and
filtered, but this milestone does not expose transition commands for them.

## Local state and code guide

State is saved to `.skrov/state.json` relative to your working directory; that
directory is ignored by Git. To isolate experiments, use a new path:

```bash
skrov --data /tmp/skrov-experiment/state.json --empty list
skrov --data /tmp/skrov-experiment/state.json add "Recovery walk" --domain Health --energy low --context any
skrov --data /tmp/skrov-experiment/state.json now --energy low --context home
```

`--empty` omits sample tasks only when creating a new workspace. Task transitions
retain their reasons and timestamps; override events are a separate history.
JSON writes use atomic replacement, and unreadable/invalid data is reported
instead of being reset. This small local adapter assumes one command writes a
workspace at a time; it does not provide concurrent editing or cloud sync.

- [Python learning guide](docs/python-guide.md), with a suggested reading order.
- [Architecture and milestone scope](docs/architecture.md).
- [Guidance for Codex and contributors](AGENTS.md).
- [Original exploratory CLI prototype](docs/reference/README.md), preserved as reference.
