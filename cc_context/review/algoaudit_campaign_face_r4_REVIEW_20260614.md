# IndustrialPlanner exact campaign/resume state-machine review, round 4

## Verdict

**本轮零 soundness finding**。

我只认并校验了 `zmd_snapshot_f4418b04.zip`。校验结果：

```text
f4418b045b257e186c0d06ad6045908a33118d597b8f65666fb39691378965d1  zmd_snapshot_f4418b04.zip
```

范围限定在 campaign 持久化、resume 状态机、terminal frontier evidence。并行 scheduler 合并、worker 子问题正确性、Benders/cuts/preprocess/binding/master 各面不在本轮重判内。未修改源代码，因此无 unified diff / patch。

## Files audited

Primary files:

- `src/search/exact_campaign.py`
- `src/search/certified_frontier.py`
- `src/search/outer_search.py`

Support surfaces checked for export/publication fail-closed behavior:

- `src/io/delivery_manifest.py`
- `src/search/certified_surface.py`
- `PROJECT_LOCK.md`

## Regression and probes run

Targeted campaign/terminal test set:

```text
python -m pytest -q -p no:randomly \
  src/tests/test_campaign_freeze_monitor.py \
  src/tests/test_exact_campaign_bound_state.py \
  src/tests/test_exact_campaign_inspector.py \
  src/tests/test_exact_campaign_state_soundness.py \
  src/tests/test_p0_certified_soundness_fixes.py \
  src/tests/test_v62_candidate_frontier_contract.py \
  src/tests/test_v63_terminal_evidence_contract.py \
  src/tests/test_v81_release_certified_claim_guard.py \
  src/tests/test_v83_certified_surface_soundness.py \
  src/tests/test_v84_terminal_layout_max_empty_rect.py \
  src/tests/test_v85_terminal_required_optionals.py \
  src/tests/test_v86_terminal_power_witness_validation.py \
  src/tests/test_v87_terminal_ghost_anchor_validation.py \
  src/tests/test_v87_terminal_power_pole_irredundancy.py \
  src/tests/test_v89_terminal_ghost_pick_protocol_validation.py \
  src/tests/test_v91_terminal_nested_public_field_validation.py \
  src/tests/test_v94_terminal_protocol_storage_surplus_validation.py \
  src/tests/test_v97_canonical_campaign_state_authority.py \
  src/tests/test_v98_b5a_symlink_campaign_path_authority.py
```

Result:

```text
125 passed in 15.21s
```

Additional env-gate / frontier evidence tests:

```text
python -m pytest -q -p no:randomly \
  src/tests/test_exact_outer_skip_unknown.py \
  src/tests/test_v63_terminal_evidence_contract.py
```

Result:

```text
23 passed in 2.37s
```

Proof-obligation anchor check:

```text
python scripts/check_p1_2_proof_obligations.py
```

Result:

```text
P1.2 proof obligation check passed: 8 obligations anchored
```

One-off probes run during review:

```text
frontier projection equivalence probe: 1000 randomized strict-mode cases passed
resume budget-clear ordering probe: stale final_result shapes rejected before stop clearing
CERTIFIED→CERTIFIED overwrite probe: terminal state becomes fail-closed on resume/public validation
terminal invariant probe: CERTIFIED final with non-CERTIFIED best record is rejected
```

I did not run the full `src/tests` suite because this checkout lacks the external `data/preprocessed/candidate_placements.json` artifact and I did not regenerate that 45 MB artifact for this state-machine-only review.

## Findings

No findings.

## Q1: terminal only replays the final solution, not every historical candidate record

Judgment: sound for this face under the declared trust boundary.

`terminal_certified_final_result_violation` proves the final result is internally terminal by requiring the final candidate record to still be `CERTIFIED`, requiring the persisted candidate solution to match `final_result.placement_solution`, and rejecting any other `CERTIFIED` candidate with a better objective (`src/search/exact_campaign.py:1672-1704`). It then delegates the full-domain closure check to terminal frontier evidence (`src/search/exact_campaign.py:1706-1715`, `src/search/certified_frontier.py:291-421`). Project-bound validation geometrically replays the final layout and scans that layout for a better empty rectangle (`src/search/exact_campaign.py:797-1050`).

