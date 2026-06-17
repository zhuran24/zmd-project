# 10. Local merge reseal

Date: 2026-06-17

This file records the local merge of the V99 close-kernel package into the
current repository state after the follow-up F-CAM-R8-02 durable resume
sanitization fix.

## Why resealed

The downloaded V99 package sealed `src/search/exact_campaign.py` and
`src/search/outer_search.py` before the local F-CAM-R8-02 fix was merged. That
fix is still P1.2-scope because checkpoint-loaded strong candidate evidence must
be durably demoted and stale public proof surfaces must be cleared before proof
reuse.

The local merge keeps the F-CAM-R8-02 source changes and rebinds the V99
close-kernel manifest to the resulting source hashes.

## Rebound sinks

| path | local source_sha256 |
|---|---|
| `src/search/exact_campaign.py` | `2dea863944da6ee72e070fba98a737d41e992a50bf2bf6414f7d573a143d53b5` |
| `src/search/outer_search.py` | `2db84f7294742fd5859a7efd883865c89c630e3ceaa6408437e13a44e2aaf8bc` |

## Local verification

```text
$ python scripts/check_p1_2_proof_obligations.py
P1.2 proof obligation check passed: 9 obligations anchored; 50 proof-bearing sink files sealed

$ python scripts/check_phase_review_gate.py
phase_1_2_spike_close: status=blocked_manual_review_count, anchor=v99_p1_2_close_kernel_sealing, next_allowed=False, counting_authority=owner_manual_count_outside_repo

$ python -m pytest -q src/tests/test_p1_2_proof_obligations.py src/tests/test_phase_review_gate.py src/tests/test_delivery_manifest.py src/tests/test_exact_campaign_state_soundness.py
53 passed, 3 warnings
```

## Current claim boundary

This reseal does not change the V99 non-claims: it does not open P1.3B, satisfy
owner manual clean-review count, prove full-project bug absence, or claim future
production integration safety. It only records that the current local P1.2
technical close-kernel includes the follow-up resume-sanitization fix and still
fails closed under the V99 gate.
