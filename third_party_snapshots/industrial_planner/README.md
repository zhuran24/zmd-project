# IndustrialPlanner Reference Notes

This directory records Phase-2 provenance notes for the IndustrialPlanner export
adapter.

## Observed upstream surfaces

- repository: `hsyhhssyy/IndustrialPlanner`
- observed branch during Phase 2 work: `v2`
- public sample blueprints live under `public/blueprints/`
- sample root shape observed during implementation:
  - `schema`
  - `id`
  - `version`
  - optional `blueprintVersion`
  - `name`
  - `createdAt`
  - `baseId`
  - `devices[]`

## Copy policy

The current repository does **not** vendor upstream IndustrialPlanner runtime
code (App.tsx, sim/, ui/, etc.). Phase 2 borrows format observations, device
vocabulary, and public-sample shape signals to build a one-way exporter.

## Vendored data

A small slice of upstream **base definitions** is vendored under `bases/` so we
can statically reference the seven known base ids and their placeable sizes
(70x70 valley4 core, 80x80 wuling core, etc.) without a runtime dependency.
The vendored payload is field-subset only — `foundationBuildings` and other
runtime code is intentionally not extracted.

Refresh via:

```
python scripts/refresh_industrial_planner_bases.py
```

This re-extracts `BASES` from `src/domain/registry.ts` on the upstream `v2`
branch, updates `bases/bases.json` and `bases/SOURCE_METADATA.json`, and prints
a diff report. PROJECT_LOCK active scope remains `valley4_protocol_core`;
expanding to other bases requires an explicit scope-expansion review.
