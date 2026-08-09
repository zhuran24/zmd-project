# `src/adapters/`

Adapters translate between project data and external catalogs, planners or viewers. They are not
solve or certification authorities. This boundary is about semantics, not directory names: an
adapter that writes, labels or republishes a result can still affect the authenticated publication
surface and therefore may require lock/spec/obligation review.

## Subdirectories

| Directory | Current role |
|---|---|
| `industrial_planner/` | Project blueprint to IndustrialPlanner formats, static validation, throughput and compatibility reports |
| `endfield_calc/` | Mechanical ingestion/normalization of upstream TypeScript catalog snapshots |
| `dige/` | Internal viewer model projection |
| `base_planner/` | Outer/multi-base decision-support representation; not certified evidence |

File counts change frequently and are intentionally not used as architecture claims.

## Data direction

```text
upstream snapshots
  -> adapter normalization
  -> src/interchange contracts
  -> owner-reviewed canonical rules / preprocess plan
  -> frozen or hash-bound preprocess artifacts
  -> certified solver

supervisor-sealed campaign
  -> verified canonical publisher
  -> canonical delivery surface
  -> adapter/viewer/report derivatives
```

`industrial_planner` output is a consumer-facing derivative. Its validator and throughput LP can
find compatibility defects, but cannot mint `CERTIFIED`, open a phase gate, or replace terminal
fixed-witness verification.

## Certified-publication restrictions

Adapters must not:

- redefine `rules/canonical_rules.json` or frozen preprocess semantics without their owner gates;
- treat `candidate_placements.json`, hints or external planner data as self-authenticating;
- write the canonical `data/blueprints/optimal_blueprint.json`,
  `data/solutions/final_solution.json` or certified manifest outside the verified publisher;
- copy a caller-provided `CERTIFIED` label into a public or release surface without the central
  certified-surface verdict;
- describe validator/probe/throughput output as proof-bearing evidence.

The current candidate-placement artifact is present in the worktree and remains hash-bound. Its
presence does not weaken the resume or publication checks.

## Change discipline

Pure mapping changes may stay postprocess-only. Changes that alter canonical output paths, status
normalization, release metadata, proof-bearing terminology, or what a public consumer is told are
publication-boundary changes. Those changes require review against `PROJECT_LOCK.md`, relevant
specifications, the strong-status allowlist and P1.2 proof obligations.
