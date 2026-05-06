# Spec 15 — Target Export Registry and Compatibility Manifest

**Status**: CURRENT_CODE_ALIGNED  
**Updated**: 2026-03-25

## Purpose

Define the additive contracts needed for downstream compatibility without
polluting the canonical blueprint schema.

## Export registry

`src/interchange/export_registry.py` keeps named target exporters, capability
metadata, and provenance notes. Exporters operate on canonical blueprint
payloads and remain optional.

## Compatibility manifest

`src/interchange/compatibility_manifest.py` records how a target export behaves.
At minimum it separates mappings into:

- `direct_mappings`
- `lossy_mappings`
- `dropped_fields`
- `derived_mappings`

and carries a target capability descriptor.

## Phase 1 note

Phase 1 lands the contract and tests only. Real target exporters remain deferred
until compatibility-first work begins.
