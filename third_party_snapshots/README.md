# third_party_snapshots

This directory stores vendored snapshot metadata, sample fixtures, and future
license records for build-time-only adapters.

Rules:

- no runtime dependency on upstream repositories
- keep metadata about source, observed date, and license
- synthetic fixtures must be labeled clearly
- if real upstream data is copied later, record the exact commit/tag when
  available and update `BORROWED_COMPONENTS.md`

Current note:

- `third_party_snapshots/endfield_calc/upstream_repository_fixture/` vendors the
  raw TypeScript catalog files from `JamboChen/endfield-calc`. Refreshed
  2026-05-08 from master commit `49be16e1`, package version `0.6.2`. Previously
  vendored archive was version `0.5.2` observed 2026-03-27. Upstream now
  exposes 16 facility types (added `ITEM_PORT_LIQUID_PURIFIER_1` and
  `ITEM_PORT_MIX_POOL_2`; `ITEM_PORT_DISMANTLER_1` re-tiered 4→3) and 281
  recipe entries (was 172). See
  `endfield_calc/upstream_repository_fixture/SOURCE_METADATA.json` for the
  full refresh log.

- `data/solutions/endfield_calc.semantic_aligned_catalog.json` is the build-time, partial semantic projection of the verified overlapping slice into `rules/canonical_rules.json` IDs. It intentionally keeps only the mapped 17-recipe subset; the raw upstream extras remain in the raw normalized catalog.
