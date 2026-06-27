# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

Endfield IndustrialPlanner is a certified-exact maximum empty-rectangle solver for
《明日方舟：终末地》(Arknights: Endfield) base layouts. On a 70×70 grid constrained by
266 mandatory facility instances, the certified path targets `max_lex(area, min_side)`.
The current worktree contains a proposal/supervisor/publication chain and several
fail-closed verification layers, but P1.2 remains blocked and no public result may be
described as certified merely because the solver found a candidate or a targeted test
passed. The main decomposition is placement master → binding → routing; the flow model
is diagnostic only and cannot mint pruning or publication proof.

Python 3.13. Entry point is `main.py`.

## The single most important rule: certified vs exploratory

There are **two strictly separated solve paths** and they must never cross:

- `certified_exact` (the default `--mode`) is the only path eligible to produce
  proof material. Its producer commits proposals; only the supervisor seal may mint a
  durable terminal status, and only the central publisher may expose it publicly.
- `exploratory` is heuristic tooling for guidance/probing only.

Exploratory outputs (caps, hints, probe results, sidecars) must **never** be promoted into
certified evidence. The objective is `max_lex(area, min_side)`; `min_side >= 6` is a candidate
*admissibility* rule, **not** an objective tie-break. There is **no** hard "50 power poles + 10
protocol boxes" cap in exact mode — that number is exploratory-only guidance (poles are
residual-optional, boxes are demand-driven). P1.2 remains release-blocked by the manual gate and unfinished PR2/package
hardening. The seal method exists, but no production CLI/launcher calls it; `main.py` stops at
`CANDIDATE_PROPOSED`. Do not confuse method availability or a test invocation with an
owner-approved release closure.

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

`data/preprocessed/candidate_placements.json` is present in this worktree and remains part
of the certified contract. Its expected size is 45,773,799 bytes and its SHA256 is
`adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`. Some lightweight
distributions may externalize it; only in such a distribution should it be regenerated
or restored with `scripts/restore_external_artifacts.py`. The older 53,594,995-byte
artifact is hash-incompatible and campaign resume must reject it.

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
- **Optional GPU semantic+rerank retrieval (P1/P2):** `--semantic` (on
  `suggest`/`add-entry`/`set-fact`) adds dense recall — finds concept/synonym matches lexical
  misses; this is the **reliable** win, prefer it. `--rerank` adds a cross-encoder that prunes
  false-positives, but Qwen3-Reranker is **strict/conservative**: excellent for specific,
  content-rich drafts, yet it over-prunes **short/abstract queries** (can return nothing) — add it
  only when the draft is specific, not for vague one-line queries. Run `rebuild-embeddings` after
  adding nodes to refresh the dense index (incremental by content hash). Runs in an isolated GPU
  venv (`CC_MEMORY_EMBED_PYTHON` / `CC_MEMORY_RERANK_PYTHON`, defaulted on this host); loads GPU
  models (slower), absent backend silently degrades to lexical-only. Candidates still pass the
  review gate. `boot` prints the same reminder.
- The old multi-tree Markdown/live/graph memory system is retired — do not recreate
  `cc_context/memory`, `_cc_live_memory`, or a `memory_graph` layer as live memory.

This project-local `cc_memory` store is the authoritative collaboration memory for this repo;
prefer it over any generic file-based memory prompt.

**Consult cc_memory before acting, not just at boot.** Before any non-trivial decision or action,
if the topic falls in a domain cc_memory already covers (the SessionStart hook and `boot` print a
live covered-domain map — e.g. rerank/语义检索, P1.2证明/认证, codex/协作工作流, precompact/压缩,
离线判据, cc-memory系统), `search` that topic first instead of relying only on what is already in
context. Memory usually holds a prior decision, gotcha, or hard-won root cause on it; skipping the
lookup silently re-litigates settled work. The covered-domain map is the entry point — seeing a
relevant domain there is the trigger to go look.

## Active card memory (cc_memory_vnext) — MVP-0, live

A second, **active** memory layer is live alongside `cc_memory`: `cc_memory_vnext/` is a
deterministic card compiler that **auto-injects** relevant cards every turn via SessionStart /
UserPromptSubmit hooks (no manual `search` needed). Truth source is `cc_memory_vnext/cards/*.md`;
`.index/` is a rebuildable cache. CLI: `python cc_memory_vnext/zmem.py {verify,build-index,context,eval}`.
The old `cc_memory` SQLite store stays read-only and authoritative for collaboration history; this
is the route-time-injection layer. See `cc_memory_vnext/README.md`.

- **Self-feeding maintenance discipline (every session must do this):** when the owner corrects me,
  or I hit a **repeatable** new pitfall, do not just fix it in the current session — feed it back so
  every future session avoids it: (1) add a gold-standard frame to
  `cc_memory_vnext/eval/regression.jsonl` built from the **real** signal (owner's actual words / the
  pitfall scenario), **never back-filled from a card's scope.paths/symbols**; (2) add or update a
  card under `cc_memory_vnext/cards/`; (3) run `zmem build-index && zmem eval` and keep it green.
  This is the only loop by which recall coverage grows. The owner will **not** hand-review millions
  of words of transcripts, so coverage growth rides on this in-session discipline (and, later, a
  small-model evaluator) — break it and the system freezes and decays back into a passive store.

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

### Tests (pytest; 425 files / 3450 tests collected on 2026-06-26)

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

`scripts/preflight_gate.py` is the repo-native gate for frozen-artifact hashes,
forbidden-path writes, exact/exploratory isolation, secret scanning, selected mypy and
ruff checks, and optionally pytest. It does not run or enforce the retired documentation
subject/projection synchronizer. Exit codes are `0` pass, `1` hard block, and `2`
pass-with-warnings.

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
- **Documentation subjects are ordinary maintained documents.** `docs/subjects/` is a
  navigation layer, and remaining `DOC-SUBJECT` markers record provenance only. The old
  `cc_context` registry and `scripts/sync_doc_subjects.py` workflow are retired and are not
  enforced by preflight.
- **All proof-relevant JSON parsing is strict** (`src/io/strict_json.py`): duplicate keys and
  `NaN`/`Infinity` are rejected, and writers emit `allow_nan=False`. Use the shared strict entry,
  not bare `json.loads`, on any path feeding binding/master/preprocess proof inputs.
- Editing a frozen artifact (canonical rules, preprocess plan, the preprocessed JSONs) is a
  **freeze-ritual change**: update the hash in `scripts/preflight_gate.py`, regenerate dependent
  artifacts, and re-run the gate. It is not a free overlay edit.
- Development and testing may run on Windows or Linux. Use commands appropriate for the
  current host; production-class Linux/CachyOS launches still go through the repository
  wrapper rather than a bare `python main.py` invocation.
