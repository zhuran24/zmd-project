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

- IndustrialPlanner one-way exporter
- compatibility sidecar bundles per target
- preprocess regeneration from `NormalizedCatalog`
- any target-specific schema mapping beyond placeholder registration
