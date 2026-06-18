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

## Local verification

```text
$ python scripts/check_p1_2_proof_obligations.py
P1.2 proof obligation check passed: 9 obligations anchored; 50 proof-bearing sink files sealed

$ python scripts/check_phase_review_gate.py
phase_1_2_spike_close: status=blocked_manual_review_count, anchor=v99_p1_2_close_kernel_sealing, next_allowed=False, counting_authority=owner_manual_count_outside_repo

$ python -m pytest -q -p no:randomly src/tests/test_p1_2_proof_obligations.py src/tests/test_phase_review_gate.py src/tests/test_delivery_manifest.py src/tests/test_exact_campaign_state_soundness.py src/tests/test_v100_public_surface_current_process_freshness.py
62 passed

$ python -m pytest -q src/tests/test_certified_exact_source_digest_surface.py src/tests/test_v100_public_surface_current_process_freshness.py src/tests/test_v102_candidate_result_producer_authority.py
10 passed

$ python -m pytest -q src/tests/test_exact_campaign_state_soundness.py src/tests/test_delivery_manifest.py src/tests/test_v63_terminal_evidence_contract.py src/tests/test_parallel_scheduler.py src/tests/test_v62_candidate_frontier_contract.py -p no:randomly --basetemp=.pytest_tmp_seq_campaign
92 passed
```

## Current claim boundary

This reseal does not change the V99 non-claims: it does not open P1.3B, satisfy
owner manual clean-review count, prove full-project bug absence, or claim future
production integration safety. It only records that the current local P1.2
technical close-kernel includes the follow-up resume-sanitization,
current-process freshness content-binding, verified strong-status producer
authority, and root-entrypoint source-digest fixes and still fails closed under
the V99 gate.
