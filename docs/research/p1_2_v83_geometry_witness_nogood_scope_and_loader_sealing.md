# P1.2 V83 geometry-witness, nogood-scope, and mandatory-loader sealing

> **[Snapshot note]** Written before the P1.2 close. Statements like "P1.2 remains blocked" reflect the state at writing time; P1.2 was closed by explicit owner_manual_decision on 2026-07-07 (P1.3 opened). Current authority: data/review_gates/phase_1_2_spike_close.json.

Date: 2026-06-11

Review anchor: `v83_geometry_witness_nogood_scope_and_loader_sealing`

## Result

Third independent overnight review round: three algorithmic/soundness
findings, all reproduced locally before patching. Owner clean-streak count
remains 0.

## Findings

### F-01 (fake certified claim): self-consistent forged checkpoint published geometrically false CERTIFIED

Candidate records were trusted by status alone; terminal final_result
validation never re-derived geometry. A forged checkpoint claiming a 3x2
empty rectangle on a 3x3 toy whose center cell is mandatory-occupied reached
`surface_publishable=True`. Patch: project-bound terminal final_result
validation (mandatory coverage, facility-type match, pose reverse-lookup,
occupancy bounds/overlap, and a real empty-rectangle witness scan over the
occupancy grid), wired into the delivery-manifest export path. This also
guards against solver bugs publishing geometrically wrong results, not just
forged checkpoints. **Local correction to the reviewer patch**: the
`ghost_pick` entry is the empty rectangle's own placement marker; counting it
as occupancy made the witness scan reject every genuine terminal result. The
occupancy collection now skips `ghost_pick` (mandatory coverage and the
witness scan keep the forged-geometry rejection intact). Residual
(reviewer-disclosed): `proof_summary` is still an arbitrary mapping; full
proof-carrying certificates for CERTIFIED/INFEASIBLE candidates remain future
work.

### F-02 (certified false negative): single-layout nogood escalated to candidate INFEASIBLE

On the default coordinate-master path, a binding-INFEASIBLE (and, env-gated,
routing-exhausted) whole-layout nogood led straight to candidate
`RUN_STATUS_INFEASIBLE`, escalating "this layout is infeasible" to "this ghost
size is infeasible" (the in-code comment even documented the shortcut).
Patch: once the whole-layout nogood is applied, return
`master_cut_added_continue` so the LBBD loop reselects layouts; candidate
INFEASIBLE may only come from the master proving the cut-augmented model
empty. The probe and the rewritten
`test_routing_exhaustion_generates_exact_safe_whole_layout_cut` confirm the
candidate-level INFEASIBLE now arrives via the master after the cut.

### F-03 (proof obligation bypass): malformed mandatory_exact_instances silently filtered

The certified loaders accepted dict wrappers and silently skipped records with
`is_mandatory: false` / non-exact bound types, shrinking the certified
instance set and loosening the static-area safe bound. Patch: deny-unknown
loader (top-level array; per-record object with non-empty unique ids,
`is_mandatory is True`, `bound_type == "exact"`), shared by the master loader
and the safe-area bound computation.

## Regression

New: `src/tests/test_v83_certified_surface_soundness.py` (3 tests, from the
reviewer bundle). Rewritten because they pinned sealed behavior:
`test_routing_exhaustion_generates_exact_safe_whole_layout_cut` (final
proof summary now reports the master round) and
`test_unproven_result_is_persisted_to_campaign` (the malformed-artifact route
to UNPROVEN now fails closed at the loader; UNPROVEN persistence remains
covered by the scheduler/inspector suites). One reviewer-updated test in
`test_delivery_manifest.py` adapts to earlier fail-closed ordering.

## Review provenance

Reviewer report/probes/logs archived under
`补丁包/gpt_deliveries/20260611_031728/`. Reviewer-audited-clean surfaces:
V82 oriented domain wiring, persisted-cut channels (no new route into the
master), checkpoint/resume schema, `EXACT_SUBPROBLEM_PARAMS` (still watch).

## Closure position

All three findings sealed fail-closed; production path now does geometric
re-verification at publication. Residuals: proof-carrying candidate
certificates (future work), `EXACT_SUBPROBLEM_PARAMS` on watch.

Residual policy status: P1.2 remains blocked by the manual close gate. V83
does not claim owner clean-review credit and does not open P1.3B.
