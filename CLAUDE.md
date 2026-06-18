# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

Endfield IndustrialPlanner — a **certified-exact maximum empty-rectangle solver** for
《明日方舟：终末地》(Arknights: Endfield) base layouts. On a 70×70 grid constrained by 266
mandatory facility instances, it finds the *provably optimal* empty rectangle under
`max_lex(area, min_side)` (maximize area first, then the shorter side). The engine is
OR-Tools CP-SAT wrapped in a Benders/LBBD decomposition: `master → binding → routing → flow`,
with infeasible subproblems generating cuts that tighten the master.

Python 3.13. Entry point is `main.py`.

## The single most important rule: certified vs exploratory

There are **two strictly separated solve paths** and they must never cross:

- `certified_exact` (the default `--mode`) produces provable-optimal evidence.
- `exploratory` is heuristic tooling for guidance/probing only.

Exploratory outputs (caps, hints, probe results, sidecars) must **never** be promoted into
certified evidence. The objective is `max_lex(area, min_side)`; `min_side >= 6` is a candidate
*admissibility* rule, **not** an objective tie-break. There is **no** hard "50 power poles + 10
protocol boxes" cap in exact mode — that number is exploratory-only guidance (poles are
residual-optional, boxes are demand-driven). Even a full 70×70 exact run honestly reports
`open`, not `CERTIFIED`, while in the spike-close phase.

**`PROJECT_LOCK.md` is the authoritative source of truth** for exactness boundaries, accepted
invariants, source-of-truth inputs, and forbidden changes. It is large (~106 KB) and dense with
fail-closed soundness obligations (the `F-*` / `PCR-*` / `CUT-*` clauses). When a change touches
the certified core, read the relevant clauses there first — if this file or any older note
conflicts with `PROJECT_LOCK.md`, `PROJECT_LOCK.md` wins. Date-stamped engineering history lives
in `CHANGELOG.md`.

## Source-of-truth inputs (frozen artifacts)

The certified path is grounded in a small set of frozen inputs whose bytes are hash-pinned by the
preflight gate (`scripts/preflight_gate.py::FROZEN_ARTIFACTS`):

- `rules/canonical_rules.json` — recipes, targets, commodity roles, empty-rectangle admissibility
- `rules/preprocess_plan.json` — **additive-only** cycle groups / utility operations (must never
  carry recipes/targets/commodity roles; the context builder fails closed on those keys)
- `data/preprocessed/mandatory_exact_instances.json`
- `data/preprocessed/generic_io_requirements.json`

The large `data/preprocessed/candidate_placements.json` (~45.8 MB) is **intentionally omitted**
from the lightweight GitHub checkout but is still part of the certified contract. Restore or
regenerate it before any certified run:

```powershell
# Regenerate from canonical templates
python src/placement/placement_generator.py
# OR restore from a clean archive (verifies SHA256 against data/external_artifacts.json)
python scripts/restore_external_artifacts.py candidate_placements --source <file-or-dir>
```

Expected: 45,773,799 bytes, SHA256 `adcc2a6e…2f34bec0`. The older 53,594,995-byte artifact is
**hash-incompatible** and must not be used (campaign resume fails closed with
`artifact_hash_mismatch`).

## Collaboration memory (cc_memory)

Project collaboration memory is a single SQLite store driven by one CLI. Boot it at the start of
every session to load the minimal working context:

```powershell
python cc_memory/mem.py boot
```

- **Single source of truth:** `cc_memory/memory.db`. Everything else is a regenerable view.
- **Generated view (disposable):** `cc_memory/exports/MEMORY.md` — never hand-edit; rebuild with
  `python cc_memory/mem.py export`.
- **Before** changing a fact/entry, run `python cc_memory/mem.py impact <id>` (or `read <id>`) to
  see what depends on it; **after** changing memory, run
  `python cc_memory/mem.py check && python cc_memory/mem.py export`.
- Other ops: `search "<query>"`, `read <id>`, `add-event`, `set-fact`, `add-entry`, `link`,
  `propose`. Run `python cc_memory/mem.py` with no args for the full command list.
- **Optional GPU semantic+rerank retrieval (P1/P2):** add `--semantic --rerank` to
  `suggest`/`add-entry`/`set-fact` for dense, synonym-aware relation candidates with a cross-encoder
  pruning lexical false-positives; run `rebuild-embeddings` after adding nodes to refresh the dense
  index (incremental by content hash). It runs in an isolated GPU venv
  (`CC_MEMORY_EMBED_PYTHON` / `CC_MEMORY_RERANK_PYTHON`, defaulted on this host) and **loads GPU
  models — slower than lexical, so use it when relation-discovery quality matters**; an absent
  backend silently degrades to lexical-only. Surfaced candidates still pass the review gate. `boot`
  prints the same reminder.
