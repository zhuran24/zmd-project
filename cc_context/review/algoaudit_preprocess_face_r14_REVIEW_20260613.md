# 终末地 IndustrialPlanner preprocess round 14 review

## Scope and baseline

- Snapshot: `/mnt/data/zmd_snapshot_2cd169b4.zip`
- Required sha256: `2cd169b46a12cc1e52e1915d89279be48fc0f6adbd02b1530d0994d18d1879eb`
- Observed sha256: `2cd169b46a12cc1e52e1915d89279be48fc0f6adbd02b1530d0994d18d1879eb`
- Scope: R13-01 fix confirmation, R11/R12 light confirmation, and preprocess free attack angles only.

## Verdict

R13-01 itself is confirmed sound after review: the cycle recipe I/O closure check is complete for the current recipe data model, shared by validation and the direct solver entry, compatible with the R11/R12 checks, and correctly routes non-cycle consumers of cycle-internal commodities into the cycle group demand map.

本轮不是零 soundness finding。I found and fixed two new preprocess drift holes outside the R13-01 patch:

1. `F-PRE-R14-01` HIGH: schema-valid multi-output recipes were accepted even though the demand solver charges recipe runs per demanded output, causing co-product over-counting.
2. `F-PRE-R14-02` HIGH: recipes outside a cycle group could output a cycle-internal commodity, but positive demand for that commodity is routed directly to the cycle solver before non-cycle producer lookup, silently ignoring the outsider recipe and its inputs.

Both fixes are fail-closed guards. They do not change current frozen canonical outputs.

---

## Q1. F-PRE-R13-01 fix confirmation

### Q1.1 Interface completeness

`PreprocessRecipe` carries exactly `recipe_id`, `template`, `ticks_per_cycle`, `inputs`, and `outputs`; commodity-bearing fields are only `inputs` and `outputs` (`src/interchange/preprocess_context.py:31-43`). The canonical Pydantic model mirrors that shape (`src/rules/models.py:127-133`), and the JSON Schema recipe object has no catalyst/byproduct/utility commodity field beyond `inputs` and `outputs` (`rules/canonical_rules.schema.json:347-392`). `ticks_per_cycle` is scalar time, not a commodity reference.

Therefore `_cycle_group_recipe_io_outside_internal()` using `set(recipe.inputs) | set(recipe.outputs)` is complete for the current recipe contract (`src/interchange/preprocess_context.py:513-527`).

The `recipe is None: continue` branch is safe. The validated path rejects unknown group recipes before calling the helper (`src/interchange/preprocess_context.py:330-332`). The direct unvalidated solver path repeats the helper first, then indexes `context.recipes[recipe_id]` while building the matrix (`src/interchange/preprocess_context.py:489-500`), which fails closed with `KeyError` if the recipe is missing. Probe result:

```text
unknown_recipe_direct: KeyError 'missing_recipe'
```

### Q1.2 双端覆盖 and no third bypass

The validation side and solver entry use the same helper:

- Validation: `_cycle_group_recipe_io_outside_internal(context, group)` at `src/interchange/preprocess_context.py:333-335`.
- Direct solver: `_cycle_group_recipe_io_outside_internal(context, group)` at `src/interchange/preprocess_context.py:458-460`.

Repository search found `_solve_square_linear_system()` only called by `_solve_cycle_group_exact()` (`src/interchange/preprocess_context.py:500`), and cycle group solves flow through `solve_cycle_group_exact()` / `_solve_cycle_group_exact()`; no third matrix constructor or bypass path was found.

R13 mutation probes after patch:

```text
context_mutation: ValueError cycle group 'buckwheat_cycle' recipes must reference only commodities listed in internal_commodities; outside commodities: planter_buckwheat: source_ore
solver_direct_mutation: ValueError cycle group 'buckwheat_cycle' recipes must reference only commodities listed in internal_commodities; outside commodities: planter_buckwheat: source_ore
```

### Q1.3 R12/R11 compatibility

R12 remains intact. Positive external demand keys must be internal and net-export (`src/interchange/preprocess_context.py:475-484`), negative demands are rejected (`src/interchange/preprocess_context.py:468-472`), and explicit zero keys are ignored (`src/interchange/preprocess_context.py:473-474`). Context validation still reverse-checks `cycle_internal` membership against the declared group (`src/interchange/preprocess_context.py:293-308`) and `net_export_commodities` membership (`src/interchange/preprocess_context.py:346-350`).