It intentionally does not replay every historical `INFEASIBLE` or non-best `CERTIFIED` proof. Resume binds records to the current exact artifacts by exact artifact hash (`src/search/exact_campaign.py:1501-1504`), and the campaign state machine treats strong per-candidate outcomes as already certified by the subproblem stack. If a worker or cross-face proof produced a false `INFEASIBLE`, terminal completeness could be mathematically wrong, but that is a false subproblem certificate, not a persistence/resume state-machine escalation. The state machine is not making a stronger claim than “the full frontier is exhausted under the trusted candidate records.”

## Q2: CERTIFIED to CERTIFIED overwrite of `solution`

Judgment: no publishable false-CERTIFIED path found.

`mark_candidate_result` rejects contradictory strong statuses but allows same-status `CERTIFIED→CERTIFIED` and overwrites `record["solution"]` (`src/search/exact_campaign.py:2065-2073`, `src/search/exact_campaign.py:2130-2136`). The normal coordinator does not redispatch an already strong record: `mark_candidate_started` returns immediately for `CERTIFIED` / `INFEASIBLE` records (`src/search/exact_campaign.py:2008-2020`), and live frontier construction skips `CERTIFIED` candidates (`src/search/outer_search.py:631-647`, `src/search/outer_search.py:653-661`).

The dangerous shape was tested directly: start from a valid terminal state, then call `mark_candidate_result(6, 6, "CERTIFIED", solution=new_solution)` for the final candidate without recommitting terminal evidence. Resume validation rejects the state with `terminal_certified_final_result_solution_mismatch`, because the final result is compared against the current candidate record solution before the frontier evidence check (`src/search/exact_campaign.py:1687-1691`). `best_certified_result()` also refuses to publish unless project-bound terminal evidence is valid (`src/search/exact_campaign.py:2190-2195`), and manifest export routes publishable claims through the central verifier (`src/search/certified_surface.py:447-472`).

A direct API misuse can still save an invalid checkpoint because `save()` is an atomic writer, not a validator (`src/search/exact_campaign.py:2203-2206`). That invalid checkpoint is fail-closed on resume/export; I do not count it as a soundness finding under the coordinator-only writer contract.

## Q3: terminal projection versus live frontier construction

Judgment: strict-mode projection is equivalent to the live frontier logic.

The live strict frontier and terminal projection use the same three pruning rules in the same order:

1. skip explicit `CERTIFIED` / `INFEASIBLE`,
2. prune by certified containment,
3. prune by infeasible superset,
4. prune by objective `<= best_certified_candidate`,
5. build the undominated frontier by width/height containment and sort by objective.

Live code: `src/search/outer_search.py:631-693`.
Terminal projection: `src/search/certified_frontier.py:186-238`.

The apparent asymmetry is the `EXACT_OUTER_SKIP_UNKNOWN` env-gate, where live frontier can also skip `UNKNOWN` (`src/search/outer_search.py:650-655`). That mode is blocked from certified lifecycle at run entry (`src/search/outer_search.py:1703-1716`) and has explicit tests. In strict certified mode, `UNKNOWN`, `UNPROVEN`, `RUNNING`, missing records, and malformed non-mapping records all remain in potential domain unless pruned by the same certified/infeasible/objective rules. A randomized strict-mode probe compared `_compute_exact_frontier_state` to `compute_terminal_frontier_projection` across 1000 sparse/mixed record states and found no mismatch.

## Q4: resume does not geometrically replay non-terminal CERTIFIED records

Judgment: no new state-machine finding.

