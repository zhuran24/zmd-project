---
status: CURRENT_CODE_ALIGNED
source_of_truth: code-first; main.py, src/search/outer_search.py, src/search/campaign_telemetry.py, src/search/exact_campaign.py
last_verified_against: 2026-03-26
owner: search-runtime
---

# 21 Frontier Probe and Campaign Telemetry

## 1. Scope

This spec records the current exact-safe probe insertion behavior for
`certified_exact` outer search.

Probe mode is a **runtime scheduling improvement only**. It does not change:

- the exact objective `max_lex(area, min_side)`;
- candidate admissibility rules;
- campaign termination conditions;
- certified proof requirements.

## 2. CLI surface

`main.py` exposes:

- `--frontier-probe-mode off|auto`

Default is `off`.

## 3. Activation rules

`auto` may activate a probe round only when all of the following hold:

- solve mode is `certified_exact`;
- the campaign has no certified result yet;
- the current potential domain is still large relative to the frontier;
- no earlier fresh probe has already been executed for the campaign.

If the most recent probe candidate remains unresolved because the campaign stopped
with `UNKNOWN` or `UNPROVEN`, resume keeps that same candidate as the pending
probe instead of selecting a different one.

## 4. Candidate choice

The current probe selector chooses one **non-frontier** candidate from the
potential domain, biased toward the middle of the current domain and toward
near-square shapes.

The current internal probe policy label is:

- `mid_domain_near_square_v1`

This label is telemetry-only and may change with future exact-safe scheduling
revisions.

## 5. Safety boundary

Probe mode is exact-safe because:

1. the probe is still a legitimate candidate from the current potential domain;
2. it is evaluated by the same exact precheck / master / binding / routing path;
3. pruning still happens only through the same certified / infeasible rules;
4. probe insertion changes evaluation order only, not the completeness contract.

Probe mode must not:

- replace the exact frontier as the only source of candidates;
- skip unresolved `UNKNOWN` / `UNPROVEN` candidates and still claim global optimality;
- rewrite campaign evidence using non-exact data.

## 6. Telemetry fields

Campaign telemetry records probe activity additively through:

- `selection_reason`
- wave-level `probe_round_active`
- wave-level `probe_candidate_keys`
- wave-level `probe_prune_gain_sum` / `probe_prune_gain_max`
- aggregate `probe_round_count`
- aggregate `probe_candidate_count`
- aggregate `probe_prune_gain_sum` / `probe_prune_gain_max`
- aggregate `probe_resume_pending_count`
- aggregate `probe_mode_counts`

These are diagnostic/runtime fields only.
