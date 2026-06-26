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

`docs/subjects/` and any remaining `DOC-SUBJECT` markers are ordinary documentation
and provenance metadata, not the live collaboration memory. The old `cc_context/...`
projection registry and `scripts/sync_doc_subjects.py` workflow are retired and are not
present in this worktree. Do not treat a marker as a generated or preflight-enforced
projection, and do not recreate the retired tooling from historical instructions.

## CodeGraph Entry

CodeGraph is the local code-structure index for this repo. Use it to navigate
symbols, call chains, callers/callees, and change impact when `.codegraph/`
exists, especially before broad grep/read sweeps. Treat it as a regenerable
navigation aid only: it is not project memory, not proof evidence, and not a
replacement for source reads, `PROJECT_LOCK.md`, tests, or preflight gates.

If the MCP tools are not visible in a fresh Codex session, restart the agent and
check that the global CodeGraph MCP entry is loaded. The repo index can be
refreshed with `codegraph sync .` or rebuilt with `codegraph init .`; `.codegraph/`
is intentionally ignored by git.

## Project Shape

This is the Endfield IndustrialPlanner certified-exact maximum empty-rectangle
solver. The default path is `certified_exact`; `exploratory` is a separate heuristic
or diagnostic path.

P1.2 publication-chain state (current worktree, 2026-06-26): the producer
path in `outer_search.py` may commit only a `CANDIDATE_PROPOSED` record plus bound
replay/fixed-witness material. `ExactCampaign.supervisor_seal()` is the sole durable
terminal `CERTIFIED` mint and re-reads the committed proposal, validates its bindings,
runs the sink replay and terminal fixed-witness verification, then validates the disk
state before and after the write. The repository currently has no production CLI or
launcher that calls it; `main.py` stops at `CANDIDATE_PROPOSED`. Public solution,
blueprint, and delivery-manifest
files are emitted only by `publish_verified_certified_delivery_surface()` from a
sealed, disk-current campaign; generic serializers and compatibility exporters are not
certification authorities.

The close-kernel manifest and checker in
`data/proof_obligations/p1_2_proof_obligations.json` and
`scripts/check_p1_2_proof_obligations.py` structurally seal proof-bearing sinks. The
current worktree also contains the fixed-witness capsule/verifier, the fail-closed P1.2
OPEN-GATE resolver, and an independent whole-layout infeasibility reverifier. These are
implemented safeguards, not a claim that P1.2 is closed. The manual review gate remains
blocked, PR2's smaller/read-once verification TCB is not implemented, and the review
snapshot packager still needs immutable commit materialization and broader policy
coverage. A passing structural checker or targeted regression set is therefore not a
soundness or release conclusion.

Candidate records carry data-only replay requests. No Python function identity,
closure, mutable registry, writer identity, or current-process freshness stamp grants
proof authority. The isolated replay verifier, protected source and interpreter, and
operating-system process/file isolation remain in the trusted computing base. Adding a
strong-status sink, drifting a sealed hash, changing a required guard, or weakening a
publication denial must reopen review rather than be locally resealed away.

Main solve and publication chain:

