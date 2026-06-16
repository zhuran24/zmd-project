# P1.2 V86 power-witness terminal sealing

Date: 2026-06-11

Review anchor: `v86_power_witness_terminal_sealing`

## Result

Sixth overnight independent review round: one algorithmic/soundness finding,
reproduced locally before patching. Owner clean-streak count remains 0.

## Finding

### F-01 (fake certified claim / proof obligation bypass): terminal validator did not replay the power-coverage witness

The exact master requires every `needs_power=true` facility to be covered by a
selected power pole, but the project-bound terminal validator never replayed
that obligation. A forged terminal checkpoint placing a powered mandatory
facility with no `pose_optional::power_pole::*` selection reached
`surface_publishable=True` while the certified exact master proved the same
layout `INFEASIBLE` (reproduced end-to-end; the probe also solved the real
master to show the contradiction).

Patch: the terminal validator now replays power coverage from the same
canonical authority — every placed instance whose template declares
`needs_power` must be covered by the `power_coverage_cells` of a selected
power-pole entry in the placement solution — failing closed with
`terminal_certified_final_result_solution_power_coverage_missing`.

## Regression

New: `src/tests/test_v86_terminal_power_witness_validation.py` (reject +
accept directions, from the reviewer bundle, locally re-verified). Zero
collateral: full suite back at the documented environmental baseline (2804
passed).

## Review provenance

Reviewer report/probe/outputs archived under the latest
`补丁包/gpt_deliveries/` delivery directory for 2026-06-11 06:12.

## Closure position

Sealed fail-closed; production unaffected (the real master always selects
covering poles). Residuals carried forward: proof-carrying candidate
certificates (future work), `EXACT_SUBPROBLEM_PARAMS` on watch.

Residual policy status: P1.2 remains blocked by the manual close gate. V86
does not claim owner clean-review credit and does not open P1.3B.
