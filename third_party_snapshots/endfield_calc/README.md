# endfield-calc snapshot area

This directory now ships two build-time compatibility fixtures:

1. `minimal_fixture/` — a synthetic JSON snapshot used for adapter-unit tests.
2. `upstream_repository_fixture/` — a vendored raw TypeScript repository fixture
   copied from a user-provided `JamboChen/endfield-calc` archive.

The original flat `typescript_fixture/` is still kept as a tiny parser-focused
fixture, but real compatibility coverage now runs against the repository-shaped
fixture as well.

Notes:

- no runtime dependency is introduced on the upstream project
- the vendored upstream fixture records package version `0.5.2`
- the exact git commit was unavailable from the uploaded archive
- `scripts/snapshot_endfield_calc.py` can now ingest:
  - a JSON snapshot directory
  - a flat TypeScript fixture directory
  - an extracted upstream repository root
  - a `.zip` archive containing the upstream repository layout
