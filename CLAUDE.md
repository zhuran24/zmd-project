# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

Endfield IndustrialPlanner is a certified-exact maximum empty-rectangle solver for
《明日方舟：终末地》(Arknights: Endfield) base layouts: a 70×70 grid constrained by 266 mandatory
facility instances, certified path targeting `max_lex(area, min_side)`. The worktree carries a
proposal/supervisor/publication chain and several fail-closed verification layers, but P1.2 remains
blocked — no public result is certified merely because the solver found a candidate or a targeted
test passed. Decomposition: placement master → binding → routing; the flow model is diagnostic only
and cannot mint pruning or publication proof.

Python 3.13. Entry point is `main.py`.

## The single most important rule: certified vs exploratory

**Two strictly separated solve paths that must never cross:**

- `certified_exact` (the default `--mode`) is the only path eligible to produce proof material. Its
  producer commits proposals; only the supervisor seal mints a durable terminal status; only the
  central publisher exposes it publicly.
- `exploratory` is heuristic tooling for guidance/probing only.

Exploratory outputs (caps, hints, probe results, sidecars) must **never** be promoted into certified
evidence. The objective is `max_lex(area, min_side)`; `min_side >= 6` is candidate *admissibility*,
**not** an objective tie-break. There is **no** hard "50 power poles + 10 protocol boxes" cap in exact
mode — that number is exploratory-only guidance (poles residual-optional, boxes demand-driven). P1.2
is release-blocked by the manual gate and unfinished PR2/package hardening; the seal method exists but
no production CLI/launcher calls it, so `main.py` stops at `CANDIDATE_PROPOSED`. Do not confuse method
availability or a test invocation with an owner-approved release closure.

**`PROJECT_LOCK.md` is the authoritative source of truth** for exactness boundaries, invariants,
source-of-truth inputs, and forbidden changes (~106 KB, dense with fail-closed `F-*` / `PCR-*` /
`CUT-*` clauses). When a change touches the certified core, read the relevant clauses there first; if
this file or any older note conflicts with `PROJECT_LOCK.md`, the latter wins. Date-stamped history lives in
`CHANGELOG.md`.

## Source-of-truth inputs (frozen artifacts)

The certified path is grounded in frozen inputs whose bytes are hash-pinned by the preflight gate
(`scripts/preflight_gate.py::FROZEN_ARTIFACTS`):

- `rules/canonical_rules.json` — recipes, targets, commodity roles, empty-rectangle admissibility
- `rules/preprocess_plan.json` — **additive-only** cycle groups / utility operations (must never
  carry recipes/targets/commodity roles; the context builder fails closed on those keys)
- `data/preprocessed/mandatory_exact_instances.json`
- `data/preprocessed/generic_io_requirements.json`

