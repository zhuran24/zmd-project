# IndustrialPlanner 70×70 Single-Base End-to-End Runbook

This is the operator runbook for the **current active IndustrialPlanner
contract**:

- active base: `valley4_protocol_core`
- active lot size: 70×70
- preserved but inactive: every other known base and the larger-base
  outer-deployment path

The goal is to make one human-readable path line up with the actual repository
contract:

`current source truth -> deterministic fixture planning/generation -> IndustrialPlanner export bundle -> validator/throughput -> support reports -> checked-in no-drift gates`

This runbook intentionally does **not** reactivate any other base. Those assets
remain `future_scope` until the single-base line is fully closed and a new base
contract is explicitly defined.

## One-command path

```bash
python scripts/run_industrial_planner_single_base_e2e.py \
  --run-dir .artifacts/industrial_planner_single_base_e2e
```

That command writes one self-contained working set under the chosen run
directory:

- `canonical/`
  - regenerated canonical fixture JSON
  - planning report JSON/Markdown
- `bundle/`
  - `industrial_planner.blueprint.json`
  - `industrial_planner.compatibility_manifest.json`
  - `validation_report.json` / `validation_report.md`
  - `throughput_report.json` / `throughput_report.md`
- `support_suite/`
  - regenerated canonical matrix / deployment matrix / overview files
- `checks/`
  - checked-in support-suite inventory summary JSON/Markdown/plain-text
  - checked-artifact family gate summary JSON/Markdown/plain-text
- `run_summary.json` / `run_summary.md` / `run_summary.txt`

Use `run_summary.md` as the primary reviewer handoff. It records the blocking
stage, failure classification, delivery-readiness verdict, and the role of each
artifact.

Once a run lands at `ready_for_single_base_delivery`, promote it into a fixed
versioned release with
`python scripts/build_industrial_planner_single_base_delivery_release.py ...`.
That second step is documented in
`docs/industrial_planner_single_base_delivery_release.md` and is where the
project now records the active single-base final delivery bundle/version.

## Manual path

If you need to run the stages one by one, use this order.

### 1. Regenerate the active canonical fixture

```bash
python scripts/build_industrial_planner_full_demand_fixture.py \
  --output data/examples/industrial_planner/full_demand_recipe_capacity_canonical_blueprint.json \
  --report-json data/examples/industrial_planner/generated_full_demand_bundle/full_demand_fixture_plan_report.json \
  --report-markdown data/examples/industrial_planner/generated_full_demand_bundle/full_demand_fixture_plan_report.md
```

This is the deterministic single-base planning/generation step. If this step
fails, there is no valid canonical source payload for the downstream export.

### 2. Export the IndustrialPlanner bundle

```bash
python scripts/export_industrial_planner_bundle.py \
  data/examples/industrial_planner/full_demand_recipe_capacity_canonical_blueprint.json \
  --output-dir data/examples/industrial_planner/generated_full_demand_bundle \
  --base-id valley4_protocol_core
```

This writes the target blueprint plus manifest/validator/throughput sidecars.

### 3. Rebuild the active support-report surface

```bash
python scripts/audit_industrial_planner_full_demand_support_suite.py \
  --output-dir data/examples/industrial_planner
```

This regenerates the strict canonical matrix, the companion deployment matrix,
and the umbrella overview for the active single-base contract.

### 4. Recheck the checked-in support-suite inventory

```bash
python scripts/audit_industrial_planner_full_demand_support_suite_inventory.py \
  --inventory data/examples/industrial_planner/full_demand_support_suite_inventory.json \
  --check
```

This tells you whether the checked-in support-report family is still in sync.

### 5. Recheck the repo-level checked-artifact family gate

```bash
python scripts/audit_industrial_planner_checked_artifact_suite.py \
  --family-inventory data/examples/industrial_planner/checked_artifact_family_inventory.json
```

This is the repo-level no-drift verdict for the active checked artifact family.

## What each artifact means

- `full_demand_recipe_capacity_canonical_blueprint.json`
  - regenerated **source truth for this run**
  - this is the canonical single-base payload used by the downstream exporter
- `full_demand_fixture_plan_report.*`
  - planning/generation evidence
  - if the workflow stops here, the failure belongs to the planning step
- `industrial_planner.blueprint.json`
  - the **actual target delivery blueprint** for IndustrialPlanner import
- `industrial_planner.compatibility_manifest.json`
  - translation/fallback/validation sidecar
  - explains how the exporter got there, but is **not** the blueprint itself
- `validation_report.*`
  - offline import/layout-health diagnostics
  - these are the real structural delivery blockers on the export side
- `throughput_report.*`
  - static recipe/capacity audit
  - this is **not** runtime simulation and **not** the exact proof artifact
- `full_demand_base_support_matrix.*`
  - strict canonical support view for the active contract
- `full_demand_deployment_path_matrix.*`
  - companion matrix that keeps dormant future-scope metadata visible without
    reactivating it
- `full_demand_support_overview.*`
  - the umbrella support summary reviewers should usually read first
- `support_suite_inventory_summary.*`
  - checked-in support-suite drift verdict
- `checked_artifact_suite_summary.*`
  - repo-level checked artifact drift verdict
- `run_summary.*`
  - one place that ties all of the above together and names the first blocking
    stage if the path does not close

## Failure classes used by the one-command workflow

- `planning_failed`
  - the deterministic fixture planner did not produce a valid canonical source
    payload
- `export_failed`
  - a canonical payload existed, but the IndustrialPlanner bundle could not be
    written
- `validation_failed`
  - the bundle exists, but import compatibility or layout health did not pass
- `throughput_not_proven_equivalent`
  - the bundle exists, but the static recipe/capacity audit is not at
    `proven_equivalent`
- `support_generation_failed`
  - the fresh support-report set could not be regenerated cleanly
- `checked_in_support_drift_detected`
  - the checked-in support-suite inventory is stale
- `checked_artifact_drift_detected`
  - the repo-level checked-artifact family gate is stale

## Validator interpretation

For this line, the delivery gate is:

- `is_import_compatible = true`
- `is_layout_healthy = true`

`is_clean = false` is still acceptable **when the remaining issue is only
non-fatal `port_warnings`**. That distinction matters because the current bundle
can still be structurally deliverable even when the validator keeps advisory
port warnings in the sidecar.

## What counts as “single-base delivery ready”

For this runbook, the line is considered delivery-ready only when all of the
following are true:

- planning step lands at `proven_equivalent`
- validator import/layout both pass
- throughput audit lands at `proven_equivalent`
- fresh support-suite outputs regenerate cleanly
- checked-in support-suite inventory is clean
- checked-artifact family gate is clean

That is intentionally stricter than “I can export a JSON file.”

## Honest boundary on exact full-scale status

This runbook helps close the **single-base delivery path**. It does **not** mean
that the full-scale 70×70 exact `CERTIFIED` terminal result is already checked
in.

The current honest statement remains:

- the single-base delivery bundle/support surface can be regenerated and checked
- the full-scale exact `CERTIFIED` end-state is still an open item

So this document is about making the active delivery chain reproducible and
reviewable, not about pretending the exact endgame is already solved.
