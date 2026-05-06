# Spec 16 — IndustrialPlanner One-Way Export Contract

**Status**: CURRENT_CODE_ALIGNED  
**Updated**: 2026-03-25

## Purpose

Define the additive Phase-2 exporter that projects the canonical
`optimal_blueprint.json` payload into an IndustrialPlanner-readable blueprint
bundle without changing the canonical internal schema.

## Files

- `src/adapters/industrial_planner/mapping_registry.py`
- `src/adapters/industrial_planner/export_blueprint.py`
- `src/adapters/industrial_planner/compatibility_report.py`
- `scripts/export_industrial_planner_bundle.py`

## Bundle layout

The exporter writes:

```text
data/exports/industrial_planner/
  industrial_planner.blueprint.json
  industrial_planner.compatibility_manifest.json
```

## Root contract

The emitted target blueprint follows the observed IndustrialPlanner public
blueprint shape:

```json
{
  "schema": "industrial-planner-blueprint",
  "id": "ExactExport-...",
  "version": "1.0",
  "blueprintVersion": "1",
  "name": "Exact Export ...",
  "createdAt": "...",
  "baseId": "valley4_protocol_core",
  "devices": []
}
```

## Mapping rules

- canonical `metadata.export_timestamp` -> target `createdAt`
- canonical `facilities[*].anchor` -> target `devices[*].origin`
- canonical `facilities[*].orientation` -> target `devices[*].rotation`
- canonical facilities remain canonical truth; target `typeId` selection is done
  purely inside the adapter
- routing cells are flattened into `devices[]`
- `protocol_core` is not exported as a movable device; the exporter uses
  `baseId` instead and records the semantic loss in the compatibility manifest
- exact-only metadata such as objective payload, solve time, and Benders proof
  counters stay out of the target root JSON and are recorded as dropped fields
  in the sidecar manifest

## Loss model

This exporter is explicitly **one-way lossy**.

Known loss surfaces:

- generic canonical manufacturing templates map to representative IndustrialPlanner
  processor devices
- elevated bridge semantics are flattened into planar logistics devices
- liquid routing family selection is commodity-name heuristic only
- target-side facility configs are populated only where a stable mapping exists
  (for example boundary output ports -> unloader pickup config)