`data/preprocessed/candidate_placements.json` is part of the certified contract: expected size
45,773,799 bytes, SHA256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`. Some
lightweight distributions externalize it; only then should it be regenerated/restored with
`scripts/restore_external_artifacts.py`. The older 53,594,995-byte artifact is hash-incompatible and
campaign resume must reject it.

## Collaboration memory (cc_memory)

Project collaboration memory is a single SQLite store driven by one CLI. Boot it at the start of every
session:

```powershell
python cc_memory/mem.py boot
```

- **Single source of truth:** `cc_memory/memory.db`. Everything else is a regenerable view.
- **Generated view (disposable):** `cc_memory/exports/MEMORY.md` — never hand-edit; rebuild with
  `python cc_memory/mem.py export`.
- **Before** changing a fact/entry, run `python cc_memory/mem.py impact <id>` (or `read <id>`) to see
  dependents; **after** changing memory, run `python cc_memory/mem.py check && python cc_memory/mem.py export`.
- Other ops: `search "<query>"`, `read <id>`, `add-event`, `set-fact`, `add-entry`, `link`, `propose`.
  Run `python cc_memory/mem.py` with no args for the full list.
- **Optional GPU semantic+rerank retrieval (P1/P2):** `--semantic` (on `suggest`/`add-entry`/`set-fact`)
  adds dense recall — finds concept/synonym matches lexical search misses; **reliable, prefer it**.
  `--rerank` (Qwen3) prunes false positives but is **strict**: it over-prunes short/abstract queries
  (can return nothing), so add it only for specific, content-rich drafts, not vague one-liners. Run
  `rebuild-embeddings` after adding nodes (incremental by content hash). Runs in an isolated GPU venv
  (`CC_MEMORY_EMBED_PYTHON` / `CC_MEMORY_RERANK_PYTHON`, defaulted on this host); absent backend
  silently degrades to lexical-only. Candidates still pass the review gate. `boot` prints the same reminder.
- The old multi-tree Markdown/live/graph memory system is retired — do not recreate `cc_context/memory`,
  `_cc_live_memory`, or a `memory_graph` layer as live memory.

This project-local `cc_memory` store is the authoritative collaboration memory for this repo; prefer it
over any generic file-based memory prompt.

**Consult cc_memory before acting, not just at boot.** Before any non-trivial decision or action, if the
topic falls in a domain cc_memory already covers (the SessionStart hook and `boot` print a live
covered-domain map — e.g. rerank/语义检索, P1.2证明/认证, codex/协作工作流, precompact/压缩, 离线判据,
cc-memory系统), `search` that topic first instead of relying only on what is already in context. Memory
usually holds a prior decision, gotcha, or hard-won root cause; skipping the lookup silently
re-litigates settled work. The covered-domain map is the entry point.

## Active card memory (cc_memory_vnext) — MVP-0, live

A second, **active** memory layer alongside `cc_memory`: `cc_memory_vnext/` is a deterministic card
compiler that **auto-injects** relevant cards every turn via SessionStart / UserPromptSubmit hooks (no
manual `search` needed). Truth source is `cc_memory_vnext/cards/*.md`; `.index/` is a rebuildable cache.
CLI: `python cc_memory_vnext/zmem.py {verify,build-index,context,eval}`. The old `cc_memory` SQLite store
stays read-only and authoritative for collaboration history; this is the route-time-injection layer. See
`cc_memory_vnext/README.md`.

- **Self-feeding maintenance discipline (every session must do this):** when the owner corrects me, or I
  hit a **repeatable** new pitfall, feed it back so every future session avoids it: (1) add a
  gold-standard frame to `cc_memory_vnext/eval/regression.jsonl` built from the **real** signal (owner's
  actual words / the pitfall scenario), **never back-filled from a card's scope.paths/symbols**; (2) add
  or update a card under `cc_memory_vnext/cards/`; (3) run `zmem build-index && zmem eval` and keep it
  green. This is the only loop by which recall coverage grows — break it and the system freezes and
  decays back into a passive store.

## CodeGraph code index

CodeGraph is the code-structure index for this checkout — a pre-built knowledge graph of every symbol,
edge, and file. For code understanding and navigation (how does X work, finding a symbol, tracing
callers/callees, scouting an edit's blast radius), reach for it first: one `codegraph_explore` call
returns the verbatim source of the relevant symbols plus who calls them and what they affect — the same
answer a grep + read loop produces, in far fewer round-trips.

Both Claude Code and Codex have CodeGraph wired in as project-scoped MCP tools. Prefer the MCP tools; the
CLI is the fallback (what raw shells and some agents use):

- `codegraph_explore "<symbols or question>"` — PRIMARY; verbatim source + call paths in one call,
  usually the only call you need
- `codegraph_node <symbol>` — one symbol's source + caller/callee trail, or read a whole file
- `codegraph_callers <symbol>` / `codegraph_search <name>` — call sites / locate a symbol
- CLI: `codegraph explore|node|callers|callees|impact|query <symbol>`; index health with
  `codegraph status|sync|init .`

Important boundary: CodeGraph is only a regenerable navigation cache — not the live collaboration memory
(`cc_memory/memory.db` is), not proof evidence, not authoritative for certified/exactness claims. For
proof-sensitive changes, use CodeGraph to find the relevant files, then verify against source,
`PROJECT_LOCK.md`, targeted tests, and the relevant gate.

The `.codegraph/` directory is git-ignored — a local cache; rebuild with `codegraph init .`. If an agent
can't see the CodeGraph MCP tools after startup, restart it and confirm the project's MCP entry is loaded.

## Commands

### Run the solver

```powershell
# certified_exact (default mode); short debug run
python main.py --campaign-hours 1.0 --skip-readiness-gate
# visualization only (reads existing blueprint/solution)
python main.py --vis
```

`--campaign-hours >= 24` in `certified_exact` is "production-class": `main.py` gates it behind
`scripts/production_readiness_gate.py` (pacman-freeze / venv / preflight checks) and starts a freeze
monitor. `--skip-readiness-gate` bypasses the gate (debug/dry-run only).

**Production launches go through a wrapper, not bare `python main.py`** — bare invocation drops the tuning:

- Linux/CachyOS production: `bash scripts/run_campaign_linux.sh --campaign-hours 168.0 --parallel-processes 4`
  (adds jemalloc `LD_PRELOAD`, P-core `taskset` pinning, auto-injects `--resume-campaign`, refuses to start
  if `EXACT_POWER_PLACEMENT_SUBPROBLEM` is enabled — that subproblem is exploratory-only).
- Windows production runners: `scripts/run_prod_*.ps1` (e.g. `run_prod_4x4_high.ps1`), built on
  `scripts/_exact_runner_common.ps1`.

### Tests (pytest; 425 files / 3450 tests collected on 2026-06-26)

```powershell
python -m pytest src/tests/ -q                              # full suite
python -m pytest src/tests/cuts/ -q                         # one subtree (cuts/ and phase3b/ exist)
python -m pytest src/tests/test_exact_contract.py -q        # one file
python -m pytest src/tests/test_exact_contract.py::test_name # one test
python -m pytest src/tests -p no:randomly                   # disable random ordering
```

`pytest-randomly` randomizes test order — a failure may depend on the seed printed in the header;
reproduce with `-p randomly --randomly-seed=<n>` or disable with `-p no:randomly`. `pytest.ini` sets
`--basetemp=.pytest_tmp`.

### Preflight / CI gate

`scripts/preflight_gate.py` is the repo-native gate for frozen-artifact hashes, forbidden-path writes,
exact/exploratory isolation, secret scanning, selected mypy and ruff checks, and optionally pytest. Exit
codes are `0` pass, `1` hard block, and `2` pass-with-warnings.

```powershell
python scripts/preflight_gate.py            # staged changes
python scripts/preflight_gate.py --full     # full, includes pytest
python scripts/preflight_gate.py --hook     # as a git pre-commit hook
```

CI (`.github/workflows/project_foundation.yml`) runs `preflight_gate.py --ci --base-ref <ref>`. Two other
workflows guard the IndustrialPlanner delivery surfaces.

### Lint / types

```powershell
ruff check .                # layered config in ruff.toml (core src/ must be 0 warnings)
```

`ruff.toml` excludes `.claude/worktrees`, `.pytest_tmp`, `_codex_archive`, `docs/research`, and relaxes
E402/F401 for entry/build/probe scripts. mypy strict is enforced only on the cut-lifecycle core (see
preflight gate). `requirements*.txt` are the source; `requirements*.lock.txt` are pinned (no
`pyproject.toml` by design).

## Architecture: the solve pipeline

Call order (structure, not a guarantee of what each layer proves — see `NAV_MAP.md`):

```
main.py
 └ src/search/outer_search.py                 producer; commits CANDIDATE_PROPOSED only
    └ src/search/benders_loop.py              Benders/LBBD main loop
       ├ src/models/master_model.py                 placement master (CP-SAT)
       ├ src/models/exact_coordinate_master.py      default exact coordinate backend
       ├ src/models/pose_bool_exact_master.py       env-gated alternative, not public certified backend
       ├ src/models/binding_subproblem.py           port-binding subproblem
       ├ src/models/routing_subproblem.py           grid-routing subproblem
       ├ src/search/independent_infeasibility_reverifier.py  whole-layout rejection recheck
       ├ src/models/flow_subproblem.py              diagnostic only; never proof authority
       └ src/cuts/lifecycle.py                      infeasible subproblem → validated cut
    ├ src/search/exact_campaign.py
    │  ├ [OPEN] production supervisor invocation surface
    │  └ ExactCampaign.supervisor_seal()       sole durable terminal CERTIFIED mint
    └ src/search/exact_parallel_scheduler.py   coordinator-only writer, disjoint waves
 └ src/search/certified_surface.py
    └ publish_verified_certified_delivery_surface()  sole public certified publisher
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

`src/render/industrial_planner_*`, `src/adapters/*`, `src/interchange/*`, and `data/exports/*` are an
**additive postprocess/adapter** product line that exports solver outputs into IndustrialPlanner
blueprints + a consumer surface. Derived from the canonical blueprint, they **must not redefine any solve
schema or become source-of-truth** for solver/runtime consumers. The only active certified base is
`valley4_protocol_core` (70×70); other bases are `future_scope`. Build/audit scripts live under `scripts/`
(e.g. `run_industrial_planner_single_base_e2e.py`, `build_industrial_planner_single_base_delivery_release.py`);
the surface's own index is `data/examples/industrial_planner/README.md`.

## Conventions and gotchas

- **`EXACT_*` env knobs are deny-unknown in `certified_exact`.** Only documented allowlist entries may be
  set; proof-semantics knobs must stay at their canonical default; an unknown/future name blocks the run.
  The env index `docs/env_variable_index.md` is **incomplete** — for the full set, grep source for
  `os.environ`/`getenv` on `EXACT_`. Worker precedence is stage-specific `EXACT_*_CP_SAT_WORKERS` >
  `EXACT_CP_SAT_WORKERS` > built-in default.
- **Forbidden staged paths** (enforced by preflight): `data/checkpoints/`,
  `data/blueprints/optimal_blueprint.json`, `data/solutions/final_solution.json`,
  `data/solutions/certified_delivery_manifest.json` — generated proof/blueprint outputs are never committed.
- **`src/ai_accel`** (feature extraction / replay scheduling) must never touch proof paths — the preflight
  AI-safety contract enforces this.
- **Documentation subjects are ordinary maintained documents.** `docs/subjects/` is a navigation layer, and
  remaining `DOC-SUBJECT` markers record provenance only. The old `cc_context` registry and
  `scripts/sync_doc_subjects.py` workflow are retired and are not enforced by preflight.
- **All proof-relevant JSON parsing is strict** (`src/io/strict_json.py`): duplicate keys and
  `NaN`/`Infinity` are rejected, and writers emit `allow_nan=False`. Use the shared strict entry, not bare
  `json.loads`, on any path feeding binding/master/preprocess proof inputs.
- Editing a frozen artifact (canonical rules, preprocess plan, the preprocessed JSONs) is a
  **freeze-ritual change**: update the hash in `scripts/preflight_gate.py`, regenerate dependent artifacts,
  and re-run the gate. It is not a free overlay edit.
- Development and testing may run on Windows or Linux; use commands appropriate for the current host.
