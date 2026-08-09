# P1.2 V84 layout-optimality and artifact-boundary sealing

> **[Snapshot note]** Written before the P1.2 close. Statements like "P1.2 remains blocked" reflect the state at writing time; P1.2 was closed by explicit owner_manual_decision on 2026-07-07 (P1.3 opened). Current authority: data/review_gates/phase_1_2_spike_close.json.

Date: 2026-06-11

Review anchor: `v84_layout_optimality_and_artifact_boundary_sealing`

## Result

Fourth overnight independent review round: three algorithmic/soundness
findings, all adversarial deepenings of the V83 geometric re-verification, all
reproduced locally before patching. Owner clean-streak count remains 0.

## Findings

### F-1: witness scan proved existence, not optimality

The V83 witness scan accepted any placement of the claimed rectangle. A forged
checkpoint could therefore claim a small rectangle while the final layout
plainly contained a larger one (reproduced: claimed 1x1 published while a 2x2
existed). Terminal validation now computes the layout's lex-best empty
rectangle (admissibility-floored) and rejects when it beats the claim
(`terminal_certified_final_result_layout_has_better_empty_rect`). This is
sound because the final layout is itself a feasible witness for the larger
size, contradicting the frontier's INFEASIBLE/dominance story for it.

**Landing scope correction**: the optimality scan is gated on a non-empty
mandatory set. With no mandatory instances every candidate is trivially
feasible on the empty grid, so any non-full-grid claim would be "improvable";
that shape exists only in synthetic test projects, while the production
mandatory set (266 instances) is non-empty and pinned by the frozen-artifact
hashes. The existence witness and all other V83/V84 checks remain
unconditional.

### F-2: exact artifact hashing followed symlinks

`sha256_file` accepted symlinked artifacts, letting out-of-project files enter
the certified evidence boundary (reproduced: a symlinked
`candidate_placements.json` reached `surface_publishable=True` with
`regular_file: False` in the manifest). It now rejects symlinks and
non-regular files.

### F-3: unknown extra placement instances forged occupancy blockers

The terminal placement solution accepted arbitrary extra instance entries,
which entered the occupancy grid and could block the witness scan from seeing
better empty rectangles (composing with F-1). Unknown instances — anything
not in the mandatory set and not the `ghost_pick` marker — now fail closed
(`terminal_certified_final_result_solution_unknown_instance`).

## Regression

New: `src/tests/test_v84_terminal_layout_max_empty_rect.py` (3 tests, from the
reviewer bundle, locally re-verified). Collateral adaptations: the inspector
toy grid shrinks to 2x2 and the b5a toy to 5x1 so their terminal claims are
the layouts' true maxima; one condition-cut anchor index recomputed for the
smaller grid; two out-of-order scheduler mocks now use the `ghost_pick` key
instead of custom keys; full suite back to the documented environmental
baseline (2801 passed).

## Review provenance

Reviewer report/probes/outputs archived under
`补丁包/gpt_deliveries/20260611_041603/`.

## Closure position

All three findings sealed fail-closed. Residuals carried forward:
proof-carrying candidate certificates (future work), `EXACT_SUBPROBLEM_PARAMS`
on watch.

Residual policy status: P1.2 remains blocked by the manual close gate. V84
does not claim owner clean-review credit and does not open P1.3B.
