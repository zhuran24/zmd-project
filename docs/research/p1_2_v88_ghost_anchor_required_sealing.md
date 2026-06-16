# P1.2 V88 ghost-anchor required sealing

Date: 2026-06-11

Review anchor: `v88_ghost_anchor_required_sealing`

## Result

Eighth overnight independent review round: one algorithmic/soundness finding,
reproduced locally before patching. Owner clean-streak count remains 0.

## Finding

### F-01 (fake certified claim): missing anchor fields bypassed the V87 anchor replay

`final_result.ghost_rect` could omit `anchor_x`/`anchor_y` entirely; the V87
anchor replay only fired when the fields were present, and the blueprint
serializer fell back to `anchor=-1,-1` while the surface stayed
`publishable=True`. The protocol now requires the anchor: the exact master
extracts the selected ghost pick (with its proven anchor) into the solution,
the published `ghost_rect` always carries `anchor_x`/`anchor_y`, terminal
validation fails closed on a missing anchor
(`terminal_certified_final_result_ghost_rect_anchor_missing`), and the
serializer refuses to emit a certified blueprint without one.

## Landing corrections

The reviewer patch injected the `ghost_pick` marker into the master solution
but missed five downstream consumers that treat every solution entry as a
facility with a pool pose; the real-solver end-to-end path crashed with
`KeyError: 'ghost_rect'`. Locally corrected: `_run_flow_diagnostic`,
`_build_owner_by_cell`, `_extract_occupied_cells`, the conflict/nogood
pose-index map (a ghost index must never become a nogood literal), and the
power-placement subproblem occupancy now all skip `ghost_pick`.

## Regression

New: `src/tests/test_v88_*` from the reviewer bundle plus its adaptations to
the V84-V86 terminal tests. Protocol-change collateral: ~21 tests updated for
the now-mandatory anchor (assertion literals gain the deterministic toy
anchors; mock expected-best dicts carry `anchor_x/anchor_y`; the V83 witness
test now expects `ghost_rect_anchor_occupied`, since with a required anchor
the empty-rect-not-witnessed reason became logically unreachable — an empty
anchor region is itself the witness). Full suite back at the documented
environmental baseline (2810 passed).

## Review provenance

Reviewer report/probe/outputs archived under the 2026-06-11 07:1x
`补丁包/gpt_deliveries/` directory.

## Closure position

Sealed fail-closed with the anchor now part of the published protocol.
Residuals carried forward: proof-carrying candidate certificates (future
work), `EXACT_SUBPROBLEM_PARAMS` on watch.

Residual policy status: P1.2 remains blocked by the manual close gate. V88
does not claim owner clean-review credit and does not open P1.3B.
