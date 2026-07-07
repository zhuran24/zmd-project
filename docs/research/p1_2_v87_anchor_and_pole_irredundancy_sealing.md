# P1.2 V87 ghost-anchor and pole-irredundancy terminal sealing

> **[Snapshot note]** Written before the P1.2 close. Statements like "P1.2 remains blocked" reflect the state at writing time; P1.2 was closed by explicit owner_manual_decision on 2026-07-07 (P1.3 opened). Current authority: data/review_gates/phase_1_2_spike_close.json.

Date: 2026-06-11

Review anchor: `v87_anchor_and_pole_irredundancy_sealing`

## Result

Seventh overnight independent review round: two algorithmic/soundness
findings, both adversarial deepenings of the V84/V86 terminal replay, both
reproduced locally before patching. Owner clean-streak count remains 0.

## Findings

### F-1 (fake certified claim): unforced power poles accepted as occupancy blockers

V84 rejects unknown extra instances, but authorized `pose_optional::power_pole`
entries beyond what the power-coverage obligation actually forces were still
counted as occupancy. A forged checkpoint could flood empty cells with
"legitimate" surplus poles, shrinking the apparent best empty rectangle and
publishing a smaller ghost as optimal. The validator now rejects power-pole
entries that cover no powered facility that another selected pole does not
already cover
(`terminal_certified_final_result_solution_unforced_power_pole_instance`).

### F-2 (fake certified claim): published ghost anchor never replayed

The witness scans prove some placement of the claimed rectangle exists, but
`final_result.ghost_rect.anchor_x/y` — the coordinate actually published into
the blueprint — was never checked. A forged result could publish a CERTIFIED
empty rectangle sitting on top of facilities. The validator now verifies the
claimed anchor region is in-bounds and unoccupied
(`terminal_certified_final_result_ghost_rect_anchor_occupied`).

## Regression

New: `src/tests/test_v87_terminal_ghost_anchor_validation.py` and
`src/tests/test_v87_terminal_power_pole_irredundancy.py` (from the reviewer
bundle, locally re-verified). Zero collateral: full suite back at the
documented environmental baseline (2806 passed).

## Review provenance

Reviewer report/probes/outputs archived under
`补丁包/gpt_deliveries/20260611_061810/`.

## Closure position

Both findings sealed fail-closed; production unaffected (the real master only
selects forced poles and publishes the anchor it actually proved). Residuals
carried forward: proof-carrying candidate certificates (future work),
`EXACT_SUBPROBLEM_PARAMS` on watch.

Residual policy status: P1.2 remains blocked by the manual close gate. V87
does not claim owner clean-review credit and does not open P1.3B.
