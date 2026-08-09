# R4 response review execution record

**Document nature:** historical execution and validation record  
**Cutoff date:** 2026-07-23  
**Terminal status:** `COMPLETE_WITH_PARTIAL_ADMISSION`  
**Authoritative response run:** `.artifacts/track_b_r4_external_brain_handoff_20260722/responses/run-20260723T023657Z-R4resp-357f260d`

This file isolates execution history from the terminal interpretation in
[README.md](README.md). Commands were run from
`/home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721` with fixed
Python
`/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13`.

## Initial identity checks

The initial read-only checks returned:

```text
branch = codex/track-b-b0-1190-20260721
HEAD = 398f8725c770f3c36408adebe9448a890ed886fe
index = clean
package receipt replay = PASS
READY selected receipt replay = PASS
```

The three source reads matched:

```text
6885  357f260d8da002cca947822aece83e0183161fb1efd4348f1fccecab0afe374a  /home/zhuran24/下载/回复.txt
5268  88196c4ae9de07a05f5d50467baa36d934857842f4c37239ef7d735c69cf8700  /home/zhuran24/下载/r4_next_certificate.md
7184  d3169ba46fc55516cf047804d56ea568c867e4684a0ab0f912024d4f3c8644f6  /home/zhuran24/下载/r4_next_certificate.py
```

## Verbatim archive

One preliminary shell command attempted to redirect stdout into a child of the
not-yet-created response directory. The shell rejected the redirection before
Python started; it created no response run or canonical document. The
successful no-overwrite publication used the full fixed argument set below:

```bash
PY=/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13
AUTH=.artifacts/track_b_r4_external_brain_handoff_20260722/run-20260722T084343Z-R4hP1A
RESP=.artifacts/track_b_r4_external_brain_handoff_20260722/responses/run-20260723T023657Z-R4resp-357f260d

PYTHONDONTWRITEBYTECODE=1 "$PY" \
  docs/research/r4_response_review_20260723/archive_r4_response_bundle_v2.py archive \
  --authority-run "$AUTH" \
  --output-dir "$RESP" \
  --cleanroom-dir docs/research/cleanroom_rederivation_20260718 \
  --expected-package-id 1a1288a705e699b406d6636c56170f39cb2aecfce18337943e6114035b53369f \
  --expected-manifest-sha256 8097c4acb76fa90f20b8e48996d1a9a1e4d688758368a029395bb8e005669d4b \
  --expected-receipt-relative-path verifications/independent-a002-20260722T0845Z/receipt.json \
  --expected-receipt-size 13840 \
  --expected-receipt-sha256 cbbefb4d288e4f2e8f624f7f1b9f87c7f678622738184f831226b6436b0840f4 \
  --response-text /home/zhuran24/下载/回复.txt \
  --response-text-size 6885 \
  --response-text-sha256 357f260d8da002cca947822aece83e0183161fb1efd4348f1fccecab0afe374a \
  --certificate-markdown /home/zhuran24/下载/r4_next_certificate.md \
  --certificate-markdown-size 5268 \
  --certificate-markdown-sha256 88196c4ae9de07a05f5d50467baa36d934857842f4c37239ef7d735c69cf8700 \
  --certificate-python /home/zhuran24/下载/r4_next_certificate.py \
  --certificate-python-size 7184 \
  --certificate-python-sha256 d3169ba46fc55516cf047804d56ea568c867e4684a0ab0f912024d4f3c8644f6
```

Result: exit 0; one response run and cleanroom documents 12, 13, and 14 were
published. Reusing this command now correctly fails no-overwrite.

## Claim ledger

```bash
PYTHONDONTWRITEBYTECODE=1 "$PY" \
  docs/research/r4_response_review_20260723/build_r4_claim_ledger_v2.py \
  --authority-run "$AUTH" \
  --response-run "$RESP" \
  --output-dir "$RESP/claims"
```

Result: exit 0; 17 claims, each with one or more exact source-byte slices. The
external-code inspection records 160 physical lines and zero parsing,
compilation, import, execution, or network use.

## Recomputation attempts and authority set

The first immutable report set used runner SHA-256
`20c70ec2880c2b9fb85894cd0edc0a8df304e059b74193a400ddc4a7b6bbd96a`.
All numerical comparisons passed, but a subsequent fail-closed audit found
that the runner did not pin the original provenance constants or semantically
replay every report field. That runner was strengthened. Its reports remain
unchanged and are non-authoritative because the current runner bytes no longer
match them.