R11-03 remains intact. Validation still proves zero RHS and every net-export unit direction (`src/interchange/preprocess_context.py:352-354`), and `_solve_cycle_group_exact()` still rejects negative run rates (`src/interchange/preprocess_context.py:501-505`). The R14 patch adds guards before demand expansion assumptions are used; it does not weaken the cycle linear-system proof path.

Probe results:

```text
positive_unknown: ValueError ... is not listed in internal_commodities
positive_internal_not_export: ValueError ... is not declared in net_export_commodities
negative_export: ValueError ... must be non-negative: -1
zero_unknown: accepted {'planter_buckwheat': Fraction(0, 1), 'seed_collector_buckwheat': Fraction(0, 1)}
```

### Q1.4 Reverse flow: non-cycle recipe references to cycle-internal commodities

For non-cycle consumption of a cycle-internal commodity, demand propagation is correct. `_backpropagate_non_cycle_demands()` records the demanded commodity flow, then if `role.cycle_group is not None` it adds the demand to `cycle_external_demands[group][commodity]` and continues before producer lookup (`src/preprocess/demand_solver.py:276-316`). The group is then solved exactly in `solve_demands_exact()` (`src/preprocess/demand_solver.py:104-130`).

Default probe values confirm the expected crop-cycle demands and machines:

```text
cycle_flow_buckwheat= 11/2
cycle_flow_sandleaf= 21/2
planter_buckwheat= 11
planter_sandleaf= 21
```

For non-cycle production of a cycle-internal commodity, I found a separate drift hole: because demand for any `cycle_group` commodity is forwarded to the cycle solver before producer lookup, an outsider producer could be ignored. That is fixed as `F-PRE-R14-02` below by requiring any recipe output of a cycle-internal commodity to belong to that commodity's declared cycle group.

---

## Q2. R11/R12 light confirmation

- `load_default_preprocess_context()` and `load_preprocess_context_from_paths()` strict-load and schema-validate canonical rules and preprocess plan before context construction (`src/interchange/preprocess_context.py:411-426`).
- Placement generator `load_templates()` strict-loads canonical rules and validates `canonical_rules.schema.json` before returning templates (`src/placement/placement_generator.py:474-481`).
- Geometry contract validation still pins dimensions, port rule type, `rotatable`, `is_solid_z`, and family-specific geometry (`src/placement/placement_generator.py:161-277`).
- R12 RHS membership and R11 non-negativity proof paths were not weakened by the R14 patch.

---

## Findings and fixes

### F-PRE-R14-01 - HIGH - Multi-output recipe co-products are accepted but demand backprop double-charges recipe runs

**Affected files / lines**

- `src/preprocess/demand_solver.py:276-316`: `_backpropagate_non_cycle_demands()` handles one pending commodity at a time and adds `machine_runs[recipe.recipe_id] += run_rate` for each demanded output.
- Pre-fix schema allowed arbitrary output count under `recipes.*.outputs`; fixed at `rules/canonical_rules.schema.json:378-389`.
- Pre-fix context validation did not enforce the single-output solver premise after template validation; fixed at `src/interchange/preprocess_context.py:246-255`.
- Pre-fix semantic validation only rejected no-output and self-loop recipes; fixed at `src/rules/semantic_validator.py:100-109`.

**Probe on the original snapshot**

Mutation: add `bonus_battery` as a second output of `packaging_battery`, add a `bonus_battery` target of one equivalent full-speed line, and mark it as `generic_input`.

```text
accepted
packaging_battery_run= 4
packaging_battery_count= 4
valley_battery_flow= 3/5
bonus_battery_flow= 1/5
```

The original `valley_battery` target already requires 3 full-speed `packaging_battery` runs and would co-produce `3/5` bonus/tick if co-products were modeled. The extra `bonus_battery` target needs only `1/5` bonus/tick, so a coupled co-product solve should not add another full run. The current solver instead charges the same recipe again and raises `packaging_battery` from 3 to 4. That can inflate `machine_counts` / mandatory instances and create false-INFEASIBLE layouts under canonical drift.

**Fix**

Fail closed until a coupled co-product solve exists:

