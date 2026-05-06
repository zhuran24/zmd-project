---
spec_id: 23
status: current_code_aligned
source_of_truth: code-first; src/adapters/base_planner/outer_deployment_plan.py, src/adapters/industrial_planner/deployment_transform.py, src/adapters/industrial_planner/export_blueprint.py, src/adapters/industrial_planner/throughput_audit.py, src/adapters/industrial_planner/outer_export_probe.py, scripts/build_industrial_planner_outer_base_plan.py, scripts/probe_industrial_planner_outer_base_export.py, scripts/audit_industrial_planner_outer_base_bundle.py, scripts/audit_industrial_planner_outer_base_bundle_suite.py, scripts/audit_industrial_planner_full_demand_deployment_matrix.py, scripts/audit_industrial_planner_full_demand_support_suite.py, scripts/audit_industrial_planner_full_demand_support_suite_inventory.py, scripts/audit_industrial_planner_checked_artifact_suite.py, data/examples/industrial_planner/full_demand_support_suite_inventory.json, data/examples/industrial_planner/outer_base_bundle_inventory.json, data/examples/industrial_planner/checked_artifact_family_inventory.json, .github/workflows/industrial_planner_checked_artifacts.yml
---

# Spec 23 — IndustrialPlanner Outer Base Planning Representation

## 1. Scope

This spec defines an **adapter-side / postprocess-only** representation for
projecting the existing canonical 70×70 IndustrialPlanner fixture into a larger
real base without widening the canonical blueprint schema or the
`certified_exact` proof boundary.

The current implementation is intentionally narrow:

- canonical blueprint truth stays at 70×70;
- the outer plan is a sidecar only;
- the probe path is validator-grounded and does not become certified evidence;
- translated export/manifest/throughput bridges remain postprocess-only and do not widen canonical truth;
- no change is made to `src/models/*`, `src/search/*`, campaign schemas, or
  artifact-hash semantics.

## 2. Representation

`OuterBaseDeploymentPlan` records:

- base id / lot size / canonical contract size;
- inner-island origin and moat thickness;
- true-edge boundary assignments;
- straight moat-only connector reservations;
- explicit witness reservations;
- canonical-instance -> exported-origin/rotation mappings;
- probe diagnostics;
- postprocess manifest export mappings for translated target-side pairings.

For equal 70×70 bases the plan degenerates to an identity transform with zero
moat and no connector reservations. For larger bases the current planner picks a
deterministic centered inner-island origin.

## 3. Boundary semantics

The current plan builder preserves the existing canonical 70×70 facility truth
and derives true-edge deployment as follows:

- non-boundary facilities are translated by the inner-island offset;
- pure-output boundary ports are re-oriented so their required bus face stays
  in-lot when the selected base does not expose a matching foundation bus edge;
- pure-input boundary ports keep their truthful true-edge handoff, but when the
  selected edge lacks matching foundation bus the exported loader is staged 4
  cells inboard and paired with an explicit grouped in-lot bus-witness strip so
  validator-visible bus-side adjacency is still satisfied without widening the
  canonical schema.

## 4. Export / throughput bridge semantics

`outer_export_probe.py` still materializes the translated export view and runs
the real IndustrialPlanner validator on it.

In addition, `export_blueprint.py` can now consume an `OuterBaseDeploymentPlan`
directly. When it does, the compatibility manifest gains a
`postprocess_export_mappings` section that records canonical-instance ids,
translated target origins, target rotations, target type ids, and mapping mode.
`throughput_audit.py` consumes that section before falling back to the older
anchor-equality heuristic, which lets the static audit keep its canonical-truth
pairing surface even after boundary devices move to the true lot edge.

Those bridges remain sidecar-only: validator health still caps the top-level
status, and none of this metadata becomes certified evidence.

Current known result on `wuling_protocol_core`:

- the plan reaches the true 80×80 lot edge;
- pure outputs can be re-oriented and given in-lot grouped bus witnesses;
- the two pure-input boundary loaders can be staged 4 cells inboard while their
  boundary assignments still point at the true lot edge, with grouped in-lot
  bus witnesses covering the missing base-side adjacency;
