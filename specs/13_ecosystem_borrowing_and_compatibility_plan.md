# Spec 13 — Ecosystem Borrowing and Compatibility Plan

**Status**: ACCEPTED_DRAFT  
**Updated**: 2026-03-25

## Purpose

Freeze the repository-level plan for borrowing useful ideas from surrounding
Endfield and factory-planning repositories without rewriting the certified exact
solver core.

## Phase 1 scope

Phase 1 is borrowing-first and intentionally internal:

- add neutral contracts under `src/interchange/`
- add source-specific adapters under `src/adapters/`
- strengthen postprocess reporting and viewer layering
- record provenance and synthetic third-party snapshot fixtures
- avoid target compatibility promises and avoid solver-core rewrites

## Guardrails

- `optimal_blueprint.json` remains the canonical layout artifact
- `rules/canonical_rules.json` and `data/preprocessed/*` remain certified inputs
- solver core under `src/models/` and `src/search/` is unchanged in semantics
- external repositories are referenced through snapshot-friendly build-time
  adapters or documentation notes only

## Phase 2 deferments

> **(2026-06-04 currency)** 前两项已不再 deferred —— IndustrialPlanner 单向 exporter 与 compatibility sidecar 均已交付 (见 spec 16 export contract / spec 22 precision export + validator / spec 23 outer-base planning; 对应 `export_blueprint.py` / `export_industrial_planner_bundle.py` / `blueprint_validator.py` 等已落地)。下列保留作历史 deferment 记录。

- ~~IndustrialPlanner one-way exporter~~ — **已交付** (spec 16 / 22)
- ~~compatibility sidecar bundles per target~~ — **已交付** (spec 22 Part B validator + compatibility manifest)
- preprocess regeneration from `NormalizedCatalog` (仍 deferred；另见 spec 19)
- any target-specific schema mapping beyond placeholder registration (仍 deferred)