The authoritative `a002` runner is 35,480 bytes with SHA-256
`f903b711da4ba709b202a3074b89910cff9826cf5db0d54e618280630a634891`.
It ran:

```bash
LEDGER="$RESP/claims/quantitative-claim-ledger.json"

PYTHONDONTWRITEBYTECODE=1 "$PY" \
  docs/research/r4_response_review_20260723/run_r4_local_recomputation_bundle_v2.py \
  --authority-run "$AUTH" --response-run "$RESP" --claim-ledger "$LEDGER" \
  --checker-id upper_counts --profile strict_instance \
  --script docs/research/r4_response_review_20260723/independent_r4_upper_counts_v1.py \
  --output-dir "$RESP/recomputations/upper-counts-a002"

PYTHONDONTWRITEBYTECODE=1 "$PY" \
  docs/research/r4_response_review_20260723/run_r4_local_recomputation_bundle_v2.py \
  --authority-run "$AUTH" --response-run "$RESP" --claim-ledger "$LEDGER" \
  --checker-id marked_geometry --profile strict_instance \
  --script docs/research/r4_response_review_20260723/independent_r4_marked_geometry_v1.py \
  --output-dir "$RESP/recomputations/marked-geometry-a002"

PYTHONDONTWRITEBYTECODE=1 "$PY" \
  docs/research/r4_response_review_20260723/run_r4_local_recomputation_bundle_v2.py \
  --authority-run "$AUTH" --response-run "$RESP" --claim-ledger "$LEDGER" \
  --checker-id w2d_audit --profile w2d_authority \
  --script docs/research/r4_response_review_20260723/independent_r4_w2d_audit_v1.py \
  --output-dir "$RESP/recomputations/w2d-audit-a002"
```

All three commands returned exit 0 and `PASS_EXACT_MATCH`. The marked-geometry
enumeration took 2.43 seconds; the other two completed in under one second.
No solver or external-response code ran.

## Verdict and admission

The adversarial verdict was published only after replaying all three reports:

```bash
PYTHONDONTWRITEBYTECODE=1 "$PY" \
  docs/research/r4_response_review_20260723/build_r4_adversarial_verdict_v2.py \
  --authority-run "$AUTH" --response-run "$RESP" --claim-ledger "$LEDGER" \
  --recomputation-report "$RESP/recomputations/upper-counts-a002/report.json" \
  --recomputation-report "$RESP/recomputations/marked-geometry-a002/report.json" \
  --recomputation-report "$RESP/recomputations/w2d-audit-a002/report.json" \
  --output-dir "$RESP/adversarial/a002"
```

Result: exit 0, upper candidate `PASS`, witness suggestion
`NEEDS_PREREQUISITES`.

An initial `a002` admission correctly returned `PARTIAL`. The admission tool
was then extended to record its own detached byte identity; the immutable
`a002` output remains history. The authoritative admission command was:

```bash
PYTHONDONTWRITEBYTECODE=1 "$PY" \
  docs/research/r4_response_review_20260723/close_r4_response_candidate_admission_v2.py \
  --authority-run "$AUTH" --response-run "$RESP" --claim-ledger "$LEDGER" \
  --recomputation-report "$RESP/recomputations/upper-counts-a002/report.json" \
  --recomputation-report "$RESP/recomputations/marked-geometry-a002/report.json" \
  --recomputation-report "$RESP/recomputations/w2d-audit-a002/report.json" \
  --adversarial-verdict "$RESP/adversarial/a002/verdict.json" \
  --output-dir "$RESP/admission/a003"
```

Result: exit 0 and `PARTIAL`. The upper candidate is admitted only as a B1
follow-up input; the witness suggestion is not admitted. Every encoder,
formal, solver, search, assembly, router, and Track W execution flag is false.

## Final validation

The receipt verifier, READY selector, and response archive replay all returned
exit 0. Their terminal states were:

```text
package receipt: status=PASS, receipt_semantic_replay=true
READY selector: status=READY_FOR_MANUAL_EXTERNAL_SUBMISSION,
                receipt_byte_identity_match=true,
                receipt_semantic_replay=true
response archive: archive_complete=true,
                  all_raw_canonical_byte_equal=true,
                  external_bytes_executed=false
```

The focused validation used:

