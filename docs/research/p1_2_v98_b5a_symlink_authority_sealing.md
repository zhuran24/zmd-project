# P1.2 V98 B5A symlink-authority sealing

Date: 2026-06-11

Review anchor: `v98_b5a_symlink_authority_sealing`

## Result

Eighteenth overnight independent review round: one algorithmic/soundness
finding, discrimination confirmed (the shipped regression fails on the
unpatched tree and passes on the patched tree). Owner clean-streak count
remains 0.

## Finding

### F-01 (proof obligation bypass / reachable phase-gate false ready): B5A wrapper pre-resolved the campaign path, washing out a symlink alias

This is the B5A sibling of the V97 inspector finding: the central verifier
fails closed on a symlinked campaign path (`campaign_state_not_regular_file`),
but the B5A anchor-sprint wrapper called `.resolve()` on `campaign_state_path`
before handing it to the verifier, so a caller-supplied symlink alias became
a canonical checkpoint and the B5A summary reported
`b5a_certified_surface_public/publishable=True` and `b5a_anchor_found=True`.
Patch: B5A keeps the caller-visible path and lets the central verifier see
and reject the symlink.

## Regression

New: `src/tests/test_v98_b5a_symlink_campaign_path_authority.py` (verified to
fail on the unpatched tree, pass on the patched tree). Zero collateral: full
suite at the documented environmental baseline (2833 passed).

## Review provenance

Reviewer report/probe archived under the 2026-06-11 17:2x
`补丁包/gpt_deliveries/` directory.

## Closure position

Sealed fail-closed; with V97 (inspector) and V98 (B5A wrapper), no public
surface pre-resolves the campaign path before the central authority check.
Residuals carried forward: proof-carrying candidate certificates (future
work), `EXACT_SUBPROBLEM_PARAMS` on watch.

Residual policy status: P1.2 remains blocked by the manual close gate. V98
does not claim owner clean-review credit and does not open P1.3B.
