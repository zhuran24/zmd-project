# P1.2 V95 optional-metadata and stop-reason sealing

Date: 2026-06-11

Review anchor: `v95_optional_metadata_and_stop_reason_sealing`

## Result

Fifteenth overnight independent review round: two algorithmic/soundness
findings, both reproduced locally before patching. Owner clean-streak count
remains 0.

## Findings

### F-1 (fake certified claim): forged public metadata on pose-level optional entries

Pose-level optional placement entries accepted forged public
`instance_id`/`operation_type` metadata (e.g. `operation_type:
CERTIFIED_BY_FORGED_OPTIONAL_OPERATION` flowed into `final_solution.json`
while the surface stayed publishable). Optional-entry public metadata must
now agree with the canonical pose identity
(`terminal_certified_final_result_solution_metadata_mismatch`).

### F-2 (fake certified claim): last_stop_reason carried arbitrary public fields

The terminal `last_stop_reason` accepted extra fields (e.g. a forged `note`)
that were written into `certified_delivery_manifest.json` and passed the
surface verifier. The stop-reason shape is now closed
(`terminal_certified_last_stop_reason_unknown_field:<k>`).

## Regression

New: `src/tests/test_v95_terminal_optional_metadata_validation.py` (both
directions, from the reviewer bundle, locally re-verified). Zero collateral:
full suite at the documented environmental baseline (2826 passed).

## Review provenance

Reviewer report/probes/outputs archived under the 2026-06-11 11:5x
`补丁包/gpt_deliveries/` directory.

## Closure position

Sealed fail-closed; every public payload component (final_result top level,
nested shapes, placement entries including optional metadata, stop reason,
release status/note) is now a closed contract. Residuals carried forward:
proof-carrying candidate certificates (future work),
`EXACT_SUBPROBLEM_PARAMS` on watch.

Residual policy status: P1.2 remains blocked by the manual close gate. V95
does not claim owner clean-review credit and does not open P1.3B.
