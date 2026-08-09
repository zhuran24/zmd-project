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

- `third_party_snapshots/industrial_planner/` (added 2026-07-18, rules audit)
  vendors the geometry/entity data core from `hsyhhssyy/IndustrialPlanner`
  (commit `dd334ed5`, plus tag 1.1.2.9 historical reference): entity
  definitions (protocol storage box / protocol core / pickup port / belt
  family / power diffuser) and base definitions (valley4_protocol_core).
  Build-time-only reference fixture for rule cross-checking; trust model,
  confidence levels, and the outerRing blacklist are recorded in its
  `SOURCE_METADATA.json`. Authority remains owner in-game adjudication
  (docs/research/rules_audit_20260718/00).
- `third_party_snapshots/endfield_calc/` now contains both synthetic fixtures
  and a vendored raw upstream repository fixture from `JamboChen/endfield-calc`.
  Refreshed 2026-05-08 from master commit `49be16e1` (package version `0.6.2`,
  178 items / 260 recipes / 16 facilities). Previously vendored was version
  `0.5.2` observed 2026-03-27 (130/172/14, commit unavailable). Refresh via
  `python scripts/refresh_endfield_calc_snapshot.py` (mechanical sync only;
  does not touch `canonical_rules.json`).
- The vendored upstream fixture is build-time only and is not imported as a
  runtime dependency.
- A partial semantic-alignment registry still records the verified overlapping
  17-recipe slice between the vendored `endfield-calc` fixture and
  `rules/canonical_rules.json`; unmatched upstream entities remain outside the
  local canonical truth set. The 2026-05-08 refresh expanded the upstream
  catalog but the 17-recipe canonical projection was intentionally unchanged
  (PROJECT_LOCK gate).
- `third_party_snapshots/industrial_planner/bases/` vendors a field-subset of
  the upstream `BASES` array (id / name / placeableSize / outerRing / tags) so
  the project can reference all seven base ids statically. Refresh via
  `python scripts/refresh_industrial_planner_bases.py`. PROJECT_LOCK active
  scope remains `valley4_protocol_core` (70x70); other bases (including
  `wuling_protocol_core` 80x80) stay future_scope.
- The IndustrialPlanner exporter is intentionally one-way and lossy. Its mapping
  rules and dropped semantics are recorded in
  `industrial_planner.compatibility_manifest.json` rather than pushed into the
  canonical blueprint schema.
