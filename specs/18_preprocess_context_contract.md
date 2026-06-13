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

Both input layers — and every other JSON entry on the preprocess (re)generation chain (placement generator's canonical read, `machine_counts` loading, frozen-parity consumption) — are parsed with the shared strict JSON loader (`src/io/strict_json.py`): duplicate object keys and `NaN`/`Infinity` constants are rejected (F-PRE-R8-01: the hash closure pins bytes, not their parse; Python's default last-write-wins on duplicate keys could silently rewrite a target value, a port rule, or a machine count at first build). Preprocess artifact writers emit `allow_nan=False`. Strictness covers numeric overflow as well (F-PRE-R9-01): a JSON number literal that parses to a non-finite float (`1e309` → `inf`) is rejected via `parse_float` — `parse_constant` alone only catches the spelled-out constants — and the context/parity report writer (`scripts/build_current_preprocess_context.py`) uses a strict atomic writer with `allow_nan=False`, so a non-finite value can neither enter through a literal nor exit as a non-standard `Infinity` constant.

Schema validation runs at the file-loading boundary (F-PRE-R10-01): the path loaders (`load_default_preprocess_context`, `load_preprocess_context_from_paths`) validate the strict-loaded payloads against `canonical_rules.schema.json` / `preprocess_plan.schema.json` **before** context construction applies code-level defaults — otherwise a schema-required field (e.g. `tick_interval_seconds`, utility slot counts) silently missing from a source file would be absorbed by a default and masquerade as legal data. The dict-level builder (`build_preprocess_context_from_rules_and_plan`) intentionally stays a pure constructor so tests can probe semantic validation with variant dicts; file entrances are the enforcement boundary. Relatedly, the placement generator's closed-form pose families verify the canonical geometry they hard-code (F-PRE-R10-02, `_validate_template_geometry_contract`): schema-valid edits to `dimensions` / `core_limits` / `power_coverage_radius` / `placement_rule` that contradict the frozen generator geometry (core 9x9 + 6/14, omni 3x3, pole 2x2 + radius 5, boundary 1x3, long-sides w>h, square w==h) fail closed instead of generating poses that disagree with canonical.

Round 11 extends both boundaries (F-PRE-R11-01/02/03): the placement generator's own `load_templates()` is a third canonical file entrance and validates `canonical_rules.schema.json` right after strict loading (any future strict-load-from-disk reader inherits the same obligation); the geometry contract additionally pins `rotatable` and `is_solid_z` per family with boolean type checks, because the generators consume or implicitly assume them (orientation enumeration, unconditional `occupied_cells` emission) and a schema-valid flip would fork canonical semantics from generated poses; and cycle-group solving proves non-negativity, not just uniqueness — context validation requires every `net_export_commodity` to be internal to its group and proves a non-negative basis solution per net-export direction, while `_solve_cycle_group_exact()` rejects any negative run rate at solve time (downstream demand aggregation filters non-positive entries, so an unchecked negative solution would silently delete machines from the frozen demand artifacts).

Round 12 closes the RHS membership boundary (F-PRE-R12-01): the cycle RHS is assembled by iterating `internal_commodities`, so a positive demand keyed outside that list was silently dropped — a `cycle_internal` commodity missing from its group's `internal_commodities` could carry positive downstream flow with zero supporting machines in the frozen artifacts. Validation now reverse-checks that every `cycle_internal` commodity is listed in its declared group's `internal_commodities`, and the solver entry rejects positive demand keys that are not both internal and net-export (keeping the R11 non-negativity proof premise) plus all negative demands; explicit zeros remain accepted.

Round 13 closes the recipe I/O side of the same membership boundary (F-PRE-R13-01): the cycle matrix and the post-solve machine-run aggregation only ever look at `internal_commodities`, so a cycle recipe whose inputs or outputs reference a commodity outside that list contributes machines whose external consumption/production never reaches `commodity_demands`/`port_budget`/`generic_io_requirements` — under canonical drift the frozen artifacts would under-state external supply while still reporting the 52-port budget feasible (fail-open). Validation now requires every cycle-group recipe's `inputs ∪ outputs` to be a subset of the group's `internal_commodities` (`_cycle_group_recipe_io_outside_internal()`), and `_solve_cycle_group_exact()` repeats the check at its entry so direct solver calls on unvalidated contexts are covered too.

Round 14 keeps the demand-expansion model fail-closed for co-product drift (F-PRE-R14-01): `_backpropagate_non_cycle_demands()` expands one demanded commodity at a time by selecting its unique producer and adding that producer's run rate. That is exact for the current canonical single-output recipes, but a multi-output recipe with two demanded outputs would be charged twice instead of sharing the same recipe run. Until preprocess owns a coupled co-product solve, `canonical_rules.schema.json`, `validate_canonical_document()`, and `validate_preprocess_context()` all require every recipe to provide exactly one output commodity.

The same round also seals cycle-internal producer ownership (F-PRE-R14-02): a commodity with `cycle_group` set is supplied by that group's exact cycle solve, and `_backpropagate_non_cycle_demands()` forwards positive demand for it before any non-cycle producer lookup. Therefore recipes outside the declared group may consume cycle-internal commodities as external demand edges, but may not output them; `validate_preprocess_context()` rejects such outsider producers so their machines/inputs cannot be silently skipped.

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