```bash
PYTHONDONTWRITEBYTECODE=1 "$PY" -m pytest -q \
  src/tests/test_r4_external_brain_handoff_v1.py \
  src/tests/test_r4_response_review_v2.py

PYTHONDONTWRITEBYTECODE=1 "$PY" \
  docs/research/cleanroom_rederivation_20260718/verify_r3_certificates.py

PYTHONDONTWRITEBYTECODE=1 "$PY" scripts/check_repo_secrets.py
```

Results:

```text
focused pytest: 43 passed in 0.34s
R3 replay: OK; stencil=396, placements=840, P>=9,
           excess=63, lex-max=(1190,34)
direct secret scan: 39,726 candidate text paths checked; passed
py_compile: exit 0 for all eight review tools and the focused test
Ruff check: all checks passed
Ruff format --check: 9 files already formatted
git diff --check: exit 0
```

The full repository gate used:

```bash
PREFLIGHT_TIMEOUT_SCALE=12 PYTHONDONTWRITEBYTECODE=1 "$PY" \
  scripts/preflight_gate.py --full
```

It returned exit 0:

```text
result: PASSED
preflight checks: 19 passed
pytest: 4,718 passed, 74 skipped in 94.89s
mypy: Success, 13 source files
Ruff: All checks passed
secret scan: 39,726 candidate text paths checked
```

## Process ownership

The three task subagents reported no MCP or auxiliary processes. No shared
Chrome/CDP, CodeGraph daemon, main Codex process, solver, or other user process
was terminated.

## Authority-chain replay closure

A later fail-closed replay audit found that the unnumbered ledger did not bind
its builder or require the complete fixed 17-claim semantics, and that
admission checked selected verdict fields instead of invoking the verdict
builder's complete read-only replay. The previous artifacts remain unchanged
as historical records. The replacement authority generation is uniformly
named `a004`.

The four authority-chain tools used for a004 were:

```text
36579  95bc53e24267c318e2584b9cf095afbc97becfc469f3e7b3f1ff500d55b7e597  build_r4_claim_ledger_v2.py
37243  8f569368cf163982486e341ee664640aeda1de7d5aef290e7a9449e329ea0df8  run_r4_local_recomputation_bundle_v2.py
19505  b414a9250e298f447796e4a5fa8f889efa275aef70d18e9c7626fefe294fbb6c  build_r4_adversarial_verdict_v2.py
17955  cf47cc662e3c3cf6e7e13915869866a09067854b837a5a775bdf8504dfd3f5d5  close_r4_response_candidate_admission_v2.py
```

Receipt semantic replay and READY detached-byte replay both passed immediately
before publication. The a004 chain was then published with:

```bash
LEDGER="$RESP/claims/a004/quantitative-claim-ledger.json"

PYTHONDONTWRITEBYTECODE=1 "$PY" \
  docs/research/r4_response_review_20260723/build_r4_claim_ledger_v2.py \
  --authority-run "$AUTH" --response-run "$RESP" \
  --output-dir "$RESP/claims/a004"

PYTHONDONTWRITEBYTECODE=1 "$PY" \
  docs/research/r4_response_review_20260723/run_r4_local_recomputation_bundle_v2.py \
  --authority-run "$AUTH" --response-run "$RESP" --claim-ledger "$LEDGER" \
  --checker-id upper_counts --profile strict_instance \
  --script docs/research/r4_response_review_20260723/independent_r4_upper_counts_v1.py \
  --output-dir "$RESP/recomputations/upper-counts-a004"

PYTHONDONTWRITEBYTECODE=1 "$PY" \
  docs/research/r4_response_review_20260723/run_r4_local_recomputation_bundle_v2.py \
  --authority-run "$AUTH" --response-run "$RESP" --claim-ledger "$LEDGER" \
  --checker-id marked_geometry --profile strict_instance \
  --script docs/research/r4_response_review_20260723/independent_r4_marked_geometry_v1.py \
  --output-dir "$RESP/recomputations/marked-geometry-a004"

PYTHONDONTWRITEBYTECODE=1 "$PY" \
  docs/research/r4_response_review_20260723/run_r4_local_recomputation_bundle_v2.py \
  --authority-run "$AUTH" --response-run "$RESP" --claim-ledger "$LEDGER" \
  --checker-id w2d_audit --profile w2d_authority \
  --script docs/research/r4_response_review_20260723/independent_r4_w2d_audit_v1.py \
  --output-dir "$RESP/recomputations/w2d-audit-a004"

PYTHONDONTWRITEBYTECODE=1 "$PY" \
  docs/research/r4_response_review_20260723/build_r4_adversarial_verdict_v2.py \
  --authority-run "$AUTH" --response-run "$RESP" --claim-ledger "$LEDGER" \
  --recomputation-report "$RESP/recomputations/upper-counts-a004/report.json" \
  --recomputation-report "$RESP/recomputations/marked-geometry-a004/report.json" \
  --recomputation-report "$RESP/recomputations/w2d-audit-a004/report.json" \
  --output-dir "$RESP/adversarial/a004"

PYTHONDONTWRITEBYTECODE=1 "$PY" \
  docs/research/r4_response_review_20260723/close_r4_response_candidate_admission_v2.py \
  --authority-run "$AUTH" --response-run "$RESP" --claim-ledger "$LEDGER" \
  --recomputation-report "$RESP/recomputations/upper-counts-a004/report.json" \
  --recomputation-report "$RESP/recomputations/marked-geometry-a004/report.json" \
  --recomputation-report "$RESP/recomputations/w2d-audit-a004/report.json" \
  --adversarial-verdict "$RESP/adversarial/a004/verdict.json" \
  --output-dir "$RESP/admission/a004"
```

