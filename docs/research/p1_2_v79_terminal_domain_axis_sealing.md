# P1.2 V79 terminal candidate-domain axis sealing

> **[Snapshot note]** Written before the P1.2 close. Statements like "P1.2 remains blocked" reflect the state at writing time; P1.2 was closed by explicit owner_manual_decision on 2026-07-07 (P1.3 opened). Current authority: data/review_gates/phase_1_2_spike_close.json.

Date: 2026-06-10

Review anchor: `v79_terminal_domain_axis_sealing`

## Result

No new architecture-breaking flaw was found in the V73-V78 certified-surface
architecture. The remaining gap was inside the V75 terminal-evidence contract
itself: the validator sealed two of the four candidate-domain slicing axes and
left the other two open.

This round came from an internal multi-lens adversarial review of the V75/V76
test migration (independent lenses, with empirical probes against the real
validator), so the finding class is the same one V75's own document names: "a
sliced generation domain could masquerade as full-domain exhaustion".

## Finding

`terminal_frontier_evidence_violation` rejected `start_area` slices
(`terminal_frontier_start_area_not_full_domain`) and non-authoritative
`area_upper_bound` (`terminal_frontier_area_upper_bound_not_authoritative`),
but two sibling axes of the same candidate-generation contract were recorded in
the evidence, replayed during validation, and never validated:

1. `max_aspect_ratio` filters high-aspect candidates out of the generated
   domain (`generate_candidate_sizes`). An exhausted aspect-sliced domain
   validated as terminal full-frontier CERTIFIED even though the filtered
   candidates were never refuted. Empirical probe: on a 6x6 grid with
   `max_aspect_ratio=3.0` the domain shrinks from 21 to 18 candidates, the
   excluded `(6,1)` candidate is never solved, and the validator returned
   `None` (no violation) for a CERTIFIED claim over the sliced domain. The axis
   is reachable end-to-end via `main.py --max-aspect-ratio`.
2. `min_side` was validated only against grid bounds. PROJECT_LOCK fixes
   `min_side >= 6` as admissibility, so the certified target domain is exactly
   the `min_side=6` domain. A search run with `min_side > 6` exhausts a strict
   sub-domain of the target domain; its terminal claim is unsound for the
   project objective. A `min_side < 6` run searches a superset and stays safe.

A third, sibling seam sat on the publication side: the V77/V78 delivery
manifest deep validation silently skipped the blueprint-to-facility-pools
reverse lookup when the terminal `final_result.placement_solution` was not
instance-shaped (`_looks_like_instance_placement_solution` false), instead of
failing closed. Real solver output is always instance-shaped pose picks, so a
non-instance shape on the terminal certified path can only be a forged or
corrupted payload and must not publish.

## Patch

`src/search/certified_frontier.py`:

- new constant `TERMINAL_FRONTIER_MIN_SIDE_ADMISSIBILITY = 6` (PROJECT_LOCK
  admissibility floor);
- `terminal_frontier_evidence_violation` now rejects
  `max_aspect_ratio is not None` with
  `terminal_frontier_aspect_ratio_sliced_domain` and
  `min_side > TERMINAL_FRONTIER_MIN_SIDE_ADMISSIBILITY` with
  `terminal_frontier_min_side_sliced_domain`, beside the existing `start_area`
  and `area_upper_bound` authority checks.

`src/io/delivery_manifest.py`:

- `_validate_optimal_blueprint_matches_final_result` now raises for a terminal
  certified `final_result` whose `placement_solution` is not instance-shaped,
  instead of returning early and skipping the deep blueprint recovery check.

Production defaults are unaffected: `main.py` ships `--min-side` default `6`
and `--max-aspect-ratio` default `None`, and the real benders path emits
instance-shaped placement solutions.

## Regression

New tests:

- `test_v79_resume_rejects_terminal_evidence_from_aspect_ratio_slice`
- `test_v79_resume_rejects_terminal_evidence_from_min_side_slice`
- `test_v79_delivery_manifest_rejects_non_instance_placement_solution`
- `test_aspect_ratio_sliced_search_cannot_claim_terminal_certified`
  (end-to-end: an aspect-sliced `run_outer_search` exits UNPROVEN instead of
  publishing terminal CERTIFIED)

One existing test was updated: `test_v65_terminal_result_is_committed_before_
final_solution_export` used a non-instance mock solution shape as a shortcut;
it now uses the instance-shaped pose pick that real solver output has.

Validation commands used for this patch:

```bash
python scripts/check_p1_2_proof_obligations.py
python -m pytest -p no:randomly -q src/tests/test_delivery_manifest.py \
  src/tests/test_p1_2_proof_obligations.py \
  src/tests/test_v62_candidate_frontier_contract.py \
  src/tests/test_v63_terminal_evidence_contract.py \
  src/tests/test_exact_campaign_inspector.py \
  src/tests/test_regression.py \
  src/tests/test_parallel_scheduler.py \
  src/tests/test_exact_contract.py
```

## Closure position

Architecture status: acceptable with the V79 repair. The candidate-generation
contract now has all four slicing axes (`start_area`, `area_upper_bound`,
`max_aspect_ratio`, `min_side`) explicitly sealed in the terminal-evidence
validator, and the certified publication path rejects non-replayable placement
shapes.

Known residual (left open for the next review round): a `--min-side` value
*below* the admissibility floor produces a superset domain, which is safe for
exhaustion soundness and therefore accepted by V79; but such a run can publish
a sub-admissible rectangle (final `min(w,h) < 6`) as the terminal CERTIFIED
best with no publication-time admissibility guard. Sealing this axis cleanly
needs a project-level admissibility field (toy test projects legitimately use
smaller `min_side` floors), which is a canonical-schema decision rather than a
validator patch; the production CLI default (`--min-side 6`) does not reach
this shape.

Residual policy status: P1.2 remains blocked by the manual close gate. V79 is a
safety patch and audit anchor update only. It does not claim owner clean-review
credit and does not open P1.3B.
