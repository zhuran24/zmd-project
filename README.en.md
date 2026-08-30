# ZMD Certified-Exact Layout Research

[中文](README.md) | [English](README.en.md)

ZMD jointly solves facility placement, power coverage, port binding, and two-layer routing on a `70×70` grid, maximizing a valid contiguous empty rectangle under all hard constraints and producing independently replayable exact evidence. Its research path first constructs a complete layout without assuming a target empty rectangle (the “zero-condition whole layout”), then joins a complete valid witness with a global-optimality proof on the same problem, rules, objective, and premises, while developing methods that can rederive structure and evidence across contexts.

## Method and toolchain

`rules and objective → resource accounts / failure shapes / forced structure → necessary conditions, sufficient constructions, finite representations → exact models → independent replay → certification`

| Area | Tools and purpose |
|---|---|
| Specification | Canonical rules, specifications, and frozen inputs fix problem identity |
| Exact computation | Python, OR-Tools CP-SAT, and LBBD/Benders interfaces handle placement, power, binding, and routing |
| Reasoning outer loop | Counting, finite enumeration, equality structure, constructions, and failure certificates change the next problem |
| Verification | Independent checkers, negative controls, and replay through a separate implementation or environment check inputs, implementations, and scope |
| Engineering | CodeGraph, pytest, pytest-xdist, and Ruff support code understanding and regression checks |
| Promotion | The three-tree Git structure and promotion packets separate research discovery from certification |

Pinned dependencies are listed in [`requirements.lock.txt`](requirements.lock.txt) and [`requirements-dev.lock.txt`](requirements-dev.lock.txt).

## Three-tree workflow

| Branch | Role |
|---|---|
| `main` | History and materials tree, and the public repository entry point |
| `research/main` | Conjectures, experiments, constructions, counterexamples, and new representations |
| `certification/main` | From-scratch independent review and replay of mature candidates (cold review) |

Mature research crosses in a compact promotion packet containing the exact claim, premises, selected changes, reproduction commands, controls, and known unknowns; the research branch is not merged wholesale. The public repository also retains `certification/baseline-repair-20260825`, an internal repair line of the certification tree rather than a fourth tree.

## Project history

ZMD is one continuous project. Two complete backups and Git rebuilds created three parentless epochs; the third epoch later split normally into the three trees. Breaks in Git parentage are not project restarts.

`first epoch → first Git rebuild → second epoch → second Git rebuild → third epoch → main / research / certification`

See [`PROJECT_LINEAGE.md`](PROJECT_LINEAGE.md) for the timeline, backup points, public redaction, and branches found only on former GitHub repositories. The machine-readable index is [`history/continuity.json`](history/continuity.json).

## Project entry points

| Question | Entry point |
|---|---|
| Current state and problem routing | [CURRENT](docs/CURRENT.md) · [START_HERE](docs/START_HERE.md) |
| Code, specifications, and rules | [NAV_MAP](NAV_MAP.md) · [problem statement](specs/01_problem_statement.md) · [rules](rules/) |
| Exactness and certification boundary | [PROJECT_LOCK](PROJECT_LOCK.md) · [CATALOG](docs/CATALOG.md) |
| Operations and document structure | [AGENT_OPERATIONS](docs/AGENT_OPERATIONS.md) · [GUIDANCE_INDEX](docs/GUIDANCE_INDEX.md) · [SECTION_INDEX](docs/SECTION_INDEX.md) |
| Other stable entries | [docs/README](docs/README.md) · [HISTORY_START](HISTORY_START.md) · [BORROWED_COMPONENTS](BORROWED_COMPONENTS.md) |