Every command returned zero. Complete admission replay returned:

```text
claim_count=17
report_statuses=PASS_EXACT_MATCH,PASS_EXACT_MATCH,PASS_EXACT_MATCH
verdict_status=COMPLETE
admission_status=PARTIAL
current_project_ledger=U=(1190,34),L=absent
upper_bound_changed=false
upper_b1_followup_input_admitted=true
witness_track_w_followup_input_admitted=false
all_execution_authorizations=false
```

The immutable a004 identities are:

```text
5510   ff004391bef1962f5d4a848eed1397e70cd7a3d75385c31cb87d20063676bad8  claims/a004/external-code-inert-inspection.json
22770  897303dd26e307125575d4d107ba34c9ee05bf809abf894dbf54c48968654ccd  claims/a004/quantitative-claim-ledger.json
16986  710cb182b295470335375ab567be66833760c35fc494d12ea7d2998e92c1aa37  recomputations/upper-counts-a004/report.json
15502  954593d928bbe449b8b5a39f8788125294383073f0894c029dd1fbf87ae0bc7e  recomputations/marked-geometry-a004/report.json
12775  d37db9dabf42424de9140d40e149c663f291c7f6ac2795bb7f3258bd2148d48c  recomputations/w2d-audit-a004/report.json
10305  1f291629a39c5d3990d028276c7a9175b56a27b048ad4259e6a7913dfd17e633  adversarial/a004/verdict.json
10273  2ebceb7bcdf93ad8cffa75e49eef89af679729f64a47a06ae27fa44682c206ff  admission/a004/admission.json
```

Reusing the ledger and admission publication commands returned exit 2 with
their respective no-overwrite errors. The focused R4 suite, including
per-claim, coordinated downstream-tamper, candidate/global-field, and
four-producer path canaries, returned `160 passed`.

## Post-repair terminal validation

The authority-chain repair was validated on its final implementation and
documentation bytes with:

```bash
PYTHONDONTWRITEBYTECODE=1 "$PY" -m pytest -q \
  src/tests/test_r4_external_brain_handoff_v1.py \
  src/tests/test_r4_response_authority_chain_v2.py \
  src/tests/test_r4_response_review_v2.py

PYTHONDONTWRITEBYTECODE=1 "$PY" \
  docs/research/cleanroom_rederivation_20260718/verify_r3_certificates.py

PYTHONDONTWRITEBYTECODE=1 "$PY" scripts/check_repo_secrets.py

PREFLIGHT_TIMEOUT_SCALE=12 PYTHONDONTWRITEBYTECODE=1 "$PY" \
  scripts/preflight_gate.py --full
```

The terminal results were:

```text
focused R4 pytest: 160 passed
R3 replay: OK; stencil=396, placements=840, P>=9,
           excess=63, lex-max=(1190,34)
direct secret scan: 39,743 candidate text paths checked; passed
full preflight: PASSED; 19 checks passed
full pytest: 4,835 passed, 74 skipped
```

These checks do not change the `PARTIAL` admission, `U=(1190,34)`,
`L=absent`, or any execution authorization.
