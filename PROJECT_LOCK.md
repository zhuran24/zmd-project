# PROJECT_LOCK.md

**Status**: CURRENT_LOCK  
**Updated**: 2026-04-14  
**Purpose**: Freeze exactness boundaries, source-of-truth rules, accepted invariants, and forbidden changes for the current repository state.  
**History**: Date-stamped engineering history lives in [CHANGELOG.md](CHANGELOG.md). If this file conflicts with older notes, this file wins.

## 1. Exactness Constitution

- `certified_exact` and `exploratory` are separate paths. Exploratory outputs must not be promoted as certified evidence.
- The exact empty-rectangle objective is `max_lex(area, min_side)`.
- `min_side >= 6` is a candidate admissibility rule, not an objective tie-break.
- `Phi(w, h)` is not the exact source of truth.
- `(area, width, height)` is not the exact source-of-truth comparator.
- Exact mode has no hard `50 power poles + 10 protocol storage boxes` cap. If that number appears anywhere, it is exploratory-only guidance.

## 2. Certified Source of Truth

The certified path is grounded in:

- `rules/canonical_rules.json` (now also carries consolidated preprocess recipe / target / commodity truth)
- `data/preprocessed/candidate_placements.json`
- `data/preprocessed/mandatory_exact_instances.json`
- `data/preprocessed/generic_io_requirements.json`
- artifact-hash-compatible campaign state
- provenance-complete exact-safe cuts

The following remain additive postprocess artifacts and must not redefine internal solve schemas:

- `data/solutions/final_solution.json`
- `data/blueprints/optimal_blueprint.json`
- `data/solutions/certified_delivery_manifest.json`
- generated viewer/report sidecars such as `viewer_report.json`
- compatibility export bundles such as `data/exports/industrial_planner/*`
- adapter-side outer deployment sidecars / validator probes for IndustrialPlanner larger-base experiments
- neutral interchange contracts under `src/interchange/*`
- build-time / export-time adapters under `src/adapters/*`
- build-time preprocess overlays such as `rules/preprocess_plan.json` and `src/interchange/preprocess_context.py` (currently cycle groups / utility operations / optional future overrides only)

## 2A. IndustrialPlanner Active Scope

- The current certified IndustrialPlanner support contract targets `valley4_protocol_core` (70×70) exclusively.
- The other known IndustrialPlanner bases (`valley4_infra_outpost`, `valley4_rebuilt_command`, `valley4_refugee_shelter`, `wuling_tianwangping_aid`, and `wuling_protocol_core`) are preserved as `future_scope` and are not part of the active checked-in audit / CI contract.
- The checked-in full-demand base matrix, deployment-path matrix, umbrella overview, support-suite inventory, and checked-artifact gate must default to that single active 70×70 base.
- The outer-deployment subsystem for larger-base translation remains adapter-side `future_scope`: it may stay in the repository, but it must not be treated as active certified evidence or as part of the default CI-critical path until explicitly reactivated.

## 3. Accepted Invariants

- Best certified result is monotonic across campaign persistence and resume.
- `final_solution.json`, `optimal_blueprint.json`, and `certified_delivery_manifest.json` must be derived from the same best certified result when one exists.
- Optional compatibility exports must be derived from the canonical blueprint and must not become the source of truth for solver/runtime consumers.
- Postprocess manifest/export mappings used to bridge translated larger-base exports remain adapter-side evidence only and must not be promoted into certified proof.
- Production parallel scheduling uses a coordinator-only writer with disjoint candidate waves.
- Optional frontier probe mode is an exact-safe scheduling hint only and must not replace completeness requirements.
- Global pooling semantics for shared boundary/core resources must remain commodity-aggregated.
- A fully enclosed legal empty rectangle remains allowed; exterior connectivity is not part of the exact contract.

## 4. Forbidden Changes

- Reintroducing exploratory caps as exact-mode bounds.
- Treating exploratory artifacts, legacy cuts, or diagnostic flow checks as certified proof.
- Changing campaign, artifact, or proof schemas without explicitly updating the lock/spec/test boundary together.
- Rebinding globally pooled resources into per-line or per-instance hard bindings without a new exact proof basis.
- Adding any exterior-path requirement for the ghost rectangle.
- Enabling `EXACT_POWER_PLACEMENT_SUBPROBLEM=1` in any certified / production campaign path. The power-pole subproblem feature flag is exploratory only: the current infeasible cut omits the selected ghost anchor literal (over-prune across ghost alternatives), and the feasible-path injects a single arbitrary pole layout without exhausting pole alternatives before cutting the upstream master layout. The production readiness gate and `scripts/run_campaign_linux.sh` both block when the env var is set; do not bypass them.

## 5. Allowed Changes

- Exact-safe lower bounds, dominance rules, reuse, caching, and scheduling improvements.
- Optional frontier probes that evaluate legitimate potential-domain candidates without weakening proof semantics.
- Additive postprocess exports, viewer/report sidecars, and delivery summaries.
- Additive neutral contract layers in `src/interchange/*` and build-time/export-time adapters in `src/adapters/*`.
- Adapter-side outer deployment planning/probing for larger IndustrialPlanner bases, plus optional exporter/throughput-manifest bridge metadata for those translated exports, may remain preserved as future-scope tooling provided those artifacts stay postprocess-only and are not promoted as certified evidence.
- Documentation, governance, provenance, and regression coverage improvements.
- Runtime discoverability improvements that do not alter solver semantics.

## 6. Update Rule

If a change affects exact boundaries, runtime roles, or certified output meaning, update:

1. `PROJECT_LOCK.md`
2. `FILE_STATUS.md`
3. the relevant spec(s)
4. the relevant regression tests
