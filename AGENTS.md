# Codex Agent Entry

This file is the Codex entrypoint for this repository. It should route agents into
the existing project instructions and memory; it must not create a second memory
system.

## First Read

At the start of any non-trivial task in this repo:

1. Read `CLAUDE.md` first. It is the maintained human/agent runbook for this codebase.
2. Boot the project memory with `python cc_memory/mem.py boot`.
3. Use `python cc_memory/mem.py search "<query>"` and `python cc_memory/mem.py read <id> --body`
   for task-specific memory.
4. Check `git status --short` before editing or staging. This repo is often touched
   by concurrent sessions; never sweep unrelated changes into your work.
5. If the task touches exactness, proof, candidate status, campaign resume, parallel
   scheduling, frozen inputs, or certified outputs, read the relevant section of
   `PROJECT_LOCK.md` before changing code.

`AGENTS.md` is intentionally thin. Keep durable project knowledge in the existing
places: `CLAUDE.md` for operating rules, `PROJECT_LOCK.md` for exactness contracts,
and `cc_memory/memory.db` for collaboration memory.

## Existing Memory System

The only live collaboration memory is `cc_memory/memory.db`, accessed through
`cc_memory/mem.py`.

- Do not create or revive another memory system.
- Do not recreate `cc_context/memory`, `_cc_live_memory`, or a `memory_graph` layer.
- Do not hand-edit `cc_memory/exports/MEMORY.md`; it is a generated view.
- Do not edit `cc_memory/memory.db` with raw SQLite for normal memory work; use
  `cc_memory/mem.py` so mutations, dependencies, suggestions, checks, and exports
  stay coherent.
- Before changing a memory fact or entry, run `python cc_memory/mem.py impact <id>`
  or `python cc_memory/mem.py read <id> --body`.
- After changing memory, run `python cc_memory/mem.py check && python cc_memory/mem.py export`.
- If `check` fails because of pending relation suggestions, review them with
  `python cc_memory/mem.py relations` and accept/reject explicitly.

### Writing Or Editing Memory

Use the existing memory CLI for all memory writes. A normal write flow is:

1. Search/read the relevant existing nodes.
2. Run `impact` before overwriting an existing fact or entry.
3. Add a source event that records the evidence or user instruction.
4. Write the fact or entry through the CLI.
5. Review generated relation suggestions.
6. Run `check && export`.

Common write commands:

```powershell
# Record source material or a user instruction.
python cc_memory/mem.py add-event --summary "short summary" --text "evidence or instruction"

# Add or update a durable fact. Use --event when the fact came from a recorded event.
python cc_memory/mem.py set-fact --id <fact-id> --subject <subject> --predicate <predicate> --value "..." --event <event-id>

# Add or update an entry. Prefer --depends-on for hard dependencies.
python cc_memory/mem.py add-entry --id <entry-id> --title "..." --body "..." --depends-on <fact-or-entry-id> --event <event-id>

# Link existing nodes when the relationship matters.
python cc_memory/mem.py link <source-id> <target-id> --type DEPENDS_ON --reason "why this dependency is hard"

# Queue an explicit proposed memory change instead of silently rewriting uncertain state.
python cc_memory/mem.py propose --operation update_fact --touches <id> --reason "why this should change" --event <event-id>
```

For semantic/rerank relation discovery on non-trivial memory writes, add
`--semantic --rerank` to `set-fact` or `add-entry` when the GPU backends are
available. If the optional backend is unavailable, the CLI should degrade to
lexical behavior; report the warning instead of pretending semantic review ran.

Relation suggestions are part of the write gate:

```powershell
python cc_memory/mem.py relations
python cc_memory/mem.py review-relation <suggestion-id> --accept --type RELATED_TO --reason "why accepted"
python cc_memory/mem.py review-relation <suggestion-id> --reject --reason "why rejected"
python cc_memory/mem.py check
python cc_memory/mem.py export
```

Use `--force` only when intentionally replacing an existing node after reading its
current body and impact set. If a memory change is uncertain, add an event and a
proposal rather than overwriting the fact.

Important memory entries to look up when relevant:

