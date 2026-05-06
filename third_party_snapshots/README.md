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
  raw TypeScript catalog files from a user-provided `JamboChen/endfield-calc`
  archive. The package version is known (`0.5.2`); the exact git commit was not
  recoverable from the archive.

- `data/solutions/endfield_calc.semantic_aligned_catalog.json` is the build-time, partial semantic projection of the verified overlapping slice into `rules/canonical_rules.json` IDs. It intentionally keeps only the mapped 17-recipe subset; the raw upstream extras remain in the raw normalized catalog.
