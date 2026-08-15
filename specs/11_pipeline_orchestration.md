---
status: CURRENT_CODE_ALIGNED
source_of_truth: main.py, src/search/outer_search.py, src/search/exact_campaign.py, src/search/certified_surface.py, src/search/exact_parallel_scheduler.py
last_verified_against: 2026-08-11
state_projection: docs/CURRENT.md
owner: search-runtime
---

# 11 Pipeline Orchestration

## 1. Scope and release state

This specification describes the stable `certified_exact` orchestration contract. It deliberately
omits mutable gate values, decision IDs, input hashes, research bounds, cut-family progress, and
attempt counts. Read [docs/CURRENT.md](../docs/CURRENT.md) for the checked machine-state
projection and [docs/CATALOG.md](../docs/CATALOG.md) for stable claims, decisions, and evidence.

A phase gate that permits entry does not itself publish a delivery. Public `CERTIFIED` output still
requires a disk-current supervisor seal, every verified-publisher precondition, and the canonical
transactional publisher.

## 2. Inputs and campaign identity

The exact path consumes and hash-binds, among other project inputs:

- `rules/canonical_rules.json`;
- `rules/preprocess_plan.json`;
- `data/preprocessed/candidate_placements.json`;
- `data/preprocessed/mandatory_exact_instances.json`;
- `data/preprocessed/generic_io_requirements.json`;
- proof-bearing source and obligation material named by the campaign contract.

Current byte identities and source floors belong to `data/proof_obligations/`, the external-artifact
registry, campaign manifests, and their checkers. They must not be copied into this prose spec.
A byte mismatch reopens resume compatibility; evidence from one input closure cannot be reused
under another.

Campaign identity includes the complete `generic_input_slots_by_operation` map from the same
hash-bound plan snapshot. The map is threaded and compared atomically; a scalar shortcut or a
second unbound plan read cannot define compatibility.

## 3. Objective and candidate domain

The exact objective, grid, emptiness semantics, and admissibility floor come from
`rules/canonical_rules.json`. Heuristic scores, exploratory caps, hints, probes, and compatibility
exports do not become formal evidence. The six gating predicates and public theorem scope are
specified in `docs/项目说明/01_overview.md`.

## 4. Three authority layers

### 4.1 Producer

`src/search/outer_search.py` evaluates candidates and may reach an internal per-candidate verdict.
When the strict frontier is exhausted, the producer commits a `CANDIDATE_PROPOSED` record plus
replay, frontier, sink, and fixed-witness material. It does not mint a durable terminal `CERTIFIED`
state and does not publish canonical delivery files.

### 4.2 Supervisor mint

`ExactCampaign.supervisor_seal()` is the sole durable terminal mint. It reopens canonical campaign
bytes from disk, checks proposal identity and current source/input closure, replays terminal evidence,
verifies the fixed-witness capsule, and rechecks disk state before and after the transition. Ordinary
producer-side stop-state writes cannot replace this transition.

The supported production supervisor entry is the standalone command
`scripts/run_supervisor_seal.py`, driven by a proposal-ready marker. `main.py` does not silently turn
a successful solve process into a supervisor seal.

### 4.3 Verified public publisher

`publish_verified_certified_delivery_surface()` is the sole canonical publisher. It requires a
supervisor-sealed, disk-current campaign, valid terminal evidence, current exact inputs and source
closure, and an owner-controlled publish gate that allows publication. It transactionally writes and
revalidates:

- `data/solutions/final_solution.json`;
- `data/blueprints/optimal_blueprint.json`;
- `data/solutions/certified_delivery_manifest.json`.

Publication failure clears the canonical set rather than leaving a partial or stale public surface.
Generic serializers, report/viewer builders, adapters, and compatibility exporters may write
non-authoritative copies only.

The publisher derives blueprint `active_ports` only from the terminal fixed-witness audit's
digest-bound normalized `port_specs`. It never promotes every physical pose slot to active. Unknown,
duplicate, out-of-grid, wrong-pose, or commodity-inconsistent active ports block publication.

## 5. Candidate solve topology

For the current theorem, placement is followed by binding and exact routing checks. Generic-input
finished goods are routed from producer outputs to actual provider-instance physical inputs.
Provider counts, physical port counts, demand, and any instance-aware lower bound are read from the
same frozen input closure rather than repeated here.

Power and terminal whole-layout checks are part of the accepted evidence path.
`src/models/flow_subproblem.py` is diagnostic-only: its verdict neither gates certified acceptance
nor creates a proof-bearing cut. A candidate-layer success is not the same thing as campaign
terminal certification or public publication.

## 6. Persistent state and monotonicity

`ExactCampaign` owns proposal/candidate records, artifact hashes, exact-safe evidence, terminal
frontier material, fixed-witness material, and final stop state. A worse candidate cannot replace a
better accepted candidate. `UNKNOWN`, `UNPROVEN`, worker failure, or budget exhaustion cannot be
rewritten as frontier exhaustion.

Producer-side “best” data remains proposal material until supervisor sealing succeeds.
Documentation and telemetry must not call it public certified output before that transition.

## 7. Parallel scheduler and workers

The parallel path is coordinator-owned and wave-based. Workers evaluate candidates; the coordinator
merges wave results and is the campaign-state writer. Candidate identity and wave membership are
rechecked before evidence is accepted. A worker failure does not authorize partial frontier
completion.

Worker-count precedence remains stage-specific environment variable, then
`EXACT_CP_SAT_WORKERS`, then built-in defaults in `src/models/cp_sat_worker_config.py`. For host
sizing and worker/process trade-offs, see `docs/parallel_configuration.md`.

## 8. Probes and telemetry

`--frontier-probe-mode off|auto` changes scheduling only. Probe outcomes and telemetry are
non-authoritative diagnostics. They do not alter the objective, frontier-exhaustion rule, supervisor
checks, or publish gate. See `docs/frontier_probe_strategy.md` and
`specs/21_frontier_probe_and_campaign_telemetry.md`.

## 9. Current-state lookup

Do not maintain a second status table in this spec.

- gate, canonical summary, exact checked-in result, and selected active claims:
  [docs/CURRENT.md](../docs/CURRENT.md)
- cut lifecycle, production attach boundary, research ledgers, and owner decisions:
  [docs/CATALOG.md](../docs/CATALOG.md)
- future sequencing:
  [docs/项目说明/ROADMAP.md](../docs/项目说明/ROADMAP.md)
- dated chronology and migrated historical coordinates:
  [docs/项目说明/HISTORY.md](../docs/项目说明/HISTORY.md)
- machine gate and proof inputs: `data/review_gates/` and `data/proof_obligations/`

A current-state change updates the machine or structured source first, then regenerates the human
projection. It does not require hand-editing this orchestration contract.
