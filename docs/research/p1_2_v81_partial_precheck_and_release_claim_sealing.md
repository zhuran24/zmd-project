# P1.2 V81 partial-precheck and release-claim sealing

Date: 2026-06-11

Review anchor: `v81_partial_precheck_and_release_claim_sealing`

## Result

V81 was the first fully independent external review after the V80 deny-unknown
flip (new zero-history session, full-project snapshot, sandbox-verified probes).
It found one algorithmic/soundness finding and one publication finding. Both are
sealed in this round. The owner clean-streak count is 0.

## Findings

### F-01 (algorithmic/soundness): time-budget-partial precheck group consumed as complete INFEASIBLE proof

`EXACT_MANDATORY_RECTANGLE_PRECHECK_TIME_BUDGET_SECONDS` is an operational
allowlist knob (V80 classification). When the budget expires inside a group,
the producer (`src/models/master_model.py`) marks the group payload with
`partial_due_to_time_budget=True` and only covers the anchor prefix it actually
checked. Both consumers ignored that flag:

- `src/search/benders_loop.py::_triggered_mandatory_rectangle_precheck_group`
- the inline duplicate predicate in
  `src/search/benders_loop.py::run_benders_for_ghost_rect`

Their trigger condition ("all considered anchors screened infeasible, none
unsupported") then misread "an infeasible anchor prefix" as "all anchors
infeasible", and the pre-master consumer converted that into candidate
`INFEASIBLE`. A truly feasible candidate whose feasible anchors were never
reached before the budget expired could be pruned, which is a certified false
negative; downstream terminal frontier evidence cannot distinguish that
INFEASIBLE from a sound one.

Probe (locally reproduced before the patch): a single-group payload with
`considered_anchor_count=1`, `screened_infeasible_anchor_count=1`,
`partial_due_to_time_budget=True` triggered the predicate. After the patch it
returns no trigger, while a complete group (no partial flag) still triggers.

Patch: both predicates now require
`not bool(entry.get("partial_due_to_time_budget", False))`. A group completed
before the budget expired remains a sound proof and still triggers; only the
interrupted group is excluded, so the budget knob keeps its operational
classification (expiry now degrades to "continue solving", never to a proof).

### F-02 (publication): single-base release builder propagated self-claimed CERTIFIED

`scripts/build_industrial_planner_single_base_delivery_release.py` validated
run-summary readiness without binding `exact_full_scale_certified.status` to
any certified authority, then copied that status into the release manifest and
the active pointer. A forged `run_summary.json` claiming `CERTIFIED` produced
release/pointer artifacts that displayed "exact full-scale CERTIFIED status:
CERTIFIED" with no terminal frontier evidence and no certified delivery
manifest.

Patch: `_validate_ready_run_summary` now fails closed when
`exact_full_scale_certified.status` claims `CERTIFIED` (case-insensitive). The
official e2e writes `open` for this field, so the production path is
unaffected. Lifting this restriction requires wiring the release path to the
canonical `certified_surface` verifier verdict, which is future work, not a
config knob.

## Regression

New tests:

- `test_v81_mandatory_rectangle_partial_time_budget_group_is_not_infeasible`
- `test_v81_mandatory_rectangle_complete_group_still_triggers_infeasible`
  (both in `src/tests/test_exact_contract.py`)
- `test_v81_release_rejects_self_claimed_certified_run_summary`
- `test_v81_release_rejects_lowercase_certified_claim`
- `test_v81_release_accepts_open_exact_certified_status`
  (in `src/tests/test_v81_release_certified_claim_guard.py`; deliberately a
  separate module because `test_industrial_planner_single_base_delivery_release.py`
  is skipped wholesale when the `.artifacts` e2e fixture is absent)

Anchors advanced to `v81_partial_precheck_and_release_claim_sealing` across the
proof-obligation manifest (including `phase_gate_required_anchor`), the review
gate (both `current_review_anchor` fields plus an `informational_history`
entry), `scripts/check_p1_2_proof_obligations.py` (required tests plus source
needles for the partial-flag exclusion and the release fail-closed message),
the hardcoded anchor in `src/tests/test_p1_2_proof_obligations.py`, and the
documentation projections.

## Review provenance

External reviewer report archived at
`补丁包/gpt_deliveries/20260611_013112/V81_REVIEW.md` (delivery channel kept the
report; the reviewer's patch/probe bundle links were not collectable, so the
patch in this round was re-implemented locally from the report and re-verified
with local probes). The reviewer also explicitly listed surfaces audited with
no finding: the V80 terminal-evidence deny-unknown contract, the admissibility
publication gate, the env-guard allowlist (besides F-01), budget/anchor knobs
(besides F-01), and the downstream release/viewer/landing surfaces (besides
F-02's source).

## Closure position

Both findings sealed fail-closed; production defaults unaffected
(`EXACT_MANDATORY_RECTANGLE_PRECHECK_TIME_BUDGET_SECONDS` defaults to disabled,
and the official e2e never claims CERTIFIED). Known residuals carried forward
unchanged from V80: v1 terminal evidence stays fail-closed (no migration), the
allowlist keeps conservative proof-affecting classifications, and
`EXACT_SUBPROBLEM_PARAMS` remains a watched risk surface (reviewer found no
exploitable path this round).

Residual policy status: P1.2 remains blocked by the manual close gate. V81 is a
safety patch and audit anchor update only. It does not claim owner clean-review
credit and does not open P1.3B.