- translated export/manifest/throughput sidecars preserve all 17 recipe-capacity
  rollups and all 4 boundary-commodity proofs;
- the translated export now validates cleanly (`import-compatible=True`,
  `layout-healthy=True`) and the throughput sidecar lands at
  `proven_equivalent`.

The outer probe/exporter status on that path is currently
`validator_clean_outer_export`.

The repository also carries an additive `full_demand_deployment_path_matrix`
report that keeps the canonical-only 70×70 matrix intact while surfacing the
best available checked-in path once the adapter-side outer deployment path is
considered. A companion `full_demand_support_overview` umbrella report now
regenerates both matrices together and highlights which bases actually change
status across those two decision surfaces. That same support-suite workflow now
also exposes a no-drift `--check` mode that recomputes all six checked-in
JSON/Markdown reports in memory and fails closed if the checked-in decision
surface has gone stale.

The checked-in translated `generated_outer_base_bundle/*` example now has a
parallel no-drift workflow too. `audit_industrial_planner_outer_base_bundle.py`
rebuilds an individual outer deployment plan, probe, translated export,
manifest, validator report, and throughput report together, and it can compare
that artifact set against a checked-in example directory in one shot. To keep
that path reproducible, the IndustrialPlanner compatibility manifest now uses
the canonical blueprint `export_timestamp` as its `generated_at` field instead
of a fresh wall-clock timestamp.

The repository now also carries a checked-in
`data/examples/industrial_planner/full_demand_support_suite_inventory.json` and
an inventory-driven
`audit_industrial_planner_full_demand_support_suite_inventory.py` workflow.
That suite consumes every listed strict/additive report set instead of
hard-coding a single output directory, which makes the decision-surface gate
scale cleanly if more checked-in report sets are added later.

The current checked-in support-suite inventory intentionally covers two
decision-surface shapes:

- `default_full_demand_support_suite` keeps the full all-known-base strict /
  additive report set checked in at the root fixture directory;
- `protocol_core_transition_support_suite` keeps a focused overlapping subset
  for `valley4_protocol_core` + `wuling_protocol_core`, so the support-suite
  gate now exercises both full-universe and focused-subset report sets while
  tracking unique audited-base coverage and repeated-base overlap in its suite
  summary.

In parallel, the repository also carries a checked-in
`data/examples/industrial_planner/outer_base_bundle_inventory.json` and an
inventory-driven `audit_industrial_planner_outer_base_bundle_suite.py`
workflow. That suite consumes every listed outer-deployment example instead of
hard-coding a single directory, which makes the outer-path gate scale cleanly
if more translated bundles or degenerate identity bundles are checked in later.

The current checked-in outer-bundle inventory intentionally covers both of the
implemented shapes:

- `wuling_protocol_core_full_demand_outer_bundle` exercises the real translated
  larger-base path on an 80×80 lot;
- `valley4_protocol_core_identity_outer_bundle` exercises the zero-moat,
  zero-connector, 273-identity-mapping degenerate case on the canonical-size
  70×70 lot while still going through the same plan/probe/export/audit bundle
  workflow.

A higher-level `audit_industrial_planner_checked_artifact_suite.py` gate now
reads a checked-in `checked_artifact_family_inventory.json` registry and runs
every listed family-specific no-drift leg together, so CI can fail closed when
either the strict / additive decision reports or any checked-in translated
outer example drifts away from current code without hard-coding separate
family wiring in the top-level gate. That CLI can now emit JSON, Markdown, and
plain-text summaries in one run, and the checked-in GitHub Actions workflow
`.github/workflows/industrial_planner_checked_artifacts.yml` uses those
sidecars after running focused IndustrialPlanner regressions on relevant
changes, including the checked-artifact gate coverage. All of those reports
remain decision-support only and do not widen canonical truth or certified
evidence.

## 5. Non-goals

This spec does **not**:

- widen the canonical blueprint schema;
- change the certified solver contract;
- promote validator or probe output into certified evidence;
- add runtime flow simulation or promote translated throughput sidecars into certified proof;
- solve smaller-than-70×70 bases that already fail on manufacturing-area
  shortfall.
