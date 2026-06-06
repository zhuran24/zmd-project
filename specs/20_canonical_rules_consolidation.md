---
status: CURRENT_CODE_ALIGNED
source_of_truth: rules/canonical_rules.json, rules/canonical_rules.schema.json, src/rules/models.py, src/rules/semantic_validator.py, src/interchange/preprocess_context.py
last_verified_against: 2026-03-25
owner: rules
---
# 20 Canonical Rules Consolidation

## 1. Scope

This document records the first consolidation step after the frozen-compatible preprocess-context refactor.

Current split:

- `canonical_rules.json`
  - grid / time / logistics globals
  - routing rules
  - facility templates
  - the 17 real preprocess recipes
  - `production_targets`
  - `commodity_metadata`
- `preprocess_plan.json`
  - cycle groups
  - utility operations
  - optional overlay overrides

## 2. Why this split exists

The goal of consolidation is to reduce duplicate truth without immediately widening the certified runtime input surface.
`canonical_rules.json` now carries the stable, repository-owned recipe and target truth.
`preprocess_plan.json` remains as an additive overlay for the parts that are still most naturally expressed as regeneration-time helper data.

## 3. Runtime boundary

This consolidation does **not** make `PreprocessContext` or `canonical_rules.json` the immediate runtime replacement for the frozen preprocess artifacts.
Certified exact runtime still consumes:

- `data/preprocessed/candidate_placements.json` (required external large artifact in current lightweight GitHub checkout)
- `data/preprocessed/mandatory_exact_instances.json`
- `data/preprocessed/generic_io_requirements.json`

## 4. Current guarantees

- `CanonicalRulesDocument` validates the consolidated fields.
- `CanonicalSemanticValidator` now checks production-target and commodity-metadata consistency.
- `PreprocessContext` merges canonical rules first and then applies overlay keys from `preprocess_plan.json`.
- Context-driven regeneration continues to match the frozen preprocess artifacts.

## 5. Deferred work

This repository has **not** yet folded cycle-group declarations or utility-operation declarations back into canonical rules.
That remains a possible later step, but only if it does not blur the certified runtime boundary or create a second uncontrolled migration wave.
