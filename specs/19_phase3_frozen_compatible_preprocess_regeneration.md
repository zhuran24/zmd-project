---
status: CURRENT_CODE_ALIGNED
source_of_truth: code-first; rules/canonical_rules.json, rules/preprocess_plan.json, src/interchange/preprocess_context.py, src/preprocess/*
last_verified_against: 2026-03-25
owner: preprocess-regeneration
---
# 19 Frozen-Compatible Preprocess Regeneration

## 1. What this phase does

This path upgrades preprocess regeneration from hard-coded Python logic to a context-driven path while keeping the current frozen artifacts and certified runtime boundary intact.

## 2. What changed

The repository now includes:

- `rules/preprocess_plan.json`
- `rules/preprocess_plan.schema.json`
- `src/interchange/preprocess_context.py`
- `scripts/build_current_preprocess_context.py`

And the following preprocess modules read from that context layer:

- `src/preprocess/demand_solver.py`
- `src/preprocess/instance_builder.py`
- `src/preprocess/operation_profiles.py`

## 3. Current consolidation state

The repository has now performed a **partial canonical-rules consolidation**:

- `canonical_rules.json` carries the 17 real preprocess recipes
- `canonical_rules.json` carries `production_targets`
- `canonical_rules.json` carries `commodity_metadata`
- `preprocess_plan.json` remains the additive plan for cycle groups and utility operations only — canonical recipe/target/commodity overrides are rejected fail-closed (R6-F-01), and the plan is bound into the exact campaign hash closure + preflight frozen registry

This reduces duplicated truth while keeping the certified runtime input surface unchanged.

## 4. Frozen-compatible guarantee

The success criterion remains:

- remove recipe/template/profile hardcoding from preprocess code paths
- regenerate the same frozen business results
- keep certified runtime reading the same frozen preprocess artifacts

## 5. Shadow parity and audit outputs

The repository provides a build-time audit path through:

- `data/solutions/current_preprocess_context.json`
- `data/solutions/preprocess_context_diff_report.json`
- `data/solutions/preprocess_context_diff_report.md`

These files document whether the context-driven regeneration path matches the frozen preprocess artifacts on disk.

## 6. Explicit non-goals of this phase

This path does **not**:

- modify `src/models/*` or `src/search/*`
- switch certified runtime to read `NormalizedCatalog`
- change the certified runtime's default frozen preprocess input artifacts
- widen exploratory caps into certified exact mode
