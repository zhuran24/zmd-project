---
status: CURRENT_CODE_ALIGNED
source_of_truth: code-first; main.py, src/search/outer_search.py, src/search/exact_campaign.py, src/search/exact_parallel_scheduler.py, src/models/cp_sat_worker_config.py
last_verified_against: 2026-03-26
owner: search-runtime
---

# 11 Pipeline Orchestration

## 1. Purpose

This spec records the current production orchestration contract for `certified_exact`.
If runtime behavior diverges, code is the immediate source of truth and this file
must be updated in the same change.

## 2. Required Inputs

The certified path consumes these frozen preprocess artifacts:

- `rules/canonical_rules.json`
- `data/preprocessed/candidate_placements.json`
- `data/preprocessed/mandatory_exact_instances.json`
- `data/preprocessed/generic_io_requirements.json`

Artifact hashes are part of the campaign resume contract.

## 3. Exact Objective and Candidate Domain

The exact empty-rectangle goal is:

`max_lex(area, min_side)`

Notes:

- `min_side >= 6` is an admissibility rule for the default certified candidate domain.
- `min_side >= 6` is not part of the lexicographic objective.
- `Phi(w, h)` is not the certified objective.
- `(area, width, height)` is not the certified source-of-truth comparator.

## 4. Campaign Behavior

`ExactCampaign` is the persistent state owner for:

- candidate status
- artifact hashes
- exact-safe cuts
- best certified result
- final stop reason and terminal status

Best certified result is monotonic:

- a worse certified candidate cannot replace a better certified result
- `UNKNOWN`, `UNPROVEN`, `INFEASIBLE`, or worker failure cannot erase an existing best certified result

## 5. Parallel Scheduler

The production parallel path is coordinator-owned and wave-based:

- coordinator is the single writer for campaign state and final result artifacts
- workers only execute candidate evaluation
- candidates dispatched within the same wave are disjoint
- frontier is recomputed only after the wave is merged

This changes runtime scheduling only. It does not change the exact mathematical semantics.

## 6. Worker Configuration

Runtime source of truth: `src/models/cp_sat_worker_config.py`

Default CP-SAT worker counts:

- `master = 8`
- `local_capacity = 8`
- `binding = 4`
- `routing = 8`

Environment-variable precedence:

1. stage-specific env
   - `EXACT_MASTER_CP_SAT_WORKERS`
   - `EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS`
   - `EXACT_BINDING_CP_SAT_WORKERS`
   - `EXACT_ROUTING_CP_SAT_WORKERS`
2. global env
   - `EXACT_CP_SAT_WORKERS`
3. built-in defaults

`main.py` prints the resolved worker profile once at startup. The launcher scripts in
`scripts/*.ps1` are wrappers around these knobs; they do not redefine precedence.

For memory envelopes, recommended `parallel_processes × workers` combinations, and the
48GB baseline guidance, see `docs/parallel_configuration.md`.

## 7. Certified vs Exploratory Boundary

`certified_exact` must not use exploratory-only caps or artifacts as formal evidence.

If `50 power poles + 10 protocol storage boxes` is mentioned anywhere, it is exploratory-only
guidance and not an exact-mode hard cap.

## 8. Outputs

The current certified delivery artifacts are derived from the same best certified result:

- `data/solutions/final_solution.json`
- `data/blueprints/optimal_blueprint.json`
- `data/solutions/certified_delivery_manifest.json`

If no certified result exists, delivery metadata may still be emitted, but certified payloads
must not be fabricated.

## 9. Optional Frontier Probe Mode

`main.py` also exposes an exact-safe scheduling toggle:

- `--frontier-probe-mode off|auto`

Current behavior:

- `off` keeps the historical frontier-only schedule.
- `auto` may insert one medium-area non-frontier probe before the normal frontier sweep.

Probe mode is scheduling-only. It does not change the exact objective, the proof contract,
or the campaign termination conditions. For operator guidance and the manual two-step probe
workflow, see `docs/frontier_probe_strategy.md`.

## 10. Telemetry

Campaign telemetry records selection reasons and probe activity additively.
Probe-specific fields are runtime diagnostics only and do not redefine certified semantics.