- `memory-runtime-protocol`
- `codex-needs-explicit-read-memory`
- `concurrent-session-shared-index-hazard-20260617`
- `soundness-claims-cxwf-verdict-20260616`
- `soundness-patches-adopted-20260617`
- `followup-h50-g-neg-and-publish-20260617`
- `arch-layering-plan-proof-vs-ops`

`docs/subjects/` and `DOC-SUBJECT` projection blocks are documentation surfaces, not
the live collaboration memory. Some documentation still mentions retired
`cc_context/...` projection tooling; verify that the referenced scripts and registry
exist before relying on those instructions. Do not resurrect missing old tooling just
because an older projection document names it.

## Project Shape

This is the Endfield IndustrialPlanner certified-exact maximum empty-rectangle
solver. The default path is `certified_exact`; `exploratory` is a separate heuristic
or diagnostic path.

P1.2 close-kernel sealing (2026-06-17): proof-bearing strong-status source sinks on
the current default certified path are registered in
`data/proof_obligations/p1_2_proof_obligations.json::close_kernel_contract` and checked by
`scripts/check_p1_2_proof_obligations.py`. Adding a new `CERTIFIED` / proof-bearing
`INFEASIBLE` surface, drifting a sealed sink hash, or removing required guard tokens reopens
the P1.2 close claim until reviewed. The current local seal includes the follow-up
F-CAM-R8-02 durable resume-sanitization fix; do not replace it with the earlier package
snapshot without re-sealing `src/search/exact_campaign.py` and `src/search/outer_search.py`.
The V99 close-kernel floor is checker-owned: required proof-bearing tokens, scan roots,
sink paths, sink classifications, non-checker source hashes, and critical gate files
must not be shrinkable or resealable by editing the manifest alone.

Main call chain:

```text
main.py
  -> src/search/outer_search.py
     -> src/search/benders_loop.py
        -> src/models/master_model.py
        -> src/models/exact_coordinate_master.py
        -> src/models/binding_subproblem.py
        -> src/models/routing_subproblem.py
        -> src/models/flow_subproblem.py
     -> src/search/exact_campaign.py
     -> src/search/exact_parallel_scheduler.py
```

High-signal directories:

- `src/search/`: outer frontier, Benders/LBBD loop, campaign persistence, parallel waves.
- `src/models/`: CP-SAT master and subproblems.
- `src/cuts/`: cut object lifecycle, replay, quarantine, family validators. This is
  an important subsystem, but not a blanket statement that every cut-family path is
  already production-integrated into the main certified run.
- `src/io/`: strict JSON and proof-surface serializers.
- `src/runtime/`: process priority, checkpoints, freeze monitor, production guards.
- `src/adapters/`, `src/render/`, `src/interchange/`: postprocess/export surfaces,
  not solver source-of-truth.
- `rules/`, `data/preprocessed/`, `specs/`, `docs/subjects/`: frozen rules, inputs,
  specs, and documentation subjects.

## Exactness Rules

`PROJECT_LOCK.md` wins on exactness boundaries. If it conflicts with README,
historical docs, generated exports, or older memory, use `PROJECT_LOCK.md` and note
the conflict.

Core invariants:

- `certified_exact` and `exploratory` must not cross.
- Exploratory caps, hints, probes, or diagnostics must never become certified proof.
- The exact objective is `max_lex(area, min_side)`.
- `min_side >= 6` is candidate admissibility, not an objective replacement.
- Exact mode has no hard `50 power poles + 10 protocol storage boxes` cap.
- Phase 1.2 spike close is not formally closed; P1.3B remains blocked unless the
  owner explicitly opens it.
- `EXACT_*` env knobs are deny-unknown in certified mode. Unknown or proof-semantics
  knobs must fail closed, not silently alter certified behavior.
- `EXACT_POWER_PLACEMENT_SUBPROBLEM=1` is exploratory/forensic only and must not be
  enabled in certified or production campaign paths.
- `PoseBoolExactMaster` is env-gated and not the public certified backend unless the
  project lock explicitly changes.

Frozen source-of-truth inputs:

