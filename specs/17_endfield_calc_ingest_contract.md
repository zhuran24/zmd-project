# Spec 17 — endfield-calc Snapshot and TypeScript Ingest Contract

**Status**: CURRENT_CODE_ALIGNED  
**Updated**: 2026-05-08 (vendored snapshot refresh; 具体 source_version / 计数以 `third_party_snapshots` endfield-calc `SOURCE_METADATA.json` 为准)

## Purpose

Define the additive build-time adapter path that consumes `JamboChen/endfield-calc`
data without introducing a runtime dependency on the upstream repository.

## Supported sources

The adapter supports two input modes:

1. JSON snapshot directories containing:
   - `items.json`
   - `recipes.json`
   - `facilities.json`
   - optional `SNAPSHOT_METADATA.json`
2. Upstream-shaped TypeScript source inputs in any of these layouts:
   - flat fixture directory containing `items.ts`, `recipes.ts`, `facilities.ts`, `constants.ts`
   - extracted upstream repository root containing `src/data/*` and `src/types/constants.ts`
   - `.zip` archive containing that upstream repository layout

## Output

Both input modes normalize into the existing neutral contract:

- `src/interchange/normalized_catalog.py`
- output artifact example: `data/solutions/endfield_calc.normalized_catalog.json`

## Design rules

- build-time only; no runtime `import` of upstream code
- parse and resolve upstream constant tables before normalization
- preserve provenance metadata in `metadata.source`, `metadata.source_version`,
  `metadata.source_commit`, and `metadata.extensions`
- do not rewrite the certified preprocess path by default
- optional diff reports compare the ingested catalog against the current rules-
  derived catalog without changing certified runtime inputs

## Script surface

`scripts/snapshot_endfield_calc.py` now supports:

- `--source-format auto|json|typescript`
- `--emit-snapshot-dir` for materializing parsed JSON snapshots
- direct input from an extracted upstream repository root or `.zip` archive
- `--compare-rules` + diff report outputs for compatibility auditing