- The old multi-tree Markdown/live/graph memory system is retired — do not recreate
  `cc_context/memory`, `_cc_live_memory`, or a `memory_graph` layer as live memory.

This project-local `cc_memory` store is the authoritative collaboration memory for this repo;
prefer it over any generic file-based memory prompt.

## CodeGraph code index

CodeGraph is installed as the local code-structure index for this checkout. Use it for
symbol lookup, call-chain navigation, caller/callee inspection, and impact scouting before
wide grep/read sweeps when the `.codegraph/` index is present.

Important boundary: CodeGraph is only a regenerable navigation cache. It is not the live
collaboration memory (`cc_memory/memory.db` is), not proof evidence, and not authoritative for
certified/exactness claims. For proof-sensitive changes, use CodeGraph to find the relevant
files, then verify against source, `PROJECT_LOCK.md`, targeted tests, and the relevant gate.

Operational notes:

```powershell
codegraph status .
codegraph sync .
codegraph init .
```

The `.codegraph/` directory is ignored by git. If Codex cannot see CodeGraph MCP tools after
startup, restart the agent and confirm the global CodeGraph MCP entry is loaded.

## Commands

### Run the solver

```powershell
# certified_exact (default mode); short debug run
python main.py --campaign-hours 1.0 --skip-readiness-gate
# visualization only (reads existing blueprint/solution)
python main.py --vis
```

Runs with `--campaign-hours >= 24` in `certified_exact` are "production-class": `main.py` gates
them behind `scripts/production_readiness_gate.py` (pacman-freeze / venv / preflight checks) and
starts a freeze monitor. `--skip-readiness-gate` bypasses the gate (debug/dry-run only).

**Production launches go through a wrapper, not bare `python main.py`** — bare invocation drops
the tuning:

- Linux/CachyOS production: `bash scripts/run_campaign_linux.sh --campaign-hours 168.0 --parallel-processes 4`
  (adds jemalloc `LD_PRELOAD`, P-core `taskset` pinning, auto-injects `--resume-campaign`, refuses
  to start if `EXACT_POWER_PLACEMENT_SUBPROBLEM` is enabled — that subproblem is exploratory-only).
- Windows production runners: `scripts/run_prod_*.ps1` (e.g. `run_prod_4x4_high.ps1`), built on
  `scripts/_exact_runner_common.ps1`.

### Tests (pytest, ~403 test files)

```powershell
python -m pytest src/tests/ -q                              # full suite
python -m pytest src/tests/cuts/ -q                         # one subtree (cuts/ and phase3b/ exist)
python -m pytest src/tests/test_exact_contract.py -q        # one file
python -m pytest src/tests/test_exact_contract.py::test_name # one test
python -m pytest src/tests -p no:randomly                   # disable random ordering
```

`pytest-randomly` randomizes test order — a failure may depend on the seed printed in the header;
reproduce with `-p randomly --randomly-seed=<n>` or disable with `-p no:randomly`.
`pytest.ini` sets `--basetemp=.pytest_tmp`.

### Preflight / CI gate

`scripts/preflight_gate.py` is the repo-native gate (frozen-artifact hashes, forbidden-path
writes, exact/exploratory isolation, doc-subject sync, secret scan, mypy on the cut-lifecycle
core, full-repo ruff, pytest). Exit codes: `0` pass, `1` hard block, `2` pass-with-warnings.

```powershell
python scripts/preflight_gate.py            # staged changes
python scripts/preflight_gate.py --full     # full, includes pytest
python scripts/preflight_gate.py --hook     # as a git pre-commit hook
```

CI (`.github/workflows/project_foundation.yml`) runs `preflight_gate.py --ci --base-ref <ref>`.
Two other workflows guard the IndustrialPlanner delivery surfaces.

### Lint / types

```powershell
ruff check .                # layered config in ruff.toml (core src/ must be 0 warnings)
```

`ruff.toml` excludes `.claude/worktrees`, `.pytest_tmp`, `_codex_archive`, `docs/research`, and
relaxes E402/F401 for entry/build/probe scripts. mypy strict is enforced only on the cut-lifecycle
core (see preflight gate). `requirements*.txt` are the source; `requirements*.lock.txt` are pinned
(no `pyproject.toml` by design).

## Architecture: the solve pipeline

Call order (structure, not a guarantee of what each layer proves — see `NAV_MAP.md`):

