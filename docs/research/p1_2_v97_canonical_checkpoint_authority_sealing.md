# P1.2 V97 canonical-checkpoint authority sealing

> **[Snapshot note]** Written before the P1.2 close. Statements like "P1.2 remains blocked" reflect the state at writing time; P1.2 was closed by explicit owner_manual_decision on 2026-07-07 (P1.3 opened). Current authority: data/review_gates/phase_1_2_spike_close.json.

Date: 2026-06-11

Review anchor: `v97_canonical_checkpoint_authority_sealing`

## Result

Seventeenth overnight independent review round: one algorithmic/soundness
finding, reproduced locally before patching (the reviewer's four shipped
regression tests fail on the unpatched tree and pass on the patched tree).
Owner clean-streak count remains 0.

## Finding

### F-01 (proof obligation bypass): non-canonical campaign checkpoint accepted as publishing authority

The central certified surface accepted a non-canonical
`data/checkpoints/shadow_state.json` as a publishing authority: with the
canonical `exact_campaign_state.json` absent, `export_certified_delivery_manifest`,
`evaluate_certified_delivery_surface`, and `build_exact_campaign_inspection`
still produced publishable/CERTIFIED artifacts from the shadow checkpoint. A
sibling: the inspector resolved the campaign path before calling the central
verifier, washing out a symlink alias so the V96 ancestry check never saw it.

Patch: the certified manifest writer forces the checkpoint authority to
`data/checkpoints/exact_campaign_state.json` when a best_certified_result is
present; the central verifier keeps the raw checkpoint path for the
regular-file and symlink-ancestry checks and requires the canonical
checkpoint for certified export; the inspector no longer resolves
`campaign_state_path` before the central verifier. Violations:
`campaign_state_path_not_canonical` and the writer-side
"requires canonical campaign checkpoint authority".

## Regression

New: `src/tests/test_v97_canonical_campaign_state_authority.py` (four
directions; verified to fail on the unpatched tree and pass on the patched
tree). Zero collateral: full suite at the documented environmental baseline
(2832 passed).

## Review provenance

Reviewer report/probes/outputs archived under the 2026-06-11 12:4x
`补丁包/gpt_deliveries/` directory.

## Closure position

Sealed fail-closed; the publishing authority is now pinned to the canonical
in-project checkpoint with no resolve-then-trust gap. Residuals carried
forward: proof-carrying candidate certificates (future work),
`EXACT_SUBPROBLEM_PARAMS` on watch.

Residual policy status: P1.2 remains blocked by the manual close gate. V97
does not claim owner clean-review credit and does not open P1.3B.
