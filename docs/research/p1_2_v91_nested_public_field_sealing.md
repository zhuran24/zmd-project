# P1.2 V91 nested public-field sealing

> **[Snapshot note]** Written before the P1.2 close. Statements like "P1.2 remains blocked" reflect the state at writing time; P1.2 was closed by explicit owner_manual_decision on 2026-07-07 (P1.3 opened). Current authority: data/review_gates/phase_1_2_spike_close.json.

Date: 2026-06-11

Review anchor: `v91_nested_public_field_sealing`

## Result

Eleventh overnight independent review round: one algorithmic/soundness
finding, reproduced locally before patching. Owner clean-streak count
remains 0.

## Finding

### F-01 (fake certified claim): allowlisted final_result fields could smuggle forged certified semantics in their nested shapes

V90 closed the `final_result` top level, but the interiors of the allowlisted
fields remained open mappings: `ghost_rect` accepted forged
`proof_status`/`routing_solution_certified` keys that flowed into
`final_solution.json`, `search_stats` accepted a forged `proof_status` that
flowed into the delivery manifest, and mandatory `placement_solution` entries
accepted metadata contradicting the certified contract (`is_mandatory:
false`, `bound_type: heuristic`, `solve_mode: exploratory`) — all while the
central verifier stayed `publishable=True` (reproduced). The nested shapes
are now closed as well: unknown `ghost_rect`/`search_stats` keys fail closed
(`terminal_certified_final_result_ghost_rect_unknown_field:<k>` /
`..._search_stats_unknown_field:<k>`), and mandatory entry metadata must
agree with the certified instance contract.

## Regression

New: `src/tests/test_v91_terminal_nested_public_field_validation.py` (four
directions, from the reviewer bundle, locally re-verified; the reviewer also
pre-adapted the V85-V89 terminal test mocks). Zero further collateral: full
suite at the documented environmental baseline (2817 passed).

## Review provenance

Reviewer report/probes/outputs archived under
`补丁包/gpt_deliveries/20260611_090730/`.

## Closure position

Sealed fail-closed. With V90 (top level) and V91 (nested shapes), the entire
published final_result is now a closed schema. Residuals carried forward:
proof-carrying candidate certificates (future work),
`EXACT_SUBPROBLEM_PARAMS` on watch.

Residual policy status: P1.2 remains blocked by the manual close gate. V91
does not claim owner clean-review credit and does not open P1.3B.
