---
status: CURRENT_CODE_ALIGNED
source_of_truth: main.py, src/search/outer_search.py, src/search/exact_campaign.py, src/search/certified_surface.py, src/search/exact_parallel_scheduler.py
last_verified_against: 2026-06-26
owner: search-runtime
---

# 11 Pipeline Orchestration

## 1. Scope and release state

This specification describes the current `certified_exact` orchestration in the working tree.
It does not declare P1.2 closed. The owner gate in
`data/review_gates/phase_1_2_spike_close.json` is still fail-closed, so no public
`CERTIFIED` delivery may be published from this tree unless that authoritative gate is explicitly
closed by its owner.

## 2. Inputs and campaign identity

The exact path consumes and hash-binds, among other project inputs:

- `rules/canonical_rules.json`;
- `rules/preprocess_plan.json`;
- `data/preprocessed/candidate_placements.json`;
- `data/preprocessed/mandatory_exact_instances.json`;
- `data/preprocessed/generic_io_requirements.json`;
- proof-bearing source and obligation material named by the campaign contract.

`candidate_placements.json` is present in this working tree. Its expected current artifact is
45,773,799 bytes with SHA256
`adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`.
A different byte set reopens resume compatibility; old campaign evidence must not be reused across
an artifact-hash mismatch.

## 3. Objective and candidate domain

The exact objective is `max_lex(area, min_side)`. The default certified domain also enforces the
project admissibility rule `min_side >= 6`; that lower bound is not a replacement objective.
Exploratory caps, hints, probes and compatibility exports do not become formal evidence.

## 4. Three authority layers

### 4.1 Producer

`src/search/outer_search.py` evaluates candidates and may reach the internal per-candidate verdict
`RUN_STATUS_CERTIFIED`. When the strict frontier is exhausted, the producer commits a
`CANDIDATE_PROPOSED` record plus replay, frontier, sink and fixed-witness material. It does not mint
a durable terminal `CERTIFIED` state and does not publish canonical delivery files.

### 4.2 Supervisor mint

`ExactCampaign.supervisor_seal()` is the sole durable terminal mint. It reopens canonical campaign
bytes from disk, checks proposal identity and current hashes, replays terminal evidence, verifies the
fixed-witness capsule and rechecks disk state before and after the transition. Ordinary
`mark_campaign_stopped(..., "CERTIFIED")` calls are rejected.

The sealed campaign checkpoint is proof authority, but it is not by itself a public delivery
surface. The current repository has no production supervisor CLI/launcher: `main.py` ends after
writing `CANDIDATE_PROPOSED`, and repository callers of `supervisor_seal()` are tests. An operator
must not infer a seal from a successful solve process.

### 4.3 Verified public publisher

`publish_verified_certified_delivery_surface()` is the sole canonical publisher. It requires a
supervisor-sealed, disk-current campaign, valid terminal evidence, current exact artifacts and a
closed P1.2 publish gate. It then transactionally writes and revalidates:

- `data/solutions/final_solution.json`;
- `data/blueprints/optimal_blueprint.json`;
- `data/solutions/certified_delivery_manifest.json`.

Publication failure clears the canonical set rather than leaving a partial or stale public surface.
Generic serializers, report/viewer builders, adapters and compatibility exporters may write
non-authoritative copies only; they cannot mint or preserve public `CERTIFIED` authority.

## 5. Candidate solve topology

For the current theorem, placement is followed by binding and exact routing checks. Power and
terminal whole-layout checks are part of the accepted evidence path. The continuous
`src/models/flow_subproblem.py` model is diagnostic-only: its verdict neither gates certified
acceptance nor creates a proof-bearing cut.

`src/search/benders_loop.py` may return internal `RUN_STATUS_CERTIFIED` for one candidate. That
value is not the same thing as campaign terminal certification or public publication.

## 6. Persistent state and monotonicity

`ExactCampaign` owns proposal/candidate records, artifact hashes, exact-safe evidence, terminal
frontier material, fixed-witness material and final stop state. A worse candidate cannot replace a
better accepted candidate. `UNKNOWN`, `UNPROVEN`, worker failure or budget exhaustion cannot be
rewritten as frontier exhaustion.

After PR1, producer-side “best” data remains proposal material until supervisor sealing succeeds.
Documentation and telemetry must not call it public certified output before that transition.

## 7. Parallel scheduler and workers

The parallel path is coordinator-owned and wave-based. Workers evaluate candidates; the
coordinator merges wave results and is the campaign-state writer. Candidate identity and wave
membership are rechecked before evidence is accepted. A worker failure does not authorize partial
frontier completion.

Worker-count precedence remains stage-specific environment variable, then `EXACT_CP_SAT_WORKERS`,
then built-in defaults in `src/models/cp_sat_worker_config.py`. For host-sizing guidance and
worker/process trade-offs, see `docs/parallel_configuration.md`.

## 8. Probes and telemetry

`--frontier-probe-mode off|auto` changes scheduling only. Probe outcomes and telemetry are
non-authoritative diagnostics. They do not alter the objective, frontier exhaustion rule,
supervisor checks or publish gate. For the frontier-probe workflow and the `selection_reason`
taxonomy, see `docs/frontier_probe_strategy.md`.

## 9. Open release work

The working tree contains the PR1 producer/supervisor split, fixed-witness terminal verification,
whole-layout independent infeasibility reverify, publish-open gate and central publisher. P1.2 still
has open work, including a supported production supervisor invocation surface, PR2 TCB reduction,
immutable package materialization and review-policy coverage, plus the blocked owner gate. These
open items must remain visible in release documents.
