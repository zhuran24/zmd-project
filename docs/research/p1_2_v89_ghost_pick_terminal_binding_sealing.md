# P1.2 V89 ghost-pick terminal binding sealing

Date: 2026-06-11

Review anchor: `v89_ghost_pick_terminal_binding_sealing`

## Result

Ninth overnight independent review round: one algorithmic/soundness finding,
reproduced locally before patching. Owner clean-streak count remains 0.

## Finding

### F-01 (proof obligation bypass / fake certified claim): candidate ghost_pick provenance never replayed

V88 made the master extract the proven `ghost_pick` (with its anchor) into the
candidate solution, but the project-bound terminal validator never replayed
that binding: a forged checkpoint could omit or tamper the candidate record's
`ghost_pick` while the public `final_result` claimed any anchor, and the
surface stayed `publishable=True` (both probe scenarios reproduced). The
validator now requires the winning candidate record to carry a `ghost_pick`
whose anchor matches the published `final_result.ghost_rect` anchor, failing
closed with `terminal_certified_candidate_solution_ghost_pick_missing` /
`..._mismatch` / `..._invalid`.

## Protocol note

Candidate records keep the `ghost_pick` provenance marker; the public
`final_result.placement_solution` deliberately strips it. Test mocks were
adapted accordingly: candidate-side solutions gain the marker (with the toy's
deterministic anchor) while placement-side dicts stay stripped — shared
helpers were split into `_certified_solution` / `_certified_placement` pairs
where one literal had served both roles.

## Regression

New: `src/tests/test_v89_terminal_ghost_pick_protocol_validation.py`
(missing / mismatched / accepted directions, from the reviewer bundle,
locally re-verified). Protocol collateral: ~29 mock adaptations across the
delivery-manifest, inspector, and b5a suites. Full suite back at the
documented environmental baseline (2813 passed).

## Review provenance

Reviewer report/probes/outputs archived under the 2026-06-11 08:1x
`补丁包/gpt_deliveries/` directory.

## Closure position

Sealed fail-closed; production unaffected (the real master writes the marker
it proved). Residuals carried forward: proof-carrying candidate certificates
(future work), `EXACT_SUBPROBLEM_PARAMS` on watch.

Residual policy status: P1.2 remains blocked by the manual close gate. V89
does not claim owner clean-review credit and does not open P1.3B.
