# Phase 1.2 P0 Acceptance Checklist

## A. F5 bounded fallback

- [ ] `src/cuts/families/pattern_nogood.py` exists.
- [ ] `src/cuts/oracles/pattern_nogood_oracle.py` exists.
- [ ] Minimizer has both `max_calls` and `max_seconds`.
- [ ] Timeout returns last verified infeasible core, not an unverified partial core.
- [ ] Cert stores `stopped_reason`, `calls`, `size_before`, `size_after`, `last_verified=true`.
- [ ] Validator reruns subproblem witness or verifies independent oracle certificate.
- [ ] Evaluator uses multiset semantics, ignores concrete instance labels.
- [ ] Step 8 translates to `sum(present_lits) <= n-1`.
- [ ] Tests cover slot anonymity, duplicate poses, timeout, oracle UNKNOWN, oracle FEASIBLE.

## B. F9 area-only density envelope

- [ ] `src/cuts/families/density_envelope.py` exists.
- [ ] Generator rejects `routing_overflow`, `binding_overflow`, `pcr_cut_overflow`.
- [ ] Only `area_capacity_overflow` can produce F9.
- [ ] Cert has `max_allowed_area`.
- [ ] Evaluator counts `sum(|pose_cells ∩ W|)`, not instance count.
- [ ] Validator uses the same area-based rule.
- [ ] Step 8 uses linear weighted area overlap coefficients.
- [ ] Tests cover historical any-overlap/origin/all-in-window unsound variants.

## C. F2/F4 capacity

- [ ] F4 generator no longer returns `[]` for real disconnected commodity.
- [ ] F2 generator computes min-cut / max-flow witness for capacity bottlenecks.
- [ ] Node-split mode exists if cell capacity matters.
- [ ] Validator independently recomputes cut capacity and demand.
- [ ] Commodity ids are deduplicated and checked against source-of-truth registry.

## D. Integration

- [ ] `step_8_apply_to_master` is implemented for F3/F5/F9 at minimum.
- [ ] No code path depends on `AddLazyConstraint` in CP-SAT.
- [ ] Ghost-bound cuts use `OnlyEnforceIf` or per-ghost rebuild.
- [ ] `GHOST_AGNOSTIC` cuts still check `exterior_blocks_hash`.
- [ ] HOLD and QUARANTINE are distinct in replay and store.

## E. Telemetry

- [ ] F5 ratio emitted.
- [ ] F5 core size emitted.
- [ ] F9/F5 ratio emitted.
- [ ] unexplained infeasible JSONL written.
- [ ] psutil RSS emitted per worker.
- [ ] capacity eviction writes audit trail, not silent deletion.

## F. Regression gate

- [ ] Existing `src/tests/cuts/` remain green.
- [ ] `python -O -m pytest src/tests/cuts/ -q` remains green.
- [ ] New red fixtures green.
- [ ] Ruff green.
- [ ] mypy strict either green or explicitly tracked as separate typing debt, not mixed with soundness claims.
