# Spec 22 — IndustrialPlanner Precision Export and Offline Validator

**Status**: CURRENT_CODE_ALIGNED  
**Scope**: additive export-side compatibility only  
**Certified exact boundary**: unchanged

## 1. Purpose

This spec defines the repository's current IndustrialPlanner compatibility surface.
It does **not** extend the certified exact solver proof chain. The canonical
`optimal_blueprint.json` remains the internal layout truth, and all
IndustrialPlanner work stays inside adapter/export/validator code.

Spec 22 has two delivered parts:

- **Part A — precise machine-type export** from canonical facilities into
  IndustrialPlanner `typeId`s where semantic evidence is strong enough.
- **Part B — pure-Python offline validator** for import compatibility and layout
  health of an IndustrialPlanner blueprint JSON.

## 2. Non-goals

This spec does not introduce:

- throughput proof,
- tick simulation,
- recipe-rate validation,
- target-side certified evidence,
- reverse import from IndustrialPlanner back into the certified solver path.

The validator is an import/layout-health checker, not a production simulator.

## 3. Architecture boundary

IndustrialPlanner compatibility is strictly additive and export-side:

- canonical blueprint schema is unchanged;
- certified solver semantics are unchanged;
- validator results do not feed back into certified proof artifacts;
- compatibility manifests and validation reports are sidecars, not proof sinks.

## 4. Part A — precise export

### 4.1 Export mode

The exporter produces a one-way, potentially lossy IndustrialPlanner bundle:

- `industrial_planner.blueprint.json`
- `industrial_planner.compatibility_manifest.json`
- `validation_report.json`
- `validation_report.md`

The export mode remains `one_way_lossy` even when individual facilities resolve
precisely, because other target-side semantics can still be approximated.

### 4.2 Precise facility resolution

For supported canonical facility classes, the exporter may emit a precise target
`typeId` instead of a generic representative machine.

Current precision-mapped canonical classes:

- `manufacturing_3x3`
- `manufacturing_5x5`
- `manufacturing_6x4`

Resolution is based on canonical recipe evidence translated into the
IndustrialPlanner commodity namespace and matched against the semantic mapping
registry. If the evidence is ambiguous or missing, the exporter falls back to a
representative generic target device and records the fallback in warnings and in
manifest metadata.

### 4.3 Boundary/storage-port derivation

`boundary_storage_port` is exported by directionality:

- pure output -> unloader-like target device
- pure input -> loader-like target device
- mixed/ambiguous -> storage fallback

If a boundary output commodity cannot be translated, the geometry device may
still be emitted, but item-binding config is omitted.

### 4.4 Commodity translation hardening

Commodity translation is fail-closed for unresolved item-bearing export config.

Accepted item-id sources are:

1. canonical item id -> semantic mapping -> upstream item id;
2. explicit upstream item id already present in semantic mapping;
3. registry-backed upstream passthrough for valid `item_*` ids listed in
   `src/adapters/industrial_planner/item_registry.json`.

Unknown upstream-like `item_*` strings are **not** serialized into export
config. Instead:

- the invalid value is dropped from the exported config,
- warnings record the unresolved raw id,
- `commodity_translation_miss_count` increases.

This applies to scalar config fields, list entries, boundary-port output config,
and other item-bearing target config subtrees.

### 4.5 Recipe metadata

IndustrialPlanner export does **not** require a top-level `recipeId` field.
Precise device-type export is based on semantic facility/commodity evidence, not
on a target-wide top-level recipe identifier.

## 5. Part B — pure-Python offline validator

### 5.1 Validator role

The validator checks a target blueprint JSON without browser/Node runtime
support. It evaluates two top-level outcomes:

- `is_import_compatible`
- `is_layout_healthy`

It may also emit non-fatal `port_warnings`, which affect `is_clean` but do not
necessarily block import or layout health.

### 5.2 Import-compatibility checks

Import compatibility covers:

- schema normalization,
- static registry membership,
- lot-boundary checks,
- placement-constraint enforcement,
- unsupported target rule detection.

**Placement constraints are Tier-2 import blockers.** A blueprint that violates
required placement constraints is not import-compatible.

### 5.3 Layout-health checks

Layout health covers:

- illegal overlap / multi-occupancy,
- port mismatch audit.

Overlap and port-audit failures are layout-health failures even if the payload is
otherwise schema-valid.

## 6. Compatibility manifest expectations

The sidecar compatibility manifest records export-side status such as:

- precise-resolution counts,
- fallback counts,
- unresolved-facility counts,
- commodity translation miss counts,
- `has_commodity_translation_miss`,
- validation outcomes.

`clean_export` remains tied to validator outcomes:

- `validation_is_import_compatible`
- `validation_is_layout_healthy`

A commodity translation miss is tracked separately in metadata and does not,
by itself, redefine the meaning of `clean_export`.

## 7. Acceptance criteria implemented by this spec

### AC-A — precise machine export

Supported manufacturing facilities resolve to precise IndustrialPlanner machine
`typeId`s when recipe evidence is sufficient.

### AC-B — offline validator

A pure-Python validator exists and can classify import compatibility and layout
health without browser dependencies.

### AC-B12 — benchmark evidence

The repository must carry reproducible benchmark evidence for a 70×70-scale
validator run. That evidence consists of:

- a checked-in benchmark fixture,
- a benchmark harness script,
- raw benchmark JSON output,
- a checked-in benchmark markdown report.

The benchmark is evidence for validator runtime behavior only. It is not a proof
of throughput, correctness beyond the validator's scope, or target-side factory
simulation.

## 8. Implemented file surface

Primary implementation files:

- `src/adapters/industrial_planner/commodity_resolver.py`
- `src/adapters/industrial_planner/mapping_registry.py`
- `src/adapters/industrial_planner/export_blueprint.py`
- `src/adapters/industrial_planner/blueprint_validator.py`
- `scripts/benchmark_industrial_planner_validator.py`

Primary checked-in evidence/fixtures:

- `data/examples/industrial_planner/precision_export_canonical_blueprint.json`
- `data/examples/industrial_planner/benchmark.full70x70.blueprint.json`
- `data/examples/industrial_planner/benchmark.full70x70.benchmark.json`
- `docs/benchmarks/industrial_planner_validator_70x70.md`

## 9. Governance note

Nothing in this spec promotes compatibility/export artifacts into certified exact
source-of-truth status. All Spec 22 artifacts remain postprocess/adapter scoped.
