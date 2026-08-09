# endfield-calc snapshot ingest mapping

The adapter accepts either JSON snapshot files or upstream TypeScript source inputs.

JSON snapshot mode:

- `SNAPSHOT_METADATA.json`
- `items.json`
- `recipes.json`
- `facilities.json`

TypeScript mode accepts:

- a flat fixture directory with `items.ts`, `recipes.ts`, `facilities.ts`, `constants.ts`
- an extracted upstream repository root with `src/data/*` + `src/types/constants.ts`
- a `.zip` archive containing that upstream repository layout

Field alias examples supported by the adapter:

- `itemId` / `item_id` -> `item_id`
- `facilityId` / `template` -> `facility_type`
- `cycleSeconds` / `ticks_per_cycle` / `duration` -> `cycle_seconds`
- `portRule` / `port_rule` -> `port_rule`

The output is a neutral `NormalizedCatalog`, not a direct runtime dependency.

Semantic alignment mode also supports a partial `current_repository_rules` projection:

- operates on the raw normalized catalog after ingest
- renames the verified overlapping 17-recipe slice into local canonical IDs
- keeps unmatched upstream entities out of the aligned catalog instead of inventing fake matches
- records upstream IDs and rationale in metadata so the raw snapshot remains auditable