- `canonical_rules.schema.json`: `outputs` now requires `minProperties: 1` and `maxProperties: 1`.
- `validate_canonical_document()`: rejects multi-output recipes with an explicit semantic error.
- `validate_preprocess_context()`: rejects `len(recipe.outputs) != 1`, covering direct dict/context construction that bypasses file schema entry.
- Regression tests added in `test_rules.py` and `test_preprocess_context.py`.

Post-fix probe:

```text
ValueError: preprocess recipe 'packaging_battery' must provide exactly one output commodity; multi-output co-product recipes require a coupled demand solve and are not supported
```

### F-PRE-R14-02 - HIGH - Outsider producers of cycle-internal commodities are ignored by demand propagation

**Affected files / lines**

- `src/preprocess/demand_solver.py:293-296`: any positive demand for a commodity with `role.cycle_group is not None` is forwarded to the cycle solver before producer lookup.
- Pre-fix `validate_preprocess_context()` did not verify that producers of cycle-internal commodities belonged to the declaring cycle group. Fixed at `src/interchange/preprocess_context.py:273-326`.

**Probe on the original snapshot**

Mutation: add a new one-commodity cycle group `orb_cycle`, a group recipe `orb_cycle_generator -> orb`, and an outsider recipe `synthetic_orb: source_ore -> orb`. Add `orb` as a `cycle_internal` + `generic_input` target whose `final_recipe_id` is `synthetic_orb`.

```text
accepted
target_rate_orb 1/5
synthetic_orb_run None
orb_cycle_generator_run 1/5
source_ore_flow 18
```

The target's `final_recipe_id` was the outsider recipe, but the machine run for `synthetic_orb` was absent and its `source_ore` input was not added. The demand was supplied by the cycle group instead. This is fail-open under canonical/plan drift because a schema-valid recipe can seed target rate while its machines and inputs vanish from frozen preprocess artifacts.

**Fix**

`validate_preprocess_context()` now constructs `cycle_group_recipes` and rejects any recipe output of a cycle-internal commodity unless that recipe is a member of the commodity's declared cycle group. Non-cycle consumption of cycle-internal commodities remains legal and is the intended external-demand edge into the group.

Post-fix probe:

```text
ValueError: cycle_internal commodity 'orb' cannot be produced by recipe 'synthetic_orb' outside cycle group 'orb_cycle'
```

---

## Regression and artifact checks

Passed:

```text
python3.13 -m pytest -q src/tests/test_preprocess_context.py src/tests/test_rules.py src/tests/test_preprocess_cycle_solver.py src/tests/test_demand.py src/tests/test_preprocess_plan_schema.py -p no:randomly
58 passed in 2.12s

python3.13 -m pytest -q src/tests/test_preprocess_candidate_geometry_contract.py -p no:randomly
5 passed in 18.93s

python3.13 -m pytest -q src/tests/test_preprocess_golden.py -k 'not chain_regenerates' -p no:randomly
3 passed, 1 deselected in 1.80s

python3.13 scripts/check_p1_2_proof_obligations.py
P1.2 proof obligation check passed: 8 obligations anchored

python3.13 scripts/build_current_preprocess_context.py
preprocess context written: data/solutions/current_preprocess_context.json
diff report written: data/solutions/preprocess_context_diff_report.json
diff markdown written: data/solutions/preprocess_context_diff_report.md
```

Frozen preprocess parity after regeneration:

```text
all_match: True
matched_count: 6/6
mandatory_exact_instance_count: 266
all_instance_count: 326
generic_output_slots: 52
generic_input_slots: 0
commodity_demands.json: MATCH
machine_counts.json: MATCH
port_budget.json: MATCH
generic_io_requirements.json: MATCH
mandatory_exact_instances.json: MATCH
all_facility_instances.json: MATCH
```

`candidate_placements.json` was not regenerated. The checked frozen artifact matches the requested baseline:

```text
sha256: adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0
size:   45,773,799 bytes
```

Not completed:

- A broad `python3.13 -m pytest -q src/tests -p no:randomly --ignore=src/tests/test_preprocess_golden.py` run timed out at 300 seconds, so I am not claiming full-suite green for this round.
- The heavy `test_preprocess_golden.py::chain_regenerates` path was not run to completion; targeted non-heavy golden tests passed.

## Patch

Unified diff: `algofix_FPRE_r14.patch`.
