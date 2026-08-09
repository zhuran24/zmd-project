# P1.2 V93 note and solution-entry sealing

> **[Snapshot note]** Written before the P1.2 close. Statements like "P1.2 remains blocked" reflect the state at writing time; P1.2 was closed by explicit owner_manual_decision on 2026-07-07 (P1.3 opened). Current authority: data/review_gates/phase_1_2_spike_close.json.

Date: 2026-06-11

Review anchor: `v93_note_and_solution_entry_sealing`

## Result

Thirteenth overnight independent review round: two algorithmic/soundness
findings, both reproduced locally before patching. Owner clean-streak count
remains 0.

## Findings

### F-1 (fake certified claim): free-text exact-status note smuggled certified claims

`exact_full_scale_certified.note` was projected verbatim into the release
manifest, active pointer, and Markdown surfaces even under `status: open`
(reproduced: a `CERTIFIED_BY_FAKE_RELEASE_SUMMARY` token reached all three).
The note is now a canonical text bound to the allowlisted status; arbitrary
exact-status prose fails closed across the release builder and every render
projection.

### F-2 (fake certified claim): public placement entries not shape-closed; ghost_pick marker skipped early surfaces

Terminal public `placement_solution` entries accepted forged extra keys
(e.g. `proof_status: CERTIFIED_BY_FORGED_SOLUTION_FIELD`) and a `ghost_pick`
marker in the public final_result was skipped rather than rejected; both
could land in `final_solution.json` via `best_certified_result()` before the
later manifest comparison fired. Placement entries are now shape-closed at
the validator, and a `ghost_pick` marker in the public final_result fails
closed (the public surface strips it by protocol; only candidate records
carry provenance).

## Regression

New tests added in place: a release-note rejection in
`test_v81_release_certified_claim_guard.py` and two terminal rejections in
`test_v91_terminal_nested_public_field_validation.py`. Zero collateral: full
suite at the documented environmental baseline (2822 passed).

## Review provenance

Reviewer report/probes/outputs archived under
`补丁包/gpt_deliveries/20260611_101713/`.

## Closure position

Sealed fail-closed; the public payload (top level, nested shapes, placement
entries) and the release text surfaces are now all closed contracts.
Residuals carried forward: proof-carrying candidate certificates (future
work), `EXACT_SUBPROBLEM_PARAMS` on watch.

Residual policy status: P1.2 remains blocked by the manual close gate. V93
does not claim owner clean-review credit and does not open P1.3B.
