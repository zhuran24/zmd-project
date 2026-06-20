# 10. Local merge reseal

Date: 2026-06-17

This file records the local merge of the V99 close-kernel package into the
current repository state after follow-up P1.2 close-kernel hardening.

## Why resealed

The downloaded V99 package sealed `src/search/exact_campaign.py` and
`src/search/outer_search.py` before later local P1.2 fixes were merged. Those
fixes are still P1.2-scope because checkpoint-loaded strong candidate evidence
must be durably demoted or freshly re-established, public proof surfaces must
not reuse stale candidate evidence, current-process freshness markers must bind
the strong candidate record content rather than only Python object identity, and
proof-bearing sink drift must invalidate certified-exact checkpoint source
digests.

The local merge keeps those source changes and rebinds the V99 close-kernel
manifest to the resulting source hashes.

## Rebound sinks

| path | local source_sha256 |
|---|---|
| `src/search/exact_campaign.py` | `5c58ab5eee45573e0fb9bd436108e90beef2169dd432f661598dd09588acd4bf` |
| `src/search/outer_search.py` | `2db84f7294742fd5859a7efd883865c89c630e3ceaa6408437e13a44e2aaf8bc` |

## 2026-06-18 no-close review follow-up reseal

The no-close-kernel adversarial review found two P1.2-scope gaps: public
candidate-result writes could self-mint proof-bearing strong-status freshness, and
the root entrypoint `main.py` was absent from the certified exact source digest.
The local merge keeps the fixes and rebinds the close-kernel manifest/checker floor
to the resulting source hashes.

| path | local source_sha256 |
|---|---|
| `src/search/exact_campaign.py` | `5f7fa05ec350f8e11c9dadf7f8a29d4a2e91cab03c9d216add043b8c176eeec2` |
| `src/search/outer_search.py` | `cedfeda25ebbaba3430e7a67721d8bc9d18fe097b24f860f6b05be80c91b0013` |
| `scripts/check_p1_2_proof_obligations.py` | `faff29ca767c1f2cd3beb30a338d750cef87d700be76f61cfd9658c5ef2e6cdb` |

## 2026-06-18 verified-producer authority reseal

The subsequent no-close-kernel adversarial round reproduced a direct P1.2
soundness blocker: an in-process caller could invoke the internal verified
producer writer, raw current-process freshness sealer, or importable freshness
registry, mark a better feasible candidate `INFEASIBLE`, and publish a smaller
`CERTIFIED` result through terminal frontier evidence, manifest export, and the
public certified surface.

The local fix makes public candidate-result writes always invalidate freshness,
turns the raw sealer into a fail-closed compatibility trap, and binds proof-bearing
strong-status freshness to the `run_outer_search` controller calling the verified
producer path. It also moves the mutable freshness registry behind a closure so
other project code cannot import and populate the proof-authority table directly.
This reseal rebinds the close-kernel manifest/checker floor to the resulting
source hashes.

| path | local source_sha256 |
|---|---|
| `src/search/exact_campaign.py` | `e503cbd09d5e01e3b4488d37964989b91586196e519e83bc6c4ca413b941d6b4` |
| `src/search/outer_search.py` | `b321e3986a32c29186f08c18f02482576f12218c522a355e7cded1fa114a3fce` |
| `scripts/check_p1_2_proof_obligations.py` | `f348bd2d020483d87b38aefbf56f52feef15eb2ca16131602d12364b5ca68a21` |

## 2026-06-18 source self-seal containment reseal

The next no-close-kernel adversarial review found that a locked project package
with the V99 manifest/checker removed could still mint a fresh campaign source
digest from the current tree. That made the source digest continuity evidence act
like a first-use self-seal instead of an authority check.

The local fix makes `compute_exact_artifact_hashes()` fail closed in locked
projects unless the V99 close-kernel manifest/checker pair exists as regular
non-symlinked files and the checker exits successfully. The guard lives in
`src/search/certified_artifact_contract.py`; that file is now a close-kernel
critical gate file and is pinned by the checker floor, while `exact_campaign.py`
is resealed as the proof-bearing campaign entrypoint that invokes the guard.

| path | local source_sha256 |
|---|---|
| `src/search/certified_artifact_contract.py` | `f3579bd9431c1d33b2a7820db39d8af523c484cc45146419150a25ec101a7b26` |
| `src/search/exact_campaign.py` | `d89dac1f403ef3a9dc2dffc3ed77eb9b7848c91e0c2ea2645145f89b361d910a` |
| `scripts/check_p1_2_proof_obligations.py` | `3fe91cc5eadb7b0f3ef62868c3f1930f3c37762b3df7fd9ed4a303caa9973f2f` |

## 2026-06-18 interim authority hardening reseal

