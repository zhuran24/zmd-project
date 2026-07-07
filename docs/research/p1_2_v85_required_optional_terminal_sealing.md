# P1.2 V85 required-optional terminal sealing

> **[Snapshot note]** Written before the P1.2 close. Statements like "P1.2 remains blocked" reflect the state at writing time; P1.2 was closed by explicit owner_manual_decision on 2026-07-07 (P1.3 opened). Current authority: data/review_gates/phase_1_2_spike_close.json.

Date: 2026-06-11

Review anchor: `v85_required_optional_terminal_sealing`

## Result

Fifth overnight independent review round: one algorithmic/soundness finding,
reproduced locally before patching. Owner clean-streak count remains 0.

## Finding

### F-01 (fake certified claim / proof obligation bypass): terminal validator did not enforce inferred required pose-level optionals

The exact master proves CERTIFIED solutions under
`sum(protocol_box_terms) >= protocol_storage_box_count`, where the count is
inferred from `generic_io_requirements` by
`infer_certified_optional_lower_bounds()`; the safe-area upper bound also
deducts that optional area. But the project-bound terminal validator only
enforced mandatory coverage, so a forged checkpoint could omit the required
`pose_optional::protocol_storage_box::*` entries entirely. The omitted box
never entered the occupancy grid, so the witness/optimality scans validated an
empty rectangle that cannot exist once the box is actually placed (reproduced
end-to-end on a 3x3 toy whose only box pose sits inside the claimed 2x2:
`surface_publishable=True` with `required_optional_present=False`).

Patch: the terminal validator now loads the same canonical authority
(`canonical_rules` + `generic_io_requirements`), reuses
`infer_certified_optional_lower_bounds()`, and fails closed with
`terminal_certified_final_result_solution_missing_required_optional_instance`
when the placement solution carries fewer authorized pose-level optional
entries than the inferred lower bound; their occupancy participates in the
witness scans.

## Regression

New: `src/tests/test_v85_terminal_required_optionals.py` (from the reviewer
bundle, locally re-verified). Zero collateral: the full suite returned to the
documented environmental baseline (2802 passed) without any test adaptation.

## Review provenance

Reviewer report/probe/outputs archived under
`补丁包/gpt_deliveries/20260611_050926/`.

## Closure position

Sealed fail-closed; production unaffected (the real master always places the
required optionals). Residuals carried forward: proof-carrying candidate
certificates (future work), `EXACT_SUBPROBLEM_PARAMS` on watch.

Residual policy status: P1.2 remains blocked by the manual close gate. V85
does not claim owner clean-review credit and does not open P1.3B.