Resume schema validation for `CERTIFIED` records checks that `solution` is a mapping but does not geometry-replay it (`src/search/exact_campaign.py:1394-1469`). Those records are then used as explicit certified records by live frontier (`src/search/outer_search.py:631-647`) and projection (`src/search/certified_frontier.py:186-200`).

For a false non-best `CERTIFIED`, its derived pruning cannot hide a better terminal result: containment pruning and objective pruning only remove candidates with objective less than or equal to that certified candidate, and a strictly better final candidate dominates those by the published `max_lex(area, min_side)` objective. For a false best `CERTIFIED`, terminal commit/export must use that record as the best candidate and project-bound validation replays the final layout before publication (`src/search/exact_campaign.py:1728-1767`, `src/search/exact_campaign.py:797-1050`).

A false `INFEASIBLE` record can prune larger candidates and can therefore make a terminal frontier appear exhausted. That is the per-candidate proof trust boundary from Q1, not a resume-state asymmetry. Human checkpoint tampering or an old same-hash bad strong record remains an accepted provenance limitation, not a fresh r4 finding.

## Q5: crash atomicity and double coordinator last-writer-wins

Judgment: atomicity and terminal self-consistency remain fail-closed; no soundness finding.

The checkpoint write path writes a temp file in the target directory, JSON-dumps the full payload, flushes and fsyncs the file, replaces the destination with `os.replace`, and fsyncs the directory (`src/search/exact_campaign.py:1304-1318`). A crash can leave the old complete file, the new complete file, or a temp file that is ignored/cleaned. It does not create a half-old/half-new checkpoint.

No lockfile means two coordinators can overwrite each other’s progress. I rechecked the concrete false-CERTIFIED worry: terminal commit sets `final_result`, `final_status`, terminal stop reason, and terminal evidence, then validates project-bound terminal evidence before saving (`src/search/outer_search.py:853-879`). A state with `final_status=CERTIFIED` but the final candidate record no longer `CERTIFIED` is rejected by terminal validation before publication (`src/search/exact_campaign.py:1672-1686`).

If a stale second coordinator writes after a terminal checkpoint, it writes its own complete in-memory state. If that state is non-terminal, it rolls back progress but does not publish a certificate. If it is terminal, it must pass the same terminal validation before the normal terminal save path. Stale delivery artifacts are also guarded: blocker paths clear terminal state and artifacts (`src/search/outer_search.py:161-212`), delivery manifests require terminal evidence (`src/io/delivery_manifest.py:60-80`), and final delivery artifacts must match the campaign final result (`src/io/delivery_manifest.py:433-470`).

## Q6: time-budget resume clears stop only after validation

Judgment: no laundering window.

`load_or_create` validates the loaded state first (`src/search/exact_campaign.py:1835-1841`) and only then clears a `campaign_time_budget_exhausted` stop (`src/search/exact_campaign.py:1848-1855`). `_validate_resume_state` rejects `final_result != None` unless `final_status == "CERTIFIED"` before any such clearing can occur (`src/search/exact_campaign.py:1511-1518`). If `final_status` is `CERTIFIED` but the stop reason is time-budget rather than terminal full-frontier exhaustion, the state is a certified-looking export surface but not terminal evidence, so it is rejected as `terminal_certified_frontier_evidence_invalid` (`src/search/exact_campaign.py:1788-1804`).

The ordering probe confirmed both cases: `final_result + final_status=None + campaign_time_budget_exhausted` rejects as `final_status_mismatch`, and `final_result + final_status=CERTIFIED + campaign_time_budget_exhausted` rejects as `terminal_certified_frontier_evidence_invalid`.

## Final assessment

The campaign/resume state machine is sound for the reviewed face: persistence writes are atomic and whole-state, resume validation rejects stale terminal shapes before mutation, terminal evidence is equivalent to strict live frontier construction, and public certified export requires project-bound terminal evidence plus final-solution/manifest consistency. The remaining risk class is exactly the declared cross-face trust boundary: same-hash strong candidate records are trusted as already-correct subproblem results.
