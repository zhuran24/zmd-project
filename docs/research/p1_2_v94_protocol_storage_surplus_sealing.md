# P1.2 V94 protocol-storage surplus sealing

> **[Snapshot note]** Written before the P1.2 close. Statements like "P1.2 remains blocked" reflect the state at writing time; P1.2 was closed by explicit owner_manual_decision on 2026-07-07 (P1.3 opened). Current authority: data/review_gates/phase_1_2_spike_close.json.

Date: 2026-06-11

Review anchor: `v94_protocol_storage_surplus_sealing`

## Result

Fourteenth overnight independent review round: one algorithmic/soundness
finding, reproduced locally before patching. Owner clean-streak count
remains 0.

## Finding

### F-01 (fake certified claim): surplus protocol storage boxes accepted as occupancy blockers

V85 replays the generic-io lower bound for required `protocol_storage_box`
optionals, and V87 rejects unforced power poles, but storage boxes beyond the
inferred lower bound were still accepted and counted as occupancy. A forged
checkpoint could flood empty cells with surplus "authorized" boxes, shrinking
the apparent best empty rectangle exactly like the V87 pole blocker
(reproduced: removing the surplus entries flipped the validator to
`layout_has_better_empty_rect`, proving they were the blocker). The validator
now rejects storage-box entries beyond the inferred requirement
(`terminal_certified_final_result_solution_excess_protocol_storage_box_instance`).

## Regression

New: `src/tests/test_v94_terminal_protocol_storage_surplus_validation.py`
(from the reviewer bundle, locally re-verified). Zero collateral: full suite
at the documented environmental baseline (2823 passed).

## Review provenance

Reviewer report/probe/outputs archived under the 2026-06-11 11:2x
`补丁包/gpt_deliveries/` directory.

## Closure position

Sealed fail-closed; with V87 (poles) and V94 (storage boxes), every
pose-level optional class is now bounded both below (required coverage) and
above (no unforced blockers). Residuals carried forward: proof-carrying
candidate certificates (future work), `EXACT_SUBPROBLEM_PARAMS` on watch.

Residual policy status: P1.2 remains blocked by the manual close gate. V94
does not claim owner clean-review credit and does not open P1.3B.
