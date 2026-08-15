# Compatibility Matrix

**Role**: current compatibility/adapter boundary. Borrowing inventory is tracked in [`BORROWED_COMPONENTS.md`](../BORROWED_COMPONENTS.md); implementation guidance starts at [`src/adapters/README.md`](../src/adapters/README.md). External research notes live under [`specs/ecosystem_notes/`](../specs/ecosystem_notes/README.md), while the frozen April 2026 delivery guides are indexed as historical evidence in [`docs/history/deliveries/`](history/deliveries/README.md).

| Target / Source | Direction | Status | Boundary | Notes |
|---|---|---|---|---|
| `hsyhhssyy/IndustrialPlanner` | canonical blueprint -> target blueprint | implemented | `src/adapters/industrial_planner/*` | one-way lossy export with precise device-type export, an offline import/layout-health validator, an adapter-side static recipe/capacity conformance audit, and a fail-closed full-demand base-support matrix for the current 70×70 oracle; additive export-side compatibility only, not a certified solver proof sink and not a runtime simulation |
| `JamboChen/endfield-calc` JSON snapshot | upstream snapshot -> `NormalizedCatalog` | implemented | `src/adapters/endfield_calc/*` | build-time ingest only |
| `JamboChen/endfield-calc` TypeScript data source | upstream TS -> parsed snapshot -> `NormalizedCatalog` | implemented | `src/adapters/endfield_calc/*` | accepts flat fixture dirs, extracted repo roots, and zip archives |
| `JamboChen/endfield-calc` semantic alignment (`current_repository_rules`) | raw normalized catalog -> partial canonical-ID projection | implemented | `src/adapters/endfield_calc/semantic_mapping.py` | exact 17-recipe overlap only; utilities remain unmatched because they are absent from the upstream data files |
| `LithiumValproate/endfield-base-planner` | report/view-model borrowing | partial | `src/adapters/base_planner/*`, `src/render/report_builder.py` | report-shape borrowing only; no direct schema compatibility promise |
| `djkcyl/D.I.G.E.` | product/viewer borrowing | partial | `src/adapters/dige/*`, `src/render/web_viewer/` | cards/warnings/persistence patterns only |

## Guardrails

- `optimal_blueprint.json` remains the canonical internal layout artifact.
- Compatibility is additive and sits in adapters/exporters/sidecar manifests.
- Certified exact semantics remain in the solver core and frozen preprocess
  artifacts, not in target exports or viewer bundles.
