# BORROWED_COMPONENTS.md

This repository keeps the certified exact path internal and stable. The
borrowing-first upgrade work absorbs ideas, interface boundaries, product
patterns, sample blueprint shapes, and synthetic fixture structures from
external repositories without adding runtime source dependencies.

## Provenance rules

- Record the upstream repository, observed date, and rough surface borrowed.
- Prefer borrowing structure and vocabulary over verbatim code.
- Do not add a runtime dependency on external repositories.
- If a future phase vendors real code or data, record the exact commit and
  license under `third_party_snapshots/` and update this file.

## Borrowing inventory

| Source | Borrowed Surface | Applied Here | Verbatim Code? |
|---|---|---|---|
| `hsyhhssyy/IndustrialPlanner` | browser-side sandbox ideas, blueprint/share/persistence workflow, debug overlays, public blueprint root/device shape, product structure vocabulary | `src/render/web_viewer/index.html`, `src/render/report_builder.py`, `src/adapters/industrial_planner/*`, `specs/ecosystem_notes/industrial_planner_*` | No |
| `JamboChen/endfield-calc` | item/recipe/facility catalog separation, snapshot ingest boundary, calculation/data-layer split, cycle/throughput vocabulary, TypeScript-source snapshot shape, vendored raw upstream data fixture | `src/interchange/normalized_catalog.py`, `src/adapters/endfield_calc/*`, `third_party_snapshots/endfield_calc/*` | No runtime code; raw TypeScript data fixture only |
| `LithiumValproate/endfield-base-planner` | JSON IO split, report shaping, stable-state throughput/power/logistics summary boundary | `src/adapters/base_planner/report_shapes.py`, `src/render/report_builder.py` | No |
| `djkcyl/D.I.G.E.` | result cards, warnings/storytelling layer, persistence/share oriented viewer defaults | `src/adapters/dige/result_view_models.py`, `src/render/web_viewer/index.html` | No |
| `Aslappyslashy/EndFieldCalculator` | modeling vocabulary for constraints and decomposition language | `specs/ecosystem_notes/aslappyslashy_modeling_vocabulary_notes.md` | No |
| `kevinburke/factorio-layout-optimizer` | exploratory adjacency/block/warm-start vocabulary only | `specs/ecosystem_notes/exploratory_layout_inspirations.md` | No |

## Notes

- `third_party_snapshots/endfield_calc/` now contains both synthetic fixtures
  and a vendored raw upstream repository fixture derived from a user-provided
  `JamboChen/endfield-calc` archive. The observed package version is `0.5.2`;
  the exact git commit was unavailable from the archive.
- The vendored upstream fixture is build-time only and is not imported as a
  runtime dependency.
- A partial semantic-alignment registry now records the verified overlapping 17-recipe slice between the vendored `endfield-calc` fixture and `rules/canonical_rules.json`; unmatched upstream entities remain outside the local canonical truth set.
- The IndustrialPlanner exporter is intentionally one-way and lossy. Its mapping
  rules and dropped semantics are recorded in
  `industrial_planner.compatibility_manifest.json` rather than pushed into the
  canonical blueprint schema.
