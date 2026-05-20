# Spec 14 — Normalized Catalog Contract

**Status**: CURRENT_CODE_ALIGNED  
**Updated**: 2026-03-25

## Purpose

`NormalizedCatalog` is the additive, snapshot-friendly, upstream-neutral data
contract for borrowed data sources such as `endfield-calc`.

It does **not** replace the current certified preprocess artifacts. Instead it
creates a stable boundary where upstream item/recipe/facility data can be
normalized before any future preprocess regeneration or compatibility work.

## Payload shape

```json
{
  "metadata": {
    "version": "0.1.0",
    "source": "...",
    "generated_at": "..."
  },
  "items": [],
  "recipes": [],
  "facilities": [],
  "power": [],
  "port_rules": []
}
```

## Design rules

- deterministic ordering for hashing and fixtures
- explicit provenance metadata
- keep third-party naming differences at the adapter boundary
- allow a catalog to be produced from current repository rules for internal
  comparison and future diffing
- keep all current exact runtime consumers on frozen preprocess artifacts unless
  a later phase explicitly opts into regenerated inputs
