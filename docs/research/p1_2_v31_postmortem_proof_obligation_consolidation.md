# P1.2 v31 postmortem: proof-obligation consolidation

Date: 2026-06-07

This is not a clean review. It is a postmortem/consolidation pass after the v31 candidate review. The purpose is to stop the v29-v31 pattern of one local fix exposing a neighboring fail-open path.

## Result

**NOT CLEAN.** The consolidation pass found one additional V31-family major/soundness issue:

`Step 7` hot-path evaluation had been guarded against `source_digest`, artifact, ghost, and exterior drift, but the guard did not mirror all `Step 6` attachability obligations. In particular, if `Step 6` would return `HOLD` because the cut's `oracle_abstraction_version` is unavailable or an active assumption no longer holds, `Step 7` could still evaluate the cut and return `True` before replay/store machinery handled the HOLD transition.

In a certified-exact setting this is a soundness blocker: a cut that is not currently attachable must not prune, even if its literal/geometric predicate happens to match the incumbent. The fix makes `Step 7` evaluation use a side-effect-free mirror of `step_6_attach_scope_check`; only `ATTACH` can evaluate, and both `HOLD` and `QUARANTINE` fail closed in the hot path.

The P1.2 close counter therefore remains **0/3**. The next clean-review attempt must be built from a package that includes this consolidation patch.

## Why v29-v31 kept finding new issues

The recurring class was not a single formula bug. It was duplicated proof obligations across lifecycle faces:

1. generator / validator / replay checked one surface;
2. Step 7 family or generic evaluators checked a partially overlapping surface;
3. source digest and artifact hashes covered another surface;
4. runtime caches created hidden source-of-truth shadows;
5. phase-gate provenance carried review state separately from evidence.

Each local fix closed the concrete path found by one review but left the sibling obligation in another lifecycle face. V30 found ghost-bound evaluator drift. V31 generalized that to source/artifact drift and candidate cache drift. This postmortem found the remaining Step 6-to-Step 7 mismatch for oracle versions and active assumptions.

## Consolidated proof obligations

The follow-up patch adds `data/proof_obligations/p1_2_proof_obligations.json` plus `scripts/check_p1_2_proof_obligations.py`. The manifest is deliberately small and machine-checkable. It anchors four proof-obligation families:

1. **PO-STEP7-ATTACH-MIRROR**: every Step 7 evaluator must fail closed unless the side-effect-free Step 6 attach decision is `ATTACH`. This includes source digest, ghost/exterior scope, artifact hashes, oracle abstraction version, and active assumptions.
2. **PO-SOURCE-DIGEST-COVERAGE**: source digest fields are declared as code constants and checked against the manifest so future validator/generator source facts do not drift silently.
3. **PO-RUNTIME-CACHE-NON-AUTHORITY**: `__*` runtime caches are not proof sources. Validators that build caches must rebuild or invalidate them from canonical source payloads.
4. **PO-PHASE-GATE-PROVENANCE**: the phase gate's current review anchor and last reset must follow the latest resetting review/postmortem entry.

This is not a theorem prover. It is a guardrail that turns the V29-V31 postmortem into a finite checklist, so the next external review can search for new bug classes instead of rediscovering adjacent copies of the same duplicated obligation.

## Code changes

The patch centralizes Step 7 attachability:

- `SOURCE_DIGEST_SCHEMA_VERSION` and `SOURCE_DIGEST_FIELD_NAMES` now declare the digest contract in code.
- `STEP_7_EVALUATION_GUARD_OBLIGATIONS` now declares the Step 7 guard contract in code.
- `step_7_evaluation_attach_decision(cut, state)` delegates directly to `step_6_attach_scope_check(cut, state)`.
- `evaluator_scope_matches_current_state(cut, state)` is now a boolean wrapper over that decision.
- `step_7_evaluate_cut` and `evaluate_literal_multiset` continue to call the boolean guard, so geometric and literal hot paths share the same attachability predicate.

The patch adds regressions for:

- Step 7 failing closed when oracle version is unavailable before replay HOLD;
- Step 7 failing closed when an active assumption no longer holds before replay HOLD;
- existing source-digest and runtime-cache regressions remaining part of the proof-obligation manifest.

## Review guidance for the next package

Do not count this postmortem as a clean review. The next package should be reviewed as the first candidate after `v31_postmortem_consolidation`.

For the next external GPT Pro review, require every major finding to state:

1. the exact reachable code path;
2. a minimal witness or regression test shape;
3. whether the path is reachable in the current certified lifecycle;
4. how it can cause a false negative or fake certified claim;
5. which machine gate should have caught it but did not.

This keeps the standard strict without letting theoretical unreachable worries reset the counter forever.
