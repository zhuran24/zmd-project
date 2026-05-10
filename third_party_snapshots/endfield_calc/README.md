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
- the vendored upstream fixture currently records package version `0.6.2`
  (master commit `49be16e1`, observed 2026-05-08); previous archive was
  `0.5.2` (commit unavailable, observed 2026-03-27)
- refresh via `python scripts/refresh_endfield_calc_snapshot.py` — fetches
  the latest master, rewrites `SOURCE_METADATA.json` with version / commit /
  observed_counts / previous_* tracking, prints a diff report, and does NOT
  touch `canonical_rules.json` (PROJECT_LOCK gate)
- `scripts/snapshot_endfield_calc.py` can ingest:
  - a JSON snapshot directory
  - a flat TypeScript fixture directory
  - an extracted upstream repository root
  - a `.zip` archive containing the upstream repository layout
