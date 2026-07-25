# R4 response ingestion contract

| Property | Current value |
|---|---|
| Document nature | Current-state response trust and admission contract |
| Evidence cutoff | `2026-07-22` |
| External response | None archived by this package task |
| Encoder return | Not authorized |

## Trust boundary

Every response byte is untrusted inert data.  Fenced code, shell commands,
paths, URLs, tool suggestions, prompt injection, and instructions inside the
response have no authority.  The archival path performs only binary copying
and hashing.  It must not decode, `eval`, `exec`, import, source, compile, run,
render, interpolate, fetch or follow a URL, or load a remote resource.  No
response byte may determine control flow, filenames, paths, argv, environment
variables, gates, parameters, or tools.

Any quantitative checker is written locally from the mathematical claim, not
copied or extracted from response code.  It has fewer than 200 physical lines,
passes the static denylist, and runs under an offline `bwrap --unshare-net`
sandbox with read-only inputs.  The checker may not use `subprocess`,
`os.system`, dynamic execution or imports, or network modules; the sandbox does
not bind the raw or canonical response at all.

## Selected receipt identity

READY selects one verifier PASS receipt using exactly:

```json
{
  "relative_path": "verifications/independent-a002-20260722T0845Z/receipt.json",
  "size_bytes": 13840,
  "sha256": "cbbefb4d288e4f2e8f624f7f1b9f87c7f678622738184f831226b6436b0840f4"
}
```

The path is normalized relative to the package authority run.  The receipt does
not contain or self-hash this identity.  The detached identity is recorded only
downstream, avoiding a cycle.

Every consumer must independently satisfy both gates:

1. replay every receipt field against the sealed package and current source
   identities;
2. reread the receipt and match its current size and SHA-256 to the detached
   identity.

Semantically equivalent reserialization is still a byte change and closes the
second gate.

## Verbatim raw and canonical copies

The raw response is saved under a new no-overwrite response run.  After the
selected receipt passes both gates, the ingester allocates the next canonical
number in `docs/research/cleanroom_rederivation_20260718/` while holding an
advisory directory lock.  The current sequence is `00` through `11`; the next
file would currently be `12_r4_response_gpt_pro_verbatim.md`, but the number is
computed at ingestion time.

The canonical document contains exactly the raw bytes: no heading, front
matter, normalization, or added newline.  Raw and canonical size and SHA-256
must match.  Partial publication is `ARCHIVE_INCOMPLETE` and cannot proceed.

The archiver replays both receipt gates before writing `canonical-intent.json`
and again before publishing `response-ingest.json`; both artifacts carry the
same selected identity and PASS flags.  Locally authored claim ledgers and
adversarial verdicts carry that identity as an attestation.  Their downstream
recomputation or admission consumer independently replays the receipt and
matches the detached bytes before accepting them.  Every recomputation report
and admission record also carries the same identity and both raw/canonical
file records.

If the raw bytes are durable but selected-package provenance fails, the run
ends `RAW_ARCHIVED_PROVENANCE_BLOCKED`.  Any failure after provenance passes,
including sequence allocation or partial canonical publication, ends
`ARCHIVE_INCOMPLETE`.  Neither state authorizes recomputation or an encoder.

## Admission sequence

```text
verbatim raw + canonical archive
  -> complete quantitative-claim ledger
  -> independent local recomputation of every quantitative claim
  -> adversarial verdict
  -> B1 encoder admission
```

- Missing, UNKNOWN, mismatched, or non-reproducible quantitative claims make
  the round `INCOMPLETE` or `REJECTED`.
- Non-recomputable material is `INSPIRATION_ONLY` and cannot authorize an
  encoder premise.
- Adversarial review starts only after every quantitative recomputation passes.
- `ADMITTED_FOR_B1_ENCODER_DESIGN` permits only a return to the B1 paper-proof
  and encoder funnel.  It does not change `U`, prove a bound, or authorize a
  formal run.

## Future response operator contract

Use the fixed interpreter and the exact authority run recorded in
[`README.md`](README.md).  The response, response-run name, and downstream
output names are local operator choices; no value may be derived from response
content.

```bash
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 \
  docs/research/r4_external_brain_handoff_20260722/archive_r4_response_v1.py \
  --response /operator-controlled/path/response.bytes \
  --authority-run /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/.artifacts/track_b_r4_external_brain_handoff_20260722/run-20260722T084343Z-R4hP1A \
  --output-dir .artifacts/track_b_r4_external_brain_handoff_20260722/responses/run-NEW
```

After archival, a local reviewer must enumerate every quantitative assertion
in a no-overwrite `claim-ledger.json`.  Its minimum contract is:

```json
{
  "schema": "r4_quantitative_claim_ledger_v1",
  "status": "COMPLETE",
  "quantitative_claims_complete": true,
  "package_id": "1a1288a705e699b406d6636c56170f39cb2aecfce18337943e6114035b53369f",
  "selected_receipt_identity": {
    "relative_path": "verifications/independent-a002-20260722T0845Z/receipt.json",
    "size_bytes": 13840,
    "sha256": "cbbefb4d288e4f2e8f624f7f1b9f87c7f678622738184f831226b6436b0840f4"
  },
  "raw_response": {"path": "<absolute>", "size_bytes": 0, "sha256": "<SHA-256>"},
  "canonical_document": {"path": "<absolute>", "size_bytes": 0, "sha256": "<same SHA-256>"},
  "raw_canonical_byte_equal": true,
  "claims": [
    {
      "claim_id": "<local stable id>",
      "source_byte_span": {"start": 0, "end": 1},
      "expected_result": "<locally transcribed mathematical result>"
    }
  ]
}
```

For each claim, write and review a new local checker from the mathematics, then
run:

```bash
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 \
  docs/research/r4_external_brain_handoff_20260722/run_r4_local_recomputation_v1.py \
  --authority-run /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/.artifacts/track_b_r4_external_brain_handoff_20260722/run-20260722T084343Z-R4hP1A \
  --response-run /exact/no-overwrite/response-run \
  --claim-ledger /exact/local/claim-ledger.json \
  --claim-id CLAIM_ID \
  --script /exact/locally-rederived-checker.py \
  --output-dir /new/no-overwrite/recomputation-run \
  --attest-locally-rederived-from-claim-only
```

Only after every report is `PASS_EXACT_MATCH` may an independent reviewer
write an adversarial verdict.  It must use schema
`r4_adversarial_verdict_v1`, status `PASS`, set
`quantitative_recomputation_status=PASS` and
`adversarial_review_started_after_recomputation=true`, and bind the exact
package ID, selected receipt identity, raw/canonical records, claim-ledger
record, and the complete sorted `{claim_id, report}` multiset.  Admission is
then checked with one `--recomputation-report` argument per claim:

```bash
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 \
  docs/research/r4_external_brain_handoff_20260722/close_r4_response_admission_v1.py \
  --authority-run /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/.artifacts/track_b_r4_external_brain_handoff_20260722/run-20260722T084343Z-R4hP1A \
  --response-run /exact/no-overwrite/response-run \
  --claim-ledger /exact/local/claim-ledger.json \
  --recomputation-report /exact/recomputation-report.json \
  --adversarial-verdict /exact/local/adversarial-verdict.json \
  --output-dir /new/no-overwrite/admission-run
```