- `rules/canonical_rules.json`
- `rules/preprocess_plan.json`
- `data/preprocessed/mandatory_exact_instances.json`
- `data/preprocessed/generic_io_requirements.json`
- external large artifact `data/preprocessed/candidate_placements.json`

Editing any frozen artifact is a freeze-ritual change: update the relevant hash
contract, regenerate dependent artifacts, and run the gate. Do not "fix" a hash
mismatch by changing the expected hash unless the semantic source-of-truth change
was intended and reviewed.

## Code-Specific Guardrails

- `outer_search.py` owns the certified frontier and terminal full-frontier claim.
  UNKNOWN handling, `declare_mode`, frontier probe mode, and parallel-wave result
  persistence are proof-sensitive.
- `exact_campaign.py` owns resume validity. Campaign state is hash-bound and must
  fail closed on schema, artifact, source digest, timestamp, terminal evidence, or
  candidate-record inconsistency.
- `exact_parallel_scheduler.py` owns worker identity and crash handling. A malformed
  or crash-tainted wave must not persist sticky proof-bearing `INFEASIBLE` records.
- `benders_loop.py` owns exact/exploratory dispatch, exact session construction,
  certified env blockers, pre-master prechecks, exact-safe cut handling, and
  binding/routing orchestration.
- `master_model.py` and `exact_coordinate_master.py` are the certified master core.
  Applying a cut invalidates the previous solver witness; never extract a stale
  solution after mutating the model.
- `binding_subproblem.py` must load generic I/O requirements fail-closed and keep
  wireless/generic slots distinct from physical routed ports.
- `routing_subproblem.py` treats connector cells as terminal nodes, not belt cells.
  Only verified domain statuses may become proof-bearing rejections.
- `flow_subproblem.py` is exploratory acceleration or certified diagnostic only; it
  must not mint exact-safe pruning proof by itself.
- `src/io/strict_json.py` is the shared entry for proof-relevant JSON parsing.
  Duplicate keys and non-finite numbers must be rejected.
- `src/cuts/lifecycle.py` is a cut-family subsystem. Its `step_8_apply_to_master`
  boundary is intentionally not a blanket production integration permission.

## Commands

Read memory:

```powershell
python cc_memory/mem.py boot
python cc_memory/mem.py search "query"
python cc_memory/mem.py read <id> --body
```

Run solver/debug:

```powershell
python main.py --campaign-hours 1.0 --skip-readiness-gate
python main.py --vis
```

Production-class certified runs must use the wrappers documented in `CLAUDE.md`;
do not replace them with bare `python main.py`.

Validation:

```powershell
python scripts/preflight_gate.py
python scripts/preflight_gate.py --full
python -m pytest src/tests/ -q
python -m pytest src/tests/test_exact_contract.py -q
ruff check .
```

For a narrow code change, run the smallest relevant pytest first, then the relevant
gate. For proof/campaign/parallel/exactness changes, prefer `preflight_gate.py` plus
targeted regression tests named in the changed area.

## Git and Workspace Hygiene

- Treat `cc_memory/memory.db` as user/project state. Do not revert it casually.
- Stage exact paths only. Do not use broad commits while other sessions may be
  editing the same checkout.
- Before commit or PR work, re-check `git status --short`, `git diff --stat`, and
  staged paths.
- The current remote is the private `zhuran24/zmd_pj` repository; verify live remotes
  before pushing.

## Disk and Artifacts

Follow the machine storage policy from the user/global instructions. In short:
check mounted drives before disk-heavy work; keep small irreplaceable state in the
workspace; route large regenerable downloads, caches, extracted packages, model
files, and build artifacts away from `C:` when appropriate. Do not use `G:` for local
caches or temp outputs.

When packaging this project for handoff, keep archive filenames concise. Prefer
`zmd_<short-tag>_<YYYYMMDD_HHMM>.7z` or similar; put detailed purpose, commit,
hash, and verification notes in the message or manifest, not in the filename.

Generated proof outputs, checkpoints, blueprints, and certified delivery manifests
are intentionally guarded by preflight. Do not commit forbidden generated paths such
as `data/checkpoints/`, `data/blueprints/optimal_blueprint.json`,
`data/solutions/final_solution.json`, or
`data/solutions/certified_delivery_manifest.json`.
