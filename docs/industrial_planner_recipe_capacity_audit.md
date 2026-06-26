# IndustrialPlanner 70×70 Single-Base Recipe / Capacity Audit

> **Boundary (2026-06-26):** This document describes the frozen IndustrialPlanner postprocess/adapter surface from the April 2026 delivery line, not the current P1.2 solver or authenticated release state. Here, “current” means current within that delivery surface. Nothing in this workflow may mint, infer, or publish proof-bearing `CERTIFIED`.

This document describes the checked-in static recipe / capacity audit surface
for the **current active IndustrialPlanner contract**:
`valley4_protocol_core` on the 70×70 base.

The repository still preserves other IndustrialPlanner bases and the
outer-deployment path for later work, but those assets are currently
`future_scope`. They are intentionally excluded from the active checked-in audit
and CI gate.

## Active contract

- active audited base: `valley4_protocol_core` (70×70)
- preserved dormant bases:
  - `valley4_infra_outpost` (40×40)
  - `valley4_rebuilt_command` (40×40)
  - `valley4_refugee_shelter` (40×40)
  - `wuling_tianwangping_aid` (50×50)
  - `wuling_protocol_core` (80×80)
- preserved dormant outer path: larger-base translation / bundle workflow

To reduce clutter, the three dormant 40×40 valley4 variants are grouped into a
single `future_scope` cluster in the checked-in support reports.

## What it proves

For the active 70×70 contract, the checked-in audit surface proves that the
canonical full-demand fixture:

- covers all 17 checked recipe-capacity rollups on the active base,
- stays compatible with the IndustrialPlanner exporter / validator path,
- can be regenerated deterministically through the checked-in support-suite
  workflow, and
- fails closed when the checked-in decision surface drifts.

The main checked-in reports are:

- `data/examples/industrial_planner/full_demand_base_support_matrix.{json,md}`
- `data/examples/industrial_planner/full_demand_deployment_path_matrix.{json,md}`
- `data/examples/industrial_planner/full_demand_support_overview.{json,md}`
- `data/examples/industrial_planner/full_demand_support_suite_inventory.json`
- `data/examples/industrial_planner/checked_artifact_family_inventory.json`

## What it does not prove

This audit surface does **not**:

- widen canonical truth beyond the current 70×70 single-base contract,
- promote outer-deployment artifacts into certified evidence,
- claim that the preserved 40×40 / 50×50 / 80×80 bases are currently supported
  by the active contract, or
- replace solver/runtime source-of-truth artifacts such as
  `rules/canonical_rules.json` or the certified preprocess files.

## Inputs

The active checked-in audit path depends on:

- `rules/canonical_rules.json`
- `data/preprocessed/generic_io_requirements.json`
- `data/examples/industrial_planner/full_demand_recipe_capacity_canonical_blueprint.json`
- `src/adapters/industrial_planner/*` export / validator / throughput logic
- `src/adapters/industrial_planner/base_registry.json` for the preserved full
  base inventory
- `scripts/industrial_planner_scope.py` for the active-vs-future-scope contract

## Main implementation pieces

- `scripts/audit_industrial_planner_full_demand_base_matrix.py`
  - canonical single-base support report
- `scripts/audit_industrial_planner_full_demand_deployment_matrix.py`
  - companion report that preserves the dormant outer path as `future_scope`
- `scripts/audit_industrial_planner_full_demand_support_suite.py`
  - umbrella workflow for the six checked-in base/deployment/overview files
- `scripts/audit_industrial_planner_full_demand_support_suite_inventory.py`
  - inventory-driven wrapper for the active single report set
- `scripts/audit_industrial_planner_checked_artifact_suite.py`
  - repo-level no-drift gate for the active support family

The dormant outer path remains preserved in:

- `scripts/audit_industrial_planner_outer_base_bundle.py`
- `scripts/audit_industrial_planner_outer_base_bundle_suite.py`
- `data/examples/industrial_planner/outer_base_bundle_inventory.json`
- `data/examples/industrial_planner/generated_outer_base_bundle/*`

Those files are intentionally out of the active CI-critical path.

## Bundle outputs

The active support-suite workflow writes six checked-in files under
`data/examples/industrial_planner`:

- `full_demand_base_support_matrix.json`
- `full_demand_base_support_matrix.md`
- `full_demand_deployment_path_matrix.json`
- `full_demand_deployment_path_matrix.md`
- `full_demand_support_overview.json`
- `full_demand_support_overview.md`

The inventory/gate layer then treats that one directory as the only active
checked report set.

## Usage

### Active path

```bash
python scripts/audit_industrial_planner_full_demand_support_suite.py \
  --output-dir data/examples/industrial_planner

python scripts/audit_industrial_planner_full_demand_support_suite.py \
  --check

python scripts/audit_industrial_planner_full_demand_support_suite_inventory.py \
  --inventory data/examples/industrial_planner/full_demand_support_suite_inventory.json \
  --check

python scripts/audit_industrial_planner_checked_artifact_suite.py \
  --family-inventory data/examples/industrial_planner/checked_artifact_family_inventory.json
```

### Explicit subset / future work

The report builders still accept explicit subsets when future work needs them.
For example, the preserved valley4/wuling transition slice can still be rebuilt
manually:

```bash
python scripts/audit_industrial_planner_full_demand_support_suite.py \
  --base-id valley4_protocol_core \
  --base-id wuling_protocol_core \
  --output-dir data/examples/industrial_planner/protocol_core_transition_support_suite
```

The dormant outer-bundle workflow also remains available for manual use, but it
is currently `future_scope` and not part of the active gate:

```bash
python scripts/audit_industrial_planner_outer_base_bundle.py \
  --output-dir data/examples/industrial_planner/generated_outer_base_bundle
```

## Report interpretation

- `proven_equivalent` inside the active checked-in reports means the current
  70×70 contract is satisfied for the audited base.
- `future_scope` means the base or path is preserved for later work but is not
  currently part of the active checked-in contract.
- Grouped future-scope rows are a presentation simplification only; the full
  preserved base ids still remain in `src/adapters/industrial_planner/base_registry.json`
  and in the JSON metadata of the checked-in reports.
