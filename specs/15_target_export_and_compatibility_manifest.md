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

> **(2026-06-04 currency)** 这条"exporters 仍 deferred"已部分过时：**IndustrialPlanner 单向 exporter 已交付**（见 spec 16 export contract / spec 22 Part A precision export，对应 `export_blueprint.py` / `export_industrial_planner_bundle.py` 已落地）。本节针对的"compatibility-first 多 target exporter"通用框架仍 deferred，但具体 IndustrialPlanner target 这条已 delivered。