The next adversarial review reproduced four concrete runtime authority paths:
mutable current-symbol producer identity, closure-extracted mutable freshness
registry, a shipped test helper patching the production grant guard, and frontier
pruning that used strong-looking candidate statuses before checking freshness.

The local interim hardening pins producer/writer authority at module definition
time, replaces the mutable freshness registry with live proof-bearing record
stamps, validates candidate freshness before frontier skip/prune use, and changes
the test helper to use a pytest-only adapter instead of patching production
freshness authority. This blocks the four concrete repros, but it is not a clean
P1.2 close: the review package also demonstrated that same-process closure-cell
mutation of the verified writer can still bypass the interim guard.

| path | local source_sha256 |
|---|---|
| `src/search/exact_campaign.py` | `5d86aa106abf827183850bec14ec63f2bba89c1b92bb0e8e593737994cdd6891` |
| `src/search/outer_search.py` | `495b78db6aeb4998de6880bdc817e355d8ece04879be2363752a50b127f58c0b` |
| `scripts/check_p1_2_proof_obligations.py` | `868c458f46f06481526e7ca7d41d63ef2e799572cd1e64ccc78349e4f534de29` |

Known residual:

```text
$ PYTHONPATH=. python <downloaded-review-package>/repro/zmd_closure_cell_attack.py <tmp-project>
surface_publishable=true, terminal_valid=true
```

## Local verification

```text
$ python scripts/check_p1_2_proof_obligations.py
P1.2 proof obligation check passed: 9 obligations anchored; 50 proof-bearing sink files sealed

$ python scripts/check_phase_review_gate.py
phase_1_2_spike_close: status=blocked_manual_review_count, anchor=v99_p1_2_close_kernel_sealing, next_allowed=False, counting_authority=owner_manual_count_outside_repo

$ python -m pytest -q -p no:randomly src/tests/test_p1_2_proof_obligations.py src/tests/test_phase_review_gate.py src/tests/test_delivery_manifest.py src/tests/test_exact_campaign_state_soundness.py src/tests/test_v100_public_surface_current_process_freshness.py
62 passed

$ python -m pytest -q src/tests/test_certified_exact_source_digest_surface.py src/tests/test_v100_public_surface_current_process_freshness.py src/tests/test_v102_candidate_result_producer_authority.py
12 passed

$ python -m pytest -q src/tests/test_exact_campaign_state_soundness.py src/tests/test_parallel_scheduler.py src/tests/test_v62_candidate_frontier_contract.py src/tests/test_delivery_manifest.py src/tests/test_delivery_manifest_compatibility_exports.py src/tests/test_pre_master_precheck_soundness_contract.py src/tests/test_boundary_port_precheck_soundness.py src/tests/test_v100_public_surface_current_process_freshness.py src/tests/test_v101_terminal_infeasible_surface_soundness.py src/tests/test_v102_candidate_result_producer_authority.py src/tests/test_certified_exact_source_digest_surface.py
102 passed, 3 warnings

$ python scripts/preflight_gate.py
PASSED; core gate 675 passed, 3 warnings

$ PYTHONPATH=. python <downloaded-review-package>/repro/repro_private_producer_patched.py
PermissionError: verified_candidate_producer_caller_not_run_outer_search

$ PYTHONPATH=. python <downloaded-review-package>/repro/repro_direct_freshness_patched.py
PermissionError: direct candidate freshness sealing is forbidden; use the verified producer path

$ PYTHONPATH=. python <downloaded-review-package>/repro/repro_registry_mutation_patched.py
ImportError: cannot import name '_candidate_freshness_bucket'
```

## 2026-06-20 ④b sink-replay isolation root-cure (closure-cell residual resolved)

The same-process closure-cell residual recorded above (the
`zmd_closure_cell_attack.py` repro printing `surface_publishable=true,
terminal_valid=true`) is now resolved at the root, not patched at the symptom.

Strong-status authority no longer lives in any same-process function, closure
cell, module binding, mutable registry, or freshness stamp. A proof-bearing
candidate status (`CERTIFIED` / `INFEASIBLE`) may prune certified frontier state
or enter terminal frontier evidence, manifest export, or the public certified
surface only after a fresh isolated `python -I` child recomputes the current
artifact/source bindings and replays that candidate through `certified_exact`
(`certified_exact_isolated_solver_replay_v1`). Missing, malformed, mismatched,
failed, or non-strong replay results are demoted to `UNPROVEN` or rejected. This
is sealed by obligation `PO-CANDIDATE-SINK-REPLAY-AUTHORITY` and its eight
regression tests, with the sink-replay boundary in
`src/search/candidate_proof_replay.py`, `src/search/certified_frontier.py`,
`src/search/exact_campaign.py`, `src/search/outer_search.py`,
`src/io/delivery_manifest.py`, and `src/search/certified_surface.py`. Because a
same-process writer can no longer mint authority, the earlier closure-cell repro
is now a non-authority data write rather than a publishable certified surface.
The "known residual" note above is therefore closed.

