---
status: CURRENT_CODE_ALIGNED
source_of_truth: src/interchange/preprocess_context.py, rules/canonical_rules.json, rules/preprocess_plan.json, src/preprocess/*
last_verified_against: 2026-03-25
owner: preprocess-context
---
# 18 Preprocess Context Contract

## 1. Purpose

`PreprocessContext` is the build-time contract that feeds preprocess regeneration.
It removes recipe / template / port-profile hardcoding from Python code without widening the certified runtime truth surface.

## 2. Inputs

`PreprocessContext` is currently built from two layers:

1. `rules/canonical_rules.json`
   - grid / time / logistics globals
   - facility templates
   - the 17 real preprocess recipes
   - `production_targets`
   - `commodity_metadata`
2. `rules/preprocess_plan.json`
   - cycle groups
   - utility operation slot declarations

The plan layer is **additive-only**. Recipe / production-target / commodity-metadata truth derives exclusively from `rules/canonical_rules.json`; if the plan carries any of `recipes`, `production_targets`, or `commodity_roles`, the builder fails closed with a `ValueError` (R6-F-01: a same-key overlay could silently rewrite operation profiles without touching any canonical hash). The plan schema (`rules/preprocess_plan.schema.json`) no longer admits those sections.

## 3. Current runtime boundary

`PreprocessContext` is **not** the certified runtime placement input, but it is no longer a regeneration-only concern: `src/preprocess/operation_profiles.py` derives the runtime `OPERATION_PORT_PROFILES` from `load_default_preprocess_context()` at import time, and the binding subproblem reads utility slot declarations from `rules/preprocess_plan.json` at runtime. The plan is therefore bound into the exact campaign hash closure (`exact_campaign.OPTIONAL_EXACT_HASH_FILES`, with a missing-file sentinel for synthetic test projects) and the preflight frozen-artifact registry — a plan edit can never ride on otherwise-stale exact artifacts.
The certified exact path still consumes frozen artifacts under `data/preprocessed/*`, especially:

- `candidate_placements.json` (required external large artifact in current lightweight GitHub checkout)
- `mandatory_exact_instances.json`
- `generic_io_requirements.json`

`PreprocessContext` only governs how those preprocess artifacts can be regenerated and audited. The lightweight GitHub checkout does not carry the production `candidate_placements.json` working-tree file; restore it before certified runtime checks.

## 4. Contract contents

The current `PreprocessContext` payload includes:

- metadata
- `tick_interval_seconds`
- `belt_capacity_per_tick`
- `facility_templates`
- `recipes`
- `production_targets`
- `commodity_roles`
- `cycle_groups`
- `utility_operations`

## 5. Validation guarantees

Builder validation currently enforces at least:

- recipe -> template foreign-key existence
- `production_targets[*].final_recipe_id` existence and output compatibility
- non-cycle commodity producer uniqueness
- cycle-group square solvability
- utility-operation facility existence and non-negative generic slot counts

## 6. Public compatibility layer

The preprocess modules preserve their historical public names where practical:

- `solve_demands()` remains zero-argument compatible
- `TEMPLATE_MAPPING` still exists
- `OPERATION_PORT_PROFILES` still exists

But these are now generated from the default `PreprocessContext` rather than from hand-written parallel truth tables.
