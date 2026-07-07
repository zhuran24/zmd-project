# P1.2 V92 release-status allowlist sealing

> **[Snapshot note]** Written before the P1.2 close. Statements like "P1.2 remains blocked" reflect the state at writing time; P1.2 was closed by explicit owner_manual_decision on 2026-07-07 (P1.3 opened). Current authority: data/review_gates/phase_1_2_spike_close.json.

Date: 2026-06-11

Review anchor: `v92_release_status_allowlist_sealing`

## Result

Twelfth overnight independent review round: one soundness finding on the
public release surface, reproduced locally before patching. Owner
clean-streak count remains 0.

## Finding

### F-01 (fake certified claim): embedded CERTIFIED tokens bypassed the V81 release guard

The V81 guard rejected only a `status` exactly equal to `CERTIFIED`
(case-insensitively). A forged run summary with
`status: CERTIFIED_BY_FAKE_RELEASE_SUMMARY` sailed through into the release
manifest, the active pointer, and the human-facing Markdown surfaces
(reproduced end to end across the release builder and the render
entrypoints/frontdoor/landing/surface-alignment projections). The guard is
now an allowlist: the exact status must be one of the known non-certified
values (e.g. `open`), any value containing a certified claim fails closed,
and the render surfaces validate the same contract before projecting.

## Regression

New tests in `src/tests/test_v81_release_certified_claim_guard.py`
(embedded-claim rejection and non-allowlisted-status rejection, from the
reviewer bundle, locally re-verified). Zero collateral: full suite at the
documented environmental baseline (2819 passed).

## Review provenance

Reviewer report/probe/outputs archived under the 2026-06-11 10:0x
`补丁包/gpt_deliveries/` directory.

## Closure position

Sealed fail-closed; the release-status contract is now deny-unknown like the
rest of the certified surface. Residuals carried forward: proof-carrying
candidate certificates (future work), `EXACT_SUBPROBLEM_PARAMS` on watch.

Residual policy status: P1.2 remains blocked by the manual close gate. V92
does not claim owner clean-review credit and does not open P1.3B.