## 2026-06-20 C1 cut-island sink reclassification reseal

C1 口径 cleanup. The `src/cuts/*` cut-family mechanism (families / lifecycle /
oracles / helpers / cert schema) is a `NotImplementedError`-bearing stub island:
the real certified derivation path is `benders_loop → src.models.cut_manager →
src.models.exact_coordinate_master`, and those three import nothing from
`src.cuts`. Step 8 `apply_to_master` is not wired and is phase-gated to P1.3B.

Eight `src/cuts/*` sinks were previously mislabeled `p1_2_certified_path` in the
close-kernel manifest even though none sits on the live certified path. They are
reclassified to the already-allowed `out_of_scope_future_phase3b` classification
(semantics: future-scope, Step 8 integrates in P1.3B). They stay **registered**
sinks — each still carries proof-bearing tokens such as `INFEASIBLE` /
`proof-bearing`, so dropping them would surface as an unregistered-sink failure —
only the `classification` field changed. Their `obligation_id` values are
unchanged. The reclassified sinks are:

| path | obligation_id | before → after classification |
|---|---|---|
| `src/cuts/cert_schema.py` | PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS | p1_2_certified_path → out_of_scope_future_phase3b |
| `src/cuts/families/pattern_nogood.py` | PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS | p1_2_certified_path → out_of_scope_future_phase3b |
| `src/cuts/helpers/bounded_core_minimizer.py` | PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS | p1_2_certified_path → out_of_scope_future_phase3b |
| `src/cuts/lifecycle.py` | PO-STEP7-ATTACH-MIRROR | p1_2_certified_path → out_of_scope_future_phase3b |
| `src/cuts/oracles/pattern_nogood_oracle.py` | PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS | p1_2_certified_path → out_of_scope_future_phase3b |
| `src/cuts/oracles/power_cover_oracle.py` | PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS | p1_2_certified_path → out_of_scope_future_phase3b |
| `src/cuts/oracles/region_capacity_oracle.py` | PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS | p1_2_certified_path → out_of_scope_future_phase3b |
| `src/cuts/oracles/shape_packing_hall_oracle.py` | PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS | p1_2_certified_path → out_of_scope_future_phase3b |

The change touched `data/proof_obligations/p1_2_proof_obligations.json` (the eight
`classification` fields) and the matching checker floor
`CLOSE_KERNEL_V99_REQUIRED_SINK_CLASSIFICATION_BY_PATH` in
`scripts/check_p1_2_proof_obligations.py`. Editing the checker drifts its own
registered `source_sha256`, so the manifest sink entry for
`scripts/check_p1_2_proof_obligations.py` is resealed. No live-path sink was
touched: `src/models/cut_manager.py`, `src/models/exact_coordinate_master.py`,
`src/search/benders_loop.py`, and the other `src/models/*` / `src/search/*`
certified-path sinks remain `p1_2_certified_path`.

| path | local source_sha256 |
|---|---|
| `scripts/check_p1_2_proof_obligations.py` | `a0849188ad6571dba5422495a3092a4eceb071081725b708f772627de005be66` |

After this reseal the close-kernel inventory is **52 proof-bearing sinks** under
**10 obligations** (the sink floor `CLOSE_KERNEL_V99_MIN_SINK_COUNT` is unchanged
because no sink was removed). Current classification distribution:
`p1_2_certified_path` 23, `non_authoritative_projection` 11,
`out_of_scope_future_phase3b` 8, `p1_2_public_surface` 6,
`diagnostic_or_telemetry_non_authority` 2,
`exploratory_or_heuristic_non_authority` 1, `p1_2_close_kernel` 1.

## Current claim boundary

This reseal does not change the V99 non-claims: it does not open P1.3B, satisfy
owner manual clean-review count, prove full-project bug absence, or claim future
production integration safety. It only records that the current local P1.2
technical close-kernel includes the follow-up resume-sanitization,
current-process freshness content-binding, controller-bound verified strong-status
producer authority, hidden freshness-registry authority, raw-sealer fail-closed
behavior, root-entrypoint source-digest fixes, source self-seal containment, the
interim authority hardening above, the ④b sink-replay isolation root-cure that
resolves the same-process closure-cell residual, and the C1 cut-island sink
reclassification. The earlier same-process closure-cell residual is now resolved
by sink-side isolated replay; checker success after this reseal still does not by
itself constitute a clean P1.2 close claim, which remains an owner manual decision.
