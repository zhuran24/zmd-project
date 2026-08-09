# P1.2 V80 deny-unknown certified-surface hardening

> **[Snapshot note]** Written before the P1.2 close. Statements like "P1.2 remains blocked" reflect the state at writing time; P1.2 was closed by explicit owner_manual_decision on 2026-07-07 (P1.3 opened). Current authority: data/review_gates/phase_1_2_spike_close.json.

Date: 2026-06-10

Review anchor: `v80_deny_unknown_certified_surface`

## Result

V80 closes the V79 known residual and replaces two remaining enumerative
certified defenses with closed contracts. The patch does not change the nine cut
families, the master/binding/routing mathematical models, or the P1.3B
`PoseBoolExactMaster` integration boundary.

The certified path is stricter after this round:

- terminal-frontier evidence schema v2 is project-bound to the canonical
  empty-rectangle admissibility floor;
- unknown `candidate_generation` keys and stale v1 evidence fail closed;
- terminal CERTIFIED publication is refused when the final rectangle is below
  the project-level `min_side_admissibility`;
- `certified_exact` `EXACT_*` env handling is a closed allowlist rather than a
  blacklist of known-bad knobs.

## Finding

V79 sealed `max_aspect_ratio` and above-admissibility `min_side` slices but
honestly left one residual: a run with `min_side` below the project floor searches
a superset, so exhaustion is safe, yet its lexicographic best over that superset
can be sub-admissible. Before V80, no publication layer knew the project
admissibility floor, so such a terminal result could look CERTIFIED.

The same pattern remained in two other places. `terminal_frontier_evidence_violation`
accepted any future `candidate_generation` key unless the validator had already
learned that key as a bad axis. The certified env guard in `benders_loop.py`
blacklisted known unsafe knobs while the source tree contained hundreds of
`EXACT_*` names, so any future or overlooked proof-semantics knob began life as
trusted until audited.

These are not independent one-off bugs; they are the same fail-open shape:
unknown certified-surface axes were implicitly allowed.

## Patch

`rules/canonical_rules.json`, `rules/canonical_rules.schema.json`, and
`src/rules/models.py` now define the canonical project field
`globals.empty_rectangle` with objective `max_lex_area_min_side` and a positive
integer `min_side_admissibility`. The production project value is `6`; toy
projects may declare smaller positive floors in their own canonical rules.
`TERMINAL_FRONTIER_MIN_SIDE_ADMISSIBILITY` remains as the production projection
and compatibility default, not as the schema authority.

`src/search/certified_frontier.py` bumps terminal evidence to schema v2 and
turns `candidate_generation` into a closed domain contract. The only admitted
keys are the known generation parameters plus `domain_authority`,
`safe_area_upper_bound`, and `min_side_admissibility`. Unknown keys return
`terminal_frontier_candidate_generation_unknown_key`; v1 evidence fails schema
validation; min-side mismatches return
`terminal_frontier_min_side_admissibility_mismatch`; and a terminal final result
below the project floor returns
`terminal_frontier_final_result_below_admissibility`.

`src/search/exact_campaign.py` loads the canonical empty-rectangle admissibility
from the current project and binds resume/import validation to that value.
`src/search/outer_search.py` writes the same value into terminal evidence before
any project-bound full-frontier evidence can be accepted. Existing export-surface
verifiers continue to consume the central campaign evidence path, so no new
publication authority is introduced.

`src/search/benders_loop.py` now classifies the checked-in `EXACT_*` surface.
In `certified_exact`, operational knobs on the explicit allowlist may be
present; known proof-semantics knobs must stay false or canonical default; and
unclassified future `EXACT_*` names fail closed with
`unclassified_exact_env_not_certified`. The legacy specialized blockers remain
in place so existing violation codes such as `ghost_anchor_filter_not_certified`
and `power_coverage_witness_encoding_not_certified` are preserved.

## Regression

New red tests include:

- `test_v80_resume_rejects_terminal_evidence_unknown_candidate_generation_key`
- `test_v80_resume_rejects_terminal_evidence_min_side_admissibility_mismatch`
- `test_v80_resume_rejects_v1_terminal_frontier_evidence_schema`
- `test_v80_resume_rejects_terminal_final_result_below_project_admissibility`
- `test_v80_certified_exact_env_guard_blocks_unclassified_exact_knob`
- `test_v80_certified_exact_env_guard_blocks_known_proof_knob`
- `test_v80_certified_exact_env_guard_allows_production_wrapper_operational_envs`

Validation commands used for this patch:

```bash
python scripts/check_p1_2_proof_obligations.py
python -m pytest -p no:randomly -q \
  src/tests/test_delivery_manifest.py \
  src/tests/test_p1_2_proof_obligations.py \
  src/tests/test_v62_candidate_frontier_contract.py \
  src/tests/test_v63_terminal_evidence_contract.py \
  src/tests/test_exact_campaign_inspector.py \
  src/tests/test_parallel_scheduler.py \
  src/tests/test_exact_contract.py
python -m pytest -p no:randomly -q \
  src/tests/test_delivery_manifest.py \
  src/tests/test_p1_2_proof_obligations.py \
  src/tests/test_v62_candidate_frontier_contract.py \
  src/tests/test_v63_terminal_evidence_contract.py \
  src/tests/test_exact_campaign_inspector.py \
  src/tests/test_regression.py \
  src/tests/test_parallel_scheduler.py \
  src/tests/test_exact_contract.py
```

The last command is expected to retain the known environment failures from the
lightweight package when `data/preprocessed/candidate_placements.json` is absent;
V80 does not fabricate that external certified input.

## Closure position

V80 changes the default posture from "trusted until blacklisted" to
"deny-unknown" on the targeted certified surfaces. A superdomain run can publish
only if its certified lexicographic best is itself admissible under the current
project field. If the all-domain best is sub-admissible, V80 refuses to recover a
"best admissible" result from the same evidence because the existing terminal
projection may have pruned admissible candidates by objective comparison against
a sub-admissible certified incumbent. That missing proof obligation is closed by
refusal, not by reinterpretation.

Known residual: the env allowlist is deliberately conservative but still needs
owner review for production ergonomics. Knobs classified proof-semantics-affecting
may include some harmless aliases or debug constants; this is a safe false
positive, not a certified soundness relaxation. Full-suite validation still
requires the external `candidate_placements.json` artifact named in
`PROJECT_LOCK.md`.

Residual policy status: P1.2 remains blocked by the manual close gate. V80 is a
safety patch and audit anchor update only. It does not claim owner clean-review
credit and does not open P1.3B.
