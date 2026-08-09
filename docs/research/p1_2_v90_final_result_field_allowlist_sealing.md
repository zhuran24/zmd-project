# P1.2 V90 final-result field-allowlist sealing

> **[Snapshot note]** Written before the P1.2 close. Statements like "P1.2 remains blocked" reflect the state at writing time; P1.2 was closed by explicit owner_manual_decision on 2026-07-07 (P1.3 opened). Current authority: data/review_gates/phase_1_2_spike_close.json.

Date: 2026-06-11

Review anchor: `v90_final_result_field_allowlist_sealing`

## Result

Tenth overnight independent review round: one algorithmic/soundness finding,
reproduced locally before patching. Owner clean-streak count remains 0.

## Finding

### F-01 (fake certified claim): unbound top-level final_result fields projected into public artifacts

The terminal `final_result` accepted arbitrary top-level fields. A forged
checkpoint could inject an unbound `routing_solution` (never tied to the
candidate record, solution digest, or any proof obligation) and have it
projected verbatim into the public `optimal_blueprint.json` while the
certified surface stayed `publishable=True` (reproduced: forged belt routes
appeared in the published blueprint). The terminal validator now applies the
deny-unknown paradigm to the `final_result` top level itself: only
`ghost_rect`, `placement_solution`, `search_status`, and `search_stats` are
allowed; any other field fails closed with
`terminal_certified_final_result_unknown_field:<name>`. The real solver path
publishes exactly the allowlisted fields (verified end to end).

## Regression

`test_v72_delivery_manifest_rejects_blueprint_missing_terminal_routing_solution`
is rewritten in place: the old scenario constructed a final_result carrying a
top-level routing_solution, which the allowlist now rejects earlier; the test
asserts the new unknown-field violation. Zero other collateral: full suite at
the documented environmental baseline (2813 passed).

## Review provenance

Reviewer report/probes/outputs archived under the 2026-06-11 09:0x
`补丁包/gpt_deliveries/` directory.

## Closure position

Sealed fail-closed; this closes the deny-unknown loop begun in V80 — evidence
keys (V80), env knobs (V80), candidate-generation contract (V80), and now the
published final_result shape itself are all closed sets. Residuals carried
forward: proof-carrying candidate certificates (future work),
`EXACT_SUBPROBLEM_PARAMS` on watch.

Residual policy status: P1.2 remains blocked by the manual close gate. V90
does not claim owner clean-review credit and does not open P1.3B.