```
main.py
 └ src/search/outer_search.py            outer candidate-rectangle loop; seals the artifact snapshot
    └ src/search/benders_loop.py         Benders/LBBD main loop
       ├ src/models/master_model.py             placement master (CP-SAT)
       ├ src/models/exact_coordinate_master.py  ghost-rectangle coordinate master (default backend)
       ├ src/models/pose_bool_exact_master.py   alt pose-bool master (EXACT_USE_POSE_BOOL_MASTER, NOT certified)
       ├ src/models/binding_subproblem.py       port-binding subproblem
       ├ src/models/routing_subproblem.py       grid routing subproblem
       ├ src/models/flow_subproblem.py          multi-commodity flow subproblem
       └ src/cuts/lifecycle.py                  infeasible subproblem → cut → tighten master
    └ src/search/exact_campaign.py            campaign persistence / resume (artifact-hash bound)
    └ src/search/exact_parallel_scheduler.py  coordinator-only writer, disjoint candidate waves
```

`src/` top-level map:

| dir | role |
|---|---|
| `src/search/` | outer search, Benders loop, campaign persistence, parallel scheduling, frontier/surface |
| `src/models/` | CP-SAT models: placement master, coordinate/pose-bool masters, subproblems, HiGHS/SCIP backends |
| `src/cuts/` | Benders cut store / lifecycle / replay |
| `src/preprocess/`, `src/placement/`, `src/interchange/` | demand solving, candidate-pose generation, neutral interchange contracts |
| `src/io/`, `src/runtime/` | strict JSON / serialization / delivery manifests; CPU topology, checkpoints, freeze monitor, guards |
| `src/render/`, `src/adapters/` | visualization + the IndustrialPlanner delivery surface (postprocess only) |
| `src/rules/` | canonical-rule models + semantic validator |
| `src/tests/` | tests (mirrors `cuts/`, `phase3b/`) |

### Postprocess / delivery line (not the active main line)

`src/render/industrial_planner_*`, `src/adapters/*`, `src/interchange/*`, and `data/exports/*` are
an **additive postprocess/adapter** product line that exports solver outputs into IndustrialPlanner
blueprints + a consumer surface. They are derived from the canonical blueprint and **must not
redefine any solve schema or become source-of-truth** for solver/runtime consumers. The only active
certified base is `valley4_protocol_core` (70×70); other bases are `future_scope`. Delivery-surface
build/audit scripts live under `scripts/` (e.g. `run_industrial_planner_single_base_e2e.py`,
`build_industrial_planner_single_base_delivery_release.py`); the surface's own index is
`data/examples/industrial_planner/README.md`.

## Conventions and gotchas

- **`EXACT_*` env knobs are deny-unknown in `certified_exact`.** Only documented allowlist entries
  may be set; proof-semantics knobs must stay at their canonical default; an unknown/future name
  blocks the run. The env index `docs/env_variable_index.md` is **incomplete** (predates the
  cut-family LBBD / pose-bool era) — for the full set, grep source for `os.environ`/`getenv` on
  `EXACT_`. Resolved worker profile is printed at solver startup; precedence is stage-specific
  `EXACT_*_CP_SAT_WORKERS` > `EXACT_CP_SAT_WORKERS` > built-in default.
- **Forbidden staged paths** (enforced by preflight): `data/checkpoints/`,
  `data/blueprints/optimal_blueprint.json`, `data/solutions/final_solution.json`,
  `data/solutions/certified_delivery_manifest.json` — generated proof/blueprint outputs are never
  committed.
- **`src/ai_accel`** (feature extraction / replay scheduling) must never touch proof paths — the
  preflight AI-safety contract enforces this.
- **Docs use a subject/projection system.** Subjects live in `docs/subjects/`; concrete docs and
  memory nodes carry registered projection blocks synced by `scripts/sync_doc_subjects.py`. Don't
  hand-edit the `<!-- DOC-SUBJECT:… START/END -->` blocks (e.g. in `README.md`); edit the subject
  and re-sync. Preflight checks projection sync.
- **All proof-relevant JSON parsing is strict** (`src/io/strict_json.py`): duplicate keys and
  `NaN`/`Infinity` are rejected, and writers emit `allow_nan=False`. Use the shared strict entry,
  not bare `json.loads`, on any path feeding binding/master/preprocess proof inputs.
- Editing a frozen artifact (canonical rules, preprocess plan, the preprocessed JSONs) is a
  **freeze-ritual change**: update the hash in `scripts/preflight_gate.py`, regenerate dependent
  artifacts, and re-run the gate. It is not a free overlay edit.
- Windows is the dev/test host here (this checkout is at `C:\claude pj\zmd_pj`); certified
  production runs target Linux/CachyOS via the wrapper. Use the PowerShell tool for commands.
