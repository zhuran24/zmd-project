# P1.2 V59 condition-required cut domain validation

Status: patch evidence for a V59 certified lifecycle false-negative found in `zmd_36.7z`.

## Finding

V58 made condition-required certified power cuts reject unsupported condition keys and metadata self-contradictions.  The remaining sibling was a metadata-consistent `ghost_anchor::(x,y)` condition whose `rect_idx` did not resolve to that anchor in the current candidate master domain.

A persisted campaign candidate could contain `status="INFEASIBLE"` and an `exact_safe_cuts[]` record with:

- `cut_type="power_subproblem_infeasible_nogood"`
- `metadata.kind="power_subproblem_ghost_conditioned_nogood"`
- `source_mode="certified_exact"`
- `exact_safe=true`
- `condition_set={"ghost_anchor::(1,0)": 0}`
- matching metadata, for example `metadata.ghost_rect_idx=0` and `metadata.ghost_anchor={"x": 1, "y": 0}`

For a 2x1 grid and a 1x1 ghost rectangle, the unfiltered master enumerates `(0,0)` as rect index 0 and `(1,0)` as rect index 1.  Replay would fail closed because rect index 0 is not anchor `(1,0)`, but campaign resume accepted the terminal `INFEASIBLE` record before replay.  The outer frontier could then inherit the terminal infeasible state and prune candidates from a cut that is not replay-supported.

## Fail-closed contract extension

For certified exact-safe persisted cuts, a non-empty `condition_set` is now checked at three layers:

- the condition key parser accepts only canonical `ghost_anchor::(x,y)` keys with two non-negative decimal coordinates;
- condition-required power cuts still require exactly one condition and metadata self-consistency;
- `ExactCampaign` resume validates the condition against the current candidate ghost domain, including current grid dimensions, candidate ghost rectangle dimensions, and master rect-index enumeration.

Malformed variants such as whitespace-bearing keys, signed coordinates, negative coordinates, leading-zero ambiguity, underscore separators, extra fields, and overflow-shaped coordinates are rejected before resume or replay.

## Regression anchors

The proof obligation now names grammar regressions, resolver-domain regressions, out-of-domain anchor regressions, and a positive resolver-supported resume case under `PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS`.