```text
main.py
  -> src/search/outer_search.py                 producer; CANDIDATE_PROPOSED only
     -> src/search/benders_loop.py
        -> src/models/master_model.py
        -> src/models/exact_coordinate_master.py
        -> src/models/binding_subproblem.py
        -> src/models/routing_subproblem.py
        -> src/search/independent_infeasibility_reverifier.py
        -> src/models/flow_subproblem.py        diagnostic only; never proof authority
     -> src/search/exact_campaign.py
        -> [OPEN: production supervisor CLI/launcher]
        -> ExactCampaign.supervisor_seal()      sole durable terminal CERTIFIED mint
     -> src/search/exact_parallel_scheduler.py
  -> src/search/certified_surface.py
     -> publish_verified_certified_delivery_surface()  sole public certified publisher
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
- Phase 1.2 is not formally closed; the human-facing next phase is P1.3 and remains
  blocked unless the owner explicitly opens it. Existing `p1_3b_*` machine identifiers
  are retained only for compatibility with historical gate data.
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
- `data/preprocessed/candidate_placements.json` (present in this worktree; some distributions may externalize it)

Editing any frozen artifact is a freeze-ritual change: update the relevant hash
contract, regenerate dependent artifacts, and run the gate. Do not "fix" a hash
mismatch by changing the expected hash unless the semantic source-of-truth change
was intended and reviewed.

## Code-Specific Guardrails

- `outer_search.py` owns candidate enumeration and the producer-side frontier. It may
  commit only proposal state; UNKNOWN handling, `declare_mode`, frontier probe mode,
  and parallel-wave result persistence are proof-sensitive.
- `exact_campaign.py` owns resume validity and the supervisor seal. Campaign state is
  hash-bound and must fail closed on schema, artifact, source digest, timestamp,
  proposal/terminal evidence, fixed-witness, or candidate-record inconsistency. Do not
  create another durable terminal `CERTIFIED` writer.
- `certified_surface.py` owns the fail-closed OPEN-GATE evaluation and the sole public
  certified publisher. Compatibility exports may format data, but may not bypass the
  sealed-campaign and current-disk checks or become alternate publication authorities.
- `exact_campaign_inspector.py` is a public surface, not a raw debug dump. When
  `certified_surface.publishable` is false, candidate-level proof-bearing
  `CERTIFIED` / `INFEASIBLE` statuses and nested proof hints must be redacted or
  downgraded; do not let secondary fields bypass the central publishability gate.
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

## GPT Pro Review Loop

For recurring P1.2 adversarial soundness review packages, use the ChatGPT project
`终末地` Sources tab as the upload authority. Upload project packages from
`project?tab=sources` via `添加源` / `Choose File`; do not upload these packages
through the chat composer attachment button. Send the review prompt in the boxed
project chat composer shown at the top of the project page.

Before uploading a new project review package, delete older project packages from
the ChatGPT project Sources list so GPT cannot pick the wrong archive as the
current review target. Do not delete dependency/runtime packages, such as the
Python dependency bundle, unless the user explicitly asks.
This section is the durable standing authorization for the GPT Pro Review Loop.
Within this loop, stale project review package cleanup is authorized when the
target is clearly an older project package. Do not pause solely to reconfirm this
scoped cleanup when the filename and package role are clear. Dependency/runtime
packages remain out of scope unless the user explicitly says otherwise.

Before every prompt send, verify the selected model/control is the boxed
`Pro 扩展` option in the composer. For each uploaded package, send exactly three
review requests using the agreed P1.2 adversarial soundness prompt, then wait for
responses. On heartbeat wakeups for this loop, only check whether GPT has replied
and then continue the local verification/apply loop if a response or package is
available.

Treat GPT Pro rate-limit / risk-control shaped replies as invalid review results.
A normal `Pro 扩展` review has substantive progress/status text above the
`已思考 ...` marker and the final report below it. If a reply has no substantive
text above the `已思考 ...` marker and only has the lower final text, classify it
as throttled/abnormal; do not count it as one of the three valid review replies,
do not treat its "no issue" claim as clean evidence, and retry later after the
rate-limit pressure eases.
Desktop ChatGPT and iPad ChatGPT can be rate-limited separately. If desktop-side
reviews show the throttled/abnormal shape while the user is available, stop the
loop and notify the user instead of sending more desktop requests; the user may
resend the three review requests from iPad. If the user is offline/unresponsive
and has not already provided valid replacement reviews, stop the loop by turning
off the heartbeat rather than burning more review attempts.

Recycle unused browser pages during this loop. Keep only active review conversations
that may still produce replies and the current Sources page when it is needed for
upload/download verification; close or release stale project pages, duplicate source
tabs, blank tabs, failed upload attempts, and completed intermediate pages.
For webpage-side network, loading, timeout, or missing-content problems during
this loop, use one recovery method: close the affected tab and reopen the
identical URL in a fresh tab before checking again. This includes read timeouts,
generic ChatGPT shells, missing conversation content, stalled pages, and ChatGPT
network-error stopped responses. Do not click `重试` / retry, do not keep
probing the same stale page object, and do not count a partial network-error
answer as a valid review result.

Generated proof outputs, checkpoints, blueprints, and certified delivery manifests
are intentionally guarded by preflight. Do not commit forbidden generated paths such
as `data/checkpoints/`, `data/blueprints/optimal_blueprint.json`,
`data/solutions/final_solution.json`, or
`data/solutions/certified_delivery_manifest.json`.
