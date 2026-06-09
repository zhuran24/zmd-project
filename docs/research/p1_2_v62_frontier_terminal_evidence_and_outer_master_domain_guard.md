# P1.2 V62 frontier terminal evidence and outer master-domain guard

Status: reset-grade algorithmic / proof-obligation consolidation input.

Reviewed package: `zmd_40.7z`

Baseline anchor before review: `v61_master_domain_candidate_frontier_contract`

New anchor after review: `v62_frontier_terminal_evidence_and_outer_master_domain_guard`

## Verdict

V62 was not clean. It found sibling/order paths after the V61 master-domain and
candidate-frontier patch. The core issue is that candidate-level evidence could
still become terminal-looking certified evidence before the full certified
lifecycle had actually reached a strict, exhausted frontier.

The phase gate remains manual and fail-closed. This finding does not grant any
repo-derived clean count; it resets the owner-maintained clean-review baseline.

## Reset Family

`v62_frontier_terminal_evidence_and_outer_master_domain_guard`

The family extends `PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS` with three additional
certified lifecycle requirements:

- Candidate-level `CERTIFIED` evidence is only an incumbent until the outer
  frontier terminates with `status=CERTIFIED` and
  `reason=search_exhausted_all_candidates`.
- Master-domain-changing env/debug overrides must fail closed before any
  certified `ExactSearchSession` construction, including outer-search precheck
  and coordinator paths.
- Non-strict or `best_effort` resume states must fail closed before writing
  `final_solution`, `final_result`, delivery manifests, or other
  certified-looking terminal artifacts.

## Findings

### V62-A-01: partial frontier UNKNOWN could export an incumbent as certified

`ExactCampaign.mark_candidate_result()` promoted any candidate-level
`CERTIFIED` solution into `state["final_result"]` before the candidate frontier
was exhausted. Later UNKNOWN/max-attempt/worker-failure stops could preserve or
re-export that incumbent through `best_certified_result()`, `final_solution`,
and the delivery manifest.

Witness: a 6x6 empty project where only candidate `(6, 1)` was explored and
certified, then `max_attempts=1` stopped the campaign as `UNKNOWN`. The campaign
still had `final_status=CERTIFIED`, `final_result`, `final_solution`, and a
delivery manifest.

Required guard: terminal certified delivery must require strict declare mode,
`final_status=CERTIFIED`, `last_stop_reason.status=CERTIFIED`, and
`last_stop_reason.reason=search_exhausted_all_candidates`.

### V62-A-02: outer-search precheck could build a session under unsafe env

V61 guarded unsafe master-domain env overrides inside
`run_benders_for_ghost_rect()`, but `outer_search` could construct and use
`ExactSearchSession` for precheck/coordinator work before reaching that guard.

Witness: with `EXACT_USE_POSE_BOOL_MASTER=1`, the outer precheck path
constructed a session and registered candidate `INFEASIBLE` records without
raising the `unsafe_certified_exact_master_domain_env` blocker.

Required guard: the unsafe master-domain env check must run immediately after
certified campaign load and before probe, precheck, coordinator, or session
construction.

### V62-B-01: best_effort resume wrote certified-looking artifacts before fail-closed

A resume-compatible `declare_mode=best_effort` campaign with certified
candidate records but no `final_result` could pass resume validation. During
terminal exhaustion, outer search wrote `final_solution`, `final_result`, and
`final_status=CERTIFIED`; only after that did the delivery manifest strict
guard throw.

Witness: a best-effort 1x1 campaign produced a manifest exception, but the
state already contained `final_result` / `final_status=CERTIFIED` and
`final_solution.json` already existed.

Required guard: non-strict terminal export must return `UNPROVEN` before any
certified-looking disk artifact or campaign terminal state is written.

## Regression Coverage

The V62 patch adds:

- `test_v62_partial_frontier_unknown_does_not_export_incumbent_as_certified`
- `test_v62_outer_search_blocks_unsafe_master_domain_env_before_session`
- `test_v62_best_effort_exhaustion_blocks_before_final_solution_export`

These tests are part of `PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS`.

## Prompt Implications

Future reviews should start from this V62 anchor. They should not re-report the
direct V61 paths unless a sibling remains. They should instead check whether
any remaining certified lifecycle path can:

- publish candidate-level incumbent evidence before full frontier exhaustion;
- construct a certified session under unsafe master-domain overrides before the
  guard runs;
- write certified-looking artifacts from non-strict or candidate-subset state;
- hide a reset-grade proof-obligation issue under an infrastructure label.

Every reset-grade finding still needs the five-field proof: code path, witness,
reachability, false-negative/fake-certified/gate impact, and the missing gate
or proof obligation.
