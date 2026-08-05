---
status: CURRENT_CODE_ALIGNED
source_of_truth: main.py, src/search/outer_search.py, src/search/exact_campaign.py, src/search/certified_surface.py, src/search/exact_parallel_scheduler.py
last_verified_against: 2026-07-18
owner: search-runtime
---

# 11 Pipeline Orchestration

## 1. Scope and release state

This specification describes the current `certified_exact` orchestration in the working tree.
P1.2 was explicitly closed by the owner on 2026-07-07:
`data/review_gates/phase_1_2_spike_close.json` records
`status="closed_manual_owner_decision"` and `next_phase_entry.allowed=true`. That machine state does
not itself publish a delivery: public `CERTIFIED` output still requires a disk-current supervisor seal,
all verified-publisher preconditions, and the canonical transactional publisher.

## 2. Inputs and campaign identity

The exact path consumes and hash-binds, among other project inputs:

- `rules/canonical_rules.json`;
- `rules/preprocess_plan.json`;
- `data/preprocessed/candidate_placements.json`;
- `data/preprocessed/mandatory_exact_instances.json`;
- `data/preprocessed/generic_io_requirements.json`;
- proof-bearing source and obligation material named by the campaign contract.

The current frozen pins are `canonical_rules.json` at 18,137 bytes / SHA256
`c3666d78d5dd1329514c7813be9f91f09cb3ce7b94907ef5b6ce746c9bcbbbd5`,
`preprocess_plan.json` at 1,383 bytes / SHA256
`5c669c4fa48d2ed77a3283f06c1d5f97f7542c92253c41ba31fbaba0b313c4ee`, and
`candidate_placements.json` at 54,467,709 bytes / SHA256
`f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3`.
The 45,774,305-byte / `a914ba6348544b7ef44d0834629c6dcf90f39fa5564e0cd4c50af6af550c444b`,
45,773,799-byte / `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`,
53,594,995-byte / `d5e3911fc1bc7c0ab48d67b981d28e8090741b04884c475e78dc0e128ca4683f`,
and 53,595,501-byte / `78e2bcf0777db8523aa767ee689ba7c3e65ecf7ecc20642627876d8d42fa3fef`
candidate artifacts form a superseded, hash-incompatible historical chain.
A different byte set reopens resume compatibility; old campaign evidence must not be reused across
an artifact-hash mismatch.

Campaign identity includes the complete `generic_input_slots_by_operation` map parsed from that
same hash-bound plan snapshot. The map is threaded and compared atomically; a box-only scalar or a
second plan read cannot define resume compatibility.

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
surface. The production supervisor entry is the standalone command `scripts/run_supervisor_seal.py`
(driven from a proposal-ready marker, `349c56c`, PR2 #7); `main.py` still ends after writing
`CANDIDATE_PROPOSED` and does not seal, and no real production campaign→seal run has been recorded yet. An operator
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

The publisher derives blueprint `active_ports` only from the terminal fixed-witness audit's
digest-bound normalized `port_specs`. It never promotes every physical pose slot to active. The
delivery-manifest currentness check rebuilds the expected blueprint from the same carrier, so an
unknown, duplicate, out-of-grid, wrong-pose or commodity-inconsistent active port blocks publication.

## 5. Candidate solve topology

For the current theorem, placement is followed by binding and exact routing checks. Generic-input
finished goods are routed from producer outputs to provider physical inputs. `box_sink` exposes
3 physical inputs and 3 physical outputs, while the mandatory core exposes 14 inputs and 6 outputs.
The provider-aware, instance-aware box lower bound is currently 0 because demand 2 is covered by the
real mandatory core's 14 input ports; uninstantiated templates earn no credit. Power and terminal
whole-layout checks are part of the accepted evidence path. The continuous
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

## 9. Current post-P1.2 / release-time work

The working tree contains the PR1 producer/supervisor split, fixed-witness terminal verification,
whole-layout independent infeasibility reverify, owner-closed publish gate, central publisher, and the
supported standalone supervisor invocation `scripts/run_supervisor_seal.py`. P1.3 cut integration is
partially landed: F1/F5/F6/F7 direct attach exists behind an unsafe/default-off gate and Stage B B0/B1
is complete; B2-B5, PIC C/D/E and B6 owner promotion remain (the B1.5 typed platform landed 2026-07-11). Release-time backlog also includes the
explicitly deferred PR2 deliberate-insider TCB/loader/read-once hardening, immutable package materialization,
review-policy coverage, and production-byte re-pinning. These are not an “owner gate still blocked” claim.
