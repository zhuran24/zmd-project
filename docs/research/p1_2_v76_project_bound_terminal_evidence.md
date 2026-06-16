# P1.2 V76 project-bound terminal evidence review

Date: 2026-06-10

Review anchor: `v76_project_bound_terminal_evidence`

## Result

No new architecture-breaking flaw was found in the public CERTIFIED surface architecture. The V73-V75 shape is still the right spine: public readers do not infer CERTIFIED from local checkpoint fields; they must pass through `src/search/certified_surface.py`, which binds the checkpoint, recomputed exact artifact hashes, `final_solution.json`, `optimal_blueprint.json`, and `certified_delivery_manifest.json` into one fail-closed verifier.

V76 closes a remaining pre-publication seam. The public verifier and resume validation already rejected project-domain mismatches, but the in-memory helper path could still consider terminal frontier evidence valid without binding it to the current project grid and authoritative safe-area bound. That made `ExactCampaign.best_certified_result()` a weaker internal predicate than the public verifier. It was not a direct public false-positive path after V73-V75, but it was still a bad doorframe: a future writer could accidentally hang export logic on the weaker helper.

## Finding

`has_valid_terminal_full_frontier_certified_evidence(state)` intentionally validates a checkpoint-local terminal frontier contract. Without project context, that predicate can accept replayable evidence for a smaller candidate domain if the evidence is internally consistent. The canonical project-bound check lives in resume validation, where `terminal_frontier_evidence_violation(..., grid_dimensions=..., safe_area_upper_bound=...)` is called with values loaded from the project artifacts.

The gap was that `ExactCampaign.best_certified_result()` and delivery-manifest best-result construction used the checkpoint-local predicate first. Current public delivery was still protected by later central-verifier and resume-currentness checks, but the internal predicate boundary was too soft for a safety closure round.

## Patch

V76 adds project-bound terminal-evidence helpers in `src/search/exact_campaign.py`:

- `terminal_certified_final_result_violation_for_project(...)`
- `has_valid_terminal_full_frontier_certified_evidence_for_project(...)`

These helpers load the canonical grid and safe-area upper bound from the current project and fail closed if those artifacts cannot be read. They are now used by:

- `ExactCampaign.best_certified_result()`
- `src/io/delivery_manifest.py::_build_best_certified_result_payload(...)`
- the central certified-surface verifier's terminal-valid summary path

The delivery manifest also reports the project-bound violation reason before constructing a best-result payload.

## Regression

`test_v76_best_certified_result_rejects_frontier_evidence_not_bound_to_project_domain` builds a 2x2 project, then forges internally consistent terminal frontier evidence for only a 1x1 domain. The checkpoint-local predicate still returns true, demonstrating the narrowness of the local check, but `campaign.best_certified_result()` now returns `None` and resume validation reports `terminal_frontier_candidate_generation_grid_mismatch`.

The proof-obligation gate also had a concrete close-blocker: `test_p1_2_proof_obligation_manifest_has_required_ids` still expected the old V66 phase anchor even though the live manifest and gate had advanced to V75. V76 updates that assertion and moves the current anchor to this review package.

## Closure position

Architecture status: acceptable. The central public CERTIFIED gate is still the correct architecture.

Residual policy status: P1.2 remains blocked by the manual close gate. This patch does not claim owner clean-review credit and does not open P1.3B. It removes one internal helper inconsistency and one stale gate-test assertion so the next safety review starts from the current anchor rather than a historical V66/V75 mismatch.
