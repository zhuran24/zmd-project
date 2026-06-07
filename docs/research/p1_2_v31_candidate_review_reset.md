# P1.2 v31 candidate review reset evidence

Status: NOT CLEAN.

The v31 candidate review found major/soundness issues that block counting this review as clean:

1. The v30 evaluator hot-path fix remained incomplete: Step 7 and the generic literal evaluator could return `True` after `source_digest` or artifact drift, while Step 6 would quarantine the same cut.
2. The `candidate_placements` pose lookup cache could survive replacement of the underlying facility pool. Because runtime `__*` cache keys are excluded from `compute_source_digest`, F3 validation could certify against stale pose geometry while claiming the current source digest.
3. The Phase 1.2 close gate SoT still recorded v28 as the latest reset even though v30 was already non-clean, so the gate/preflight could pass while carrying stale review provenance.

Gate effect: consecutive clean full review counter remains `0/3`; P1.3B entry remains blocked.
