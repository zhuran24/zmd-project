# P1.2 V58 condition-required cut anchor validation

Status: patch evidence for a V58 certified lifecycle false-negative found in `zmd_35.7z`.

## Finding

V57 made condition-required certified power cuts fail closed when persisted without a non-empty `condition_set`.  The remaining sibling was a non-empty but unresolvable or self-contradictory `condition_set`.

A persisted campaign candidate could contain `status="INFEASIBLE"` and an `exact_safe_cuts[]` record with:

- `cut_type="power_subproblem_infeasible_nogood"`
- `metadata.kind="power_subproblem_ghost_conditioned_nogood"`
- `source_mode="certified_exact"`
- `exact_safe=true`
- a non-empty unsupported key such as `unknown_condition_kind::(0,0)`, or a `ghost_anchor::(x,y)` key that disagrees with `metadata.ghost_anchor` / `metadata.ghost_rect_idx`

Before this patch, `ExactCampaign` resume accepted that record because `BendersCut.from_dict` only required the condition set to be present and strictly integer-valued.  The outer frontier could then inherit the terminal `INFEASIBLE` state and prune the candidate without replaying the cut through the master.

## Fail-closed contract extension

For certified exact-safe persisted cuts, any non-empty `condition_set` must use a supported condition key grammar.  The currently supported replayable condition is exactly `ghost_anchor::(x,y)` with two integer coordinates.

For the condition-required power family, validation is stricter:

- exactly one ghost-anchor condition must be present;
- `condition_set["ghost_anchor::(x,y)"]` must match `metadata.ghost_rect_idx`;
- `(x, y)` must match `metadata.ghost_anchor.{x,y}`;
- `BendersCut.from_dict` and `BendersCut.to_dict` apply the same validation;
- generated certified cuts round-trip through `BendersCut` validation before master application, registration, or generated-cut counting;
- replay condition resolution uses the same strict parser as persistence validation.

## Regression anchors

The proof obligation now names malformed non-empty condition-set regressions, metadata mismatch regressions, resume regressions, and replay parser malformed-key regressions under `PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS`.
